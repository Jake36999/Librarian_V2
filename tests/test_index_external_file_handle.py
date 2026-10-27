"""INDEX-05: fail-safe recovery from an unsupported foreign file handle.

Librarian coordinates its own clients, but it cannot make an unrelated
Windows process share a Markdown file for deletion.  This fixture pins that
boundary: a foreign handle may make one atomic replacement fail, but it must
not hang or kill the writer, partially publish bytes, or make an explicit
retry unsafe once the handle is released.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import threading
from pathlib import Path

import pytest

from resource_librarian.app import App
from resource_librarian.keys import KeyStore


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows sharing semantics")


def _open_without_delete_sharing(path: Path) -> int:
    """Open ``path`` for reads while deliberately denying delete sharing."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    )
    create_file.restype = ctypes.c_void_p
    handle = create_file(
        str(path),
        0x80000000,  # GENERIC_READ
        0x00000001,  # FILE_SHARE_READ, intentionally no FILE_SHARE_DELETE
        None,
        3,  # OPEN_EXISTING
        0x00000080,  # FILE_ATTRIBUTE_NORMAL
        None,
    )
    invalid = ctypes.c_void_p(-1).value
    if handle in (None, invalid):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(handle)


def _close_handle(handle: int) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    close = kernel32.CloseHandle
    close.argtypes = (ctypes.c_void_p,)
    close.restype = ctypes.c_int
    if not close(ctypes.c_void_p(handle)):
        raise ctypes.WinError(ctypes.get_last_error())


def _operations(app: App) -> list[dict]:
    return [
        json.loads(line)
        for line in app.writer.log_path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _ok(result: dict) -> dict:
    assert "error" not in result, result
    return result


def test_foreign_markdown_handle_fails_one_write_then_explicit_retry_converges(vault):
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=5)
    app.broker.set_mode("auto")
    handle: int | None = None
    blocked_thread: threading.Thread | None = None
    blocked: list[dict | BaseException] = []
    try:
        created = _ok(app.person_call("write_note", {
            "folder": "Notes", "name": "Locked", "body": "Original body",
        }))
        revision = created["revision"]
        path = vault.root / "Notes" / "Locked.md"
        original = path.read_bytes()
        operation_offset = len(_operations(app))

        handle = _open_without_delete_sharing(path)

        def replace_locked_note() -> None:
            try:
                blocked.append(app.person_call("write_note", {
                    "folder": "Notes",
                    "name": "Locked",
                    "body": "Replacement body",
                    "mode": "replace",
                    "revision": revision,
                }))
            except BaseException as exc:  # surface unexpected thread failures in this test
                blocked.append(exc)

        blocked_thread = threading.Thread(
            target=replace_locked_note, daemon=True, name="foreign-handle-write"
        )
        blocked_thread.start()
        blocked_thread.join(5)
        if blocked_thread.is_alive():
            # Release before failing so the daemon cannot mutate a later test.
            _close_handle(handle)
            handle = None
            blocked_thread.join(5)
            pytest.fail("the sharing violation did not return within five seconds")

        assert len(blocked) == 1 and isinstance(blocked[0], dict), blocked
        refused = blocked[0]
        assert refused["error"] == "failed"
        assert "PermissionError" in refused["detail"] and "WinError" in refused["detail"]
        assert path.read_bytes() == original
        assert not list(path.parent.glob(f".{path.name}.*.tmp"))
        assert app.writer.alive and app.writer.accepting

        # The unsupported target handle is not a global Core outage.
        unrelated = _ok(app.person_call("write_note", {
            "folder": "Notes", "name": "Unrelated", "body": "Still writable",
        }))
        assert unrelated["written"] == "Notes/Unrelated.md"
        indexed_before_retry = app.index_service.run(
            lambda index: dict(index.note_row("Locked"))
        )
        assert indexed_before_retry["hash"] == hashlib.sha256(
            original.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
        ).hexdigest()[:24]

        _close_handle(handle)
        handle = None

        retried = _ok(app.person_call("write_note", {
            "folder": "Notes",
            "name": "Locked",
            "body": "Replacement body",
            "mode": "replace",
            # The failed atomic replacement changed no bytes, so the revision
            # read before the foreign handle was acquired remains current.
            "revision": revision,
        }))
        assert retried["revision"] != revision

        report = app.index_service.refresh()
        assert "Notes/Locked.md" not in report.removed
        final_bytes = path.read_bytes()
        assert b"Replacement body" in final_bytes and b"Original body" not in final_bytes
        final_text = final_bytes.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        indexed = app.index_service.run(lambda index: dict(index.note_row("Locked")))
        assert indexed["path"] == "Notes/Locked.md"
        assert indexed["size"] == len(final_bytes)
        assert indexed["hash"] == hashlib.sha256(final_text.encode("utf-8")).hexdigest()[:24]

        rows = _operations(app)[operation_offset:]
        locked_rows = [row for row in rows if "Notes/Locked.md" in row["targets"]]
        terminal = [row for row in locked_rows if row["status"] in {"failed", "done"}]
        assert [row["status"] for row in terminal] == ["failed", "done"]
        assert "PermissionError" in terminal[0]["detail"]
        for row in terminal:
            assert any(
                prior["id"] == row["id"] and prior["status"] == "running"
                for prior in locked_rows
            )
    finally:
        if handle is not None:
            _close_handle(handle)
        if blocked_thread is not None:
            blocked_thread.join(5)
        app.close_runtime()
