"""Revision 2: render 03-reading-list.md from the full-text readings (data/lit2_papers.csv, data/lit2_items.csv).

Domain match, evidence type, two model opinions on applicability and a reading priority are separate columns instead of one total
ranking. A paper that could not be read is listed as unexamined, never as irrelevant. Paper numbers (#n) are the first-pass ranks,
kept as identifiers. Reading priority (data/reading_priority.csv) is my judgement from titles, the readers' reasons, the judge's named
mechanism and the verified item counts: I did not read all 50 papers myself.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, REPORT  # noqa: E402

TRACKS = [("Metrics and orchestration", "AB"), ("Continuity, drift and memory", "C"), ("Verification, grounding and checking", "E"), ("Communication and evidence efficiency", "D")]


def esc(s, n=170) -> str:
    return (s or "").replace("|", "/").replace("\n", " ").strip()[:n]


def main() -> int:
    papers = list(csv.DictReader((DATA / "lit2_papers.csv").open(encoding="utf-8")))
    items = list(csv.DictReader((DATA / "lit2_items.csv").open(encoding="utf-8")))
    first = {r["slug"]: r for r in csv.DictReader((DATA / "reading_list_ranked.csv").open(encoding="utf-8"))}
    notes = list(csv.DictReader((DATA / "vault_notes_ranked.csv").open(encoding="utf-8")))
    ap = {int(r["rank"]): r for r in csv.DictReader((DATA / "applicability_second_opinion.csv").open(encoding="utf-8"))} if (DATA / "applicability_second_opinion.csv").exists() else {}
    pri = {int(r["rank"]): r for r in csv.DictReader((DATA / "reading_priority.csv").open(encoding="utf-8"))}
    by_slug = defaultdict(dict)
    for p in papers:
        by_slug[p["slug"]][p["reader"]] = p
    cat, extra = defaultdict(Counter), defaultdict(Counter)
    for i in items:
        if i["verified"] == "verified" and i["reader"] == "MiMo-V2.6-Pro":
            (cat if i["field"] == "methods" else extra)[i["slug"]][i["category"] if i["field"] == "methods" else i["field"]] += 1
    rows = []
    for slug, f in first.items():
        d = by_slug.get(slug, {})
        prim = d.get("MiMo-V2.6-Pro")
        second = next((v for k, v in d.items() if k != "MiMo-V2.6-Pro"), None)
        rk = int(f["rank"])
        rows.append({"rank": rk, "slug": slug, "title": f["title"], "first_score": f["score"], "first_AD": "/".join(f[k] for k in "ABCD"), "prim": prim, "second": second,
                     "cat": cat[slug], "extra": extra[slug], "judge": ap.get(rk, {}), "pri": pri[rk]})
    rows.sort(key=lambda r: r["rank"])
    level = lambda r: (r["prim"] or {}).get("applicability_level") or "unexamined"  # noqa: E731
    judged = [r for r in rows if r["judge"] and level(r) != "unexamined"]
    n_agree = sum(1 for r in judged if r["judge"].get("level") == level(r))
    n_bounded_or_more = sum(1 for r in judged if level(r) != "out_of_scope" and r["judge"].get("level") != "out_of_scope")
    two = [(r, r["second"]) for r in rows if r["second"] and r["prim"]]
    n_two_same = sum(1 for r, s in two if s["applicability_level"] == level(r))
    by_pri = {k: [r for r in rows if r["pri"]["priority"] == k] for k in ("high", "medium", "low")}
    lvl = lambda r: level(r).replace("_", " ").replace("candidate", "cand.").replace("bounded analogy", "bounded").replace("out of scope", "out")  # noqa: E731
    jl = lambda r: (r["judge"].get("level") or "-").replace("_", " ").replace("candidate", "cand.").replace("bounded analogy", "bounded").replace("out of scope", "out")  # noqa: E731
    out = ["# Reading list (deliverable 3, part 1, revision 2)", "",
           "Date: 2026-10-28 (revised the same evening after a second-pass review; the first-pass list is in `revision-1/`). Corpus: `E:\\Librarian research` (51 files, 50 distinct: two PDFs are byte-identical) plus 26 agent-related notes already in the Resource-Library vault. "
           "Paper numbers (#n) are the first-pass ranks, kept as identifiers.", "",
           "**What changed.** The first pass triaged each paper from its first two pages, last page and headings, scored it 0 to 3 in four categories, and extracted at most six method cards from 18 papers. That screening mislabelled adjacent work as irrelevant, and one total ranking mixed domain match, evidence quality and immediate applicability. "
           "Revision 2 reads **all 50 distinct papers in full** (MiMo-V2.6-Pro, one paper per call), repeats 17 decision-relevant papers with an independent reader (GLM-5.3 for 8, GLM-5.3-Flash for 9), and fills a fixed checklist: "
           "problem, evidence type, unit, comparators, methods (A metrics, B schemas, C drift and memory, D communication efficiency, E verification and checking), reported costs, negative results, limitations and reproducibility. "
           "Every item carries a page and a quote that a script found on that page (`data/lit2_items.csv`); that proves the quote exists, not that it supports the claim (see the support audit in `04-extraction-table.md`).", "",
           "**Applicability, three ways, none of them decisive.** Levels: *direct candidate* = the same class of control, verification or coordination problem as an LLM lead delegating to other models; *bounded analogy* = a named mechanism, schema or metric that could transfer to such work with a stated adaptation; *out of scope* = no concrete transfer. "
           f"The primary reader gave a level while reading; a judge from another model family (Qwen3.5-397B) classified each paper again from its reading record on a stricter written rubric (`scripts/build_applicability.py`). They agree on {n_agree} of {len(judged)} papers, and **both call {n_bounded_or_more} of {len(judged)} at least a bounded analogy**, so the scale barely discriminates: models find an analogy almost everywhere. "
           f"Where two readers read the same paper they gave the same level for {n_two_same} of {len(two)}. I therefore also give a **reading priority** (high, medium, low) based on titles, the readers' reasons, the judge's named mechanism and the verified item counts; it is my judgement from those records, not from reading all 50 papers, and it is meant to be argued with.", "",
           f"Reading priority: **{len(by_pri['high'])} high, {len(by_pri['medium'])} medium, {len(by_pri['low'])} low.** Low means a different learning setup, a physical system or a keyword match (for example drift in class-incremental learning, verification of weather forecasts): not unexamined, but unlikely to repay a close reading for this project.", ""]
    out += ["## Read in four tracks", "", "Papers with at least one anchor-verified method in the track's categories, most methods first. 'Costs' and 'Neg.' count verified cost items and negative results the paper reports.", ""]
    for name, letters in TRACKS:
        sel = sorted(((sum(r["cat"][c] for c in letters), r) for r in rows if sum(r["cat"][c] for c in letters)), key=lambda t: (t[1]["pri"]["priority"] == "low", -t[0], t[1]["rank"]))
        out += [f"### {name}", "", "| Paper | Priority | Methods here | Costs | Neg. | Why |", "|---|---|---:|---:|---:|---|"]
        for n, r in sel[:12]:
            out.append(f"| #{r['rank']:02d} {esc(r['title'], 70)} | {r['pri']['priority']} | {n} | {r['extra']['costs']} | {r['extra']['negative_results']} | {esc(r['pri']['why'], 120)} |")
        out.append("")
    out += ["## All papers by reading priority", "", "'Level' shows the primary reader and then the judge. Methods are anchor-verified items by category A/B/C/D/E.", ""]
    for key, label in (("high", "High priority"), ("medium", "Medium priority"), ("low", "Low priority")):
        out += [f"### {label}", "", "| # | Paper | Evidence | Level (reader / judge) | Methods A/B/C/D/E | Costs | Neg. | Why |", "|---:|---|---|---|---|---:|---:|---|"]
        for r in by_pri[key]:
            m = "/".join(str(r["cat"][c]) for c in "ABCDE")
            out.append(f"| {r['rank']} | {esc(r['title'], 75)} | {(r['prim'] or {}).get('evidence_type')} | {lvl(r)} / {jl(r)} | {m} | {r['extra']['costs']} | {r['extra']['negative_results']} | {esc(r['pri']['why'], 110)} |")
        out.append("")
    zero = [r for r in rows if r["first_AD"] == "0/0/0/0" and r["pri"]["priority"] in ("high", "medium")]
    out += ["## Papers the first pass scored zero that deserve a reading", "",
            "| # | Paper | First pass | Priority | Mechanism the judge names | Verified methods (A/B/C/D/E) |", "|---:|---|---|---|---|---|"]
    for r in zero:
        out.append(f"| {r['rank']} | {esc(r['title'], 70)} | 0/0/0/0 | {r['pri']['priority']} | {esc(r['judge'].get('mechanism'), 90)} | {'/'.join(str(r['cat'][c]) for c in 'ABCDE')} |")
    unex = [r for r in rows if level(r) == "unexamined"]
    if unex:
        out += ["", "## Unexamined (no usable reading; not the same as irrelevant)", ""] + [f"- #{r['rank']} {esc(r['title'], 100)}" for r in unex]
    out += ["", "## Vault notes on agent topics (adjacent prior art; unchanged from the first pass)", "",
            "These notes were written on 2026-09-19 from the model's general familiarity with the papers, not from a PDF the vault holds (stated in `Paper Index.md`). They are **secondary sources**: useful for orientation, not citable for section-level claims. "
            "The primary Reflexion and Tree of Thoughts papers should be read for the claims that matter; this pass did not retrieve them.", "",
            "| Rank | Note | A | B | C | D | Score | Why |", "|---:|---|:-:|:-:|:-:|:-:|---:|---|"]
    for r in notes[:26]:
        out.append(f"| {r['rank']} | {esc(r['slug'], 60)} | {r['A']} | {r['B']} | {r['C']} | {r['D']} | {r['score']} | {esc(r['reason'], 150)} |")
    (REPORT / "03-reading-list.md").write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    lv = {"n": len(judged), "agree": n_agree, "contested": len(judged) - n_agree, "at_least_bounded_by_both": n_bounded_or_more,
          "primary": {k: sum(1 for r in rows if level(r) == k) for k in ("direct_candidate", "bounded_analogy", "out_of_scope", "unexamined")},
          "judge": dict(Counter(r["judge"].get("level") for r in judged)), "priority": {k: len(v) for k, v in by_pri.items()}, "two_reader_same_level": [n_two_same, len(two)]}
    (DATA / "lit2_levels.json").write_text(json.dumps(lv, indent=1), encoding="utf-8", newline="\n")
    print(lv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
