"""WS3 driver: run planned lane calls through scripts/delegate_deepinfra.py.

- one billable request per call (the runner enforces it); bounded concurrency; resume by call id
- hard sprint cap on LIVE-price cost (rate cards for DeepSeek-V4.1-Flash and GLM-5.3 are stale, see
  data/deepinfra_live_check.json), counting in-flight upper bounds before a call starts
- results appended to tmp/sprint/lanes/results.jsonl: usage, ledger cost, live cost, latency, finish reason
Usage: python sprint_dispatch.py [--only id-prefix,...] [--concurrency 4] [--cap 4.0] [--calls path]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, REPO, TMP, to_iso  # noqa: E402

RUNNER = REPO / "scripts" / "delegate_deepinfra.py"
PY = REPO / ".venv" / "Scripts" / "python.exe"
LEDGER = REPO / "tmp" / "deepinfra-delegation" / "claude-ledger.json"
RESULTS = TMP / "lanes" / "results.jsonl"
LOCK = threading.Lock()
STATE = {"inflight": 0.0}


def live_prices() -> dict:
    data = json.loads((DATA / "deepinfra_live_check.json").read_text(encoding="utf-8"))
    return {m: tuple(v["live_in_out_per_1m"]) for m, v in data["models"].items() if v.get("live_in_out_per_1m")}


def load_results() -> list[dict]:
    if not RESULTS.exists():
        return []
    return [json.loads(l) for l in RESULTS.read_text(encoding="utf-8").splitlines() if l.strip()]


def spent_live(results: list[dict]) -> float:
    return sum(float(r.get("live_cost", 0) or 0) for r in results)


def estimate(call: dict, prices: dict) -> float:
    size = sum((REPO / f).stat().st_size for f in call["files"]) + (REPO / call["instruction_file"]).stat().st_size
    pin, pout = prices[call["model"]]
    return (size / 4.0) * pin / 1e6 + call["max_output_tokens"] * pout / 1e6


def run_call(call: dict, prices: dict, cap: float) -> dict:
    est = estimate(call, prices)
    with LOCK:
        done = load_results()
        if spent_live(done) + STATE["inflight"] + est > cap:
            return {"id": call["id"], "status": "skipped_cap", "estimate_usd": round(est, 4)}
        STATE["inflight"] += est
    started = time.perf_counter()
    cmd = [str(PY), str(RUNNER), "--task", call["id"], "--lens", call["lane"], "--model", call["model"],
           "--instruction-file", str(REPO / call["instruction_file"]), "--max-output-tokens", str(call["max_output_tokens"]),
           "--timeout", str(call["timeout"]), "--ledger", str(LEDGER), "--total-budget-usd", "8.0", "--agent", "claude-sprint",
           "--call-cap-usd", "0.60", "--temperature", "0.1"]
    for f in call["files"]:
        cmd += ["--file", str(REPO / f)]
    row = {"id": call["id"], "lane": call["lane"], "model": call["model"], "files": call["files"], "started": to_iso(datetime.now(timezone.utc))}
    try:
        proc = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=call["timeout"] + 180)
        out = [l for l in proc.stdout.splitlines() if l.strip().startswith("{")]
        if proc.returncode == 0 and out:
            res = json.loads(out[-1])
            usage = res.get("usage", {})
            pin, pout = prices[call["model"]]
            live = usage.get("input_tokens", 0) * pin / 1e6 + usage.get("output_tokens", 0) * pout / 1e6
            receipt = json.loads(open(res["receipt"], encoding="utf-8").read())
            row.update({"status": res.get("status"), "run_id": receipt.get("run_id"), "input_tokens": usage.get("input_tokens"),
                        "output_tokens": usage.get("output_tokens"), "ledger_cost": res.get("cost_usd"), "live_cost": round(live, 6),
                        "latency_s": round(receipt.get("latency_ms", 0) / 1000, 1), "finish_reason": receipt.get("finish_reason"),
                        "truncated": bool(receipt.get("truncated")), "output": res.get("output"), "receipt": res.get("receipt"),
                        "max_output_tokens": call["max_output_tokens"]})
        else:
            row.update({"status": "failed", "returncode": proc.returncode, "error": (proc.stderr or proc.stdout)[-300:],
                        "live_cost": round(est * 0.0, 6), "wall_s": round(time.perf_counter() - started, 1)})
    except subprocess.TimeoutExpired:
        row.update({"status": "failed", "error": "driver timeout", "wall_s": round(time.perf_counter() - started, 1), "live_cost": 0})
    finally:
        with LOCK:
            STATE["inflight"] -= est
            with RESULTS.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--cap", type=float, default=4.0)
    ap.add_argument("--calls", default=str(TMP / "lanes" / "calls.json"))
    args = ap.parse_args()
    calls = json.loads(open(args.calls, encoding="utf-8").read())
    only = [s for s in args.only.split(",") if s]
    if only:
        calls = [c for c in calls if any(c["id"].startswith(p) for p in only)]
    prices = live_prices()
    finished = {r["id"] for r in load_results() if r.get("status") == "completed"}
    todo = [c for c in calls if c["id"] not in finished]
    print(f"planned={len(calls)} already_done={len(calls) - len(todo)} to_run={len(todo)} spent_live=${spent_live(load_results()):.4f} cap=${args.cap}", flush=True)
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for row in pool.map(lambda c: run_call(c, prices, args.cap), todo):
            print(f"{row['id']:42} {row.get('status'):10} in={row.get('input_tokens')} out={row.get('output_tokens')} live=${row.get('live_cost')} "
                  f"{row.get('latency_s', row.get('wall_s'))}s finish={row.get('finish_reason')} {row.get('error', '')[:120]}", flush=True)
    print(f"spent_live=${spent_live(load_results()):.4f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
