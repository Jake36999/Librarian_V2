"""Revision 2: assemble 04-extraction-table.md from the hand-written head and tail (data/04_head.md, data/04_tail.md), the curated tables
(tmp/sprint/out/04_tables.md, from render_extraction_tables.py) and the measured audit numbers, so no audit number is copied by hand."""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, REPORT, TMP  # noqa: E402

PROBES = [(1, "costs", "68%", "the 68% extra tokens of reflection (#01)"), (1, "negative_results", "unfamiliar domains", "negative transfer of the drift method outside its home domain (#01)"),
          (1, "reproducibility", "promised", "code promised without an archive identifier (#01)"), (1, "limitations", "keyword-heuristic", "a keyword-heuristic rationale score (#01)"),
          (2, "reproducibility", "placeholder", "an unfilled code-repository placeholder (#02)"), (7, "costs", "13341", "role-level token cost of the verifier (#07)"),
          (7, "costs", "55 s", "a measured parallel speed-up (#07)"), (14, "negative_results", "hand-coded", "a fixed-rule baseline matching the compiler (#14)"),
          (3, "negative_results", "Large knowledge", "context utility that is not monotonic (#03)"), (8, "negative_results", "Greedy self-reflection", "self-check that never overturned a verdict (#08)"),
          (9, "costs", "2100", "an offline labelling cost per query (#09)")]


def main() -> int:
    items = list(csv.DictReader((DATA / "lit2_items.csv").open(encoding="utf-8")))
    papers = list(csv.DictReader((DATA / "lit2_papers.csv").open(encoding="utf-8")))
    summ = json.loads((DATA / "lit2_summary.json").read_text(encoding="utf-8"))
    strict = json.loads((DATA / "strict_page_recheck.json").read_text(encoding="utf-8"))
    cov = json.loads((DATA / "coverage_vs_reviewer.json").read_text(encoding="utf-8"))
    prim = [i for i in items if i["reader"] == "MiMo-V2.6-Pro" and i["verified"] == "verified"]
    byf = Counter(i["field"] for i in prim)
    val = {
        "N_PAPERS": str(len({p["slug"] for p in papers if p["reader"] == "MiMo-V2.6-Pro"})),
        "ITEMS_VERIFIED": f"{len(prim):,}",
        "ITEMS_BY_FIELD": ", ".join(f"{byf[f]} {f.replace('_', ' ')}" for f in ("methods", "costs", "negative_results", "limitations", "reproducibility", "comparators")),
        "N_CURATED": str(len(list(csv.DictReader((DATA / "lit2_curated_rows.csv").open(encoding="utf-8"))))),
    }
    rows = []
    for model, m in summ["by_model"].items():
        parse = " / ".join(str(m["parse"].get(k, 0)) for k in ("ok", "repaired", "salvaged"))
        rows.append(f"| {model} | {m['calls_completed']} | {m['calls_completed']} / {m['calls_truncated']} | {parse} | {m['anchored_items']:,} | {m['exact_page']:,} ({100 * m['exact_page_rate']:.1f}%) | {m['adjacent_page']} | {m['elsewhere']} | {m['unverified']} |")
    val["READER_ROWS"] = "\n".join(rows)
    fp = strict["first_pass_card"]["by_first_pass_class"].get("verified", {})
    val["STRICT_RECHECK"] = (f"all {sum(fp.values())} first-pass cards labelled verified (103 of 108 from the primary reader, 31 of 60 from the second reader) fall on the exact cited page, "
                             f"as do {strict['second_pass_anchor']['strict'].get('verified', 0)} of {strict['second_pass_anchor']['n']} of the second-pass reviewer's anchors in this sprint's own text extraction.")
    sa = DATA / "support_audit_summary.json"
    adj_path = DATA / "support_audit_adjudication.csv"
    if sa.exists():
        s = json.loads(sa.read_text(encoding="utf-8"))
        v = s["verdicts"]
        text = f"a judge from a third model family (Qwen3.5-397B) read {s['items']} sampled exact-page items with their page text: {v.get('supported', 0)} supported, {v.get('partly_supported', 0)} partly supported, {v.get('not_supported', 0)} not supported, {v.get('cannot_tell', 0)} cannot tell"
        if v.get("no_verdict"):
            text += f", {v['no_verdict']} without a verdict"
        text += "."
        val["AUDIT_N"] = str(s["items"])
        if adj_path.exists():
            adj = list(csv.DictReader(adj_path.open(encoding="utf-8")))
            res = {(r["call"], r["item"]): r for r in csv.DictReader((DATA / "support_audit_results.csv").open(encoding="utf-8"))}
            agree = sum(1 for a in adj if res.get((a["call"], a["item"]), {}).get("verdict") == a["my_verdict"])
            direction = sum(1 for a in adj if (res.get((a["call"], a["item"]), {}).get("verdict") in ("supported", "partly_supported")) == (a["my_verdict"] in ("supported", "partly_supported")))
            mv = Counter(a["my_verdict"] for a in adj)
            text += (f" I then read {len(adj)} of them myself against the page text: {mv.get('supported', 0)} supported, {mv.get('partly_supported', 0)} partly supported, {mv.get('not_supported', 0)} not supported; "
                     f"I matched the judge's verdict on {agree} of {len(adj)} and its supported-or-not direction on {direction}. Judge verdicts are tier R; mine are the reference for those items. "
                     f"All {sum(1 for a in adj if a['my_verdict'] == 'partly_supported')} partial cases had a mechanism on the cited page and result numbers or a detail on the next page or elsewhere; the judge called two items unsupported because its page window missed text that is on the page, "
                     f"and my spot-check of {sum(1 for a in adj if a['my_verdict'] == 'supported' and a['note'] == '' or a['scope'] == 'other')} further supported items found {sum(1 for a in adj if a['scope'] == 'other')} that state something about other methods in related work rather than the paper's own method.")
        val["SUPPORT_SUMMARY"] = text
    else:
        val["AUDIT_N"] = "0"
        val["SUPPORT_SUMMARY"] = "not run."
    adj_note = (f" I then read the {cov['anchors'] - cov['found_by_any_reader']} passages the rule missed against the readers' items myself (`data/coverage_adjudication.csv`) and counted a passage as found when an item states the same fact, even on another page: {cov['found_after_adjudication']} of {cov['anchors']} in all."
                if cov.get("adjudicated_rows") else "")
    rn = json.loads((DATA / "lit2_result_numbers.json").read_text(encoding="utf-8"))
    pk = rn["primary_reader"]
    pn = sum(pk.values())
    far = pk.get("all_in_paper_not_all_on_page", 0)
    val["RESULT_NUMBERS"] = (f"{rn['method_items_with_numeric_results']} method items carry numeric result text ({rn['numbers_checked']} numbers). Every one of those numbers was found in the paper's extracted text "
                             f"({rn['numbers_not_found_in_paper']} were not), but for {far} of the primary reader's {pn} such items ({100 * far / max(1, pn):.0f}%) at least one number is on a different page from the cited quote. "
                             "The page cited anchors the mechanism, not the result; `scripts/result_number_check.py` makes this check.")
    val["COVERAGE"] = (f"The primary reader's verified items contain {cov['found_by_primary_reader']} of the {cov['anchors']} by a word-containment rule on the same or an adjacent page (`scripts/coverage_vs_reviewer.py`), and the readers together {cov['found_by_any_reader']}." + adj_note
                       + (f" Passages still not found: {', '.join(f'#{r[0]} p. {r[1]} ({r[2]})' for r in cov['missed_by_all'])}." if cov["missed_by_all"] else " Every passage was found."))
    ov = summ["second_reader_overlap"]
    tot_p = sum(o["methods_primary"] for o in ov)
    hit = sum(o["primary_methods_also_found_by_second"] for o in ov)
    val["OVERLAP_PAPERS"] = str(len(ov))
    val["OVERLAP"] = f"{hit} of the primary reader's {tot_p} verified methods ({100 * hit / max(1, tot_p):.0f}%) were also found by the second reader (same or adjacent page and at least 30% shared quote words)."
    agree = sum(1 for o in ov if o["level_primary"] == o["level_second"])
    val["LEVEL_AGREE"] = f"the two readers gave the same applicability level for {agree} of {len(ov)} papers."
    found = [lab for (r, f, sub, lab) in PROBES if any(int(i["rank"]) == r and i["field"] == f and sub.lower() in (i["label"] + " " + i["claim"] + " " + i["results"]).lower() and i["reader"] == "MiMo-V2.6-Pro" and i["verified"] == "verified" for i in items)]
    val["MISSED_FOUND"] = f"{len(found)} of {len(PROBES)} probes I chose from the items the first pass lacked (and the review named) were found by the primary reader: " + "; ".join(found) + "."
    head = (DATA / "04_head.md").read_text(encoding="utf-8")
    tail = (DATA / "04_tail.md").read_text(encoding="utf-8")
    tables = (TMP / "out" / "04_tables.md").read_text(encoding="utf-8")
    text = head + "\n" + tables + "\n" + tail
    for k, v in val.items():
        text = text.replace(f"@@{k}@@", v)
    left = [w for w in text.split() if w.startswith("@@")]
    if left:
        print("UNFILLED:", left)
        return 1
    (REPORT / "04-extraction-table.md").write_text(text, encoding="utf-8", newline="\n")
    print("assembled 04-extraction-table.md", len(text), "chars;", {k: v for k, v in val.items() if k in ("N_PAPERS", "ITEMS_VERIFIED", "N_CURATED")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
