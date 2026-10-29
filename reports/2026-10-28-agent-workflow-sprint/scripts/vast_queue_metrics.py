"""1g: hosted-compute prior art from the G:\\vast queue controller (Vast.ai boxes, 2026-10-25).

Outputs: data/vast_events.csv, data/vast_boxes.csv, data/vast_summary.json
Only whitelisted fields are extracted. The log contains a plaintext instance API key in an
error line (line 4); that line is matched only for the word "create failed" and its content
is never copied. IP addresses and ports in the state file are not read.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, epoch_iso, write_csv, write_json  # noqa: E402

VAST = Path(r"G:\vast")
LINE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) (.*)$")
PATTERNS = [
    ("controller_start", re.compile(r"^controller start; cap \$([0-9.]+); spent so far \$([0-9.]+)")),
    ("rented", re.compile(r"^box (\w): rented (Tesla [A-Z0-9a-z ]+?) (\d+) at \$([0-9.]+)/h \(([^)]*)\)")),
    ("create_failed", re.compile(r"^box (\w): create failed")),
    ("step_error", re.compile(r"^box (\w): step error (\w+)")),
    ("start_failed", re.compile(r"^box (\w): start failed \((\w+)\)")),
    ("runner_launch", re.compile(r"^box (\w): runner launch: (\w+)")),
    ("runner_up", re.compile(r"^box (\w): runner already up")),
    ("running_jobs", re.compile(r"^box (\w): running (.+)$")),
    ("collected", re.compile(r"^box (\w): collected (\S+) \(([0-9.]+) MB\)")),
    ("destroyed", re.compile(r"^box (\w): destroyed instance \d+ \(([^)]*)\)")),
]
VERDICT = re.compile(r"-> (PASS|FAIL)")


def main() -> int:
    state = json.loads((VAST / "cloud_state.json").read_text(encoding="utf-8"))
    events = []
    for raw in (VAST / "cloud_queue.log").read_text(encoding="utf-8", errors="replace").splitlines():
        m = LINE.match(raw)
        if not m:
            continue
        ts, rest = m.groups()
        for kind, pat in PATTERNS:
            hit = pat.match(rest)
            if not hit:
                continue
            g = hit.groups()
            row = {"ts_local": ts, "kind": kind}
            if kind == "controller_start":
                row.update({"cap_usd": g[0], "spent_usd": g[1]})
            elif kind == "rented":
                row.update({"box": g[0], "gpu": g[1], "machine": g[2], "dph": g[3], "region": g[4].split(",")[-1].strip()})
            elif kind in ("create_failed", "runner_up"):
                row.update({"box": g[0]})
            elif kind in ("step_error", "start_failed", "runner_launch", "destroyed"):
                row.update({"box": g[0] if kind != "destroyed" else g[0], "detail": g[1] if kind != "destroyed" else g[1][:80]})
            elif kind == "running_jobs":
                row.update({"box": g[0], "jobs": len(g[1].split())})
            elif kind == "collected":
                v = VERDICT.search(rest)
                row.update({"box": g[0], "job": g[1], "mb": g[2], "registered": "REGISTERED" in rest, "verdict": v.group(1) if v else ""})
            events.append(row)
            break
    # The log's wall clock vs the epoch stamps in the state file (box A creation) gives the offset.
    first_rent = next(e for e in events if e["kind"] == "rented" and e["box"] == "A")
    created_a = datetime.fromtimestamp(state["boxes"]["A"]["created"], tz=timezone.utc).replace(tzinfo=None)
    logged_a = datetime.strptime(first_rent["ts_local"], "%Y-%m-%d %H:%M:%S")
    offset_s = round((logged_a - created_a).total_seconds())
    boxes = []
    for name, b in sorted(state["boxes"].items()):
        rented = next((e for e in events if e["kind"] == "rented" and e["box"] == name), None)
        destroyed = [e for e in events if e["kind"] == "destroyed" and e["box"] == name]
        t0 = datetime.strptime(rented["ts_local"], "%Y-%m-%d %H:%M:%S") if rented else None
        t1 = datetime.strptime(destroyed[-1]["ts_local"], "%Y-%m-%d %H:%M:%S") if destroyed else None
        hours = round((t1 - t0).total_seconds() / 3600, 2) if t0 and t1 else ""
        boxes.append({"box": name, "phase": b.get("phase"), "gpu": b.get("gpu"), "dph": round(b.get("dph", 0), 4), "region": (b.get("where", "").split(",")[-1].strip()),
                      "jobs_done": len(b.get("done_jobs", [])), "created_utc": epoch_iso(b["created"]), "destroy_reason": destroyed[-1]["detail"] if destroyed else "",
                      "rented_hours": hours, "est_cost_usd": round(hours * b.get("dph", 0), 2) if hours != "" else ""})
    collected = [e for e in events if e["kind"] == "collected"]
    reg = [e for e in collected if e["registered"]]
    ts_all = [datetime.strptime(e["ts_local"], "%Y-%m-%d %H:%M:%S") for e in events]
    prov = []
    for e in events:
        if e["kind"] == "runner_up":
            r = next((x for x in events if x["kind"] == "rented" and x["box"] == e["box"] and x["ts_local"] <= e["ts_local"]), None)
            if r:
                prov.append(round((datetime.strptime(e["ts_local"], "%Y-%m-%d %H:%M:%S") - datetime.strptime(r["ts_local"], "%Y-%m-%d %H:%M:%S")).total_seconds() / 60, 1))
    summary = {
        "provisioning_minutes_rent_to_runner_up": prov,
        "log_minus_epoch_offset_seconds": offset_s, "boxes_rented": sum(1 for e in events if e["kind"] == "rented"),
        "create_failures": sum(1 for e in events if e["kind"] == "create_failed"), "start_failures": sum(1 for e in events if e["kind"] == "start_failed"),
        "step_errors": sum(1 for e in events if e["kind"] == "step_error"), "boxes_final_phase": {b["box"]: b["phase"] for b in boxes},
        "boxes_with_zero_output": [b["box"] for b in boxes if b["jobs_done"] == 0], "jobs_collected": len(collected), "jobs_registered": len(reg),
        "registered_pass": sum(1 for e in reg if e["verdict"] == "PASS"), "registered_fail": sum(1 for e in reg if e["verdict"] == "FAIL"),
        "spent_closed_usd": round(state.get("spent_closed", 0), 2), "cap_usd_first": events[0].get("cap_usd"), "cap_usd_last": [e for e in events if e["kind"] == "controller_start"][-1]["cap_usd"],
        "usd_per_collected_job": round(state.get("spent_closed", 0) / max(1, len(collected)), 3),
        "wall_hours_first_event_to_last": round((max(ts_all) - min(ts_all)).total_seconds() / 3600, 2),
        "controller_restarts": sum(1 for e in events if e["kind"] == "controller_start") - 1,
        "boxes_destroyed_unfinished_at_cap": [e["box"] for e in events if e["kind"] == "destroyed" and ("credit" in e.get("detail", "") or "cap" in e.get("detail", ""))],
    }
    write_csv(DATA / "vast_events.csv", events)
    write_csv(DATA / "vast_boxes.csv", boxes)
    write_json(DATA / "vast_summary.json", summary)
    print(json.dumps(summary, indent=1)[:1400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
