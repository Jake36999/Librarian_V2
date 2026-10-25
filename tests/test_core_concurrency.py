"""Bounded real-loopback contention checks for the Windows-local Core.

These are repeatable native fixtures, not a long-running desktop certification.
Every client uses Core APIs; maintenance alone touches the owned IndexService.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

from resource_librarian import notes, tools  # noqa: F401
from resource_librarian.app import App, build
from resource_librarian.coordination import on_writer_thread
from resource_librarian.desk import DeskStore
from resource_librarian.file_access import file_access
from resource_librarian.keys import KeyStore
from resource_librarian.lenses import LensStore
from resource_librarian.registry import Context, REGISTRY
from resource_librarian.session import SessionStore
from resource_librarian.staging import StagingStore
from resource_librarian.tools import authoring

from test_app import Client
from test_lens_use import lens


@pytest.fixture
def core(vault):
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=5)
    app.broker.set_mode("auto")
    yield app
    app.close_runtime()


def _ok(result):
    assert "error" not in result, result
    return result


def test_chat_desk_touches_use_the_core_writer(core, monkeypatch):
    _ok(core.person_call("create_project", {"name": "Stress", "stage": "active", "summary": "Project"}))
    _ok(core.person_call("write_note", {"folder": "Notes", "name": "Shared", "body": "Shared"}))
    sid = core.person_call("open_session", {"purpose": "explore", "project": "Stress"})["opened"]
    core.loop = SimpleNamespace(ctx=SimpleNamespace(session=sid))
    original, calls = DeskStore.touch, []

    def touch(store, project, note):
        calls.append(on_writer_thread())
        return original(store, project, note)

    monkeypatch.setattr(DeskStore, "touch", touch)
    try:
        core._touch_desk("Read [[Shared]] with me.")
        assert calls == [True]
        assert DeskStore(core.vault).working_set("Stress")[0]["touches"] == 1
    finally:
        core.loop = None


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_concurrent_loopback_clients_refresh_checkpoint_and_auxiliary_stores(vault, monkeypatch, seed):
    original = sqlite3.connect
    connections, sql_threads, checkpoints = [], set(), []
    guard = threading.Lock()

    class Tracked(sqlite3.Connection):
        def close(self):
            if hasattr(self, "record"):
                self.record["closed"] = True
            return super().close()

    def connect(path, *args, **kwargs):
        conn = original(path, *args, **{**kwargs, "factory": Tracked})
        record = {"path": Path(path).name, "closed": False, "thread": threading.current_thread()}
        conn.record = record
        with guard:
            connections.append(record)
        if record["path"] == "index.sqlite":
            def trace(sql):
                with guard:
                    sql_threads.add(threading.current_thread())
                    if "wal_checkpoint" in sql.lower():
                        checkpoints.append(sql)
            conn.set_trace_callback(trace)
        return conn

    monkeypatch.setattr(sqlite3, "connect", connect)
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=5)
    app.broker.set_mode("auto")
    server = build(app, 0)
    serving = threading.Thread(target=server.serve_forever, daemon=True)
    serving.start()
    request_ms = []

    class TimedClient(Client):
        def request(self, *args, **kwargs):
            started = time.monotonic()
            try:
                return super().request(*args, **kwargs)
            finally:
                with guard:
                    request_ms.append((time.monotonic() - started) * 1000)

    client = TimedClient(server, app.token)
    started = time.monotonic()
    rounds = 6
    barrier = threading.Barrier(7)
    counts = Counter()

    def tool(tool_name, **arguments):
        status, payload = client.post("/api/tool/" + tool_name, {"arguments": arguments})
        assert status == 200, payload
        return _ok(payload)

    def run(label, action):
        barrier.wait(10)
        for index in range(rounds):
            action(index)
            with guard:
                counts[label] += 1

    try:
        tool("create_project", name="Stress", stage="active", summary="Project")
        tool("write_note", folder="Notes", name="Shared", body="Initial shared note")
        tool("write_note", folder="Notes", name="Human", body="Human baseline")
        sid = tool("open_session", purpose="explore", project="Stress")["opened"]
        app.writer.submit(lambda: [StagingStore(vault).add({
            **lens(name=f"Stress lens {seed}-{index}"), "id": f"lens-{index}",
            "kind": "lens", "status": "staged", "sensitivity": "normal",
        }) for index in range(rounds)], caller="stress-fixture")

        def browser(index):
            tool("write_note", folder="Notes", name=f"Browser{seed}-{index}", body=f"browser-{index}")
            tool("desk_touch", project="Stress", note="Shared")

        def mcp(index):
            status, payload = client.post("/api/mcp/call", {"tool": "write_note", "tier": "contribute",
                "arguments": {"folder": "Notes", "name": f"MCP{seed}-{index}", "body": f"mcp-{index}"}})
            assert status == 200, payload
            _ok(payload["result"])

        def agent(index):
            ctx = Context(tier="contribute", vault=vault, extras={**app._extras(), "caller": "stress-agent"})
            _ok(REGISTRY.call("write_note", {"folder": "Notes", "name": f"Agent{seed}-{index}",
                                             "body": f"agent-{index}"}, ctx))
            SessionStore(vault).append(sid, {"type": "plan", "fields": {f"stress-{index}": "🧭 verified"}})

        def reader(index):
            assert tool("get_note", name="Shared")["found"]
            tool("search", query="shared", intent="made")
            tool("desk_show", project="Stress")
            tool("lens_suggest", query="stress")

        def maintenance(index):
            app.index_service.refresh()
            app.index_service.checkpoint()

        def lenses(index):
            assert tool("staging_decide", item_ids=[f"lens-{index}"], decision="accept")["accepted"] == 1

        def obsidian(index):
            status, payload = client.post("/api/documents/heartbeat", {
                "path": "Notes/Human.md", "dirty": True, "editor": "Obsidian",
            }, headers={"Origin": "app://obsidian.md"})
            assert status == 200, payload
            (vault.root / "Notes/Human.md").write_text(f"# Human\n\nHuman iteration {index}\n", encoding="utf-8")

        errors = []

        def bounded_run(name, action):
            try:
                run(name, action)
            except BaseException as exc:
                with guard:
                    errors.append((name, exc))
                barrier.abort()

        workers = [threading.Thread(target=bounded_run, args=(name, action), daemon=True,
                                    name=f"stress-{name}") for name, action in (
            ("browser", browser), ("mcp", mcp), ("agent", agent), ("reader", reader),
            ("maintenance", maintenance), ("lenses", lenses), ("obsidian", obsidian))]
        for worker in workers:
            worker.start()
        deadline = time.monotonic() + 45
        for worker in workers:
            worker.join(max(0, deadline - time.monotonic()))
        assert not [worker.name for worker in workers if worker.is_alive()], "contention workers timed out"
        assert not errors, errors

        assert counts == Counter({name: rounds for name in (
            "browser", "mcp", "agent", "reader", "maintenance", "lenses", "obsidian")})
        assert client.post("/api/documents/release", {"path": "Notes/Human.md"})[0] == 200
        app.index_service.refresh()
        assert app.index_service.run(lambda ix: ix.conn.execute("PRAGMA integrity_check").fetchone()[0]) == "ok"
        assert len(checkpoints) == rounds
        assert sql_threads == {app.index_service._thread}
        assert len([record for record in connections if record["path"] == "index.sqlite"]) == 1
        for prefix in ("Browser", "MCP", "Agent"):
            for index in range(rounds):
                name = f"{prefix}{seed}-{index}"
                assert (vault.root / "Notes" / f"{name}.md").is_file()
                assert app.index_service.run(lambda ix, n=name: ix.note_row(n) is not None)
        assert "Human iteration 5" in (vault.root / "Notes/Human.md").read_text(encoding="utf-8")
        session = SessionStore(vault).load(sid)
        assert all(session.plan[f"stress-{index}"] == "🧭 verified" for index in range(rounds))
        assert SessionStore(vault).verify() == []
        assert DeskStore(vault).working_set("Stress")[0]["touches"] == rounds
        assert len(LensStore(vault).list()) == rounds
        assert LensStore(vault).verify() == {"chain": "", "changed": [], "unrecorded": 0}
        assert app.watcher._thread.is_alive()
    finally:
        server.shutdown()
        server.server_close()
        serving.join(3)
        app.close_runtime()
    assert all(record["closed"] for record in connections), connections
    operations = [json.loads(line) for line in app.writer.log_path.read_text(encoding="utf-8").splitlines()]
    starts = {row["id"] for row in operations if row["status"] == "running"}
    done = {row["id"] for row in operations if row["status"] == "done"}
    assert starts == done
    assert len(request_ms) == 59
    latencies = sorted(request_ms)
    print("CONCURRENCY_METRICS " + json.dumps({
        "repetition": seed, "workers": 7, "rounds_per_worker": rounds,
        "category_iterations": sum(counts.values()), "http_requests": len(request_ms),
        "http_p50_ms": round(latencies[len(latencies) // 2], 2),
        "http_p95_ms": round(latencies[int(0.95 * (len(latencies) - 1))], 2),
        "http_max_ms": round(max(latencies), 2), "elapsed_seconds": round(time.monotonic() - started, 2),
        "index_connections": 1, "checkpoint_calls": len(checkpoints),
        "closed_store_connections": dict(Counter(record["path"] for record in connections)),
        "operation_ids": len(starts), "unfinished_operations": len(starts - done),
        "model_calls": 0,
    }, sort_keys=True))


def test_obsidian_typing_only_blocks_affected_note_and_requires_explicit_retry(core):
    _ok(core.person_call("write_note", {"folder": "Notes", "name": "Human", "body": "Baseline"}))
    target = core.vault.root / "Notes/Human.md"
    for index in range(3):
        core.document_heartbeat("Notes/Human.md", editor="Obsidian", dirty=True)
        target.write_text(f"# Human\n\nHuman iteration {index}\n", encoding="utf-8")
        assert core.mcp_call("get_note", {"name": "Human"}, tier="contribute")["result"]["found"]
        _ok(core.person_call("write_note", {"folder": "Notes", "name": f"Other{index}", "body": "Unrelated"}))
    assert core.checkpoints.all() == []  # Typing/reading alone creates no approval spam.
    revision = core.mcp_call("get_note", {"name": "Human"}, tier="contribute")["result"]["revision"]
    refused = core.mcp_call("edit_note", {"note": "Human", "section": "Result", "text": "Committed",
                                           "revision": revision}, tier="contribute")["result"]
    assert refused["refused"] == "DOCUMENT_ACTIVE"
    assert len(core.checkpoints.all()) == 1
    checkpoint = refused["checkpoint"]
    core.document_release("Notes/Human.md", editor="Obsidian")
    stamp = (target.stat().st_mtime_ns, target.stat().st_size)
    deadline = time.monotonic() + 4
    while core.watcher._known.get("Notes/Human.md") != stamp or not core.document_leases.quiet("Notes/Human.md"):
        assert time.monotonic() < deadline, "editor quiet window did not settle"
        threading.Event().wait(0.02)
    core.checkpoint_resolve(checkpoint["id"], "retry_after_review")
    assert "Committed" not in target.read_text(encoding="utf-8")  # A button never retries a write itself.
    fresh = core.mcp_call("get_note", {"name": "Human"}, tier="contribute")["result"]["revision"]
    _ok(core.mcp_call("edit_note", {"note": "Human", "section": "Result", "text": "Committed",
                                    "revision": fresh}, tier="contribute")["result"])
    text = target.read_text(encoding="utf-8")
    assert "Human iteration 2" in text and "Committed" in text
    assert len(core.checkpoints.all()) == 1


@pytest.mark.parametrize("read_mode", ["get_note", "pane", "load", "upsert"])
def test_core_note_read_closes_before_prepared_writer_replaces_it(core, monkeypatch, read_mode):
    _ok(core.person_call("write_note", {"folder": "Notes", "name": "Shared", "body": "Initial"}))
    target = core.vault.root / "Notes/Shared.md"
    prepared, allow_write, reading, release_read, probed = (threading.Event() for _ in range(5))
    original_write, original_open = authoring.atomic_write_text, Path.open
    results = {}

    def write(path, text, *args, **kwargs):
        if path == target:
            prepared.set()
            assert allow_write.wait(5)
            lock = file_access(path)
            acquired = lock.acquire(blocking=False)
            if acquired:
                lock.release()
            try:
                assert not acquired, "the active Core note reader did not hold its path lock"
            finally:
                probed.set()
        return original_write(path, text, *args, **kwargs)

    class Reader:
        def __init__(self, *args, **kwargs):
            self.reader = original_open(target, *args, **kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.reader.close()

        def read(self, *args):
            reading.set()
            assert release_read.wait(5)
            return self.reader.read(*args)

    def open_path(path, *args, **kwargs):
        if path == target and prepared.is_set() and not release_read.is_set() and \
                threading.current_thread() in (reader, core.index_service._thread):
            return Reader(*args, **kwargs)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(authoring, "atomic_write_text", write)
    monkeypatch.setattr(Path, "open", open_path)
    writer = threading.Thread(target=lambda: results.update(write=core.person_call("edit_note", {
        "note": "Shared", "section": "Result", "text": "Committed"})))
    def read_note():
        if read_mode == "get_note":
            result = core.person_call("get_note", {"name": "Shared"})
            assert result["found"]
        elif read_mode == "pane":
            result = core.read_file("Notes/Shared.md")
        elif read_mode == "load":
            result = notes.load(target)
        else:
            result = core.index_service.run(lambda ix: ix.upsert(target, force=True))
        results["read"] = result

    reader = threading.Thread(target=read_note)
    writer.start()
    try:
        assert prepared.wait(5)
        reader.start()
        assert reading.wait(5)
        allow_write.set()
        assert probed.wait(5), "writer did not reach the reader-lock probe"
    finally:
        allow_write.set()
        release_read.set()
        writer.join(8)
        if reader.ident is not None:
            reader.join(8)
    assert not writer.is_alive() and not reader.is_alive()
    _ok(results["write"])
    assert "read" in results
    assert "Committed" in target.read_text(encoding="utf-8")
