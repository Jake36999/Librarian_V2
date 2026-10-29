"""WS8: write draft paper notes into the Resource-Library vault (the owner chose this write-back).

Usage: python -I write_vault_notes.py [--write]   (default is a dry run that prints the plan)
Inputs: data/reading_list_ranked.csv, data/papers_metadata.json (Crossref/arXiv, fetched), data/method_cards.jsonl (MiMo cards whose quotes were anchor-verified).
Rules: follows the vault's `_Template - Research Paper.md`; status is "draft"; never overwrites a file; no existing note is edited.
Bibliographic metadata comes from the fetched records, never from a model's memory (vault rule).
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA  # noqa: E402

VAULT = Path(r"D:\Resource-Library") / "06-Papers"
TOP = 12
CATS = {"A": "metrics for agent and orchestration performance", "B": "schemas for deploying and running agents on kinds of task",
        "C": "long-horizon planning, drift and memory", "D": "communication-efficient multi-agent cooperation"}
BOTTOM = {
    1: "Proposes ReflectiChain, which keeps a long-horizon LLM agent from drifting away from its initial instructions by checking each step's rationale against the original constraints and re-anchoring when similarity falls, and defines metrics (semantic-execution drift, semantic fidelity index) to measure that drift.",
    2: "Describes a Thought Management System that keeps a hierarchical task tree with dependencies, expands and validates it step by step, and measures orchestration with task completion rate, efficiency and resource utilisation.",
    3: "Argues that resource-limited mobile agents should reason with structured, cacheable knowledge packs requested and verified at the moment of need, and reports fewer reasoning steps and violations in a simulated UAV setting.",
    4: "Surveys the architectures, reasoning patterns, evaluation metrics and deployment trade-offs (cascade routing, drift monitoring) of AI agents used for data annotation.",
    5: "Combines reinforcement learning and LLM agents so that robots broadcast only a few human-readable features under a hard bandwidth budget, cutting message size by about 60% at equal reward in simulation.",
    6: "Proposes trust-modulated cooperation among planner, researcher and critic LLM agents and evaluates it with convergence and agreement metrics such as rounds-to-approval; the approval-rate differences it reports were not statistically significant.",
    7: "Plans robot manipulation by searching a tree of discrete action skills, branching from priors and reflecting on failed branches, with parallel search across simulated worlds.",
    8: "Defines a verify-before-act task and benchmark for smart-home agents, a dangerous-error safety metric, and a confidence-aware selective tree-of-thoughts router, with exact federated aggregation for fine-tuning.",
    9: "Composes a reward model from three tiers (long-horizon reasoning, step-level verification, integrated judgment) and bounds adversarial-response detection by the number of verification checkpoints and reasoning depth.",
    10: "Reviews agentic AI patterns, a four-stage operational framework, agent-type taxonomies and memory architectures; a survey with no new experiments.",
    11: "Extends HDDL with agent types so hierarchical multi-agent planning problems can run as Gym environments, with metrics for plan difficulty and for training and deployment.",
    12: "Grounds long-horizon LLM planning in a latent world model and a reflection step, and evaluates it on the Sema-Sim benchmark with rationale-consistency, constraint-compliance and trajectory-instability scores.",
}


def safe(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|]', "", s)).strip()


def main() -> int:
    write = "--write" in sys.argv
    ranked = list(csv.DictReader((DATA / "reading_list_ranked.csv").open(encoding="utf-8")))[:TOP]
    meta = json.loads((DATA / "papers_metadata.json").read_text(encoding="utf-8"))
    cards = [json.loads(l) for l in (DATA / "method_cards.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    plan = []
    for r in ranked:
        m = meta["papers"].get(r["slug"], {})
        rank = int(r["rank"])
        # the call id (P2-rNN-mimo) carries the reading-list rank; the model's own `paper` string is not reliable
        mine = [c for c in cards if c.get("call") == f"P2-r{rank:02d}-mimo" and c.get("verified") == "verified"]
        if m.get("status") != "ok" or not mine or rank not in BOTTOM:
            plan.append((rank, r["title"][:60], "SKIPPED", f"metadata={m.get('status')} cards={len(mine)}"))
            continue
        authors = m.get("authors") or []
        family = authors[0].split()[-1] if authors else "Unknown"
        family = family.title() if family.isupper() else family
        base = safe(f"{family}, {m.get('year')} - {re.sub(r'[:?]', '', m['title'])}")
        if len(base) > 72:
            base = base[:72].rsplit(" ", 1)[0]  # cut at a word boundary, as the existing notes do
        name = base.rstrip(" .,-") + ".md"
        path = VAULT / name
        doi = m["id"] if m["source"] in ("crossref", "publisher_record") else ""
        ident_kind = "doi" if m["source"] in ("crossref", "publisher_record") else "arxiv"
        kind = "preprint" if m["source"] == "arxiv" or m.get("type") in ("posted-content",) else ("journal_article" if m.get("type") == "journal-article" else "conference_paper")
        cats = sorted({c["category"] for c in mine})
        fm = ["---", f'uuid: "{uuid.uuid4()}"', 'type: "research_paper"', f"title: {json.dumps(m['title'], ensure_ascii=False)}", f"authors: {json.dumps(authors, ensure_ascii=False)}",
              f"year: {m.get('year')}", f"venue: {json.dumps(m.get('venue') or '', ensure_ascii=False)}", f'paper_kind: "{kind}"', f'identifier_kind: "{ident_kind}"', f'identifier: "{m["id"]}"',
              f'canonical_url: "{("https://doi.org/" + doi) if doi else m.get("url", "")}"', 'primary_topic: "Agentic AI & Models"', 'status: "draft"', 'sensitivity: "normal"',
              f"evidence_count: {len(mine)}", f'metadata_captured_at: "{meta.get("retrieved_at", "")}"', "---", ""]
        body = [f"# {name[:-3]}", "",
                f"> Draft written 2026-10-28 from the PDF text (`{r['file']}`, {r['pages']} pages) by MiMo-V2.6-Pro; every quote below was found at its cited page by script (`anchor_verification`). A person has not read this paper for this note. Bibliographic fields were fetched from {'Crossref' if doi else 'arXiv'}, not recalled.", "",
                "## Bottom Line", BOTTOM[rank], "", "## Claim", "What the paper proposes or defines, as extracted (section, page):"]
        for c in mine:
            body += [f"- **{c['name']}** (category {c['category']}) - {c['what']} (section {c['section']}, p. {c['page']})", f"  > {c['quote'].strip()}"]
        body += ["", "## Method"] + [f"- **{c['name']}**: {c['mechanism']}" for c in mine]
        body += ["", "## Evidence & Limits", "- Evidence the authors report:"] + [f"  - {c['name']}: {c['evidence']}" for c in mine if c.get("evidence")]
        lim = [c for c in mine if c.get("limits") and str(c["limits"]).lower() != "none"]
        body += ["- Limitations the authors state:"] + ([f"  - {c['name']}: {c['limits']}" for c in lim] or ["  - none found by the reader"])
        body += ["- Limitations they do not state: not assessed. Results are the authors' own, from their simulations, benchmarks or surveys; none evaluates delegation to cheaper models on software work.", "",
                 "## Relevance to This Catalogue",
                 "Read in the 2026-10-28 agent-workflow sprint for " + "; ".join(f"{k} ({CATS[k]})" for k in cats) + ". The reading-list rank is {0} of 50 distinct papers in the research folder.".format(r["rank"]),
                 "", "Hypotheses for the Librarian (from the sprint, not claims of the paper):"] + [f"- {c['librarian_use']}" for c in mine[:3] if c.get("librarian_use")]
        body += ["", "## Semantic Links", "- [parent_topic:: [[Topic - Agentic AI & Models]]]", "- [paper_hub:: [[Paper Index]]]", "",
                 "## Citation", f"{', '.join(authors[:6])}{' et al.' if len(authors) > 6 else ''}. \"{m['title']}\" {m.get('venue') or 'arXiv'}, {m.get('year')}. {('doi:' + doi) if doi else ('arXiv:' + m['id'])}.", ""]
        text = "\n".join(fm + body)
        if f"--show={rank}" in sys.argv:
            sys.stdout.buffer.write((text + chr(10)).encode('utf-8'))
        plan.append((rank, name, "EXISTS" if path.exists() else "NEW", f"{len(mine)} cards, {len(text)} chars"))
        if write and not path.exists():
            path.write_text(text, encoding="utf-8", newline="\n")
    for p in plan:
        print(p)
    print("written" if write else "dry run", sum(1 for p in plan if p[2] == "NEW"), "new notes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
