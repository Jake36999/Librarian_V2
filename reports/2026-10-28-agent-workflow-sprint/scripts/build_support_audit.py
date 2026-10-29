"""Revision 2, M8d: a semantic-support audit of anchored literature items.

A verbatim quote on the cited page proves the evidence exists, not that it supports the claim attached to it. This script draws a
stratified, seeded sample of exact-page-verified items (methods, costs, negative results, limitations; MiMo and the second readers),
packs each with the text of its cited page, and plans calls to a judge from a different model family than the reader.
The judge's verdicts are tier R; a subsample is adjudicated by hand (data/support_audit_adjudication.csv).
Writes tmp/sprint/packets/S2b-batch-NN.txt, tmp/sprint/lanes/instr/S2.txt, tmp/sprint/lanes/calls_s2.json, data/support_audit_sample.csv
"""
from __future__ import annotations

import csv
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_lanes import COMMON, GLM, INSTR, MIMO, PACKETS  # noqa: E402
from common import DATA, TMP, write_csv  # noqa: E402

S2_TEXT = COMMON + """
TASK: audit whether claims are supported by the page of a paper they cite. The packet holds numbered items; each has a CLAIM (what a reader said the paper states or measures), the QUOTE the reader gave, and the full TEXT of the cited PAGE.
For each item decide from the page text alone (never from background knowledge):
 supported = the page states or directly shows what the claim says, including any numbers;
 partly_supported = the page supports part of the claim, or supports it only with a narrower scope, a different number, or a condition the claim omits;
 not_supported = the page does not state what the claim says, or contradicts it;
 cannot_tell = the page text is too garbled or incomplete to decide.
Output schema: {"verdicts": [{"item": <int>, "verdict": "supported|partly_supported|not_supported|cannot_tell", "reason": "<at most 25 words naming what matches or what is missing>", "quote_relevant": <true|false>}]}
Return one verdict per item, in order.
"""

PLAN = {"methods": 30, "costs": 10, "negative_results": 10, "limitations": 10}


def main() -> int:
    items = [r for r in csv.DictReader((DATA / "lit2_items.csv").open(encoding="utf-8")) if r["verified"] == "verified" and r["field"] in PLAN]
    calls = {c["id"]: c for c in json.loads((TMP / "lanes" / "calls_l2.json").read_text(encoding="utf-8"))}
    rng = random.Random(20261028)
    sample = []
    for field, n in PLAN.items():
        pool = [r for r in items if r["field"] == field]
        # half from the primary reader, half from the independent readers when both exist
        prim = [r for r in pool if r["reader"] == "MiMo-V2.6-Pro"]
        sec = [r for r in pool if r["reader"] != "MiMo-V2.6-Pro"]
        k2 = min(len(sec), n // 3)
        sample += rng.sample(prim, min(len(prim), n - k2)) + rng.sample(sec, k2)
    rng.shuffle(sample)
    PACKETS.mkdir(parents=True, exist_ok=True)
    INSTR.mkdir(parents=True, exist_ok=True)
    (INSTR / "S2.txt").write_text(S2_TEXT, encoding="utf-8", newline="\n")
    rows, plan_calls = [], []
    # one judge from a third family (Qwen3.5-397B): never MiMo or GLM, so it is independent of every reader; GLM-5.3 as judge leaked its reasoning
    # into the answer in the applicability call, so it is not used here
    groups = [("qwen", "Qwen/Qwen3.5-397B-A17B", list(sample))]
    nb = 0
    for tag, judge, grp in groups:
        for b in range(0, len(grp), 10):
            chunk = grp[b:b + 10]
            nb += 1
            parts = []
            for k, r in enumerate(chunk, start=1):
                slug = r["slug"]
                text = (TMP / "src" / "papers" / f"{slug}.txt").read_text(encoding="utf-8", errors="replace")
                pages = re.split(r"\[\[PAGE (\d+)\]\]\n", text)
                full = " ".join({int(pages[i]): pages[i + 1] for i in range(1, len(pages) - 1, 2)}.get(int(r["page"]), "").split())
                # window of the page centred on the quote (the first run cut every page after 7,000 characters and the quote could fall beyond the cut)
                toks = re.findall(r"\w+", r["quote"].lower())[:6]
                hit = re.search(r"\W+".join(re.escape(t) for t in toks), full, re.I) if toks else None
                centre = hit.start() if hit else 0
                page_text = full[max(0, centre - 3500): centre + 3500]
                claim = " | ".join(x for x in (r["label"], r["claim"], r["results"] if r["results"] not in ("", "not_reported") else "") if x)
                parts.append(f"=== ITEM {k} ===\nCLAIM: {claim}\nQUOTE: {r['quote']}\nPAGE {r['page']} TEXT:\n{page_text}\n")
                rows.append({"batch": nb, "item": k, "call": f"S2b-{nb:02d}-{tag}", "slug": slug, "rank": r["rank"], "reader": r["reader"], "field": r["field"],
                             "page": r["page"], "label": r["label"], "claim": r["claim"][:300], "quote": r["quote"]})
            name = f"S2b-batch-{nb:02d}.txt"
            (PACKETS / name).write_text("\n".join(parts), encoding="utf-8", newline="\n")
            plan_calls.append({"id": f"S2b-{nb:02d}-{tag}", "lane": "S2", "model": judge, "files": [f"tmp/sprint/packets/{name}"], "instruction_file": "tmp/sprint/lanes/instr/S2.txt",
                               "max_output_tokens": 8000, "timeout": 900})
    (TMP / "lanes" / "calls_s2.json").write_text(json.dumps(plan_calls, indent=1), encoding="utf-8", newline="\n")
    write_csv(DATA / "support_audit_sample.csv", rows)
    print(f"sample={len(sample)} batches={len(plan_calls)} by_field={ {f: sum(1 for r in sample if r['field'] == f) for f in PLAN} } secondary_readers={sum(1 for r in sample if r['reader'] != 'MiMo-V2.6-Pro')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
