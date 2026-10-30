"""Re-check every Tier A closure of an audited session (G5 readiness R4).

A verifier result says a predicate holds. This module checks that claim again,
by a different route where it can, so a measured Tier A share counts only
closures that stand up. Each re-check states its method:

- `independent`: different code from the verifier's own (its own text
  normalisation, a direct read of the stored records);
- `rerun`: the same code run again. This proves only that the result
  reproduces, not that the verifier is right, and it is labelled so.

A closure whose re-check fails is a **false closure**. G5's proposed
decision rule needs zero of them.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from . import audit_events, closure
from .vault import Vault


def _plain(text: str) -> str:
    """Case-folded letters and digits only: deliberately unlike clerk.normal."""
    text = unicodedata.normalize("NFKC", str(text)).casefold()
    return re.sub(r"[^\w]+", " ", text).strip()


def _evidence(vault: Vault, ident: str) -> dict[str, Any] | None:
    for path in vault.evidence.glob(f"*/{ident}.json"):
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def _quote(vault, result, session):
    params = result.get("params") or {}
    record = _evidence(vault, str(params.get("evidence", "")))
    if record is None:
        return "fails", "the evidence record is missing"
    needle = _plain(params.get("quote", ""))
    if not needle:
        return "unsupported", "no quote was recorded with the result"
    found = any(needle in _plain(s) for s in _strings(record.get("payload")))
    return ("holds", "") if found else ("fails", "the quote is not in the evidence text")


def _integrity(vault, result, session):
    ident = str((result.get("params") or {}).get("evidence", ""))
    record = _evidence(vault, ident)
    if record is None:
        return "fails", "the evidence record is missing"
    body = json.dumps({"kind": record["kind"], "source": record["source"],
                       "fetched_at": record["fetched_at"], "payload": record["payload"]},
                      sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:32]
    return ("holds", "") if digest == ident else ("fails", "the content hash does not match")


def _coverage(vault, result, session):
    params = result.get("params") or {}
    from .dik import path_for
    path = path_for(vault, str(params.get("source", "")))
    if not path.is_file():
        return "fails", "the coverage record is missing"
    data = json.loads(path.read_text(encoding="utf-8")).get("data") or []
    wanted = set(params.get("parts") or [])
    rows = [d for d in data if not wanted or d.get("id") in wanted or d.get("locator") in wanted]
    expected = params.get("status") or "observed"
    ok = bool(rows) and all(d.get("status") == expected for d in rows)
    return ("holds", "") if ok else ("fails", f"not every named part is {expected!r}")


def _claim_run(vault, result, session):
    ident = str((result.get("params") or {}).get("run", ""))
    path = vault.librarian / "claims" / "runnable.jsonl"
    runs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()] if path.is_file() else []
    mine = [r for r in runs if r.get("type") == "run" and r.get("id") == ident]
    ok = bool(mine) and mine[-1].get("verdict") == "confirmed"
    return ("holds", "") if ok else ("fails", "the latest stored run is not confirmed")


def _diff_clean(vault, result, session):
    from .coordination import fingerprint
    audit = session.audit
    for ident in result.get("artifacts") or []:
        artifact = audit.artifacts[ident]
        if fingerprint(vault.root / artifact["path"]) != artifact["fingerprint"]:
            return "fails", f"{ident} no longer matches its recorded fingerprint"
    return "holds", ""


def _citation(vault, result, session):
    from . import notes
    rel = str((result.get("params") or {}).get("note", ""))
    path = vault.root / rel
    if not path.is_file():
        return "fails", "the note is missing"
    note = notes.load(path)
    ids = note.frontmatter.get("evidence") or []
    if any(_evidence(vault, str(i)) is None for i in ids):
        return "fails", "a cited evidence record is missing"
    stems = {p.stem.casefold() for p in vault.root.rglob("*.md")}
    missing = [link for link in notes.wikilinks(note.body)
               if link.rsplit("/", 1)[-1].casefold() not in stems]
    return ("fails", f"unresolved links: {missing[:3]}") if missing else ("holds", "")


def _boundary(vault, result, session):
    calls = session.contract_calls.get(result["contract"], [])
    crossed = [c for c in calls if c.get("class") not in ("read", "untrusted", "stage")]
    return ("fails", "a call wrote outside staging") if crossed else ("holds", "")


def _rerun(verifier):
    def check(vault, result, session, index_run=None):
        from . import research_grains
        context = {"session": session}
        if index_run is not None:
            context["index_run"] = index_run
        again = research_grains.run(verifier, vault, result.get("params") or {}, **context)
        if again.outcome == "pass" and again.statement == result.get("statement"):
            return "holds", ""
        return "fails", f"re-run gave {again.outcome}: {again.statement[:200]}"
    return check


INDEPENDENT = {"quote.located": _quote, "evidence.integrity": _integrity,
               "coverage.status": _coverage, "claim_run.passed": _claim_run,
               "target.diff_clean": _diff_clean, "citation.resolves": _citation,
               "boundary.staged": _boundary}
RERUN = ("arithmetic.reproduces", "index.findable", "schema.valid")


def audit(vault: Vault, session: Any, index_run: Any = None) -> dict[str, Any]:
    """Re-check every latest Tier A pass of the session at its current epoch."""
    state = session.audit
    rows = []
    for rid, req in state.requirements.items():
        for predicate in req["predicates"]:
            latest = audit_events._latest_result(state, rid, predicate)
            if not latest or latest[1]["outcome"] != "pass":
                continue
            ident, result = latest
            verifier = closure.base_id(result["verifier"])
            bound = (req.get("verifiers") or {}).get(predicate, {}).get("params", {})
            loose = closure.unbound_subject(verifier, bound, result.get("params") or {})
            if loose:
                # Independent of the model's choice: a pass on a subject the
                # person did not bind establishes nothing about the predicate.
                rows.append({"result": ident, "requirement": rid, "predicate": predicate,
                             "verifier": verifier, "statement": result.get("statement", ""),
                             "method": "binding", "verdict": "fails",
                             "why": f"subject not bound by the person: {', '.join(loose)}"})
                continue
            if verifier in INDEPENDENT:
                method, (verdict, why) = "independent", INDEPENDENT[verifier](
                    vault, result, session)
            elif verifier in RERUN:
                method, (verdict, why) = "rerun", _rerun(verifier)(vault, result, session,
                                                                   index_run)
            else:
                method, verdict, why = "none", "unsupported", "no re-check for this verifier"
            rows.append({"result": ident, "requirement": rid, "predicate": predicate,
                         "verifier": verifier, "statement": result.get("statement", ""),
                         "method": method, "verdict": verdict,
                         **({"why": why} if why else {})})
    return {"checked": len(rows),
            "false_closures": [r for r in rows if r["verdict"] == "fails"],
            "unsupported": [r for r in rows if r["verdict"] == "unsupported"],
            "rows": rows}
