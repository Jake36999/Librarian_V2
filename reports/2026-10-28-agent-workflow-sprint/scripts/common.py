"""Shared helpers for the sprint measurement scripts (standard library only).

Run the scripts with `python -I`; each one adds this folder to sys.path itself
because isolated mode does not.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"D:\Librarian_V2")
REPORT = REPO / "reports" / "2026-10-28-agent-workflow-sprint"
DATA = REPORT / "data"
TMP = REPO / "tmp" / "sprint"
HOME = Path(os.path.expanduser("~"))
CLAUDE_PROJECTS = HOME / ".claude" / "projects"
CODEX_SESSIONS = HOME / ".codex" / "sessions"

# `git commit` prints "[branch abc1234] subject" (also "[master (root-commit) abc1234]").
COMMIT_OUT = re.compile(r"\[[^\]\n]{1,80}? ([0-9a-f]{7,40})\]")
LIMIT_WORDS = re.compile(r"usage limit|hit my (usage )?limit|limit (has )?reset|reset now", re.I)


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def epoch_iso(value) -> str:
    return to_iso(datetime.fromtimestamp(float(value), tz=timezone.utc))


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git(*args: str, cwd: Path = REPO) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, encoding="utf-8", errors="replace", check=True,
    ).stdout


HEX = re.compile(r"\b[0-9a-f]{7,40}\b")
_KNOWN: dict | None = None


def known_commits() -> dict:
    """short7 -> (full hash, committer time) for every commit on any branch."""
    global _KNOWN
    if _KNOWN is None:
        _KNOWN = {}
        for line in git("log", "--all", "--format=%H %cI").splitlines():
            full, when = line.split(" ", 1)
            _KNOWN[full[:7]] = (full, parse_ts(when))
    return _KNOWN


def find_commits(text: str, ts_iso: str | None, window_s: int = 900) -> list[str]:
    """Every real commit named in a command's output that was created shortly before it.

    `git commit -q` prints no "[branch hash]" line, so any hex token that is a known
    commit (for example from a trailing `git log --oneline`) is accepted, then
    constrained to commits made at most `window_s` before the result (and at most 5 s
    after, for clock skew) so an old HEAD listed after a failed commit is not joined.
    """
    known = known_commits()
    ref = parse_ts(ts_iso) if ts_iso else None
    found = []
    for tok in HEX.findall(text):
        item = known.get(tok[:7])
        if not item or item[0] in found:
            continue
        full, when = item
        if ref is not None:
            lag = (ref - when).total_seconds()
            if lag < -5 or lag > window_s:
                continue
        found.append(full)
    return found


# A delegation is a command that EXECUTES the runner: an interpreter whose program argument is the
# script. Reading, searching, editing, diffing or testing the script is inspection, not delegation.
_INTERP = r"(?:[^\s;|&'\"`()]*[\\/])?(?:python[0-9.]*|py)(?:\.exe)?"
_ENV = r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
_WRAP = r"(?:(?:timeout\s+\d+[smh]?|nohup|time|env|command|exec)\s+)*"
# Runners: the repository's scripts/delegate_deepinfra.py and the two scratchpad scripts Claude wrote
# on 2026-10-24 (second_reader.py, then delegate.py). The product module tools/delegate.py is never run as a script.
_RUNNER = re.compile(r"(?:^|[;&|(\n]|\bthen\b|\bdo\b)\s*&?\s*" + _ENV + _WRAP + _ENV + r"['\"]?" + _INTERP
                     + r"['\"]?\s+(?:-[A-Za-z]+\s+)*['\"]?(?:[^\s'\"]*[\\/])?(?P<runner>delegate_deepinfra|delegate|second_reader)\.py['\"]?", re.I)
_KIND_RANK = {"launch": 4, "dry_run": 3, "help": 2, "other_runner": 1}


def delegate_launches(cmd: str) -> list[dict]:
    """Structural invocations of the DeepInfra runner in a shell command (one dict per invocation)."""
    found = []
    matches = list(_RUNNER.finditer(cmd))
    for i, m in enumerate(matches):
        args = cmd[m.end():matches[i + 1].start() if i + 1 < len(matches) else len(cmd)]
        flags = set(re.findall(r"(?<![\w-])(--[a-z][a-z0-9-]*)", args))
        if "--help" in flags or re.match(r"\s+-h(?![\w-])", args):
            kind = "help"
        elif "--dry-run" in flags:
            kind = "dry_run"
        elif flags & {"--task", "--instruction", "--instruction-file", "--out", "--prompt-file"}:
            kind = "launch"
        else:
            kind = "other_runner"
        task = re.search(r"--task[ =]+['\"]?([^\s'\"]+)", args)
        model = re.search(r"--model[ =]+['\"]?([^\s'\"]+)", args)
        out = re.search(r"--out[ =]+['\"]?([^\s'\"]+)", args)
        found.append({"kind": kind, "runner": m.group("runner").lower(), "task": task.group(1) if task else "",
                      "model": model.group(1) if model else "", "out": out.group(1) if out else ""})
    return found


def delegate_kind(cmd: str) -> str:
    """'launch' | 'dry_run' | 'help' | 'other_runner' | 'inspect' (mentions the runner or API only) | ''."""
    runs = delegate_launches(cmd)
    if runs:
        return max((r["kind"] for r in runs), key=lambda k: _KIND_RANK[k])
    low = cmd.lower()
    if "delegate_deepinfra" in low or "api.deepinfra.com" in low:
        return "inspect"
    return ""


def command_category(cmd: str) -> str:
    """Rule-based class of a shell command; used for both Claude and Codex logs."""
    c = cmd.strip()
    low = c.lower()
    if re.search(r"\bgit\b[^;&|\n]{0,80}?\bcommit\b(?!-tree|-graph)", low):
        return "commit"
    if delegate_kind(c) == "launch":
        return "delegate"
    if re.search(r"\bpytest\b|py\.test|-m\s+unittest", low):
        return "test"
    if "apply_patch" in low:
        return "edit"
    if re.search(r"\bsleep\b|start-sleep|tail\s+-f|-wait\b", low):
        return "poll"
    if re.search(r"\bgit\s+(status|log|diff|show|blame|branch|rev-parse|ls-files|stash|add|checkout|merge|rebase)\b", low):
        return "git"
    if re.search(r"(^|[;&|]\s*|\bawait\s+)(cat|head|tail|sed|ls|find|rg|grep|wc|get-content|select-string|get-childitem|type|dir|awk|jq)\b", low):
        return "read"
    if re.search(r"\b(python|python3|node|npm|pwsh|powershell|uv|pip|cargo|cmake)\b|\.exe\b|\.ps1\b|\.bat\b", low):
        return "run"
    return "other"


CATEGORY_PRIORITY = ["commit", "delegate", "test", "edit", "run", "poll", "git", "read",
                     "web", "subagent", "mcp", "plan", "toolsearch", "other", "text"]


def top_category(categories: list[str]) -> str:
    if not categories:
        return "text"
    for name in CATEGORY_PRIORITY:
        if name in categories:
            return name
    return categories[0]
