"""Accepted third-party folders become Sources (owner, 2026-11-15).

Folder review only classifies folders. A third-party or research-docs folder's
documents must then enter the normal source pipeline (intake -> staging -> the
approved batch), so they get catalogue entries, chapter summaries and use history.
Own content is indexed whole and never turned into Sources.
"""
import pytest

from resource_librarian.vault import Vault


@pytest.fixture
def attached(tmp_path):
    from resource_librarian import content_roots
    vault = Vault(tmp_path / "library"); vault.root.mkdir()
    source = tmp_path / "source"
    for rel in ("papers/a.pdf", "papers/b.md", "papers/sub/c.txt", "papers/.env", "papers/build/gen.md",
                "papers/notes.py", "drafts/own.md", "papers/excluded/x.md"):
        p = source / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text("synthetic")
    manifest = dict(version=1, mode="create", excludes=[], roots=[
        dict(path=".", access="read_write"),
        dict(path=str(source / "papers"), access="read_only", attached=True, purpose="third-party",
             authorship="third_party", folder_decision="folder-1", graph_label="library-third-party"),
        dict(path=str(source / "papers" / "excluded"), access="read_only", attached=True, purpose="exclude",
             authorship=None, folder_decision="folder-2"),
        dict(path=str(source / "drafts"), access="read_only", attached=True, purpose="own-docs",
             authorship="owner_created", folder_decision="folder-3")])
    (vault.root / '.librarian').mkdir(exist_ok=True)
    content_roots._write_json(content_roots.manifest_path(vault.root), manifest)
    return vault, source


def test_capture_accepts_a_file_inside_an_accepted_attached_root(attached):
    from resource_librarian.intake import capture
    vault, source = attached
    ref = capture(str(source / "papers/a.pdf"), vault)
    assert ref.kind == "file" and ref.key == (source / "papers/a.pdf").resolve().as_posix()


@pytest.mark.parametrize("rel", ["papers/excluded/x.md", "elsewhere.md"])
def test_capture_refuses_excluded_or_unattached_files(attached, rel):
    from resource_librarian.intake import capture
    vault, source = attached
    (source / "elsewhere.md").write_text("synthetic")
    with pytest.raises(ValueError):
        capture(str(source / rel), vault)


def test_documents_lists_only_this_folders_own_third_party_documents(attached):
    from resource_librarian.folder_sources import documents
    vault, source = attached
    found = [p.relative_to(source).as_posix() for p in documents(vault, str(source / "papers"))]
    # no credentials, no build output, no code, nothing under a differently decided child root
    assert found == ["papers/a.pdf", "papers/b.md", "papers/sub/c.txt"]


def test_own_folders_are_never_turned_into_sources(attached):
    from resource_librarian.folder_sources import documents
    vault, source = attached
    with pytest.raises(ValueError, match="FOLDER_SOURCES"):
        documents(vault, str(source / "drafts"))


def test_queue_defers_every_document_once_and_respects_the_limit(attached):
    from resource_librarian.folder_sources import queue
    vault, source = attached
    calls = []
    def ingest(ref, note):
        calls.append(ref); return {"status": "queued"}
    out = queue(vault, str(source / "papers"), ingest=ingest, limit=2)
    assert out["queued"] == 2 and out["remaining"] == 1 and len(calls) == 2
    again = queue(vault, str(source / "papers"), ingest=ingest, limit=10)
    assert again["queued"] == 1 and again["already_queued"] == 2       # idempotent across runs
