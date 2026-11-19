"""A green review must mean the source was actually read (owner pilot, 2026-11-16).

The pilot showed `read: queued` next to `review: complete` for a 12-chunk paper: the review stage
only checked that a Bottom Line draft existed.
"""
import pytest

import resource_librarian.batch as batch
from resource_librarian import deep_read as reading


@pytest.fixture(autouse=True)
def draft_ok(monkeypatch):
    monkeypatch.setattr(batch.REGISTRY, "call", lambda *a, **k: {"draft": {"status": "ok"}})


def paper(chunks, read, **extra):
    record = {"version": reading.RECORD_VERSION, "chunks": chunks, "read": {str(i): {} for i in range(read)}}
    return {"id": "p", "kind": "source", "source_kind": "paper", "file": "x.pdf", "deep_read": record, **extra}


def test_review_is_partial_while_chunks_remain_unread():
    out = batch._review(None, paper(12, 0))
    assert out["status"] == "partial" and "0 of 12" in out["reason"]
    assert batch._review(None, paper(12, 11))["status"] == "partial"


def test_review_completes_only_when_every_chunk_was_read():
    assert batch._review(None, paper(12, 12))["status"] == "complete"


def test_a_paper_never_read_is_not_reviewed_complete():
    item = {"id": "p", "kind": "source", "source_kind": "paper", "file": "x.pdf"}
    assert batch._review(None, item)["status"] == "partial"


def test_sources_with_nothing_to_deep_read_keep_the_draft_only_review():
    item = {"id": "r", "kind": "source", "source_kind": "repository"}
    assert batch._review(None, item)["status"] == "complete"


def test_a_missing_draft_stays_queued():
    batch.REGISTRY.call = lambda *a, **k: {"draft": {"status": "pending"}}
    assert batch._review(None, paper(12, 12))["status"] == "queued"


def test_an_ungrounded_draft_is_not_reported_as_waiting_for_a_model(monkeypatch):
    """2026-11-17: 39 sources sat partial as "waiting for the clerk model" though it had answered."""
    monkeypatch.setattr(batch.REGISTRY, "call", lambda *a, **k: {"draft": {"status": "not_confident"}})
    out = batch._review(None, paper(12, 12))
    assert out["status"] == "partial" and "waiting" not in out["reason"] and "answered" in out["reason"]
    monkeypatch.setattr(batch.REGISTRY, "call", lambda *a, **k: {"draft": {"status": "refused"}})
    assert batch._review(None, paper(12, 12))["status"] == "failed"


def test_a_not_confident_draft_is_asked_once_more(monkeypatch):
    """ACCEPT-02, 2026-11-19: the model's own "not confident" was uneven on the same evidence
    (4 of 43 papers, each with a sound Bottom Line). A second ask that succeeds completes it."""
    answers = iter([{"draft": {"status": "not_confident"}}, {"draft": {"status": "ok"}}])
    calls = []
    monkeypatch.setattr(batch.REGISTRY, "call", lambda *a, **k: calls.append(a[0]) or next(answers))
    assert batch._review(None, paper(12, 12))["status"] == "complete"
    assert calls == ["staging_review", "staging_review"]


def test_a_grounded_low_confidence_draft_completes_the_reading_and_says_so(monkeypatch):
    """Still unsure after the second ask, but the Bottom Line rests on the source's words: the
    paper is not left partial; the draft is marked low confidence for a person to confirm."""
    monkeypatch.setattr(batch.REGISTRY, "call", lambda *a, **k: {"draft": {"status": "not_confident"}})
    monkeypatch.setattr(batch, "_grounded_draft", lambda ctx, item_id: True)
    out = batch._review(None, paper(12, 12))
    assert out == {"status": "complete", "draft": "low_confidence"}


def test_grounded_draft_reads_the_stored_draft_against_its_evidence(vault):
    from resource_librarian.registry import Context
    from resource_librarian.staging import StagingStore
    store = StagingStore(vault)
    evidence = ("GraphRAG builds an entity knowledge graph from source documents, then "
                "pregenerates community summaries to answer global questions over the corpus.")
    store.add({"id": "g", "kind": "source", "name": "GraphRAG", "status": "processing",
               "evidence_text": evidence,
               "review": {"draft": {"status": "not_confident",
                                    "bottom_line": "GraphRAG builds a knowledge graph and community summaries.",
                                    "what_it_solves": "Answering global questions over a whole corpus."}}})
    ctx = Context(tier="curate", vault=vault)
    assert batch._grounded_draft(ctx, "g") is True
    store.add({"id": "h", "kind": "source", "name": "Elsewhere", "status": "processing",
               "evidence_text": evidence,
               "review": {"draft": {"status": "not_confident",
                                    "bottom_line": "A study of marine biology in tropical coral reefs.",
                                    "what_it_solves": "Answering global questions over a whole corpus."}}})
    assert batch._grounded_draft(ctx, "h") is False           # the Bottom Line is not in the text
    assert batch._grounded_draft(None, "g") is False
