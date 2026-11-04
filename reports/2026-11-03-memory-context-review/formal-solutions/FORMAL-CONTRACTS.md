# Proposed formal contracts and reference checks

3 November 2026. These are design formulations and proof sketches under stated assumptions, not a machine-checked proof of Librarian. They refine MC/EK proposals without adopting them.

## 1. Temporal visibility is distinct from current-use eligibility

For a record version v, let its asserted valid interval be `[vf, vt)` and recorded/system interval be `[sf, st)`. For known intervals:

`visible(v, domain_time, knowledge_time) = vf <= domain_time < vt AND sf <= knowledge_time < st`

Open-ended intervals may use an explicit infinity. Unknown intervals remain unknown. Multiple sources may provide conflicting visible assertions; visibility does not choose a winner or establish truth. Explicit exploratory branches are not merged into the operative requirements automatically.

Current use adds independent checks:

`eligible(v, task, principal) = visible_for_query(v) AND authorized(v, principal) AND applicable(v, task) AND qualified_support(v, task) AND not_withdrawn(v)`

Use three-valued results where inputs can be unknown. Unknown applicability blocks verified closure but can remain visibly tentative research material. Historical retrieval can show an inapplicable old version, with status and current access preserved. These are proposed domain policies built on the [bitemporal distinction](https://docs.xtdb.com/about/time-in-xtdb.html), not guarantees supplied by timestamps alone.

## 2. Support groups preserve alternatives

For declared sufficient support groups G(c) of claim c:

`supported(c) = OR over g in G(c) [AND over p in g qualified(p)]`

Example: `(A AND B) OR C`. Removing A does not remove C's independent justification. An unresolved premise yields unknown unless another fully qualified group suffices. A direct refutation/conflict is a separate status; positive support algebra alone must not erase it.

The formal inspiration is [provenance semirings](https://web.cs.ucdavis.edu/~green/papers/pods07.pdf) and [assumption-based maintenance](https://cdn.aaai.org/AAAI/1987/AAAI87-033.pdf). This limited application does not claim complete negation, probabilistic confidence, natural-language entailment or automated conflict resolution. Support combinations can grow exponentially; cap enumeration and report incomplete coverage rather than silently discard alternatives.

**Conditional argument:** if every group is genuinely sufficient, every admitted premise is qualified, and the OR/AND evaluator is correct, at least one valid support group is enough to preserve support. The difficult premise is establishing those conditions from real evidence; an LLM edge label does not prove them.

## 3. Worker acceptance must be one atomic decision

Proposed acceptance predicate:

`accept(result) only if input_revision = current_revision AND scope_current AND evidence_current AND required_checks_pass AND receipt_not_accepted`

The checks and accepted-receipt insertion must share a consistent transaction/version fence. If scope or evidence authority resides outside that transaction, include its version fence and define revocation handling; a stale cached check is insufficient. Use a unique logical result identity plus payload identity, so the same key with changed content becomes a conflict.

**Conditional argument:** with a serialized transition and unique accepted identity, a stale result cannot pass the revision predicate and two concurrent deliveries cannot create two accepted contributions. This proves only acceptance under the modeled state; it does not guarantee exactly-once remote effects. Future goal changes must also make earlier closure ineligible for the new revision while preserving its history.

A transaction spanning only SQLite cannot make arbitrary filesystem/remote changes atomic. Reconcile existing event/Writer ownership with a journaled operation and projection watermark. [SQLite isolation](https://www.sqlite.org/isolation.html) and [Temporal's retry discussion](https://docs.temporal.io/activity-definition) establish the relevant implementation boundaries.

## 4. Resource reservations

For a declared resource cap B:

`spent + sum(outstanding_reservations) <= B`

A reservation r is admitted only through an atomic check-and-increment. Settlement replaces r with actual consumption a, assuming `0 <= a <= r`. Unknown completion keeps its reservation; timeout alone must not release it. Additional retries require their own admitted allowance. Budget increases must be explicit events.

**Inductive argument:** the initial zero ledger satisfies the bound. Admission checks the resulting sum. Settlement does not increase the sum when a <= r. Hence all such transitions preserve the inequality. If provider charges can exceed the bound or are unknown, this is not an exact monetary guarantee: reserve a defensible upper bound, constrain generation, or disclose estimated/unknown cost and halt further discretionary spending.

## 5. Context capacity and semantic preservation

For the actual route serialization:

`count(system + schemas + essential_state + dialogue + evidence + continuation) + output_reserve <= context_capacity`

Enforce at dispatch, identifying counting method and uncertainty. A heuristic is not a strict bound unless its overestimate is justified. Context selection must preserve protocol structure. If essentials do not fit, split/park rather than truncate them.

**Limit:** a fixed finite representation has fewer possible values than arbitrary unbounded histories. Therefore a universally lossless compression into that representation cannot exist. The engineering contract must specify what is preserved exactly and how omitted evidence can be reopened. Even exact inclusion cannot prove that a model attends to a constraint; behavioral tests remain necessary.

## 6. Recipe qualification

Attach a receipt to a fingerprint of recipe, input versions, relevant environment/tool versions, operative requirements and verifier specification. A changed relevant component means the earlier receipt is historical unless an explicit equivalence check requalifies it. Specify which outcome equivalence is required; stochastic LLM text should not be assumed deterministic.

Use [CWL](https://www.commonwl.org/v1.2/Workflow.html) as an execution-contract reference and [Workflow Run RO-Crate](https://www.researchobject.org/workflow-run-crate/) for optional exchange of run evidence. A content hash identifies bytes under its collision assumptions; it does not prove authorship, permission or correctness.

## Executed finite reference checks

The standalone [Python explorer](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/formal-solutions/check_reference_models.py) uses only the standard library. Full output is in [reference-model-results.json](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/formal-solutions/reference-model-results.json).

| Check | Result | What was modeled |
|---|---|---|
| Revision and duplicate guards | 97 reachable states, 148 transitions; invariant holds | Two workers, two revisions, up to two deliveries each; atomic acceptance |
| Remove revision guard | Counterexample found | Dispatch at revision 0 → revise to 1 → accept stale result |
| Remove duplicate guard | Counterexample found | Dispatch → accept → accept duplicate |
| Atomic reservations | Five reachable states, six transitions; invariant holds | Two possible workers, two units each, cap three; one attempt each |
| Separate precheck/write | Counterexample found | Both see free capacity, both reserve; total four exceeds cap three |
| Alternative support | Eight Boolean valuations and two unknown cases checked | `(A AND B) OR C`; flattening dependencies to AND loses valid support |

This exhaustive exploration is limited to those finite abstractions. It does not include actual persistence, crash recovery, real access checks, source verification, delivery liveness, arbitrary worker counts or production Python code. Mutation controls show the checker catches the intended bad designs; they do not validate every possible defect.

## Next verification step

Specify the combined event/revision/reservation machine in TLA+, with TLC exploring bounded concurrency and restart states. State safety separately from liveness: eventual completion requires availability/fairness assumptions and cannot be inferred from absence of stale acceptance. Connect implementation event traces and Hypothesis stateful tests to the same predicates. A TLC result covers the modeled finite configuration; an unbounded theorem requires a separate proof and implementation refinement still needs evidence.

Useful tools: [TLA+ CLI tools](https://github.com/tlaplus/tlaplus) and [Hypothesis stateful testing](https://hypothesis.readthedocs.io/en/latest/stateful.html). Neither was installed or run in this pass; only the supplied finite Python reference models were executed.
