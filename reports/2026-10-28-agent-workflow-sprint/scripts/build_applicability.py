"""Revision 2: an independent second opinion on each paper's applicability level.

The primary reader judged applicability while reading, and was generous (it called swarm reinforcement learning "bounded analogy").
A judge from another model family sees only the reading record (title, evidence type, method list, the reader's reason) and applies a
stricter written rubric. Papers where the two disagree are listed as contested in 03-reading-list.md; neither level is treated as truth.
Writes tmp/sprint/packets/AP-batch-01.txt, tmp/sprint/lanes/instr/AP.txt, tmp/sprint/lanes/calls_ap.json
"""
from __future__ import annotations

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_lanes import COMMON, INSTR, PACKETS  # noqa: E402
from common import DATA, TMP  # noqa: E402

# GLM-5.3 was tried first and leaked its reasoning into the answer until the output cap (no usable JSON), as it did twice in the first pass.
QWEN = "Qwen/Qwen3.5-397B-A17B"

AP_TEXT = COMMON + """
TASK: classify how applicable each paper is to one project, from a short reading record of the paper (never from background knowledge about it).
The project (the Librarian) is a research and agentic co-work application where a token-limited closed-weight lead model (Claude or Codex) delegates work to cheaper models and parallel agents, and where the lead must check what comes back. Relevant needs: measuring orchestration cost and quality; schemas for deploying agents; long-horizon plan and constraint tracking, memory and handoffs; cheaper communication between agents; mechanically checking agent output.
Levels:
 direct_candidate = the paper studies the same class of control, verification or coordination problem for LLM or software agents, with a method or measurement that could be adopted or tested almost as described;
 bounded_analogy = one named mechanism, schema, metric or caution in the paper could be implemented for LLM delegation or checking with a stated adaptation, although the environment differs;
 out_of_scope = it would need a different learning setup, a physical or non-software system, or a domain with no concrete mechanism that carries over. A generic similarity (agents, cooperation, learning, graphs) is not enough.
Output schema: {"papers": [{"rank": <int>, "level": "direct_candidate|bounded_analogy|out_of_scope", "mechanism": "<the one named mechanism that carries over, at most 12 words, or none>", "reason": "<at most 25 words>"}]}
Return one object per paper in the packet.
"""


def main() -> int:
    papers = [p for p in csv.DictReader((DATA / "lit2_papers.csv").open(encoding="utf-8")) if p["reader"] == "MiMo-V2.6-Pro"]
    items = [i for i in csv.DictReader((DATA / "lit2_items.csv").open(encoding="utf-8")) if i["reader"] == "MiMo-V2.6-Pro" and i["field"] == "methods" and i["verified"] == "verified"]
    parts = []
    for p in sorted(papers, key=lambda p: int(p["rank"])):
        ms = [f"[{i['category']}] {i['label'][:60]}" for i in items if i["slug"] == p["slug"]][:8]
        parts.append(f"=== PAPER {int(p['rank'])} ===\nTITLE: {p['title']}\nEVIDENCE TYPE: {p['evidence_type']}\nMETHODS: {'; '.join(ms) or 'none extracted'}\nREADER'S REASON: {p['applicability_reason']}\n")
    PACKETS.mkdir(parents=True, exist_ok=True)
    INSTR.mkdir(parents=True, exist_ok=True)
    (INSTR / "AP.txt").write_text(AP_TEXT, encoding="utf-8", newline="\n")
    (PACKETS / "AP-batch-01.txt").write_text("\n".join(parts), encoding="utf-8", newline="\n")
    call = [{"id": "AP-02-qwen", "lane": "AP", "model": QWEN, "files": ["tmp/sprint/packets/AP-batch-01.txt"], "instruction_file": "tmp/sprint/lanes/instr/AP.txt", "max_output_tokens": 12000, "timeout": 900}]
    (TMP / "lanes" / "calls_ap.json").write_text(json.dumps(call, indent=1), encoding="utf-8", newline="\n")
    print("papers in packet:", len(parts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
