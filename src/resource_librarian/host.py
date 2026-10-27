"""Explicit, per-user Librarian Host lifecycle management.

This is deliberately a small desktop-process companion, not a Windows
service: a person starts/stops a Core, sees its state, and can restart it.
There is no browser-tab reference counting and no idle reaper.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

from .coordination import atomic_write_text
from . import connection, process_identity
from .keys import config_dir


# Core shutdown can spend five seconds waiting for admitted work and another
# ten draining its writer, plus watcher/MCP/server teardown. The Host must
# wait beyond that complete bound, rather than racing the Core at exactly
# fifteen seconds and reporting it as still alive just before process exit.
STOP_EXIT_SECONDS = 25.0


def _path() -> Path:
    return config_dir() / "host.json"


def _load() -> dict[str, Any]:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data: dict[str, Any]) -> None:
    atomic_write_text(_path(), json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _log_path() -> Path:
    folder = config_dir() / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"core-{int(time.time() * 1000)}.log"


def _log_tail(path: Path, limit: int = 2_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-limit:]
    except OSError:
        return ""


def _startup_record(path: Path) -> dict[str, Any] | None:
    """Read the Core's one JSON startup line from its private log.

    Pipes left attached after launch can fill with later diagnostics and stall
    a healthy server.  A normal user-owned log avoids that failure mode while
    retaining visible crash diagnostics in Host Status.
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("listening"):
            return row
    return None


def _alive(pid: int, start: Any = None) -> bool:
    """Whether the process a record names is still the one that wrote it.

    Never ``os.kill(pid, 0)``: on Windows it reports an exited Core as alive
    while any handle to it is open, so Stop waited out its whole window.
    """
    return process_identity.is_alive(pid, start)


def _shutdown_phases(vault: str) -> list[dict[str, Any]]:
    """The phases a stopped Core recorded (CORE-02A), so the tray can say
    what happened rather than a generic "still draining"."""
    try:
        row = json.loads(connection.shutdown_path(vault).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    phases = row.get("phases") if isinstance(row, dict) else None
    return [p for p in phases if isinstance(p, dict)] if isinstance(phases, list) else []


class HostManager:
    @staticmethod
    def _same_vault(left: str, right: str) -> bool:
        try:
            a, b = str(Path(left).resolve()), str(Path(right).resolve())
        except OSError:
            return False
        return a.casefold() == b.casefold() if os.name == "nt" else a == b

    @staticmethod
    def _public_process(row: dict[str, Any], *, managed_by_host: bool) -> dict[str, Any]:
        """Status is safe to show in a tray or CLI: connection tokens never
        leave the private record used below for the authenticated request."""
        out = {key: row[key] for key in ("pid", "vault", "url", "started_at", "status", "log",
                                          "secret_source") if row.get(key) not in (None, "")}
        out["managed_by_host"] = managed_by_host
        return out

    def _discovered(self) -> list[dict[str, Any]]:
        return [row for row in connection.records()
                if _alive(int(row.get("pid") or 0), row.get("process_start"))]

    def status(self) -> dict[str, Any]:
        data = _load()
        pid = int(data.get("pid") or 0)
        active = _alive(pid, data.get("process_start"))
        if data and not active:
            data = {**data, "status": "stopped", "detail": "process is no longer running"}
            _save(data)
        discovered = self._discovered()
        cores: list[dict[str, Any]] = []
        seen: set[tuple[int, str]] = set()
        for row in discovered:
            marker = (int(row["pid"]), str(row["vault"]))
            seen.add(marker)
            cores.append(self._public_process(
                row, managed_by_host=bool(data and int(data.get("pid") or 0) == marker[0]
                                           and self._same_vault(str(data.get("vault") or ""), marker[1]))))
        # A just-started Core may not yet have published its optional private
        # discovery record. Keep its Host record visible, but never fabricate
        # a token for it.
        if active and (pid, str(data.get("vault") or "")) not in seen:
            cores.append(self._public_process(data, managed_by_host=True))
        return {"status": "running" if cores else "stopped",
                "process": self._public_process(data, managed_by_host=True) if data else None,
                "cores": cores,
                "commands": ["Open", "Status", "Doctor", "Restart", "Stop", "Quit"]}

    def _target(self, vault: str = "") -> tuple[dict[str, Any], dict[str, Any] | None] | None:
        """Choose one explicit live Core.  When several adapter-owned Cores
        are running the caller must name its vault; guessing would make Stop
        a destructive surprise."""
        data = _load()
        wanted = str(Path(vault).resolve()) if vault else ""
        if wanted:
            host_row = data if self._same_vault(str(data.get("vault") or ""), wanted) else {}
            record = connection.load(wanted)
            if record is not None and _alive(int(record.get("pid") or 0), record.get("process_start")):
                return (host_row, record)
            if host_row and _alive(int(host_row.get("pid") or 0), host_row.get("process_start")):
                return (host_row, None)
            return None
        if data and _alive(int(data.get("pid") or 0), data.get("process_start")):
            return (data, connection.load(str(data.get("vault") or "")))
        candidates = self._discovered()
        if len(candidates) == 1:
            return ({}, candidates[0])
        return None

    def start(self, vault: str, *, open_browser: bool = False) -> dict[str, Any]:
        vault_path = str(Path(vault).resolve())
        active_here = connection.load(vault_path)
        if active_here is not None and _alive(int(active_here.get("pid") or 0),
                                              active_here.get("process_start")):
            return {"started": False, "status": "running",
                    "process": self._public_process(active_here, managed_by_host=False),
                    "detail": "a compatible Core is already running for this vault"}
        current = _load()
        if current and self._same_vault(str(current.get("vault") or ""), vault_path) and \
                _alive(int(current.get("pid") or 0), current.get("process_start")):
            # Discovery can fail closed if a profile ACL cannot be protected.
            # The Host's own record still proves that starting a second Core
            # for this *same* vault is unsafe.
            return {"started": False, "status": "running",
                    "process": self._public_process(current, managed_by_host=True),
                    "detail": "the Host already has a running Core for this vault"}
        # A Host may manage Cores for distinct vaults at once.  Their vault
        # coordinators remain independent; each Core publishes its own
        # private attachment record, which is what status/stop uses below.
        args = [sys.executable, "-m", "resource_librarian", "--vault", vault_path,
                "app", "--port", "0"]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        log = _log_path()
        environment = dict(os.environ)
        # The Host owns the child process.  This flag enables the one
        # authenticated, graceful lifecycle endpoint; it does not create a
        # service, ref-counting, or automatic shutdown behaviour.
        environment["LIBRARIAN_HOST_MANAGED"] = "1"
        environment.pop("LIBRARIAN_EXIT_WITH_STDIN", None)
        with log.open("w", encoding="utf-8", newline="") as output:
            process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=output,
                                       stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                       creationflags=flags, env=environment)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            started = _startup_record(log)
            if started is not None:
                # The private record is written before the startup line.  In
                # normal Windows launches its PID matches Popen's PID; using
                # the Core's own record when available also handles a Python
                # launcher/wrapper without leaving the Host monitoring the
                # wrong process.
                record = connection.load(vault_path)
                published_url = str(started["listening"]).rstrip("/")
                own_record = record is not None and \
                    str(record.get("url") or "").rstrip("/") == published_url
                core_pid = int(record.get("pid") or 0) if own_record else process.pid
                data = {"pid": core_pid, "vault": vault_path,
                        "url": str(started["listening"]), "started_at": time.time(),
                        "status": "running", "log": str(log)}
                if own_record and record.get("process_start") is not None:
                    data["process_start"] = record["process_start"]
                _save(data)
                if open_browser:
                    webbrowser.open(data["url"])
                return {"started": True, "status": "running", "process": data}
            if process.poll() is not None:
                raise RuntimeError(f"Core exited ({process.returncode}): {_log_tail(log, 500)}")
            time.sleep(.1)
        # Startup has no hidden retry loop.  Termination only happens for the
        # child this call just launched, and its log remains available.
        process.terminate()
        raise RuntimeError(f"Core did not report its dynamic port within 20 seconds: {_log_tail(log, 500)}")

    def stop(self, vault: str = "", *, force: bool = False) -> dict[str, Any]:
        target = self._target(vault)
        if target is None:
            if not vault and len(self._discovered()) > 1:
                return {"stopped": False, "detail": "more than one Core is running; choose a vault to stop"}
            return {"stopped": False, "detail": "no running Host Core"}
        data, record = target
        chosen_vault = str((record or data).get("vault") or "")
        pid = int((record or data).get("pid") or 0)
        started = (record or data).get("process_start")
        if record is None or int(record.get("pid") or 0) != pid:
            return {"stopped": False, "detail": "the protected Core connection record is unavailable; "
                    "refusing an ungraceful kill", "log": data.get("log", "")}
        request = urllib.request.Request(
            str(record["url"]).rstrip("/") + "/api/host/stop",
            data=json.dumps({"force": bool(force)}).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json",
                     "X-Librarian-Token": str(record["token"]),
                     "Origin": str(record["url"]).rstrip("/")})
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                reply = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                detail = {"error": str(exc)}
            if exc.code == 409:
                return {"stopped": False, "detail": detail.get("error", "Core has active work"),
                        "active": detail.get("active", {}), "checkpoint": detail.get("checkpoint", "")}
            raise RuntimeError(str(detail.get("error") or exc)) from exc
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"could not ask the Core to stop cleanly: {exc}") from exc
        deadline = time.monotonic() + STOP_EXIT_SECONDS
        while _alive(pid, started) and time.monotonic() < deadline:
            time.sleep(.1)
        if _alive(pid, started):
            return {"stopped": False, "detail": "Core accepted stop but is still draining work",
                    "pid": pid, "reply": reply}
        if data:
            _save({**data, "status": "stopped", "stopped_at": time.time()})
        connection.remove(chosen_vault, pid=pid, token=str(record.get("token") or ""))
        return {"stopped": True, "pid": pid, "reply": reply, "phases": _shutdown_phases(chosen_vault)}

    def restart(self, vault: str = "", *, open_browser: bool = False) -> dict[str, Any]:
        before = _load()
        target = self._target(vault)
        if target is not None:
            chosen = vault or str((target[1] or target[0]).get("vault") or "")
        else:
            chosen = vault or str(before.get("vault") or "")
        if not chosen:
            raise ValueError("a vault path is required for the first Host start")
        if target is not None:
            record = target[1]
            if record is not None and record.get("secret_source") == "obsidian":
                return {"started": False, "status": "running",
                        "detail": "this Core uses Obsidian SecretStorage; restart it from the Librarian Obsidian settings"}
            stopped = self.stop(chosen)
            if not stopped.get("stopped"):
                return {"started": False, "status": "running", "detail": stopped.get("detail", ""),
                        "active": stopped.get("active", {})}
        return self.start(chosen, open_browser=open_browser)

