"""CORE-03: session events go through the active Core's writer.

Session logs were appended beside the writer, so their order relative to
the vault writes they describe was not guaranteed.  Offline tooling (no
Core in the process) keeps the direct path, byte-compatibly.
"""
import json
import threading

import pytest

from resource_librarian import session as session_module
from resource_librarian.app import App
from resource_librarian.session import SessionStore, verify_chain
from resource_librarian.vault import jsonl_lines


@pytest.fixture
def core(vault):
    app = App(vault, coordinate=True)
    yield app
    app.close_runtime()


def _ops(vault):
    path = vault.librarian / "runtime" / "operations.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] \
        if path.exists() else []


def _lines(store, session_id):
    return jsonl_lines(store.path(session_id).read_text(encoding="utf-8"))


def test_offline_appends_stay_direct_and_chained(vault):
    store = SessionStore(vault)
    opened = store.new("explore", question="q")
    store.append(opened.id, {"type": "message", "role": "user", "text": "hi"})
    assert session_module.core_writer(vault) is None
    assert verify_chain(_lines(store, opened.id)) == ""
    assert _ops(vault) == []                         # no Core, no writer trail


def test_with_a_core_every_store_appends_through_its_writer(core, vault):
    store = SessionStore(vault)                      # any module's store, not the App's
    opened = store.new("explore", question="q")
    store.append(opened.id, {"type": "message", "role": "user", "text": "hi"})
    callers = [op["caller"] for op in _ops(vault)]
    assert callers.count("session-event") >= 4       # opened + message, start and finish each
    assert verify_chain(_lines(store, opened.id)) == ""
    reloaded = store.load(opened.id)
    assert reloaded.purpose == "explore"


def test_a_write_and_the_event_describing_it_keep_their_order(core, vault):
    store = SessionStore(vault)
    opened = store.new("explore", question="q")
    order = []
    core.writer.submit(lambda: order.append("write"), caller="tool")
    store.append(opened.id, {"type": "message", "role": "assistant", "text": "done"})
    order.append("event")
    ops = [op["caller"] for op in _ops(vault) if op.get("finished_at")]
    assert order == ["write", "event"]
    assert ops.index("tool") < len(ops) - 1 and ops[-1] == "session-event"


def test_concurrent_appends_keep_one_unbroken_chain(core, vault):
    store = SessionStore(vault)
    opened = store.new("explore", question="q")
    before = len(_lines(store, opened.id))

    def burst(n):
        for i in range(25):
            store.append(opened.id, {"type": "message", "role": "user", "text": f"{n}-{i}"})
    threads = [threading.Thread(target=burst, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    lines = _lines(store, opened.id)
    assert len(lines) == before + 8 * 25
    assert verify_chain(lines) == ""


def test_rewind_goes_through_the_writer_and_keeps_the_chain(core, vault):
    store = SessionStore(vault)
    opened = store.new("explore", question="q")
    for text in ("one", "two", "three"):
        store.append(opened.id, {"type": "message", "role": "user", "text": text})
    store.truncate_to(opened.id, 1)
    assert "session-rewind" in [op["caller"] for op in _ops(vault)]
    lines = _lines(store, opened.id)
    events = [json.loads(line) for line in lines if line.strip()]
    assert [e["text"] for e in events if e["type"] == "message"] == ["one", "two"]
    assert verify_chain(lines) == ""


def test_a_stopped_core_detaches_only_its_own_writer(vault):
    first = App(vault, coordinate=True)
    writer = first.writer
    assert session_module.core_writer(vault) is writer
    first.close_runtime()
    assert session_module.core_writer(vault) is None
    successor = App(vault, coordinate=True)
    try:
        session_module.detach_core_writer(vault, writer)      # a late, stale detach
        assert session_module.core_writer(vault) is successor.writer
    finally:
        successor.close_runtime()
