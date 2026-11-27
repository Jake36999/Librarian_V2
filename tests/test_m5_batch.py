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


def test_the_running_spend_reads_only_new_lines_and_sees_every_writer(vault):
    # M5: the library's ceiling is checked before each model call, so its count must be cheap and
    # include calls recorded outside the Core's own log instance (record_call).
    from resource_librarian import usage_log
    from resource_librarian.vault import render_config
    log = usage_log.UsageLog(vault)
    assert log.spent() == 0.0 and log.over_ceiling() is False
    usage_log.record_call(vault, role="clerk", task="review", usd=0.4)
    usage_log.record_call(vault, role="clerk", task="review", usd=0.2)
    assert abs(log.spent() - 0.6) < 1e-9
    assert abs(log.spent() - usage_log.spent_usd(vault)) < 1e-9          # same count, read once
    config = vault.config()
    config.setdefault("budget", {})["ceiling_usd"] = 0.5
    vault.config_path.write_text(render_config(config))
    assert log.over_ceiling() is True


def test_a_file_source_gets_a_readable_title_and_keeps_its_name(tmp_path, monkeypatch):
    # M5 (as-is W-INT-01): the title a reader sees; the name (and so duplicate checks) unchanged.
    from resource_librarian import intake
    md = tmp_path / "Optimizing_Queries_with_Joins.md"
    md.write_text("text")
    assert intake.readable_title(md) == "Optimizing Queries with Joins"
    assert intake.file_title(md) == "Optimizing_Queries_with_Joins"
    plain = tmp_path / "already readable.md"
    plain.write_text("text")
    assert intake.readable_title(plain) == "already readable"
    pdf = tmp_path / "x_y_z.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    class Meta:
        title = "A Real Paper Title About Joins"

    class Reader:
        def __init__(self, path):
            self.metadata = Meta
    import pypdf
    monkeypatch.setattr(pypdf, "PdfReader", Reader)
    assert intake.readable_title(pdf) == "A Real Paper Title About Joins"
    Meta.title = "Microsoft Word - draft3.docx"
    assert intake.readable_title(pdf) == "x y z"
    # A template's placeholder (M5 acceptance, 2026-11-27: the IEEE template's own title).
    Meta.title = "Paper Title (use style: paper title)"
    assert intake.readable_title(pdf) == "x y z"


def test_a_handle_whose_label_holds_a_space_is_a_graph_citation():
    # M5 acceptance (2026-11-27): a label is made from the library's title, so "M5 Acceptance" gave
    # Geo-Grapher's cite_as "M5 Acceptance-third-party-papers/doc:4", which the handle pattern refused.
    assert graph_evidence.is_handle("M5 Acceptance-third-party-papers/doc:4")
    assert graph_evidence.HANDLE.match("M5 Acceptance-third-party-papers/doc:4")["graph"] == \
        "M5 Acceptance-third-party-papers"
    assert graph_evidence.is_handle("Lib-papers/doc:3")
    assert not graph_evidence.is_handle("Lib-papers /doc:3")          # no space at the label's edge
    assert not graph_evidence.is_handle(" /doc:3") and not graph_evidence.is_handle("doc:3")


def test_a_stages_key_leaves_out_only_what_it_or_a_later_stage_writes(vault, monkeypatch):
    # M5 planted cases (27 November): `clean_file`, which parse writes, was in every stage's key, so a
    # run resumed after parse found validate's and parse's keys changed and read the source again.
    from resource_librarian import batch
    (vault.root / "Inbox").mkdir(exist_ok=True)
    (vault.root / "Inbox" / "a.pdf").write_bytes(b"%PDF-1.4 original")
    (vault.root / "Inbox" / "a.md").write_text("[page 1]\nconverted", encoding="utf-8")
    before = {"id": "x", "name": "A", "file": "Inbox/a.pdf", "evidence": []}
    after = {**before, "clean_file": "Inbox/a.md"}                   # what parse wrote
    monkeypatch.setattr(batch, "_unmapped_cleanup", lambda vault, path: False)
    for stage in ("validate", "parse"):
        assert batch._keyed_identity(vault, after, stage, batch.STAGES) == \
            batch._keyed_identity(vault, before, stage, batch.STAGES)
    # The reading's input is the conversion, so its key still changes with it ...
    assert batch._keyed_identity(vault, after, "read", batch.STAGES) != \
        batch._keyed_identity(vault, before, "read", batch.STAGES)
    # ... and the original file stays in every key: a changed PDF still re-runs parse.
    changed = dict(before)
    (vault.root / "Inbox" / "b.pdf").write_bytes(b"%PDF-1.4 changed")
    changed["file"] = "Inbox/b.pdf"
    assert batch._keyed_identity(vault, changed, "parse", batch.STAGES) != \
        batch._keyed_identity(vault, before, "parse", batch.STAGES)
    # A conversion that lost its page anchors still re-runs parse when approved again (2026-11-16).
    monkeypatch.setattr(batch, "_unmapped_cleanup", lambda vault, path: True)
    assert batch._keyed_identity(vault, after, "parse", batch.STAGES) != \
        batch._keyed_identity(vault, before, "parse", batch.STAGES)


def test_a_published_paper_with_no_stored_link_opens_a_ticket_and_a_linked_one_closes_it(vault):
    # Delegated review (27 November): `unlinked_paper` was declared in tickets.yaml and never raised.
    from resource_librarian import batch
    from resource_librarian.registry import Context
    ctx = Context(tier="curate", vault=vault, extras={})
    item = {"id": "p-9", "name": "A Paper"}
    batch._paper_link_ticket(ctx, item, {"published": True, "graph_id": "g", "documents": 1})  # older wheel
    [ticket] = TicketStore(vault).all(open_only=True)
    assert ticket["class"] == "unlinked_paper" and ticket["scope"] == "paper:p-9" and ticket["owner"] == "doctor"
    assert "no stored link" in ticket["summary"]
    batch._paper_link_ticket(ctx, item, {"published": True, "cite_as": "Lib-papers/doc:2", "status": "partial"})
    assert len(TicketStore(vault).all(open_only=True)) == 1            # still open: content incomplete
    batch._paper_link_ticket(ctx, item, {"published": True, "cite_as": "Lib-papers/doc:2", "status": "complete"})
    assert TicketStore(vault).all(open_only=True) == []              # closed by the Core's recheck
