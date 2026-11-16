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
    found = [p.relative_to(source).as_posix() for p in documents(vault, str(source / "papers"),
                                                                 scope=(".pdf", ".md", ".txt"))]
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
    wide = (".pdf", ".md", ".txt")
    out = queue(vault, str(source / "papers"), ingest=ingest, limit=2, scope=wide)
    assert out["queued"] == 2 and out["remaining"] == 1 and len(calls) == 2
    again = queue(vault, str(source / "papers"), ingest=ingest, limit=10, scope=wide)
    assert again["queued"] == 1 and again["already_queued"] == 2       # idempotent across runs


@pytest.mark.parametrize("rel", ["papers/b.md", "papers/notes.py", "drafts/own.md"])
def test_connected_file_read_preserves_original(attached, rel):
    from resource_librarian.tools.browse import read_file
    from resource_librarian.registry import Context
    vault, source = attached
    path = source / rel
    before = path.read_bytes()
    result = read_file(Context(tier="consult", vault=vault), str(path))
    assert "synthetic" in result["text"]
    assert path.read_bytes() == before


def test_connected_pdf_conversion_reads_in_place(attached, monkeypatch):
    from resource_librarian.tools.pdf import pdf_to_markdown_tool
    from resource_librarian import text, pdf_markdown
    from resource_librarian.registry import Context
    vault, source = attached
    path = source / "papers/a.pdf"
    before = path.read_bytes()
    monkeypatch.setattr(text, "extract", lambda *a: text.Extraction(pages=["source text"]))
    monkeypatch.setattr(pdf_markdown, "clean_document", lambda *a, **kw: ("source text", 1))
    result = pdf_to_markdown_tool(Context(tier="contribute", vault=vault), str(path))
    assert result["path"].startswith(".librarian/conversions/")
    assert path.read_bytes() == before


@pytest.mark.parametrize("rel", ["papers/excluded/x.md", "papers/.env", "elsewhere.md"])
def test_connected_reads_refuse_excluded_credentials_and_unattached(attached, rel):
    from resource_librarian.file_access import connected_read_path
    vault, source = attached
    with pytest.raises((TypeError, ValueError)):
        connected_read_path(vault, str(source / rel))


def test_connected_attachment_acceptance_resolves_original(attached):
    from resource_librarian.staging import _attachment_path
    vault, source = attached
    assert _attachment_path(vault, str(source / "papers/b.md")) == (source / "papers/b.md").resolve()


def test_connected_read_honours_attach_without_folder_classification(attached):
    from resource_librarian import content_roots
    from resource_librarian.file_access import connected_read_path
    vault, source = attached
    data = content_roots.load(vault.root)
    for root in data['roots']:
        if root.get('attached'):
            root.pop('purpose', None)
    content_roots._write_json(content_roots.manifest_path(vault.root), data)
    assert connected_read_path(vault, str(source / 'papers/b.md')).is_file()


def test_connected_read_honours_configured_exclusion(attached):
    from resource_librarian import content_roots
    from resource_librarian.file_access import connected_read_path
    vault, source = attached
    data = content_roots.load(vault.root)
    data['roots'][1]['excludes'] = ['b.md']
    content_roots._write_json(content_roots.manifest_path(vault.root), data)
    with pytest.raises((TypeError, ValueError)):
        connected_read_path(vault, str(source / 'papers/b.md'))


@pytest.mark.parametrize('enabled', [False, True])
def test_connected_read_uses_existing_project_switch(attached, enabled):
    from resource_librarian import projects
    from resource_librarian.file_access import connected_read_path
    vault, source = attached
    target = source / 'project' / 'analysis.py'
    target.parent.mkdir(); target.write_text('value = 1')
    projects._save(vault, {'enabled': enabled, 'roots': [{'path': str(target.parent)}]})
    if enabled:
        assert connected_read_path(vault, str(target)) == target.resolve()
    else:
        with pytest.raises(TypeError):
            connected_read_path(vault, str(target))


def test_third_party_attached_pdf_reads_without_grant_and_retains_provenance(attached, monkeypatch):
    from resource_librarian import text
    from resource_librarian.registry import Context, REGISTRY
    import resource_librarian.tools
    vault, source = attached
    pdf = source / "papers/a.pdf"
    monkeypatch.setattr(text, "extract", lambda *args: text.Extraction(pages=["Paper text"]))
    result = REGISTRY.call("read_file", {"path": str(pdf)}, Context(tier="consult", vault=vault))
    assert result.get("text") == "Paper text", result
    assert any(row["authorship"] == "third_party" for row in result["access"]["sources"])
    assert result["access"]["taint_sources"]


def test_authorship_lookup_does_not_validate_presentation_descriptions(vault, monkeypatch):
    from resource_librarian.folder_review import decision_for
    from resource_librarian.staging import StagingStore
    from resource_librarian import provenance
    decision = {"purpose": "third-party", "authorship": "third_party"}
    StagingStore(vault).add({"id": "folder-policy", "kind": "folder",
        "source_root": str(vault.root), "path": "papers", "status": "accepted",
        "decision": decision, "description": {"text": "Presentation only"}})
    def refuse(*a, **kw):
        raise AssertionError("policy lookup rebuilt the presentation provenance")
    monkeypatch.setattr(provenance, "check_sections", refuse)
    assert decision_for(vault, vault.root / "papers/a.pdf") == decision


@pytest.mark.parametrize("handle", ["https://example.org/paper", "file:3820cc3f43198421", "conversion:abc123"])
def test_evidence_handles_are_not_treated_as_local_paths(vault, monkeypatch, handle):
    from types import SimpleNamespace
    from resource_librarian.access import _native_authorship
    import resource_librarian.folder_review as folders
    def refuse(*a, **kw):
        raise AssertionError("non-path evidence handle entered folder policy resolution")
    monkeypatch.setattr(folders, "decision_for", refuse)
    assert _native_authorship(SimpleNamespace(vault=vault), handle) is None


# --- Scope (owner, 2026-11-16): a vendored repository's thousands of .txt/.rst files are not Sources ---

def test_default_scope_is_pdfs_only_so_a_folder_never_queues_thousands_of_text_files(attached):
    from resource_librarian.folder_sources import documents
    vault, source = attached
    assert [p.name for p in documents(vault, str(source / "papers"))] == ["a.pdf"]


def test_scope_is_chosen_per_call_and_validated(attached):
    from resource_librarian.folder_sources import documents
    vault, source = attached
    names = lambda scope: sorted(p.name for p in documents(vault, str(source / "papers"), scope=scope))
    assert names((".md",)) == ["b.md"] and names((".pdf", ".txt")) == ["a.pdf", "c.txt"]
    with pytest.raises(ValueError, match="FOLDER_SOURCES"):
        documents(vault, str(source / "papers"), scope=(".py",))
    with pytest.raises(ValueError, match="FOLDER_SOURCES"):
        documents(vault, str(source / "papers"), scope=())


def test_queue_reports_what_the_scope_left_out_so_the_owner_sees_it(attached):
    from resource_librarian.folder_sources import queue
    vault, source = attached
    out = queue(vault, str(source / "papers"), ingest=lambda ref, note: {"status": "queued"}, limit=10)
    assert out["scope"] == [".pdf"] and out["queued"] == 1
    assert out["not_in_scope"] == {".md": 1, ".txt": 1}                # visible, free, and widenable
