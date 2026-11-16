"""A durable, compact record of every model call's usage.

The Core's InvocationRuntime already emits a bounded trace row per call: role, task, models, outcome,
elapsed time and normalised token usage. It never carries prompts, source text or hidden reasoning.
This writes the useful part of each row to `.librarian/runtime/usage-YYYYMMDD.jsonl`, one short line
per call, so a large ingestion can be audited and capped after the fact. Tokens are recorded, not
dollars: prices change, and `summary()` is what a budget tool prices against the model catalogue.

Logging never breaks a model call: any failure is swallowed.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class UsageLog:
    def __init__(self, vault: Any):
        self.vault = vault
        self._lock = threading.Lock()

    def folder(self) -> Path:
        return self.vault.librarian / "runtime"

    def today_path(self) -> Path:
        return self.folder() / f"usage-{datetime.now(timezone.utc):%Y%m%d}.jsonl"

    @staticmethod
    def _tokens(usage: Any) -> tuple[int | None, int | None]:
        if not isinstance(usage, dict):
            return None, None            # "unavailable": unknown, never counted as zero
        pick = lambda *names: next((usage[n] for n in names if isinstance(usage.get(n), int)), None)
        return pick("prompt_tokens", "input_tokens"), pick("completion_tokens", "output_tokens")

    def record(self, row: dict[str, Any]) -> None:
        try:
            plan = row.get("plan") or {}
            result = row.get("result") or {}
            scope = plan.get("scope") or {}
            tokens_in, tokens_out = self._tokens((result.get("telemetry") or {}).get("usage"))
            line = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "role": scope.get("role", ""), "task": scope.get("task_kind", ""),
                    "host": (plan.get("route") or {}).get("host_id", ""),
                    "model": result.get("observed_model") or result.get("requested_model")
                    or (plan.get("route") or {}).get("requested_model", ""),
                    "outcome": result.get("outcome", ""), "ms": result.get("elapsed_ms"),
                    "in": tokens_in, "out": tokens_out}
            text = json.dumps(line, separators=(",", ":"))
            with self._lock:
                self.folder().mkdir(parents=True, exist_ok=True)
                with open(self.today_path(), "a", encoding="utf-8") as handle:
                    handle.write(text + "\n")
        except Exception:                # noqa: BLE001 - diagnostics never break a model call
            pass

    def summary(self) -> dict[str, dict[str, int]]:
        """Calls and tokens per `role|model` across every day's file."""
        totals: dict[str, dict[str, int]] = {}
        for path in sorted(self.folder().glob("usage-*.jsonl")):
            for text in path.read_text(encoding="utf-8").splitlines():
                try:
                    line = json.loads(text)
                except ValueError:
                    continue
                entry = totals.setdefault(f"{line.get('role', '')}|{line.get('model', '')}",
                                          {"calls": 0, "in": 0, "out": 0, "unknown": 0})
                entry["calls"] += 1
                if line.get("in") is None:
                    entry["unknown"] += 1
                else:
                    entry["in"] += line["in"]; entry["out"] += line.get("out") or 0
        return totals


# -- calls that do not go through the InvocationRuntime (OCR pages, PDF cleanup) --------------

_WRITE = threading.Lock()


def record_call(vault: Any, *, role: str, task: str, model: str = "", host: str = "",
                tokens_in: int | None = None, tokens_out: int | None = None,
                usd: float | None = None, outcome: str = "ok") -> None:
    """One paid call made outside the runtime: its tokens and, when the provider reported it,
    its dollar cost. Same file and line shape as `UsageLog.record`, plus `usd`."""
    try:
        line = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "role": role,
                "task": task, "host": host, "model": model, "outcome": outcome, "ms": None,
                "in": tokens_in, "out": tokens_out}
        if usd is not None:
            line["usd"] = round(float(usd), 6)
        log = UsageLog(vault)
        with _WRITE:
            log.folder().mkdir(parents=True, exist_ok=True)
            with open(log.today_path(), "a", encoding="utf-8") as handle:
                handle.write(json.dumps(line, separators=(",", ":")) + chr(10))
    except Exception:                    # noqa: BLE001 - diagnostics never break a model call
        pass


def spent_usd(vault: Any) -> float:
    """Dollars known to be spent: reported costs, plus unpriced cleanup tokens at the library's
    own `[budget] cleanup_usd_per_mtok_in/out`. Tokens with no price are never guessed."""
    price_in = vault.setting("budget", "cleanup_usd_per_mtok_in")
    price_out = vault.setting("budget", "cleanup_usd_per_mtok_out")
    total = 0.0
    folder = UsageLog(vault).folder()
    for path in sorted(folder.glob("usage-*.jsonl")):
        for text in path.read_text(encoding="utf-8").splitlines():
            try:
                line = json.loads(text)
            except ValueError:
                continue
            if isinstance(line.get("usd"), (int, float)):
                total += line["usd"]
            elif line.get("role") == "cleanup" and isinstance(price_in, (int, float))                     and isinstance(price_out, (int, float)):
                total += (line.get("in") or 0) * price_in / 1e6 + (line.get("out") or 0) * price_out / 1e6
    return total


def budget(vault: Any) -> dict[str, Any]:
    """The library's spend against its optional ceiling (`[budget] ceiling_usd`)."""
    ceiling = vault.setting("budget", "ceiling_usd")
    ceiling = float(ceiling) if isinstance(ceiling, (int, float)) and not isinstance(ceiling, bool) else None
    spent = spent_usd(vault)
    return {"ceiling_usd": ceiling, "spent_usd": spent, "over": ceiling is not None and spent >= ceiling}
