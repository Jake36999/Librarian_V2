from resource_librarian import concepts, tools  # noqa: F401
from resource_librarian.evidence import EvidenceStore
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.staging import StagingStore

from conftest import write_note


def _use(store: EvidenceStore, term: str, sentence: str, source: str) -> None:
    store.put("term_usage", source, {"term": term, "sentence": sentence})


def test_a_term_seen_in_two_sources_is_staged(vault):
    evidence = EvidenceStore(vault)
    _use(evidence, "backpressure", "Backpressure keeps a fast producer from "
                                   "overrunning a slow consumer.", "source-a")
    _use(evidence, "backpressure", "Without backpressure the queue grows without "
                                   "bound.", "source-b")
    out = concepts.candidates(vault)
    assert out["scanned"] == 1
    assert out["staged"] == ["concept-backpressure"]
    item = StagingStore(vault).load("concept-backpressure")
    assert item["kind"] == "concept" and item["name"] == "backpressure"
    assert sorted(item["sources"]) == ["source-a", "source-b"]
    assert len(item["usages"]) == 2
    assert item["proposed_by"] == "terms"


def test_a_term_seen_in_only_one_source_is_not_staged(vault):
    evidence = EvidenceStore(vault)
    _use(evidence, "sharding", "Sharding splits data across nodes.", "source-a")
    out = concepts.candidates(vault)
    assert out["scanned"] == 1
    assert out["staged"] == []


def test_min_sources_is_configurable(vault):
    evidence = EvidenceStore(vault)
    for i in range(3):
        _use(evidence, "idempotency", f"Usage number {i} of idempotency.", f"source-{i}")
    assert concepts.candidates(vault, min_sources=3)["staged"] == ["concept-idempotency"]
    assert concepts.candidates(vault, min_sources=4)["staged"] == []


def test_a_term_already_staged_is_not_restaged(vault):
    evidence = EvidenceStore(vault)
    _use(evidence, "backpressure", "First usage of backpressure here today.", "source-a")
    _use(evidence, "backpressure", "Second usage of backpressure here today.", "source-b")
    first = concepts.candidates(vault)
    assert first["staged"] == ["concept-backpressure"]
    second = concepts.candidates(vault)
    assert second["staged"] == []


def test_a_term_already_decided_is_not_restaged(vault):
    evidence = EvidenceStore(vault)
    _use(evidence, "backpressure", "First usage of backpressure here today.", "source-a")
    _use(evidence, "backpressure", "Second usage of backpressure here today.", "source-b")
    concepts.candidates(vault)
    store = StagingStore(vault)
    item = store.load("concept-backpressure")
    item["status"] = "rejected"
    store.save(item)
    assert concepts.candidates(vault)["staged"] == []


def test_a_term_with_an_existing_concept_note_is_not_restaged(vault):
    write_note(vault.root, "Concepts/Backpressure.md",
               "type: concept\nconcept_kind: term\nstatus: active",
               "## Definition\nAlready written up.\n")
    evidence = EvidenceStore(vault)
    _use(evidence, "backpressure", "First usage of backpressure here today.", "source-a")
    _use(evidence, "backpressure", "Second usage of backpressure here today.", "source-b")
    assert concepts.candidates(vault)["staged"] == []


def test_concept_candidates_tool(vault):
    evidence = EvidenceStore(vault)
    _use(evidence, "backpressure", "First usage of backpressure here today.", "source-a")
    _use(evidence, "backpressure", "Second usage of backpressure here today.", "source-b")
    c = Context(tier="contribute", vault=vault)
    out = REGISTRY.call("concept_candidates", {}, c)
    assert out["staged"] == ["concept-backpressure"]
    listed = REGISTRY.call("staging_list", {"kind": "concept"}, c)
    assert listed["total"] == 1


def test_usages_are_capped_and_terms_are_grouped_case_insensitively(vault):
    evidence = EvidenceStore(vault)
    for i in range(10):
        _use(evidence, "Backpressure" if i % 2 else "backpressure",
             f"Usage number {i} discussing backpressure at length.", f"source-{i}")
    out = concepts.candidates(vault)
    assert out["staged"] == ["concept-backpressure"]
    item = StagingStore(vault).load("concept-backpressure")
    assert len(item["usages"]) == concepts.MAX_USAGES
    assert len(item["sources"]) == 10
