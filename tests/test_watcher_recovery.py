"""Filesystem read failures must not kill the watcher or unlock a note."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from resource_librarian import coordination
from resource_librarian.app import App
from resource_librarian.coordination import (
    DocumentBusyError, DocumentLeases, VaultWatcher, atomic_write_text,
)
from resource_librarian.keys import KeyStore
from resource_librarian.rules import Refusal


@pytest.fixture
def watched(vault):
    path = vault.root / "Notes" / "Watched.md"
    atomic_write_text(path, "original")
    leases = DocumentLeases(vault)
    watcher = VaultWatcher(vault, leases, interval=0.1)
    watcher._known = watcher._snapshot()
    yield path, leases, watcher
    watcher.close()


def _locked(monkeypatch, path):
    original = coordination.fingerprint
    locked = threading.Event()
    locked.set()

    def read(target):
        if target == path and locked.is_set():
            raise PermissionError("sensitive exception text must not enter health")
        return original(target)

    monkeypatch.setattr(coordination, "fingerprint", read)
    return locked


def test_failed_observation_retries_unchanged_stat_and_only_blocks_its_note(watched, monkeypatch):
    path, leases, watcher = watched
    leases.note_core_write(["Notes/Watched.md"])
    old_stamp = watcher._known["Notes/Watched.md"]
    atomic_write_text(path, "replacement with a different size")
    locked = _locked(monkeypatch, path)

    watcher.scan_once()
    assert watcher._known["Notes/Watched.md"] == old_stamp
    assert leases.pending_reads() == ["Notes/Watched.md"]
    with pytest.raises(DocumentBusyError, match="unreadable"):
        leases.assert_writable(["Notes/Watched.md"])
    leases.assert_writable(["Notes/Unrelated.md"])
    assert watcher.health()["errors"] == [{"path": "Notes/Watched.md", "error": "PermissionError"}]
    assert "sensitive" not in json.dumps(watcher.health())

    # Time alone must never unlock an unreadable document.
    monkeypatch.setattr(coordination.time, "monotonic", lambda: 1000000000.0)
    watcher.scan_once()
    with pytest.raises(DocumentBusyError, match="unreadable"):
        leases.assert_writable(["Notes/Watched.md"])

    locked.clear()
    watcher.scan_once()
    assert leases.pending_reads() == []
    assert watcher.health()["errors"] == []
    assert watcher._known["Notes/Watched.md"] == (path.stat().st_mtime_ns, path.stat().st_size)
    with pytest.raises(DocumentBusyError, match="editor saving"):
        leases.assert_writable(["Notes/Watched.md"])


def test_retry_of_delayed_exact_core_write_does_not_manufacture_conflicts(watched, monkeypatch):
    path, leases, watcher = watched
    atomic_write_text(path, "Core replacement")
    leases.note_core_write(["Notes/Watched.md"])
    locked = _locked(monkeypatch, path)
    watcher.scan_once()
    locked.clear()
    watcher.scan_once()
    watcher.scan_once()
    assert leases.pending_reads() == []
    leases.assert_writable(["Notes/Watched.md"])
    assert "Notes/Watched.md" not in leases._changed


def test_known_mismatching_human_bytes_are_not_hidden_by_core_time_suppression(watched):
    path, leases, watcher = watched
    leases.note_core_write(["Notes/Watched.md"])
    atomic_write_text(path, "human edit immediately after Core")
    watcher.scan_once()
    with pytest.raises(DocumentBusyError, match="editor saving"):
        leases.assert_writable(["Notes/Watched.md"])


def test_exact_supplied_core_fingerprint_avoids_a_second_file_read(watched, monkeypatch):
    path, leases, watcher = watched
    expected = coordination.fingerprint(path)
    original = coordination.fingerprint

    def unexpected_read(_target):
        raise AssertionError("the caller already supplied the exact published fingerprint")

    monkeypatch.setattr(coordination, "fingerprint", unexpected_read)
    leases.note_core_write(["Notes/Watched.md"],
                           fingerprints={"Notes/Watched.md": expected})
    assert leases._core_fingerprints["Notes/Watched.md"][0] == expected

    # The supplied proof is still only for those exact bytes. A later human
    # replacement must be observed normally and remain protected.
    monkeypatch.setattr(coordination, "fingerprint", original)
    atomic_write_text(path, "human edit immediately after Core")
    watcher.scan_once()
    with pytest.raises(DocumentBusyError, match="editor saving"):
        leases.assert_writable(["Notes/Watched.md"])


def test_human_edit_after_observed_core_save_is_not_hidden_by_suppression(watched):
    path, leases, watcher = watched
    atomic_write_text(path, "Core replacement")
    leases.note_core_write(["Notes/Watched.md"])
    watcher.scan_once()
    leases.assert_writable(["Notes/Watched.md"])
    atomic_write_text(path, "human replacement after Core observation")
    watcher.scan_once()
    with pytest.raises(DocumentBusyError, match="editor saving"):
        leases.assert_writable(["Notes/Watched.md"])


@pytest.mark.parametrize("deleted", [False, True])
def test_failed_new_or_deleted_event_is_not_consumed(watched, monkeypatch, deleted):
    path, leases, watcher = watched
    leases.note_core_write(["Notes/Watched.md"])
    if deleted:
        path.unlink()
    else:
        watcher._known.pop("Notes/Watched.md")
    locked = _locked(monkeypatch, path)
    watcher.scan_once()
    assert ("Notes/Watched.md" in watcher._known) is deleted
    locked.clear()
    watcher.scan_once()
    assert ("Notes/Watched.md" in watcher._known) is not deleted
    assert not leases.pending_reads()


def test_post_commit_fingerprint_failure_preserves_write_and_pauses_rescan(watched, monkeypatch):
    path, leases, watcher = watched
    atomic_write_text(path, "already committed bytes")
    locked = _locked(monkeypatch, path)
    leases.note_core_write(["Notes/Watched.md"])
    assert path.read_text(encoding="utf-8") == "already committed bytes"
    assert leases.pending_reads() == ["Notes/Watched.md"]
    assert "Notes/Watched.md" not in leases._core_fingerprints
    watcher.scan_once()
    locked.clear()
    watcher.scan_once()
    # Without the original post-write hash there is no proof this was Core,
    # so normal debounce applies even while time suppression remains active.
    with pytest.raises(DocumentBusyError, match="editor saving"):
        leases.assert_writable(["Notes/Watched.md"])


def test_locked_heartbeat_keeps_the_editor_lease_after_read_recovery(watched, monkeypatch):
    path, leases, watcher = watched
    locked = _locked(monkeypatch, path)
    reply = leases.heartbeat("Notes/Watched.md", editor="Obsidian")
    assert reply["leases"][0]["baseline"] == "unreadable"
    locked.clear()
    watcher.scan_once()
    assert not leases.pending_reads()
    later = leases._leases["Notes/Watched.md"].touched + 2
    monkeypatch.setattr(coordination.time, "monotonic", lambda: later)
    with pytest.raises(DocumentBusyError, match="Obsidian"):
        leases.assert_writable(["Notes/Watched.md"])
    leases.release("Notes/Watched.md")
    leases.assert_writable(["Notes/Watched.md"])


def test_stat_read_error_is_not_reported_as_deletion(watched, monkeypatch):
    path, leases, watcher = watched
    original = Path.stat
    locked = True

    def stat(target, *args, **kwargs):
        if target == path and locked:
            raise PermissionError("do not log this")
        return original(target, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    snapshot = watcher._snapshot()
    assert snapshot["Notes/Watched.md"] == watcher._known["Notes/Watched.md"]
    assert leases.pending_reads() == ["Notes/Watched.md"]
    watcher.scan_once()
    with pytest.raises(DocumentBusyError, match="unreadable"):
        leases.assert_writable(["Notes/Watched.md"])
    locked = False
    watcher.scan_once()
    assert not leases.pending_reads()
    assert not watcher.health()["errors"]


def test_partial_directory_failure_retains_known_paths_and_clears_health_on_recovery(watched, monkeypatch):
    path, leases, watcher = watched
    original = watcher._list
    broken = True

    def scan(folder):
        # DEPLOY-02: the walk lists folders itself; one listing fails part-way.
        if folder != watcher.vault.root and broken:
            raise PermissionError("private filesystem detail")
        return original(folder)

    monkeypatch.setattr(watcher, "_list", scan)
    known = dict(watcher._known)
    watcher.scan_once()
    assert set(known) <= set(watcher._known)
    assert watcher.health()["errors"] == [{"path": "<snapshot>", "error": "PermissionError"}]
    broken = False
    watcher.scan_once()
    assert not watcher.health()["errors"]


def test_watcher_thread_survives_scan_oserror_and_processes_next_edit(watched, monkeypatch):
    path, leases, watcher = watched
    original = watcher.scan_once
    failed, retried = threading.Event(), threading.Event()

    def scan():
        if not failed.is_set():
            failed.set()
            atomic_write_text(path, "external edit after a failed poll")
            raise PermissionError("injected read failure")
        original()
        retried.set()

    monkeypatch.setattr(watcher, "scan_once", scan)
    watcher.start()
    assert failed.wait(3)
    assert retried.wait(3)
    assert watcher.health()["status"] == "ready"
    assert watcher._thread.is_alive()
    assert "Notes/Watched.md" in leases._changed


def test_pending_read_health_is_degraded_while_thread_lives(watched, monkeypatch):
    path, leases, watcher = watched
    locked = _locked(monkeypatch, path)
    leases.note_core_write(["Notes/Watched.md"])
    watcher.start()
    assert watcher.health()["status"] == "degraded"
    locked.clear()
    watcher.close()
    assert watcher.health()["status"] == "stopped"


def test_programming_errors_remain_visible_not_silently_retried(watched, monkeypatch):
    _, _, watcher = watched

    def broken():
        raise ValueError("programming error")

    monkeypatch.setattr(watcher, "scan_once", broken)
    with pytest.raises(ValueError, match="programming error"):
        watcher._run()


def test_refused_alias_does_not_prevent_other_document_observation(watched, monkeypatch):
    path, leases, watcher = watched
    original = watcher.vault.safe_relative

    def resolve(_vault, rel):
        if rel == "Notes/Alias.md":
            raise Refusal("VAULT_REQUIRED", "outside path and private detail")
        return original(rel)

    monkeypatch.setattr(type(watcher.vault), "safe_relative", resolve)
    atomic_write_text(path, "normal visible edit")
    snapshot = watcher._snapshot()
    snapshot["Notes/Alias.md"] = (1, 1)
    monkeypatch.setattr(watcher, "_snapshot", lambda: snapshot.copy())
    watcher.scan_once()
    assert "Notes/Alias.md" not in watcher._known
    assert "Notes/Watched.md" in leases._changed
    assert watcher.health()["errors"] == [{"path": "Notes/Alias.md", "error": "Refusal"}]


def test_health_is_bounded_and_does_not_include_raw_exception_messages(watched):
    _, leases, watcher = watched
    for number in range(75):
        rel = f"Notes/{number:03}.md"
        watcher._error(rel, PermissionError("fake-key-secret"))
        leases.unreadable(rel)
    health = watcher.health()
    assert health["status"] == "not_started"
    assert len(watcher._errors) == 50
    assert len(health["errors"]) == len(health["pending_reads"]) == 20
    assert health["pending_count"] == 75
    assert "fake-key-secret" not in json.dumps(health)


def test_meta_reports_coordinated_watcher_and_stopped_state(vault):
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False))
    try:
        assert app.meta()["non_secret_health"]["watcher"]["status"] == "ready"
        # Stop polling so the pending-read health can be checked deterministically.
        app.watcher.close()
        app.document_leases.unreadable("Notes/Locked.md")
        health = app.meta()["non_secret_health"]["watcher"]
        assert health["status"] == "stopped"
        assert health["pending_count"] == 1
    finally:
        app.close_runtime()


def test_meta_does_not_claim_an_uncoordinated_watcher(vault):
    app = App(vault, keys=KeyStore(use_keyring=False))
    try:
        assert app.meta()["non_secret_health"]["watcher"] == {"status": "not_coordinated"}
    finally:
        app.close_runtime()
