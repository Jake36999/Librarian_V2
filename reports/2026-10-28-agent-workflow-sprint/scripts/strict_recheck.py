"""Revision 2: re-check saved quotes with the exact-page rule.

The first pass accepted a quote within one page of the cited page. This script checks (a) every first-pass method card and
(b) the 25 source anchors proposed by the second-pass review, against this sprint's own text extraction, with the strict rule:
`verified` = quote on the cited page (or starting there and running onto the next); `adjacent_page`; `quote_elsewhere`; `unverified`.
Run with the repository venv. Output: data/strict_page_recheck.csv, data/strict_page_recheck.json
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_anchors import DATA, REPO, TMP, check_page_strict, split_pages  # noqa: E402

SECOND_PASS = Path(r"D:\Librarian_V2\reports\2026-10-28-agent-workflow-second-pass\data\supplement_methods.json")


def main() -> int:
    inv = list(csv.DictReader((DATA / "papers_inventory.csv").open(encoding="utf-8")))
    by_file = {}
    for r in inv:
        f = (r.get("file") or r.get("filename") or "").strip()
        if f:
            by_file[f] = r.get("slug") or r.get("id") or ""
    cache: dict[str, dict[int, str]] = {}

    def pages_of(slug: str):
        if slug not in cache:
            p = TMP / "src" / "papers" / f"{slug}.txt"
            cache[slug] = split_pages(p) if p.exists() else {}
        return cache[slug]

    call_file = {c["id"]: Path(c["files"][0]).stem for c in json.loads((TMP / "lanes" / "calls_p2.json").read_text(encoding="utf-8"))}
    rows = []
    for line in (DATA / "method_cards.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        slug = call_file.get(c.get("call", ""), "")  # the model's own "paper" field is unreliable; the call names the file it read
        pg = pages_of(slug)
        status, at = check_page_strict(c, pg) if pg else ("no_text", None)
        rows.append({"source": "first_pass_card", "paper": slug[:40], "page": c.get("page"), "first_pass_class": c.get("verified", ""), "strict_class": status})
    if SECOND_PASS.exists():
        for a in json.loads(SECOND_PASS.read_text(encoding="utf-8")):
            slug = by_file.get(a["file"], "")
            pg = pages_of(slug) if slug else {}
            status, at = check_page_strict({"page": a["page"], "quote": a["quote"]}, pg) if pg else ("no_text", None)
            rows.append({"source": "second_pass_anchor", "paper": slug[:40] or a["file"][:40], "page": a["page"], "first_pass_class": "", "strict_class": status})
    out = DATA / "strict_page_recheck.csv"
    with out.open("w", encoding="utf-8", newline="") as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    summary = {}
    for src in ("first_pass_card", "second_pass_anchor"):
        sel = [r for r in rows if r["source"] == src]
        summary[src] = {"n": len(sel), "strict": dict(Counter(r["strict_class"] for r in sel))}
        if src == "first_pass_card":
            summary[src]["by_first_pass_class"] = {k: dict(Counter(r["strict_class"] for r in sel if r["first_pass_class"] == k)) for k in sorted({r["first_pass_class"] for r in sel})}
    (DATA / "strict_page_recheck.json").write_text(json.dumps(summary, indent=1, sort_keys=True), encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
