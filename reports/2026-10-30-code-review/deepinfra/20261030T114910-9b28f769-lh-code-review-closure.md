# Closure-enforcement and replay audit — 4 findings

## 1. `_verifier_result` accepts a result whose `verifier` is not the planned one when the plan has no entry for that predicate

**Where:** `audit_events._verifier_result` calls `closure.check_result(verifier, strength, state.contracts[contract]["verifiers"].get(f"{requirement}: {predicate}"))`.

**Trigger:** a contract admitted for a *non-authoritative* requirement (or a predicate the plan omitted) has no key for `"R1: p"`. `check_result` receives `planned=None`, and its guard is `if planned and ident != planned:` — so any registered verifier is accepted. A `review.llm` result at `advisory` strength can therefore be recorded against a predicate the person never planned a check for, and `_latest_result` will surface it as that predicate's current outcome.

**Why existing checks don't stop it:** `check_plan` only enforces a plan entry for `authoritative` requirements; `check_result`'s `planned` argument is falsy for the rest. `_unplanned` in `audit_events` is only consulted by `_predicate_outcome`/`_core_status`, not by `_verifier_result`. `grain_counts` then counts it as `tier_a` only if the verifier kind is authoritative — but `_core_status` for a `partial` requirement returns `"partial"` on *any* pass, including an advisory LLM pass.

**Fix direction:** in `_verifier_result`, refuse when `planned is None` and the requirement's closure is not `human_judgment`; or make `check_result` require `planned` to be non-None for any result that will be cited by a reduction.

## 2. `_latest_result` is keyed on `(requirement, predicate)` only — a result from an older contract at the same epoch shadows a newer contract's result

**Where:** `audit_events._latest_result` iterates `state.results` and keeps the last match on `(requirement, predicate)` at `state.epoch`. `_reduction` (status `verified`) and `_core_status` both use it.

**Trigger:** a contract is revised (`_contract` bumps `state.epoch` on revision > 1, so this specific path is safe), **but** `admit_contract` in `tools/audited.py` re-admits with `revision = existing["revision"] + 1` and `epoch = session.audit.epoch` — the *current* epoch, not a bumped one. `_contract` then bumps `state.epoch` only `if revision > 1`, which it is, so the epoch does advance. However, `_verifier_result` records `"epoch": _epoch(state, event)` — the *new* epoch — and `_latest_result` filters on `result["epoch"] == state.epoch`. So a result recorded under contract revision 1 at epoch N is invisible after revision 2 bumps to N+1. That is correct for staleness, but the reverse case is the bug: **two contracts admitted at the same epoch** (e.g. `admit_contract` for a second contract without revising the first — `_contract` only bumps on `revision > 1`, and a fresh contract id has `revision == 1`) share an epoch. A result recorded under contract A for `R1: p` is then the "latest" for contract B's reduction of `R1`, even though B planned a different verifier and B's `check_result` was never consulted for that result.

**Why existing checks don't stop it:** `_reduction`'s `verified` branch checks `state.results[r]["contract"]` only for the integrity loop, not for predicate provenance. `_core_status` in `tools/audited.py` builds `latest` from `_latest_result` without filtering by `contract`. `check_result` is only called at *record* time, not at *reduce* time.

**Fix direction:** `_latest_result` should take a `contract` argument (or `_reduction` should filter `state.results` by `result["contract"] == contract` before picking the latest per predicate).

## 3. `_reduction` `verified` does not re-check that the cited result's verifier is still the planned one for the *current* contract revision

**Where:** `audit_events._reduction`, `status == "verified"` branch.

**Trigger:** a contract is revised (`_contract` bumps epoch, so old results go stale — good). But `admit_contract` in `tools/audited.py` passes `"epoch": session.audit.epoch` and `_contract` bumps only on `revision > 1`. A revision-2 contract that *changes the plan* (e.g. drops `quote.located` for `R1: p` and plans `review.llm`) is admitted at the bumped epoch. A `verifier_result` recorded *before* the revision at the old epoch is stale (filtered out). But a `verifier_result` recorded *after* the revision, at the new epoch, with `verifier="quote.located"` — the old plan — is accepted by `_verifier_result` because `check_result` compares against `state.contracts[contract]["verifiers"]`, which is the *new* plan. So `check_result` would refuse it. **However**, `_reduction`'s `verified` branch does not re-verify that the cited result's `verifier` matches `state.contracts[contract]["verifiers"][f"{requirement}: {predicate}"]`. If a result was recorded under a *different* contract (finding 2) or before a plan change that did not bump epoch (a fresh contract id at revision 1, same epoch), `_reduction` will accept it.

**Why existing checks don't stop it:** `check_result` runs only at record time; `_reduction` trusts `state.results[ident]` as-is. The `verified` branch checks `outcome`, `strength`, and `ident in cited`, but not `result["verifier"] == planned`.

**Fix direction:** in `_reduction`'s `verified` loop, add `if result["verifier"] != state.contracts[result["contract"]]["verifiers"].get(f"{requirement}: {predicate}"): raise _refuse(...)`.

## 4. `authorize` read-scope check only inspects `_PATH_ARGS` string kwargs — a read tool whose path arrives under another key, or as a list, bypasses the contract's `read` targets

**Where:** `closure.authorize`, the `else` branch (`klass in ("read", "untrusted")`): `for key in _PATH_ARGS: value = kwargs.get(key); if isinstance(value, str) ...`.

**Trigger:** `_PATH_ARGS = ("path", "note", "source_path", "file", "target")`. A read tool that takes `evidence_id`, `ids`, `paths`, `folder`, or a list of paths is not checked. `read_evidence` in `tools/audited.py` takes `evidence_id` — not in `_PATH_ARGS` — so under an audited contract with `read: []` and `operations: ["read"]`, `read_evidence` is authorized with no scope check at all. The contract's `read` targets are never consulted for it.

**Why existing checks don't stop it:** `operation_class` returns `"untrusted"` for `read_evidence` (it is `open_world=True`), and the `else` branch's `_PATH_ARGS` loop is the only read-scope enforcement. `watched_paths()` in `AuditState` includes `contract["read"]`, so an external edit to a read target stales the epoch — but the *call* itself is not bounded to those targets. The docstring of `closure.py` claims "the paths it reads must be among the contract's targets"; the implementation only enforces that for five literal kwarg names.

**Fix direction:** either extend `_PATH_ARGS` and handle list values, or require read tools to declare their path arguments in the spec and check those; at minimum, `read_evidence` should be refused when `evidence_id` is not among the contract's read targets (or the contract should be required to list evidence ids it may read).

---

**Assumptions:** `session.contract_calls` entries carry `class`, `untrusted`, `key`, `tool` as written by `authorize`; `SessionStore.append_audit` replays through `audit_events.replay` (so `state.invalid` short-circuits later events). **Risks:** findings 1–3 interact — a single fix to `_latest_result` (contract-scoped) plus a `planned`-required check in `_verifier_result` closes most of the surface; finding 4 is independent.

**Deterministic tests for the integrator:**
1. Admit a `partial` contract with no plan entry for `R1: p`; record `verifier_result` with `verifier="review.llm"`, `strength="advisory"`, `outcome="pass"`; assert `_reduction` for `R1` does not return `partial` (or that the result is refused).
2. Admit contract A (rev 1) and contract B (rev 1) at the same epoch; record a pass under A for `R1: p`; reduce B; assert B's `verified` is refused or B's `_latest_result` is empty.
3. Admit contract rev 1 with plan `{R1: p → quote.located}`; record a pass; revise to rev 2 with plan `{R1: p → review.llm}`; record a pass under rev 2 with `verifier="quote.located"`; assert `_verifier_result` refuses (or `_reduction` refuses).
4. Under an audited contract with `read: []`, `operations: ["read","untrusted"]`, call `read_evidence(evidence_id="E1")`; assert `authorize` refuses with `CONTRACT_SCOPE` (currently it does not).