"""Revision 2: render the curated tables of 04-extraction-table.md from data/lit2_curation.csv and data/lit2_items.csv.

Each curated row names a paper (first-pass rank), an item field and a substring that identifies one anchor-verified item of the primary
reader; the paper, section, page and claim are copied from that item, so every citation is exact. Only the last column, the
Librarian hypothesis, is hand-written. Rows whose match is not found fail loudly. Output: tmp/sprint/out/04_tables.md and
data/lit2_curated_rows.csv (with the verbatim quote of each row).
"""
from __future__ import annotations

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, TMP, write_csv  # noqa: E402

SECTIONS = [
    ("A", "A. Metrics for agent and orchestration performance", "methods"),
    ("B", "B. Schemas for deploying and running agents on different kinds of task", "methods"),
    ("C", "C. Long-horizon planning, drift and memory management", "methods"),
    ("D", "D. Communication-efficient multi-agent cooperation", "methods"),
    ("E", "E. Verification, grounding and deterministic checking", "methods"),
    ("COST", "F. What verification, coordination and generation cost (as the papers report it)", "costs"),
    ("NEG", "G. Negative, null and failed-transfer results", "negative_results"),
    ("LIM", "H. Limitations, assumptions and reproducibility notes that travel with the methods", "limitations"),
]


def esc(s: str, n: int) -> str:
    s = " ".join((s or "").replace("|", "/").split())
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "..."


def main() -> int:
    items = [r for r in csv.DictReader((DATA / "lit2_items.csv").open(encoding="utf-8")) if r["reader"] == "MiMo-V2.6-Pro" and r["verified"] == "verified"]
    titles = {int(r["rank"]): r["title"] for r in csv.DictReader((DATA / "lit2_papers.csv").open(encoding="utf-8"))}
    cur = list(csv.DictReader((DATA / "lit2_curation.csv").open(encoding="utf-8")))
    out, rows, missing = [], [], []
    for key, heading, _field in SECTIONS:
        sel = [c for c in cur if c["group"] == key]
        if not sel:
            continue
        out += [f"## {heading}", "", "| Item | Source (paper, section, page) | What the paper reports | Applies to Librarian (Hypothesis) |", "|---|---|---|---|"]
        for c in sel:
            fields = [c["field"]] + (["reproducibility"] if key == "LIM" and c["field"] == "limitations" else [])
            hit = next((i for i in items if int(i["rank"]) == int(c["rank"]) and i["field"] in fields and c["match"].lower() in (i["label"] + " " + i["claim"] + " " + i["results"]).lower()), None)
            if hit is None and key == "LIM":
                hit = next((i for i in [r for r in csv.DictReader((DATA / "lit2_items.csv").open(encoding="utf-8")) if r["reader"] == "MiMo-V2.6-Pro" and r["verified"] == "verified"]
                            if int(i["rank"]) == int(c["rank"]) and i["field"] in ("limitations", "reproducibility") and c["match"].lower() in (i["label"] + " " + i["claim"]).lower()), None)
            if hit is None:
                missing.append((c["group"], c["rank"], c["match"]))
                continue
            sec = f", {esc(hit['section'], 50)}" if hit["section"] else ""
            what = hit["results"] if key in ("A", "B", "C", "D", "E") and hit["results"] not in ("", "not_reported") else hit["claim"]
            name = hit["label"] or hit["field"].replace("_", " ")
            if key in ("A", "B", "C", "D", "E"):
                what = f"{esc(hit['claim'], 150)} Result: {esc(what, 150)}" if what != hit["claim"] else esc(hit["claim"], 280)
            else:
                what = esc(hit["claim"], 260)
            out.append(f"| {esc(name, 48)} | #{int(c['rank']):02d} {esc(titles.get(int(c['rank']), ''), 38)}{sec}, p. {hit['page']} | {what} | {esc(c['hypothesis'], 260)} |")
            rows.append({"group": key, "rank": c["rank"], "field": hit["field"], "item": name, "page": hit["page"], "section": hit["section"], "quote": hit["quote"], "hypothesis": c["hypothesis"]})
        out.append("")
    (TMP / "out" / "04_tables.md").write_text("\n".join(out), encoding="utf-8", newline="\n")
    write_csv(DATA / "lit2_curated_rows.csv", rows)
    print("curated rows rendered:", len(rows), "| not found:", missing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
