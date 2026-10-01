"""The arithmetic in a note, checked against the data it came from (P7; V1's provenance.py).

A repository note makes two kinds of statement. *That the planner is the harder half* is a
judgement and no tool can verify it. *That the repository has 1,436 files* is arithmetic over
a survey, and if the note and the survey disagree one of them is wrong. This checks the
arithmetic and leaves the judgement alone.

Each number the note states about the repository's structure - files, source or test files,
files in one language, modules, endpoints, entry points - is looked up in the source's own
evidence (its survey and code-structure records):

- **supported**: the evidence holds that quantity, with that number;
- **contradicted**: the evidence holds that quantity with a different number - a defect in
  the note (or the survey was capped: a capped count is never called a contradiction);
- **unsupported**: the evidence does not model that quantity. Reported, not failed - a false
  accusation is worse than a missed one.
"""
from __future__ import annotations

import json
import re
from typing import Any

from . import notes
from .evidence import EvidenceStore
from .vault import Vault

LANGUAGES = ("python", "javascript", "typescript", "go", "rust", "java", "kotlin", "ruby",
             "csharp", "cpp", "c", "php")
CLAIM = re.compile(
    r"(?<![\w.,])(?P<n>\d{1,3}(?:,\d{3})+|\d+)\s+(?P<what>source files|test files|files|"
    r"modules|endpoints|routes|entry points|(?P<lang>" + "|".join(LANGUAGES) + r") files)\b",
    re.I)
SKIP_SECTIONS = ("Evidence",)
CAPS = {"modules": 80, "endpoints": 60, "entry points": 40}   # what the survey keeps at most


def quantities(vault: Vault, fm: dict[str, Any]) -> dict[str, tuple[int, str, bool]]:
    """(number, evidence id, capped) per quantity the evidence models."""
    store = EvidenceStore(vault)
    out: dict[str, tuple[int, str, bool]] = {}
    for ref in fm.get("evidence") or []:
        record = store.get(str(ref))
        if record is None:
            continue
        p = record.payload
        if record.kind == "survey" and isinstance(p.get("files"), int):
            out.setdefault("files", (p["files"], record.id, bool(p.get("truncated"))))
        elif record.kind == "code_structure":
            if isinstance(p.get("files"), int):
                out["files"] = (p["files"], record.id, False)       # the full checkout wins
            if isinstance(p.get("test_files"), int):
                out["test files"] = (p["test_files"], record.id, False)
            if isinstance(p.get("source_files_read"), int):
                out["source files"] = (p["source_files_read"], record.id,
                                       bool(p.get("limited")))
            for lang, count in (p.get("languages") or {}).items():
                out[f"{lang.lower()} files"] = (int(count), record.id, False)
            out["modules"] = (len(p.get("modules") or []), record.id,
                              len(p.get("modules") or []) >= CAPS["modules"])
        elif record.kind == "access_point":
            routes = len(p.get("routes") or [])
            out["endpoints"] = out["routes"] = (routes, record.id, routes >= CAPS["endpoints"])
            entries = len(p.get("entry_points") or [])
            out["entry points"] = (entries, record.id, entries >= CAPS["entry points"])
    return out


def check(vault: Vault, path, fm: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    note = notes.load(path)
    fm = fm if fm is not None else note.frontmatter
    known = quantities(vault, fm)
    out = []
    for heading, text in note.sections().items():
        if heading in SKIP_SECTIONS:
            continue
        for m in CLAIM.finditer(text):
            stated = int(m.group("n").replace(",", ""))
            what = m.group("what").lower()
            found = known.get(what)
            start = max(0, m.start() - 60)
            row = {"claim": " ".join(text[start:m.end() + 20].split()), "section": heading,
                   "quantity": what, "stated": stated}
            if found is None:
                out.append({**row, "outcome": "unsupported"})
                continue
            recorded, evidence, capped = found
            if recorded == stated:
                outcome = "supported"
            elif capped and stated > recorded:
                outcome = "unsupported"                 # the survey stopped counting there
            else:
                outcome = "contradicted"
            out.append({**row, "outcome": outcome, "recorded": recorded, "evidence": evidence,
                        **({"capped": True} if capped else {})})
    return out


def run(vault: Vault, conn, source: str = "", limit: int = 50) -> dict[str, Any]:
    rows = conn.execute("SELECT name, path, frontmatter FROM note WHERE shape = 'source'"
                        + (" AND name = ?" if source else "") + " ORDER BY name",
                        (source,) if source else ()).fetchall()
    results = []
    for row in rows:
        claims = check(vault, vault.root / row["path"], json.loads(row["frontmatter"]))
        if claims:
            results.append({"source": row["name"], "claims": claims})
        if len(results) >= limit:
            break
    every = [c for r in results for c in r["claims"]]
    return {"checked": len(rows), "with_claims": len(results),
            "supported": sum(c["outcome"] == "supported" for c in every),
            "contradicted": sum(c["outcome"] == "contradicted" for c in every),
            "unsupported": sum(c["outcome"] == "unsupported" for c in every),
            "results": results}
