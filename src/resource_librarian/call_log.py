"""A durable, compact record of every call an outside surface makes into the Core.

The usage log (usage_log.py) records each model call the Core makes. Nothing recorded the calls made
*into* the Core: how many a tier-0 agent spent, how much came back to it, and how many were refused.
On 19-20 November a tier-0 run drove the Core from scripts, so its own transcript showed a handful
of turns for dozens of calls; the implementation plan's baselines (M0) need the count from the Core's
side. One short line per call goes to `.librarian/runtime/calls-YYYYMMDD.jsonl`: the surface, the
declared agent, the tool, the session, the outcome, the time taken and the size of the result. It never
carries arguments or result content.

Logging never breaks a call: any failure is swallowed.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# A rough size of what a result costs the caller to read, for comparing runs; not a tokenizer.
CHARS_PER_TOKEN = 4


def outcome_of(result: Any) -> str:
    """`ok`, a refusal code, or the registry's error kind (invalid_arguments, failed)."""
    if not isinstance(result, dict):
        return "ok"
    if result.get("refused"):
        return str(result["refused"])
    if result.get("error"):
        return str(result["error"])
    return "ok"


class CallLog:
    def __init__(self, vault: Any):
        self.vault = vault
        self._lock = threading.Lock()

    def folder(self) -> Path:
        return self.vault.librarian / "runtime"

    def today_path(self) -> Path:
        return self.folder() / f"calls-{datetime.now(timezone.utc):%Y%m%d}.jsonl"

    def record(self, *, surface: str, tool: str, started: float, result: Any,
               session: str = "", agent: str = "") -> None:
        try:
            size = len(json.dumps(result, default=str, separators=(",", ":")))
            line = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "surface": surface, "tool": tool, "outcome": outcome_of(result),
                    "ms": int((time.monotonic() - started) * 1000), "bytes": size}
            if session:
                line["session"] = session
            if agent:
                line["agent"] = agent[:80]
            text = json.dumps(line, separators=(",", ":"))
            with self._lock:
                self.folder().mkdir(parents=True, exist_ok=True)
                with open(self.today_path(), "a", encoding="utf-8") as handle:
                    handle.write(text + "\n")
        except Exception:                # noqa: BLE001 - diagnostics never break a call
            pass

    def summary(self, since: str = "") -> dict[str, dict[str, int]]:
        """Calls, refusals and result size per surface (and declared agent), from `since` (an ISO
        date or time) on."""
        totals: dict[str, dict[str, int]] = {}
        for path in sorted(self.folder().glob("calls-*.jsonl")):
            for text in path.read_text(encoding="utf-8").splitlines():
                try:
                    line = json.loads(text)
                except ValueError:
                    continue
                if since and str(line.get("ts", "")) < since:
                    continue
                key = line.get("surface", "") + (f"|{line['agent']}" if line.get("agent") else "")
                entry = totals.setdefault(key, {"calls": 0, "refused": 0, "result_tokens": 0, "ms": 0})
                entry["calls"] += 1
                if line.get("outcome", "ok") != "ok":
                    entry["refused"] += 1
                entry["result_tokens"] += int(line.get("bytes") or 0) // CHARS_PER_TOKEN
                entry["ms"] += int(line.get("ms") or 0)
        return totals
