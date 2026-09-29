import json

import pytest

from resource_librarian import clerk, notes, staging, tools  # noqa: F401
from resource_librarian.index import Index
from resource_librarian.lenses import LensStore
from resource_librarian.promote import Draft, findability, promote
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.search import Engine
from resource_librarian.vault import render_config

from conftest import add_source, write_note

DESCRIPTION = ("Change data capture: streams row-level changes out of relational databases "
               "into Kafka topics.")


def source_item(item_id, name, status="staged"):
    return {"id": item_id, "kind": "source", "source_kind": "repository", "name": name,
            "title": name, "canonical_url": f"https://github.com/{name.replace(' - ', '/')}",
            "topic": "Data", "fields": {"license_class": "Permissive", "ecosystem": "Java",
                                        "category": "data_platform"},
            "sections": {"Architecture & Mechanics": "- Reads the write-ahead log.\n"
                                                     "- Emits one event per changed row."},
            "evidence_text": f"description: {DESCRIPTION}\n\nArchitecture & Mechanics:\n"
                             f"- Reads the write-ahead log.\n- Emits one event per changed row.",
            "evidence": [], "proposed_by": "intake", "status": status}


@pytest.fixture
def staged(vault):
    store = staging.StagingStore(vault)
    store.add(source_item("s-a", "debezium - debezium"))
    store.add(source_item("s-b", "other - thing"))
    store.add({"id": "l-1", "kind": "lens", "name": "interface-first stance",
               "source": "design patterns",
               "source_quote": "program to an interface, not an implementation",
               "attends_to": ["interfaces"], "role_purpose": "reason through interfaces"})
    write_note(vault.root, "Concepts/Change Data Capture.md",
               "type: concept\nconcept_kind: pattern\nstatus: active",
               "## Definition\nStreaming row-level changes out of a database.\n")
    for i in range(3):
        add_source(vault.root, f"filler {i}", f"Draws pictures number {i}.")
    return vault


def drafts(payload):
    if payload["task"] == "bottom_line":
        return {"bottom_line": "Change data capture: streams row-level changes out of "
                               "relational databases.",
                "what_it_solves": "Streams row-level changes out of relational databases "
                                  "into Kafka topics.", "confident": True}
    if payload["task"] == "sensitivity":
        return {"sensitivity": "normal", "reason": "data tooling"}
    return {"recommendation": "fits", "reason": "reads the log",
            "evidence_quote": "Reads the write-ahead log"}


def ctx(vault, tier="curate", answer=drafts):
    return Context(tier=tier, vault=vault, extras={"clerk": clerk.Scripted(answer)})


def test_review_splits_framed_and_unframed(staged):
    c = ctx(staged)
    out = REGISTRY.call("staging_review", {"item_id": "s-a", "need": "change data capture",
                                           "disqualifiers": ["needs a GPU"]}, c)
    assert out["draft"]["status"] == "ok" and out["fit"]["recommendation"] == "fits"
    assert "Reads the write-ahead log" in out["fit"]["quote_context"]
    payloads = c.extras["clerk"].payloads
    bottom = next(p for p in payloads if p["task"] == "bottom_line")
    assert "change data capture" not in bottom["user"]             # unframed
    assert "change data capture" in next(p for p in payloads if p["task"] == "fit")["user"]


def test_person_accepts_and_it_is_catalogued(staged):
    c = ctx(staged)
    REGISTRY.call("staging_review", {"item_id": "s-a"}, c)
    out = REGISTRY.call("staging_decide", {"item_ids": ["s-a"], "decision": "accept"}, c)
    result = out["results"][0]
    assert result["status"] == "accepted" and result["promotion"]["catalogued"], result
    note = notes.load(staged.root / result["promotion"]["path"])
    assert note.frontmatter["attested_by"] == "person"
    assert note.frontmatter["drafted_by"] == "scripted"
    assert note.frontmatter["concepts"] == ["[[Change Data Capture]]"]
    assert "Bottom Line" in note.sections() and "Architecture & Mechanics" in note.sections()
    concept = notes.load(staged.root / "Concepts" / "Change Data Capture.md")
    assert "[[debezium - debezium]]" in concept.sections()["Sources Using This"]
    assert "Streaming row-level" in concept.sections()["Definition"]    # the person's text kept
    topic = (staged.root / "Indexes" / "Topic - Data.md").read_text()
    assert "[[debezium - debezium]]" in topic
    assert "Data" in (staged.root / "Indexes" / "Master Index.md").read_text()


def test_agent_needs_the_vault_setting(staged):
    agent = ctx(staged, tier="contribute")
    REGISTRY.call("staging_review", {"item_id": "s-a"}, agent)
    refused = REGISTRY.call("staging_decide", {"item_ids": ["s-a"], "decision": "accept"},
                            agent)["results"][0]
    assert refused["refused"] == "PERSON_CONFIRMS"
    config = staged.config()
    config["promotion"]["mode"] = "agent"
    staged.config_path.write_text(render_config(config))
    accepted = REGISTRY.call("staging_decide", {"item_ids": ["s-a"], "decision": "accept"},
                             agent)["results"][0]
    note = notes.load(staged.root / accepted["promotion"]["path"])
    assert note.frontmatter["attested_by"] == "agent"


def test_sensitive_is_never_accepted_by_an_agent(staged):
    config = staged.config()
    config["promotion"]["mode"] = "agent"
    staged.config_path.write_text(render_config(config))

    def dual_use(payload):
        if payload["task"] == "sensitivity":
            return {"sensitivity": "review_required", "reason": "credential theft"}
        return drafts(payload)
    agent = ctx(staged, tier="contribute", answer=dual_use)
    REGISTRY.call("staging_review", {"item_id": "s-a"}, agent)
    assert staging.StagingStore(staged).load("s-a")["sensitivity"] == "review"
    refused = REGISTRY.call("staging_decide", {"item_ids": ["s-a"], "decision": "accept"},
                            agent)["results"][0]
    assert refused["refused"] == "SENSITIVITY_REVIEW"
    assert REGISTRY.call("staging_flag", {"item_id": "s-a", "sensitive": False},
                         agent)["error"] == "invalid_arguments"
    person = REGISTRY.call("staging_decide", {"item_ids": ["s-a"], "decision": "accept"},
                           ctx(staged))["results"][0]
    assert person["status"] == "accepted"


def test_reject_goes_to_quarantine_and_batch_reports_each(staged):
    c = ctx(staged)
    assert REGISTRY.call("staging_decide", {"item_ids": ["s-a"], "decision": "reject"},
                         c)["error"] == "invalid_arguments"                  # needs a reason
    out = REGISTRY.call("staging_decide", {"item_ids": ["s-a", "s-b", "nope"],
                                           "decision": "reject", "reason": "off topic"}, c)
    assert [r.get("status") for r in out["results"][:2]] == ["rejected", "rejected"]
    assert "error" in out["results"][2]
    quarantined = json.loads((staged.work("quarantine") / "staging" / "s-a.json").read_text())
    assert quarantined["reason"] == "off topic"


def test_no_draft_no_accept_for_an_agent(staged):
    config = staged.config()
    config["promotion"]["mode"] = "agent"
    staged.config_path.write_text(render_config(config))
    out = REGISTRY.call("staging_decide", {"item_ids": ["s-a"], "decision": "accept"},
                        ctx(staged, tier="contribute"))["results"][0]
    assert "no reviewed draft" in out["error"]


def test_lens_accept_goes_to_the_agent_store(staged):
    out = REGISTRY.call("staging_decide", {"item_ids": ["l-1"], "decision": "accept"},
                        ctx(staged))["results"][0]
    assert out["lens"] == "interface-first-stance"
    listed = REGISTRY.call("lens_list", {"query": "interfaces"}, ctx(staged))
    assert listed["total"] == 1 and listed["lenses"][0]["id"] == "interface-first-stance"
    lens = REGISTRY.call("lens_show", {"lens_id": "interface-first-stance"}, ctx(staged))
    assert lens["source_quote"].startswith("program to an interface")
    assert not list(staged.root.glob("**/interface-first*.md"))       # not a note


def test_duplicate_name_is_refused(staged):
    add_source(staged.root, "debezium - debezium", "already here")
    c = ctx(staged)
    REGISTRY.call("staging_review", {"item_id": "s-a"}, c)
    out = REGISTRY.call("staging_decide", {"item_ids": ["s-a"], "decision": "accept"}, c)
    assert out["results"][0]["refused"] == "UNIQUE_NOTE_NAMES"


def concept_item(item_id, name, sources=("source-a", "source-b")):
    return {"id": item_id, "kind": "concept", "name": name,
            "usages": [{"source": s, "sentence": f"{name} used in {s}."} for s in sources],
            "sources": list(sources), "proposed_by": "terms"}


def test_concept_review_points_at_accept_not_a_draft(staged):
    store = staging.StagingStore(staged)
    store.add(concept_item("concept-sharding", "sharding"))
    out = REGISTRY.call("staging_review", {"item_id": "concept-sharding"}, ctx(staged))
    assert out["kind"] == "concept"
    assert "given at accept" in out["note"]


def test_concept_list_and_summary(staged):
    store = staging.StagingStore(staged)
    store.add(concept_item("concept-sharding", "sharding"))
    listed = REGISTRY.call("staging_list", {"kind": "concept"}, ctx(staged))
    assert listed["total"] == 1
    row = listed["items"][0]
    assert row["kind"] == "concept" and row["name"] == "sharding"
    assert row["sources"] == 2 and row["usages"] == 2


def test_concept_accept_needs_a_persons_definition(staged):
    store = staging.StagingStore(staged)
    store.add(concept_item("concept-sharding", "sharding"))
    out = REGISTRY.call("staging_decide", {"item_ids": ["concept-sharding"],
                                           "decision": "accept"}, ctx(staged))
    assert "a person's own" in out["results"][0]["error"]


def test_concept_accept_rejects_a_bad_concept_kind(staged):
    store = staging.StagingStore(staged)
    store.add(concept_item("concept-sharding", "sharding"))
    out = REGISTRY.call("staging_decide", {"item_ids": ["concept-sharding"],
                                           "decision": "accept",
                                           "fields": {"definition": "Splits data across nodes.",
                                                      "concept_kind": "nonsense"}}, ctx(staged))
    assert "concept_kind" in out["results"][0]["error"]


def test_concept_accept_writes_a_note_a_person_can_be_found_by(staged):
    store = staging.StagingStore(staged)
    store.add(concept_item("concept-sharding", "sharding"))
    out = REGISTRY.call("staging_decide", {"item_ids": ["concept-sharding"],
                                           "decision": "accept",
                                           "fields": {"definition": "Splits data across nodes.",
                                                      "concept_kind": "pattern",
                                                      "aliases": ["partitioning"]}}, ctx(staged))
    result = out["results"][0]
    assert result["status"] == "accepted" and result["path"] == "Concepts/sharding.md"
    note = notes.load(staged.root / result["path"])
    assert note.frontmatter["type"] == "concept"
    assert note.frontmatter["concept_kind"] == "pattern"
    assert note.frontmatter["aliases"] == ["partitioning"]
    assert "Splits data across nodes." in note.sections()["Definition"]
    assert "sharding used in source-a" in note.sections()["Usages"]
    assert staging.StagingStore(staged).load("concept-sharding")["status"] == "accepted"


def test_concept_accept_refuses_a_second_note_at_the_same_name(staged):
    store = staging.StagingStore(staged)
    store.add(concept_item("concept-change-data-capture", "Change Data Capture"))
    out = REGISTRY.call("staging_decide",
                        {"item_ids": ["concept-change-data-capture"], "decision": "accept",
                         "fields": {"definition": "A different definition."}}, ctx(staged))
    assert "already exists" in out["results"][0]["error"]


def test_not_findable_is_loud(vault):
    for i in range(30):
        add_source(vault.root, f"twin {i}", "Streams changes into topics.")
    with Index(vault) as index:
        index.refresh()
        engine = Engine(index, vault.config()["heuristics"])
        report = promote(vault, engine, Draft(
            name="twin 99", kind="repository", title="twin 99", canonical_url="u",
            bottom_line="Streams changes into topics.", what_it_solves="Streams changes."))
        assert not report.catalogued and report.to_dict()["status"] == "written but not findable"
        assert "needs_attention" in notes.load(vault.root / report.path).frontmatter
        assert findability(engine, "twin 99")
