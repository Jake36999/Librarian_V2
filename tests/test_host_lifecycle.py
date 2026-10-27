"""The explicit local Host lifecycle and private adapter handoff."""
from __future__ import annotations

import os
import subprocess
import sys
import json
from pathlib import Path

import pytest

from resource_librarian import connection, process_identity
from resource_librarian.host import HostManager


def test_windows_tray_companion_is_explicit_and_release_hashed():
    """The optional Windows UI must stay a thin, visible Host control plane.

    Running a notification-area UI is not suitable for headless test workers,
    but this guards the important release and lifecycle contract without
    pretending it has a service or autonomous lifetime policy.
    """
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "librarian-host.ps1").read_text(encoding="utf-8")
    manifest = json.loads((root / "release-manifest.json").read_text(encoding="utf-8"))
    release = (root / "scripts" / "build-release.ps1").read_text(encoding="utf-8")
    verifier = (root / "scripts" / "verify-release.ps1").read_text(encoding="utf-8")

    for label in ("Open", "Status", "Doctor", "Restart", "Stop", "Quit"):
        assert f'Items.Add("{label}"' in script
    assert "NotifyIcon" in script
    assert "host\", \"start" in script
    assert "host\", \"stop" in script
    assert "host\", \"restart" in script
    assert "client reference counting" in script
    assert "idle shutdown policy" in script
    assert "Stop-Process" not in script

    assert "host_companion" in manifest["artifacts"]
    assert 'Add-ManifestArtifact $manifest "host_companion"' in release
    assert '"host_companion"' in verifier


def _child_pid_is_reliable() -> bool:
    """Some restricted Windows runners virtualise process IDs across a
    shell boundary.  The Host quite correctly uses OS PIDs, so an end-to-end
    lifecycle assertion cannot be meaningful on those runners.

    Probe with the *base* interpreter: a venv's python.exe is a redirector
    that starts the base interpreter as a child, so its Popen PID never
    matches.  That is the launch path Librarian.bat and the Host use, and the
    Host follows the Core's published PID for it - so it must be tested, not
    skipped (CORE-02A).
    """
    child = subprocess.Popen([getattr(sys, "_base_executable", sys.executable), "-c",
                              "import os; print(os.getpid())"],
                             stdout=subprocess.PIPE, text=True)
    stdout, _ = child.communicate(timeout=10)
    return child.pid == int(stdout.strip())


def test_host_status_lists_discovered_core_without_page_token(vault, tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path / "config"))
    started = process_identity.process_start(os.getpid())
    if started is None:
        pytest.skip("this platform does not expose a process start identity")
    assert connection.publish(vault.root, url="http://127.0.0.1:9123", token="page-secret",
                              pid=os.getpid(), protocol_version="2",
                              secret_source="obsidian", process_start=started)

    status = HostManager().status()

    assert status["status"] == "running"
    assert status["cores"] == [{"pid": os.getpid(),
                                "process_start": started,
                                "vault": str(vault.root),
                                "url": "http://127.0.0.1:9123", "secret_source": "obsidian",
                                "managed_by_host": False}]
    assert "page-secret" not in repr(status)


def test_host_start_attaches_to_existing_core_for_same_vault(vault, tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path / "config"))
    assert connection.publish(vault.root, url="http://127.0.0.1:9123", token="page-secret",
                              pid=os.getpid(), protocol_version="2",
                              secret_source="desktop")

    result = HostManager().start(str(vault.root))

    assert result["started"] is False
    assert result["detail"] == "a compatible Core is already running for this vault"
    assert "page-secret" not in repr(result)


def test_host_start_ignores_its_own_row_once_the_pid_is_recycled(vault, tmp_path, monkeypatch):
    """Review (2026-10-24): this start path checked the Host's own row by PID
    alone, so a recycled PID read as "already running" and nothing started."""
    from resource_librarian import host as host_module, process_identity
    if process_identity.process_start(os.getpid()) is None:
        pytest.skip("this platform does not expose a process start identity")
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path / "config"))
    host_module._save({"pid": os.getpid(), "vault": str(vault.root.resolve()),
                       "process_start": "win:1", "status": "running"})

    class Launched(Exception):
        pass

    def popen(*args, **kwargs):
        raise Launched
    monkeypatch.setattr(host_module.subprocess, "Popen", popen)
    with pytest.raises(Launched):                    # it went on to start a Core
        HostManager().start(str(vault.root))


def test_host_managed_core_starts_and_stops_cleanly(vault, tmp_path, monkeypatch):
    """A real child is important here: the Host must use its protected
    handoff record and authenticated endpoint rather than a console or kill.
    """
    if not _child_pid_is_reliable():
        pytest.skip("the restricted test runner virtualises child process IDs")
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path / "config"))
    manager = HostManager()
    started = manager.start(str(vault.root))
    try:
        assert started["started"] is True
        assert manager.status()["status"] == "running"
        stopped = manager.stop(str(vault.root))
        assert stopped["stopped"] is True
        assert manager.status()["status"] == "stopped"
        # The Core recorded its shutdown in order (CORE-02A).
        assert [p["phase"] for p in stopped["phases"]] == [
            "admission_closed", "work_cancelled", "writer_drained", "index_closed",
            "lease_released"]
    finally:
        # The normal assertion path already stopped it.  This second explicit
        # request is harmless and avoids leaving a child if a diagnostic
        # assertion above fails.
        manager.stop(str(vault.root), force=True)
