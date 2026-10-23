"""Core-owned index boundaries for adapter/agent request contexts."""
from __future__ import annotations

import pytest

from resource_librarian import communities, extract
from resource_librarian.index import IndexService
from resource_librarian.registry import Context
from resource_librarian.tools import library

from conftest import add_source


def _no_direct_index(*_args, **_kwargs):
    raise AssertionError("an App-backed request opened a second SQLite index")


def test_library_reads_use_the_core_index_worker(vault, monkeypatch):
    add_source(vault.root, "osquery", "Query operating system state with SQL.")
    service = IndexService(vault)
    ctx = Context(tier="curate", vault=vault, extras={"index_service": service})
    try:
        # Construct the service first, then prove a request path does not
        # instantiate library.Index in the calling/adaptor thread.
        monkeypatch.setattr(library, "Index", _no_direct_index)
        found = library.search_tool(ctx, "operating system SQL")
        status = library.index_status(ctx)
    finally:
        service.close()
    assert found["results"][0]["name"] == "osquery"
    assert status["notes"] >= 1


def test_first_party_packs_accept_the_core_index_service(vault, monkeypatch):
    add_source(vault.root, "osquery", "Query operating system state with SQL.")
    service = IndexService(vault)
    try:
        monkeypatch.setattr(communities, "Index", _no_direct_index)
        built = communities.rebuild(vault, index_service=service)
        monkeypatch.setattr(extract, "Index", _no_direct_index)
        with pytest.raises(TypeError, match="catalogued repository"):
            extract.plan(vault, "missing", index_service=service)
    finally:
        service.close()
    assert built["advisory"] is True


def test_index_service_closes_after_accepted_work_and_rejects_new_work(vault):
    service = IndexService(vault)
    assert service.stats()["notes"] == 0
    service.close()

    with pytest.raises(RuntimeError, match="closed"):
        service.stats()
