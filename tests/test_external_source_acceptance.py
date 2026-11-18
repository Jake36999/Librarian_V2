"""A source whose file lives in an attached project folder can be accepted into the catalogue
(audit R5, 2026-11-17). Connected projects are read where they are, through client access: the
file is referenced in place, never copied into the vault."""
import json

import pytest

from resource_librarian import notes, staging
from resource_librarian.app import App
from resource_librarian.keys import KeyStore


@pytest.fixture
def core(vault, tmp_path):
    project = tmp_path / "project"
    (project / "docs").mkdir(parents=True)
    doc = project / "docs" / "design.md"
    doc.write_text("# Design\n\nThe design keeps attached files where they are.\n", encoding="utf-8")
    manifest = vault.librarian / "content-roots.json"
    manifest.write_text(json.dumps({"version": 1, "mode": "create", "excludes": [], "roots": [
        {"path": ".", "access": "read_write"},
        {"path": str(project / "docs"), "access": "read_only", "attached": True, "purpose": "own-docs",
         "authorship": "owner_created"}]}), encoding="utf-8")
    staging.StagingStore(vault).add({"id": "design", "kind": "source", "name": "Design notes",
        "source_kind": "document", "title": "Design notes", "canonical_url": "file:design",
        "file": doc.resolve().as_posix(),
        "review": {"draft": {"status": "ok", "bottom_line": "The design keeps attached files in place.",
                              "what_it_solves": "Explains where attached files live.", "model": "fixture-clerk"}},
        "sections": {"Claims": "- The design keeps attached files where they are (part 1)"}, "evidence": []})
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=5)
    app.set_mode("auto")
    try:
        yield app, doc
    finally:
        app.close_runtime()


def test_an_attached_file_is_accepted_and_referenced_in_place(core):
    app, doc = core
    before = doc.read_bytes()
    out = app.person_call("staging_decide", {"item_ids": ["design"], "decision": "accept"})
    assert out.get("accepted") == 1, json.dumps(out, indent=2)
    note = next((app.vault.root / "Sources").rglob("Design notes.md"))
    fm = notes.load(note).frontmatter
    assert fm["file"] == doc.resolve().as_posix()                # the original, where it is
    assert not list((app.vault.root / "Sources").rglob("design.md"))   # nothing copied in
    assert doc.read_bytes() == before


def test_an_in_place_source_has_indexed_text_and_a_quotable_original(core):
    """2026-11-18: in-place Sources had no `in_text` passages and quotes past the card failed."""
    from resource_librarian import text
    from resource_librarian.registry import Context
    from resource_librarian.tools.sessions import _original_text
    app, doc = core
    doc.write_text("# Design\n\nThe design keeps attached files where they are.\n\n"
                   "A later passage says the archive is rebuilt every night.\n", encoding="utf-8")
    assert app.person_call("staging_decide", {"item_ids": ["design"], "decision": "accept"}).get("accepted") == 1
    report = app.index_service.run(lambda index: text.sync_documents(index))
    assert any(e["note"] == "Design notes" for e in report["indexed"]), report
    rows = app.index_service.run(lambda index: index.conn.execute(
        "SELECT count(*) FROM chunk WHERE note = 'Design notes' AND role = 'document'").fetchone()[0])
    assert rows >= 1
    note = next((app.vault.root / "Sources").rglob("Design notes.md"))
    from resource_librarian import notes
    rel, original = _original_text(Context(vault=app.vault), notes.load(note).frontmatter)
    assert "rebuilt every night" in original and rel == doc.resolve().as_posix()
