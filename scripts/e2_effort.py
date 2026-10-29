#!/usr/bin/env python
"""Measure a lead agent's effort for one E2' arm from Claude Code session logs.

Effort is read from the logs the client already writes; nothing is
self-reported. One API response is split over several log lines that repeat
its usage, so assistant records are counted once per message id. A session's
subagent logs (any *.jsonl under the session's folder) spend the same quota
and are included.

Usage: e2_effort.py --session ID [--session ID ...] [--projects DIR]
                    [--ledger PATH --task-id ID] [--gap-minutes 5] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


PROJECTS = Path.home() / ".claude" / "projects"
COMPONENTS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
              "output_tokens")
# Metric M1's weighted index: the client's own Opus 5.5 list prices, relative to
# ordinary input ($4.98, $7.98, $0.20 and $19.66 per million tokens).
WEIGHTS = {"input_tokens": 1.0, "cache_creation_input_tokens": 1.60,
           "cache_read_input_tokens": 0.04, "output_tokens": 3.94}
INPUT_USD_PER_TOKEN = 4.98 / 1_000_000


def session_files(session_id: str, projects: Path) -> list[Path]:
    """The session's main log and every log under its folder, in any project."""
    files = sorted(projects.glob(f"*/{session_id}.jsonl"))
    for folder in projects.glob(f"*/{session_id}"):
        if folder.is_dir():
            files += sorted(folder.rglob("*.jsonl"))
    if not files:
        raise SystemExit(f"no logs found for session {session_id} under {projects}")
    return files


def _records(files: Iterable[Path]) -> Iterable[dict[str, Any]]:
    for path in files:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue  # a line cut off by a crash is not usage
                if isinstance(record, dict):
                    yield record


def _time(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def measure(files: Iterable[Path], *, gap_minutes: float = 5.0) -> dict[str, Any]:
    """Tokens by component, the weighted index, requests and active time."""
    seen: set[str] = set()
    totals = dict.fromkeys(COMPONENTS, 0)
    models: set[str] = set()
    times: list[datetime] = []
    for record in _records(files):
        stamp = _time(record.get("timestamp", ""))
        if stamp and record.get("type") in ("user", "assistant"):
            times.append(stamp)
        message = record.get("message")
        if record.get("type") != "assistant" or not isinstance(message, dict):
            continue
        message_id = message.get("id")
        usage = message.get("usage")
        if not message_id or message_id in seen or not isinstance(usage, dict):
            continue
        if message.get("model") == "<synthetic>":
            continue  # written by the client itself, not an API request
        seen.add(message_id)
        if message.get("model"):
            models.add(message["model"])
        for key in COMPONENTS:
            totals[key] += int(usage.get(key) or 0)
    times.sort()
    gap = gap_minutes * 60
    active = sum(d for d in ((b - a).total_seconds() for a, b in zip(times, times[1:]))
                 if d <= gap)
    weighted = sum(totals[k] * WEIGHTS[k] for k in COMPONENTS)
    return {
        "requests": len(seen),
        "tokens": totals,
        "weighted_index": round(weighted),
        "shadow_usd": round(weighted * INPUT_USD_PER_TOKEN, 4),
        "active_minutes": round(active / 60, 1),
        "wall_minutes": round((times[-1] - times[0]).total_seconds() / 60, 1) if times else 0.0,
        "models": sorted(models),
    }


def delegate_usd(ledger_path: Path, task_id: str) -> dict[str, Any]:
    """DeepInfra spend recorded against one task id in the pooled ledger."""
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    calls = [c for c in ledger.get("calls", []) if c.get("task_id") == task_id]
    return {"calls": len(calls),
            "usd": round(sum(float(c.get("charged_usd", 0)) for c in calls), 6),
            "open_runs": [c["run_id"] for c in calls
                          if c.get("status") in ("started", "uncertain")]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--session", action="append", required=True,
                        help="Claude Code session id; repeat for an arm resumed in a new session")
    parser.add_argument("--projects", type=Path, default=PROJECTS)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--task-id")
    parser.add_argument("--gap-minutes", type=float, default=5.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if bool(args.ledger) != bool(args.task_id):
        raise SystemExit("--ledger and --task-id go together")

    files = [f for s in args.session for f in session_files(s, args.projects)]
    result = {"sessions": args.session, "files": len(files),
              **measure(files, gap_minutes=args.gap_minutes)}
    if args.ledger:
        result["delegate"] = delegate_usd(args.ledger, args.task_id)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for key, value in result.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
