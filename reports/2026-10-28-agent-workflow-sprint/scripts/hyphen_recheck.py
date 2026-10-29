"""Revision 2 follow-up: how many full-text items that failed the strict page rule are punctuation or hyphenation false negatives?

The strict rule compares lightly normalised text, so a line break inside a hyphenated word ("VLM- related") defeats it. This script
re-checks every full-text item that did not pass, with a lenient comparison (letters and digits only, lower case) on the exact cited page,
then on that page plus the next one, then on the neighbouring pages. It changes no existing file. Run with the repository venv.
Output: data/hyphen_recheck.csv and data/hyphen_recheck.json
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_anchors import DATA, TMP, split_pages  # noqa: E402


def flat(s: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", s.lower())


def main() -> int:
    items = list(csv.DictReader((DATA / "lit2_items.csv").open(encoding="utf-8")))
    cache: dict[str, dict[int, str]] = {}
    status = Counter(r["verified"] for r in items)
    out = []
    for r in items:
        if r["verified"] == "verified":
            continue
        slug = r["slug"]
        if slug not in cache:
            p = TMP / "src" / "papers" / f"{slug}.txt"
            cache[slug] = {n: flat(t) for n, t in split_pages(p).items()} if p.exists() else {}
        pages = cache[slug]
        q = flat(r["quote"] or "")
        try:
            n = int(r["page"])
        except (TypeError, ValueError):
            n = None
        verdict = "no_page_or_quote"
        if q and len(q) >= 20 and n is not None and pages:
            if q in pages.get(n, ""):
                verdict = "exact_page"
            elif q in pages.get(n, "") + pages.get(n + 1, ""):
                verdict = "runs_onto_next_page"
            elif q in pages.get(n - 1, "") or q in pages.get(n + 1, ""):
                verdict = "adjacent_page"
            elif any(q in t for t in pages.values()):
                verdict = "elsewhere_in_paper"
            else:
                verdict = "not_found"
        out.append({"rank": r["rank"], "slug": slug, "reader": r["reader"], "field": r["field"], "page": r["page"], "first_status": r["verified"], "lenient": verdict,
                    "quote": (r["quote"] or "")[:120]})
    with (DATA / "hyphen_recheck.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    total = len(items)
    claimed = total - status.get("no_claim", 0)  # rates use claim-bearing items; a 'no_claim' row has no quote to check
    strict_ok = status.get("verified", 0)
    cnt = Counter(o["lenient"] for o in out)
    recovered = cnt.get("exact_page", 0) + cnt.get("runs_onto_next_page", 0)
    by_reader = {}
    for rd in sorted({r["reader"] for r in items}):
        n_rd = sum(1 for r in items if r["reader"] == rd and r["verified"] != "no_claim")
        ok_rd = sum(1 for r in items if r["reader"] == rd and r["verified"] == "verified")
        rec_rd = sum(1 for o in out if o["reader"] == rd and o["lenient"] in ("exact_page", "runs_onto_next_page"))
        nf_rd = sum(1 for o in out if o["reader"] == rd and o["lenient"] == "not_found")
        by_reader[rd] = {"claim_bearing_items": n_rd, "strict_exact": ok_rd, "recovered": rec_rd, "not_found_anywhere": nf_rd,
                         "strict_rate": round(ok_rd / n_rd, 4), "lenient_rate": round((ok_rd + rec_rd) / n_rd, 4)}
    summary = {"items": total, "claim_bearing_items": claimed, "strict_status": dict(status), "strict_exact_rate": round(strict_ok / claimed, 4),
               "lenient_results_for_the_rest": dict(cnt), "recovered_to_exact_or_run_on": recovered,
               "recovered_on_the_page": cnt.get("exact_page", 0), "recovered_run_onto_next_page": cnt.get("runs_onto_next_page", 0),
               "lenient_exact_rate": round((strict_ok + recovered) / claimed, 4), "by_reader": by_reader}
    (DATA / "hyphen_recheck.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
