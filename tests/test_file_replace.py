"""The hosted "promotion interrupted" intermittent (diagnosed 2026-11-07): os.replace
raised PermissionError on a just-written note that another process briefly held.
On Windows the replacement waits that out a few times and then lets a lasting error
stand; elsewhere a PermissionError is never retried."""
from __future__ import annotations

import pytest

from resource_librarian import file_access
from resource_librarian.coordination import atomic_write_text


@pytest.fixture
def held(monkeypatch):
    """os.replace refusing the first `n` attempts, as a briefly held file does."""
    real = file_access.os.replace
    state = {"left": 0, "tries": 0}

    def replace(source, destination):
        state["tries"] += 1
        if state["left"] > 0:
            state["left"] -= 1
            raise PermissionError(13, "The process cannot access the file")
        return real(source, destination)

    monkeypatch.setattr(file_access.os, "replace", replace)
    monkeypatch.setattr(file_access, "REPLACE_WAITS", (0.001,) * 7)
    return state


def test_a_brief_hold_is_waited_out(tmp_path, monkeypatch, held):
    monkeypatch.setattr(file_access, "RETRY_REPLACE", True)
    note = tmp_path / "Indexes" / "Topic - Unfiled.md"
    held["left"] = 2
    atomic_write_text(note, "the new index\n")
    assert note.read_text(encoding="utf-8") == "the new index\n" and held["tries"] == 3
    assert not list(note.parent.glob(".*.tmp"))                    # no temp file left


def test_a_lasting_hold_still_fails_and_leaves_the_old_bytes(tmp_path, monkeypatch, held):
    monkeypatch.setattr(file_access, "RETRY_REPLACE", True)
    note = tmp_path / "note.md"
    note.write_text("old\n", encoding="utf-8")
    held["left"] = 100
    with pytest.raises(PermissionError):
        atomic_write_text(note, "new\n")
    assert note.read_text(encoding="utf-8") == "old\n" and held["tries"] == 8
    assert not list(tmp_path.glob(".*.tmp"))


def test_elsewhere_a_permission_error_is_never_retried(tmp_path, monkeypatch, held):
    monkeypatch.setattr(file_access, "RETRY_REPLACE", False)
    held["left"] = 1
    with pytest.raises(PermissionError):
        atomic_write_text(tmp_path / "note.md", "new\n")
    assert held["tries"] == 1
