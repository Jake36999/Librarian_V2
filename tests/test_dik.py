"""Requirements Addendum R16 (2026-09-30); Research Pipeline §3; plan P6: Data, Information,
Knowledge.

Data: one record per component, with its locator, revision, method, origin and status.
Information: typed edges citing the Data they join, saying their basis - static structure is
never called runtime behaviour, and nothing is related to a chapter not read. Knowledge: the
source note, each section labelled with where its claims come from."""
from resource_librarian import clerk, dik, intake, notes, tools  # noqa: F401
from resource_librarian.evidence import EvidenceStore
from resource_librarian.registry import REGISTRY, Context

from test_intake import RESPONSES, clerk_answers


def repo_evidence(vault):
    store = EvidenceStore(vault)
    ids = [
        store.put("survey", "https://github.com/acme/planner",
                  {"paths": ["planner/__init__.py", "planner/core.py", "planner/util.py",
                             "planner/api.py", "tests/test_core.py", "README.md"],
                   "tree_sha": "abc123"}).id,
        store.put("code_structure", "https://github.com/acme/planner (shallow clone)",
                  {"languages": {"python": 4}, "modules": [
                      {"file": "planner/core.py", "symbols": ["def plan"]},
                      {"file": "planner/util.py", "symbols": ["def cost"]},
                      {"file": "planner/api.py", "symbols": ["def serve"]}],
                   "imports": [{"file": "planner/core.py", "imports": [".util", "numpy"]},
                               {"file": "planner/api.py", "imports": ["planner.core", "fastapi"]}]}
                  ).id,
        store.put("access_point", "https://github.com/acme/planner (shallow clone)",
                  {"entry_points": [{"kind": "console script", "name": "planner",
                                     "target": "planner.api:main", "file": "planner/api.py"}],
                   "routes": [{"path": "/plan", "method": "POST", "file": "planner/api.py"}],
                   "environment": [{"name": "PLANNER_TOKEN", "file": "planner/api.py",
                                    "credential": True}]}).id]
    return ids


def test_a_repositorys_data_and_information_come_from_its_evidence(vault):
    record = dik.repository(vault, "acme - planner", repo_evidence(vault))
    kinds = {d["kind"] for d in record["data"]}
    assert {"file", "module", "language", "entry_point", "endpoint", "setting",
            "dependency"} <= kinds
    module = next(d for d in record["data"] if d["id"] == "module:planner/core.py")
    assert module["revision"] == "abc123" and module["origin"] == "observed"
    assert module["method"].startswith("static structure") and module["evidence"]
    edges = {(e["type"], e["from"], e["to"]): e for e in record["information"]}
    assert ("imports", "module:planner/core.py", "module:planner/util.py") in edges   # .util
    assert ("imports", "module:planner/api.py", "module:planner/core.py") in edges    # dotted
    assert ("depends_on", "module:planner/core.py", "dependency:numpy") in edges
    assert ("exposes", "module:planner/api.py", "endpoint:POST /plan") in edges
    assert ("reads", "module:planner/api.py", "setting:PLANNER_TOKEN") in edges
    tests = edges[("tests", "file:tests/test_core.py", "module:planner/core.py")]
    assert tests["status"] == "inferred" and tests["basis"] == "file names"
    assert all(e["cites"] == [e["from"], e["to"]] for e in record["information"])
    assert all("runtime" not in e["basis"] for e in record["information"])


def test_the_repository_note_labels_its_components_and_relations(vault):
    record = dik.repository(vault, "acme - planner", repo_evidence(vault))
    out = dik.sections(record)
    assert "`planner/core.py` - def plan *(structurally observed)*" in out["Components"]
    assert "Read at `abc123`" in out["Components"]
    assert "static structure" in out["How It Fits Together"]
    assert "nothing here was observed running" in out["How It Fits Together"]


BOOK = [["Chapter 1: Why plans fail", "Plans fail when estimates are anchored."],
        ["More on anchoring and its causes in estimation."],
        ["Chapter 2: Estimating well", "Reference classes reduce anchoring."],
        ["Chapter 3: Keeping plans honest", "Reviews should compare plan and outcome."]]


def pages():
    return ["\n".join(p) for p in BOOK]


def test_a_documents_chapters_carry_their_coverage_and_claims(vault):
    # four pages, one chunk per page; the reader read pages 1-3 (chapters 1 and 2)
    read = {"0": {"points": ["Plans fail when estimates are anchored."]},
            "1": {"points": ["Anchoring has causes."]},
            "2": {"points": ["Reference classes reduce anchoring."]}}
    record = dik.document(vault, "Planning Book", pages(), read,
                          [(1, 1), (2, 2), (3, 3), (4, 4)], "2026-09-30")
    chapters = {d["name"]: d for d in record["data"]}
    assert list(chapters) == ["Chapter 1: Why plans fail", "Chapter 2: Estimating well",
                              "Chapter 3: Keeping plans honest"]
    assert chapters["Chapter 1: Why plans fail"]["locator"] == "pp. 1-2"
    assert chapters["Chapter 1: Why plans fail"]["coverage"] == "full"
    assert chapters["Chapter 3: Keeping plans honest"]["coverage"] == "not opened"
    assert chapters["Chapter 3: Keeping plans honest"]["status"] == "not examined"
    assert record["coverage"] == "partial: 2 of 3 chapters opened"
    assert [e["type"] for e in record["information"]] == ["precedes", "precedes"]


def test_chapters_are_related_only_when_both_were_read(vault, tmp_path):
    read = {"0": {"points": ["Plans fail when estimates are anchored."]},
            "1": {"points": ["Anchoring has causes."]},
            "2": {"points": ["Reference classes reduce anchoring."]}}
    record = dik.document(vault, "Planning Book", pages(), read,
                          [(1, 1), (2, 2), (3, 3), (4, 4)], "2026-09-30")

    def answers(payload):
        assert "Keeping plans honest" not in payload["user"]            # unread: not offered
        return {"relations": [
            {"from": "chapter:pp. 1-2", "to": "chapter:pp. 3-3", "type": "prepares",
             "why": "anchoring, then its remedy"},
            {"from": "chapter:pp. 3-3", "to": "chapter:pp. 4-4", "type": "continues"}]}
    out = dik.relate_chapters(record, clerk.Scripted(answers), tmp_path / "q")
    assert out["added"] == 1                                    # the unread chapter's is dropped
    edge = [e for e in record["information"] if e["type"] == "prepares"][0]
    assert edge["status"] == "inferred" and edge["basis"].startswith("model reading")
    assert "How The Chapters Relate" in dik.sections(record)


def test_the_batch_records_data_and_the_note_labels_origins(library):
    c = Context(tier="curate", vault=library, extras={
        "clerk": clerk.Scripted(clerk_answers), "fetcher": intake.Replay(RESPONSES)})
    item = REGISTRY.call("ingest", {"ref": "acme/rowstream"}, c)["item"]
    REGISTRY.call("staging_decide", {"item_ids": [item], "decision": "approve"}, c)
    done = REGISTRY.call("process_approved", {}, c)["items"][0]
    assert done["stages"]["data"] == "complete" and done["stages"]["lenses"] == "complete"
    assert dik.load(library, "acme - rowstream")["data"]
    accepted = REGISTRY.call("staging_decide", {"item_ids": [item], "decision": "accept"}, c)
    note = notes.load(library.root / accepted["results"][0]["promotion"]["path"])
    assert note.frontmatter["dik"].startswith(".librarian/derived/dik/")
    assert "*Origin: source-stated" in note.body                    # the Claims section
    assert "project application" not in note.body.lower()          # never in a source note


from test_intake import library  # noqa: E402,F401  (fixture)


def test_a_models_records_are_what_its_listing_states(vault):
    record = dik.model("gpt-oss-20b - deepinfra", {
        "provider": "deepinfra", "model_id": "openai/gpt-oss-20b", "context_length": 131072,
        "price_input_per_1m": 0.03, "tool_calling": True, "best_for": ["Talking_Fast"]},
        "2026-10-01")
    facts = {d["locator"]: d for d in record["data"] if d["kind"] == "listing_fact"}
    assert facts["context_length"]["value"] == 131072 and facts["context_length"]["origin"] == \
        "source-stated"
    assert facts["price_output_per_1m"]["status"] == "unknown"        # the listing omits it
    guess = [d for d in record["data"] if d["kind"] == "suggested_use"][0]
    assert guess["origin"] == "model-produced" and guess["status"] == "proposed"


def test_a_datasets_records_carry_its_access_points_and_their_checks(vault):
    from resource_librarian import components
    components.check(vault, "https://zenodo.org/records/7/rows.csv",
                     intake.Replay({"https://zenodo.org/records/7/rows.csv": "a,b"}))
    record = dik.dataset(vault, "Rows Benchmark", {
        "canonical_url": "https://zenodo.org/records/7",
        "access_points": ["https://zenodo.org/records/7/rows.csv",
                          "https://zenodo.org/api/records/7"]}, "2026-10-01")
    points = {d["locator"]: d for d in record["data"] if d["kind"] == "access_point"}
    assert points["https://zenodo.org/records/7/rows.csv"]["status"] == "observed"
    assert points["https://zenodo.org/records/7/rows.csv"]["name"] == "csv"
    assert points["https://zenodo.org/api/records/7"]["status"] == "unknown"     # not checked
    assert [e["type"] for e in record["information"]] == ["offers", "offers"]


def test_an_accepted_note_is_rebuilt_and_its_sections_offered_as_a_revision(vault):
    ids = repo_evidence(vault)
    from conftest import add_source
    add_source(vault.root, "acme - planner", "A query planner.",
               extra_fm="evidence:\n" + "".join(f"- {i}\n" for i in ids))
    before = (vault.root / "Sources/repository/acme - planner.md").read_text(encoding="utf-8")
    out = REGISTRY.call("dik_rebuild", {}, Context(tier="contribute", vault=vault))
    row = next(r for r in out["results"] if r["source"] == "acme - planner")
    assert row["status"] == "rebuilt" and row["records"] > 5 and row["revision"]
    assert (vault.root / "Sources/repository/acme - planner.md").read_text(
        encoding="utf-8") == before                                   # nothing written yet
    again = REGISTRY.call("dik_rebuild", {"source": "acme - planner"},
                          Context(tier="contribute", vault=vault))
    assert again["results"][0]["revision"] == row["revision"]         # one open revision
    person = Context(tier="curate", vault=vault)
    merged = REGISTRY.call("staging_decide", {"item_ids": [row["revision"]],
                                              "decision": "accept"}, person)
    assert set(merged["results"][0]["sections"]) == {"Components", "How It Fits Together"}
    note = notes.load(vault.root / "Sources/repository/acme - planner.md")
    assert "*Origin: structurally observed" in note.sections()["Components"]
    assert note.frontmatter["dik"].startswith(".librarian/derived/dik/")


def test_an_accepted_document_is_rebuilt_from_its_file(vault):
    from conftest import pdf_bytes
    (vault.root / "Inbox").mkdir(exist_ok=True)
    (vault.root / "Inbox" / "plans.pdf").write_bytes(pdf_bytes(
        [["Chapter 1: Anchoring", "Plans anchor."], ["Chapter 2: Remedies", "Use reference classes."]]))
    person = Context(tier="curate", vault=vault, extras={"clerk": clerk.Scripted(clerk_answers)})
    item = REGISTRY.call("ingest", {"ref": "Inbox/plans.pdf"}, person)["item"]
    REGISTRY.call("staging_decide", {"item_ids": [item], "decision": "accept"}, person)
    out = REGISTRY.call("dik_rebuild", {"source": "plans"}, person)
    assert out["results"][0]["status"] == "rebuilt"
    record = dik.load(vault, "plans")
    assert [d["name"] for d in record["data"]] == ["Chapter 1: Anchoring", "Chapter 2: Remedies"]
    assert all(d["coverage"] == "not opened" for d in record["data"])   # never deep-read
