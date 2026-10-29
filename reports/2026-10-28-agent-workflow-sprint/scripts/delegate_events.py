"""Revision 2: delegation calls reconstructed from the agents' own records, then located in the session logs.

The first pass classified any shell command that mentioned a runner as a delegation, and started every
follow-up window when the shell call returned. Both were wrong (a launch can yield before the API call
finishes; reading, searching or editing a runner is not a delegation). Here:

* A *call* is a record the runner itself wrote: a receipt (repository runner), a row of the Claude scratchpad
  ledger (delegate.py) or a scratchpad log (second_reader.py).
* A *launch* is a shell command that executes a runner (interpreter + runner script as its program).
* Each call is linked to its launch, its real completion time (receipt, or output-file time for the scratchpad
  runners) and the first later tool call that reads its output file.

Message text is never written; commands are used only to classify and to extract task, model and file names.
Outputs: data/delegate_events.csv, data/delegate_launch_audit.csv, data/delegate_inventory.json
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CLAUDE_PROJECTS, CODEX_SESSIONS, DATA, REPO, delegate_kind, delegate_launches, parse_ts, to_iso, write_csv  # noqa: E402
from codex_log_metrics import decode_cmds, out_text  # noqa: E402

DEV_CLAUDE = ("2ca0af49",)  # the development session; the sprint's own sessions (23197395, 61d3eaf3) are excluded
SCRATCH = Path(os.path.expanduser("~")) / "AppData" / "Local" / "Temp" / "claude" / "D--Librarian-V2"
RUNS = REPO / "tmp" / "deepinfra-delegation" / "runs"
SPRINT_AGENT = "claude-sprint"
# USD per 1M tokens (input, output) in the scratchpad runner's own table (delegate.py); used for second_reader logs, which store no cost.
SCRATCH_PRICES = {"XiaomiMiMo/MiMo-V2.6-Pro": (0.43, 0.87), "zai-org/GLM-5.3": (0.45, 2.00), "Qwen/Qwen3.5-397B-A17B": (0.45, 3.00),
                  "deepseek-ai/DeepSeek-V4-Pro": (1.30, 2.60)}


def utc(epoch: float) -> datetime:
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


def iso(dt) -> str:
    return to_iso(dt) if dt else ""


def outcome(text: str) -> str:
    t = text or ""
    if re.search(r"Rejected|unacceptable risk", t):
        return "rejected"
    if re.search(r"running in (the )?background|Script running with cell ID", t) or ('"session_id"' in t and '"exit_code"' not in t):
        return "yielded"
    if re.search(r"Script failed|Script error|Traceback|^Exit code [1-9]", t):
        return "error"
    return "returned"


def block_text(block: dict) -> str:
    c = block.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(x.get("text", "") for x in c if isinstance(x, dict))
    return ""


def load_claude(prefix: str) -> dict:
    path = glob.glob(str(CLAUDE_PROJECTS / "D--Librarian-V2" / (prefix + "*.jsonl")))[0]
    th = {"family": "claude", "id": prefix, "trace": [], "cmds": {}, "results": {}}
    for raw in open(path, encoding="utf-8", errors="replace"):
        try:
            o = json.loads(raw)
        except ValueError:
            continue
        if not o.get("timestamp"):
            continue
        ts = parse_ts(o["timestamp"])
        content = (o.get("message") or {}).get("content")
        if o.get("type") == "assistant":
            for b in content or []:
                if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                    continue
                inp, name = b.get("input") or {}, b.get("name", "")
                if name in ("Bash", "PowerShell"):
                    cmd = str(inp.get("command", ""))
                    th["trace"].append((ts, b["id"], cmd))
                    k = delegate_kind(cmd)
                    if k:
                        th["cmds"][b["id"]] = {"ts": ts, "kind": k, "runs": delegate_launches(cmd), "bg": bool(inp.get("run_in_background")),
                                               "sha": hashlib.sha256(cmd.encode()).hexdigest()[:12]}
                elif name == "Read":
                    th["trace"].append((ts, b["id"], str(inp.get("file_path", ""))))
        elif o.get("type") == "user" and isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    th["results"].setdefault(b.get("tool_use_id"), (ts, block_text(b)))
    return th


def load_codex() -> list[dict]:
    threads: dict[str, dict] = {}
    for path in sorted(glob.glob(str(CODEX_SESSIONS / "2026" / "*" / "*" / "rollout-*.jsonl"))):
        with open(path, encoding="utf-8", errors="replace") as handle:
            try:
                meta = json.loads(handle.readline()).get("payload", {})
            except ValueError:
                continue
            if meta.get("cwd") != "D:\\Librarian_V2":
                continue
            tid, cutoff = meta.get("id", ""), meta.get("subagent_history_start_ordinal")
            th = threads.setdefault(tid, {"family": "codex", "id": tid, "trace": [], "cmds": {}, "results": {}})
            for raw in handle:
                try:
                    o = json.loads(raw)
                except ValueError:
                    continue
                if cutoff is not None and o.get("ordinal") is not None and o["ordinal"] < cutoff:
                    continue
                p = o.get("payload") or {}
                pt = p.get("type")
                if o.get("type") != "response_item" or not o.get("timestamp"):
                    continue
                ts = parse_ts(o["timestamp"])
                if pt in ("function_call", "custom_tool_call"):
                    name = p.get("name", "")
                    body = str((p.get("input") if pt == "custom_tool_call" else p.get("arguments")) or "")
                    cmd = decode_cmds(body) if name == "exec" else body
                    cid = p.get("call_id")
                    th["trace"].append((ts, cid, cmd))
                    k = delegate_kind(cmd)
                    if k:
                        th["cmds"][cid] = {"ts": ts, "kind": k, "runs": delegate_launches(cmd), "bg": False, "sha": hashlib.sha256(cmd.encode()).hexdigest()[:12]}
                elif pt in ("function_call_output", "custom_tool_call_output"):
                    th["results"].setdefault(p.get("call_id"), (ts, out_text(p)))
    return list(threads.values())


def find_launch(threads, runner, task, out_name, start, slack=240):
    """The launch command (any thread) that most plausibly started a call: same runner and task/output, issued just before it began."""
    best = None
    for th in threads:
        for cid, c in th["cmds"].items():
            if c["kind"] != "launch":
                continue
            lag = (start - c["ts"]).total_seconds()
            if lag < -15 or lag > slack:
                continue
            for r in c["runs"]:
                if r["runner"] != runner or r["kind"] != "launch":
                    continue
                oname = os.path.basename(r["out"].strip("'\"")) if r["out"] else ""
                # a templated output name (a shell loop) matches every call the loop starts
                if (task and r["task"] == task) or (out_name and oname == out_name) or (runner == "second_reader" and (not oname or "$" in oname)):
                    if best is None or c["ts"] > best[1]["ts"]:
                        best = (th, c, cid)
    return best


def first_read(threads, th_pref, needle, after):
    """First later tool call (preferably in the launching thread) that mentions the output file."""
    ordered = sorted(threads, key=lambda t: t is not th_pref)
    hits = []
    for th in ordered:
        for ts, cid, text in th["trace"]:
            if ts >= after and needle in text and cid not in th["cmds"]:
                hits.append((ts, th))
                break
        if hits and th is th_pref:
            break
    return min(hits, key=lambda h: h[0]) if hits else None


def main() -> int:
    claude = [load_claude(p) for p in DEV_CLAUDE]
    codex = load_codex()
    threads = claude + codex
    events, audit = [], []

    # ---- launch audit: every command that mentions a runner or the API, classified structurally (no text stored)
    for th in threads:
        for cid, c in th["cmds"].items():
            res = th["results"].get(cid)
            audit.append({"family": th["family"], "thread": th["id"][-8:], "ts": iso(c["ts"]), "kind": c["kind"], "n_runs": len(c["runs"]),
                          "runners": ";".join(r["runner"] for r in c["runs"]), "tasks": ";".join(r["task"] for r in c["runs"]),
                          "background": c["bg"], "return_state": outcome(res[1]) if res else "", "command_sha256": c["sha"]})

    # ---- Claude scratchpad calls
    reader = next(iter(sorted(SCRATCH.glob("2ca0af49*/scratchpad/reader"))), None)
    records = []
    if reader:
        for r in json.loads((reader / "ledger.json").read_text(encoding="utf-8")):
            records.append({"runner": "delegate", "task": r["task"], "model": r["model"], "in": r["prompt_tokens"], "out": r["completion_tokens"],
                            "cost": r["cost"], "secs": r["secs"], "finish": r["finish"], "path": reader / r["out"], "src": "scratchpad ledger.json",
                            "cost_basis": "runner rate table (estimate)"})
        for lg in sorted((reader / "out").glob("*.log")):
            try:
                j = json.loads(lg.read_text(encoding="utf-8").strip().splitlines()[0])
            except (ValueError, IndexError):
                continue
            pin, pout = SCRATCH_PRICES.get(j.get("model"), (0, 0))
            records.append({"runner": "second_reader", "task": lg.stem, "model": j.get("model", ""), "in": j.get("prompt_tokens", 0), "out": j.get("completion_tokens", 0),
                            "cost": round((j.get("prompt_tokens", 0) * pin + j.get("completion_tokens", 0) * pout) / 1e6, 4), "secs": j.get("secs", 0),
                            "finish": j.get("finish", ""), "path": lg.with_suffix(".md"), "src": "scratchpad out/*.log", "cost_basis": "runner rate table (estimate)"})
    for r in records:
        mt = r["path"].stat().st_mtime if r["path"].exists() else None
        term = utc(mt) if mt else None
        start = datetime.fromtimestamp(mt - float(r["secs"]), tz=timezone.utc) if mt else None
        link = find_launch(claude, r["runner"], r["task"] if r["runner"] == "delegate" else "", r["path"].name, start) if start else None
        events.append(_event("claude", "development", r, start, term, link, claude, threads))

    # ---- repository runner calls from receipts (both families)
    for f in sorted(glob.glob(str(RUNS / "*.receipt.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        u = d.get("usage") or {}
        start = parse_ts(d["started_at"])
        term = parse_ts(d["completed_at"]) if d.get("completed_at") else None
        pop = "sprint" if d.get("agent") == SPRINT_AGENT else "development"
        out_path = Path(d["output_path"]) if d.get("output_path") else None
        r = {"runner": "delegate_deepinfra", "task": d.get("task", ""), "model": d.get("model", ""), "in": u.get("input_tokens", 0), "out": u.get("output_tokens", 0),
             "cost": d.get("estimated_cost_usd") or 0, "secs": round((d.get("latency_ms") or 0) / 1000, 1), "finish": d.get("finish_reason") or d.get("status", ""),
             "path": out_path, "src": "receipt " + d.get("run_id", ""), "cost_basis": "runner rate card (estimate; failed calls at reserve)",
             "status": d.get("status", ""), "run_id": d.get("run_id", ""), "agent": d.get("agent") or ""}
        link = find_launch(threads, "delegate_deepinfra", r["task"], "", start) if pop == "development" else None
        ev = _event("", pop, r, start, term, link, claude, threads, needle=d.get("run_id", ""))
        events.append(ev)

    write_csv(DATA / "delegate_events.csv", events)
    write_csv(DATA / "delegate_launch_audit.csv", audit)
    ev_dev = [e for e in events if e["population"] == "development"]
    inv = {
        "calls_by_family_runner_status": dict(Counter(f"{e['family'] or 'unlinked'}|{e['runner']}|{e['status']}" for e in ev_dev)),
        "development_calls": len(ev_dev),
        "development_cost_usd_by_runner": {k: round(sum(e["cost_usd"] for e in ev_dev if e["runner"] == k), 4) for k in sorted({e["runner"] for e in ev_dev})},
        "sprint_calls": sum(1 for e in events if e["population"] == "sprint"),
        "launch_commands_by_family_kind": dict(Counter(f"{a['family']}|{a['kind']}" for a in audit)),
        "launch_return_states": dict(Counter(f"{a['family']}|{a['return_state']}" for a in audit if a["kind"] == "launch")),
        "calls_linked_to_a_launch": sum(1 for e in ev_dev if e["ts_launch"]),
        "calls_with_output_reread": sum(1 for e in ev_dev if e["first_read_ts"]),
        "launch_return_precedes_real_completion": sum(1 for e in ev_dev if e["return_before_completion_s"] not in ("", None) and float(e["return_before_completion_s"]) > 0),
    }
    (DATA / "delegate_inventory.json").write_text(json.dumps(inv, indent=1, sort_keys=True), encoding="utf-8", newline="\n")
    print(json.dumps(inv, indent=1, sort_keys=True))
    return 0


def _event(family, population, r, start, term, link, claude, threads, needle=""):
    th, c, cid = link if link else (None, None, None)
    fam = th["family"] if th else family
    ret = th["results"].get(cid) if th else None
    name = r["path"].name if r.get("path") else ""
    needle = needle or name
    rd = first_read(threads, th, needle, max(term, c["ts"]) if (term and c) else (term or start)) if (needle and term) else None
    # when the agent could first have had the result: the call's real end, and for a shell call that blocked, the moment it returned
    avail = term
    if term and ret and outcome(ret[1]) != "yielded":
        avail = max(term, ret[0])
    return {
        "result_available_ts": iso(avail),
        "family": fam, "population": population, "runner": r["runner"], "task": r["task"], "model": r["model"], "status": r.get("status") or ("completed" if r["src"].startswith("scratchpad") else ""),
        "finish": r["finish"], "input_tokens": r["in"], "output_tokens": r["out"], "cost_usd": r["cost"], "cost_basis": r["cost_basis"], "record": r["src"],
        "thread": th["id"][-8:] if th else "", "ts_launch": iso(c["ts"]) if c else "", "launch_background": c["bg"] if c else "",
        "launch_return_ts": iso(ret[0]) if ret else "", "launch_return_state": outcome(ret[1]) if ret else "",
        "call_start": iso(start), "call_end": iso(term), "call_secs": r["secs"],
        "return_before_completion_s": round((term - ret[0]).total_seconds(), 1) if (ret and term) else "",
        "first_read_ts": iso(rd[0]) if rd else "", "read_lag_s": round((rd[0] - term).total_seconds(), 1) if (rd and term) else "",
        "read_by_other_thread": bool(rd and th and rd[1] is not th),
    }


if __name__ == "__main__":
    raise SystemExit(main())
