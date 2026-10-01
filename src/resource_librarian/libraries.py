"""The libraries this person has opened, for switching between them.

One library per domain (Co-work Roadmap §4 F), so a person keeps several and
moves between them the way Obsidian moves between vaults. The list lives in
the user's own config directory, beside mcp.json - never inside a vault, since
it names other vaults' locations. Every library the app opens is remembered;
one can also be added by path. Nothing here reads another library's content:
switching loads a library, it never joins two.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .keys import config_dir
from .vault import Vault, now_iso

FILE = "libraries.json"
_lock = threading.Lock()


def _path() -> Path:
    return config_dir() / FILE


def _read() -> list[dict[str, Any]]:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return [e for e in data.get("libraries", []) if isinstance(e, dict) and e.get("path")]


def _write(entries: list[dict[str, Any]]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"libraries": entries}, indent=1), encoding="utf-8")
    tmp.replace(path)


def _key(root: Path | str) -> str:
    return str(Path(root).expanduser().resolve()).casefold()


def remember(vault: Vault) -> None:
    """Record that `vault` was opened now (its display name refreshed).

    The name is the vault's own configured title, not its folder's: a
    `new-vault.ps1` vault always lives in a folder named `.librarian-app`
    (§ the per-project launcher), so the folder name alone cannot tell two
    such libraries apart in the switcher.
    """
    with _lock:
        entries = [e for e in _read() if _key(e["path"]) != _key(vault.root)]
        entries.insert(0, {"path": str(vault.root), "name": vault.title,
                           "last_opened": now_iso()})
        _write(entries)


def forget(path: str) -> bool:
    with _lock:
        entries = _read()
        kept = [e for e in entries if _key(e["path"]) != _key(path)]
        _write(kept)
        return len(kept) != len(entries)


def resolve(path: str) -> Vault:
    """The library at `path`, or a refusal naming why it cannot be opened."""
    raw = str(path or "").strip().strip('"')
    if not raw:
        raise ValueError("a library is a folder path")
    vault = Vault(Path(raw).expanduser().resolve())
    if not vault.exists():
        raise ValueError(f"{raw} is not a library: no .librarian/config.toml there "
                         f"(new-vault.ps1 or `resource-librarian init` makes one)")
    return vault


def known(current: Vault | None = None) -> list[dict[str, Any]]:
    """Every remembered library, most recently opened first, marking the open
    one and any whose folder has since gone missing."""
    out = []
    for e in _read():
        try:
            present = Vault(Path(e["path"])).exists()
        except OSError:
            present = False
        out.append({**e, "current": current is not None and _key(e["path"]) == _key(current.root),
                    "missing": not present})
    return out
