"""Desk/lens connections must close even when setup or a transaction fails."""
from __future__ import annotations

import sqlite3

import pytest

from resource_librarian.desk import DeskStore
from resource_librarian.lenses import LensStore


@pytest.fixture
def connections(monkeypatch):
    original = sqlite3.connect
    opened = []

    class Tracked(sqlite3.Connection):
        closed = False

        def close(self):
            self.closed = True
            return super().close()

    def connect(*args, **kwargs):
        conn = original(*args, **{**kwargs, "factory": Tracked})
        opened.append(conn)
        return conn

    monkeypatch.setattr(sqlite3, "connect", connect)
    yield opened
    for conn in opened:
        if not conn.closed:
            conn.close()


@pytest.mark.parametrize("operation", [
    lambda store: store.pin("Project", "Note"),
    lambda store: store.unpin("Project", "Note"),
    lambda store: store.touch("Project", "Note"),
    lambda store: store.working_set("Project"),
])
def test_desk_operations_close_without_waiting_for_gc(vault, connections, operation):
    operation(DeskStore(vault))
    assert len(connections) == 1
    assert connections[0].closed


def test_lens_migration_failure_closes_connection(vault, connections, monkeypatch):
    def fail(*_args):
        raise RuntimeError("migration failed")

    monkeypatch.setattr(LensStore, "_migrate", fail)
    with pytest.raises(RuntimeError, match="migration failed"):
        LensStore(vault).list()
    assert len(connections) == 1
    assert connections[0].closed


def test_desk_body_failure_closes_and_rolls_back(vault, connections):
    store = DeskStore(vault)
    with pytest.raises(RuntimeError, match="aborted"):
        with store._conn() as conn:
            conn.execute("INSERT INTO desk VALUES (?, ?, ?, ?, ?)", ("P", "N", 1, 1, "now"))
            raise RuntimeError("aborted")
    assert connections[0].closed
    assert store.working_set("P") == []
    assert all(conn.closed for conn in connections)


def test_lens_reads_preserve_existing_cleanup(vault, connections):
    store = LensStore(vault)
    assert store.list() == []
    assert store.get("missing") is None
    assert store.origins() == {}
    assert store.suggest() == []
    assert all(conn.closed for conn in connections)


def test_desk_has_bounded_busy_timeout(vault):
    with DeskStore(vault)._conn() as conn:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_lens_has_bounded_busy_timeout(vault):
    conn = LensStore(vault)._conn()
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    finally:
        conn.close()
