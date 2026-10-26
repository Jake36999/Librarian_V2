"""INDEX-04: serving contexts cannot silently reopen the vault database."""
from __future__ import annotations

import base64
import threading

import pytest

from resource_librarian import communities, extract, intake, tools  # noqa: F401
from resource_librarian import index as index_module
from resource_librarian.app import App
from resource_librarian.index import IndexService, run_index
from resource_librarian.keys import KeyStore
from resource_librarian.registry import Context, REGISTRY
from resource_librarian.rules import Refusal
from resource_librarian.tools import communities as community_tools
from resource_librarian.tools import extract as extract_tools
from resource_librarian.tools import library
from resource_librarian.vault import Vault

from test_upkeep import surveyed


def _never_open(*_args, **_kwargs):
    raise AssertionError("unexpected direct index construction")


@pytest.fixture
def service(vault):
    service = IndexService(vault)
    yield service
    service.close()


@pytest.mark.parametrize("extra", [{"index_access": "core"}, {"vault_writer": object()},
                                    {"index_access": "invalid"}, {"caller": "core"},
                                    {"caller_kind": "mcp"}])
@pytest.mark.parametrize("operation", ["index", "engine", "sql_engine", "legacy", "builder"])
def test_missing_owner_refuses_before_any_direct_construction(vault, monkeypatch, extra, operation):
    monkeypatch.setattr(library, "Index", _never_open)
    monkeypatch.setattr(index_module, "Index", _never_open)
    ctx = Context(vault=vault, extras=dict(extra))
    with pytest.raises(Refusal) as refused:
        if operation == "index":
            library.with_index(ctx, lambda index: index.stats())
        elif operation == "engine":
            library.with_engine(ctx, lambda engine: engine.index.stats())
        elif operation == "sql_engine":
            library.with_engine(ctx, lambda engine: engine.index.stats(), include_vectors=False)
        elif operation == "legacy":
            library.engine_for(ctx)
        else:
            library._build_engine(ctx)
    assert refused.value.code == "CORE_REQUIRED"


@pytest.mark.parametrize("operation", [library.engine_for, library._build_engine])
def test_legacy_engine_cannot_escape_core_owner_even_if_cached(vault, service, operation, monkeypatch):
    monkeypatch.setattr(library, "Index", _never_open)
    ctx = Context(vault=vault, extras={"index_service": service, "engine": object()})
    with pytest.raises(Refusal, match="offline-only"):
        operation(ctx)


@pytest.mark.parametrize("mode", [None, "core", "offline"])
def test_foreign_service_never_opens_either_vault(vault, tmp_path, service, mode):
    other = Vault(tmp_path / "Other")
    ctx = Context(vault=other, extras={"index_service": service, "index_access": mode})
    with pytest.raises(Refusal) as refused:
        library.with_index(ctx, lambda index: index.stats())
    assert refused.value.code == "CORE_REQUIRED"
    assert not other.root.exists()
    assert not service._index.path.exists()


def test_explicit_offline_mode_cannot_disguise_a_supplied_core(vault, service):
    ctx = Context(vault=vault, extras={"index_service": service, "index_access": "offline"})
    with pytest.raises(Refusal):
        library.with_engine(ctx, lambda engine: engine.index.stats())
    with pytest.raises(Refusal):
        run_index(vault, lambda index: index.stats(), index_service=service, offline=True)


@pytest.mark.parametrize("extra", [{"caller": "core"}, {"caller_kind": "mcp"}])
def test_serving_caller_cannot_select_offline_after_losing_its_service(vault, extra):
    ctx = Context(vault=vault, extras={**extra, "index_access": "offline"})
    with pytest.raises(Refusal):
        library.with_index(ctx, lambda index: index.stats())


def test_closed_owner_refuses_without_falling_back(vault, service, monkeypatch):
    service.close()
    monkeypatch.setattr(library, "Index", _never_open)
    monkeypatch.setattr(index_module, "Index", _never_open)
    ctx = Context(vault=vault, extras={"index_service": service, "index_access": "core"})
    with pytest.raises(RuntimeError, match="closed"):
        library.with_engine(ctx, lambda engine: engine.index.stats())
    with pytest.raises(RuntimeError, match="closed"):
        library.with_index(ctx, lambda index: index.stats())
    assert not service._index.path.exists()


@pytest.mark.parametrize("operation", [
    lambda vault: run_index(vault, lambda index: index.stats()),
    lambda vault: communities.rebuild(vault),
    lambda vault: extract.plan(vault, "missing"),
    lambda vault: extract.materialize(vault, "missing"),
])
def test_direct_pack_api_requires_explicit_offline_or_core(vault, operation, monkeypatch):
    monkeypatch.setattr(index_module, "Index", _never_open)
    with pytest.raises(Refusal) as refused:
        operation(vault)
    assert refused.value.code == "CORE_REQUIRED"
    assert not (vault.derived / "communities.json").exists()
    assert not (vault.derived / "extract").exists()


@pytest.mark.parametrize("operation", [
    lambda ctx: community_tools.rebuild_communities(ctx),
    lambda ctx: extract_tools.extract_plan(ctx, "missing"),
    lambda ctx: extract_tools.extract_materialize(ctx, "missing"),
])
def test_registered_pack_functions_do_not_infer_offline_from_missing_service(vault, operation, monkeypatch):
    monkeypatch.setattr(index_module, "Index", _never_open)
    ctx = Context(vault=vault, extras={"index_access": "core"})
    with pytest.raises(Refusal):
        operation(ctx)


def test_core_callbacks_stay_on_worker_and_standalone_context_stays_compatible(vault, service):
    ctx = Context(vault=vault, extras={"index_access": "core", "index_service": service})
    assert library.with_index(ctx, lambda index: threading.current_thread()) is service._thread
    assert library.with_engine(ctx, lambda engine: engine.index.stats()["notes"]) >= 0
    service.close()
    # Legacy direct Context is the 2.x offline compatibility projection.
    assert library.with_index(Context(vault=vault), lambda index: index.stats()["notes"]) >= 0
    assert communities.rebuild(vault, offline=True)["advisory"] is True


def test_core_missing_service_is_a_structured_refusal_with_no_new_index(vault, monkeypatch):
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False))
    try:
        extras = app._extras()
        assert extras["index_access"] == "core"
        extras.pop("index_service")
        extras.pop("broker", None)
        extras.pop("agent_profile", None)
        monkeypatch.setattr(library, "Index", _never_open)
        result = REGISTRY.call("index_status", {}, Context(tier="curate", vault=vault, extras=extras))
        assert result["refused"] == "CORE_REQUIRED"
    finally:
        app.close_runtime()


def test_extract_network_io_runs_outside_worker_and_index_remains_responsive(vault, service):
    surveyed(vault, tree="abc123")
    api = "https://api.github.com/repos/example/planner"
    replay = intake.Replay({
        f"{api}/git/trees/abc123?recursive=1": {"tree": [
            {"path": "src/plan.py", "type": "blob", "sha": "b1"}]},
        f"{api}/git/blobs/b1": {"content": base64.b64encode(b"def plan():\n    pass\n").decode()},
    })
    calls = []

    class Fetcher:
        def get(self, url):
            assert threading.current_thread() is not service._thread
            assert service.stats()["notes"] >= 1
            calls.append(url)
            return replay.get(url)

    result = extract.materialize(vault, "planner", index_service=service, fetcher=Fetcher())
    assert len(calls) == 2
    assert result["excerpts"][0]["text"].startswith("def plan")
    assert result["excerpts"][0]["revision"] == "tree abc123 (as surveyed)"
    assert (vault.root / result["cache"]).is_file()


def test_extract_explicit_offline_mode_propagates_to_materialization(vault):
    surveyed(vault, tree="abc123")
    api = "https://api.github.com/repos/example/planner"
    replay = intake.Replay({
        f"{api}/git/trees/abc123?recursive=1": {"tree": [
            {"path": "src/plan.py", "type": "blob", "sha": "b1"}]},
        f"{api}/git/blobs/b1": {"content": base64.b64encode(b"print('read only')").decode()},
    })
    result = extract.materialize(vault, "planner", offline=True, fetcher=replay)
    assert result["materialized"] == 1
    assert extract.plan(vault, "planner", offline=True)["revision"] == "abc123"
