"""1h: per-model digest of the 2026-09-29 DeepInfra reliability benchmark (read-only input).

Input:  D:\\Resource-Library\\10-Models\\DeepInfra Reliability Benchmark 2026-09-29\\model_results.csv
Output: data/benchmark_models.csv, data/benchmark_summary.json
The benchmark ran four agentic probes per model against the v1 library tools; it is dated
and its roster differs from the runner's, so it gives priors on failure types, not current rates.
"""
from __future__ import annotations

import csv
import os
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, write_csv, write_json  # noqa: E402

SRC = Path(r"D:\Resource-Library\10-Models\DeepInfra Reliability Benchmark 2026-09-29")
INTEREST = ("MiMo", "GLM", "DeepSeek", "Qwen3", "gpt-oss", "Kimi", "Llama-4")


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main() -> int:
    rows = list(csv.DictReader((SRC / "model_results.csv").open(encoding="utf-8")))
    by = defaultdict(list)
    for r in rows:
        by[r["model"]].append(r)
    out = []
    for model, rs in sorted(by.items()):
        lat = [num(r["latency_seconds"]) for r in rs if num(r["latency_seconds"]) is not None]
        cost = sum(num(r["cost_usd"]) or 0 for r in rs)
        status = Counter(r["status"] for r in rs)
        errs = Counter((r["error"] or "")[:40] for r in rs if r["status"] != "pass")
        out.append({
            "model": model, "probes": len(rs), "pass": status.get("pass", 0), "pass_rate": round(status.get("pass", 0) / len(rs), 2),
            "median_latency_s": round(st.median(lat), 1) if lat else "", "max_latency_s": round(max(lat), 1) if lat else "",
            "cost_usd": round(cost, 4), "statuses": ";".join(f"{k}={v}" for k, v in sorted(status.items())),
            "top_errors": ";".join(f"{k}x{v}" for k, v in errs.most_common(2)), "in_per_1m": rs[0]["input_per_1m"], "out_per_1m": rs[0]["output_per_1m"],
            "of_interest": any(k in model for k in INTEREST),
        })
    write_csv(DATA / "benchmark_models.csv", out)
    allstatus = Counter(r["status"] for r in rows)
    probe = defaultdict(Counter)
    for r in rows:
        probe[r["probe"]][r["status"]] += 1
    pass_rates = [o["pass_rate"] for o in out]
    write_json(DATA / "benchmark_summary.json", {
        "models": len(out), "probe_rows": len(rows), "status_counts": dict(allstatus),
        "per_probe_status": {k: dict(v) for k, v in probe.items()},
        "models_all_pass": sum(1 for o in out if o["pass_rate"] == 1.0), "models_none_pass": sum(1 for o in out if o["pass_rate"] == 0.0),
        "median_model_pass_rate": st.median(pass_rates),
    })
    print(f"models={len(out)} rows={len(rows)} statuses={dict(allstatus)} all_pass={sum(1 for o in out if o['pass_rate']==1.0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
