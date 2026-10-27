"""INDEX-05: real-process crash recovery under mixed Core traffic."""
from __future__ import annotations

import builtins
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from resource_librarian.app import App
from resource_librarian.coordination import LeaseHeldError, StaleLeaseError, VaultCoordinator
from resource_librarian.host import HostManager, STOP_EXIT_SECONDS
from resource_librarian.keys import KeyStore
from resource_librarian import connection, process_identity
from resource_librarian.session import SessionStore


pytestmark = pytest.mark.skipif(os.name != "nt", reason="INDEX-05 Windows process fixture")


def _wait_json(path: Path, process: subprocess.Popen, log: Path,
               timeout: float = 15) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, PermissionError, json.JSONDecodeError):
            row = None
        if isinstance(row, dict):
            return row
        if process.poll() is not None:
            detail = log.read_text(encoding="utf-8", errors="replace")[-3000:]
            raise AssertionError(f"interruption worker exited {process.returncode}: {detail}")
        time.sleep(0.02)
    detail = log.read_text(encoding="utf-8", errors="replace")[-3000:]
    raise AssertionError(f"timed out waiting for {path.name}: {detail}")


def _request(url: str, token: str, method: str, path: str,
             body: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url + path, data=data, method=method,
        headers={"Content-Type": "application/json", "X-Librarian-Token": token,
                 **(headers or {})})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status, json.loads(response.read())


class _Call:
    def __init__(self, fn, name: str) -> None:
        self.started = threading.Event()
        self.result = None
        self.error: BaseException | None = None

        def run() -> None:
            self.started.set()
            try:
                self.result = fn()
            except BaseException as exc:
                self.error = exc

        self.thread = threading.Thread(target=run, name=name)

    def start(self) -> None:
        self.thread.start()
        assert self.started.wait(2)

    def join(self, timeout: float = 3) -> None:
        self.thread.join(timeout)
        assert not self.thread.is_alive(), f"{self.thread.name} did not stop after its Core died"


def _launch_worker(vault, tmp_path: Path, monkeypatch, mode: str = "crash"):
    root = Path(__file__).resolve().parents[1]
    markers = tmp_path / "markers"
    markers.mkdir()
    log = tmp_path / "interruption-worker.log"
    config = tmp_path / "config"
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(config))
    environment = dict(os.environ)
    environment["LIBRARIAN_CONFIG_DIR"] = str(config)
    # Launch the actual base interpreter so Popen owns the process which holds
    # the vault lock.  Carry this test environment's installed packages and
    # the current source tree explicitly; no installed build is substituted.
    python_paths = [str(root / "src"), *(p for p in sys.path if p)]
    environment["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(python_paths))
    command = [getattr(sys, "_base_executable", sys.executable),
               str(root / "tests" / "fixtures" / "core_interruption_worker.py"),
               str(vault.root), str(markers), mode]
    output = log.open("w", encoding="utf-8", newline="")
    process = subprocess.Popen(
        command, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
        cwd=root, env=environment,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return process, output, markers, log


def _kill(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.kill()
    process.wait(timeout=5)


def test_ownerless_lock_permission_error_is_not_misreported_as_a_live_core(
        vault, monkeypatch):
    coordinator = VaultCoordinator(vault)
    original_open = builtins.open

    def denied(path, *args, **kwargs):
        if Path(path) == coordinator.path:
            raise PermissionError("ownerless lock probe denied")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", denied)
    with pytest.raises(PermissionError, match="ownerless lock probe denied"):
        coordinator.acquire()


def test_unpinned_legacy_lock_owner_cannot_mask_a_permission_error(vault, monkeypatch):
    coordinator = VaultCoordinator(vault)
    coordinator.info_path.parent.mkdir(parents=True, exist_ok=True)
    coordinator.info_path.write_text(json.dumps({
        "pid": os.getpid() + 1000,
        "started_at": "legacy-row-without-process-identity",
    }), encoding="utf-8")
    monkeypatch.setattr(VaultCoordinator, "_pid_alive", staticmethod(lambda _pid, _start=None: True))
    original_open = builtins.open

    def denied(path, *args, **kwargs):
        if Path(path) == coordinator.path:
            raise PermissionError("unpinned lock probe denied")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", denied)
    with pytest.raises(PermissionError, match="unpinned lock probe denied"):
        coordinator.acquire()


def test_crash_after_mutation_before_done_recovers_without_replay(vault, tmp_path, monkeypatch):
    process, output, markers, log = _launch_worker(vault, tmp_path, monkeypatch)
    calls: list[_Call] = []
    try:
        ready = _wait_json(markers / "ready.json", process, log)
        assert ready["pid"] == process.pid
        url, token = ready["url"], ready["token"]
        live = VaultCoordinator(vault)
        with pytest.raises(LeaseHeldError):
            live.acquire()

        mutation = _Call(lambda: _request(url, token, "POST", "/api/tool/write_note", {
            "arguments": {"folder": "Notes", "name": "CrashTarget",
                          "body": "durable mutation before crash"}}), "crash-mutation-client")
        calls.append(mutation)
        mutation.start()
        applied = _wait_json(markers / "mutation-applied.json", process, log)
        _wait_json(markers / "wal-open.json", process, log)

        # These requests represent the Core's Browser, MCP and maintenance
        # paths.  Writer/index requests remain in flight at the forced crash;
        # document heartbeat is deliberately allowed to complete first.
        mcp = _Call(lambda: _request(url, token, "POST", "/api/mcp/call", {
            "tool": "write_note", "tier": "contribute",
            "arguments": {"folder": "Notes", "name": "QueuedAfterCrash",
                          "body": "must not appear"}}), "crash-mcp-client")
        search = _Call(lambda: _request(url, token, "POST", "/api/tool/search", {
            "arguments": {"query": "durable", "intent": "made"}}), "crash-search-client")
        checkpoint = _Call(lambda: _request(url, token, "POST", "/api/checkpoints", {
            "type": "review", "scope": "queued behind crash",
            "choices": ["acknowledge"]}), "crash-checkpoint-client")
        calls.extend((mcp, search, checkpoint))
        for call in (mcp, search, checkpoint):
            call.start()

        admitted = _wait_json(markers / "mixed-admitted.json", process, log)
        assert admitted["person_calls"] >= 2
        assert admitted["mcp_calls"] >= 1
        assert admitted["mutations"] >= 1
        assert {key for key, value in admitted.items()
                if key.endswith("_admitted") and value} == {
            "crash_write_admitted", "search_admitted",
            "mcp_write_admitted", "checkpoint_admitted"}

        status, heartbeat = _request(
            url, token, "POST", "/api/documents/heartbeat",
            {"path": "Notes/Baseline.md", "dirty": True, "editor": "Obsidian"},
            headers={"Origin": "app://obsidian.md"})
        assert status == 200 and heartbeat["leases"][0]["path"] == "Notes/Baseline.md"
        (vault.root / "Notes" / "Baseline.md").write_text(
            "# Baseline\n\nexternal edit immediately before crash\n", encoding="utf-8")

        assert all(call.thread.is_alive() for call in calls)
        killed_at = time.monotonic()
        (markers / "crash-now").write_bytes(b"crash\n")
        process.wait(timeout=5)
        assert process.returncode == 97
        assert time.monotonic() - killed_at < 5
        assert process_identity.is_alive(ready["pid"], ready["process_start"]) is False
        for call in calls:
            call.join()
        assert all(call.error is not None for call in calls)
    finally:
        _kill(process)
        output.close()

    target = vault.root / "Notes" / "CrashTarget.md"
    assert "durable mutation before crash" in target.read_text(encoding="utf-8")
    assert not (vault.root / "Notes" / "QueuedAfterCrash.md").exists()
    rows = [json.loads(line) for line in
            (vault.librarian / "runtime" / "operations.jsonl").read_text(
                encoding="utf-8").splitlines()]
    crash_rows = [row for row in rows if row["id"] == applied["operation_id"]]
    assert [row["status"] for row in crash_rows] == ["running"]

    stale = VaultCoordinator(vault)
    with pytest.raises(StaleLeaseError):
        stale.acquire()

    successor = App(vault, coordinate=True, takeover=True, keys=KeyStore(use_keyring=False))
    try:
        recoveries = [row for row in successor.checkpoints.all()
                      if row["type"] == "operation_recovery"]
        assert len(recoveries) == 1
        assert recoveries[0]["evidence"]["operation_id"] == applied["operation_id"]
        assert recoveries[0]["evidence"]["targets"] == ["Notes/CrashTarget.md"]
        assert recoveries[0]["evidence"]["current_fingerprints"]["Notes/CrashTarget.md"]
        assert recoveries[0]["evidence"]["consequence"] == (
            "The operation may have partially applied. Librarian made no repair or replay.")
        assert "durable mutation before crash" not in json.dumps(recoveries[0])
        assert "durable mutation before crash" in target.read_text(encoding="utf-8")
        assert not (vault.root / "Notes" / "QueuedAfterCrash.md").exists()
        assert successor.document_leases.view() == {"leases": []}
        assert SessionStore(vault).verify() == []
        assert SessionStore(vault).load(ready["session_id"]).status == "open"

        successor.index_service.refresh()

        def verify(index):
            assert index.conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert index.conn.execute(
                "SELECT value FROM meta WHERE key = 'crash_probe'").fetchone() is None
            row = index.note_row("CrashTarget")
            text = target.read_text(encoding="utf-8", errors="replace")
            stat = target.stat()
            assert row is not None
            assert row["hash"] == hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]
            assert (row["mtime_ns"], row["size"]) == (stat.st_mtime_ns, stat.st_size)
            assert row["file_identity"] == f"{stat.st_dev}:{stat.st_ino}:{stat.st_ctime_ns}"
            baseline_path = vault.root / "Notes" / "Baseline.md"
            baseline_text = baseline_path.read_text(encoding="utf-8", errors="replace")
            baseline = index.note_row("Baseline")
            assert baseline is not None
            assert baseline["hash"] == hashlib.sha256(
                baseline_text.encode("utf-8")).hexdigest()[:24]
            for table in ("chunk", "facet", "link", "component"):
                assert index.conn.execute(
                    f"SELECT COUNT(*) FROM {table} AS child LEFT JOIN note "
                    "ON note.path = child.path WHERE note.path IS NULL").fetchone()[0] == 0

        successor.index_service.run(verify)
        successor.index_service.checkpoint()
    finally:
        assert successor.close_runtime() is True

    # A clean second start sees the same historical card rather than creating
    # another recovery or replaying the ambiguous operation.
    restarted = App(vault, coordinate=True, keys=KeyStore(use_keyring=False))
    try:
        recoveries = [row for row in restarted.checkpoints.all()
                      if row["type"] == "operation_recovery"]
        assert len(recoveries) == 1
        assert recoveries[0]["evidence"]["operation_id"] == applied["operation_id"]
        assert "durable mutation before crash" in target.read_text(encoding="utf-8")
        assert not (vault.root / "Notes" / "QueuedAfterCrash.md").exists()
    finally:
        assert restarted.close_runtime() is True


def test_authenticated_host_force_stop_preserves_pending_recovery_evidence(
        vault, tmp_path, monkeypatch):
    process, output, markers, log = _launch_worker(
        vault, tmp_path, monkeypatch, mode="host-force")
    calls: list[_Call] = []
    try:
        ready = _wait_json(markers / "ready.json", process, log)
        assert ready["pid"] == process.pid and ready["mode"] == "host-force"
        url, token = ready["url"], ready["token"]
        manager = HostManager()

        mutation = _Call(lambda: _request(url, token, "POST", "/api/tool/write_note", {
            "arguments": {"folder": "Notes", "name": "CrashTarget",
                          "body": "durable mutation before forced stop"}}),
            "host-force-mutation-client")
        calls.append(mutation)
        mutation.start()
        applied = _wait_json(markers / "mutation-applied.json", process, log)
        _wait_json(markers / "wal-open.json", process, log)

        mcp = _Call(lambda: _request(url, token, "POST", "/api/mcp/call", {
            "tool": "write_note", "tier": "contribute",
            "arguments": {"folder": "Notes", "name": "QueuedAfterCrash",
                          "body": "must not appear"}}), "host-force-mcp-client")
        search = _Call(lambda: _request(url, token, "POST", "/api/tool/search", {
            "arguments": {"query": "durable", "intent": "made"}}),
            "host-force-search-client")
        checkpoint = _Call(lambda: _request(url, token, "POST", "/api/checkpoints", {
            "type": "review", "scope": "queued behind host force stop",
            "choices": ["acknowledge"]}), "host-force-checkpoint-client")
        calls.extend((mcp, search, checkpoint))
        for call in (mcp, search, checkpoint):
            call.start()
        admitted = _wait_json(markers / "mixed-admitted.json", process, log)
        assert all(admitted[key] for key in (
            "crash_write_admitted", "search_admitted",
            "mcp_write_admitted", "checkpoint_admitted"))

        status, heartbeat = _request(
            url, token, "POST", "/api/documents/heartbeat",
            {"path": "Notes/Baseline.md", "dirty": True, "editor": "Obsidian"},
            headers={"Origin": "app://obsidian.md"})
        assert status == 200 and heartbeat["leases"][0]["path"] == "Notes/Baseline.md"
        (vault.root / "Notes" / "Baseline.md").write_text(
            "# Baseline\n\nexternal edit immediately before forced stop\n", encoding="utf-8")

        refused = manager.stop(str(vault.root), force=False)
        assert refused["stopped"] is False
        assert refused["checkpoint"] == "forced_engagement_close"
        assert refused["active"]["person_calls"] >= 2
        assert refused["active"]["mcp_calls"] >= 1
        assert process.poll() is None

        started = time.monotonic()
        stopped = manager.stop(str(vault.root), force=True)
        elapsed = time.monotonic() - started
        assert stopped["stopped"] is True, stopped
        assert elapsed < STOP_EXIT_SECONDS + 3
        assert stopped["reply"]["forced"] is True
        assert stopped["reply"]["active"]["person_calls"] >= 2
        assert stopped["reply"]["active"]["mcp_calls"] >= 1
        process.wait(timeout=3)
        assert process.returncode == 0
        assert process_identity.is_alive(ready["pid"], ready["process_start"]) is False
        assert connection.load(vault.root) is None
        for call in calls:
            call.join()
        assert all(call.error is not None for call in calls)

        phases = stopped["phases"]
        assert [phase["phase"] for phase in phases] == [
            "admission_closed", "work_cancelled", "writer_drained", "shutdown_pending"]
        assert phases[-1]["reason"] == "writer_still_running"
        assert phases[-2]["drained"] is False
    finally:
        _kill(process)
        output.close()

    target = vault.root / "Notes" / "CrashTarget.md"
    assert "durable mutation before forced stop" in target.read_text(encoding="utf-8")
    assert not (vault.root / "Notes" / "QueuedAfterCrash.md").exists()
    rows = [json.loads(line) for line in
            (vault.librarian / "runtime" / "operations.jsonl").read_text(
                encoding="utf-8").splitlines()]
    assert [row["status"] for row in rows if row["id"] == applied["operation_id"]] == ["running"]

    with pytest.raises(StaleLeaseError):
        VaultCoordinator(vault).acquire()

    successor = App(vault, coordinate=True, takeover=True, keys=KeyStore(use_keyring=False))
    try:
        recoveries = [row for row in successor.checkpoints.all()
                      if row["type"] == "operation_recovery"]
        assert len(recoveries) == 1
        assert recoveries[0]["evidence"]["operation_id"] == applied["operation_id"]
        assert "durable mutation before forced stop" not in json.dumps(recoveries[0])
        assert successor.document_leases.view() == {"leases": []}
        assert SessionStore(vault).verify() == []
        assert SessionStore(vault).load(ready["session_id"]).status == "open"
        successor.index_service.refresh()

        def verify(index):
            assert index.conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert index.conn.execute(
                "SELECT value FROM meta WHERE key = 'crash_probe'").fetchone() is None
            row = index.note_row("CrashTarget")
            text = target.read_text(encoding="utf-8", errors="replace")
            stat = target.stat()
            assert row is not None
            assert row["hash"] == hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]
            assert (row["mtime_ns"], row["size"]) == (stat.st_mtime_ns, stat.st_size)
            assert row["file_identity"] == f"{stat.st_dev}:{stat.st_ino}:{stat.st_ctime_ns}"
            for table in ("chunk", "facet", "link", "component"):
                assert index.conn.execute(
                    f"SELECT COUNT(*) FROM {table} AS child LEFT JOIN note "
                    "ON note.path = child.path WHERE note.path IS NULL").fetchone()[0] == 0

        successor.index_service.run(verify)
        successor.index_service.checkpoint()
    finally:
        assert successor.close_runtime() is True
