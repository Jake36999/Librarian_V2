"""1c: Claude Code session-log metrics. Metadata only: numbers, timestamps, enums and IDs.

Usage: python -I claude_log_metrics.py <project-dir-name> [<output-name>]
Outputs (data/claude_<name>_*.csv): sessions, messages, events, prompts, commits, delegates.
Message text is never written. Assistant records are de-duplicated by message id
(one API response is split over several log lines, each repeating the usage).
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (CLAUDE_PROJECTS, DATA, LIMIT_WORDS, command_category,  # noqa: E402
                    epoch_iso, find_commits, top_category, write_csv)

READ_TOOLS = {"Read", "Grep", "Glob", "LS", "NotebookRead"}
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}
POLL_TOOLS = {"Monitor", "TaskStop", "ScheduleWakeup", "CronCreate"}
USAGE_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


def tool_category(name: str, tool_input: dict) -> tuple[str, str]:
    if name in SHELL_TOOLS:
        cmd = str((tool_input or {}).get("command", ""))
        return command_category(cmd), cmd
    if name in READ_TOOLS:
        return "read", ""
    if name in EDIT_TOOLS:
        return "edit", ""
    if name in ("Agent", "Task"):
        return "subagent", ""
    if name in ("WebSearch", "WebFetch"):
        return "web", ""
    if name in POLL_TOOLS:
        return "poll", ""
    if name == "ToolSearch":
        return "toolsearch", ""
    if name.startswith("mcp__ccd_turn") or name in ("TodoWrite", "TaskCreate", "TaskUpdate", "EnterPlanMode", "ExitPlanMode"):
        return "plan", ""
    if name.startswith("mcp__"):
        return "mcp", ""
    return "other", ""


def result_text(block: dict) -> str:
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(x.get("text", "") for x in content if isinstance(x, dict))
    return ""


def parse_delegate_command(cmd: str) -> dict:
    def grab(flag):
        m = re.search(r"--" + flag + r"[ =]+['\"]?([^\s'\"]+)", cmd)
        return m.group(1) if m else ""
    return {"task": grab("task"), "model": grab("model"), "agent": grab("agent"),
            "max_output_tokens": grab("max-output-tokens"), "files_n": len(re.findall(r"--file[ =]", cmd))}


def parse_delegate_result(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if not isinstance(obj, dict):
                continue
            usage = obj.get("usage") or {}
            for key in ("status", "cost_usd", "committed_total_usd", "model"):
                if key in obj and isinstance(obj[key], (int, float, str)):
                    out[key] = obj[key]
            if isinstance(usage, dict):
                out["input_tokens"] = usage.get("input_tokens", usage.get("prompt_tokens", ""))
                out["output_tokens"] = usage.get("output_tokens", usage.get("completion_tokens", ""))
    return out


def process(project: str, name: str) -> None:
    files = sorted((CLAUDE_PROJECTS / project).glob("*.jsonl"))
    sessions, messages, events, prompts, commits, delegates = [], [], [], [], [], []
    for path in files:
        session = path.stem
        msgs: dict[str, dict] = {}
        uses: dict[str, dict] = {}
        first_ts = last_ts = None
        cwds, branches, models = Counter(), Counter(), Counter()
        n_human = n_tool_results = n_stop_hooks = 0
        with open(path, encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                if not raw.strip():
                    continue
                try:
                    o = json.loads(raw)
                except ValueError:
                    continue
                t = o.get("type")
                ts = o.get("timestamp")
                if ts:
                    first_ts = ts if first_ts is None or ts < first_ts else first_ts
                    last_ts = ts if last_ts is None or ts > last_ts else last_ts
                if o.get("cwd"):
                    cwds[o["cwd"]] += 1
                if o.get("gitBranch"):
                    branches[o["gitBranch"]] += 1
                if t == "assistant":
                    m = o.get("message") or {}
                    mid = m.get("id") or o.get("uuid")
                    rec = msgs.setdefault(mid, {
                        "ts": ts, "request_id": o.get("requestId", ""), "model": m.get("model", ""),
                        "is_sidechain": bool(o.get("isSidechain")), "stop_reason": "", "usage": {k: 0 for k in USAGE_KEYS},
                        "thinking": 0, "tools": [], "cats": [], "is_error": False, "effort": str(o.get("perTurnEffort", "")),
                        "branch": o.get("gitBranch", ""),
                    })
                    if ts and (rec["ts"] is None or ts < rec["ts"]):
                        rec["ts"] = ts
                    usage = m.get("usage") or {}
                    for key in USAGE_KEYS:
                        rec["usage"][key] = max(rec["usage"][key], int(usage.get(key) or 0))
                    det = usage.get("output_tokens_details") or {}
                    rec["thinking"] = max(rec["thinking"], int(det.get("thinking_tokens") or 0))
                    rec["stop_reason"] = m.get("stop_reason") or rec["stop_reason"]
                    if o.get("isApiErrorMessage"):
                        rec["is_error"] = True
                        q = o.get("quotaLimits") or {}
                        events.append({"project": project, "session": session, "ts": ts, "kind": "api_limit",
                                       "http_status": o.get("apiErrorStatus", ""), "api_error": o.get("apiError", ""),
                                       "limit_type": q.get("rateLimitType", ""), "limit_status": q.get("status", ""),
                                       "resets_at": epoch_iso(q["resetsAt"]) if q.get("resetsAt") else "",
                                       "overage_status": q.get("overageStatus", ""), "overage_reason": q.get("overageDisabledReason", "")})
                    for block in m.get("content") or []:
                        if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("id") not in uses:
                            cat, cmd = tool_category(block.get("name", ""), block.get("input") or {})
                            uses[block["id"]] = {"cat": cat, "ts": ts, "msg": mid, "name": block.get("name", ""),
                                                 "delegate": parse_delegate_command(cmd) if cat == "delegate" else None}
                            rec["tools"].append(block.get("name", ""))
                            rec["cats"].append(cat)
                elif t == "user":
                    m = o.get("message") or {}
                    content = m.get("content")
                    blocks = [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []
                    results = [b for b in blocks if b.get("type") == "tool_result"]
                    if results:
                        for block in results:
                            n_tool_results += 1
                            use = uses.get(block.get("tool_use_id"))
                            if not use:
                                continue
                            text = result_text(block)
                            use["latency_s"] = None
                            if use["cat"] == "commit":
                                for found in find_commits(text, ts) or [""]:
                                    commits.append({"project": project, "session": session, "ts": ts, "commit": found, "msg_id": use["msg"],
                                                    "joined": bool(found)})
                            if use["cat"] == "delegate":
                                row = {"project": project, "session": session, "ts_call": use["ts"], "ts_result": ts, **(use["delegate"] or {}), **parse_delegate_result(text)}
                                delegates.append(row)
                    else:
                        if isinstance(content, str):
                            chars, text = len(content), content
                        else:
                            text = " ".join(b.get("text", "") for b in blocks if b.get("type") == "text")
                            chars = len(text)
                        origin = o.get("origin")
                        kind = origin.get("kind", "") if isinstance(origin, dict) else ""
                        if kind != "task-notification":
                            n_human += 1
                        prompts.append({"project": project, "session": session, "ts": ts, "chars": chars, "origin_kind": kind,
                                        "prompt_source": o.get("promptSource", ""), "turn_origin": o.get("turnOrigin", ""),
                                        "limit_report": bool(LIMIT_WORDS.search(text)) and chars < 400})
                elif t == "system":
                    sub = o.get("subtype")
                    if sub == "compact_boundary":
                        cm = o.get("compactMetadata") or {}
                        events.append({"project": project, "session": session, "ts": ts, "kind": "compaction", "trigger": cm.get("trigger", ""),
                                       "pre_tokens": cm.get("preTokens", ""), "post_tokens": cm.get("postTokens", ""),
                                       "duration_ms": cm.get("durationMs", "")})
                    elif sub == "api_error":
                        events.append({"project": project, "session": session, "ts": ts, "kind": "conn_error",
                                       "retry_attempt": o.get("retryAttempt", ""), "max_retries": o.get("maxRetries", ""),
                                       "retry_in_ms": o.get("retryInMs", "")})
                    elif sub == "stop_hook_summary":
                        n_stop_hooks += 1
                elif t == "cost-state":
                    for model, mu in (o.get("modelUsage") or {}).items():
                        events.append({"project": project, "session": session, "ts": ts or "", "kind": "cost_state", "model": model,
                                       "input_tokens": mu.get("inputTokens", ""), "output_tokens": mu.get("outputTokens", ""),
                                       "thinking_tokens": mu.get("thinkingTokens", ""), "cache_read_tokens": mu.get("cacheReadInputTokens", ""),
                                       "cache_creation_tokens": mu.get("cacheCreationInputTokens", ""), "cost_usd": mu.get("costUSD", ""),
                                       "total_duration_ms": o.get("totalDuration", "")})
        cat_counts = Counter()
        tot = Counter()
        for mid, r in msgs.items():
            cats = r["cats"]
            category = "error" if r["is_error"] else top_category(cats)
            cat_counts[category] += 1
            models[r["model"]] += 1
            if not r["is_error"]:
                for k in USAGE_KEYS:
                    tot[k] += r["usage"][k]
                tot["thinking"] += r["thinking"]
            messages.append({
                "project": project, "session": session, "ts": r["ts"], "msg_id": mid, "request_id": r["request_id"], "model": r["model"],
                "is_sidechain": r["is_sidechain"], "stop_reason": r["stop_reason"],
                "input_tokens": r["usage"]["input_tokens"], "cache_creation_tokens": r["usage"]["cache_creation_input_tokens"],
                "cache_read_tokens": r["usage"]["cache_read_input_tokens"], "output_tokens": r["usage"]["output_tokens"],
                "thinking_tokens": r["thinking"], "n_tool_uses": len(r["tools"]), "tools": ";".join(r["tools"]),
                "category": category, "cmd_cats": ";".join(cats), "effort": r["effort"], "is_api_error": r["is_error"],
                "git_branch": r["branch"],
            })
        sessions.append({
            "project": project, "session": session, "file_bytes": path.stat().st_size, "first_ts": first_ts, "last_ts": last_ts,
            "assistant_messages": len(msgs), "human_prompts": n_human, "tool_results": n_tool_results,
            "input_tokens": tot["input_tokens"], "cache_creation_tokens": tot["cache_creation_input_tokens"],
            "cache_read_tokens": tot["cache_read_input_tokens"], "output_tokens": tot["output_tokens"], "thinking_tokens": tot["thinking"],
            "models": json.dumps(dict(models), sort_keys=True), "categories": json.dumps(dict(cat_counts), sort_keys=True),
            "cwds": ";".join(sorted(cwds)), "branches": ";".join(sorted(branches)), "stop_hooks": n_stop_hooks,
        })
    messages.sort(key=lambda r: (r["ts"] or "", r["msg_id"]))
    events.sort(key=lambda r: (r.get("ts") or "", r["kind"]))
    prefix = f"claude_{name}_"
    write_csv(DATA / (prefix + "sessions.csv"), sessions)
    write_csv(DATA / (prefix + "messages.csv"), messages)
    write_csv(DATA / (prefix + "events.csv"), events)
    write_csv(DATA / (prefix + "prompts.csv"), prompts)
    write_csv(DATA / (prefix + "commits.csv"), commits)
    write_csv(DATA / (prefix + "delegates.csv"), delegates)
    print(f"{project}: sessions={len(sessions)} messages={len(messages)} events={len(events)} prompts={len(prompts)} commits={len(commits)} delegates={len(delegates)}")


if __name__ == "__main__":
    project = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else re.sub(r"[^A-Za-z0-9]+", "_", project).strip("_").lower()
    process(project, out)
