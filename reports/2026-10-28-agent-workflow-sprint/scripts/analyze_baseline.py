"""WS5: baseline values for M1-M6, M10-M12 from the measured CSVs in data/ (no model tokens).

Writes data/baseline_metrics.json plus data/m1_changes.csv, m5_limits.csv, m6_resumes.csv.
The sprint's own Claude session is excluded from the baseline (it is reported as self-metrics).
"""
from __future__ import annotations

import bisect
import csv
import glob
import json
import os
import statistics as st
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, parse_ts, to_iso, write_csv, write_json  # noqa: E402

import numpy as np

SPRINT_SESSIONS = {"61d3eaf3-e0bc-4aa9-aa45-2de25ffb574b", "23197395-4e2e-4e3c-ad90-9cbe3af61a81"}
WINDOW = (parse_ts("2026-10-24T09:00:00Z"), parse_ts("2026-10-28T16:00:00Z"))
# The session logs keep growing (the second-pass review and this revision ran in Codex and Claude sessions of their own). Everything in the
# baseline is cut at the moment the first-pass analysis was frozen, so that later sessions about this sprint do not change its numbers.
DATA_CUTOFF = parse_ts("2026-10-28T20:44:00Z")
PRODUCTIVE = {"edit", "commit", "delegate", "test"}


def rows(name):
    return list(csv.DictReader((DATA / name).open(encoding="utf-8")))


def num(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def stats(xs):
    xs = sorted(xs)
    if not xs:
        return {"n": 0}
    def pct(p):
        k = (len(xs) - 1) * p
        lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
        return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)
    return {"n": len(xs), "median": round(pct(0.5), 2), "p25": round(pct(0.25), 2), "p75": round(pct(0.75), 2), "p90": round(pct(0.9), 2),
            "mean": round(sum(xs) / len(xs), 2), "total": round(sum(xs), 2)}


def merge(intervals):
    out = []
    for a, b in sorted(intervals):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def clip(intervals, lo, hi):
    return [(max(a, lo), min(b, hi)) for a, b in intervals if min(b, hi) > max(a, lo)]


def measure(intervals):
    return sum((b - a).total_seconds() for a, b in merge(intervals)) / 3600


def intersect(xs, ys):
    xs, ys, out = merge(xs), merge(ys), []
    for a, b in xs:
        for c, d in ys:
            lo, hi = max(a, c), min(b, d)
            if hi > lo:
                out.append((lo, hi))
    return out


def main() -> int:
    result: dict = {}
    commits = {r["hash"]: r for r in rows("commits.csv") if r["on_master"] == "True"}
    ctime = {h: parse_ts(r["commit_time"]) for h, r in commits.items()}
    claude_join = {r["commit"] for r in rows("claude_librarian_v2_commits.csv") if r["joined"] == "True" and r["session"] not in SPRINT_SESSIONS}
    codex_join = {r["commit"] for r in rows("codex_commits.csv") if r["joined"] == "True"}
    fam = {h: ("claude" if h in claude_join else "codex" if h in codex_join else "unjoined") for h in commits}
    result["commit_join"] = {"master": len(commits), **Counter(fam.values())}

    # ---- token events ----
    cl_msgs = [r for r in rows("claude_librarian_v2_messages.csv") if r["is_api_error"] != "True" and r["is_sidechain"] != "True" and r["session"] not in SPRINT_SESSIONS and parse_ts(r["ts"]) <= DATA_CUTOFF]
    # `fresh` = uncached input INCLUDING cache creation (as in the first pass); `cc` = the cache-creation part of it, kept
    # separate because the fitted price of cache creation is higher than that of ordinary input.
    claude_ev = [{"t": parse_ts(r["ts"]), "fresh": num(r["input_tokens"]) + num(r["cache_creation_tokens"]), "cc": num(r["cache_creation_tokens"]), "read": num(r["cache_read_tokens"]),
                  "out": num(r["output_tokens"]), "cat": r["category"], "kind": "main"} for r in cl_msgs]
    cx_req = [r for r in rows("codex_requests.csv") if parse_ts(r["ts"]) <= DATA_CUTOFF]
    codex_ev = [{"t": parse_ts(r["ts"]), "fresh": num(r["input_tokens"]) - num(r["cached_input_tokens"]), "cc": 0.0, "read": num(r["cached_input_tokens"]),
                 "out": num(r["output_tokens"]), "cat": r["category"], "kind": r["kind"], "used_secondary": r["used_secondary"], "resets_secondary": r["resets_secondary"]} for r in cx_req]
    result["token_totals"] = {
        f: {k: round(sum(e[k] for e in evs)) for k in ("fresh", "cc", "read", "out")} | {"requests": len(evs), "cache_read_share_of_input": round(sum(e["read"] for e in evs) / max(1, sum(e["read"] + e["fresh"] for e in evs)), 4)}
        for f, evs in (("claude", claude_ev), ("codex", codex_ev))}
    result["codex_tokens_by_thread_kind"] = {}
    for kind in ("main", "worker", "guardian"):
        evs = [e for e in codex_ev if e["kind"] == kind]
        result["codex_tokens_by_thread_kind"][kind] = {k: round(sum(e[k] for e in evs)) for k in ("fresh", "read", "out")} | {"requests": len(evs)}

    # ---- Claude price weights inferred from the client's own cost-state records (Opus 5.5) ----
    X, y = [], []
    for p in glob.glob(str(DATA / "claude_*_events.csv")):
        for r in csv.DictReader(open(p, encoding="utf-8")):
            if r["kind"] == "cost_state" and r["model"] == "claude-opus-5-5" and num(r["cost_usd"]) > 0:
                X.append([num(r["input_tokens"]), num(r["output_tokens"]), num(r["cache_read_tokens"]), num(r["cache_creation_tokens"])])
                y.append(num(r["cost_usd"]))
    weights = None
    if len(y) >= 8:
        A, b = np.array(X), np.array(y)
        scale = A.max(axis=0).clip(min=1)
        coef, *_ = np.linalg.lstsq(A / scale, b, rcond=None)
        coef = coef / scale * 1e6
        pred = (A * (coef / 1e6)).sum(axis=1)
        r2 = 1 - ((b - pred) ** 2).sum() / ((b - b.mean()) ** 2).sum()
        weights = {"usd_per_mtok_input": round(float(coef[0]), 3), "usd_per_mtok_output": round(float(coef[1]), 3), "usd_per_mtok_cache_read": round(float(coef[2]), 3),
                   "usd_per_mtok_cache_creation": round(float(coef[3]), 3), "records": len(y), "r2": round(float(r2), 4),
                   "note": "inferred from Claude Code cost-state records (client-computed list price); sign or size anomalies mean the fit is unreliable"}
    result["claude_opus_price_fit"] = weights
    W_READ, W_OUT, W_CC = 0.1, 5.0, 1.25  # default index weights when no fit is trusted (ratios are [U] until the vendor page is fetched)
    if weights and all(weights[k] > 0 for k in ("usd_per_mtok_input", "usd_per_mtok_output", "usd_per_mtok_cache_read", "usd_per_mtok_cache_creation")):
        W_READ = weights["usd_per_mtok_cache_read"] / weights["usd_per_mtok_input"]
        W_OUT = weights["usd_per_mtok_output"] / weights["usd_per_mtok_input"]
        W_CC = weights["usd_per_mtok_cache_creation"] / weights["usd_per_mtok_input"]
    result["index_weights"] = {"fresh_input": 1.0, "cache_creation": round(W_CC, 3), "cache_read": round(W_READ, 3), "output": round(W_OUT, 3)}

    def idx(c):
        # `fresh` already counts cache creation once at the input weight; add the extra weight for that part
        return c["fresh"] + (W_CC - 1.0) * c.get("cc", 0.0) + W_READ * c["read"] + W_OUT * c["out"]

    # ---- attribute tokens to the next ACCEPTED (code) commit by the same agent family ----
    # Windows end only at code commits: bookkeeping commits (plan records, docs) are counted per window,
    # not used as boundaries, so the cost of recording and verifying work stays inside the change it serves.
    def variants(r):
        code = r["code_commit"] == "True" and r["bookkeeping_only"] != "True" and r["n_parents"] == "1"
        ins, rew = int(r["insertions_text_files"] or 0), int(r["rewritten_lines_24h"] or 0)
        a1 = code and r["is_revert"] != "True" and not (ins >= 10 and rew / ins >= 0.3)
        a2 = a1 and (r["survival_ratio"] == "" or float(r["survival_ratio"]) >= 0.5)
        return code, a1, a2

    changes, unattributed = [], {}
    for family, evs in (("claude", claude_ev), ("codex", codex_ev)):
        hs = sorted([h for h in commits if fam[h] == family and variants(commits[h])[0]], key=lambda h: ctime[h])
        all_h = sorted([h for h in commits if fam[h] == family], key=lambda h: ctime[h])
        times = [ctime[h] for h in hs]
        acc = {h: Counter() for h in hs}
        un = Counter()
        for e in sorted(evs, key=lambda e: e["t"]):
            i = bisect.bisect_left(times, e["t"])
            if i >= len(hs):
                un["requests"] += 1; un["fresh"] += e["fresh"]; un["cc"] += e["cc"]; un["read"] += e["read"]; un["out"] += e["out"]
                continue
            c = acc[hs[i]]
            c["requests"] += 1; c["fresh"] += e["fresh"]; c["cc"] += e["cc"]; c["read"] += e["read"]; c["out"] += e["out"]
            c["gap_s"] = max(c["gap_s"], (times[i] - e["t"]).total_seconds())
            if e["cat"] == "guardian":
                c["guardian_requests"] += 1
            if e["kind"] == "worker":
                c["worker_requests"] += 1
            if e["cat"] == "subagent":
                c["orchestration_requests"] += 1
        unattributed[family] = {k: round(v) for k, v in un.items()}
        prev_t = None
        for h in hs:
            r = commits[h]
            code, a1, a2 = variants(r)
            c = acc[h]
            book = sum(1 for x in all_h if fam[x] == family and not variants(commits[x])[0] and (prev_t is None or ctime[x] > prev_t) and ctime[x] <= ctime[h])
            prev_t = ctime[h]
            changes.append({"hash": h[:7], "family": family, "commit_time": r["commit_time"], "subject": r["subject"][:80], "A0": code, "A1": a1, "A2": a2,
                            "requests": c["requests"], "fresh_tokens": round(c["fresh"]), "cache_creation_tokens": round(c["cc"]), "cache_read_tokens": round(c["read"]), "output_tokens": round(c["out"]),
                            "weighted_index": round(idx({"fresh": c["fresh"], "cc": c["cc"], "read": c["read"], "out": c["out"]})),
                            "bookkeeping_commits_in_window": book, "worker_requests": c["worker_requests"], "guardian_requests": c["guardian_requests"],
                            "orchestration_requests": c["orchestration_requests"], "max_gap_h": round(c["gap_s"] / 3600, 1), "insertions": r["insertions"],
                            "survival_ratio": r["survival_ratio"], "drafted_by_delegate": r["drafted_by"] == "True", "reviewed_by_delegate": r["reviewed_by"] == "True"})
    result["unattributed_after_last_code_commit"] = unattributed
    write_csv(DATA / "m1_changes.csv", changes)
    m1 = {}
    for family in ("claude", "codex"):
        for var in ("A0", "A1", "A2"):
            sel = [c for c in changes if c["family"] == family and c[var]]
            m1[f"{family}_{var}"] = {"n": len(sel), "fresh_tokens": stats([c["fresh_tokens"] for c in sel]), "cache_creation_tokens": stats([c["cache_creation_tokens"] for c in sel]),
                                     "output_tokens": stats([c["output_tokens"] for c in sel]),
                                     "cache_read_tokens": stats([c["cache_read_tokens"] for c in sel]), "weighted_index": stats([c["weighted_index"] for c in sel]),
                                     "requests": stats([c["requests"] for c in sel])}
    result["M1_tokens_per_accepted_change"] = m1
    # delegated vs undelegated changes (observational)
    for family in ("claude", "codex"):
        for flag in (True, False):
            sel = [c for c in changes if c["family"] == family and c["A0"] and (c["drafted_by_delegate"] or c["reviewed_by_delegate"]) == flag]
            result.setdefault("M1_by_delegation", {})[f"{family}_delegate_involved={flag}"] = {"n": len(sel), "weighted_index_median": stats([c["weighted_index"] for c in sel]).get("median"),
                                                                                                   "output_tokens_median": stats([c["output_tokens"] for c in sel]).get("median")}
    if weights and weights["usd_per_mtok_input"] > 0:
        cl = [c for c in changes if c["family"] == "claude" and c["A0"]]
        merged = [(c["fresh_tokens"] * weights["usd_per_mtok_input"] + c["output_tokens"] * weights["usd_per_mtok_output"] + c["cache_read_tokens"] * weights["usd_per_mtok_cache_read"]) / 1e6 for c in cl]
        four = [((c["fresh_tokens"] - c["cache_creation_tokens"]) * weights["usd_per_mtok_input"] + c["cache_creation_tokens"] * weights["usd_per_mtok_cache_creation"]
                 + c["output_tokens"] * weights["usd_per_mtok_output"] + c["cache_read_tokens"] * weights["usd_per_mtok_cache_read"]) / 1e6 for c in cl]
        # modelled list-price dollars, not billing: the plans bill by quota. `four` is the one to quote; `merged` is the first pass.
        result["M2_claude_shadow_usd_per_accepted_change_A0"] = stats(four)
        result["M2_claude_shadow_usd_first_pass_merged_bucket"] = stats(merged)

    # ---- Codex quota: tokens per weekly percentage point ----
    byreset = defaultdict(list)
    for e in sorted(codex_ev, key=lambda e: e["t"]):
        if e["used_secondary"] != "":
            byreset[e["resets_secondary"]].append((e["t"], num(e["used_secondary"]), idx(e)))
    quota = []
    for reset, series in byreset.items():
        cum, pts = 0.0, []
        for t, used, w in series:
            cum += w
            pts.append((cum, used))
        if len(pts) > 30 and pts[-1][1] > pts[0][1] + 5:
            xs = np.array([p[0] for p in pts]); ys = np.array([p[1] for p in pts])
            slope = float(np.polyfit(xs, ys, 1)[0])
            quota.append({"weekly_window_resets": reset, "requests": len(pts), "used_percent_from": pts[0][1], "used_percent_to": pts[-1][1], "weighted_tokens_per_1pct": round(1 / slope) if slope > 0 else None})
    result["codex_weekly_quota_fit"] = quota

    # ---- M5: limits ----
    claude_events = [e for e in rows("claude_librarian_v2_events.csv") if e["session"] not in SPRINT_SESSIONS and parse_ts(e["ts"]) <= DATA_CUTOFF]  # the sprint's own sessions are not baseline
    claude_blocked, m5 = [], []
    for e in claude_events:
        if e["kind"] == "api_limit" and e["resets_at"]:
            a, b = parse_ts(e["ts"]), parse_ts(e["resets_at"])
            claude_blocked.append((a, b))
            m5.append({"agent": "claude", "kind": e["limit_type"], "hit": e["ts"], "resets_at": e["resets_at"], "blocked_h": round((b - a).total_seconds() / 3600, 2)})
    cx_events = [e for e in rows("codex_events.csv") if parse_ts(e["ts"]) <= DATA_CUTOFF]
    uniq = {}
    for e in cx_events:
        if e["kind"] == "usage_limit":
            uniq.setdefault(e["turn_id"], e)
    limit_evs = sorted(uniq.values(), key=lambda e: e["ts"])
    cx_times = sorted(e["t"] for e in codex_ev)
    codex_idle, bursts = [], []
    for e in limit_evs:
        a = parse_ts(e["ts"])
        i = bisect.bisect_right(cx_times, a + timedelta(seconds=5))
        nxt = cx_times[i] if i < len(cx_times) else None
        gap_h = round((nxt - a).total_seconds() / 3600, 2) if nxt else None
        ps, ss = num(e["used_primary"]), num(e["used_secondary"])
        window = "weekly" if ss >= ps else "five_hour"
        reset = e["resets_secondary"] if window == "weekly" else e["resets_primary"]
        m5.append({"agent": "codex", "kind": window, "hit": e["ts"], "resets_at": reset, "observed_idle_h": gap_h, "used_primary": e["used_primary"], "used_secondary": e["used_secondary"]})
        if nxt and (nxt - a).total_seconds() >= 600:
            codex_idle.append((a, nxt))
    write_csv(DATA / "m5_limits.csv", m5)
    claude_union, codex_union = clip(merge(claude_blocked), *WINDOW), clip(merge(codex_idle), *WINDOW)
    both = intersect(claude_union, codex_union)
    total_h = (WINDOW[1] - WINDOW[0]).total_seconds() / 3600
    result["M5_limits"] = {
        "window_hours": round(total_h, 1), "claude_blocked_hours": round(measure(claude_union), 1), "codex_observed_idle_hours": round(measure(codex_union), 1),
        "both_blocked_hours": round(measure(both), 1), "claude_blocked_share": round(measure(claude_union) / total_h, 3),
        "codex_idle_share": round(measure(codex_union) / total_h, 3), "both_blocked_share": round(measure(both) / total_h, 3),
        "claude_events": [m for m in m5 if m["agent"] == "claude"], "codex_unique_limit_turns": len(limit_evs),
        "codex_limit_turns_per_day": dict(Counter(e["ts"][:10] for e in limit_evs)),
        "codex_idle_gaps_h": stats([m["observed_idle_h"] for m in m5 if m["agent"] == "codex" and m.get("observed_idle_h") and m["observed_idle_h"] >= 0.1667]),
    }
    # work bursts: contiguous Codex activity (gaps < 30 min) that ends in a usage-limit event
    activity = cx_times
    segs, start, prev = [], None, None
    for t in activity:
        if start is None:
            start = prev = t
        elif (t - prev).total_seconds() > 1800:
            segs.append((start, prev)); start = prev = t
        else:
            prev = t
    if start:
        segs.append((start, prev))
    ends = [parse_ts(e["ts"]) for e in limit_evs]
    burst_min = [(b - a).total_seconds() / 60 for a, b in segs if any(abs((b - x).total_seconds()) <= 300 for x in ends)]
    result["M5_limits"]["codex_bursts_ending_in_limit_minutes"] = stats(burst_min)
    result["M5_limits"]["codex_bursts_total"] = len(segs)
    # work in flight at a Codex limit: last request category of the main family before the limit
    cat_before = Counter()
    ordered = sorted(codex_ev, key=lambda e: e["t"])
    times_all = [e["t"] for e in ordered]
    for x in ends:
        i = bisect.bisect_left(times_all, x) - 1
        if i >= 0:
            cat_before[ordered[i]["cat"]] += 1
    result["M5_limits"]["codex_last_request_category_before_limit"] = dict(cat_before)

    # ---- M6: resume cost (cold-start tokens before the first productive request) ----
    comp_cl = [parse_ts(e["ts"]) for e in claude_events if e["kind"] == "compaction"]
    thread_kind = {r["thread"]: r["kind"] for r in rows("codex_threads.csv")}
    comp_cx_all = [parse_ts(e["ts"]) for e in cx_events if e["kind"] == "compaction"]
    comp_cx = [parse_ts(e["ts"]) for e in cx_events if e["kind"] == "compaction" and thread_kind.get(e["thread"]) == "main"]
    def resumes(stream, family, limit_times, comp_times):
        out = []
        stream = sorted(stream, key=lambda e: e["t"])
        for i in range(1, len(stream)):
            gap = (stream[i]["t"] - stream[i - 1]["t"]).total_seconds() / 60
            is_comp = any(stream[i - 1]["t"] <= c <= stream[i]["t"] for c in comp_times)
            if gap < 60 and not is_comp:
                continue
            is_limit = any(stream[i - 1]["t"] <= x <= stream[i]["t"] for x in limit_times)
            kind = "limit" if is_limit else ("compaction" if is_comp else "idle")
            fresh = out_t = reads = cc = 0
            for j in range(i, min(len(stream), i + 400)):
                fresh += stream[j]["fresh"]; cc += stream[j]["cc"]; out_t += stream[j]["out"]; reads += 1
                if stream[j]["cat"] in PRODUCTIVE:
                    break
            out.append({"family": family, "boundary": kind, "t": to_iso(stream[i]["t"]), "gap_min": round(gap), "requests_before_first_productive": reads,
                        "fresh_tokens_before_first_productive": round(fresh), "cache_creation_tokens_before_first_productive": round(cc), "output_tokens_before_first_productive": round(out_t),
                        "reached_productive": stream[min(i + reads - 1, len(stream) - 1)]["cat"] in PRODUCTIVE})
        return out
    cl_limit_times = [a for a, _ in claude_blocked] + [parse_ts(r["ts"]) for r in rows("claude_librarian_v2_prompts.csv") if r["limit_report"] == "True" and r["session"] not in SPRINT_SESSIONS]
    res = resumes(claude_ev, "claude", cl_limit_times, comp_cl) + resumes([e for e in codex_ev if e["kind"] == "main"], "codex_main", ends, comp_cx)
    write_csv(DATA / "m6_resumes.csv", res)
    m6 = {}
    for fam_name in ("claude", "codex_main"):
        for kind in ("limit", "compaction", "idle"):
            sel = [r for r in res if r["family"] == fam_name and r["boundary"] == kind and r["reached_productive"]]
            m6[f"{fam_name}_{kind}"] = {"n": len(sel), "fresh_tokens": stats([r["fresh_tokens_before_first_productive"] for r in sel]),
                                        "cache_creation_tokens": stats([r["cache_creation_tokens_before_first_productive"] for r in sel]),
                                        "requests": stats([r["requests_before_first_productive"] for r in sel])}
    result["M6_resume_cost"] = m6

    # ---- session-start cold start (Claude): tokens before the first productive request in each session ----
    starts = []
    for sess in sorted({r["session"] for r in cl_msgs}):
        ms = sorted([e for r, e in zip(cl_msgs, claude_ev) if r["session"] == sess], key=lambda e: e["t"])
        fresh = out_t = n = 0
        for e in ms:
            fresh += e["fresh"]; out_t += e["out"]; n += 1
            if e["cat"] in PRODUCTIVE:
                break
        starts.append({"session": sess[:8], "requests_before_first_productive": n, "fresh_tokens": round(fresh), "output_tokens": round(out_t), "messages": len(ms)})
    result["M6_session_start_claude"] = starts

    # ---- post-result interval (revision 2). Calls come from data/delegate_events.csv: runner records (receipts, scratchpad ledger and logs)
    # linked to the shell launch. A result is *available* at the call's real end (not when a yielding shell call returned) and is
    # *consumed* at the first later tool call that reads its output file. Results consumed within 90 s of each other form one batch.
    # The interval runs from consumption to the next accepted-family commit, the next launch by the same family, or 3 hours.
    # It contains everything the orchestrator did in that time (integration, tests, unrelated work): it is NOT verification labour.
    def post_result_intervals(events, stream, commit_times, family):
        stream = sorted(stream, key=lambda e: e["t"])
        times = [e["t"] for e in stream]
        launches = sorted(parse_ts(r["ts_launch"]) for r in events if r["ts_launch"])
        batches = []
        for r in sorted(events, key=lambda r: r["_t0"]):
            if batches and (r["_t0"] - batches[-1]["rows"][-1]["_t0"]).total_seconds() <= 90 and r["_cls"] == batches[-1]["cls"]:
                batches[-1]["rows"].append(r)
            else:
                batches.append({"cls": r["_cls"], "rows": [r]})
        for b in batches:
            b["t0"] = b["rows"][0]["_t0"]
            own = {parse_ts(r["ts_launch"]) for r in b["rows"] if r["ts_launch"]}
            cands = [("commit", t) for t in commit_times if t > b["t0"]] + [("next_launch", t) for t in launches if t > b["t0"] + timedelta(seconds=30) and t not in own]
            cands.append(("cap_3h", b["t0"] + timedelta(hours=3)))
            b["reason"], b["t1"] = min(cands, key=lambda c: c[1])
            b["t1"] = min(b["t1"], b["t0"] + timedelta(hours=3))
            b["acc"] = Counter(); b["cats"] = Counter()
        for e in stream:  # each request is charged to the latest-starting open batch, so windows never double-count
            open_ = [b for b in batches if b["t0"] < e["t"] <= b["t1"]]
            if open_:
                b = max(open_, key=lambda b: b["t0"])
                b["acc"]["requests"] += 1
                for k in ("fresh", "cc", "read", "out"):
                    b["acc"][k] += e[k]
                b["cats"][e["cat"]] += 1
        out = []
        for b in batches:
            a = b["acc"]
            out.append({"family": family, "class": b["cls"], "n_calls": len(b["rows"]), "models": ";".join(sorted({r["model"].split("/")[-1] for r in b["rows"]})),
                        "tasks": ";".join(r["task"] for r in b["rows"])[:120], "consumed_at": to_iso(b["t0"]), "window_ended_by": b["reason"],
                        "minutes": round((b["t1"] - b["t0"]).total_seconds() / 60, 1), "requests": a["requests"], "fresh_tokens": round(a["fresh"]),
                        "cache_creation_tokens": round(a["cc"]), "cache_read_tokens": round(a["read"]), "output_tokens": round(a["out"]),
                        "delegate_output_tokens": sum(int(num(r["output_tokens"])) for r in b["rows"]), "categories": json.dumps(dict(b["cats"]), sort_keys=True),
                        "all_outputs_reread": all(r["first_read_ts"] for r in b["rows"])})
        return out
    cl_commit_times = sorted(ctime[h] for h in commits if fam[h] == "claude")
    cx_commit_times = sorted(ctime[h] for h in commits if fam[h] == "codex")
    dev_events = []
    for r in rows("delegate_events.csv"):
        if r["population"] != "development" or r["status"] not in ("completed", "") or not r["call_end"]:
            continue
        r["_t0"] = parse_ts(r["first_read_ts"] or r["result_available_ts"] or r["call_end"])
        r["_cls"] = "reading" if r["runner"] == "second_reader" else "work_packet"
        dev_events.append(r)
    work = [r for r in dev_events if "canary" not in r["task"].lower() and r["task"] != "test_stage"]
    pr = []
    for family, stream, commit_times in (("claude", claude_ev, cl_commit_times), ("codex_main", [e for e in codex_ev if e["kind"] == "main"], cx_commit_times)):
        fam_events = [r for r in work if (r["family"] == "claude") == (family == "claude")]
        pr += post_result_intervals(fam_events, stream, commit_times, family)
    write_csv(DATA / "m7_post_result_intervals.csv", pr)
    result["M7_post_result_interval"] = {
        f"{fam_name}_{cls}": {"batches": len(sel), "calls": sum(r["n_calls"] for r in sel),
                              "ended_by": dict(Counter(r["window_ended_by"] for r in sel)),
                              "fresh_tokens": stats([r["fresh_tokens"] for r in sel]), "cache_creation_tokens": stats([r["cache_creation_tokens"] for r in sel]),
                              "output_tokens": stats([r["output_tokens"] for r in sel]), "requests": stats([r["requests"] for r in sel]), "minutes": stats([r["minutes"] for r in sel])}
        for fam_name in ("claude", "codex_main") for cls in ("work_packet", "reading")
        for sel in [[r for r in pr if r["family"] == fam_name and r["class"] == cls]]}
    result["M7_note"] = ("Intervals start at the first re-read of the delegate output (not when a yielding shell call returned) and include everything the orchestrator did "
                         "until the next commit or launch. They are descriptive upper bounds on result-related work, not verification cost, and they have no matched "
                         "direct-work counterfactual.")

    # ---- M10 parallel efficiency (Codex threads) ----
    by_thread = defaultdict(list)
    for r in cx_req:
        by_thread[(r["thread"], r["kind"])].append(parse_ts(r["ts"]))
    active, thread_time = [], 0.0
    for (tid, kind), ts_list in by_thread.items():
        ts_list.sort()
        s = p = ts_list[0]
        for t in ts_list[1:] + [None]:
            if t is None or (t - p).total_seconds() > 600:
                end = p + timedelta(seconds=60)
                active.append((s, end, kind))
                thread_time += (end - s).total_seconds() / 3600
                if t is not None:
                    s = t
            if t is not None:
                p = t
    union_h = measure([(a, b) for a, b, k in active if k != "guardian"])
    work_h = sum((b - a).total_seconds() for a, b, k in active if k != "guardian") / 3600
    events_sweep = []
    for a, b, k in active:
        if k != "guardian":
            events_sweep += [(a, 1), (b, -1)]
    events_sweep.sort()
    cur = peak = 0
    for _, d in events_sweep:
        cur += d
        peak = max(peak, cur)
    orch_tokens = sum(e["fresh"] + e["out"] for e in codex_ev if e["cat"] == "subagent")
    result["M10_parallel"] = {"non_guardian_thread_active_hours": round(work_h, 1), "union_wall_hours": round(union_h, 1), "mean_parallelism_when_active": round(work_h / union_h, 2) if union_h else None,
                              "definition": "overlap proxy from request timestamps (gaps over 10 minutes split activity, one-minute tail): not speedup, throughput or the share of agent-time used",
                              "peak_concurrent_threads": peak, "threads": dict(Counter(k for (_, k) in by_thread)),
                              "orchestration_request_share_of_fresh_plus_output": round(orch_tokens / max(1, sum(e["fresh"] + e["out"] for e in codex_ev)), 4)}

    # ---- M11 context tax ----
    cl_peak = max((num(r["input_tokens"]) + num(r["cache_creation_tokens"]) + num(r["cache_read_tokens"]) for r in cl_msgs), default=0)
    cx_peak = max((num(r["input_tokens"]) for r in cx_req), default=0)
    comps = {(e["project"] if "project" in e else "", e["ts"], e.get("pre_tokens")) for e in claude_events if e["kind"] == "compaction"}
    cl_out = sum(e["out"] for e in claude_ev)
    result["M11_context"] = {"claude_peak_context_tokens": cl_peak, "codex_peak_single_request_input_tokens": cx_peak,
                             "claude_compactions": len(comps), "claude_compactions_per_100k_output": round(len(comps) / max(1, cl_out) * 1e5, 3),
                             "codex_compactions_all_threads": len(comp_cx_all), "codex_compactions_per_100k_output": round(len(comp_cx_all) / max(1, sum(e["out"] for e in codex_ev)) * 1e5, 3)}

    # ---- M12 instrumentation integrity + delegation facts ----
    d = rows("delegations.csv")
    real = [r for r in d if r["role"] != "canary" and r["run_id"] != "scratchpad-import" and r.get("population", "development") == "development"]
    live = json.loads((DATA / "deepinfra_live_check.json").read_text(encoding="utf-8")) if (DATA / "deepinfra_live_check.json").exists() else {}
    stale = {m: v["status"] for m, v in live.get("models", {}).items() if v["status"] != "verified"}
    ratios = [num(r["estimated_input_tokens"]) / num(r["input_tokens"]) for r in real if r["input_tokens"] not in ("", "0")]
    result["M12_instrumentation"] = {
        "dev_calls": len(real), "completed": sum(1 for r in real if r["status_receipt"] == "completed"), "failed": sum(1 for r in real if r["status_receipt"] == "failed"),
        "orphan_unsettled": sum(1 for r in real if r["orphan_unsettled"] == "True"), "truncated_finish_length": sum(1 for r in real if r["finish_reason"] == "length"),
        "truncated_share_of_completed": round(sum(1 for r in real if r["finish_reason"] == "length") / max(1, sum(1 for r in real if r["status_receipt"] == "completed")), 3),
        "overlapping_starts": sum(1 for r in real if r["started_before_prev_done"] == "True"), "input_estimate_ratio": stats(ratios),
        "latency_s": stats([num(r["latency_s"]) for r in real if r["latency_s"] != ""]), "stale_or_unlisted_rate_cards": stale,
        "claude_ledger_aggregated_import_usd": 0.5457, "ledger_reconciliation": json.loads((DATA / "ledger_reconciliation.json").read_text(encoding="utf-8")),
        "dev_spend_usd_estimated": round(sum(num(r["ledger_charged_usd"]) for r in real), 4),
    }
    inv_path = DATA / "delegate_inventory.json"
    if inv_path.exists():  # revision 2: calls reconstructed from the runners' own records, including the Claude scratchpad runners
        result["M12_instrumentation"]["delegate_call_inventory"] = json.loads(inv_path.read_text(encoding="utf-8"))

    # ---- M3 rework and survival ----
    crows = [commits[h] for h in commits if variants(commits[h])[0]]
    ratios = [int(r["rewritten_lines_24h"] or 0) / int(r["insertions_text_files"]) for r in crows if int(r["insertions_text_files"] or 0) >= 10]
    surv = [float(r["survival_ratio"]) for r in crows if r["survival_ratio"] != ""]
    result["M3_rework"] = {"accepted_code_commits": len(crows), "with_ge10_insertions": len(ratios),
                           "share_with_ge30pct_lines_rewritten_in_24h": round(sum(1 for x in ratios if x >= 0.3) / max(1, len(ratios)), 3),
                           "share_with_any_line_rewritten_in_72h": round(sum(1 for r in crows if int(r["rewritten_lines_72h"] or 0) > 0) / max(1, len(crows)), 3),
                           "survival_ratio": stats(surv), "reverts": sum(1 for r in crows if r["is_revert"] == "True"),
                           "delegate_drafted_commits": sum(1 for r in crows if r["drafted_by"] == "True"),
                           "delegate_drafted_with_fixes_in_review": sum(1 for r in crows if r["drafted_by"] == "True" and ("fixed in review" in r["subject"].lower() or r["fixed_in_review"] == "True"))}
    # Right-censoring: a commit made shortly before the data ends has had no time to be rewritten. Report mature cohorts separately.
    cut = parse_ts("2026-10-28T21:00:00Z")
    def follow_h(r):
        return (cut - ctime[r["hash"]]).total_seconds() / 3600
    m24 = [r for r in crows if follow_h(r) >= 24]
    m72 = [r for r in crows if follow_h(r) >= 72]
    r24 = [int(r["rewritten_lines_24h"] or 0) / int(r["insertions_text_files"]) for r in m24 if int(r["insertions_text_files"] or 0) >= 10]
    result["M3_rework_mature_cohorts"] = {
        "analysis_cutoff": to_iso(cut), "accepted_code_commits": len(crows), "with_at_least_24h_followup": len(m24), "with_at_least_72h_followup": len(m72),
        "censored_before_24h": len(crows) - len(m24), "censored_before_72h": len(crows) - len(m72),
        "ge10_insertions_with_24h_followup": len(r24), "share_ge30pct_rewritten_in_24h_mature": round(sum(1 for x in r24 if x >= 0.3) / max(1, len(r24)), 3),
        "count_ge30pct_rewritten_in_24h_mature": sum(1 for x in r24 if x >= 0.3),
        "share_any_line_rewritten_in_72h_mature": round(sum(1 for r in m72 if int(r["rewritten_lines_72h"] or 0) > 0) / max(1, len(m72)), 3),
        "count_any_line_rewritten_in_72h_mature": sum(1 for r in m72 if int(r["rewritten_lines_72h"] or 0) > 0),
        "note": "Line survival and rewrite counts are proxies: legitimate refactors delete good code, untouched bugs survive, pre-commit repairs are invisible and deletion-only fixes insert no lines."}
    # ---- plan growth ----
    pg = rows("plan_growth.csv")
    result["resume_payload"] = {"plan_tokens_first": int(pg[0]["tokens"]), "plan_tokens_last": int(pg[-1]["tokens"]), "s19_tokens_last": int(pg[-1]["s19_tokens"]), "plan_versions": len(pg)}
    write_json(DATA / "baseline_metrics.json", result)
    print(json.dumps({k: result[k] for k in ("commit_join", "token_totals", "index_weights", "claude_opus_price_fit")}, indent=1)[:2500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
