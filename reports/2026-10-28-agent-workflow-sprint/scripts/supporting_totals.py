"""Gather the figures the reports cite that had no home in data/ (found by the independent critic pass).

Output: data/supporting_totals.json, data/sprint_lane_results.csv
The sprint's own session usage is cut at SELF_CUTOFF so the numbers in 00-summary.md stay reproducible while the log grows.
"""
from __future__ import annotations

import csv
import json
import os
import statistics as st
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, TMP, parse_ts, write_csv, write_json  # noqa: E402

SELF_SESSION = "61d3eaf3-e0bc-4aa9-aa45-2de25ffb574b"
SELF_CUTOFF = "2026-10-28T20:44:38.000Z"


def rows(name):
    return list(csv.DictReader((DATA / name).open(encoding="utf-8")))


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def main() -> int:
    out: dict = {}
    # Codex tool-output friction
    fr = Counter()
    for t in rows("codex_threads.csv"):
        for k, v in json.loads(t["friction"] or "{}").items():
            fr[k] += v
    out["codex_git_friction_events"] = dict(fr)
    # transcript events
    ev = rows("transcript_events.csv")
    out["handoff_events_by_source"] = dict(Counter(e["source"] for e in ev if e["kind"] == "handoff"))
    dev = [e for e in ev if e["kind"] == "finding_disposition" and e["source"] in ("chat1", "chat2", "claude_dev")]
    def label(n):
        n = n.lower()
        return "upheld" if ("upheld" in n or "accept" in n) else "rejected" if ("reject" in n or "false" in n) else "partial" if "partial" in n else "other"
    c = Counter(label(e["note"]) for e in dev)
    out["development_transcript_dispositions"] = {"n": len(dev), **dict(c), "note": "model-labelled, not adjudicated; mixes reviewers and review types"}
    # delegate output sizes from receipts (development population)
    d = [r for r in rows("delegations.csv") if r.get("population") == "development" and r["role"] != "canary" and r["output_tokens"] not in ("", None)]
    o = [num(r["output_tokens"]) for r in d]
    out["development_receipt_output_tokens"] = {"n": len(o), "median": st.median(o), "mean": round(sum(o) / len(o)), "at_or_near_cap": sum(1 for r in d if num(r["output_tokens"]) >= 0.95 * num(r["max_output_tokens"]))}
    # sprint lane results
    res = [json.loads(l) for l in (TMP / "lanes" / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    # 67 launches in revision 2 were refused by the runner's own argument check (--max-output-tokens above 16,384) before any request: no call, no cost
    refused = [r for r in res if "max-output-tokens must be" in str(r.get("error"))]
    res = [r for r in res if r not in refused]
    flat = [{"id": r["id"], "lane": r["lane"], "model": r["model"], "status": r.get("status"), "input_tokens": r.get("input_tokens"), "output_tokens": r.get("output_tokens"),
             "live_cost_usd": r.get("live_cost"), "ledger_cost_usd": r.get("ledger_cost"), "latency_s": r.get("latency_s"), "finish_reason": r.get("finish_reason"), "truncated": r.get("truncated")} for r in res]
    write_csv(DATA / "sprint_lane_results.csv", flat)
    by_lane = defaultdict(lambda: [0, 0, 0.0])
    for r in res:
        by_lane[r["lane"]][0] += 1
        by_lane[r["lane"]][1] += int(bool(r.get("truncated")))
        by_lane[r["lane"]][2] += float(r.get("live_cost") or 0)
    out["sprint_deepinfra"] = {"calls": len(res), "refused_before_request": len(refused), "failed": sum(1 for r in res if r.get("status") != "completed"), "input_tokens": sum(int(r.get("input_tokens") or 0) for r in res),
                               "output_tokens": sum(int(r.get("output_tokens") or 0) for r in res), "live_cost_usd": round(sum(float(r.get("live_cost") or 0) for r in res), 3),
                               "ledger_estimate_usd": round(sum(float(r.get("ledger_cost") or 0) for r in res), 3), "truncated": sum(1 for r in res if r.get("truncated")),
                               "by_lane_calls_truncated_usd": {k: [v[0], v[1], round(v[2], 3)] for k, v in by_lane.items()},
                               "latency_s_median": st.median(float(r.get("latency_s") or 0) for r in res)}
    # anchor pass per model
    agg = defaultdict(lambda: {"calls": 0, "claimed": 0, "verified": 0})
    for r in rows("anchor_verification.csv"):
        if r["lane"] == "L2":  # revision-2 full-text readings use the exact-page rule and are reported in `lit2`
            continue
        m = r["model"].split("/")[-1]
        agg[m]["calls"] += 1
        agg[m]["claimed"] += int(r["claimed"] or 0)
        agg[m]["verified"] += int(r["verified"] or 0)
    out["anchor_pass_by_model"] = {m: {**v, "pass_rate": round(v["verified"] / max(1, v["claimed"]), 3)} for m, v in agg.items()}
    out["anchor_pass_all"] = {"claimed": sum(v["claimed"] for v in agg.values()), "verified": sum(v["verified"] for v in agg.values())}
    out["anchor_pass_all"]["pass_rate"] = round(out["anchor_pass_all"]["verified"] / out["anchor_pass_all"]["claimed"], 4)
    # anchor pass for the extraction lanes only (the critic lane C audits the reports and is reported separately)
    ext = defaultdict(lambda: {"calls": 0, "claimed": 0, "verified": 0})
    for r in rows("anchor_verification.csv"):
        if r["lane"] in ("C", "L2"):
            continue
        ext[r["model"].split("/")[-1]]["calls"] += 1
        ext[r["model"].split("/")[-1]]["claimed"] += int(r["claimed"] or 0)
        ext[r["model"].split("/")[-1]]["verified"] += int(r["verified"] or 0)
    out["anchor_pass_extraction_lanes_by_model"] = {m: {**v, "pass_rate": round(v["verified"] / max(1, v["claimed"]), 3)} for m, v in ext.items()}
    c_all = sum(v["claimed"] for v in ext.values())
    c_ok = sum(v["verified"] for v in ext.values())
    out["anchor_pass_extraction_lanes"] = {"claimed": c_all, "verified": c_ok, "pass_rate": round(c_ok / c_all, 4), "calls": sum(v["calls"] for v in ext.values())}
    reg = rows("claim_register.csv")
    outside = [r for r in reg if r["group"] == "outside"]
    out["claim_register"] = {"claims": len(reg), "outside_claims": len(outside), "tags": dict(Counter(r["tag"] for r in outside)),
                             "local_assertions_and_hypotheses": sum(1 for r in reg if r["group"] == "local"), "other_not_examined": sum(1 for r in reg if r["group"] == "other")}
    lit2 = DATA / "lit2_summary.json"
    if lit2.exists():
        out["lit2"] = json.loads(lit2.read_text(encoding="utf-8"))
    adj = rows("critic_adjudication.csv")
    out["critic_pass"] = {"findings": len(adj), "by_class": dict(Counter(r["class"] for r in adj)), "by_critic": {k: dict(Counter(r["class"] for r in adj if r["critic"] == k)) for k in sorted({r["critic"] for r in adj})},
                          "class_key": "D real defect, T traceability gap (number correct, no summary file), X false positive", "calls_cost_usd": round(sum(float(r.get("live_cost") or 0) for r in res if r["lane"] == "C"), 4)}
    # capture-recapture on the double-read transcript chunks
    s = json.loads((DATA / "transcript_event_summary.json").read_text(encoding="utf-8"))
    tot = [0, 0, 0]
    per = []
    for a in s["agreement_sample"]:
        n1, n2, m = a["mimo_events"], a["glm_flash_events"], a["matched"]
        per.append({"chunk": a["chunk"], "mimo": n1, "flash": n2, "matched": m, "lincoln_petersen_findable": round(n1 * n2 / m, 1) if m else None})
        tot = [tot[0] + n1, tot[1] + n2, tot[2] + m]
    lp = tot[0] * tot[1] / tot[2]
    out["capture_recapture_events"] = {"per_chunk": per, "pooled": {"mimo": tot[0], "flash": tot[1], "matched": tot[2], "findable_estimate": round(lp, 1), "mimo_share": round(tot[0] / lp, 2), "flash_share": round(tot[1] / lp, 2)}}
    # this session's own orchestrator usage up to the cutoff
    cut = parse_ts(SELF_CUTOFF)
    ms = [r for r in rows("claude_librarian_v2_messages.csv") if r["session"] == SELF_SESSION and r["is_api_error"] != "True" and parse_ts(r["ts"]) <= cut]
    out["self_session_until_cutoff"] = {"cutoff": SELF_CUTOFF, "assistant_messages": len(ms), "fresh_tokens": sum(int(r["input_tokens"]) + int(r["cache_creation_tokens"]) for r in ms),
                                        "cache_read_tokens": sum(int(r["cache_read_tokens"]) for r in ms), "output_tokens": sum(int(r["output_tokens"]) for r in ms),
                                        "peak_context_tokens": max(int(r["input_tokens"]) + int(r["cache_creation_tokens"]) + int(r["cache_read_tokens"]) for r in ms),
                                        "model": sorted({r["model"] for r in ms})}
    write_json(DATA / "supporting_totals.json", out)
    print(json.dumps({k: out[k] for k in ("codex_git_friction_events", "handoff_events_by_source", "development_transcript_dispositions", "development_receipt_output_tokens", "anchor_pass_all", "self_session_until_cutoff")}, indent=0)[:1800])
    print("sprint_deepinfra", json.dumps(out["sprint_deepinfra"])[:420])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
