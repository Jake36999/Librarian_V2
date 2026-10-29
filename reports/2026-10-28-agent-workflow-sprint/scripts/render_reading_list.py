"""WS6: render 03-reading-list.md from data/reading_list_ranked.csv and data/vault_notes_ranked.csv."""
from __future__ import annotations

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, REPORT  # noqa: E402


def esc(s: str) -> str:
    return (s or "").replace("|", "/").replace("\n", " ").strip()


def main() -> int:
    papers = list(csv.DictReader((DATA / "reading_list_ranked.csv").open(encoding="utf-8")))
    inv = {r["slug"]: r for r in csv.DictReader((DATA / "papers_inventory.csv").open(encoding="utf-8"))}
    meta = json.loads((DATA / "papers_metadata.json").read_text(encoding="utf-8"))["papers"]
    notes = list(csv.DictReader((DATA / "vault_notes_ranked.csv").open(encoding="utf-8")))
    short = {json.loads(l)["slug"] for l in []}
    out = ["# Relevance-ranked reading list (deliverable 3, part 1)", "",
           "Date: 2026-10-28. Corpus: `E:\\Librarian research` (51 files, 50 distinct: two PDFs are byte-identical) plus 26 agent-related notes already in the Resource-Library vault.",
           "", "**How the ranking was made.** A cheap model (DeepSeek-V4.1-Flash) scored each paper 0 to 3 for four categories from its first two pages, last page and heading list: **A** metrics for agent and orchestration performance, **B** schemas for deploying and running agents on kinds of task, **C** long-horizon planning, drift and memory, **D** communication-efficient multi-agent cooperation. "
           "Score = 2 x best category + sum of categories + domain bonus (yes +2, partial +0.5, no -3) - 2 for a keyword trap + 1 if the evidence quote was found at its cited page, -1 if not. Ties favour papers with a method or experiment. "
           "The one-line reasons are model-written; for the top 18 they were corroborated by anchor-verified method cards from two readers (`04-extraction-table.md`). "
           "A paper that scores zero everywhere is a keyword match on something else (for example \"drift\" in class-incremental learning, \"cooperation\" among UAVs, \"agent\" in scheduling), not a candidate.", "",
           "## Papers", "", "| Rank | Paper (title as printed) | Pages | Type | A | B | C | D | Score | Why it is where it is |", "|---:|---|---:|---|:-:|:-:|:-:|:-:|---:|---|"]
    for r in papers:
        out.append(f"| {r['rank']} | {esc(r['title'])[:110]} | {r['pages']} | {esc(r['kind'])} | {r['A']} | {r['B']} | {r['C']} | {r['D']} | {r['score']} | {esc(r['reason'])[:170]} |")
    zero = [r for r in papers if max(int(r[k]) for k in "ABCD") == 0]
    noid = [m["file"] for m in meta.values() if m.get("status") == "no_identifier"]
    dupes = [r["file"] for r in inv.values() if r.get("duplicate_of")]
    out += ["", f"**Zero in all four categories: {len(zero)} papers** (they sit at the bottom of the table). "
            f"**Duplicate removed:** `{dupes[0] if dupes else 'none'}` is byte-identical to its twin. "
            f"**No identifier on the first page:** {len(noid)} files, so bibliographic metadata could not be fetched deterministically for them: " + "; ".join(f"`{n}`" for n in noid) + ".", "",
            "## Vault notes on agent topics (adjacent prior art)", "",
            "These notes were written on 2026-09-19 from the model's general familiarity with the papers, not from a PDF the vault holds (stated in `Paper Index.md`). They are **secondary sources**: useful for orientation, not citable for a section or page. The ranking applies the same rubric to the note text.", "",
            "| Rank | Note | A | B | C | D | Score | Why |", "|---:|---|:-:|:-:|:-:|:-:|---:|---|"]
    for r in notes[:26]:
        out.append(f"| {r['rank']} | {esc(r['slug'])[:60]} | {r['A']} | {r['B']} | {r['C']} | {r['D']} | {r['score']} | {esc(r['reason'])[:150]} |")
    (REPORT / "03-reading-list.md").write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    print("rendered", len(papers), "papers and", len(notes), "notes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
