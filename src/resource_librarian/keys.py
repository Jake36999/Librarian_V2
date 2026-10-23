"""Provider keys, kept in the core process and never returned.

The interface only ever learns whether a key is saved, where it came from, and
its last four characters. Where a key lives depends on the host:

- **Obsidian** hands keys to the core when it starts it, from its
  SecretStorage, as environment variables: in memory only
  (`source: obsidian_managed`).  The Core cannot overwrite these keys; the
  adapter restarts it when the person rotates a secret in Obsidian.
- **The website** has the core save them: in the operating system's keychain
  when the `keyring` package and a backend are available, otherwise in a
  `.env` file in the user's own config directory (mode 0600), which is never
  inside a vault, so no vault sync or commit can carry it.

A saved key is also set in this process's environment under the provider's
variable name, which is where `providers` reads it. A key never reaches a note,
a log, a session, or a reply.
"""
from __future__ import annotations

import contextlib
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


# Keys that are not a model provider's: the web search backends (websearch.py) and
# GitHub's API for repository intake (intake.py), read from the environment. Kept and
# shown like the model keys (owner, 2026-10-01).
SEARCH_KEYS = {"tavily": "TAVILY_API_KEY", "brave": "BRAVE_API_KEY", "github": "GITHUB_TOKEN"}


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


def _windows_principal() -> str:
    """The current Windows SID in icacls' SID form, never a display name.

    `%USERNAME%` can resolve to the wrong principal on domain, renamed, and
    service-account installations.  `whoami /user` is present on supported
    Windows editions; an empty value lets the caller fail closed rather than
    grant a broad ACL.
    """
    try:
        done = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],
                              capture_output=True, text=True, timeout=10)
        if done.returncode != 0:
            return ""
        # CSV is deliberately parsed without trusting the account display
        # name, which may contain commas.  The SID is the final quoted field.
        fields = [part.strip().strip('"') for part in done.stdout.strip().rsplit(",", 1)]
        sid = fields[-1] if fields else ""
        return f"*{sid}" if re.fullmatch(r"S-1-[0-9-]+", sid) else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _owner_only(path: Path) -> bool:
    """Windows has no POSIX modes - `chmod(0o600)` leaves the file readable by
    whatever the folder grants. Drop inherited entries and grant the current
    user alone, which is what 0600 means. False (never raised) if `icacls`
    is unavailable; `doctor` reports an unprotected file either way."""
    principal = _windows_principal()
    if not principal:
        return False
    try:
        done = subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"{principal}:F"],
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
    def __init__(self, use_keyring: bool = True, *, obsidian_managed: bool = False):
        self._lock = threading.Lock()
        self._keyring = _keyring() if use_keyring else None
        self.path = config_dir() / ".env"
        self._host = {n for n in _key_names() if os.environ.get(n)}   # handed in at start
        self._obsidian_mode = bool(obsidian_managed)
        self._managed = set(self._host) if self._obsidian_mode else set()
        self._extra_names: set[str] = set()
        # Always inspect the protected fallback.  If keyring became available
        # after an older install created it, the credentials must remain
        # usable long enough for the person to explicitly migrate them rather
        # than disappearing or being falsely labelled "already secure".
        self._fallback: dict[str, str] = self._read_fallback()
        self._fallback_file_pending = bool(self._fallback)
        self._pending_fallback_names: set[str] = set()
        self._saved: dict[str, str] = self._read()
        if self._keyring is not None:
            for name, value in list(self._fallback.items()):
                if name not in self._saved:
                    self._saved[name] = value
                    self._pending_fallback_names.add(name)
                else:
                    # The keychain is authoritative for this name.  Keep no
                    # stale fallback value in the migration set, but retain
                    # the file-pending marker so a later explicit migration
                    # cleans the old protected file.
                    self._fallback.pop(name, None)
        for name, value in self._saved.items():
            os.environ.setdefault(name, value)

    @property
    def backend(self) -> str:
        return "keychain" if self._keyring is not None else "config file"

    @property
    def migration_pending(self) -> bool:
        """Whether a former fallback file still needs explicit keychain migration."""
        return bool(self._pending_fallback_names or self._fallback_file_pending)

    @property
    def obsidian_managed(self) -> bool:
        return bool(self._managed)

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
        return self._read_fallback()

    def _read_fallback(self) -> dict[str, str]:
        """Read the protected fallback independently of the active backend."""
        out: dict[str, str] = {}
        if self.path.is_file():
            try:
                lines = self.path.read_text(encoding="utf-8").splitlines()
            except OSError:
                return out
            for line in lines:
                name, _, value = line.partition("=")
                if NAME.match(name.strip()) and value.strip():
                    out[name.strip()] = value.strip()
        return out

    def _write_fallback(self, values: dict[str, str]) -> None:
        """Atomically replace the protected fallback without exposing a key.

        Usually this is called only when no OS keychain exists.  During an
        explicit migration it also removes a superseded entry from an old
        fallback file, so a later restart cannot resurrect an outdated key.
        """
        if not values:
            with contextlib.suppress(FileNotFoundError):
                self.path.unlink()
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        if os.name == "nt":
            os.close(fd)
            if not _owner_only(tmp):          # restricted while still empty, before any key
                with contextlib.suppress(OSError):
                    tmp.unlink()
                raise PermissionError("could not restrict the fallback key file to the effective Windows SID")
            fd = os.open(tmp, os.O_WRONLY | os.O_TRUNC)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("# Provider keys for resource-librarian. Never commit this file.\n")
            for name, value in sorted(values.items()):
                handle.write(f"{name}={value}\n")
        os.replace(tmp, self.path)
        os.chmod(self.path, 0o600)
        if os.name == "nt":
            _owner_only(self.path)

    def _write(self) -> None:
        if self._keyring is None:
            self._write_fallback(self._saved)

    # -- the interface's view ------------------------------------------------
    def _status_name(self, name: str, *, label: str) -> dict[str, Any]:
        if not name:
            return {"provider": label, "needed": False, "saved": False}
        value = os.environ.get(name, "")
        source = "fallback_pending_migration" if name in self._pending_fallback_names else \
            "saved" if name in self._saved else "obsidian_managed" if name in self._managed else \
            "host" if name in self._host else \
            "environment" if value else ""
        return {"provider": label, "needed": True, "saved": bool(value),
                "last4": value[-4:] if len(value) >= 8 else ("" if not value else "••••"),
                "source": source, "migration_pending": name in self._pending_fallback_names}

    def status(self, provider: str) -> dict[str, Any]:
        return self._status_name(key_env(provider), label=provider)

    def register_ref(self, name: str) -> None:
        """Make a host's non-secret environment reference observable.

        Host records store only this variable name.  When a keychain is in
        use, loading it here means an existing personal key works after a
        restart without storing its value in the host registry.
        """
        name = str(name or "").strip()
        if not name or not NAME.match(name):
            return
        with self._lock:
            self._extra_names.add(name)
            if self._obsidian_mode and os.environ.get(name):
                self._managed.add(name)
            if self._keyring is not None and name not in self._saved:
                try:
                    value = self._keyring.get_password(SERVICE, name)
                except Exception:                           # noqa: BLE001
                    value = None
                if value:
                    self._saved[name] = value
                    os.environ.setdefault(name, value)

    def status_ref(self, name: str, label: str = "host") -> dict[str, Any]:
        self.register_ref(name)
        return self._status_name(name, label=label)

    def all(self) -> list[dict[str, Any]]:
        return [self.status(p) for p in [*PRESETS, *SEARCH_KEYS]]

    def save(self, provider: str, key: str) -> dict[str, Any]:
        return self.save_ref(key_env(provider), key, label=provider)

    def save_ref(self, name: str, key: str, *, label: str = "host") -> dict[str, Any]:
        self.register_ref(name)
        key = (key or "").strip()
        if not name:
            raise ValueError(f"{label} needs no key")
        if name in self._managed:
            raise PermissionError("this key is managed by Obsidian SecretStorage; change it in "
                                  "the Librarian Obsidian settings and restart the Core")
        if len(key) < 8 or any(c.isspace() for c in key):
            raise ValueError("that does not look like an API key")
        with self._lock:
            previous_saved = self._saved.get(name)
            previous_fallback = self._fallback.get(name)
            was_pending = name in self._pending_fallback_names
            previous_keyring = None
            if self._keyring is not None:
                previous_keyring = self._keyring.get_password(SERVICE, name)
            self._saved[name] = key
            try:
                if self._keyring is not None:
                    self._keyring.set_password(SERVICE, name, key)
                    # A fresh keychain save supersedes a same-name fallback
                    # value.  Rewrite the old protected file now, so it can
                    # never overwrite this choice during a later migration.
                    if was_pending:
                        self._fallback.pop(name, None)
                        self._pending_fallback_names.discard(name)
                        self._write_fallback(self._fallback)
                        self._fallback_file_pending = self.path.is_file()
                else:
                    self._fallback[name] = key
                self._write()
            except Exception:
                if previous_saved is None:
                    self._saved.pop(name, None)
                else:
                    self._saved[name] = previous_saved
                if previous_fallback is None:
                    self._fallback.pop(name, None)
                else:
                    self._fallback[name] = previous_fallback
                if was_pending:
                    self._pending_fallback_names.add(name)
                if self._keyring is not None:
                    with contextlib.suppress(Exception):
                        if previous_keyring is None:
                            self._keyring.delete_password(SERVICE, name)
                        else:
                            self._keyring.set_password(SERVICE, name, previous_keyring)
                    with contextlib.suppress(Exception):
                        self._write_fallback(self._fallback)
                raise
            os.environ[name] = key
            self._host.discard(name)
        return self._status_name(name, label=label)

    def remove(self, provider: str) -> dict[str, Any]:
        return self.remove_ref(key_env(provider), label=provider)

    def remove_ref(self, name: str, *, label: str = "host") -> dict[str, Any]:
        self.register_ref(name)
        if name in self._managed:
            raise PermissionError("this key is managed by Obsidian SecretStorage; remove it in "
                                  "the Librarian Obsidian settings and restart the Core")
        with self._lock:
            previous_fallback = self._fallback.get(name)
            was_pending = name in self._pending_fallback_names
            if self._keyring is not None and name in self._saved:
                try:
                    self._keyring.delete_password(SERVICE, name)
                except Exception:                           # noqa: BLE001
                    pass
            self._saved.pop(name, None)
            self._fallback.pop(name, None)
            self._pending_fallback_names.discard(name)
            try:
                if self._keyring is not None and (was_pending or previous_fallback is not None):
                    self._write_fallback(self._fallback)
                    self._fallback_file_pending = self.path.is_file()
                else:
                    self._write()
            except Exception:
                # The keychain removal already occurred; restore only the
                # migration bookkeeping and report the filesystem failure so
                # the person can retry rather than claim an incomplete erase.
                if previous_fallback is not None:
                    self._fallback[name] = previous_fallback
                if was_pending:
                    self._pending_fallback_names.add(name)
                raise
            os.environ.pop(name, None)
            self._host.discard(name)
        return self._status_name(name, label=label)

    def migrate_to_keychain(self) -> dict[str, Any]:
        """Move fallback-file credentials into the operating-system keychain.

        The fallback exists for hosts where a credential backend genuinely is
        unavailable.  It must not become a sticky second-class storage mode
        once the backend is installed or repaired.  This deliberately moves
        only values that were persisted in the fallback file: environment and
        Obsidian-managed secrets stay external, and no secret value is ever
        returned to an adapter.

        Keychain writes happen before the fallback file is removed.  A
        failed write leaves the file untouched; a failed cleanup reports the
        duplicate explicitly instead of claiming a completed migration.
        """
        if self._obsidian_mode:
            raise PermissionError("Obsidian SecretStorage credentials are managed by Obsidian and cannot be migrated here")
        with self._lock:
            # A current keyring does not mean an older protected fallback was
            # already copied.  ``_pending_fallback_names`` is populated on
            # startup precisely for the keyring-installed-after-fallback path.
            backend = self._keyring or _keyring()
            if backend is None:
                return {"migrated": 0, "backend": "config file", "available": False,
                        "detail": "No supported operating-system keychain is available yet; the protected fallback remains in use."}
            values = (dict(self._fallback) if self._keyring is not None else dict(self._saved))
            if not values:
                self._keyring = backend
                with contextlib.suppress(OSError):
                    self.path.unlink()
                self._fallback_file_pending = self.path.is_file()
                if not self._fallback_file_pending:
                    self._fallback.clear()
                    self._pending_fallback_names.clear()
                return {"migrated": 0, "backend": "keychain", "already_secure": False,
                        "fallback_retained": self.path.is_file()}
            previous: dict[str, str | None] = {}
            written: list[str] = []
            try:
                for name, value in values.items():
                    previous[name] = backend.get_password(SERVICE, name)
                    backend.set_password(SERVICE, name, value)
                    written.append(name)
            except Exception as exc:  # preserve fallback before reporting a backend failure
                for name in written:
                    try:
                        if previous[name] is None:
                            backend.delete_password(SERVICE, name)
                        else:
                            backend.set_password(SERVICE, name, previous[name])
                    except Exception:  # a provider backend may not support rollback; never hide it
                        pass
                raise OSError(f"could not write all saved credentials to the operating-system keychain: {exc}") from exc
            self._keyring = backend
            fallback_retained = False
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                fallback_retained = True
            if not fallback_retained:
                self._fallback.clear()
                self._pending_fallback_names.clear()
                self._fallback_file_pending = False
            return {"migrated": len(values), "backend": "keychain", "already_secure": False,
                    "fallback_retained": fallback_retained,
                    "detail": ("Keychain migration completed, but the old protected fallback file could not be removed. "
                               "Remove it only after confirming the keychain entries work.") if fallback_retained else ""}
