"""1d: Codex rollout metrics. Metadata only: numbers, timestamps, enums and IDs.

Usage: python -I codex_log_metrics.py [cwd-filter]   (default D:\\Librarian_V2)
Outputs: data/codex_threads.csv, codex_requests.csv, codex_events.csv, codex_commits.csv, codex_delegates.csv

Forked and spawned threads replay their parent's history before
`subagent_history_start_ordinal`; events below that ordinal are inherited copies and are
ignored, so every counted event belongs to exactly one thread.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CODEX_SESSIONS, DATA, command_category, epoch_iso, find_commits, top_category, write_csv  # noqa: E402

# `tools.exec_command({"cmd":"..."})` and the object-literal form `({cmd:"..."})` both occur.
CMD = re.compile(r'\bcmd["\']?\s*:\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|`(?:[^`\\]|\\.)*`)')
WALL = re.compile(r"Wall time ([0-9.]+) seconds")
ORCH = ("spawn_agent", "wait_agent", "send_message", "followup_task", "list_agents", "interrupt_agent", "request_user_input", "wait")


def kind_of(source) -> str:
    if source == "vscode":
        return "main"
    blob = json.dumps(source)
    if "guardian" in blob:
        return "guardian"
    if "thread_spawn" in blob:
        return "worker"
    return "other"


def out_text(payload: dict) -> str:
    out = payload.get("output")
    if isinstance(out, list):
        return " ".join(x.get("text", "") for x in out if isinstance(x, dict))
    return str(out or "")


def decode_cmds(body: str) -> str:
    cmds = []
    for raw in CMD.findall(body):
        inner = raw[1:-1]
        if raw[0] == '"':
            try:
                cmds.append(json.loads(raw))
                continue
            except ValueError:
                pass
        cmds.append(inner.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\"))
    return "\n".join(cmds)


def parse_delegate(cmd: str) -> dict:
    def grab(flag):
        m = re.search(r"--" + flag + r"[ =]+['\"]?([^\s'\"]+)", cmd)
        return m.group(1) if m else ""
    return {"task": grab("task"), "model": grab("model"), "agent": grab("agent"), "max_output_tokens": grab("max-output-tokens")}


def main() -> int:
    cwd_filter = sys.argv[1] if len(sys.argv) > 1 else "D:\\Librarian_V2"
    threads, requests, events, commits, delegates = [], [], [], [], []
    for path in sorted(glob.glob(str(CODEX_SESSIONS / "2026" / "*" / "*" / "rollout-*.jsonl"))):
        with open(path, encoding="utf-8", errors="replace") as handle:
            first = handle.readline()
            try:
                meta = json.loads(first).get("payload", {})
            except ValueError:
                continue
            if meta.get("cwd") != cwd_filter:
                continue
            tid = meta.get("id", "")
            kind = kind_of(meta.get("source"))
            cutoff = meta.get("subagent_history_start_ordinal")
            handle.seek(0)
            first_ts = last_ts = None
            models, cats, triggers = Counter(), Counter(), Counter()
            orch, friction = Counter(), Counter()
            tot = Counter()
            cum_max = 0
            first_offset = None  # the thread counter just before this file's first counted request (a fork or a branch starts above zero)
            calls: dict[str, dict] = {}
            pending: list[str] = []
            last_rl: dict = {}
            n_started = n_complete = n_limit = n_abort = n_compact = n_assistant = dup_events = 0
            for raw in handle:
                try:
                    o = json.loads(raw)
                except ValueError:
                    continue
                ts = o.get("timestamp")
                ordv = o.get("ordinal")
                if cutoff is not None and ordv is not None and ordv < cutoff:
                    continue
                if ts:
                    first_ts = ts if first_ts is None or ts < first_ts else first_ts
                    last_ts = ts if last_ts is None or ts > last_ts else last_ts
                t = o.get("type")
                p = o.get("payload") or {}
                pt = p.get("type") if isinstance(p, dict) else None
                if t == "turn_context":
                    models[p.get("model", "")] += 1
                elif t == "compacted":
                    n_compact += 1
                    events.append({"ts": ts, "thread": tid, "kind": "compaction", "window_number": p.get("window_number", "")})
                elif t == "event_msg" and pt == "task_started":
                    n_started += 1
                    triggers[str((p.get("turn_attribution") or {}).get("turn_trigger", ""))] += 1
                    events.append({"ts": ts, "thread": tid, "kind": "task_started", "turn_id": p.get("turn_id", ""),
                                   "trigger": (p.get("turn_attribution") or {}).get("turn_trigger", ""),
                                   "context_window": p.get("model_context_window", "")})
                elif t == "event_msg" and pt == "task_complete":
                    n_complete += 1
                    err = p.get("error") or {}
                    code = err.get("codex_error_info") if isinstance(err, dict) else ""
                    row = {"ts": ts, "thread": tid, "kind": "usage_limit" if code == "usage_limit_exceeded" else ("task_error" if code else "task_complete"),
                           "turn_id": p.get("turn_id", ""), "duration_ms": p.get("duration_ms", ""), "ttft_ms": p.get("time_to_first_token_ms", ""),
                           "error_code": code or ""}
                    if code == "usage_limit_exceeded":
                        n_limit += 1
                        row.update({"used_primary": (last_rl.get("primary") or {}).get("used_percent", ""),
                                    "used_secondary": (last_rl.get("secondary") or {}).get("used_percent", ""),
                                    "resets_primary": epoch_iso((last_rl.get("primary") or {})["resets_at"]) if (last_rl.get("primary") or {}).get("resets_at") else "",
                                    "resets_secondary": epoch_iso((last_rl.get("secondary") or {})["resets_at"]) if (last_rl.get("secondary") or {}).get("resets_at") else ""})
                    events.append(row)
                elif t == "event_msg" and pt == "turn_aborted":
                    n_abort += 1
                    events.append({"ts": ts, "thread": tid, "kind": "turn_aborted", "turn_id": p.get("turn_id", ""), "reason": p.get("reason", "")})
                elif t == "event_msg" and pt == "token_count":
                    info = p.get("info") or {}
                    rl = p.get("rate_limits") or {}
                    if rl:
                        last_rl = rl
                    last = info.get("last_token_usage") or {}
                    total = info.get("total_token_usage") or {}
                    cum_now = int(total.get("total_tokens") or 0)
                    if last and cum_now and cum_now <= cum_max:
                        # Codex sometimes logs the same request twice (same cumulative total, same last_token_usage);
                        # a real request always moves the thread's cumulative counter, so count only events that do.
                        dup_events += 1
                        continue
                    if last:
                        if first_offset is None:
                            first_offset = cum_now - int(last.get("total_tokens") or 0)
                        cum_max = max(cum_max, cum_now)
                        for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens"):
                            tot[key] += int(last.get(key) or 0)
                        prim, sec = rl.get("primary") or {}, rl.get("secondary") or {}
                        category = "guardian" if kind == "guardian" else top_category(pending)
                        requests.append({
                            "ts": ts, "thread": tid, "kind": kind, "model": models.most_common(1)[0][0] if models else "",
                            "input_tokens": last.get("input_tokens", 0), "cached_input_tokens": last.get("cached_input_tokens", 0),
                            "output_tokens": last.get("output_tokens", 0), "reasoning_tokens": last.get("reasoning_output_tokens", 0),
                            "total_tokens": last.get("total_tokens", 0), "context_window": info.get("model_context_window", ""),
                            "used_primary": prim.get("used_percent", ""), "used_secondary": sec.get("used_percent", ""),
                            "resets_primary": epoch_iso(prim["resets_at"]) if prim.get("resets_at") else "",
                            "resets_secondary": epoch_iso(sec["resets_at"]) if sec.get("resets_at") else "",
                            "plan_type": rl.get("plan_type", ""), "category": category, "n_calls": len(pending),
                        })
                    cats[top_category(pending) if kind != "guardian" else "guardian"] += 1
                    pending = []
                elif t == "response_item" and pt in ("function_call", "custom_tool_call"):
                    name = p.get("name", "")
                    body = p.get("input") if pt == "custom_tool_call" else p.get("arguments")
                    body = str(body or "")
                    if name in ORCH:
                        orch[name] += 1
                        pending.append("subagent")
                        calls[p.get("call_id")] = {"cat": "subagent", "ts": ts}
                    else:
                        cmd = decode_cmds(body) if name == "exec" else body
                        cat = command_category(cmd + " " + ("apply_patch" if "apply_patch" in body else ""))
                        pending.append(cat)
                        calls[p.get("call_id")] = {"cat": cat, "ts": ts, "cmd": cmd if cat == "delegate" else ""}
                elif t == "response_item" and pt in ("function_call_output", "custom_tool_call_output"):
                    use = calls.get(p.get("call_id"))
                    text = out_text(p)
                    if "Permission denied" in text and ".git" in text:
                        friction["git_permission_denied"] += 1
                    if "index.lock" in text:
                        friction["index_lock"] += 1
                    if use and use["cat"] == "commit":
                        for found in find_commits(text, ts) or [""]:
                            commits.append({"ts": ts, "thread": tid, "kind": kind, "commit": found, "joined": bool(found)})
                    if use and use["cat"] == "delegate":
                        delegates.append({"ts_call": use["ts"], "ts_result": ts, "thread": tid, "kind": kind, **parse_delegate(use.get("cmd", ""))})
                    if use:
                        wm = WALL.search(text)
                        if wm:
                            cats["_wall_s_" + use["cat"]] += float(wm.group(1))
                elif t == "response_item" and pt == "message" and p.get("role") == "assistant":
                    n_assistant += 1
            threads.append({
                "thread": tid, "session": meta.get("session_id", ""), "kind": kind, "nickname": meta.get("agent_nickname", ""),
                "agent_path": meta.get("agent_path", ""), "forked_from": meta.get("forked_from_id", ""), "parent": meta.get("parent_thread_id", ""),
                "cutoff_ordinal": cutoff if cutoff is not None else "", "file": os.path.basename(path), "file_bytes": os.path.getsize(path),
                "first_ts": first_ts, "last_ts": last_ts, "models": json.dumps(dict(models), sort_keys=True),
                "requests": sum(1 for r in requests if r["thread"] == tid), "input_tokens": tot["input_tokens"],
                "cached_input_tokens": tot["cached_input_tokens"], "output_tokens": tot["output_tokens"],
                "reasoning_tokens": tot["reasoning_output_tokens"], "total_tokens": tot["total_tokens"], "cumulative_total_max": cum_max, "counter_offset": first_offset if first_offset is not None else "", "duplicate_token_events": dup_events,
                "task_started": n_started, "task_complete": n_complete, "usage_limit_events": n_limit, "turn_aborted": n_abort,
                "compactions": n_compact, "assistant_messages": n_assistant, "turn_triggers": json.dumps(dict(triggers), sort_keys=True),
                "orchestration_calls": json.dumps(dict(orch), sort_keys=True), "request_categories": json.dumps({k: v for k, v in cats.items() if not k.startswith("_")}, sort_keys=True),
                "tool_wall_seconds": json.dumps({k[8:]: round(v, 1) for k, v in cats.items() if k.startswith("_wall_s_")}, sort_keys=True),
                "friction": json.dumps(dict(friction), sort_keys=True),
            })
    threads.sort(key=lambda r: r["first_ts"] or "")
    requests.sort(key=lambda r: (r["ts"] or "", r["thread"]))
    events.sort(key=lambda r: (r.get("ts") or "", r["thread"]))
    write_csv(DATA / "codex_threads.csv", threads)
    write_csv(DATA / "codex_requests.csv", requests)
    write_csv(DATA / "codex_events.csv", events)
    write_csv(DATA / "codex_commits.csv", commits)
    write_csv(DATA / "codex_delegates.csv", delegates)
    print(f"threads={len(threads)} requests={len(requests)} events={len(events)} commits={len(commits)} delegates={len(delegates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
