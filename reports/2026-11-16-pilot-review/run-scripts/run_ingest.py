"""Sequential, budget-capped ingestion driver for one library (owner approval 2026-11-16).

One round: queue the next N newest documents of a folder -> intake them -> approve the
normal-sensitivity Sources this round staged -> run the approved batch -> report spend.
Stops when the library's [budget] ceiling stops intake or the batch, or the folder is done.
Never prints the Core token. Every round is appended to a JSONL log for the report.
"""
import json, sys, time, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from core import call, tool

LOG = Path(__file__).parent / "ingest-log.jsonl"


def note(**row):
    row["t"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(LOG, "a", encoding="utf-8") as h:
        h.write(json.dumps(row) + "\n")
    print(json.dumps(row)[:1500], flush=True)


def balance(v):
    u = call(v, "GET", "/api/usage?provider=deepinfra")
    return u.get("balance")


def budget(v):
    # spend as the Core's own ceiling sees it
    return call(v, "GET", "/api/meta").get("budget") or {}


def staged_sources(v):
    out, offset = [], 0
    while True:
        page = tool(v, "staging_list", {"kind": "source", "status": "staged", "limit": 200, "offset": offset})
        rows = page.get("items") or []
        out += rows
        if len(rows) < 200:
            return out
        offset += 200


def wait_batch(v, poll=30):
    while True:
        s = tool(v, "batch_status")
        if s.get("status") != "running":
            return s
        time.sleep(poll)


def round_(v, folder, limit, scope, phase, adopt=False):
    before = balance(v)
    seen = set() if adopt else {r["id"] for r in staged_sources(v)}
    q = call(v, "POST", "/api/folders/sources", {"folder": folder, "limit": limit, "scope": scope, "order": "newest"})
    if "http_error" in q:
        note(phase=phase, step="queue", error=q); return "error"
    queued = q.get("queued", 0)
    intake = tool(v, "intake_run", {"limit": max(queued, 1) + 5}, timeout=7200)
    staged = [r for r in staged_sources(v) if r["id"] not in seen]
    normal = [r["id"] for r in staged if r.get("sensitivity", "normal") == "normal"]
    held = [r["id"] for r in staged if r.get("sensitivity", "normal") != "normal"]
    if normal:
        d = tool(v, "staging_decide", {"item_ids": normal, "decision": "approve",
                                        "reason": "owner instruction in chat 2026-11-16 (budgeted ingestion), applied by agent Claude via the person route"})
        if "error" in d:
            note(phase=phase, step="approve", error=str(d)[:600])
    started = tool(v, "process_approved", {"background": True}) if normal else {}
    final = wait_batch(v) if started.get("started") else {}
    items = final.get("items") or []
    after = balance(v)
    note(phase=phase, folder=folder, queued=queued, remaining=q.get("remaining"),
         intake_processed=intake.get("processed"), intake_stopped=intake.get("stopped", ""),
         approved=len(normal), held_sensitive=held, run=final.get("run", ""),
         batch_status=final.get("status", ""), batch_detail=final.get("detail", ""),
         item_status={k: sum(1 for i in items if i.get("status") == k) for k in {i.get("status") for i in items}},
         balance_before=before, balance_after=after,
         account_delta=(None if before is None or after is None else round(before - after, 4)))
    if intake.get("stopped") or "budget" in str(final.get("detail", "")):
        return "ceiling"
    if not queued and not normal:
        return "done"
    return "more"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("vault"); ap.add_argument("folder"); ap.add_argument("phase")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--scope", default=".pdf,.md")
    ap.add_argument("--rounds", type=int, default=1000)
    ap.add_argument("--adopt-staged", action="store_true", help="first round also approves sources already staged")
    a = ap.parse_args()
    scope = a.scope.split(",")
    for n in range(a.rounds):
        state = round_(a.vault, a.folder, a.limit, scope, a.phase, adopt=a.adopt_staged and n == 0)
        if state != "more":
            note(phase=a.phase, step="stopped", reason=state, rounds=n + 1)
            break
