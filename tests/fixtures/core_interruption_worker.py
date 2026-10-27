"""Real child Core held at deterministic interruption boundaries for INDEX-05.

This is test support, not a production entry point.  The parent owns this
exact process and terminates it only after both the Markdown mutation and an
uncommitted WAL transaction have reached their markers. It covers abrupt
``os._exit`` and authenticated Host force-stop modes.
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import threading
import time
from pathlib import Path

from resource_librarian import connection, process_identity
from resource_librarian.app import App, build
from resource_librarian.keys import KeyStore
from resource_librarian.vault import Vault


def _write(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(payload, sort_keys=True))
        handle.flush()
        os.fsync(handle.fileno())


def main() -> int:
    vault = Vault(Path(sys.argv[1]).resolve())
    markers = Path(sys.argv[2]).resolve()
    mode = sys.argv[3] if len(sys.argv) > 3 else "crash"
    if mode not in {"crash", "host-force"}:
        raise ValueError(f"unknown interruption mode {mode!r}")
    markers.mkdir(parents=True, exist_ok=True)
    token = "process-interruption-token"
    hold = threading.Event()

    app = App(vault, token=token, coordinate=True, keys=KeyStore(use_keyring=False),
              broker_timeout=2, host_managed=mode == "host-force")
    app.broker.set_mode("auto")
    baseline = app.person_call(
        "write_note", {"folder": "Notes", "name": "Baseline", "body": "before crash"})
    if "error" in baseline:
        raise RuntimeError(baseline)
    session_id = app.person_call(
        "open_session", {"purpose": "explore", "question": "process interruption"})["opened"]
    app.index_service.refresh()

    # Mark each traffic path only after its own App admission context has
    # accepted it. Aggregate call/mutation counts cannot identify which route
    # reached the Core (the checkpoint, for example, has nested counters).
    traffic_guard = threading.Lock()
    traffic = {
        "crash_write_admitted": False,
        "search_admitted": False,
        "mcp_write_admitted": False,
        "checkpoint_admitted": False,
    }

    def mark(name: str) -> None:
        with traffic_guard:
            traffic[name] = True

    original_counted_call = app._counted_call

    @contextlib.contextmanager
    def counted_call(kind: str, what: str):
        with original_counted_call(kind, what):
            if kind == "person" and what == "the call 'write_note'":
                mark("crash_write_admitted")
            elif kind == "person" and what == "the call 'search'":
                mark("search_admitted")
            elif kind == "mcp" and what == "the MCP call 'write_note'":
                mark("mcp_write_admitted")
            yield

    original_counted_mutation = app._counted_mutation

    @contextlib.contextmanager
    def counted_mutation(what: str):
        with original_counted_mutation(what):
            # _serialized("checkpoint", ...) has validated the request and
            # is immediately about to submit its writer operation.
            if what == "the checkpoint mutation":
                mark("checkpoint_admitted")
            yield

    app._counted_call = counted_call
    app._counted_mutation = counted_mutation

    original_record = app.writer._record
    wal_started = threading.Event()

    def hold_wal() -> None:
        def transaction(index):
            index.conn.execute("BEGIN IMMEDIATE")
            index.conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                ("crash_probe", "must roll back"))
            _write(markers / "wal-open.json", {"pid": os.getpid()})
            wal_started.set()
            hold.wait(600)
        app.index_service.run(transaction)

    def record(operation) -> None:
        target = "Notes/CrashTarget.md"
        if operation.status == "done" and target in operation.targets:
            _write(markers / "mutation-applied.json", {
                "pid": os.getpid(), "operation_id": operation.id,
                "target": target,
            })
            threading.Thread(target=hold_wal, daemon=True,
                             name="interruption-wal").start()
            if not wal_started.wait(10):
                raise RuntimeError("the crash WAL transaction did not start")
            # The parent terminates this process.  Returning would append the
            # terminal writer record and invalidate the crash boundary.
            hold.wait(600)
        original_record(operation)

    app.writer._record = record
    server = build(app, 0)
    url = f"http://127.0.0.1:{server.server_address[1]}"

    def observe_mixed_traffic() -> None:
        while not hold.wait(0.01):
            with traffic_guard:
                admitted = dict(traffic)
            with app._lock:
                person = app._calls.get("person", 0)
                mcp = app._calls.get("mcp", 0)
                mutations = app._mutations
            if all(admitted.values()):
                _write(markers / "mixed-admitted.json", {
                    "person_calls": person, "mcp_calls": mcp,
                    "mutations": mutations,
                    **admitted,
                })
                return

    def crash_when_requested() -> None:
        request = markers / "crash-now"
        while not request.exists():
            time.sleep(0.01)
        os._exit(97)

    threading.Thread(target=observe_mixed_traffic, daemon=True,
                     name="interruption-observer").start()
    if mode == "crash":
        threading.Thread(target=crash_when_requested, daemon=True,
                         name="interruption-crash-control").start()
    process_start = process_identity.process_start(os.getpid())
    if mode == "host-force":
        if not connection.publish(
                vault.root, url=url + "/", token=token, pid=os.getpid(),
                process_start=process_start, protocol_version="2",
                secret_source="desktop"):
            raise RuntimeError("host-force fixture could not publish its protected connection")
    _write(markers / "ready.json", {
        "pid": os.getpid(), "url": url, "token": token,
        "session_id": session_id,
        "process_start": process_start, "mode": mode,
    })
    try:
        server.serve_forever()
    finally:
        # The abrupt crash fixture never reaches this block. The Host force
        # fixture records a truthful pending shutdown before process exit.
        server.closing = True
        server.server_close()
        if app.mcp is not None and getattr(app.mcp, "owner", None) is app:
            app.mcp.stop()
        app.close_runtime()
        if mode == "host-force":
            connection.remove(vault.root, pid=os.getpid(), token=token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
