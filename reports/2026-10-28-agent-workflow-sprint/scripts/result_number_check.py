"""Revision 2: where do the numbers in a reader's result text come from?

For every anchor-verified method item the reader wrote a `results` string. Its mechanism quote is anchored to the cited page, but the result
text was written from anywhere in the paper. The support audit found that most sampled methods with numeric results had numbers that were not on
the cited page. This script checks every such number against (a) the cited page and (b) the whole extracted text of the paper.
Output: data/lit2_result_numbers.csv (one row per item) and data/lit2_result_numbers.json (counts).
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, TMP, write_csv  # noqa: E402

NUM = re.compile(r"\d[\d,]*\.?\d*")


def squash(s: str) -> str:
    return " ".join(s.replace("ﬂ", "fl").replace("ﬁ", "fi").replace("−", "-").replace(",", "").split())


def numbers(s: str) -> list[str]:
    return [n.rstrip(".") for n in (x.replace(",", "") for x in NUM.findall(s or "")) if len(n.rstrip(".")) >= 2]


def main() -> int:
    items = [i for i in csv.DictReader((DATA / "lit2_items.csv").open(encoding="utf-8")) if i["field"] == "methods" and i["verified"] == "verified"]
    cache: dict[str, tuple[str, dict[int, str]]] = {}

    def paper(slug: str):
        if slug not in cache:
            t = (TMP / "src" / "papers" / f"{slug}.txt").read_text(encoding="utf-8", errors="replace")
            p = re.split(r"\[\[PAGE (\d+)\]\]\n", t)
            pages = {int(p[k]): squash(p[k + 1]) for k in range(1, len(p) - 1, 2)}
            cache[slug] = (squash(" ".join(pages.values())), pages)
        return cache[slug]

    rows = []
    for i in items:
        res = i["results"]
        ns = numbers(res) if res not in ("", "not_reported") else []
        if not ns:
            continue
        whole, pages = paper(i["slug"])
        here = pages.get(int(i["page"]), "")
        on_page = [n for n in ns if n in here]
        in_paper = [n for n in ns if n in whole]
        kind = "all_on_cited_page" if len(on_page) == len(ns) else ("all_in_paper_not_all_on_page" if len(in_paper) == len(ns) else "some_not_found_in_paper")
        rows.append({"rank": i["rank"], "reader": i["reader"], "page": i["page"], "label": i["label"][:50], "numbers": len(ns), "on_cited_page": len(on_page), "in_paper": len(in_paper),
                     "kind": kind, "not_found": ";".join(n for n in ns if n not in whole)})
    write_csv(DATA / "lit2_result_numbers.csv", rows)
    prim = [r for r in rows if r["reader"] == "MiMo-V2.6-Pro"]
    out = {"method_items_with_numeric_results": len(rows), "primary_reader": dict(Counter(r["kind"] for r in prim)), "all_readers": dict(Counter(r["kind"] for r in rows)),
           "numbers_checked": sum(int(r["numbers"]) for r in rows), "numbers_not_found_in_paper": sum(int(r["numbers"]) - int(r["in_paper"]) for r in rows)}
    (DATA / "lit2_result_numbers.json").write_text(json.dumps(out, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
