"""Provider keys, kept in the core process and never returned.

The interface only ever learns whether a key is saved, where it came from, and
its last four characters. Where a key lives depends on the host:

- **Obsidian** hands keys to the core when it starts it, from its
  SecretStorage, as environment variables: in memory only (`source: host`).
- **The website** has the core save them: in the operating system's keychain
  when the `keyring` package and a backend are available, otherwise in a
  `.env` file in the user's own config directory (mode 0600), which is never
  inside a vault, so no vault sync or commit can carry it.

A saved key is also set in this process's environment under the provider's
variable name, which is where `providers` reads it. A key never reaches a note,
a log, a session, or a reply.
"""
from __future__ import annotations

import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Any

from .providers import PRESETS

SERVICE = "resource-librarian"
NAME = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


def config_dir() -> Path:
    """The user's own config directory for this program; never a vault."""
    if os.environ.get("LIBRARIAN_CONFIG_DIR"):
        return Path(os.environ["LIBRARIAN_CONFIG_DIR"])
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / SERVICE


# Keys that are not a model provider's: the web search backends (websearch.py reads
# them from the environment). Kept and shown like the model keys (owner, 2026-10-01).
SEARCH_KEYS = {"tavily": "TAVILY_API_KEY", "brave": "BRAVE_API_KEY"}


def key_env(provider: str) -> str:
    if provider in SEARCH_KEYS:
        return SEARCH_KEYS[provider]
    preset = PRESETS.get(provider)
    if preset is None:
        raise KeyError(f"unknown provider {provider!r}")
    return preset["key_env"]


def _key_names() -> list[str]:
    return [p["key_env"] for p in PRESETS.values() if p["key_env"]] + list(SEARCH_KEYS.values())


def _keyring() -> Any:
    try:
        import keyring                                      # type: ignore
        from keyring.backends import fail                   # type: ignore
    except Exception:                                       # noqa: BLE001
        return None
    try:
        if isinstance(keyring.get_keyring(), fail.Keyring):
            return None
    except Exception:                                       # noqa: BLE001
        return None
    return keyring


def _owner_only(path: Path) -> bool:
    """Windows has no POSIX modes - `chmod(0o600)` leaves the file readable by
    whatever the folder grants. Drop inherited entries and grant the current
    user alone, which is what 0600 means. False (never raised) if `icacls`
    is unavailable; `doctor` reports an unprotected file either way."""
    user = os.environ.get("USERNAME", "")
    if not user:
        return False
    try:
        done = subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:F"],
                              capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


def owner_only(path: Path) -> bool:
    """Whether `path` is readable by its owner alone - POSIX mode 600, or on
    Windows an ACL with no inherited entries and one explicit grant."""
    if os.name != "nt":
        return oct(path.stat().st_mode)[-3:] == "600"
    try:
        done = subprocess.run(["icacls", str(path)], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return False
    grants = [line for line in done.stdout.splitlines()[:-1] if ":" in line and "(" in line]
    return done.returncode == 0 and len(grants) == 1 and "(I)" not in grants[0]


class KeyStore:
    def __init__(self, use_keyring: bool = True):
        self._lock = threading.Lock()
        self._keyring = _keyring() if use_keyring else None
        self.path = config_dir() / ".env"
        self._host = {n for n in _key_names() if os.environ.get(n)}   # handed in at start
        self._saved: dict[str, str] = self._read()
        for name, value in self._saved.items():
            os.environ.setdefault(name, value)

    @property
    def backend(self) -> str:
        return "keychain" if self._keyring is not None else "config file"

    # -- storage -------------------------------------------------------------
    def _read(self) -> dict[str, str]:
        out: dict[str, str] = {}
        names = _key_names()
        if self._keyring is not None:
            for name in names:
                value = self._keyring.get_password(SERVICE, name)
                if value:
                    out[name] = value
            return out
        if self.path.is_file():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                name, _, value = line.partition("=")
                if NAME.match(name.strip()) and value.strip():
                    out[name.strip()] = value.strip()
        return out

    def _write(self) -> None:
        if self._keyring is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        if os.name == "nt":
            os.close(fd)
            _owner_only(tmp)                 # restricted while still empty, before any key
            fd = os.open(tmp, os.O_WRONLY | os.O_TRUNC)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("# Provider keys for resource-librarian. Never commit this file.\n")
            for name, value in sorted(self._saved.items()):
                handle.write(f"{name}={value}\n")
        os.replace(tmp, self.path)
        os.chmod(self.path, 0o600)
        if os.name == "nt":
            _owner_only(self.path)

    # -- the interface's view ------------------------------------------------
    def status(self, provider: str) -> dict[str, Any]:
        name = key_env(provider)
        if not name:
            return {"provider": provider, "needed": False, "saved": False}
        value = os.environ.get(name, "")
        source = "saved" if name in self._saved else "host" if name in self._host else \
            "environment" if value else ""
        return {"provider": provider, "needed": True, "saved": bool(value),
                "last4": value[-4:] if len(value) >= 8 else ("" if not value else "••••"),
                "source": source}

    def all(self) -> list[dict[str, Any]]:
        return [self.status(p) for p in [*PRESETS, *SEARCH_KEYS]]

    def save(self, provider: str, key: str) -> dict[str, Any]:
        name = key_env(provider)
        key = (key or "").strip()
        if not name:
            raise ValueError(f"{provider} needs no key")
        if len(key) < 8 or any(c.isspace() for c in key):
            raise ValueError("that does not look like an API key")
        with self._lock:
            if self._keyring is not None:
                self._keyring.set_password(SERVICE, name, key)
            self._saved[name] = key
            self._write()
            os.environ[name] = key
            self._host.discard(name)
        return self.status(provider)

    def remove(self, provider: str) -> dict[str, Any]:
        name = key_env(provider)
        with self._lock:
            if self._keyring is not None and name in self._saved:
                try:
                    self._keyring.delete_password(SERVICE, name)
                except Exception:                           # noqa: BLE001
                    pass
            self._saved.pop(name, None)
            self._write()
            os.environ.pop(name, None)
            self._host.discard(name)
        return self.status(provider)
