"""M5, second part: what the batch leaves behind is linked, marked and named (implementation plan M5).

- W-CIT-01: a Source note and its graph paper are linked by the publication's receipt, not a title
  derived each time, so a renamed note keeps its paper.
- W-PAR-01: the parse stage's projection is marked provisional; only the publish stage's is published.
- W-BAT-01: a folder draft that fails says why.
- W-ACC-02: an accepted note that is not findable opens a ticket for the reindex remedy.
"""
from __future__ import annotations

import pytest

from resource_librarian import clerk, graph_evidence, staging, tools  # noqa: F401
from resource_librarian.tickets import TicketStore

from conftest import add_source
from test_graph_evidence import GRAPH, geo  # noqa: F401  (fixture)
from test_sessions import Model, library  # noqa: F401  (fixture)


def test_a_stored_link_finds_the_papers_note_whatever_its_title(library, geo):
    # doc:8's title, "Unread Paper", names no note; the note that published it says so itself.
    add_source(library.root, "Renamed Paper Note", "A paper about host state, renamed since.",
               extra_fm=f'graph_paper: "{GRAPH}/doc:8"')
    found = graph_evidence.resolve(Model(library).ctx, f"{GRAPH}/doc:8")
    assert found["note"] == "Renamed Paper Note" and found["linked_by"] == "stored link"
    by_title = graph_evidence.resolve(Model(library).ctx, f"{GRAPH}/doc:7")
    assert by_title["note"] == "osquery" and by_title["linked_by"] == "title"


def test_accepting_a_published_source_writes_its_stored_link(vault):
    store = staging.StagingStore(vault)
    store.add({"id": "p1", "kind": "source", "name": "A Paper", "status": "enriched",
               "review": {"draft": {"status": "ok", "bottom_line": "A paper.", "what_it_solves": "A need."}},
               "processing": {"coverage": "full", "publication": {"graph_id": "g", "document_id": "doc:3",
                                                                  "cite_as": "Lib-papers/doc:3"}}})
    draft, _coverage = staging._source_draft(store, store.load("p1"), "", "", "person", "", None, None, lambda _check: None)
    assert draft.fields["graph_paper"] == "Lib-papers/doc:3"


def test_the_parse_stages_projection_is_marked_provisional(vault, monkeypatch):
    from resource_librarian import paper_graph
    monkeypatch.setattr(paper_graph, "export_document", lambda vault, item, text_layer=False: {
        "file_path": "Inbox/p.pdf", "coverage": {"status": "full_conversion", "limitations": []}})
    assert paper_graph.write_artifact(vault, {})["provisional"] is True
    assert paper_graph.write_artifact(vault, {}, text_layer=True)["provisional"] is False


def test_a_failed_folder_draft_says_why(tmp_path):
    from resource_librarian.folder_review import FolderReview
    from test_folder_review import fake_planner
    from resource_librarian.vault import Vault
    vault = Vault(tmp_path / "library")
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    (source / "src" / "a.py").write_text("x = 1\n")
    review = FolderReview(vault, planner=fake_planner)
    card = review.survey(source)["cards"][0]
    bad = clerk.Scripted(lambda payload: {"nonsense": True})
    with pytest.raises(ValueError, match=r"FOLDER_DRAFT_FAILED: \w+"):
        review.draft(card["id"], bad, approved=True)


def test_an_accepted_note_that_is_not_findable_opens_a_reindex_ticket(vault, monkeypatch):
    from resource_librarian.registry import REGISTRY, Context
    from resource_librarian.tools import staging as staging_tools
    monkeypatch.setattr(staging_tools.staging, "decide", lambda *a, **k: [
        {"id": "s-x", "status": "accepted", "promotion": {"catalogued": False}}])
    out = REGISTRY.call("staging_decide", {"item_ids": ["s-x"], "decision": "accept"},
                        Context(tier="curate", vault=vault, extras={"caller_kind": "person"}))
    assert out["not_findable"] == ["s-x"]
    [ticket] = TicketStore(vault).all(open_only=True)
    assert ticket["class"] == "mapped_shortfall" and ticket["scope"] == "findability:s-x"
    assert ticket["owner"] == "doctor"
