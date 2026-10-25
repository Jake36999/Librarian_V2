"""Exclude short Core hash/replacement overlap without a vault-wide lock."""
from __future__ import annotations

import gc
import os
import threading
from pathlib import Path

import pytest

from resource_librarian import coordination, file_access as access_module
from resource_librarian.coordination import atomic_write_bytes, atomic_write_text, fingerprint, fingerprint_bytes
from resource_librarian.file_access import file_access


@pytest.mark.skipif(os.name != "nt", reason="Windows CRT sharing baseline")
def test_external_open_reader_still_causes_explicit_windows_write_failure(tmp_path):
    path = tmp_path / "note.md"
    path.write_text("old", encoding="utf-8")
    with path.open("rb"):
        with pytest.raises(PermissionError):
            atomic_write_text(path, "new")
    assert path.read_text(encoding="utf-8") == "old"
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("binary", [False, True])
def test_core_fingerprint_reader_finishes_before_atomic_replacement(tmp_path, monkeypatch, binary):
    path = tmp_path / "note.md"
    path.write_bytes(b"opened revision")
    entered, release, writer_entered, finished = (threading.Event() for _ in range(4))
    original = Path.open
    results, errors = [], []

    class Reader:
        def __init__(self, target, *args, **kwargs):
            self.reader = original(target, *args, **kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.reader.close()

        def read(self, size):
            entered.set()
            assert release.wait(5), "test did not release its held fingerprint read"
            return self.reader.read(size)

    def open_path(target, *args, **kwargs):
        if target == path and args == ("rb",):
            return Reader(target, *args, **kwargs)
        return original(target, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_path)

    def hash_note():
        try:
            results.append(fingerprint(path))
        except BaseException as exc:
            errors.append(exc)

    def replace_note():
        try:
            writer_entered.set()
            if binary:
                atomic_write_bytes(path, b"replacement revision")
            else:
                atomic_write_text(path, "replacement revision")
        except BaseException as exc:
            errors.append(exc)
        finally:
            finished.set()

    reader = threading.Thread(target=hash_note)
    writer = threading.Thread(target=replace_note)
    reader.start()
    try:
        assert entered.wait(3)
        writer.start()
        assert writer_entered.wait(3)
        assert not finished.wait(0.1), "replacement overlapped its Core fingerprint handle"
        # Another note remains writable while this path is held.
        atomic_write_text(tmp_path / "other.md", "unrelated")
    finally:
        release.set()
        reader.join(5)
        if writer.ident is not None:
            writer.join(5)
    assert not reader.is_alive() and not writer.is_alive()
    assert not errors
    assert results == [fingerprint_bytes(b"opened revision")]
    assert fingerprint(path) == fingerprint_bytes(b"replacement revision")


def test_same_canonical_path_reuses_reentrant_lock(tmp_path):
    path = tmp_path / "note.md"
    first = file_access(path)
    second = file_access(tmp_path / "sub" / ".." / "note.md")
    assert first is second
    with first:
        with second:
            atomic_write_text(path, "nested operation")
            assert fingerprint(path) == fingerprint_bytes(b"nested operation")


@pytest.mark.skipif(os.name != "nt", reason="Windows case folding")
def test_windows_case_alias_has_one_lock(tmp_path):
    path = tmp_path / "note.md"
    first = file_access(path)
    assert first is file_access(Path(str(path).upper()))


def test_finished_paths_do_not_accumulate_forever_in_lock_registry(tmp_path):
    path = tmp_path / "one-off.md"
    lock = file_access(path)
    key = os.path.normcase(str(path.resolve()))
    assert access_module._locks[key] is lock
    del lock
    gc.collect()
    assert key not in access_module._locks


def test_read_error_is_not_replaced_with_missing_hash(tmp_path, monkeypatch):
    path = tmp_path / "note.md"
    path.write_text("existing", encoding="utf-8")
    original = Path.open

    def deny(target, *args, **kwargs):
        if target == path:
            raise PermissionError("locked")
        return original(target, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny)
    with pytest.raises(PermissionError):
        fingerprint(path)
    # A failed read releases the lock; errors do not strand later writers.
    monkeypatch.setattr(Path, "open", original)
    atomic_write_text(path, "later")
    assert fingerprint(path) == fingerprint_bytes(b"later")
