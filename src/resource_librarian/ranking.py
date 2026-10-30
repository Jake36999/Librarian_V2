"""Personal, source-bound retrieval ranking experiments.

This module deliberately learns only retrieval weights.  It cannot touch model
routing, permissions, profiles, promotion, or host settings.  A person chooses
the active configuration; there is no live traffic split in a one-person vault.
"""
from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from . import evaluation
from .coordination import atomic_write_text
from .rules import Refusal
from .search import Engine, search
from .vault import Vault, jsonl_lines, now_iso

EXPLORATORY_EVENTS = 30
EXPLORATORY_QUERIES = 10
RECOMMENDABLE_EVENTS = 75
RECOMMENDABLE_QUERIES = 20


def _path(vault: Vault) -> Path:
    return vault.librarian / "ranking.json"


def _load(vault: Vault) -> dict[str, Any]:
    try:
        raw = json.loads(_path(vault).read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except (OSError, ValueError):
        pass
    return {"schema_version": 1, "active": "current", "candidates": [], "history": []}


def _save(vault: Vault, data: dict[str, Any]) -> None:
    atomic_write_text(_path(vault), json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _feedback(vault: Vault) -> list[dict[str, Any]]:
    path = vault.work("eval") / "feedback.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in jsonl_lines(path.read_text(encoding="utf-8")):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict) or not str(row.get("query") or "").strip() or \
                str(row.get("verdict") or "") not in ("opened", "taken", "dismissed", "irrelevant"):
            continue
        rows.append(row)
    return rows


def evidence(vault: Vault) -> dict[str, Any]:
    rows = _feedback(vault)
    queries = {" ".join(str(row["query"]).casefold().split()) for row in rows}
    positives = sum(1 for row in rows if row["verdict"] in ("opened", "taken"))
    negatives = len(rows) - positives
    state = "insufficient"
    if len(rows) >= RECOMMENDABLE_EVENTS and len(queries) >= RECOMMENDABLE_QUERIES:
        state = "recommendable"
    elif len(rows) >= EXPLORATORY_EVENTS and len(queries) >= EXPLORATORY_QUERIES:
        state = "exploratory"
    return {"valid_events": len(rows), "distinct_queries": len(queries), "positive": positives,
            "negative": negatives, "state": state,
            "thresholds": {"exploratory": {"events": EXPLORATORY_EVENTS, "queries": EXPLORATORY_QUERIES},
                           "recommendable": {"events": RECOMMENDABLE_EVENTS,
                                             "queries": RECOMMENDABLE_QUERIES}}}


def active_overrides(vault: Vault) -> dict[str, Any]:
    data = _load(vault)
    active = str(data.get("active") or "current")
    if active == "current":
        return {}
    candidate = next((row for row in data.get("candidates", []) if row.get("id") == active), None)
    return dict(candidate.get("heuristics") or {}) if isinstance(candidate, dict) else {}


def status(vault: Vault) -> dict[str, Any]:
    data = _load(vault)
    active = str(data.get("active") or "current")
    return {"active": active, "mode": "Current" if active == "current" else "Candidate",
            "evidence": evidence(vault), "candidates": data.get("candidates", []),
            "history": data.get("history", [])[-20:]}


def generate(vault: Vault, current: dict[str, Any]) -> dict[str, Any]:
    """Generate one bounded candidate from observed, normalised feedback."""
    proof = evidence(vault)
    if proof["state"] == "insufficient":
        return {"generated": False, "evidence": proof,
                "detail": "more local feedback is needed before a ranking candidate is proposed"}
    rows = _feedback(vault)
    positive = sum(1 for row in rows if row["verdict"] in ("opened", "taken"))
    ratio = positive / max(1, len(rows))
    # Stay close to the current config: this is a personal candidate to
    # benchmark, not an opaque trained ranker.  The values are bounded to
    # existing heuristic semantics and remain independently reversible.
    coverage = float(current.get("coverage_weight", 1.0))
    name = float(current.get("name_weight", 1.2))
    candidate = {
        "coverage_weight": round(min(2.0, max(0.4, coverage * (1.08 if ratio >= .5 else .92))), 3),
        "name_weight": round(min(2.5, max(0.4, name * (1.03 if ratio >= .5 else .97))), 3),
    }
    data = _load(vault)
    row = {"id": f"ranking-{now_iso()[:10]}-{secrets.token_hex(3)}", "version": 1,
           "created_at": now_iso(), "state": proof["state"], "heuristics": candidate,
           "evidence": proof, "benchmark": None, "selected_at": ""}
    data.setdefault("candidates", []).append(row)
    _save(vault, data)
    return {"generated": True, "candidate": row, "active": data.get("active", "current")}


def _candidate(vault: Vault, candidate_id: str) -> dict[str, Any]:
    row = next((item for item in _load(vault).get("candidates", []) if item.get("id") == candidate_id), None)
    if not isinstance(row, dict):
        raise KeyError(f"no ranking candidate {candidate_id!r}")
    return row


def benchmark_measure(vault: Vault, engine: Engine, candidate: dict[str, Any],
                      k: int = 5) -> dict[str, Any]:
    """Measure one candidate while the caller owns the index worker.

    This deliberately does not write ``ranking.json``: a Core-backed caller
    runs the retrieval work through ``IndexService`` and records the resulting
    report on its VaultWriter thread after the SQLite callback returns.
    """
    candidate_id = str(candidate["id"])
    folder = vault.work("eval")
    saved = dict(engine.h)
    try:
        current_q = evaluation.run_questions(engine, folder / "questions.json", k)
        current_s = evaluation.run_scenarios(engine, folder / "scenarios.json", k)
        engine.h.update(candidate.get("heuristics") or {})
        engine.forget()
        candidate_q = evaluation.run_questions(engine, folder / "questions.json", k)
        candidate_s = evaluation.run_scenarios(engine, folder / "scenarios.json", k)
    finally:
        engine.h.clear()
        engine.h.update(saved)
        engine.forget()
    report = {"at": now_iso(), "candidate": candidate_id, "k": k,
              "quality": {"questions": evaluation.compare(current_q, candidate_q, ("current", "candidate")),
                          "current_hit": current_q.get("hit", 0.0), "candidate_hit": candidate_q.get("hit", 0.0),
                          "current_mrr": current_q.get("mrr", 0.0), "candidate_mrr": candidate_q.get("mrr", 0.0)},
              "coverage": {"current": current_q.get("by_kind", {}), "candidate": candidate_q.get("by_kind", {}),
                           "slices": {"current": current_q.get("by_slice", {}),
                                      "candidate": candidate_q.get("by_slice", {})}},
              "safety": {"current_exclusions": current_q.get("by_slice", {}),
                         "candidate_exclusions": candidate_q.get("by_slice", {}),
                         "expected_missing": sorted(set(current_q.get("expected_but_not_in_vault", [])) |
                                                    set(candidate_q.get("expected_but_not_in_vault", [])))},
              "scenarios": {"current": current_s, "candidate": candidate_s},
              "note": "Measured offline; selecting the candidate remains a person decision."}
    return report


def record_benchmark(vault: Vault, candidate_id: str, report: dict[str, Any]) -> dict[str, Any]:
    """Persist a completed benchmark outside the IndexService worker."""
    data = _load(vault)
    for item in data.get("candidates", []):
        if item.get("id") == candidate_id:
            item["benchmark"] = report
            break
    else:
        raise KeyError(f"no ranking candidate {candidate_id!r}")
    _save(vault, data)
    return report


def benchmark(vault: Vault, engine: Engine, candidate_id: str, k: int = 5) -> dict[str, Any]:
    """Compatibility wrapper for offline/direct callers."""
    candidate = _candidate(vault, candidate_id)
    return record_benchmark(vault, candidate_id, benchmark_measure(vault, engine, candidate, k))


def compare(vault: Vault, engine: Engine, query: str, intent: str = "donor", limit: int = 10,
            candidate_id: str = "") -> dict[str, Any]:
    data = _load(vault)
    wanted = candidate_id or next((str(item.get("id")) for item in data.get("candidates", [])
                                   if item.get("id") != data.get("active")), "")
    row = _candidate(vault, wanted) if wanted else None
    saved = dict(engine.h)
    try:
        current = search(engine, query, intent, limit=limit).to_dict()
        if row is not None:
            engine.h.update(row.get("heuristics") or {})
            engine.forget()
            candidate = search(engine, query, intent, limit=limit).to_dict()
        else:
            candidate = {"results": [], "verdict": "no candidate", "ranking": ""}
    finally:
        engine.h.clear()
        engine.h.update(saved)
        engine.forget()
    return {"mode": "Compare", "candidate": wanted, "current": current, "candidate_result": candidate,
            "explanation": "Both result sets use the same query; only the candidate's bounded retrieval weights differ."}


def select(vault: Vault, candidate_id: str) -> dict[str, Any]:
    data = _load(vault)
    candidate = _candidate(vault, candidate_id)
    if not candidate.get("benchmark"):
        # The card promises a benchmarked candidate; the person selects on evidence.
        raise Refusal("RANKING_UNBENCHMARKED", f"candidate {candidate_id} has no recorded "
                                               "benchmark; run ranking_benchmark before selecting it")
    before = str(data.get("active") or "current")
    data["active"] = candidate_id
    data.setdefault("history", []).append({"at": now_iso(), "action": "select", "from": before,
                                             "to": candidate_id})
    for item in data.get("candidates", []):
        if item.get("id") == candidate_id:
            item["selected_at"] = now_iso()
    _save(vault, data)
    return {"active": candidate_id, "previous": before, "mode": "Candidate"}


def restore(vault: Vault) -> dict[str, Any]:
    data = _load(vault)
    history = data.get("history", [])
    previous = next((str(row.get("from")) for row in reversed(history)
                     if row.get("action") in ("select", "restore")), "current")
    before = str(data.get("active") or "current")
    data["active"] = previous
    data.setdefault("history", []).append({"at": now_iso(), "action": "restore", "from": before,
                                             "to": previous})
    _save(vault, data)
    return {"active": previous, "previous": before, "restored": True, "mode": "Current" if previous == "current" else "Candidate"}

