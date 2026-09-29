"""Measurement: can a known answer be found, and can someone mid-project find
what they need in their own words.

Two sets, both kept in the vault (`.librarian/eval/`), because they describe
this vault's contents and a stranger's vault needs its own:

- `questions.json`: questions with known answers (`expects`: note names), each
  with an intent. Scored hit@k, recall@k, MRR.
- `scenarios.json`: a component of a real system described in that system's
  own words, with `strong` and `acceptable` answers. Scored useful@k, strong@k,
  MRR, run through `donor` on the description alone (V1's protocol, so the
  numbers are comparable).

Both are reported **per slice** (per intent, per source kind), so a gain in
one part of the vault cannot hide a loss in another. An expected answer that is
not a note in the vault is reported, never silently scored as a miss.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import search as search_mod
from .search import Engine

K = 5


def _load(path: Path, key: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return list(json.loads(path.read_text(encoding="utf-8")).get(key) or [])


def _names(response: search_mod.Response) -> list[str]:
    out: list[str] = []
    for r in response.results:
        name = r.fields.get("note", r.name)
        if name not in out:
            out.append(name)
    return out


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def run_questions(engine: Engine, path: Path, k: int = K) -> dict[str, Any]:
    rows = []
    missing: set[str] = set()
    for q in _load(path, "questions"):
        expects = list(q.get("expects") or [])
        missing |= {e for e in expects if engine.index.note_row(e) is None}
        response = search_mod.search(engine, q["question"], q.get("intent", "donor"),
                                     q.get("filters"), limit=k, source=q.get("source") or "")
        # `orient` returns topics and concepts after its sources; count the
        # notes, in order, up to k.
        got = [n for n in _names(response)
               if engine.index.note_row(n) is not None][:k]
        found = [n for n in got if n in expects]
        first = next((i for i, n in enumerate(got, 1) if n in expects), None)
        kind = ""
        if expects and engine.index.note_row(expects[0]) is not None:
            row = engine.index.note_row(expects[0])
            kind = row["kind"] or row["shape"]
        rows.append({"id": q["id"], "intent": q.get("intent", "donor"), "kind": kind,
                     "hit": bool(found), "recall": len(found) / len(expects) if expects else 0.0,
                     "rr": 1.0 / first if first else 0.0, "first": first,
                     "verdict": response.verdict, "returned": got})
    return {"k": k, "total": len(rows), **_summary(rows, ("hit", "recall", "rr")),
            "by_intent": _slices(rows, "intent", ("hit", "rr")),
            "by_kind": _slices(rows, "kind", ("hit", "rr")),
            "misses": [{"id": r["id"], "intent": r["intent"], "returned": r["returned"]}
                       for r in rows if not r["hit"]],
            "expected_but_not_in_vault": sorted(missing)}


def run_scenarios(engine: Engine, path: Path, k: int = K) -> dict[str, Any]:
    rows = []
    missing: set[str] = set()
    for s in _load(path, "scenarios"):
        expects = s.get("expects") or {}
        strong = set(expects.get("strong") or [])
        useful = strong | set(expects.get("acceptable") or [])
        missing |= {e for e in useful if engine.index.note_row(e) is None}
        response = search_mod.search(engine, s["description"], "donor", limit=k)
        got = _names(response)[:k]
        first = next((i for i, n in enumerate(got, 1) if n in useful), None)
        home = s.get("home_topic") or ""
        rows.append({"id": s["id"], "useful": first is not None,
                     "strong": any(n in strong for n in got),
                     "rr": 1.0 / first if first else 0.0,
                     "cross_domain": any(r.name in useful and r.fields.get("topic") != home
                                         for r in response.results[:k]),
                     "expected_to_fail": "expected to fail" in str(s.get("note", "")).lower(),
                     "verdict": response.verdict, "returned": got})
    answerable = [r for r in rows if not r["expected_to_fail"]]
    verdicts: dict[str, dict[str, int]] = {}
    for r in rows:
        bucket = verdicts.setdefault(r["verdict"], {"useful": 0, "not_useful": 0})
        bucket["useful" if r["useful"] else "not_useful"] += 1
    return {"k": k, "total": len(rows), **_summary(rows, ("useful", "strong", "rr",
                                                          "cross_domain")),
            "answerable_only": _summary(answerable, ("useful", "strong", "rr")),
            "verdict_against_outcome": verdicts,
            "misses": [{"id": r["id"], "returned": r["returned"]} for r in rows
                       if not r["useful"]],
            "expected_but_not_in_vault": sorted(missing)}


def _summary(rows: list[dict], keys: tuple[str, ...]) -> dict[str, float]:
    names = {"rr": "mrr"}
    return {names.get(k, k): _mean([float(r[k]) for r in rows]) for k in keys}


def _slices(rows: list[dict], by: str, keys: tuple[str, ...]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for value in sorted({r[by] for r in rows}):
        part = [r for r in rows if r[by] == value]
        out[value or "unknown"] = {"n": len(part), **_summary(part, keys)}
    return out
