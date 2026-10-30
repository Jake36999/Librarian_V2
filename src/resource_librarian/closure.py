"""Closure validity and per-call authorization for audited sessions (HARNESS-05).

Two tables decide what an audited contract may claim and do.

**Closure validity.** Each verifier has a kind and the strongest result it can
give. A requirement may close authoritatively only through a deterministic,
test, solver or evidence verifier at exact or bounded strength. An LLM review
can at most support partial closure, and a person's acceptance is recorded as
acceptance, not as verification. A contract whose verifier plan could not
close its authoritative requirements is refused at admission, before anything
runs.

**Per-call authorization.** While an audited contract executes, every tool
call is checked against it:
- its operation class must be one the contract allows;
- its resolved write targets must be among the contract's targets;
- the paths it reads must be among the contract's targets;
- its arguments must be within the size limit;
- its idempotency key (the contract, tool and arguments) must not repeat a
  write that already succeeded.

Calls that each pass can still combine into something the contract does not
allow. After untrusted input enters a contract, only reads and staging remain:
untrusted text can feed a draft for a person, never a canonical write,
promotion, execution, route change or publication.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .rules import Refusal


@dataclass(frozen=True)
class Verifier:
    kind: str           # deterministic | test | solver | evidence | llm
    max_strength: str   # the strongest result it can honestly give
    predicate: str      # exactly what a pass means, never more


VERIFIERS: dict[str, Verifier] = {
    "evidence.integrity": Verifier("evidence", "exact",
                                   "the evidence object passes its integrity and ingestion checks"),
    "coverage.status": Verifier("deterministic", "exact",
                                "these named sources or parts have this recorded examination "
                                "status"),
    "quote.located": Verifier("deterministic", "exact",
                              "the quote is present in the named evidence at the stated offset"),
    "arithmetic.reproduces": Verifier("deterministic", "exact",
                                      "the calculation reproduces from its operands and "
                                      "assumptions"),
    "claim_run.passed": Verifier("test", "bounded",
                                 "the declared claim-run passed in the recorded environment and "
                                 "scope"),
    "index.findable": Verifier("deterministic", "exact",
                               "the artifact resolves through the declared lookup"),
    "target.diff_clean": Verifier("deterministic", "exact",
                                  "only the contract's write targets changed, as declared"),
    # HARNESS-07: mechanical closure for bounded operations
    "schema.valid": Verifier("deterministic", "exact",
                             "the note parses and meets the vault's content model for its shape"),
    "citation.resolves": Verifier("deterministic", "exact",
                                  "every evidence id and wiki link the note cites resolves"),
    "boundary.staged": Verifier("deterministic", "exact",
                                "the contract changed the vault only through staging"),
    "review.llm": Verifier("llm", "advisory",
                           "a model's read-only assessment; advisory, never verification"),
}

AUTHORITATIVE_KINDS = frozenset({"deterministic", "test", "solver", "evidence"})
_STRENGTH_ORDER = {"advisory": 0, "bounded": 1, "exact": 2}

# The closure-validity table: what each closure class may be closed by.
CLOSURE_TABLE = {
    "authoritative": "a deterministic, test, solver or evidence verifier at exact or bounded "
                     "strength for every predicate",
    "partial": "any registered verifier; an LLM review at most supports partial closure",
    "human_judgment": "a person's acceptance of the exact artifact; verifiers only inform it",
}

OPERATIONS = ("read", "untrusted", "stage", "write", "promote", "execute", "route", "publish")
DEFAULT_OPERATIONS = ("read", "stage", "write")
# What untrusted input may still lead to within the same contract.
AFTER_UNTRUSTED = frozenset({"read", "untrusted", "stage"})

MAX_CALL_BYTES = 256_000
_PATH_ARGS = ("path", "note", "source_path", "file", "target")
_EXECUTE = frozenset({"sandbox_run", "sandbox_run_file", "run_claim_input", "run_pipeline",
                      "run_workflow", "run_resume", "engagement_start", "macro_run",
                      "capability_install"})
_PROMOTE = frozenset({"promote_offering", "staging_decide", "process_approved",
                      "model_catalog_adopt", "lens_pack_accept", "accept_workflow"})
_ROUTE = frozenset({"task_route"})
_PUBLISH = frozenset({"vault_push"})


def _refuse_plan(message: str) -> Refusal:
    return Refusal("AUDIT_EVENT_INVALID", message)


def base_id(verifier: str) -> str:
    """`quote.located@2` names the registered verifier `quote.located`."""
    return str(verifier).split("@", 1)[0]


def check_plan(requirements: dict[str, dict[str, Any]], addressed: list[str],
               plan: Any) -> dict[str, str]:
    """Validate a contract's verifier plan before admission; return it normalised.

    `plan` maps `"requirement: predicate"` to a verifier id. Every predicate of
    an authoritative requirement must have a verifier that can close it.
    """
    if plan is None:
        plan = {}
    if not isinstance(plan, dict):
        raise _refuse_plan("contract verifiers must map 'requirement: predicate' to a verifier")
    valid = [f"{rid}: {p}" for rid in addressed for p in requirements.get(rid, {}).get(
        "predicates", [])]
    normalised: dict[str, str] = {}
    for key, verifier in plan.items():
        key = str(key)
        if key not in valid:
            # A bare predicate is accepted when exactly one addressed
            # requirement has it: the mapping is then not a guess (G5 pilot:
            # a real model keyed its plan by predicate text alone).
            matches = [k for k in valid if k.split(": ", 1)[1] == key]
            if len(matches) != 1:
                raise _refuse_plan(
                    f"verifier plan names {key!r}, not a predicate of a requirement this "
                    f"contract addresses. Key each verifier by 'requirement: predicate', "
                    f"exactly; valid keys here: {valid}")
            key = matches[0]
        if base_id(verifier) not in VERIFIERS:
            raise _refuse_plan(f"unknown verifier {verifier!r}; registered: {sorted(VERIFIERS)}")
        normalised[key] = base_id(verifier)
    for rid in addressed:
        req = requirements[rid]
        if req["closure"] != "authoritative":
            continue
        for predicate in req["predicates"]:
            key = f"{rid}: {predicate}"
            if key not in normalised:
                raise _refuse_plan(f"authoritative requirement {rid} needs a verifier for "
                                   f"{predicate!r} before the contract runs (plan key "
                                   f"{key!r})")
            v = VERIFIERS[normalised[key]]
            if v.kind not in AUTHORITATIVE_KINDS or v.max_strength == "advisory":
                raise _refuse_plan(
                    f"{normalised[key]} ({v.kind}, at most {v.max_strength}) cannot close "
                    f"authoritative requirement {rid}: it would cap at partial. "
                    f"Authoritative closure needs {CLOSURE_TABLE['authoritative']}")
    return normalised


def check_result(verifier: str, strength: str, planned: str | None) -> None:
    """A result must come from a registered verifier, the planned one, within its strength."""
    ident = base_id(verifier)
    if ident not in VERIFIERS:
        raise _refuse_plan(f"unknown verifier {verifier!r}; registered: {sorted(VERIFIERS)}")
    if planned and ident != planned:
        raise _refuse_plan(f"the contract planned {planned} for this predicate, not {ident}")
    limit = VERIFIERS[ident].max_strength
    if _STRENGTH_ORDER[strength] > _STRENGTH_ORDER[limit]:
        raise _refuse_plan(f"{ident} can give at most {limit} results, not {strength}")


# ------------------------------------------------------------ per-call authorization

def operation_class(spec: Any, intent: Any, vault: Any) -> str:
    """The table: what kind of authority a call exercises."""
    name = spec.name
    if name in _PUBLISH:
        return "publish"
    if name in _ROUTE:
        return "route"
    if name in _EXECUTE:
        return "execute"
    if name in _PROMOTE:
        return "promote"
    if spec.effect == "read":
        return "untrusted" if spec.open_world else "read"
    if intent is not None and intent.targets:
        staging = vault.work("staging").relative_to(vault.root).as_posix().rstrip("/") + "/"
        if all(str(t).replace("\\", "/").startswith(staging) for t in intent.targets):
            return "stage"
    return "write"


def _covered(path: str, targets: list[str]) -> bool:
    path = path.replace("\\", "/")
    return any(path == t or (t.endswith("/") and path.startswith(t)) for t in targets)


def idempotency_key(contract_id: str, revision: int, tool: str, kwargs: dict[str, Any]) -> str:
    body = json.dumps({"contract": contract_id, "revision": revision, "tool": tool,
                       "args": kwargs}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:24]


def authorize(session: Any, spec: Any, kwargs: dict[str, Any], intent: Any,
              vault: Any, *, raw: dict[str, Any] | None = None,
              adjusted: list[str] | None = None) -> dict[str, Any] | None:
    """Check one call against the executing contract; None outside contract execution.

    `raw` is the call's arguments as given and `adjusted` what coercion changed:
    the size is measured on what was proposed, not on what coercion cut it to.
    Returns the call's descriptor (recorded with the call) or raises Refusal.
    """
    if session.purpose != "audited" or session.phase != "execute":
        return None
    contract_id = session.audit.current_contract
    if not contract_id:
        raise Refusal("CONTRACT_SCOPE", "no admitted contract is executing; preflight first")
    contract = session.audit.contracts[contract_id]
    allowed = contract.get("operations") or list(DEFAULT_OPERATIONS)
    klass = operation_class(spec, intent, vault)
    size = max(len(json.dumps(v, ensure_ascii=False, default=str).encode("utf-8"))
               for v in (kwargs, raw or {}))
    if size > MAX_CALL_BYTES:
        raise Refusal("CONTRACT_SCOPE", f"{spec.name}'s arguments are {size} bytes, over the "
                                        f"{MAX_CALL_BYTES}-byte limit for one call")
    cut = [a for a in adjusted or [] if "truncated" in a]
    if cut:
        # Coercion would have cut the arguments to fit: the call that ran would
        # not be the one proposed. A contract executes the proposal or nothing.
        raise Refusal("CONTRACT_SCOPE", f"{spec.name}'s arguments would be cut to fit "
                                        f"({'; '.join(cut)[:200]}); split the content instead")
    if klass not in allowed:
        raise Refusal("CONTRACT_SCOPE", f"{spec.name} is a {klass} operation; contract "
                                        f"{contract_id} allows only {sorted(allowed)}")
    if spec.open_world and "untrusted" not in allowed:
        # An open-world write (an ingest, a fetch that stores) brings outside text in too.
        raise Refusal("CONTRACT_SCOPE", f"{spec.name} brings in untrusted input; contract "
                                        f"{contract_id} does not allow 'untrusted'")
    targets = contract["write"]
    if klass not in ("read", "untrusted"):
        if intent is None or not intent.targets:
            raise Refusal("CONTRACT_SCOPE", f"{spec.name} declares no write targets, so it "
                                            "cannot be checked against the contract before it "
                                            "runs")
        outside = [t for t in intent.targets if not _covered(str(t), targets)]
        if outside:
            raise Refusal("CONTRACT_SCOPE", f"{spec.name} would write {', '.join(outside)}, "
                                            f"outside contract {contract_id}'s targets")
    else:
        readable = contract["read"] + targets
        for key in _PATH_ARGS:
            value = kwargs.get(key)
            if isinstance(value, str) and value and not _covered(value, readable):
                raise Refusal("CONTRACT_SCOPE", f"{spec.name} would read {value}, outside "
                                                f"contract {contract_id}'s targets")
    history = session.contract_calls.get(contract_id, [])
    if any(c["untrusted"] for c in history) and klass not in AFTER_UNTRUSTED:
        raise Refusal("COMPOSITION_REFUSED",
                      f"{spec.name} ({klass}) after untrusted input in contract {contract_id}: "
                      "untrusted text may only feed reads and staged drafts for the person")
    key = idempotency_key(contract_id, contract["revision"], spec.name, kwargs)
    if klass not in ("read", "untrusted") and any(c["key"] == key for c in history):
        raise Refusal("CONTRACT_SCOPE", f"this exact {spec.name} already succeeded under "
                                        f"contract {contract_id}; it is not repeated")
    return {"contract": contract_id, "revision": contract["revision"], "class": klass,
            "untrusted": klass == "untrusted" or bool(spec.open_world), "key": key,
            "bytes": size,
            # HARNESS-07: what the protected-target audit accounts each change to.
            **({"targets": [str(t).replace("\\", "/") for t in intent.targets]}
               if klass not in ("read", "untrusted") and intent is not None else {})}
