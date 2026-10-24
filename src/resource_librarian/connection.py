"""Private discovery records for an already-running local Core.

The vault lease is deliberately *diagnostic only*: it has no port, token, or
other connection material.  An adapter still needs a safe way to attach to a
Core which is already serving that vault, though.  This module keeps that
short-lived connection material in the person's configuration directory with
owner-only permissions.  It is not stored in a vault, synced through
Obsidian, or exposed by a public API.

The record is an optimisation for adapters, not an authority.  Consumers must
still verify that its PID is alive and complete the normal authenticated
``/api/meta`` handshake before using it.  Failure to read or protect the file
simply means an adapter starts through the ordinary Host path.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any

from .keys import _owner_only, config_dir


def _key(vault_path: str | Path) -> str:
    """Stable, non-reversible filename for a canonical vault path."""
    path = str(Path(vault_path).resolve())
    if os.name == "nt":
        path = path.casefold()
    return hashlib.sha256(path.encode("utf-8")).hexdigest()[:24]


def directory() -> Path:
    return config_dir() / "cores"


def path_for(vault_path: str | Path) -> Path:
    return directory() / f"{_key(vault_path)}.json"


def _private_write(path: Path, payload: str) -> bool:
    """Atomically write a record without ever leaving secret text in a broad
    Windows ACL.  On a platform where the ACL cannot be made owner-only, fail
    closed: discovery is optional, exposing a page token is not.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{secrets.token_hex(6)}.tmp")
    fd: int | None = None
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        if os.name == "nt":
            os.close(fd)
            fd = None
            if not _owner_only(temp):
                return False
            fd = os.open(temp, os.O_WRONLY | os.O_TRUNC)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = None
            handle.write(payload)
            handle.flush()
            with contextlib.suppress(OSError):
                os.fsync(handle.fileno())
        os.replace(temp, path)
        os.chmod(path, 0o600)
        if os.name == "nt" and not _owner_only(path):
            with contextlib.suppress(OSError):
                path.unlink()
            return False
        return True
    except OSError:
        return False
    finally:
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)
        with contextlib.suppress(OSError):
            temp.unlink()


def publish(vault_path: str | Path, *, url: str, token: str, pid: int,
            protocol_version: str, secret_source: str,
            process_started: float | None = None) -> bool:
    """Publish an adapter attachment record.  ``token`` is deliberately only
    written into this owner-only, per-user location.
    """
    payload = {
        "schema_version": 1,
        "vault": str(Path(vault_path).resolve()),
        "url": str(url).rstrip("/"),
        "token": token,
        "pid": int(pid),
        "protocol_version": str(protocol_version),
        "secret_source": secret_source,
    }
    if process_started is not None:
        # Creation time pins the record to the process that wrote it, so a
        # recycled PID is not read as a live Core; older readers ignore it.
        payload["process_started"] = float(process_started)
    return _private_write(path_for(vault_path), json.dumps(payload, separators=(",", ":")) + "\n")


def load(vault_path: str | Path) -> dict[str, Any] | None:
    """Return a syntactically valid record only.  Liveness/handshake belongs
    to the caller because this module intentionally has no network behaviour.
    """
    try:
        row = json.loads(path_for(vault_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    required = ("vault", "url", "token", "pid", "protocol_version")
    if not isinstance(row, dict) or not all(row.get(key) not in (None, "") for key in required):
        return None
    try:
        if str(Path(str(row["vault"])).resolve()) != str(Path(vault_path).resolve()):
            return None
        row["pid"] = int(row["pid"])
    except (OSError, TypeError, ValueError):
        return None
    # Identity metadata, not a required field: keep a number, drop anything else.
    started = row.get("process_started")
    if isinstance(started, (int, float)) and not isinstance(started, bool):
        row["process_started"] = float(started)
    else:
        row.pop("process_started", None)
    return row


def records() -> list[dict[str, Any]]:
    """Return valid per-vault discovery records without exposing a directory
    convention to callers.

    The small Host uses this only to show and explicitly select running Cores
    that were started by Obsidian or Cowork.  Connection records remain an
    attachment hint, not an authority: callers still check PID liveness and
    perform the authenticated `/api/meta` or lifecycle handshake.
    """
    try:
        paths = sorted(directory().glob("*.json"))
    except OSError:
        return []
    found: list[dict[str, Any]] = []
    for path in paths:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            vault = str(raw.get("vault") or "") if isinstance(raw, dict) else ""
        except (OSError, ValueError, TypeError):
            continue
        if not vault:
            continue
        # `load` rechecks the canonical vault and therefore rejects a file
        # that does not match the filename derived from that vault.
        row = load(vault)
        if row is not None and path == path_for(vault):
            found.append(row)
    return found


def remove(vault_path: str | Path, *, pid: int | None = None, token: str = "") -> None:
    """Remove only this Core's record; never erase a newer Core's handoff."""
    path = path_for(vault_path)
    row = load(vault_path)
    if row is None:
        return
    if pid is not None and int(row.get("pid") or 0) != int(pid):
        return
    if token and str(row.get("token") or "") != token:
        return
    with contextlib.suppress(OSError):
        path.unlink()
