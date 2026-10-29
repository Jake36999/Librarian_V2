"""Tier A checks for the grains of a research round (HARNESS-06).

A research session is checked grain by grain, never as a whole. Each grain
with a deterministic check closes through one of the registered verifiers
(`closure.VERIFIERS`), and its result carries a statement: the exact instance
of that verifier's predicate the check established, such as "the quote is
present in evidence `<id>` at offset N", never "the claim is true".

| Grain | Verifier | Built on |
| --- | --- | --- |
| intake | evidence.integrity | `EvidenceStore.intact`, the staged item's `quality.py` verdict |
| coverage | coverage.status | the source's `dik.py` record, with "not examined" named |
| quote | quote.located | `clerk.locate` over one evidence record's text fields |
| arithmetic | arithmetic.reproduces | `provenance.check` against the evidence counts |
| executable claim | claim_run.passed | the latest person-initiated run in `claim_run.py` |
| findability | index.findable | `promote.findability` (promotion step 5) |
| staging integrity | target.diff_clean | each artifact's fingerprint and the contract's targets |

Synthesis and interpretation have no check here. They are staged for the
person, whose acceptance closes them (`human_judgment`). A predicate that no
check can establish gets the outcome `no_suitable_tool`, and stays with the
person instead of being closed by something weaker.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import closure
from .vault import Vault

NO_SUITABLE_TOOL = "no_suitable_tool"


@dataclass(frozen=True)
class Check:
    outcome: str                      # pass | fail | unavailable | inconclusive
    strength: str                     # exact | bounded: what the verifier can give
    statement: str                    # the predicate instance established, never more
    detail: str = ""
    evidence: tuple[str, ...] = field(default_factory=tuple)


def _param(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"this check needs params[{key!r}], a non-empty string")
    return value.strip()


# ------------------------------------------------------------------ the checks

def integrity(vault: Vault, params: dict[str, Any], **_: Any) -> Check:
    """Intake: the evidence matches its content hash; the staged item's capture
    verdict, when one is named, is usable."""
    from .evidence import EvidenceStore
    ident = _param(params, "evidence")
    record = EvidenceStore(vault).get(ident)
    if record is None:
        return Check("fail", "exact", f"evidence `{ident}` is not in the evidence store")
    if not EvidenceStore.intact(record):
        return Check("fail", "exact", f"evidence `{ident}` no longer matches its content hash",
                     evidence=(ident,))
    item = params.get("item")
    if not item:
        return Check("pass", "exact", f"evidence `{ident}` matches its content hash; no "
                                      "capture verdict was named, so none was checked",
                     evidence=(ident,))
    from .staging import StagingStore
    try:
        verdict = (StagingStore(vault).load(str(item)).get("intake") or {}).get("quality") or {}
    except (OSError, ValueError, TypeError) as exc:
        return Check("unavailable", "exact", f"staged item `{item}` could not be read",
                     detail=str(exc)[:200], evidence=(ident,))
    name = verdict.get("verdict", "")
    if name != "usable":
        return Check("fail", "exact", f"evidence `{ident}` matches its content hash, but staged "
                                      f"item `{item}`'s capture verdict is {name or 'missing'}",
                     detail=str(verdict.get("reason", ""))[:200], evidence=(ident,))
    return Check("pass", "exact", f"evidence `{ident}` matches its content hash and staged item "
                                  f"`{item}`'s capture verdict is usable", evidence=(ident,))


def coverage(vault: Vault, params: dict[str, Any], **_: Any) -> Check:
    """Coverage: the named parts of a source have the recorded examination status.
    The statement always names what was not examined."""
    from . import dik
    source = _param(params, "source")
    expected = str(params.get("status") or "observed")
    record = dik.load(vault, source)
    data = record.get("data") or []
    if not data:
        return Check("unavailable", "exact", f"source `{source}` has no coverage record")
    wanted = params.get("parts") or []
    if wanted:
        by_id = {str(d.get("id")): d for d in data} | {str(d.get("locator")): d for d in data}
        unknown = [p for p in wanted if str(p) not in by_id]
        if unknown:
            return Check("fail", "exact", f"source `{source}`'s coverage record has no part "
                                          f"{', '.join(map(str, unknown))}")
        data = [by_id[str(p)] for p in wanted]
    off = [d for d in data if d.get("status") != expected]
    not_examined = [str(d.get("locator") or d.get("id")) for d in record["data"]
                    if d.get("status") == "not examined"]
    named = f"; not examined: {', '.join(not_examined)}" if not_examined else \
        "; no part is recorded as not examined"
    scope = f"{len(data)} named part(s)" if wanted else f"all {len(data)} part(s)"
    if off:
        return Check("fail", "exact", f"source `{source}`: {len(off)} of {scope} do not have "
                                      f"recorded status {expected!r}{named}")
    return Check("pass", "exact", f"source `{source}`: {scope} have recorded status "
                                  f"{expected!r}{named}")


def _texts(value: Any, at: str = "") -> list[tuple[str, str]]:
    """Every string field of an evidence payload, by its path."""
    if isinstance(value, str):
        return [(at or "payload", value)]
    if isinstance(value, dict):
        return [t for k, v in value.items() for t in _texts(v, f"{at}.{k}" if at else str(k))]
    if isinstance(value, list):
        return [t for i, v in enumerate(value) for t in _texts(v, f"{at}[{i}]")]
    return []


def quote(vault: Vault, params: dict[str, Any], **_: Any) -> Check:
    """Quote: the quote is present in the named evidence, at an offset."""
    from . import clerk
    from .evidence import EvidenceStore
    ident = _param(params, "evidence")
    text = _param(params, "quote")
    if len(clerk.normal(text).strip(" .\"'")) < 8:
        return Check("inconclusive", "exact", "the quote is too short to locate (under 8 "
                                              "characters once normalised)")
    record = EvidenceStore(vault).get(ident)
    if record is None:
        return Check("fail", "exact", f"evidence `{ident}` is not in the evidence store")
    for where, body in _texts(record.payload):
        at = clerk.locate(text, body)
        if at != -1:
            return Check("pass", "exact", f"the quote is present in evidence `{ident}` at "
                                          f"offset {at} of field `{where}`", evidence=(ident,))
    return Check("fail", "exact", f"the quote is not present in evidence `{ident}`",
                 evidence=(ident,))


def arithmetic(vault: Vault, params: dict[str, Any], **_: Any) -> Check:
    """Arithmetic: each stated quantity in a note reproduces from its evidence."""
    from . import provenance
    rel = _param(params, "note").replace("\\", "/")
    path = (vault.root / rel).resolve()
    if vault.root.resolve() not in path.parents or not path.is_file():
        return Check("unavailable", "exact", f"note `{rel}` is not a file in the vault")
    rows = provenance.check(vault, path)
    if not rows:
        return Check("inconclusive", "exact", f"`{rel}` states no quantity the evidence models")
    evidence = tuple(sorted({r["evidence"] for r in rows if r.get("evidence")}))
    stated = ", ".join(f"{r['stated']} {r['quantity']}" for r in rows)
    off = [r for r in rows if r["outcome"] != "supported"]
    if off:
        listed = "; ".join(f"{r['stated']} {r['quantity']} is {r['outcome']}"
                           + (f" (recorded {r['recorded']})" if "recorded" in r else "")
                           for r in off)
        return Check("fail", "exact", f"{len(off)} of {len(rows)} stated quantities in `{rel}` "
                                      f"do not reproduce: {listed}", evidence=evidence)
    return Check("pass", "exact", f"the {len(rows)} stated quantities in `{rel}` reproduce from "
                                  f"evidence {', '.join(evidence)}: {stated}", evidence=evidence)


def claim_run(vault: Vault, params: dict[str, Any], **_: Any) -> Check:
    """Executable claim: the latest person-initiated run confirmed it. Bounded: one
    input, one commit, a sandbox without network. This check never runs anything."""
    from .claim_run import RunnableStore
    ident = _param(params, "run")
    item = RunnableStore(vault).get(ident)
    if item is None:
        return Check("unavailable", "bounded", f"no claim-run `{ident}` is stored")
    if not item["runs"]:
        return Check("unavailable", "bounded", f"claim-run `{ident}` has not been run; a "
                                               "person runs it (run_claim_input)")
    last = item["runs"][-1]
    where = (f"on commit {str(last.get('commit') or '?')[:12]} ({last.get('version', '')}), "
             "in the sandbox without network")
    evidence = (str(last["evidence"]),) if last.get("evidence") else ()
    if last["verdict"] == "confirmed":
        return Check("pass", "bounded", f"claim-run `{ident}` confirmed its declared input {where}",
                     detail=str(last.get("detail", ""))[:300], evidence=evidence)
    if last["verdict"] == "not_confirmed":
        return Check("fail", "bounded", f"claim-run `{ident}` did not confirm its declared input "
                                        f"{where}", detail=str(last.get("detail", ""))[:300],
                     evidence=evidence)
    return Check("unavailable", "bounded", f"claim-run `{ident}` could not run {where}",
                 detail=str(last.get("detail", ""))[:300], evidence=evidence)


def findable(vault: Vault, params: dict[str, Any], *,
             index_run: Callable | None = None, **_: Any) -> Check:
    """Findability: promotion's step 5 finds the note through each declared lookup."""
    name = _param(params, "note")
    if index_run is None:
        return Check("unavailable", "exact", "the index is not available to this check")
    from .promote import findability
    from .search import Engine
    missed, k = index_run(lambda engine: (findability(Engine(engine.index, engine.h), name),
                                          int(engine.h.get("findability_top_k", 5))))
    if missed:
        return Check("fail", "exact", f"note `{name}` is not findable: {'; '.join(missed)}")
    return Check("pass", "exact", f"note `{name}` is in the top {k} results for its title, its "
                                  "Bottom Line and its first concept, or that concept's page "
                                  "lists it")


def diff_clean(vault: Vault, params: dict[str, Any], *, session: Any = None, **_: Any) -> Check:
    """Staging integrity: each artifact of the contract is unchanged since it was
    recorded and lies within the contract's write targets."""
    from .coordination import fingerprint
    audit = session.audit
    contract = str(params.get("contract") or audit.current_contract)
    if contract not in audit.contracts:
        return Check("unavailable", "exact", f"contract {contract!r} is not admitted")
    targets = audit.contracts[contract]["write"]
    mine = {a: v for a, v in audit.artifacts.items() if v["contract"] == contract}
    if not mine:
        return Check("inconclusive", "exact", f"contract {contract} has recorded no artifact")
    problems = []
    for ident, artifact in mine.items():
        rel = artifact["path"]
        if not closure._covered(rel, targets):
            problems.append(f"{ident} ({rel}) is outside the write targets")
            continue
        path = vault.root / rel
        if not path.is_file():
            problems.append(f"{ident} ({rel}) is missing")
        elif fingerprint(path) != artifact["fingerprint"]:
            problems.append(f"{ident} ({rel}) changed after it was recorded")
    paths = ", ".join(v["path"] for v in mine.values())
    if problems:
        return Check("fail", "exact", f"contract {contract}'s artifacts are not as recorded: "
                                      f"{'; '.join(problems)}")
    return Check("pass", "exact", f"the {len(mine)} artifact(s) of contract {contract} are "
                                  f"unchanged since recorded and lie within its write targets: "
                                  f"{paths}")


CHECKS: dict[str, Callable[..., Check]] = {
    "evidence.integrity": integrity, "coverage.status": coverage, "quote.located": quote,
    "arithmetic.reproduces": arithmetic, "claim_run.passed": claim_run,
    "index.findable": findable, "target.diff_clean": diff_clean,
}
GRAINS = {"intake": "evidence.integrity", "coverage": "coverage.status",
          "quote": "quote.located", "arithmetic": "arithmetic.reproduces",
          "executable_claim": "claim_run.passed", "findability": "index.findable",
          "staging_integrity": "target.diff_clean"}
assert set(CHECKS) <= set(closure.VERIFIERS)


def run(verifier: str, vault: Vault, params: dict[str, Any], **context: Any) -> Check:
    """Run the Tier A check for one registered verifier id."""
    check = CHECKS.get(closure.base_id(verifier))
    if check is None:
        raise KeyError(verifier)
    result = check(vault, params or {}, **context)
    if result.strength != closure.VERIFIERS[closure.base_id(verifier)].max_strength:
        raise AssertionError(f"{verifier} reported {result.strength}")  # a table drift
    return result


# --------------------------------------------------------------- measurement

def grain_counts(audit: Any) -> dict[str, int]:
    """How the grains of one audited session stand now.

    A grain is one predicate of one requirement, or a requirement with no
    predicates (synthesis, interpretation). It is closed by Tier A when its
    latest result at the current epoch is a pass, at exact or bounded strength,
    from a verifier of an authoritative kind.
    """
    from . import audit_events
    out = {"grains": 0, "tier_a": 0, "human_accepted": 0, "other": 0}
    for rid, req in audit.requirements.items():
        status = audit.requirement_status(rid)
        for predicate in req["predicates"] or [None]:
            out["grains"] += 1
            latest = audit_events._latest_result(audit, rid, predicate) if predicate else None
            result = latest[1] if latest else None
            verifier = closure.VERIFIERS.get(closure.base_id(result["verifier"])) if result else None
            if result and result["outcome"] == "pass" and verifier and \
                    verifier.kind in closure.AUTHORITATIVE_KINDS and \
                    result["strength"] in ("exact", "bounded"):
                out["tier_a"] += 1
            elif status == "human_accepted":
                out["human_accepted"] += 1
            else:
                out["other"] += 1
    return out


def tier_a_share(vault: Vault) -> dict[str, Any]:
    """The share of grains closed by Tier A across a vault's audited sessions:
    measured from their logs, never asserted."""
    from .session import SessionStore
    store = SessionStore(vault)
    totals = {"sessions": 0, "grains": 0, "tier_a": 0, "human_accepted": 0, "other": 0}
    for path in sorted(store.folder.glob("*.jsonl")):
        session = store.load(path.stem)
        if session.purpose != "audited":
            continue
        totals["sessions"] += 1
        for key, value in grain_counts(session.audit).items():
            totals[key] += value
    totals["share"] = round(totals["tier_a"] / totals["grains"], 3) if totals["grains"] else None
    return totals
