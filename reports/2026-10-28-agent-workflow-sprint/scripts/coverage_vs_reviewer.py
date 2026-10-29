"""Revision 2, M8e (partial): coverage of the full-text readings against an independent checklist.

The second-pass reviewer chose 25 passages (rank, page, short quote) as the methods, costs and caveats the first pass missed. They were
chosen by a different reader of the papers, so they are an independent checklist, though a small and selective one. For each anchor this
script asks whether any reader's anchor-verified item on the same or an adjacent page contains the anchor's words.
Output: data/coverage_vs_reviewer.csv, data/coverage_vs_reviewer.json
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA  # noqa: E402

SECOND_PASS = Path(r"D:\Librarian_V2\reports\2026-10-28-agent-workflow-second-pass\data\supplement_methods.json")


def words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9%]{3,}", (s or "").lower().replace("\ufb02", "fl").replace("\ufb01", "fi"))}


def main() -> int:
    anchors = json.loads(SECOND_PASS.read_text(encoding="utf-8"))
    items = [r for r in csv.DictReader((DATA / "lit2_items.csv").open(encoding="utf-8")) if r["verified"] in ("verified", "adjacent_page")]
    rows = []
    for a in anchors:
        aw = words(a["quote"])
        best = {"MiMo-V2.6-Pro": 0.0, "other": 0.0}
        for i in items:
            if int(i["rank"]) != int(a["rank"]) or abs(int(i["page"] or 0) - int(a["page"])) > 1:
                continue
            blob = words(" ".join([i["quote"], i["claim"], i["label"], i["results"]]))
            share = len(aw & blob) / max(1, len(aw))
            key = "MiMo-V2.6-Pro" if i["reader"] == "MiMo-V2.6-Pro" else "other"
            best[key] = max(best[key], share)
        rows.append({"rank": a["rank"], "page": a["page"], "method": a["method"], "quote": a["quote"], "primary_share": round(best["MiMo-V2.6-Pro"], 2), "second_reader_share": round(best["other"], 2),
                     "found_primary": best["MiMo-V2.6-Pro"] >= 0.75, "found_any": max(best.values()) >= 0.75})
    adj_path = DATA / "coverage_adjudication.csv"
    adj = {(int(r["rank"]), int(r["page"]), r["method"]): r for r in csv.DictReader(adj_path.open(encoding="utf-8"))} if adj_path.exists() else {}
    for r in rows:
        a = adj.get((int(r["rank"]), int(r["page"]), r["method"]))
        r["adjudicated_equivalent_found"] = (a["equivalent_found"] if a else "")
        r["found_after_adjudication"] = bool(r["found_any"] or (a and a["equivalent_found"] == "yes"))
    with (DATA / "coverage_vs_reviewer.csv").open("w", encoding="utf-8", newline="") as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    summary = {"anchors": len(rows), "found_by_primary_reader": sum(r["found_primary"] for r in rows), "found_by_any_reader": sum(r["found_any"] for r in rows), "found_after_adjudication": sum(r["found_after_adjudication"] for r in rows), "adjudicated_rows": len(adj),
               "rule": "share of the anchor's words (3+ characters) contained in a verified item on the same or an adjacent page; found = at least 75%",
               "missed_by_all": [(r["rank"], r["page"], r["method"]) for r in rows if not r["found_after_adjudication"]]}
    (DATA / "coverage_vs_reviewer.json").write_text(json.dumps(summary, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
