"""CORE-06: a pre-crash writer record is evidence, never a replay request."""
from __future__ import annotations

import json

from resource_librarian.app import App
from resource_librarian.checkpoints import CheckpointStore
from resource_librarian.coordination import (OperationLogUnreadableError, VaultCoordinator,
                                             VaultWatcher, VaultWriter, atomic_write_text, fingerprint)
from resource_librarian.vault import now_iso


def _operation(vault, operation_id: str, *, caller: str = "test-tool",
               targets: list[str] | None = None, status: str = "running",
               finished_at: str = "") -> dict:
    target_list = list(targets or [])
    return {
        "id": operation_id,
        "caller": caller,
        "targets": target_list,
        "started_at": "2026-10-24T12:00:00+00:00",
        "precondition_fingerprints": {target: "before" for target in target_list},
        "observed_fingerprints": {target: "before" for target in target_list},
        "result": {"do_not_surface": "private document text"},
        "finished_at": finished_at,
        "status": status,
        "detail": "do_not_surface either",
    }


def _write_rows(vault, *rows: dict, partial: str = "") -> None:
    path = vault.librarian / "runtime" / "operations.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row) + "\n" for row in rows) + partial
    path.write_text(text, encoding="utf-8")


def _recoveries(vault):
    return [row for row in CheckpointStore(vault).all()
            if row["type"] == "operation_recovery"]


def test_start_only_operation_becomes_a_nonmutating_checkpoint_before_watcher(vault, monkeypatch):
    note = vault.root / "Notes" / "target.md"
    atomic_write_text(note, "person's original note")
    _write_rows(vault, _operation(vault, "op-start", targets=["Notes/target.md"]))
    observed_at_start: list[bool] = []
    original_start = VaultWatcher.start

    def checked_start(watcher):
        observed_at_start.append(bool(_recoveries(vault)))
        return original_start(watcher)

    monkeypatch.setattr(VaultWatcher, "start", checked_start)
    app = App(vault, coordinate=True)
    try:
        rows = _recoveries(vault)
        assert observed_at_start == [True]
        assert len(rows) == 1
        evidence = rows[0]["evidence"]
        assert evidence["operation_id"] == "op-start"
        assert evidence["targets"] == ["Notes/target.md"]
        assert evidence["current_fingerprints"]["Notes/target.md"] == fingerprint(note)
        assert evidence["consequence"] == (
            "The operation may have partially applied. Librarian made no repair or replay.")
        assert "private document text" not in json.dumps(evidence)
        assert note.read_text(encoding="utf-8") == "person's original note"
    finally:
        app.close_runtime()


def test_resolved_historical_recovery_is_not_recreated_after_restart(vault):
    _write_rows(vault, _operation(vault, "op-once", targets=["Notes/missing.md"]))
    first = App(vault, coordinate=True)
    try:
        checkpoint = _recoveries(vault)[0]
        resolved = first.checkpoint_resolve(checkpoint["id"], "acknowledge")
        assert resolved["resolution"] == "acknowledge"
    finally:
        first.close_runtime()

    successor = App(vault, coordinate=True)
    try:
        rows = _recoveries(vault)
        assert len(rows) == 1
        assert rows[0]["id"] == checkpoint["id"]
        assert rows[0]["resolution"] == "acknowledge"
        assert successor.operation_recoveries[0]["id"] == checkpoint["id"]
    finally:
        successor.close_runtime()


def test_terminal_writer_records_do_not_create_recovery_cards(vault):
    started = _operation(vault, "op-done", status="running")
    finished = _operation(vault, "op-done", status="done", finished_at=now_iso())
    failed = _operation(vault, "op-failed", status="failed", finished_at=now_iso())
    _write_rows(vault, started, finished, failed)

    app = App(vault, coordinate=True)
    try:
        assert app.operation_recoveries == []
        assert _recoveries(vault) == []
    finally:
        app.close_runtime()


def test_empty_target_operation_is_visible_without_attempting_repair(vault):
    _write_rows(vault, _operation(vault, "op-empty"))

    app = App(vault, coordinate=True)
    try:
        row = _recoveries(vault)[0]
        assert row["evidence"]["targets"] == []
        assert row["evidence"]["current_fingerprints"] == {}
    finally:
        app.close_runtime()


def test_truncated_final_log_record_does_not_block_recovery_or_create_spurious_card(vault):
    _write_rows(vault, _operation(vault, "op-valid"), partial='{"id":"cut-off"')

    app = App(vault, coordinate=True)
    try:
        rows = _recoveries(vault)
        assert [row["evidence"]["operation_id"] for row in rows] == ["op-valid"]
    finally:
        app.close_runtime()

    # The next writer append must not glue itself to the incomplete tail and
    # turn it into a new, complete-looking integrity failure after a restart.
    successor = App(vault, coordinate=True)
    try:
        rows = _recoveries(vault)
        assert [row["evidence"]["operation_id"] for row in rows] == ["op-valid"]
    finally:
        successor.close_runtime()


def test_truncated_non_ascii_final_log_bytes_do_not_block_recovery(vault):
    valid = json.dumps(_operation(vault, "op-valid"), ensure_ascii=False).encode("utf-8") + b"\n"
    # A crash in the middle of a multibyte code point cannot be decoded as a
    # complete line. It is an incomplete tail, not permission to skip the
    # preceding durable start record or fail Core startup.
    path = vault.librarian / "runtime" / "operations.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(valid + b'{"id":"cut-\xc3')

    app = App(vault, coordinate=True)
    try:
        rows = _recoveries(vault)
        assert [row["evidence"]["operation_id"] for row in rows] == ["op-valid"]
    finally:
        app.close_runtime()


def test_unreadable_operation_log_refuses_startup_and_releases_the_lease(vault, monkeypatch):
    def unreadable(self):
        raise OperationLogUnreadableError("the vault operation log cannot be read; mutation admission is refused")

    monkeypatch.setattr(VaultWriter, "interrupted_operations", unreadable)

    import pytest
    with pytest.raises(OperationLogUnreadableError, match="mutation admission is refused"):
        App(vault, coordinate=True)

    assert not VaultCoordinator.held_here(vault)


def test_complete_malformed_log_record_is_a_visible_integrity_recovery(vault):
    _write_rows(vault, partial="not JSON\n")

    app = App(vault, coordinate=True)
    try:
        rows = _recoveries(vault)
        assert len(rows) == 1
        evidence = rows[0]["evidence"]
        assert evidence["caller"] == "operation-log"
        assert "integrity_error" in evidence
        assert evidence["targets"] == []
    finally:
        app.close_runtime()


def test_recovery_operation_itself_is_never_recursively_recovered(vault):
    _write_rows(vault, _operation(vault, "op-recovery", caller="operation-recovery"))

    app = App(vault, coordinate=True)
    try:
        assert app.operation_recoveries == []
        assert _recoveries(vault) == []
    finally:
        app.close_runtime()
