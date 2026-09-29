"""Deep read: a staged source's whole text, chunk by chunk - V1's lens scan
and whole-document reading, on V2's clerk channel and staging."""
import pytest

from resource_librarian import clerk, deep_read, tools  # noqa: F401  (registers tools)
from resource_librarian.lenses import LensStore
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.staging import StagingStore

from conftest import blind_answer
from test_intake import clerk_answers

STANCE = ("Before asking what broke, the engineer asks which load path failed, because a "
          "structure fails where force has nowhere else to go.")
LIMIT = "This method only holds when the loads are static."
BOOK = "\n\n".join([
    "Bridges carry loads across a gap by routing force into the ground.",
    STANCE,
    "Steel trusses spread a load across many members. " + LIMIT,
    "Cable-stayed bridges hang the deck from towers with straight cables.",
    "Suspension bridges hang the deck from main cables slung between towers.",
])


def chunk_of(payload: dict) -> str:
    return payload["user"].split("---\n", 1)[1].rsplit("\n---", 1)[0]


def answers(payload: dict):
    task, text = payload["task"], chunk_of(payload)
    if task == "points":
        return {"bullets": [text.split(".")[0].strip()]}
    if task == "limits":
        return {"bullets": [LIMIT.rstrip(".")] if LIMIT in text else []}
    if task == "terms":
        return {"terms": []}
    if task == "lens_perspective":
        if "load path" in text:
            return {"has_perspective": True, "name": "Load path first",
                    "explanation": "failure is read as where force had nowhere to go",
                    "source_quote": STANCE}
        return {"has_perspective": False, "name": "", "explanation": "", "source_quote": ""}
    if task == "lens_attention":
        return {"attends_to": [{"what": "where force is routed", "because": STANCE}],
                "deprioritizes": ["cosmetic damage"]}
    if task == "lens_discriminate":
        return blind_answer(payload, "Load path first", STANCE)
    if task == "lens_role":
        return {"role_purpose": "trace a failure to the path force took",
                "role_capabilities": ["statics"], "role_expectations": ["names the member"],
                "transfers_to": ["choosing which server to patch first during an incident",
                                 "deciding which surgical approach to try first"]}
    if task == "lens_probe":
        return {"probes": [{"question": "which member had nowhere left to send the force?",
                            "because": STANCE}],
                "catches": "blaming the first visible damage instead of the load path",
                "applies_when": "on structural failure analysis",
                "not_when": "on cosmetic damage inspection"}
    if task == "lens_synthesize":
        return {"prompt_fragment": "Before judging what failed, trace where force had to go."}
    return clerk_answers(payload)


@pytest.fixture
def staged(vault, monkeypatch):
    """A text file in Inbox/, ingested; chunks small enough to make four."""
    monkeypatch.setattr(deep_read, "CHUNK_CHARS", 160)
    (vault.root / "Inbox").mkdir(exist_ok=True)
    (vault.root / "Inbox" / "Bridges.txt").write_text(BOOK, encoding="utf-8")
    endpoint = clerk.Scripted(answers)
    ctx = Context(tier="curate", vault=vault, extras={"clerk": endpoint})
    out = REGISTRY.call("ingest", {"ref": "Inbox/Bridges.txt"}, ctx)
    assert out["status"] == "staged", out
    return ctx, out["item"]


def test_chunks_keep_whole_paragraphs_and_their_pages():
    units = [(1, "One short paragraph.\n\nAnother on page one."), (2, "Page two's own text.")]
    chunks = deep_read.chunk(units, size=45)
    assert [c.text for c in chunks] == ["One short paragraph.\n\nAnother on page one.",
                                        "Page two's own text."]
    assert [c.locator for c in chunks] == ["p. 1", "p. 2"]
    assert deep_read.chunk([(0, "no pages here")])[0].locator == "part 1"
    long = deep_read.chunk([(3, "A sentence. " * 20)], size=50)
    assert len(long) > 1 and all(len(c.text) <= 50 for c in long)


def test_deep_read_reads_everything_and_stages_the_lens(staged):
    ctx, item_id = staged
    out = REGISTRY.call("deep_read", {"item_id": item_id, "max_chunks": 20}, ctx)
    assert "error" not in out, out
    assert out["chunks"] == 4 and out["read"] == 4 and out["remaining"] == 0
    assert len(out["lenses_staged"]) == 1

    item = StagingStore(ctx.vault).load(item_id)
    claims = item["sections"]["Claims"]
    assert "Cable-stayed bridges hang the deck from towers" in claims        # the last chunk
    assert "(p. 1)" in claims
    assert "only holds when the loads are static" in item["sections"]["Evidence & Limits"]

    lens = StagingStore(ctx.vault).load(out["lenses_staged"][0])
    assert lens["kind"] == "lens" and lens["name"] == "Load path first"
    assert lens["source_quote"] == STANCE and lens["source_item"] == item_id
    assert lens["prompt_fragment"].startswith("Before judging")

    decided = REGISTRY.call("staging_decide", {"item_ids": [lens["id"]],
                                               "decision": "accept"}, ctx)
    assert decided["accepted"] == 1, decided
    assert LensStore(ctx.vault).get(decided["results"][0]["lens"])["role_purpose"]

    again = REGISTRY.call("deep_read", {"item_id": item_id}, ctx)
    assert again["this_call"] == 0 and again["lenses_total"] == 1        # nothing twice


def test_deep_read_is_bounded_and_resumes(staged):
    ctx, item_id = staged
    first = REGISTRY.call("deep_read", {"item_id": item_id, "max_chunks": 2}, ctx)
    assert first["read"] == 2 and first["remaining"] == 2
    second = REGISTRY.call("deep_read", {"item_id": item_id, "max_chunks": 2}, ctx)
    assert second["read"] == 4 and second["remaining"] == 0


def test_an_ungrounded_stance_is_never_staged(staged):
    ctx, item_id = staged

    def invented(payload):
        if payload["task"] == "lens_perspective" and "load path" in chunk_of(payload):
            return {"has_perspective": True, "name": "Invented", "explanation": "x",
                    "source_quote": "words that appear nowhere in the passage at all"}
        return answers(payload)
    ctx.extras["clerk"] = clerk.Scripted(invented)
    out = REGISTRY.call("deep_read", {"item_id": item_id, "max_chunks": 20}, ctx)
    assert out["lenses_staged"] == [] and out["read"] == 4


def test_with_no_clerk_the_tasks_wait_and_nothing_counts_as_read(staged, monkeypatch):
    ctx, item_id = staged
    ctx.extras.pop("clerk")
    out = REGISTRY.call("deep_read", {"item_id": item_id, "max_chunks": 2}, ctx)
    assert out["read"] == 0 and out["waiting_on_clerk"] == 2
    assert list((ctx.vault.work("queue") / "clerk").glob("*.json"))


# -- intake itself reads better ------------------------------------------------

def add_topic(vault, name: str) -> None:
    path = vault.root / "About" / "Topics.md"
    path.write_text(path.read_text(encoding="utf-8").rstrip("\n") +
                    f"\n| {name} | a subject accepted by a person |\n", encoding="utf-8")


def ingest_bridges(vault, answer=answers):
    (vault.root / "Inbox").mkdir(exist_ok=True)
    (vault.root / "Inbox" / "Bridges.txt").write_text(BOOK, encoding="utf-8")
    ctx = Context(tier="curate", vault=vault, extras={"clerk": clerk.Scripted(answer)})
    out = REGISTRY.call("ingest", {"ref": "Inbox/Bridges.txt"}, ctx)
    assert out["status"] == "staged", out
    return ctx, out["item"]


def test_a_documents_claims_earn_search_credit_and_its_limits_are_kept(vault):
    ctx, item_id = ingest_bridges(vault)
    item = StagingStore(vault).load(item_id)
    assert "Claims" in item["sections"]                      # a claim section, not a caveat
    assert "Reading Notes" not in item["sections"]
    assert "only holds when the loads are static" in item["sections"]["Evidence & Limits"]
    assert ctx.extras["engine"].index.model.section_role("Claims") == "claim"


def test_intake_picks_a_topic_from_the_accepted_list(vault):
    add_topic(vault, "Engineering")
    assert vault.topics() == ["Unfiled", "Engineering"]

    def with_topic(payload):
        if payload["task"] == "topic":
            return {"topic": "Engineering", "evidence": "Bridges carry loads across a gap",
                    "confident": True}
        return answers(payload)
    ctx, item_id = ingest_bridges(vault, with_topic)
    assert StagingStore(vault).load(item_id)["topic"] == "Engineering"
    result = REGISTRY.call("staging_decide", {"item_ids": [item_id], "decision": "accept"},
                           ctx)["results"][0]
    note = (vault.root / result["promotion"]["path"]).read_text(encoding="utf-8")
    assert "primary_topic: Engineering" in note


def test_a_persons_topic_correction_wins_and_must_be_accepted_first(vault):
    ctx, item_id = ingest_bridges(vault)                   # only Unfiled: no topic task
    refused = REGISTRY.call("staging_decide", {"item_ids": [item_id], "decision": "accept",
                                               "fields": {"primary_topic": "Engineering"}}, ctx)
    assert "not an accepted topic" in refused["results"][0]["error"]
    add_topic(vault, "Engineering")
    result = REGISTRY.call("staging_decide", {"item_ids": [item_id], "decision": "accept",
                                              "fields": {"primary_topic": "Engineering"}},
                           ctx)["results"][0]
    note = (vault.root / result["promotion"]["path"]).read_text(encoding="utf-8")
    assert "primary_topic: Engineering" in note          # was silently Unfiled before


def test_a_repository_is_asked_every_axis_code_could_not_read(vault, monkeypatch):
    from test_intake import RESPONSES
    from resource_librarian import facts, intake
    # Code reads only the licence here, so everything else is the clerk's to answer.
    monkeypatch.setattr(facts, "derive_axes", lambda *a, **k: {"license_class": "Permissive"})
    asked = []

    def recording(payload):
        asked.append(payload["task"])
        return answers(payload)
    ctx = Context(tier="curate", vault=vault, extras={"clerk": clerk.Scripted(recording),
                                                      "fetcher": intake.Replay(RESPONSES)})
    staged = REGISTRY.call("ingest", {"ref": "acme/rowstream"}, ctx)
    item = StagingStore(vault).load(staged["item"])
    asked_axes = {t[5:] for t in asked if t.startswith("axis:")}
    permitted = ctx.extras["engine"].index.model.axes_for("source", "repository")
    askable = {a for a, values in permitted.items()
               if values and a not in ("status", "attested_by")}
    # Every axis is either read by code or asked of the clerk - not just the four V2 used to ask.
    assert askable <= set(item["fields"]) | asked_axes, askable - set(item["fields"]) - asked_axes
    assert {"maturity_stage", "hardware_footprint", "agent_surface"} <= asked_axes  # V1 asked these
    assert not asked_axes & {"status", "attested_by", "license_class"}
    assert "limits" in asked


def test_a_local_model_reads_one_part_per_call(vault, monkeypatch):
    """Local models are slow; a call on one stays under ten minutes by reading
    one part at a time, and the read resumes on the next call."""
    from resource_librarian import deep_read as reading

    class LocalScripted(clerk.Scripted):
        base_url = "http://127.0.0.1:1234/v1"
    assert clerk.is_local(LocalScripted(answers)) and not clerk.is_local(clerk.Scripted(answers))
    assert not clerk.is_local(clerk.OpenAICompatible("https://api.deepinfra.com/v1/openai", "m"))
    monkeypatch.setattr(reading, "CHUNK_CHARS", 200)
    (vault.root / "Inbox").mkdir(exist_ok=True)
    (vault.root / "Inbox" / "Long.txt").write_text(
        "\n\n".join(f"Paragraph {i} says something about bridges and loads." * 3
                    for i in range(4)), encoding="utf-8")
    ctx = Context(tier="curate", vault=vault, extras={"clerk": LocalScripted(answers)})
    item = REGISTRY.call("ingest", {"ref": "Inbox/Long.txt"}, ctx)["item"]
    first = REGISTRY.call("deep_read", {"item_id": item, "max_chunks": 12}, ctx)
    assert first["this_call"] == 1 and first["remaining"] > 0 and "local model" in first["note"]
    second = REGISTRY.call("deep_read", {"item_id": item, "max_chunks": 12}, ctx)
    assert second["read"] == 2


# ------------------------------------ roadmap §4 C2: deep-reading an accepted source

def _accepted(ctx, item_id) -> str:
    out = REGISTRY.call("staging_decide", {"item_ids": [item_id], "decision": "accept",
                                           "bottom_line": "A short book about bridges.",
                                           "what_it_solves": "How bridges carry loads."}, ctx)
    assert out["accepted"] == 1, out
    return out["results"][0]["promotion"]["path"]


def test_an_accepted_source_is_deep_read_as_a_revision_the_person_merges(staged):
    from resource_librarian import notes as note_io
    ctx, item_id = staged
    path = _accepted(ctx, item_id)                         # accepted after only a skim
    name = note_io.load(ctx.vault.root / path).name
    before = (ctx.vault.root / path).read_text(encoding="utf-8")
    out = REGISTRY.call("deep_read_note", {"note": name, "max_chunks": 20}, ctx)
    assert "error" not in out, out
    assert out["of"] == path and out["read"] == out["chunks"]
    assert (ctx.vault.root / path).read_text(encoding="utf-8") == before   # note untouched
    revision = StagingStore(ctx.vault).load(out["revision"])
    assert revision["revision_of"] == path and "Cable-stayed" in revision["sections"]["Claims"]
    again = REGISTRY.call("deep_read_note", {"note": name}, ctx)
    assert again["revision"] == out["revision"]                           # resumes, one revision

    done = REGISTRY.call("staging_decide", {"item_ids": [out["revision"]],
                                            "decision": "accept"}, ctx)
    assert done["results"][0]["merged_into"] == path
    merged = note_io.load(ctx.vault.root / path)
    assert "Cable-stayed bridges hang the deck" in merged.sections()["Claims"]
    assert merged.frontmatter["deep_read"]
    kept = StagingStore(ctx.vault).load(out["revision"])
    assert "Claims" in kept["previous_sections"]                        # undo is possible


def test_rejecting_a_revision_leaves_the_accepted_note_and_its_file_alone(staged):
    from resource_librarian import notes as note_io
    ctx, item_id = staged
    path = _accepted(ctx, item_id)
    note = note_io.load(ctx.vault.root / path)
    out = REGISTRY.call("deep_read_note", {"note": note.name, "max_chunks": 20}, ctx)
    before = (ctx.vault.root / path).read_text(encoding="utf-8")
    attached = note.frontmatter.get("file")
    REGISTRY.call("staging_decide", {"item_ids": [out["revision"]], "decision": "reject",
                                     "reason": "not needed"}, ctx)
    assert (ctx.vault.root / path).read_text(encoding="utf-8") == before
    if attached:
        assert (ctx.vault.root / attached).is_file()                   # not quarantined


def test_a_model_cannot_merge_a_revision_into_a_persons_note(staged):
    ctx, item_id = staged
    path = _accepted(ctx, item_id)
    from resource_librarian import notes as note_io
    name = note_io.load(ctx.vault.root / path).name
    out = REGISTRY.call("deep_read_note", {"note": name, "max_chunks": 20}, ctx)
    model = Context(tier="contribute", vault=ctx.vault, extras=ctx.extras)
    done = REGISTRY.call("staging_decide", {"item_ids": [out["revision"]], "decision": "accept"},
                         model)
    assert done["results"][0].get("refused") == "PERSON_CONFIRMS"


# ------------------------------------------------ C4: the document-level pass

DOC_STANCE = {"name": "Force-routing reading",
              "explanation": "every structure is read by where it routes force into the ground",
              "claims": ["C1", "C3"],
              "catches": "judging a bridge by its look instead of where its force goes",
              "applies_when": "comparing structures", "not_when": "on finishes",
              "prompt_fragment": "Read each structure by where it routes force into the ground."}


def document_answers(stance=DOC_STANCE, probes=({"probe": "L1.P1", "claim": "C3"},)):
    def answer(payload):
        task = payload["task"]
        if task == "lens_document":
            return {"stances": [stance]}
        if task == "lens_support":
            return {"quote": chunk_of(payload).split(".")[0].strip() + "."}
        if task == "probe_answers":
            return {"answered": list(probes)}
        return answers(payload)
    return answer


def read_all(vault, item, answer):
    return deep_read.deep_read(vault, item, clerk.Scripted(answer), max_chunks=20)


def test_a_stance_across_parts_is_staged_with_quotes_from_two_parts(staged, vault):
    ctx, item = staged
    out = read_all(vault, item, document_answers())
    assert out["remaining"] == 0
    assert out["document"]["proposed"] == 1 and "status" not in out["document"]
    [lens_id] = out["document"]["staged"]
    lens = StagingStore(vault).load(lens_id)
    assert lens["level"] == "document" and lens["name"] == "Force-routing reading"
    assert len({q["quote"] for q in lens["quotes"]}) >= 2      # the source's own words, twice
    assert any("routing force into the ground" in r for r in lens["rests_on"])
    assert lens["trace"]["document"] and lens["provenance"]
    # Question resolution: the per-part lens's probe is answered by another part.
    load_path = next(x for x in StagingStore(vault).items(kind="lens")
                     if x["name"] == "Load path first")
    assert load_path["probes"][0]["confirmed_by"]["claim"].startswith("Steel trusses")
    assert out["document"]["probes_confirmed"] == 1


def test_the_pass_runs_once_per_text(staged, vault):
    ctx, item = staged
    read_all(vault, item, document_answers())
    again = read_all(vault, item, document_answers())
    assert "document" not in again
    assert StagingStore(vault).load(item)["deep_read"]["document"]["chunks"] >= 3


def test_a_stance_resting_on_one_part_is_discarded(staged, vault):
    ctx, item = staged
    one_part = {**DOC_STANCE, "claims": ["C1", "C1"]}
    out = read_all(vault, item, document_answers(stance=one_part, probes=()))
    assert out["document"]["staged"] == []
    reasons = [d["reason"] for d in StagingStore(vault).load(item)["deep_read"]["discards"]]
    assert any("fewer than two parts" in r for r in reasons)


def test_a_refused_document_answer_is_said_not_taken_for_none(staged, vault):
    ctx, item = staged

    def refused(payload):
        if payload["task"] == "lens_document":
            return {"not": "the shape asked for"}
        return document_answers()(payload)
    out = read_all(vault, item, refused)
    assert out["document"]["proposed"] == 0 and out["document"]["status"] == "refused"


def test_a_probe_answered_only_in_its_own_part_is_not_confirmed(staged, vault):
    ctx, item = staged
    out = read_all(vault, item, document_answers(probes=({"probe": "L1.P1", "claim": "C2"},)))
    assert out["document"]["probes_confirmed"] == 0
