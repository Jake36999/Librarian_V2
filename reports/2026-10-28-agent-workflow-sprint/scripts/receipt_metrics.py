"""1b: per-call table from the DeepInfra delegation receipts and ledgers, plus ledger reconciliation.

Outputs: data/delegations.csv, data/ledger_reconciliation.json
Costs are rate-card estimates written by the runner, not invoices; a failed call is
charged at its preflight reserve (see scripts/delegate_deepinfra.py settle_call).
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, REPO, parse_ts, to_iso, write_csv, write_json  # noqa: E402

BASE = REPO / "tmp" / "deepinfra-delegation"
LEDGERS = {"shared": BASE / "ledger.json", "claude": BASE / "claude-ledger.json"}


def role_of(task: str) -> str:
    t = task.lower()
    if "canary" in t:
        return "canary"
    if "diagnos" in t:
        return "diagnosis"
    if "contract" in t:
        return "contract"
    if "final-review" in t or "critic" in t or "review" in t:
        return "critic"
    if "build" in t:
        return "builder"
    if re.search(r"(^|[-_])map(per)?($|[-_])", t):
        return "mapper"
    return "other"


def chain_of(task: str) -> str:
    t = task.lower()
    if t.startswith("index05-attachment") or t.startswith("index05-scan"):
        return "index05-attachment"
    if t.startswith("index05_encoder"):
        return "index05-encoder"
    return ""


def attempt_of(task: str) -> int:
    m = re.search(r"retry(\d+)", task.lower())
    return int(m.group(1)) + 1 if m else 1


def main() -> int:
    rows, recon = [], {}
    for name, path in LEDGERS.items():
        ledger = json.loads(path.read_text(encoding="utf-8"))
        calls = ledger.get("calls", [])
        running = 0.0
        sum_final = 0.0
        by_status: dict[str, int] = {}
        orphans = 0
        receipt_total = 0.0
        prev_completed = None
        for entry in calls:
            status_ledger = entry.get("status", "")
            by_status[status_ledger] = by_status.get(status_ledger, 0) + 1
            charged = float(entry.get("charged_usd", 0.0))
            sum_final += charged
            rp = entry.get("receipt")
            receipt = {}
            if rp and os.path.exists(rp):
                receipt = json.loads(open(rp, encoding="utf-8").read())
            else:
                # find a receipt by run_id even when the ledger never recorded the path
                hits = [p for p in (BASE / "runs").glob(f"{entry['run_id']}-*.receipt.json")]
                if hits:
                    receipt = json.loads(hits[0].read_text(encoding="utf-8"))
            status_receipt = receipt.get("status", "")
            orphan = status_ledger == "started" and status_receipt == "completed"
            orphans += int(orphan)
            usage = receipt.get("usage", {}) or {}
            est_cost = receipt.get("estimated_cost_usd")
            if status_receipt == "completed" and est_cost is not None:
                receipt_total += float(est_cost)
            elif receipt:
                receipt_total += float(receipt.get("budget_charge_usd", receipt.get("preflight_reserve_usd", 0.0)) or 0.0)
            started = receipt.get("started_at")
            completed = receipt.get("completed_at")
            overlap = False
            if started and prev_completed:
                overlap = parse_ts(started) < parse_ts(prev_completed)
            if completed:
                prev_completed = completed
            manifest = receipt.get("manifest", [])
            task = entry.get("task", "")
            before = receipt.get("committed_before_usd")
            rows.append({
                "ledger": name,
                "run_id": entry.get("run_id"),
                "task": task,
                "chain": chain_of(task),
                "role": role_of(task),
                "attempt": attempt_of(task),
                "agent": entry.get("agent", ""),
                "population": "sprint" if entry.get("agent") == "claude-sprint" else "development",
                "model": receipt.get("model", ""),
                "lens": receipt.get("lens", ""),
                "started_at": started or "",
                "completed_at": completed or "",
                "latency_s": round(receipt["latency_ms"] / 1000, 1) if receipt.get("latency_ms") is not None else "",
                "status_ledger": status_ledger,
                "status_receipt": status_receipt,
                "orphan_unsettled": orphan,
                "ledger_charged_usd": charged,
                "receipt_estimated_cost_usd": est_cost if est_cost is not None else "",
                "preflight_reserve_usd": receipt.get("preflight_reserve_usd", ""),
                "cost_basis": ("metered_estimate" if status_receipt == "completed" else ("reserve" if receipt else "no_receipt")),
                "input_tokens": usage.get("input_tokens", ""),
                "output_tokens": usage.get("output_tokens", ""),
                "estimated_input_tokens": receipt.get("estimated_input_tokens", ""),
                "max_output_tokens": receipt.get("max_output_tokens", ""),
                "finish_reason": receipt.get("finish_reason", ""),
                "truncated": bool(receipt.get("truncated", False)),
                "error_class": receipt.get("error_class", ""),
                "output_chars": receipt.get("output_chars", ""),
                "files_n": len(manifest),
                "packet_bytes": sum(int(m.get("bytes", 0)) for m in manifest),
                "committed_before_usd": before if before is not None else "",
                "sum_final_before_usd": round(running, 8),
                "before_gap_usd": round(float(before) - running, 8) if before is not None else "",
                "started_before_prev_done": overlap,
                "rate_card_as_of": (receipt.get("rate_card") or {}).get("as_of", ""),
                "rate_card_source": (receipt.get("rate_card") or {}).get("source", ""),
            })
            running += charged
        recorded = float(ledger.get("committed_usd", 0.0))
        recon[name] = {
            "budget_usd": ledger.get("budget_usd"),
            "recorded_committed_usd": recorded,
            "recomputed_sum_charged_usd": round(sum_final, 8),
            "difference_usd": round(recorded - sum_final, 8),
            "sum_receipt_basis_usd": round(receipt_total, 8),
            "calls": len(calls),
            "by_status": by_status,
            "orphan_unsettled_calls": orphans,
            "aggregated_import_rows": [e.get("run_id") for e in calls if e.get("run_id") == "scratchpad-import"],
        }
    rows.sort(key=lambda r: (r["started_at"] or "0", r["run_id"]))
    write_csv(DATA / "delegations.csv", rows)
    write_json(DATA / "ledger_reconciliation.json", recon)
    print(f"delegations.csv: {len(rows)} rows; ledgers: {json.dumps({k: (v['recorded_committed_usd'], v['difference_usd'], v['orphan_unsettled_calls']) for k, v in recon.items()})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
