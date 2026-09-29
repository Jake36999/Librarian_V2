"""Concept candidates: a term that recurs across sources, staged for review.

`promote.py`'s own docstring names the gap this closes: "the concept
lifecycle, candidates and thresholds, is M4b; [promotion] only links to what
exists." This module is that lifecycle's candidate side. A term the `terms`
clerk task has already recorded as `term_usage` evidence (each usage already
grounded: the sentence is verified to contain the term, `clerk.verify`) is
worth a Concept note once it has been seen in more than one source - a
one-off mention is a fact about that source, not yet a reusable concept.

Nothing here drafts a definition. A definition is synthesis, not something
quoted from evidence the way a usage is; the candidate stages only what is
already grounded (the term, its usages, which sources used it), and a
person's own words become the Definition at accept time
(`staging.decide(..., fields={"definition": ...})`).

Re-running `candidates()` never restages a term already staged, already a
Concept note, or already decided (accepted or rejected): staging an id is
enough to remember that.
"""
from __future__ import annotations

import re
from typing import Any

from .evidence import EvidenceStore
from .staging import StagingStore
from .vault import Vault

MIN_SOURCES = 2          # a term seen in one source alone is not yet a concept
MAX_USAGES = 8            # kept on the candidate; the rest stay in the evidence store


def candidates(vault: Vault, min_sources: int = MIN_SOURCES) -> dict[str, Any]:
    """Stage one concept candidate per term seen across at least
    `min_sources` distinct sources' `term_usage` evidence."""
    store = EvidenceStore(vault)
    staging = StagingStore(vault)
    grouped: dict[str, dict[str, Any]] = {}
    for record in store.iter("term_usage"):
        term = str(record.payload.get("term", "")).strip()
        sentence = str(record.payload.get("sentence", "")).strip()
        if not term or not sentence:
            continue
        bucket = grouped.setdefault(term.lower(), {"name": term, "sources": set(),
                                                    "usages": []})
        bucket["sources"].add(record.source)
        if len(bucket["usages"]) < MAX_USAGES:
            bucket["usages"].append({"source": record.source, "sentence": sentence})

    concepts_dir = vault.root / "Concepts"
    existing = {p.stem.lower() for p in concepts_dir.glob("*.md")} if concepts_dir.is_dir() \
        else set()
    staged: list[str] = []
    for key, bucket in grouped.items():
        if len(bucket["sources"]) < min_sources or key in existing:
            continue
        item_id = f"concept-{re.sub(r'[^a-z0-9]+', '-', key).strip('-')[:50]}"
        try:
            staging.load(item_id)
            continue                                    # staged or decided before
        except TypeError:
            pass
        staging.add({"id": item_id, "kind": "concept", "name": bucket["name"],
                    "usages": bucket["usages"], "sources": sorted(bucket["sources"]),
                    "proposed_by": "terms"})
        staged.append(item_id)
    return {"scanned": len(grouped), "staged": staged}
