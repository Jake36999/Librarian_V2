"""Upkeep snapshots SQL in Core, then releases it for IO and derived writes."""
import base64
import threading

from resource_librarian import dik, intake, provenance, upkeep
from resource_librarian.app import App
from resource_librarian.coordination import on_writer_thread
from resource_librarian.keys import KeyStore
from resource_librarian.registry import Context, REGISTRY
from resource_librarian.tools import library

from conftest import add_source
from test_dik import repo_evidence
from test_upkeep import repos, surveyed


def test_upkeep_uses_core_queries_without_worker_owned_io(vault, monkeypatch):
    responses = repos(vault)
    surveyed(vault, tree="abc123")
    ids = repo_evidence(vault)
    add_source(vault.root, "acme - planner", "A query planner.",
               extra_fm="evidence:\n" + "".join(f"- {i}\n" for i in ids))
    api = "https://api.github.com/repos/example/planner"
    responses.update({f"{api}/git/trees/abc123?recursive=1": {
        "tree": [{"path": "src/plan.py", "type": "blob", "sha": "blob1"}]},
        f"{api}/git/blobs/blob1": {"content": base64.b64encode(b"def plan(): pass\n").decode()}})
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False))
    seen_sql, derived_writes, read_threads = [], [], []

    class Fetcher(intake.Replay):
        def get(self, url, accept=""):
            assert threading.current_thread() is not app.index_service._thread
            assert app.index_service.stats()["notes"] >= 1
            return super().get(url, accept)

    original_terms, original_check, original_save = upkeep._terms, provenance.check, dik.save
    def terms(*args, **kwargs):
        assert threading.current_thread() is not app.index_service._thread
        read_threads.append(threading.current_thread())
        return original_terms(*args, **kwargs)
    def check(*args, **kwargs):
        assert threading.current_thread() is not app.index_service._thread
        assert app.index_service.stats()["notes"] >= 1
        return original_check(*args, **kwargs)
    def save(*args, **kwargs):
        assert on_writer_thread()
        assert threading.current_thread() is not app.index_service._thread
        derived_writes.append(args[1]["source"])
        return original_save(*args, **kwargs)
    def no_direct(*args, **kwargs):
        raise AssertionError("a Core-backed upkeep call opened another SQLite index")
    ctx = Context(tier="curate", vault=vault, extras={"index_service": app.index_service,
        "vault_writer": app.writer, "caller_kind": "person", "fetcher": Fetcher(responses)})
    try:
        app.index_service.run(lambda index: index.conn.set_trace_callback(
            lambda sql: seen_sql.append((threading.current_thread(), sql))))
        monkeypatch.setattr(library, "Index", no_direct)
        monkeypatch.setattr(upkeep, "_terms", terms)
        monkeypatch.setattr(provenance, "check", check)
        monkeypatch.setattr(dik, "save", save)
        fresh = REGISTRY.call("freshness_check", {"source": "alpha"}, ctx)
        assert fresh["checked"] == 1 and fresh["warnings"] == 1, fresh
        duplicates = REGISTRY.call("duplicate_report", {}, ctx)
        assert duplicates["compared"] > 0 and read_threads, duplicates
        checked = REGISTRY.call("provenance_check", {"source": "planner"}, ctx)
        assert checked["supported"] >= 3 and checked["contradicted"] == 1, checked
        source = REGISTRY.call("read_source_file", {"source": "planner", "path": "src/plan.py"}, ctx)
        assert source["version"] == "tree abc123 (as surveyed)" and "def plan" in source["text"], source
        rebuilt = REGISTRY.call("dik_rebuild", {"source": "acme - planner"}, ctx)
        assert rebuilt["rebuilt"] == 1 and rebuilt["revisions_staged"] == 1, rebuilt
        assert derived_writes == ["acme - planner"]
        catalog = REGISTRY.call("model_catalog_status", {}, ctx)
        assert "catalogues" in catalog and "error" not in catalog, catalog
        assert seen_sql and {thread for thread, _ in seen_sql} == {app.index_service._thread}
    finally:
        app.close_runtime()
