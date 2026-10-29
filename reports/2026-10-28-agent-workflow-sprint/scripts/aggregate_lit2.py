"""Revision 2, literature: tabulate the verified full-text readings (lane L2).

Reads tmp/sprint/out/verified/L2-*.jsonl and data/anchor_verification.csv.
Writes data/lit2_items.csv (one row per item), data/lit2_papers.csv (one row per paper and reader),
data/lit2_summary.json (per-model completion, parse and quote-location fidelity; reader overlap).
"""
from __future__ import annotations

import csv
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, TMP, write_csv  # noqa: E402

MODEL_SHORT = {"mimo": "MiMo-V2.6-Pro", "glm": "GLM-5.3", "glmflash": "GLM-5.3-Flash"}
FIELDS_WITH_CLAIM = ("problem", "sample_and_unit", "source_availability", "comparators", "methods", "costs", "negative_results", "limitations", "reproducibility")


def words(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", (s or "").lower()))


def main() -> int:
    calls = {c["id"]: c for c in json.loads((TMP / "lanes" / "calls_l2.json").read_text(encoding="utf-8"))}
    rank_of = {}
    for r in csv.DictReader((DATA / "reading_list_ranked.csv").open(encoding="utf-8")):
        rank_of[r["slug"]] = (int(r["rank"]), r["title"])
    av = {r["call"]: r for r in csv.DictReader((DATA / "anchor_verification.csv").open(encoding="utf-8")) if r["call"].startswith("L2-")}
    results = {}
    for line in (TMP / "lanes" / "results.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["id"].startswith("L2-") and r.get("status") == "completed":
            results[r["id"]] = r
    items, papers = [], []
    for cid in sorted(results):
        f = TMP / "out" / "verified" / f"{cid}.jsonl"
        if not f.exists():
            continue
        rows = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        slug = calls[cid]["slug"]
        rank, title = rank_of.get(slug, (0, ""))
        model = MODEL_SHORT[cid.rsplit("-", 1)[1]]
        rec = next((r for r in rows if r.get("field") == "record"), {})
        counts = Counter(r["field"] for r in rows if r.get("field") not in (None, "record") and r.get("verified") != "no_claim")
        quality = Counter(r["verified"] for r in rows if r.get("field") != "record" and r.get("verified") != "no_claim")
        a = av.get(cid, {})
        papers.append({"rank": rank, "slug": slug, "title": title[:90], "call": cid, "reader": model, "parse": a.get("parse", ""), "finish": results[cid].get("finish_reason"),
                       "truncated": results[cid].get("truncated"), "evidence_type": rec.get("evidence_type"), "applicability_level": rec.get("applicability_level"),
                       "applicability_reason": rec.get("applicability_reason"), "methods": counts["methods"], "costs": counts["costs"], "negative_results": counts["negative_results"],
                       "limitations": counts["limitations"], "reproducibility": counts["reproducibility"], "anchored_items": sum(quality.values()), "exact_page": quality["verified"],
                       "adjacent_page": quality["adjacent_page"], "elsewhere": quality["quote_elsewhere"], "unverified": quality["unverified"],
                       "live_cost": results[cid].get("live_cost"), "output_tokens": results[cid].get("output_tokens"), "latency_s": results[cid].get("latency_s")})
        for r in rows:
            if r.get("field") in (None, "record"):
                continue
            label = r.get("name") or r.get("what") or ""
            claim = r.get("mechanism") or r.get("value") or r.get("text") or ""
            items.append({"rank": rank, "slug": slug, "call": cid, "reader": model, "field": r["field"], "label": str(label)[:120], "category": r.get("category", ""),
                          "claim": str(claim)[:400], "results": str(r.get("results", ""))[:250], "limits_stated": str(r.get("limits_stated", ""))[:200],
                          "prerequisites": str(r.get("prerequisites", ""))[:160], "section": r.get("section", ""), "page": r.get("page"), "quote": str(r.get("quote") or "")[:300],
                          "verified": r.get("verified")})
    write_csv(DATA / "lit2_items.csv", items)
    write_csv(DATA / "lit2_papers.csv", papers)
    # per-model lane metrics (M8a to M8c); M8d and M8e are separate
    summ = {"by_model": {}, "second_reader_overlap": {}}
    for model in sorted({p["reader"] for p in papers}):
        ps = [p for p in papers if p["reader"] == model]
        its = [i for i in items if i["reader"] == model and i["verified"] != "no_claim"]
        q = Counter(i["verified"] for i in its)
        summ["by_model"][model] = {"calls_completed": len(ps), "calls_truncated": sum(1 for p in ps if p["truncated"] in (True, "True")),
                                   "parse": dict(Counter(p["parse"] for p in ps)), "anchored_items": len(its), "exact_page": q["verified"],
                                   "adjacent_page": q["adjacent_page"], "elsewhere": q["quote_elsewhere"], "unverified": q["unverified"],
                                   "exact_page_rate": round(q["verified"] / len(its), 4) if its else None, "live_cost_usd": round(sum(float(p["live_cost"] or 0) for p in ps), 3)}
    # reader overlap on papers read twice: applicability agreement and method matches by shared quote words on the same page
    by_slug = defaultdict(dict)
    for p in papers:
        by_slug[p["slug"]][p["reader"]] = p
    agree = []
    for slug, d in by_slug.items():
        if "MiMo-V2.6-Pro" in d and len(d) > 1:
            other = next(v for k, v in d.items() if k != "MiMo-V2.6-Pro")
            m_items = [i for i in items if i["call"] == d["MiMo-V2.6-Pro"]["call"] and i["field"] == "methods" and i["verified"] == "verified"]
            o_items = [i for i in items if i["call"] == other["call"] and i["field"] == "methods" and i["verified"] == "verified"]
            matched = 0
            for mi in m_items:
                if any(abs(int(mi["page"] or 0) - int(oi["page"] or 0)) <= 1 and len(words(mi["quote"]) & words(oi["quote"])) / max(1, len(words(mi["quote"]) | words(oi["quote"]))) >= 0.3 for oi in o_items):
                    matched += 1
            agree.append({"slug": slug[:40], "rank": d["MiMo-V2.6-Pro"]["rank"], "second": other["reader"], "level_primary": d["MiMo-V2.6-Pro"]["applicability_level"], "level_second": other["applicability_level"],
                          "methods_primary": len(m_items), "methods_second": len(o_items), "primary_methods_also_found_by_second": matched})
    summ["second_reader_overlap"] = agree
    (DATA / "lit2_summary.json").write_text(json.dumps(summ, indent=1, sort_keys=True), encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in summ["by_model"].items()}, indent=1)[:2500])
    print("papers read:", len({p['slug'] for p in papers}), "| readings:", len(papers), "| items:", len(items))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
