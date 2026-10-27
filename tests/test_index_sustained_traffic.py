"""INDEX-05 sustained loopback and external-file contention characterization.

This slow fixture records timings but enforces correctness and ownership only.
It exercises the Browser, MCP and Obsidian HTTP contracts against one Core;
it is not evidence for separately packaged adapter processes.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from collections import Counter
from pathlib import Path

import pytest

from resource_librarian.app import App, build
from resource_librarian.coordination import VaultCoordinator
from resource_librarian.keys import KeyStore
from resource_librarian.notes import iter_paths

from test_app import Client


NOTE_COUNT = 750
ROUNDS = 30
WORKERS = 6


def _note(name: str, value: str) -> str:
    return f"# {name}\n\n## Evidence\n\nSustained traffic {value}.\n"


def _metadata(path: Path) -> tuple[int, int, str]:
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size, \
        f"{stat.st_dev}:{stat.st_ino}:{stat.st_ctime_ns}"


def _normalized_hash(path: Path) -> str:
    text = path.read_bytes().decode("utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


@pytest.mark.slow
def test_sustained_loopback_and_external_edits_converge(vault, monkeypatch):
    folder = vault.root / "Sustained"
    folder.mkdir()
    for number in range(NOTE_COUNT):
        name = f"Seed {number:04d}"
        (folder / f"{name}.md").write_text(
            _note(name, f"seed-{number:04d}"), encoding="utf-8")

    replacement_paths = [folder / f"Seed {number:04d}.md" for number in range(0, ROUNDS)]
    rename_paths = [folder / f"Seed {number:04d}.md" for number in range(100, 100 + ROUNDS)]
    delete_paths = [folder / f"Seed {number:04d}.md" for number in range(200, 200 + ROUNDS)]
    obsidian_paths = [folder / f"Seed {number:04d}.md" for number in range(300, 300 + ROUNDS)]

    original_connect = sqlite3.connect
    connections: list[dict] = []
    sql_threads: set[threading.Thread] = set()
    checkpoints: list[str] = []
    sharing_retries: Counter = Counter()
    guard = threading.Lock()

    def sharing_retry(label: str, action):
        """Tolerate only the brief CRT sharing window an editor would retry."""
        deadline = time.monotonic() + 2
        while True:
            try:
                return action()
            except PermissionError:
                with guard:
                    sharing_retries[label] += 1
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.01)

    class Tracked(sqlite3.Connection):
        def close(self):
            if hasattr(self, "record"):
                self.record["closed"] = True
            return super().close()

    def connect(path, *args, **kwargs):
        connection = original_connect(path, *args, **{**kwargs, "factory": Tracked})
        record = {"path": Path(path).name, "closed": False,
                  "thread": threading.current_thread()}
        connection.record = record
        with guard:
            connections.append(record)
        if record["path"] == "index.sqlite":
            def trace(sql):
                with guard:
                    sql_threads.add(threading.current_thread())
                    if "wal_checkpoint" in sql.lower():
                        checkpoints.append(sql)
            connection.set_trace_callback(trace)
        return connection

    monkeypatch.setattr(sqlite3, "connect", connect)
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=5)
    app.broker.set_mode("auto")
    initial = app.index_service.refresh()
    assert initial.reason in {"", "the index has never been built"}

    server = build(app, 0)
    serving = threading.Thread(target=server.serve_forever, daemon=True,
                               name="sustained-loopback-server")
    serving.start()
    request_ms: list[float] = []

    class TimedClient(Client):
        def request(self, *args, **kwargs):
            started = time.monotonic()
            try:
                return super().request(*args, **kwargs)
            finally:
                with guard:
                    request_ms.append((time.monotonic() - started) * 1000)

    client = TimedClient(server, app.token)
    barrier = threading.Barrier(WORKERS)
    counts = Counter()
    errors: list[tuple[str, BaseException]] = []
    refresh_reasons: list[str] = []
    last_reads: dict[str, dict] = {}
    started = time.monotonic()

    def tool(tool_name: str, **arguments):
        status, payload = client.post(f"/api/tool/{tool_name}", {"arguments": arguments})
        assert status == 200, payload
        assert "error" not in payload, payload
        return payload

    def browser(index: int) -> None:
        tool("write_note", folder="Notes", name=f"Browser Sustained {index:02d}",
             body=f"browser sustained round {index}")

    def mcp(index: int) -> None:
        status, payload = client.post("/api/mcp/call", {
            "tool": "write_note", "tier": "contribute",
            "arguments": {"folder": "Notes", "name": f"MCP Sustained {index:02d}",
                          "body": f"mcp sustained round {index}"},
        })
        assert status == 200, payload
        assert "error" not in payload["result"], payload

    def external(index: int) -> None:
        replacement = replacement_paths[index]
        before = replacement.stat()
        old = replacement.read_bytes()
        changed = old.replace(f"seed-{index:04d}".encode(), f"swap-{index:04d}".encode())
        assert changed != old and len(changed) == len(old)
        temporary = replacement.with_suffix(".replacement")
        temporary.write_bytes(changed)
        os.utime(temporary, ns=(before.st_atime_ns, before.st_mtime_ns))
        sharing_retry("replace", lambda: os.replace(temporary, replacement))
        assert (replacement.stat().st_size, replacement.stat().st_mtime_ns) == \
            (before.st_size, before.st_mtime_ns)

        source = rename_paths[index]
        target = source.with_name(f"{source.stem} Renamed.md")
        sharing_retry("rename", lambda: source.rename(target))
        sharing_retry("delete", delete_paths[index].unlink)
        created = folder / f"Created {index:02d}.md"
        created.write_text(_note(f"Created {index:02d}", f"created-{index:02d}"),
                           encoding="utf-8")

    def obsidian(index: int) -> None:
        path = obsidian_paths[index]
        rel = path.relative_to(vault.root).as_posix()
        status, payload = client.post("/api/documents/heartbeat", {
            "path": rel, "dirty": True, "editor": "Obsidian",
        }, headers={"Origin": "app://obsidian.md"})
        assert status == 200 and payload["leases"][0]["path"] == rel, payload
        sharing_retry("obsidian", lambda: path.write_text(
            _note(path.stem, f"obsidian-{index:02d}"), encoding="utf-8"))
        status, payload = client.post("/api/documents/release", {
            "path": rel, "editor": "Obsidian",
        }, headers={"Origin": "app://obsidian.md"})
        assert status == 200, payload

    def reader(index: int) -> None:
        search = tool("search", query="sustained traffic", intent="made")
        status = tool("index_status")
        with guard:
            last_reads["search"] = search
            last_reads["status"] = status

    def maintenance(index: int) -> None:
        report = app.index_service.refresh()
        app.index_service.checkpoint()
        with guard:
            refresh_reasons.append(report.reason)

    def run(label: str, action) -> None:
        for index in range(ROUNDS):
            barrier.wait(20)
            action(index)
            with guard:
                counts[label] += 1
            barrier.wait(30)

    def bounded(label: str, action) -> None:
        try:
            run(label, action)
        except BaseException as exc:
            with guard:
                errors.append((label, exc))
            barrier.abort()

    workers = [
        threading.Thread(target=bounded, args=(label, action), daemon=True,
                         name=f"sustained-{label}")
        for label, action in (
            ("browser", browser), ("mcp", mcp), ("external", external),
            ("obsidian", obsidian), ("reader", reader), ("maintenance", maintenance),
        )
    ]

    try:
        for worker in workers:
            worker.start()
        deadline = time.monotonic() + 120
        for worker in workers:
            worker.join(max(0, deadline - time.monotonic()))
        assert not [worker.name for worker in workers if worker.is_alive()], \
            "sustained workers exceeded their characterization bound"
        assert not errors, errors
        assert counts == Counter({label: ROUNDS for label in (
            "browser", "mcp", "external", "obsidian", "reader", "maintenance")})
        assert app.watcher is not None and app.watcher.health()["status"] == "ready"
        assert app.document_leases.view() == {"leases": []}

        # Freeze the external-observation source before exact final comparison;
        # the watcher stayed live and healthy throughout all contention rounds.
        app.watcher.close()
        settled = app.index_service.refresh()
        stable = app.index_service.refresh()
        assert settled.reason == ""
        assert stable.reason == ""
        assert stable.upserted == [] and stable.removed == []

        expected_paths = {
            path.relative_to(vault.root).as_posix(): path for path in iter_paths(vault.root)
        }

        def verify(index):
            rows = {row["path"]: row for row in index.conn.execute("SELECT * FROM note")}
            assert set(rows) == set(expected_paths)
            assert stable.unchanged == len(rows)
            for rel, path in expected_paths.items():
                row = rows[rel]
                assert (row["mtime_ns"], row["size"], row["file_identity"]) == _metadata(path)
                assert row["hash"] == _normalized_hash(path)
            assert index.conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert not index.conn.in_transaction
            for table in ("chunk", "facet", "link", "component"):
                assert index.conn.execute(
                    f"SELECT COUNT(*) FROM {table} AS child LEFT JOIN note "
                    "ON note.path = child.path WHERE note.path IS NULL").fetchone()[0] == 0

        app.index_service.run(verify)
        for index in range(ROUNDS):
            assert f"swap-{index:04d}" in replacement_paths[index].read_text(encoding="utf-8")
            assert not rename_paths[index].exists()
            assert rename_paths[index].with_name(
                f"{rename_paths[index].stem} Renamed.md").is_file()
            assert not delete_paths[index].exists()
            assert (folder / f"Created {index:02d}.md").is_file()
            assert (vault.root / "Notes" / f"Browser Sustained {index:02d}.md").is_file()
            assert (vault.root / "Notes" / f"MCP Sustained {index:02d}.md").is_file()
            assert f"obsidian-{index:02d}" in obsidian_paths[index].read_text(encoding="utf-8")

        assert last_reads["search"]["verdict"]
        assert last_reads["status"]["notes"] > NOTE_COUNT
        assert len(checkpoints) == ROUNDS
        assert sql_threads == {app.index_service._thread}
        assert len([row for row in connections if row["path"] == "index.sqlite"]) == 1
    finally:
        barrier.abort()
        cleanup_deadline = time.monotonic() + 20
        for worker in workers:
            worker.join(max(0, cleanup_deadline - time.monotonic()))
        lingering_workers = [worker.name for worker in workers if worker.is_alive()]
        server.shutdown()
        server.server_close()
        serving.join(3)
        closed = app.close_runtime()

    assert not lingering_workers, f"workers survived bounded teardown: {lingering_workers}"
    assert closed is True
    assert all(record["closed"] for record in connections), connections
    operations = [json.loads(line) for line in app.writer.log_path.read_text(
        encoding="utf-8").splitlines()]
    running = {row["id"] for row in operations if row["status"] == "running"}
    terminal = {row["id"] for row in operations if row["status"] in {"done", "failed"}}
    assert running == terminal
    assert {row["status"] for row in operations} <= {"running", "done"}
    successor = VaultCoordinator(vault)
    successor.acquire()
    successor.release()

    latencies = sorted(request_ms)
    print("SUSTAINED_INDEX_METRICS " + json.dumps({
        "seed_notes": NOTE_COUNT,
        "final_notes": len(list(iter_paths(vault.root))),
        "final_markdown_bytes": sum(path.stat().st_size for path in iter_paths(vault.root)),
        "rounds": ROUNDS,
        "worker_iterations": sum(counts.values()),
        "requests": len(latencies),
        "request_p50_ms": round(latencies[len(latencies) // 2], 2),
        "request_p95_ms": round(latencies[int(0.95 * (len(latencies) - 1))], 2),
        "request_max_ms": round(max(latencies), 2),
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "refreshes": len(refresh_reasons),
        "refreshes_with_reason": sum(bool(reason) for reason in refresh_reasons),
        "checkpoint_calls": len(checkpoints),
        "index_connections": 1,
        "operation_ids": len(running),
        "sharing_retries": dict(sharing_retries),
        "model_calls": 0,
    }, sort_keys=True))
