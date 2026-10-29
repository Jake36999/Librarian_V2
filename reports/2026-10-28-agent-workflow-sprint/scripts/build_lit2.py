"""Revision 2, literature: instruction file and call plan for a full-text, section-checklist reading of every distinct paper.

The first pass triaged on first and last pages, then asked for at most six method cards from 18 papers. This pass reads all
50 distinct papers in full with a fixed checklist (problem, evidence type, unit, comparators, methods, reported costs,
negative results, limitations, reproducibility, applicability) and requires a page number and verbatim quote for every item.
The primary reader reads every paper; an independent reader repeats the most decision-relevant ones.
Writes tmp/sprint/lanes/instr/L2.txt and tmp/sprint/lanes/calls_l2.json.
"""
from __future__ import annotations

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_lanes import COMMON, GLM, GLM_FLASH, INSTR, MIMO  # noqa: E402
from common import DATA, REPO, TMP  # noqa: E402

L2_TEXT = COMMON + """
TASK: read ONE research paper in full and fill a structured, evidence-anchored reading record. The reader is building an orchestration platform (the Librarian) where a token-limited lead model delegates to cheaper models and parallel agents on long software and research tasks. Report what the paper says in its own terms. Do not fill gaps from background knowledge: write "not_reported" where the paper does not say.
The paper text has `[[PAGE n]]` markers. Every item that carries a "quote" must also carry "page": the n of the nearest preceding marker, and the quote must be copied verbatim from that page (at most 25 words, no ellipses).
Categories for methods: A = metrics for agent or orchestration performance; B = schemas, architectures or protocols for deploying and running agents on kinds of task; C = long-horizon planning, goal or plan-execution drift, memory and context management; D = communication-efficient multi-agent cooperation; E = verification, validation and deterministic checking of model or agent output (including evidence-sufficiency and grounding checks, task-effect specifications, formal properties); none = a method that fits none of these.
Applicability: direct_candidate = the same class of control, verification or coordination problem as an LLM lead delegating to other models; bounded_analogy = a schema or method that could transfer but the environment differs; out_of_scope = no concrete transfer. Judge only from the paper's own content.
Extract only what the paper itself proposes, defines, measures or states. Costs are anything the paper reports about running, verifying, coordinating, training or human labour (tokens, latency, compute, queries, review time), even when treated as a side note. Negative results are results where the method did not help, was not significant, underperformed a baseline or variant, or failed on a subset.
Output schema:
{"paper": "<slug>",
 "reading_record": {
  "problem": {"text": "<at most 30 words>", "page": <int>, "quote": "<verbatim>"},
  "evidence_type": "simulation|benchmark|user_study|survey_review|case_study|formal_proof|position|tool_description|other",
  "sample_and_unit": {"text": "<at most 30 words, or not_reported>", "page": <int|null>, "quote": "<verbatim or empty>"},
  "comparators": [{"text": "<at most 20 words>", "page": <int>, "quote": "<verbatim>"}],
  "source_availability": {"text": "<code or data statement as printed, or not_reported>", "page": <int|null>, "quote": "<verbatim or empty>"},
  "applicability_level": "direct_candidate|bounded_analogy|out_of_scope",
  "applicability_reason": "<at most 30 words>"},
 "methods": [{"name": "<short>", "category": "A|B|C|D|E|none", "mechanism": "<at most 50 words; formulas as printed>", "prerequisites": "<at most 20 words or not_reported>", "results": "<numbers as printed, at most 30 words, or not_reported>", "section": "<heading as printed with its number>", "page": <int>, "quote": "<verbatim>", "limits_stated": "<at most 25 words or not_reported>"}],
 "costs": [{"what": "tokens|latency|compute|human_labour|memory|communication|training|other", "value": "<as printed, at most 25 words>", "page": <int>, "quote": "<verbatim>"}],
 "negative_results": [{"text": "<at most 30 words>", "page": <int>, "quote": "<verbatim>"}],
 "limitations": [{"text": "<at most 30 words>", "page": <int>, "quote": "<verbatim>"}],
 "reproducibility": [{"text": "<at most 25 words: code or data placeholders, missing details, inconsistent numbers>", "page": <int>, "quote": "<verbatim>"}]}
Limits: at most 3 comparators, 8 methods, 5 costs, 5 negative results, 5 limitations, 3 reproducibility items. Keep every free-text field terse: the whole answer must stay well under 9,000 tokens or it is discarded. Empty lists are correct when the paper has none; do not pad. Prefer fewer correct items to many guesses.
"""

SECOND_STRONG = {1, 2, 3, 7, 8, 11, 12, 14}      # independent reader GLM-5.3 (decision-relevant, directly named LLM-agent or verification work)
SECOND_VOLUME = {5, 6, 9, 17, 25, 26, 28, 42, 45}  # independent reader GLM-5.3-Flash (adjacent methods the first pass ranked low)


def main() -> int:
    INSTR.mkdir(parents=True, exist_ok=True)
    (INSTR / "L2.txt").write_text(L2_TEXT, encoding="utf-8", newline="\n")
    rows = list(csv.DictReader((DATA / "reading_list_ranked.csv").open(encoding="utf-8")))
    calls = []

    def add(cid, model, slug, max_out):
        calls.append({"id": cid, "lane": "L2", "model": model, "slug": slug, "files": [f"tmp/sprint/src/papers/{slug}.txt"],
                      "instruction_file": "tmp/sprint/lanes/instr/L2.txt", "max_output_tokens": max_out, "timeout": 1500})
    for r in rows:
        rank = int(r["rank"])
        add(f"L2-{rank:02d}-mimo", MIMO, r["slug"], 16000)
    for r in rows:
        rank = int(r["rank"])
        if rank in SECOND_STRONG:
            add(f"L2-{rank:02d}-glm", GLM, r["slug"], 16000)
        elif rank in SECOND_VOLUME:
            add(f"L2-{rank:02d}-glmflash", GLM_FLASH, r["slug"], 16000)
    (TMP / "lanes" / "calls_l2.json").write_text(json.dumps(calls, indent=1), encoding="utf-8", newline="\n")
    live = json.loads((DATA / "deepinfra_live_check.json").read_text(encoding="utf-8"))["models"]
    est = 0.0
    for c in calls:
        size = (REPO / c["files"][0]).stat().st_size + (INSTR / "L2.txt").stat().st_size
        pin, pout = live[c["model"]]["live_in_out_per_1m"]
        est += size / 4 * pin / 1e6 + 10000 * pout / 1e6
    print(f"calls={len(calls)} primary={sum(1 for c in calls if c['id'].endswith('mimo'))} second={sum(1 for c in calls if not c['id'].endswith('mimo'))} "
          f"estimated_live_usd={est:.2f} (10k output tokens assumed per call)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
