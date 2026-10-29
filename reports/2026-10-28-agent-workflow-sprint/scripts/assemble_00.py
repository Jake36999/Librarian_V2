"""Revision 2: assemble 00-summary.md from data/00_template.md (hand-written prose) and the measured numbers, so none is copied by hand."""
from __future__ import annotations

import csv
import glob
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CLAUDE_PROJECTS, DATA, REPORT, TMP  # noqa: E402

SELF_SESSION = "61d3eaf3-e0bc-4aa9-aa45-2de25ffb574b"
REVIEW_ARRIVED = "meta review of your work"


def self_tokens() -> str:
    path = CLAUDE_PROJECTS / "D--Librarian-V2" / f"{SELF_SESSION}.jsonl"
    start, msgs = None, {}
    for raw in open(path, encoding="utf-8", errors="replace"):
        try:
            o = json.loads(raw)
        except ValueError:
            continue
        ts = o.get("timestamp")
        if o.get("type") == "user" and start is None:
            c = (o.get("message") or {}).get("content")
            text = c if isinstance(c, str) else " ".join(b.get("text", "") for b in (c or []) if isinstance(b, dict))
            if REVIEW_ARRIVED in text:
                start = ts
        if o.get("type") == "assistant" and start and ts and ts >= start:
            m = o.get("message") or {}
            u = m.get("usage") or {}
            rec = msgs.setdefault(m.get("id") or o.get("uuid"), {"in": 0, "cc": 0, "cr": 0, "out": 0})
            for k, key in (("in", "input_tokens"), ("cc", "cache_creation_input_tokens"), ("cr", "cache_read_input_tokens"), ("out", "output_tokens")):
                rec[k] = max(rec[k], int(u.get(key) or 0))
    tot = {k: sum(r[k] for r in msgs.values()) for k in ("in", "cc", "cr", "out")}
    peak = max((r["in"] + r["cc"] + r["cr"] for r in msgs.values()), default=0)
    return (f"{len(msgs)} requests, {tot['cc'] / 1e3:,.0f}k cache-creation, {tot['cr'] / 1e6:,.1f}M cache-read and {tot['out'] / 1e3:,.0f}k output tokens (ordinary input {tot['in']:,}); "
            f"context peaked at {peak / 1e3:,.0f}k. Priced at the Opus 5.5 rates fitted in `02-baseline.md` that is roughly ${(tot['in'] * 4.98 + tot['cc'] * 7.98 + tot['cr'] * 0.20 + tot['out'] * 19.66) / 1e6:,.0f} modelled, "
            "but this session runs on a different model and plan, so treat it as a size, not a price")


def main() -> int:
    papers = list(csv.DictReader((DATA / "lit2_papers.csv").open(encoding="utf-8")))
    items = list(csv.DictReader((DATA / "lit2_items.csv").open(encoding="utf-8")))
    summ = json.loads((DATA / "lit2_summary.json").read_text(encoding="utf-8"))
    cov = json.loads((DATA / "coverage_vs_reviewer.json").read_text(encoding="utf-8"))
    levels = json.loads((DATA / "lit2_levels.json").read_text(encoding="utf-8"))
    strict = json.loads((DATA / "strict_page_recheck.json").read_text(encoding="utf-8"))
    reg = list(csv.DictReader((DATA / "claim_register.csv").open(encoding="utf-8")))
    prim = [p for p in papers if p["reader"] == "MiMo-V2.6-Pro"]
    val = {"N_PAPERS": str(len(prim)), "OTHER_N": str(sum(1 for r in reg if r["group"] == "other"))}
    val["LEVELS"] = (f"Read in full, the primary reader called {levels['primary']['direct_candidate']} papers direct candidates, {levels['primary']['bounded_analogy']} bounded analogies and {levels['primary']['out_of_scope']} out of scope; "
                     f"a second opinion from a different model family on a stricter rubric agreed on {levels['agree']} of {levels['n']} and contests {levels['contested']}, which `03-reading-list.md` lists. "
                     f"Both opinions call {levels['at_least_bounded_by_both']} of {levels['n']} at least a bounded analogy, so the scale barely discriminates; I also give a reading priority ({levels['priority']['high']} high, {levels['priority']['medium']} medium, {levels['priority']['low']} low). "
                     f"The reading produced {sum(1 for i in items if i['reader'] == 'MiMo-V2.6-Pro' and i['verified'] == 'verified'):,} anchor-verified items.")
    val["COSTS_ONE"] = "reflection adds about 68% more tokens than ReAct (#01), a task layer costs 6.0k tokens per task against 1.1k for a plain call (#02), one verifier consumed 13.3k vision-model tokens per task (#07), and a three-tier verifier needs 2,100 tokens and 7.3 s per query (#09)."
    rates = " and ".join(f"{m} {100 * v['exact_page_rate']:.1f}%" for m, v in summ["by_model"].items())
    allv = sum(v["exact_page"] for v in summ["by_model"].values())
    alln = sum(v["anchored_items"] for v in summ["by_model"].values())
    fp = strict["first_pass_card"]["by_first_pass_class"].get("verified", {})
    hy = json.loads((DATA / "hyphen_recheck.json").read_text(encoding="utf-8"))
    val["FIDELITY"] = (f"In the full-text readings {100 * allv / max(1, alln):.1f}% of {alln:,} anchored items had their quote on the exact cited page ({rates}); "
                       f"all {sum(fp.values())} first-pass cards labelled verified, re-checked with the same strict rule, also pass. "
                       f"The strict rule is a floor: a letters-and-digits comparison (`data/hyphen_recheck.json`) puts {100 * (allv + hy['recovered_to_exact_or_run_on']) / max(1, alln):.1f}% on the exact page "
                       f"and finds only {hy['lenient_results_for_the_rest']['not_found']} quotes ({100 * hy['lenient_results_for_the_rest']['not_found'] / max(1, alln):.1f}%) nowhere in the paper.")
    sa = DATA / "support_audit_summary.json"
    adj = DATA / "support_audit_adjudication.csv"
    if sa.exists():
        s = json.loads(sa.read_text(encoding="utf-8"))
        v = s["verdicts"]
        txt = f"On a sample of {s['items']} items a judge from a third model family (Qwen3.5-397B) found {v.get('supported', 0)} supported, {v.get('partly_supported', 0)} partly supported and {v.get('not_supported', 0)} not supported by the cited page"
        if adj.exists():
            a = list(csv.DictReader(adj.open(encoding="utf-8")))
            mv = Counter(x["my_verdict"] for x in a)
            txt += f"; reading {len(a)} of them myself I found {mv.get('supported', 0)} supported, {mv.get('partly_supported', 0)} partly supported and {mv.get('not_supported', 0)} not supported"
        val["SUPPORT"] = txt + "."
    else:
        val["SUPPORT"] = "The support audit was not run."
    rn = json.loads((DATA / "lit2_result_numbers.json").read_text(encoding="utf-8"))
    pk = rn["primary_reader"]
    val["RESULT_NUMBERS_ONE"] = (f"Most partial cases are result numbers that sit on a different page from the cited mechanism quote: all {rn['numbers_checked']} numbers in {rn['method_items_with_numeric_results']} result texts appear in the paper, "
                                 f"but {100 * pk.get('all_in_paper_not_all_on_page', 0) / max(1, sum(pk.values())):.0f}% of the primary reader's items have one on another page.")
    val["COVERAGE"] = f"Against the review's 25 independently chosen passages, the primary reader's items contain {cov['found_by_primary_reader']} and the readers together {cov['found_by_any_reader']}; this is a small, selective checklist, not a recall estimate."
    pm = summ["by_model"].get("MiMo-V2.6-Pro", {})
    pc = pm.get("parse", {})
    val["PARSE"] = (f"Of {pm.get('calls_completed', 0)} primary readings, {pc.get('ok', 0)} parsed as is, {pc.get('repaired', 0)} after brace repair and {pc.get('salvaged', 0)} only by salvaging complete array items from damaged JSON; "
                    f"{pm.get('calls_truncated', 0)} were truncated. A salvaged list may be missing items, so it is never counted as a complete reading.")
    res = [json.loads(l) for l in (TMP / "lanes" / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    res = [r for r in res if "max-output-tokens must be" not in str(r.get("error"))]
    r2 = [r for r in res if r["id"].split("-")[0] in ("L2", "S2", "S2b", "AP")]
    val["REV2_DEEPINFRA"] = f"{len(r2)} calls (full-text readings, support audit, applicability opinion), ${sum(float(r.get('live_cost') or 0) for r in r2):.2f} at live prices"
    val["SPRINT_DEEPINFRA"] = f"{len(res)} calls, ${sum(float(r.get('live_cost') or 0) for r in res):.2f}"
    val["SELF_TOKENS"] = self_tokens()
    text = (DATA / "00_template.md").read_text(encoding="utf-8")
    for k, v in val.items():
        text = text.replace(f"@@{k}@@", v)
    left = [w for w in text.split() if w.startswith("@@")]
    if left:
        print("UNFILLED:", left)
        return 1
    (REPORT / "00-summary.md").write_text(text, encoding="utf-8", newline="\n")
    print("assembled 00-summary.md", len(text), "chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
