"""Short, process-local file IO exclusion, never a vault/editor lease.

Windows os.replace cannot replace an open destination. A Core fingerprint
reader must close its handle before another Core thread replaces that path.
File helpers hold them only for a read or final replacement syscall; auxiliary
stores also serialize their schema initialization. They are not whole-tool,
provider-request, approval-wait, or external-editor transaction locks.
"""
from __future__ import annotations

import os
import threading
import weakref
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_guard = threading.Lock()
_locks: weakref.WeakValueDictionary[str, Any] = weakref.WeakValueDictionary()


@dataclass(frozen=True)
class FileSnapshot:
    """Bytes and metadata captured from the same open file handle."""

    data: bytes
    mtime: float
    mtime_ns: int
    size: int
    device: int
    inode: int
    ctime_ns: int       # identity_time_ns(): creation time on Windows

    @property
    def identity(self) -> str:
        return f"{self.device}:{self.inode}:{self.ctime_ns}"


def identity_time_ns(stat: os.stat_result) -> int:
    """The time that, with device and inode, names one file.

    POSIX: ``st_ctime_ns``, the inode change time, as ever.  Windows: the
    creation time.  Up to Python 3.11 that was ``st_ctime``; from 3.12
    ``st_ctime`` is the NTFS change time and creation is ``st_birthtime``.
    The change time ``os.stat`` reports can trail the one ``os.fstat``
    reports for the same unchanged file (measured 1 ms behind, for as long
    as a test ran), so comparing it across the two calls made every freshly
    written note look changed (MF-004).
    """
    if os.name == "nt":
        birth = getattr(stat, "st_birthtime_ns", None)
        if birth is not None:
            return int(birth)
    return stat.st_ctime_ns


def file_identity(stat: os.stat_result) -> str:
    """The ``device:inode:time`` string the index stores for a file."""
    return f"{stat.st_dev}:{stat.st_ino}:{identity_time_ns(stat)}"


def _key(stat: os.stat_result) -> tuple[int, int, int, int, int]:
    return (stat.st_dev, stat.st_ino, identity_time_ns(stat), stat.st_mtime_ns, stat.st_size)


class FileChangedError(OSError):
    """A path stopped naming the file whose bytes were just read."""


# Hosted CI, 2026-11-07 (the "promotion interrupted" intermittent, three runs before):
# os.replace raised PermissionError on a just-written note. Another process (a virus
# scan or the search indexer reading the new file) briefly held the destination. On
# Windows the replacement is retried a few times, about 1 s in all, and then the error
# stands. Elsewhere a PermissionError is a real one and is never retried.
RETRY_REPLACE = os.name == "nt"
REPLACE_WAITS = (0.02, 0.04, 0.08, 0.16, 0.25, 0.25, 0.25)


def replace(source: Path, destination: Path) -> None:
    """os.replace, waiting out a brief hold on the destination (see above)."""
    import time
    for wait in (*REPLACE_WAITS, None) if RETRY_REPLACE else (None,):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if wait is None:
                raise
            time.sleep(wait)


def file_access(path: Path) -> Any:
    """One reentrant lock per canonical path, reclaimed after its last user."""
    key = os.path.normcase(str(path.resolve()))
    with _guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.RLock()
            _locks[key] = lock
        return lock


def read_bytes(path: Path) -> bytes:
    """Close this Core read handle before same-path atomic replacement."""
    with file_access(path):
        return path.read_bytes()


def read_bytes_snapshot(path: Path) -> FileSnapshot:
    """Read bytes and metadata from one handle, rejecting a replaced path.

    The post-close path stat matters on POSIX, where an open file can be
    renamed or deleted while it is being read.  On Windows the ordinary CRT
    handle also gives the replacement side a short, deterministic exclusion
    window.  Core's own writers additionally share ``file_access(path)``.
    """
    with file_access(path):
        with path.open("rb") as reader:
            # Simple instrumented readers used by deterministic concurrency
            # tests need not expose ``fileno``; real filesystem handles do.
            descriptor = getattr(reader, "fileno", None)
            before = os.fstat(descriptor()) if callable(descriptor) else path.stat()
            data = reader.read()
            seek = getattr(reader, "seek", None)
            if callable(seek):
                seek(0)
                verified = reader.read()
            else:
                verified = data
            after = os.fstat(descriptor()) if callable(descriptor) else path.stat()
        named = path.stat()
    after_key = _key(after)
    if data != verified or _key(before) != after_key or after_key != _key(named):
        raise FileChangedError("file changed while its index snapshot was being read")
    return FileSnapshot(data=data, mtime=after.st_mtime, mtime_ns=after.st_mtime_ns,
                        size=after.st_size, device=after.st_dev, inode=after.st_ino,
                        ctime_ns=identity_time_ns(after))


def read_text(path: Path, *, encoding: str = "utf-8", errors: str = "strict") -> str:
    with file_access(path):
        return path.read_text(encoding=encoding, errors=errors)
