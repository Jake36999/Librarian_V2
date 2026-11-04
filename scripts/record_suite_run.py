"""Run the full test suite and retain the evidence: command, environment, commit,
exit code and complete output (MF-003 evidence records).

    python scripts/record_suite_run.py reports/2026-11-04-evidence/suite-40ec923

writes <stem>.log (the output) and <stem>.json (everything else).
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    stem = ROOT / argv[0]
    stem.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    started = datetime.now(timezone.utc)
    clock = time.monotonic()
    with open(stem.with_suffix(".log"), "w", encoding="utf-8") as log:
        done = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    output = stem.with_suffix(".log").read_text(encoding="utf-8", errors="replace")
    tracked_changes = git("status", "--porcelain", "--untracked-files=no")
    record = {
        "command": command, "cwd": str(ROOT), "exit_code": done.returncode,
        "summary": output.strip().splitlines()[-1] if output.strip() else "",
        "started_utc": started.isoformat(), "seconds": round(time.monotonic() - clock, 1),
        "head": git("rev-parse", "HEAD"), "tracked_changes": tracked_changes.splitlines(),
        "python": sys.version.split()[0], "executable": sys.executable,
        "platform": platform.platform(),
        "log": stem.with_suffix(".log").name,
        "log_sha256": hashlib.sha256(stem.with_suffix(".log").read_bytes()).hexdigest(),
    }
    stem.with_suffix(".json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: record[k] for k in ("exit_code", "summary", "head", "tracked_changes")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
