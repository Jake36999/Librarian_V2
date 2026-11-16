"""A library's own Geo-Grapher, run by that library's Core (owner, 2026-11-15).

Geo-Grapher follows the Librarian deployment pattern: one library, one Core, one
Geo service. The Core starts the pinned wheel's `serve-graphs` for this library's
catalog (`.librarian/geographer/catalog.sqlite`) when the library starts, and stops
it when the library closes or the Core switches away.

- The port is chosen by the service (`--port 0`) and read back from a ready file.
- A per-library token travels in the child's environment, never in argv, and is
  never returned by `status()`. Only `open_url()`, served to the authenticated
  person UI, carries it, as a one-time query the service swaps for a cookie.
- A missing or disabled configuration starts nothing; an older wheel without
  service support is reported with its fix, not retried.

The service is supervised in a background thread, so a slow start never delays
the Core's own startup.
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from . import process_identity
from .folder_review import configuration

READY_TIMEOUT = 60.0
STOP_TIMEOUT = 10.0


class GeoService:
    def __init__(self, vault: Any, *, ready_timeout: float = READY_TIMEOUT):
        self.vault = vault
        self.ready_timeout = ready_timeout
        self.token = ""
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._info: dict[str, Any] | None = None
        self._listener_start: str | None = None       # the listener's start identity, captured when it reported ready
        self._state = "stopped"
        self._error = ""
        self._stopping = threading.Event()

    # -- paths ------------------------------------------------------------
    @property
    def catalog(self) -> Path:
        return self.vault.librarian / "geographer" / "catalog.sqlite"

    @property
    def _runtime(self) -> Path:
        path = self.vault.librarian / "runtime"
        path.mkdir(parents=True, exist_ok=True)
        return path

    # -- lifecycle --------------------------------------------------------
    def start(self, librarian_url: str) -> None:
        """Start this library's service in the background; idempotent while it runs."""
        config = configuration(self.vault)
        command = config.get("command")
        with self._lock:
            if self._state in {"starting", "running"}:
                return
            if not config.get("enabled"):
                self._state, self._error = "disabled", ""
                return
            if (not isinstance(command, list) or not command
                    or not all(isinstance(s, str) and s for s in command)):
                self._state, self._error = "failed", "GEOGRAPHER_CONFIGURATION: no pinned command"
                return
            self._state, self._error, self._info = "starting", "", None
            self._stopping.clear()
            self.token = secrets.token_urlsafe(32)
        threading.Thread(target=self._run, args=(list(command), librarian_url),
                         name=f"geo-service-{self.vault.root.name}", daemon=True).start()

    def _run(self, command: list[str], librarian_url: str) -> None:
        ready = self._runtime / "geographer-ready.json"
        ready.unlink(missing_ok=True)
        log = (self.vault.librarian / "logs")
        log.mkdir(parents=True, exist_ok=True)
        argv = [*command, "serve-graphs", "--catalog", str(self.catalog), "--create-catalog",
                "--transport", "http", "--port", "0", "--ready-file", str(ready),
                "--librarian-url", librarian_url, "--library-name", self.vault.title,
                "--parent-pid", str(os.getpid())]
        env = {**os.environ, "GEOGRAPHER_ACCESS_TOKEN": self.token, "PYTHONUTF8": "1"}
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        try:
            with open(log / "geographer.log", "ab") as out:
                proc = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=out,
                                        stderr=out, creationflags=flags)
        except OSError as exc:
            self._fail(f"GEOGRAPHER_START_FAILED: {exc.__class__.__name__}")
            return
        with self._lock:
            self._proc = proc
        deadline = time.monotonic() + self.ready_timeout
        while not self._stopping.is_set():
            if ready.is_file():
                try:
                    info = json.loads(ready.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    info = None
                if isinstance(info, dict) and isinstance(info.get("port"), int):
                    with self._lock:
                        self._info, self._state = info, "running"
                        self._listener_start = process_identity.process_start(info["pid"]) if isinstance(info.get("pid"), int) else None
                    return
            code = proc.poll()
            if code is not None:
                self._fail("GEOGRAPHER_TOO_OLD: this wheel cannot run as a library service; rebuild "
                           "and reinstall the pinned Geo-Grapher wheel" if code == 2 else
                           f"GEOGRAPHER_EXITED: code {code}; see .librarian/logs/geographer.log")
                return
            if time.monotonic() > deadline:
                self._terminate()
                self._fail("GEOGRAPHER_NOT_READY: no ready file within the start timeout; "
                           "see .librarian/logs/geographer.log")
                return
            time.sleep(0.1)

    def _fail(self, error: str) -> None:
        with self._lock:
            self._state, self._error, self._info = "failed", error, None

    def stop(self) -> None:
        """Stop this library's service and its real listener (which a Windows venv
        launcher starts as a child, so both pids are ended)."""
        self._stopping.set()
        self._terminate()
        with self._lock:
            self._state, self._info, self.token, self._listener_start = "stopped", None, "", None
        (self._runtime / "geographer-ready.json").unlink(missing_ok=True)

    def _terminate(self) -> None:
        with self._lock:
            proc, info = self._proc, self._info
            self._proc = None
        # Only a process this session started is ever ended. The listener is the pid this
        # session read from the ready file after launching, and it must still be the same
        # process (start identity), so a stale file or a reused pid never reaches an
        # unrelated program.
        listener = None
        if isinstance(info, dict) and isinstance(info.get("pid"), int):
            if self._listener_start and process_identity.is_alive(info["pid"], self._listener_start):
                listener = info["pid"]
        elif proc is not None:                    # launched, but not yet ready: the file is ours
            pid = _ready_pid(self._runtime / "geographer-ready.json")   # (cleared before launch)
            if pid is not None and process_identity.is_alive(pid):
                listener = pid
        if listener is not None and (proc is None or listener != proc.pid):
            _end(listener)
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=STOP_TIMEOUT)
            except subprocess.TimeoutExpired:
                proc.kill()

    # -- views ------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        with self._lock:
            return {"state": self._state, "error": self._error,
                    "url": self._info.get("url") if self._info else None,
                    "library": self.vault.title}

    def open_url(self) -> str | None:
        """The one-time browser entry for the authenticated person UI only."""
        with self._lock:
            if self._state != "running" or not self._info:
                return None
            return f"{self._info['url']}?geo_token={self.token}"


def _ready_pid(path: Path) -> int | None:
    try:
        pid = json.loads(path.read_text(encoding="utf-8")).get("pid")
    except (OSError, ValueError, AttributeError):
        return None
    return pid if isinstance(pid, int) else None


def _end(pid: int) -> None:
    import signal
    try:
        os.kill(pid, signal.SIGTERM)          # TerminateProcess on Windows
    except OSError:
        pass
