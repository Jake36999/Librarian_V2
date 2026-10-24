"""CORE-01: one platform-aware liveness check, pinned to process identity.

On Windows `os.kill(pid, 0)` reported an exited Core as alive while a handle
to it was still open, so Host Stop always waited out its 15 s window.
"""
import json
import os
import subprocess
import sys

import pytest

from resource_librarian import connection, process_identity
from resource_librarian.coordination import LeaseInfo

# A venv's python.exe is a redirector that starts the base interpreter as a
# child, so its Popen PID is not the interpreter's.  Spawn the base one.
PYTHON = getattr(sys, "_base_executable", sys.executable)


def _sleeper() -> subprocess.Popen:
    return subprocess.Popen([PYTHON, "-c", "import time; time.sleep(30)"])


def test_a_running_child_is_alive_and_has_a_creation_time():
    child = _sleeper()
    try:
        assert process_identity.is_alive(child.pid)
        started = process_identity.process_started_at(child.pid)
        if os.name == "nt" or sys.platform.startswith("linux"):
            assert started is not None
            assert process_identity.is_alive(child.pid, started)
    finally:
        child.kill()
        child.wait()


def test_an_exited_child_is_not_alive_while_its_handle_is_still_held():
    child = subprocess.Popen([PYTHON, "-c", "pass"])
    child.wait()                      # the Popen object keeps its handle open
    assert process_identity.is_alive(child.pid) is False


@pytest.mark.parametrize("pid", [0, -1, 2**31 - 1])
def test_invalid_pids_are_not_alive(pid):
    assert process_identity.is_alive(pid) is False
    assert process_identity.process_started_at(pid) is None


def test_the_current_process_is_alive():
    identity = process_identity.current_identity()
    assert identity["pid"] == os.getpid()
    assert process_identity.is_alive(os.getpid())


def test_a_reused_pid_is_not_the_recorded_process(monkeypatch):
    child = _sleeper()
    try:
        monkeypatch.setattr(process_identity, "process_started_at", lambda pid: 1_000.0)
        assert process_identity.is_alive(child.pid, 2_000.0) is False   # recycled PID
        assert process_identity.is_alive(child.pid, 1_000.5) is True    # within tolerance
        # An older or malformed record has no usable time: never proof it stopped.
        assert process_identity.is_alive(child.pid, None) is True
        assert process_identity.is_alive(child.pid, "yesterday") is True
    finally:
        child.kill()
        child.wait()


@pytest.mark.skipif(os.name != "nt", reason="Windows access-denied path")
def test_an_inaccessible_process_counts_as_alive(monkeypatch):
    class Kernel32:
        def OpenProcess(self, access, inherit, pid):
            return None

    monkeypatch.setattr(process_identity, "_windows_library", lambda: Kernel32())
    monkeypatch.setattr(process_identity.ctypes, "get_last_error", lambda: 5)
    assert process_identity.is_alive(4242) is True          # cannot prove it stopped
    monkeypatch.setattr(process_identity.ctypes, "get_last_error", lambda: 87)
    assert process_identity.is_alive(4242) is False         # no such process


def test_connection_records_carry_and_validate_the_creation_time(tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path / "config"))
    vault = tmp_path / "vault"
    vault.mkdir()
    assert connection.publish(vault, url="http://127.0.0.1:1", token="t", pid=os.getpid(),
                              protocol_version="2", secret_source="desktop",
                              process_started=123.5)
    assert connection.load(vault)["process_started"] == 123.5
    path = connection.path_for(vault)
    row = json.loads(path.read_text(encoding="utf-8"))
    row["process_started"] = "not a time"
    path.write_text(json.dumps(row), encoding="utf-8")
    loaded = connection.load(vault)
    assert loaded is not None and "process_started" not in loaded       # dropped, not rejected
    assert connection.publish(vault, url="http://127.0.0.1:1", token="t", pid=os.getpid(),
                              protocol_version="2", secret_source="desktop")
    assert "process_started" not in connection.load(vault)


def test_our_own_pid_in_a_record_from_an_earlier_process_is_not_us():
    mine = process_identity.process_started_at(os.getpid())
    if mine is None:
        pytest.skip("this platform does not expose process creation times")
    assert process_identity.is_alive(os.getpid(), mine) is True
    assert process_identity.is_alive(os.getpid(), mine - 3_600) is False


def test_a_recycled_own_pid_lease_needs_an_explicit_takeover(vault):
    """Reviewer finding (Qwen3.5, CORE-01): a lease row with our PID was always
    treated as same-process recovery, skipping the stale-lease safeguard."""
    from resource_librarian.coordination import StaleLeaseError, VaultCoordinator
    if process_identity.process_started_at(os.getpid()) is None:
        pytest.skip("this platform does not expose process creation times")
    coordinator = VaultCoordinator(vault)
    coordinator.runtime.mkdir(parents=True, exist_ok=True)
    coordinator.info_path.write_text(json.dumps({
        "instance_id": "crashed-core", "pid": os.getpid(), "started_at": "earlier",
        "protocol_version": "1", "core_version": "2", "vault": str(vault.root),
        "process_started": 1.0}), encoding="utf-8")
    with pytest.raises(StaleLeaseError):
        coordinator.acquire()
    coordinator.acquire(takeover=True)
    coordinator.release()


def test_an_old_lease_without_a_creation_time_still_loads():
    old = {"instance_id": "a", "pid": 1, "started_at": "x", "protocol_version": "1",
           "core_version": "2", "vault": "v"}
    assert LeaseInfo(**old).process_started is None
