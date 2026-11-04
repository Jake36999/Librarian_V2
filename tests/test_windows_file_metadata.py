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


ME = "S-1-5-21-1-2-3-1001"


@pytest.mark.parametrize("sddl, expected", [
    (f"D:P(A;;FA;;;{ME})", True),
    (f"D:PAI(A;;FA;;;{ME})", True),                   # what icacls /inheritance:r leaves
    (f"D:AI(A;;FA;;;{ME})", False),                   # inheritance still on
    (f"D:P(A;ID;FA;;;{ME})", False),                  # an inherited entry
    (f"D:P(A;;FA;;;{ME})(A;;FR;;;S-1-1-0)", False),   # Everyone can read
    (f"D:P(D;;FA;;;{ME})", False),                    # a deny is not a grant
    ("D:P(A;;FA;;;S-1-5-21-1-2-3-1002)", False),      # someone else's
    ("", False),
])
def test_owner_only_means_one_protected_explicit_grant(sddl, expected):
    assert keys.sddl_owner_only(sddl, ME) is expected


@windows
def test_a_protected_key_file_passes_with_or_without_an_integrity_label(tmp_path):
    secret = tmp_path / ".env"
    secret.write_text("", encoding="utf-8")
    assert keys._owner_only(secret)
    assert keys.owner_only(secret), keys.dacl_sddl(secret)
    # An elevated creator (GitHub's runneradmin) leaves a High label; an
    # ordinary user may only lower it. Labels live outside the access list.
    subprocess.run(["icacls", str(secret), "/setintegritylevel", "Low"],
                   capture_output=True, check=True)
    assert keys.owner_only(secret), keys.dacl_sddl(secret)
    subprocess.run(["icacls", str(secret), "/grant", "*S-1-1-0:(R)"],   # Everyone
                   capture_output=True, check=True)
    assert not keys.owner_only(secret), keys.dacl_sddl(secret)


@windows
def test_an_icacls_protected_file_is_judged_by_its_real_access_list(tmp_path):
    """Key files protected the old way are judged by what icacls left.

    Unelevated, `icacls /inheritance:r /grant:r` leaves the one entry. On
    GitHub's elevated runner it kept explicit SYSTEM, Administrators and
    OWNER RIGHTS entries - observed in run 41928589143 as
    D:PAI(A;;FA;;;LA)(A;;FA;;;SY)(A;;FA;;;BA)(A;;FA;;;OW) - which is why the
    hosted key-file check failed. Such a file is not owner-only, and
    protecting it again through the API repairs it.
    """
    secret = tmp_path / ".env"
    secret.write_text("", encoding="utf-8")
    principal = keys._windows_principal()
    subprocess.run(["icacls", str(secret), "/inheritance:r", "/grant:r", f"{principal}:F"],
                   capture_output=True, check=True)
    left = keys.dacl_sddl(secret)
    assert keys.owner_only(secret) is (left.count("(") == 1), left
    assert keys._owner_only(secret) and keys.owner_only(secret), keys.dacl_sddl(secret)
