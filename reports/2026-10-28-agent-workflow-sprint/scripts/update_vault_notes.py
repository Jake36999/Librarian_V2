"""Revision 2: add the full-text reading's costs, negative results and limitations to the draft paper notes in the vault.

Usage: python -I update_vault_notes.py [--write]   (default is a dry run)
Each note written by `write_vault_notes.py` gets one section, 'Second-Pass Additions', inserted before 'Relevance to This Catalogue'
(replaced if it already exists). Only items whose quote was found on the cited PDF page are used. Notes are matched by identifier;
no other note is touched. Nothing is committed.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA  # noqa: E402

VAULT = Path(r"D:\Resource-Library") / "06-Papers"
HEAD = "## Second-Pass Additions (full-text reading, 2026-10-28)"


def clip(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "..."


def main() -> int:
    write = "--write" in sys.argv
    meta = json.loads((DATA / "papers_metadata.json").read_text(encoding="utf-8"))["papers"]
    ident = {m["id"]: slug for slug, m in meta.items() if m.get("status") == "ok"}
    papers = {(p["slug"], p["reader"]): p for p in csv.DictReader((DATA / "lit2_papers.csv").open(encoding="utf-8"))}
    items = defaultdict(list)
    for i in csv.DictReader((DATA / "lit2_items.csv").open(encoding="utf-8")):
        if i["reader"] == "MiMo-V2.6-Pro" and i["verified"] == "verified":
            items[i["slug"]].append(i)
    done = 0
    for path in sorted(VAULT.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        m = re.search(r'^identifier: "([^"]+)"', text, re.M)
        if not m or m.group(1) not in ident or 'status: "draft"' not in text or "sprint" not in text.lower():
            continue
        slug = ident[m.group(1)]
        prim = papers.get((slug, "MiMo-V2.6-Pro"))
        if not prim:
            continue
        by = defaultdict(list)
        for i in items[slug]:
            by[i["field"]].append(i)
        lines = [HEAD, "",
                 "Read in full by MiMo-V2.6-Pro with a fixed checklist; each quote below was found on its cited PDF page by script. That proves the quote exists on that page, not that the paper is right or that the item supports the use made of it here. A person has not read it.", ""]
        lines.append(f"- Evidence type: {prim['evidence_type']}. Applicability to the Librarian, the reader's judgement and not the paper's claim: **{prim['applicability_level'].replace('_', ' ')}** - {clip(prim['applicability_reason'], 220)}")
        for i in by["sample_and_unit"][:1]:
            lines.append(f"- Sample and unit (p. {i['page']}): {clip(i['claim'], 200)}")
        for i in by["comparators"][:3]:
            lines.append(f"- Comparator (p. {i['page']}): {clip(i['claim'], 160)}")
        for i in by["source_availability"][:1]:
            lines.append(f"- Code and data (p. {i['page']}): {clip(i['claim'], 200)}")
        for field, title in (("costs", "Costs the paper reports"), ("negative_results", "Negative or null results"), ("limitations", "Limitations and assumptions"), ("reproducibility", "Reproducibility notes")):
            if by[field]:
                lines += ["", f"{title}:"]
                for i in by[field][:6]:
                    head = i["label"] if field == "costs" else ""
                    claim = clip(i["claim"], 230)
                    lines.append(f"- {head + ': ' if head else ''}{claim} (p. {i['page']})")
                    lines.append(f"  > {clip(i['quote'], 220)}")
        lines.append("")
        block = "\n".join(lines)
        if HEAD in text:
            new = re.sub(re.escape(HEAD) + r".*?(?=\n## )", block.rstrip("\n") + "\n", text, count=1, flags=re.S)
        else:
            new = text.replace("## Relevance to This Catalogue", block + "\n## Relevance to This Catalogue", 1)
        if new != text:
            done += 1
            print(("WRITE " if write else "would write ") + path.name, f"+{len(new) - len(text)} chars")
            if write:
                path.write_text(new, encoding="utf-8", newline="\n")
    print("notes updated" if write else "dry run", done)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
