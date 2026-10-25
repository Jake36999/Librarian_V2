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
from pathlib import Path
from typing import Any

_guard = threading.Lock()
_locks: weakref.WeakValueDictionary[str, Any] = weakref.WeakValueDictionary()


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


def read_text(path: Path, *, encoding: str = "utf-8", errors: str = "strict") -> str:
    with file_access(path):
        return path.read_text(encoding=encoding, errors=errors)
