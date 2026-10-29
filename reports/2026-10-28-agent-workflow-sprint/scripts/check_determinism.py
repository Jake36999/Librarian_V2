"""Verification step: re-run the deterministic scripts and compare output hashes; reconcile Codex token sums.

Writes data/determinism_check.json. Scripts that read live logs (claude_log_metrics) are excluded by design.
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, REPORT, sha256_file, write_json  # noqa: E402

SCRIPTS = {
    "git_metrics.py": ["commits.csv", "rework_edges.csv", "git_summary.json"],
    "codex_log_metrics.py": ["codex_threads.csv", "codex_requests.csv", "codex_events.csv", "codex_commits.csv", "codex_delegates.csv"],
    "plan_log_metrics.py": ["plan_growth.csv", "handoff_artifacts.csv"],
    "vast_queue_metrics.py": ["vast_events.csv", "vast_boxes.csv", "vast_summary.json"],
    "benchmark_digest.py": ["benchmark_models.csv", "benchmark_summary.json"],
    "receipt_metrics.py": ["delegations.csv", "ledger_reconciliation.json"],
}


def main() -> int:
    result = {"rerun": {}, "reconciliation": {}}
    for script, outputs in SCRIPTS.items():
        # The session logs and receipts keep growing while other sessions work, so comparing with files written hours ago would flag growth as
        # non-determinism. Run once to refresh the outputs from the current inputs, then run again: the second run must reproduce the first.
        subprocess.run([sys.executable, "-I", str(REPORT / "scripts" / script)], capture_output=True, encoding="utf-8", errors="replace")
        before = {o: sha256_file(DATA / o) for o in outputs}
        run = subprocess.run([sys.executable, "-I", str(REPORT / "scripts" / script)], capture_output=True, encoding="utf-8", errors="replace")
        after = {o: sha256_file(DATA / o) for o in outputs}
        result["rerun"][script] = {"exit": run.returncode, "identical": {o: before[o] == after[o] for o in outputs}}
    # Codex: within each rollout file the per-request sum must equal the counter's own advance (final - offset at the file's first request).
    files = list(csv.DictReader((DATA / "codex_threads.csv").open(encoding="utf-8")))
    exact, off = 0, []
    for t in files:
        if not t["counter_offset"] or int(t["cumulative_total_max"] or 0) == 0:
            continue
        advance = int(t["cumulative_total_max"]) - int(t["counter_offset"])
        if advance == int(t["total_tokens"] or 0):
            exact += 1
        else:
            off.append({"file": t["file"][:48], "kind": t["kind"], "request_sum": int(t["total_tokens"] or 0), "counter_advance": advance})
    # A logical thread (one id) can span several files. A continuation that branches from an earlier point restarts the counter below the
    # previous file's final value; the previous file's requests after the branch point really happened but are not in the later counter.
    by_id: dict[str, list[dict]] = {}
    for t in sorted(files, key=lambda t: t["first_ts"] or ""):
        by_id.setdefault(t["thread"], []).append(t)
    branches = []
    for tid, fs in by_id.items():
        for prev, cur in zip(fs, fs[1:]):
            if cur["counter_offset"] and prev["cumulative_total_max"]:
                gap = int(prev["cumulative_total_max"]) - int(cur["counter_offset"])
                if gap != 0:
                    branches.append({"thread": tid[-8:], "kind": cur["kind"], "previous_file_final": int(prev["cumulative_total_max"]),
                                     "next_file_offset": int(cur["counter_offset"]), "abandoned_branch_tokens": gap})
    result["reconciliation"]["codex_request_sum_vs_counter_advance"] = {
        "rollout_files_checked": exact + len(off), "exact_match": exact, "mismatch": off,
        "continuation_branches": branches, "abandoned_branch_tokens_total": sum(b["abandoned_branch_tokens"] for b in branches),
        "note": "a positive abandoned_branch_tokens means the earlier file kept running after the point where the next file branched: real usage that the later counter omits"}
    commits = list(csv.DictReader((DATA / "commits.csv").open(encoding="utf-8")))
    master = [r for r in commits if r["on_master"] == "True"]
    head = subprocess.run(["git", "-C", str(REPORT.parents[1]), "rev-list", "--count", "master"], capture_output=True, encoding="utf-8").stdout.strip()
    result["reconciliation"]["commit_count"] = {"commits_csv_master": len(master), "git_rev_list_count": int(head)}
    led = json.loads((DATA / "ledger_reconciliation.json").read_text(encoding="utf-8"))
    result["reconciliation"]["ledger_recorded_vs_recomputed"] = {k: [v["recorded_committed_usd"], v["recomputed_sum_charged_usd"]] for k, v in led.items()}
    write_json(DATA / "determinism_check.json", result)
    print(json.dumps(result, indent=1)[:2600])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
