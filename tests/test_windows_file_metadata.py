"""MF-004: Windows file metadata that hosted CI exposed.

Python 3.12 made Windows ``st_ctime`` the NTFS change time, and ``os.stat``
can report it behind ``os.fstat`` for a file nobody changed. An elevated
process (GitHub's ``runneradmin``) labels each file it creates with an
integrity level, which ``icacls`` prints like an access grant.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from resource_librarian import keys
from resource_librarian.file_access import file_identity, identity_time_ns, read_bytes_snapshot

windows = pytest.mark.skipif(os.name != "nt", reason="Windows file metadata")


def test_identity_time_is_creation_on_windows_and_inode_change_elsewhere(monkeypatch):
    both = SimpleNamespace(st_ctime_ns=2, st_birthtime_ns=1)
    monkeypatch.setattr(os, "name", "nt")
    assert identity_time_ns(both) == 1
    # Python 3.11 has no st_birthtime on Windows; its st_ctime was creation.
    assert identity_time_ns(SimpleNamespace(st_ctime_ns=2)) == 2
    monkeypatch.setattr(os, "name", "posix")
    assert identity_time_ns(both) == 2


@windows
def test_a_change_time_lagging_only_in_os_stat_is_not_a_change(tmp_path, monkeypatch):
    note = tmp_path / "Note.md"
    note.write_bytes(b"unchanged\n")
    real = Path.stat
    expected = file_identity(real(note))

    def lagging(self, *args, **kwargs):
        st = real(self, *args, **kwargs)
        fields = {name: getattr(st, name) for name in dir(st) if name.startswith("st_")}
        fields.setdefault("st_birthtime_ns", st.st_ctime_ns)   # 3.11: st_ctime is creation
        fields["st_ctime_ns"] -= 1_000_000                      # measured 1 ms behind fstat
        return SimpleNamespace(**fields)

    monkeypatch.setattr(Path, "stat", lagging)
    snapshot = read_bytes_snapshot(note)
    assert snapshot.data == b"unchanged\n"
    assert snapshot.identity == expected == file_identity(note.stat())


@windows
def test_an_integrity_label_is_not_a_second_grant(tmp_path):
    secret = tmp_path / ".env"
    secret.write_text("", encoding="utf-8")
    assert keys._owner_only(secret) and keys.owner_only(secret)
    # An elevated creator leaves a High label; an ordinary user may only lower
    # it, and icacls prints a Low label the same way.
    subprocess.run(["icacls", str(secret), "/setintegritylevel", "Low"],
                   capture_output=True, check=True)
    assert keys.owner_only(secret)
    subprocess.run(["icacls", str(secret), "/grant", "*S-1-1-0:(R)"],   # Everyone
                   capture_output=True, check=True)
    assert not keys.owner_only(secret)
