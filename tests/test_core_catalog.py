"""Catalogue promotion has bounded plans, Core SQL and visible partial outcomes."""
from dataclasses import replace
import json
import threading

import pytest

from resource_librarian import embed, model_catalog, notes, promote as promotion
from resource_librarian.app import App
from resource_librarian.coordination import on_writer_thread
from resource_librarian.evidence import EvidenceStore
from resource_librarian.index import Index
from resource_librarian.keys import KeyStore
from resource_librarian.registry import Context, REGISTRY
from resource_librarian.tools import library

from conftest import add_source, write_note
from test_model_catalog import FAKE


@pytest.fixture
def core(vault, monkeypatch):
    monkeypatch.setattr(model_catalog, "catalogue", lambda provider: FAKE)
    monkeypatch.setattr(model_catalog, "providers", lambda: ["testprovider"])
    write_note(vault.root, "Concepts/Widget.md", "type: concept\nstatus: active",
               "# Widget\n\n## Definition\nMy own definition, never replace it.\n")
    for i in range(4):
        add_source(vault.root, f"filler-{i}", f"A different subject number {i}.")
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False))
    try:
        yield app
    finally:
        app.close_runtime()


def _ctx(core):
    return Context(tier="curate", vault=core.vault, extras={
        "index_service": core.index_service, "vault_writer": core.writer,
        "document_leases": core.document_leases, "checkpoints": core.checkpoints,
        "caller_kind": "person"})


def _forbid(*a, **kw):
    raise AssertionError("catalogue constructed a second Index")


def _source(core, entry=FAKE[0]):
    return core.vault.root / "Sources/model" / f"{entry.name}.md"


def _adopt(core, **kw):
    return core.person_call("model_catalog_adopt", {"provider": "testprovider", **kw})


def test_catalogue_uses_core_sql_and_writer_files_and_retains_public_contract(core, monkeypatch):
    sql, files = [], []
    upsert, atomic = Index.upsert, promotion.atomic_write_text
    def indexed(self, path, **kw):
        sql.append(threading.current_thread())
        return upsert(self, path, **kw)
    def write(path, text):
        assert on_writer_thread()
        files.append(path)
        return atomic(path, text)
    monkeypatch.setattr(Index, "upsert", indexed)
    monkeypatch.setattr(promotion, "atomic_write_text", write)
    monkeypatch.setattr(library, "Index", _forbid)
    out = _adopt(core)
    assert out == {"provider": "testprovider", "written": 2, "already_held": 0, "failed": []}
    assert files and set(sql) == {core.index_service._thread}
    assert EvidenceStore(core.vault).verify() == []
    note = notes.load(_source(core))
    assert note.frontmatter["attested_by"] == "person"
    assert "needs_attention" not in note.frontmatter
    concept = (core.vault.root / "Concepts/Widget.md").read_text(encoding="utf-8")
    assert "My own definition" in concept and f"[[{FAKE[0].name}]]" in concept
    assert f"[[{FAKE[1].name}]]" in concept
    before = _source(core).read_bytes()
    assert _adopt(core) == {"provider": "testprovider", "written": 0, "already_held": 2, "failed": []}
    assert _source(core).read_bytes() == before
    events = [json.loads(line) for line in core.writer.log_path.read_text(encoding="utf-8").splitlines()]
    done = [e for e in events if e["caller"] == "model-catalog" and e["status"] == "done"]
    assert len(done) == 2
    assert any(p.startswith(".evidence/") for p in done[0]["targets"])
    assert "Concepts/Widget.md" in done[0]["targets"]
    assert ".librarian/config.toml" in done[0]["precondition_fingerprints"]
    assert not any("routes.json" in p for e in done for p in e["targets"])


@pytest.mark.parametrize("target", ["Concepts/Widget.md", "Indexes/Master Index.md"])
def test_active_human_target_refuses_before_evidence_or_source_and_surfaces_checkpoint(core, target):
    core.document_leases.heartbeat(target, editor="Obsidian", dirty=True)
    out = _adopt(core)
    assert out["written"] == 0 and len(out["failed"]) == 2
    assert out["checkpoint"]["type"] == "write_conflict"
    assert all(row["refused"] == "DOCUMENT_ACTIVE" for row in out["failed"])
    assert not list(core.vault.evidence.glob("*/*.json"))
    assert not _source(core).exists()


def test_mid_promotion_conflict_reports_partial_paths_and_leaves_attention_marker(core, monkeypatch):
    original = Index.upsert
    def upsert(self, path, **kwargs):
        result = original(self, path, **kwargs)
        if path == _source(core):
            core.document_leases.heartbeat("Indexes/Master Index.md", editor="Obsidian", dirty=True)
        return result
    monkeypatch.setattr(Index, "upsert", upsert)
    out = _adopt(core)
    first = out["failed"][0]
    assert out["written"] == 0 and first["refused"] == "DOCUMENT_ACTIVE"
    assert _source(core).relative_to(core.vault.root).as_posix() in first["completed_paths"]
    assert any(path.startswith(".evidence/") for path in first["completed_paths"])
    assert "promotion incomplete" in notes.load(_source(core)).frontmatter["needs_attention"]
    status = core.person_call("model_catalog_status", {})["catalogues"][0]
    assert status["needs_attention"] == [FAKE[0].name]
    # Re-adoption never tries to repair/overwrite a partly written accepted note.
    before = _source(core).read_bytes()
    assert _adopt(core)["already_held"] == 1
    assert _source(core).read_bytes() == before


@pytest.mark.parametrize("change", ["schema", "concept", "destination"])
def test_change_between_plan_and_commit_cannot_replace_unseen_content(core, monkeypatch, change):
    original = core.writer.submit
    changed = []
    def submit(fn, **kwargs):
        if kwargs.get("caller") == "model-catalog" and not changed:
            path = (core.vault.root / "About/Note Content Model.md" if change == "schema" else
                    core.vault.root / "Concepts/Widget.md" if change == "concept" else _source(core))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(path.read_text(encoding="utf-8") + "\nHuman edit.\n" if path.exists()
                            else "A human note not yet indexed.\n", encoding="utf-8")
            changed.append(path)
        return original(fn, **kwargs)
    monkeypatch.setattr(core.writer, "submit", submit)
    out = _adopt(core)
    assert out["failed"][0]["refused"] == "DOCUMENT_ACTIVE"
    if change == "destination":
        assert _source(core).read_text(encoding="utf-8") == "A human note not yet indexed.\n"
    else:
        assert not _source(core).exists()


def test_invalid_entry_is_rejected_before_its_evidence_is_written(core, monkeypatch):
    monkeypatch.setattr(model_catalog, "catalogue", lambda provider: [replace(FAKE[0], bottom_line="")])
    out = _adopt(core)
    assert len(out["failed"]) == 1 and out["written"] == 0
    assert not list(core.vault.evidence.glob("*/*.json")) and not _source(core).exists()


def test_evidence_collision_is_never_repaired_or_overwritten(core, monkeypatch):
    monkeypatch.setattr(model_catalog, "catalogue", lambda provider: [FAKE[0]])
    ev = FAKE[0].evidence
    record = EvidenceStore(core.vault).prepare(ev["kind"], ev["source"], ev["payload"], ev["fetched_at"])
    path = EvidenceStore(core.vault)._path(record.kind, record.id)
    core.writer.submit(lambda: (path.parent.mkdir(parents=True, exist_ok=True),
        path.write_text('{"corrupted": true}', encoding="utf-8")))
    out = _adopt(core)
    assert out["failed"][0]["refused"] == "EVIDENCE_IS_NEVER_EDITED"
    assert path.read_text(encoding="utf-8") == '{"corrupted": true}'
    assert not _source(core).exists()


def test_unrelated_human_lease_does_not_block_catalogue(core):
    core.document_leases.heartbeat("Notes/working-note.md", editor="Obsidian", dirty=True)
    assert _adopt(core)["written"] == 2


@pytest.mark.parametrize("closed", ["index", "writer"])
def test_closed_core_never_falls_back_to_direct_writes(core, monkeypatch, closed):
    monkeypatch.setattr(library, "Index", _forbid)
    (core.index_service if closed == "index" else core.writer).close()
    out = REGISTRY.call("model_catalog_adopt", {"provider": "testprovider"}, _ctx(core))
    assert out["error"] == "failed"
    assert not list(core.vault.evidence.glob("*/*.json")) and not _source(core).exists()


def test_catalogue_is_person_tier_and_model_cards_never_qualify_routes(core):
    before = (dict(core.qualifications.runs), dict(core.qualifications.qualifications))
    path = core.qualifications.path
    previous = path.read_bytes() if path.exists() else None
    ctx = _ctx(core)
    ctx.tier = "contribute"
    assert REGISTRY.call("model_catalog_adopt", {"provider": "testprovider"}, ctx)["refused"] == "TIER_REFUSED"
    assert _adopt(core)["written"] == 2
    assert (core.qualifications.runs, core.qualifications.qualifications) == before
    assert (path.read_bytes() if path.exists() else None) == previous


@pytest.mark.parametrize("mode", ["valid", "invalid", "changed"])
def test_source_embedding_io_releases_core_worker_and_validates_results(vault, monkeypatch, mode):
    pytest.importorskip("numpy")
    vault.set_setting("services", "embeddings", "hash:16")
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False))
    monkeypatch.setattr(model_catalog, "catalogue", lambda provider: [FAKE[0]])
    called = []
    import numpy as np
    def encode(texts):
        assert threading.current_thread() is not app.index_service._thread
        assert app.index_service.stats()["notes"] > 0
        called.append(len(texts))
        if mode == "changed":
            vault.set_setting("services", "embeddings", "hash:8")  # direct operator config edit
        return np.full((len(texts), 16), float("nan") if mode == "invalid" else 1, dtype="float32")
    def encoders(spec, **kw):
        assert threading.current_thread() is not app.index_service._thread
        return "hash:16", encode, encode, {}
    monkeypatch.setattr(embed, "load_embedding_encoders", encoders)
    try:
        out = _adopt(app)
        assert called
        count = app.index_service.run(lambda ix: ix.conn.execute("SELECT COUNT(*) FROM embedding").fetchone()[0])
        if mode == "valid":
            assert out["written"] == 1 and "not_findable" not in out
            assert count > 0 and "needs_attention" not in notes.load(_source(app)).frontmatter
            # Reusing existing hashes needs no encoder call.
            before = len(called)
            assert embed.sync_source_via(vault, FAKE[0].name, library.IndexGateway(_ctx(app), include_vectors=False).run) == "0 chunk(s) embedded"
            assert len(called) == before
        elif mode == "invalid":
            assert out["written"] == 1 and out["not_findable"] == [FAKE[0].name]
            assert "embedding update failed" in notes.load(_source(app)).frontmatter["needs_attention"]
            assert count == 0
        else:
            assert out["written"] == 0 and out["failed"][0]["refused"] == "DOCUMENT_ACTIVE"
            assert "promotion incomplete" in notes.load(_source(app)).frontmatter["needs_attention"]
            assert count == 0
    finally:
        app.close_runtime()


def test_hosted_embedding_first_start_is_not_triggered_by_catalogue_adoption(vault, monkeypatch):
    pytest.importorskip("numpy")
    vault.set_setting("services", "embeddings", "deepinfra:BAAI/bge-m3")
    spec = embed.spec_for(vault)
    calls = []
    def encode(texts):
        calls.append(True)
        raise AssertionError("catalogue adoption spent tokens before the explicit first start")
    monkeypatch.setattr(embed, "load_embedding_encoders", lambda s, **kw: (spec, encode, encode, {}))
    monkeypatch.setattr(model_catalog, "catalogue", lambda provider: [FAKE[0]])
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False))
    try:
        out = _adopt(app)
        assert out["written"] == 1 and out["failed"] == [] and "not_findable" not in out
        assert calls == []
    finally:
        app.close_runtime()


def test_io_failure_retains_partial_marker_and_status_survives_restart(core, monkeypatch):
    original = promotion.atomic_write_text
    def write(path, text):
        if path.name == "Master Index.md":
            raise OSError("private-sentinel-must-not-appear-in-public-failure")
        return original(path, text)
    monkeypatch.setattr(promotion, "atomic_write_text", write)
    out = _adopt(core)
    assert out["written"] == 0 and len(out["failed"]) == 2
    assert all(f["completed_paths"] for f in out["failed"])
    assert "private-sentinel" not in json.dumps(out)
    assert "promotion incomplete" in notes.load(_source(core)).frontmatter["needs_attention"]
    core.close_runtime()
    app = App(core.vault, coordinate=True, keys=KeyStore(use_keyring=False))
    try:
        assert app.person_call("model_catalog_status", {})["catalogues"][0]["needs_attention"] == [e.name for e in FAKE]
    finally:
        app.close_runtime()


def test_concurrent_adoptions_never_replace_each_others_sources(core):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: _adopt(core), range(2)))
    assert sum(r["written"] for r in results) == 2, results
    assert all(_source(core, entry).is_file() for entry in FAKE)
    assert EvidenceStore(core.vault).verify() == []
    assert core.person_call("model_catalog_status", {})["catalogues"][0]["held"] == 2


def test_read_only_evidence_preparation_preserves_content_address(core):
    store = EvidenceStore(core.vault)
    ev = FAKE[0].evidence
    before = list(core.vault.evidence.glob("*/*.json"))
    record = store.prepare(ev["kind"], ev["source"], ev["payload"], ev["fetched_at"])
    assert list(core.vault.evidence.glob("*/*.json")) == before
    saved = core.writer.submit(lambda: store.put(record.kind, record.source, record.payload, record.fetched_at))
    assert saved == record and store.verify() == []


def test_provider_names_cannot_escape_package_resources():
    for provider in ("../models", "deepinfra/../deepinfra", "", "C:\\secret"):
        with pytest.raises(ValueError, match="no standard catalogue"):
            model_catalog.catalogue(provider)


def test_failed_vector_batch_rolls_back_before_other_core_work(vault, monkeypatch):
    pytest.importorskip("numpy")
    vault.set_setting("services", "embeddings", "hash:16")
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False))
    monkeypatch.setattr(model_catalog, "catalogue", lambda provider: [FAKE[0]])
    import numpy as np
    def encode(texts):
        # Fail the second insert, not the first: a partial executemany must
        # not be committed by the later needs_attention upsert.
        app.index_service.run(lambda ix: ix.conn.executescript(
            "CREATE TEMP TRIGGER fail_second_embedding BEFORE INSERT ON embedding "
            "WHEN (SELECT COUNT(*) FROM embedding) > 0 BEGIN SELECT RAISE(ABORT, 'fixture'); END;"))
        assert len(texts) > 1
        return np.ones((len(texts), 16), dtype="float32")
    monkeypatch.setattr(embed, "load_embedding_encoders", lambda spec, **kw: ("hash:16", encode, encode, {}))
    try:
        out = _adopt(app)
        assert out["not_findable"] == [FAKE[0].name]
        assert app.index_service.run(lambda ix: ix.conn.execute("SELECT COUNT(*) FROM embedding").fetchone()[0]) == 0
        assert not app.index_service.run(lambda ix: ix.conn.in_transaction)
    finally:
        app.close_runtime()
