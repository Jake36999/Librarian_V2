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
    ctime_ns: int

    @property
    def identity(self) -> str:
        return f"{self.device}:{self.inode}:{self.ctime_ns}"


class FileChangedError(OSError):
    """A path stopped naming the file whose bytes were just read."""


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
    before_key = (before.st_dev, before.st_ino, before.st_ctime_ns,
                  before.st_mtime_ns, before.st_size)
    after_key = (after.st_dev, after.st_ino, after.st_ctime_ns,
                 after.st_mtime_ns, after.st_size)
    named_key = (named.st_dev, named.st_ino, named.st_ctime_ns,
                 named.st_mtime_ns, named.st_size)
    if data != verified or before_key != after_key or after_key != named_key:
        raise FileChangedError("file changed while its index snapshot was being read")
    return FileSnapshot(data=data, mtime=after.st_mtime, mtime_ns=after.st_mtime_ns,
                        size=after.st_size, device=after.st_dev, inode=after.st_ino,
                        ctime_ns=after.st_ctime_ns)


def read_text(path: Path, *, encoding: str = "utf-8", errors: str = "strict") -> str:
    with file_access(path):
        return path.read_text(encoding=encoding, errors=errors)
