## 9. Wave 4 — session-based long-horizon co-work

### 9.1 Scope reduction

AuditedEngagement begins as **externalized state for partial research work**,
not as a new autonomous system that tries to certify research synthesis.

The first implementation reuses:

- session.py append-only chained events, replay, phases, budgets, and questions;
- VaultWriter via CORE-03 for durable ordering;
- staging.py as the promotion airlock;
- claim_run, quality, provenance arithmetic checks, schema checks, and existing
  L0 checks through a small verifier interface; and
- existing RolePolicy and ToolBundle machinery.

It does not initially implement a second event store, nine new record classes,
a generic behavior-tree framework, ranked tool selection, trust-zone
propagation, graph context, automatic promotion, or default LLM auditing.

### 9.2 Required role mapping

| Harness function | Existing product role | Authority |
| --- | --- | --- |
| Manager | Lead | Inference-only, no environment or mutation tools. |
| Executor for tool/mutation contracts | Lead | Existing bounded tool authority, narrowed by contract. |
| Executor for drafting-only contracts | Scribe | Draft/staging authority only; no promotion. |
| Tier B Auditor | Clerk | Consult/read-only authority. |
| Supporting research | research_helper | Read-only unless a stricter profile explicitly permits otherwise. |

Clerk MUST NOT become a mutation-capable Executor. The route map is a
projection of the canonical RoleRouteBinding, not a new family of roles.

### 9.3 Work packages

| ID | Size | Scope and deliverable | Dependencies | Candidate lane | Done only when |
| --- | --- | --- | --- | --- | --- |
| HARNESS-01 | Small | Amend the harness spec and related architecture docs to state Session reuse, the role mapping above, the writer-append requirement, and the intentionally deferred features. | BASE-03, CORE-03, ROUTE-04 | Core and state | No document proposes a parallel log/reducer; implementation status and terminology agree. |
| HARNESS-02 | Small | Define the minimal audited session event vocabulary: requirement, artifact, fact, question, contract, verifier result, reduction, and `external_edit`. The last is appended when a note the session read or targets changes outside the Core, fed from `VaultWatcher` and the CORE-05 fingerprints; it is what epoch invalidation will consume. Define outcome mappings among invocation, execution, audit, and session states. | HARNESS-01, BASE-04, CORE-05 | Core and state | A schema/replay fixture rejects invalid transitions and maps each result to one visible session outcome. An external edit to a session's target appears in its log. |
| HARNESS-03 | Medium | Add audited as a Session purpose with phases manage → preflight → execute → audit → reduce. Reuse phase budgets, question blocking, event replay, and CORE-03 append ownership. | HARNESS-02, ROUTE-04 | Core and state | A fixture resumes a paused audited session with the same state hash and never writes around VaultWriter. |
| HARNESS-04 | Medium | Implement a bounded Manager projection and capability manifest. It supplies active constraints, open/partial/stale requirements, latest verifier result per requirement, last N events, aggregate counts, eligible bundles, verifier IDs, approved roots, route availability, and remaining budget. | HARNESS-03, ROUTE-04 | Core and state | Projection size is token-bounded, older reports are references only, and a 50-round fixture remains bounded and deterministic. |
| HARNESS-05 | Small | Define closure validity and per-call authorization tables. Authoritative closure requires deterministic, test/solver, or evidence verification at exact/bounded strength; LLM-only assessment caps at partial. Add composition closure: calls that are each permitted within one contract must not combine into a prohibited outcome (for example, reading untrusted content and then writing outside the contract's targets). | HARNESS-02 | Core and state | Invalid verifier/strength/closure combinations are rejected before execution; each tool call validates path, operation class, size, and idempotency key; a prohibited two-call composition is refused. |
| HARNESS-06 | Medium | Ship externalized-state research rounds with **closure per research grain**. Grains with an existing deterministic verifier close authoritatively through Tier A, each with exact predicate wording ("the quote is present in evidence `<id>` at offset N", never "the claim is true"): intake (`EvidenceStore.verify`, a `quality.py` verdict); coverage (`dik.py` status, with "not examined" explicit); quote (`clerk.quoted`/`locate`); arithmetic (`provenance.py`); executable claim (`claim_run.py`); findability (`promote.py` step 5). Synthesis and interpretation stay `human_judgment` through staging. Include Tier A integrity over staging writes, a no-suitable-tool outcome, and post-filter bundle-count telemetry. Checkpoints let the person initiate (propose a constraint, request evidence) as well as approve. | HARNESS-03 through HARNESS-05 | Core and state | Research rounds resume, close verified grains with their exact predicate text, stage synthesis for human judgment, and never declare semantic completion. A test shows every checkpoint control changes state. The share of grains closed by Tier A is measured on real sessions, not asserted. |
| HARNESS-07 | Medium | Add mechanical authoritative closure for bounded operations: protected-target snapshot/diff, schema/citation/index/claim-run verifier registry, and interface/boundary verification such as submission through staging. | HARNESS-06, INDEX-05 | Core and state | A mechanical fixture completes only after an exact/bounded verifier and clean protected-target audit; out-of-scope writes cannot complete. |
| HARNESS-08 | Experimental medium | Evaluate Tier B Clerk audit against state-only and Tier-A variants on predeclared Librarian fixtures. | HARNESS-06, HARNESS-07, ADAPT-07 | Cross-cutting review | A written go/no-go result measures false-completion interception, rework, user correction, cost, latency, and route-specific failure. Tier B is non-default unless it clears a predeclared benefit/cost margin. |
| HARNESS-09 | Medium, deferred | Add targeted provenance invalidation and trust-zone broker enforcement after HARNESS-06/07 are stable. | HARNESS-08, ADAPT-09 | Core and state | Failed audit/user rejection invalidates only typed dependents; untrusted input cannot gain mutation, execution, credential, route, or promotion authority in the same episode. |

The Manager must receive a capability manifest before execution, not learn the
available tools by failed proposals. The Executor tool surface remains a static
policy-filtered bundle in the first slice. A five-action-tool cap may later be
evaluated, but it is not a universal law and does not replace a no-suitable-tool
outcome.

Mixed frontier-manager/cheap-executor routing is an evaluation hypothesis.
The cited long-horizon work used the same backbone for all three roles, and its
token result shows a weaker backbone can require more recovery work.

