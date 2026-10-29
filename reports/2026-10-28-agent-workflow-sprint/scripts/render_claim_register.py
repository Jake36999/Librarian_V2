"""Render 08-claim-register.md from data/claim_register.csv (revision 2: row-level dispositions)."""
from __future__ import annotations

import csv
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, REPORT  # noqa: E402


def esc(s: str, n: int) -> str:
    return (s or "").replace("|", "/").replace("\n", " ").strip()[:n]


def main() -> int:
    rows = list(csv.DictReader((DATA / "claim_register.csv").open(encoding="utf-8")))
    first = {r["id"]: r for r in csv.DictReader((REPORT / "revision-1" / "data" / "claim_register.csv").open(encoding="utf-8"))}
    outside = [r for r in rows if r["group"] == "outside"]
    local = [r for r in rows if r["group"] == "local"]
    other = [r for r in rows if r["group"] == "other"]
    tags = Counter(r["tag"] for r in outside)
    changed = []
    for r in outside + local:
        old = first.get(r["id"], {})
        o = old.get("tag") or "n/a"
        was_outside = old.get("class") in ("outside_company", "outside_tool", "model_capability", "pricing")
        new = r["tag"] if r["group"] == "outside" else "reclassified as local"
        if was_outside and (o != r["tag"] or r["group"] == "local") and not (o == "local" and r["group"] == "local") and not (o == r["tag"] == "unverified" and r["group"] == "local"):
            changed.append((r["id"], o, new, r["qualifier"]))
    out = ["# Claim register for outside tools and companies (deliverable 8, revision 2)", "",
           "Date: 2026-10-28 (revised the same evening). Source: the Gemini review (`workflow discussion and review - gemini.md`, 549 lines, five separate responses). "
           f"A model extracted every factual assertion with a verbatim quote (3 calls, 178 anchored claims, 99% of quotes found at the cited line); duplicates were merged to {len(rows)} claims. "
           f"Revision 2 replaces the first pass's regular-expression tagging, which operated on claim fragments, with a hand-written disposition for each examined claim (`data/claim_dispositions.csv`), "
           "each with its source, retrieval date and who checked it. A second-pass review corrected several first-pass verdicts; the ones marked below as read in this review were re-read from the primary source here, not taken on trust.", "",
           "**Tags.** *verified*: supported as stated by a primary source read in this sprint, or observed directly. *plausible*: partly supported, or consistent with secondary reports or local data. *unverified*: no supporting source read. "
           "The `qualifier` column records scope corrections (a true number attached to the wrong scope), partial support, general risks and design hypotheses. "
           f"Result for the {len(outside)} claims about outside companies, tools and services: **{tags.get('verified', 0)} verified, {tags.get('plausible', 0)} plausible, {tags.get('unverified', 0)} unverified**. "
           f"A further {len(local)} claims concern our own sessions, data or design heuristics and are listed separately; {len(other)} are opinions or local facts this sprint did not examine (all in `data/claim_register.csv`). "
           "A verified tag means 'supported by the retrieved source', not independently replicated, and it says nothing about the claim's usefulness to the Librarian.", "",
           "**Rule applied.** No design in `06-design-proposals.md` depends on a plausible or unverified claim. The outside facts the designs rest on are: DeepInfra's live model and price listing, DeepInfra's data-privacy documentation (relayed by the fetch tool), "
           "vLLM's documentation of constrained output (verified for vLLM only: it says nothing about any DeepInfra route, so each route must be qualified separately), and fields in Claude Code and Codex logs (measured locally). The OpenAI figures are used only to evaluate Gemini's review.", "",
           "**Added 2026-10-29.** Outside claims introduced by the overseer-workflow review (Agentless, MAST, the scaling-agent-systems paper, Anthropic's multi-agent research article, DeepInfra prices) are tagged in `10-final-report.md`, appendix A. They are not counted in the totals above, which concern the Gemini review.", "",
           "## Primary sources read", "",
           "| Source | Used for | Read |", "|---|---|---|",
           "| `https://openai.com/index/navier-stokes-solution/` | agent counts, durations, message and token totals, Codex consolidation, the Lean phase | 2026-10-28 with the built-in browser. The fetch tool gets HTTP 403, which is why the first pass could not read it |",
           "| `https://github.com/openai/math` (README) and `history.md` | 721 manuscripts in 373 families, about 4,000 problems, three manuscripts withdrawn on 7 October, two added on 26 October | 2026-10-28 |",
           "| `https://docs.vllm.ai/en/latest/features/structured_outputs/` | constrained output types and backends | 2026-10-28 (fetch tool) |",
           "| `https://docs.deepinfra.com/account/data-privacy` | 'Input data is not stored to disk'; 'We do not log the content of your requests'; bulk APIs may store data encrypted for a short, unstated period; Google and Anthropic models follow those companies' policies; metadata logged (request ID, cost, sampling parameters) | 2026-10-28 (fetch tool summary) |",
           "| `https://deepinfra.com/privacy` | the general policy statement | 2026-10-28 (first pass, fetch tool) |",
           "| `https://api.deepinfra.com/v1/openai/models` | rate cards, context lengths, model availability | 2026-10-28T17:05Z |", "",
           "## Outside claims", "", "| ID | Line | Claim (verbatim) | Tag | Qualifier | Basis |", "|---|---:|---|---|---|---|"]
    for r in outside:
        src = f" Source: {esc(r['source'], 90)}." if r["source"] else ""
        out.append(f"| {r['id']} | {r['line']} | {esc(r['quote'], 110)} | {r['tag']} | {r['qualifier']} | {esc(r['note'], 230)}{src} |")
    out += ["", "## Claims about our own sessions, data and design heuristics", "",
            "These were filed as outside claims by the extractor but describe what happened in our sessions, what our data show, or a proposed heuristic. They are not tagged verified, plausible or unverified. "
            "`local_supported` means a measurement or repository record supports it; `local_reported` means only a transcript says so.", "",
            "| ID | Line | Claim (verbatim) | Status | Basis |", "|---|---:|---|---|---|"]
    for r in local:
        status = r["qualifier"] or r["tag"]
        out.append(f"| {r['id']} | {r['line']} | {esc(r['quote'], 110)} | {status} | {esc(r['note'], 200)} |")
    out += ["", "## Changes from the first pass", "",
            "| ID | First pass | Now | Why |", "|---|---|---|---|"]
    for cid, o, n, q in changed:
        why = next((r["note"] for r in rows if r["id"] == cid), "")
        out.append(f"| {cid} | {o} | {n}{(' (' + q + ')') if q else ''} | {esc(why, 170)} |")
    out.append("")
    (REPORT / "08-claim-register.md").write_text("\n".join(out), encoding="utf-8", newline="\n")
    print("outside", len(outside), dict(tags), "| local", len(local), "| other", len(other), "| changed vs first pass", len(changed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
