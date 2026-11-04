# Candidate addendum: memory, context and worker continuity

**Status: proposed, 3 November 2026; not adopted.** Suggested additions to [the long-horizon harness design](/D:/Librarian_V2/docs/long-horizon-harness-design.md). The [research pass](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/REQUIREMENTS-RESEARCH.md) supplies findings, limitations, source IDs and the crosswalk to existing clauses.

These clauses specify observable outcomes. They do not prescribe a graph database, new model role, separate memory authority, numerical context threshold, or particular prompt. Existing Core/Writer ownership, Session replay, role policy and promotion boundaries remain controlling. Requirements marked conditional apply only if the named feature is adopted. No clause changes implementation status or release gates.

## Proposed requirements

### MC-01 — Bound the final dispatched context

**Clarifies §6.** The complete input assembled for each model call must fit the applicable route's supported input allowance after accounting for output reserve and protocol overhead. Accounting must include system instructions, tool schemas, required Session state, dialogue, retrieved content and continuation data. Token counts must identify their method and uncertainty. Projection-size checks alone do not satisfy this requirement.

If essentials cannot fit, the system must split or park the work with an explicit outcome. It must preserve valid tool-call/result and provider-continuation structure while reducing optional history.

**Acceptance:** inspect actual serialized calls after 50/200 rounds, with Unicode, code, schemas and continuation blocks. Every call respects its configured bound, or dispatch stops visibly. Validate useful context separately from nominal capacity.

**Basis:** existing §6; S8 and S9 motivate workload-specific evaluation, not a universal size limit.

### MC-02 — Preserve decision-critical meaning through compaction

**Clarifies §§4,6.** Every derived working context must retain the operative goal, required constraints and exceptions, applicable user corrections, unresolved decisions, uncertain operations, and evidence identities relevant to its admitted work. Summarization must not create authority or silently strengthen certainty. The context record must identify its source event boundary, current revision and omitted categories. Optional content may be reduced; missing essentials require split/park.

**Acceptance:** repeated compaction/resume preserves exact typed constraints and known exceptions; model summaries cannot replace them. Omitted process detail can be reopened from evidence. Tests distinguish inclusion from successful use.

**Basis:** existing §§4,6; S1 and S9; selective process preservation is also motivated by S5.

### MC-03 — Make promised evidence continuity rehydratable

**Clarifies §4 and §6 references.** Evidence required for a resumable decision must have an identity resolvable beyond the originating worker/Loop, with source version, locator and representation. Reopening must enforce current access and report exact-version availability. Missing, changed, expired and forbidden sources are distinct from verified continuity. Ephemeral result handles must disclose their lifetime and must not be presented as durable evidence.

**Acceptance:** after worker exit and Core restart, the parent reopens the recorded evidence version or receives a specific unavailable/stale outcome; it cannot silently substitute new content under the old verification.

**Basis:** existing provenance/resume contracts; S1/S10 provide relevant episode/source-reference patterns.

### MC-04 — Reassess historical procedure applicability

**New, conditional on reusable experience/procedure memory.** A remembered procedure must expose known assumptions, applicable scope/version, observed result, limitations and evidence. Before it guides a consequential action, available current facts must be checked against those conditions. Unsupported applicability remains tentative and cannot substitute for required current checks. A failure record must state what failed under which conditions; it must not permanently ban an approach after those conditions change.

**Acceptance:** an old workaround and an obsolete failed attempt are each rejected as current guidance when their preconditions no longer hold. Unknown applicability is visible.

**Basis:** design inference from S5; no trained applicability oracle is required.

### MC-05 — Give corrections and temporal validity explicit semantics

**New, conditional on cross-session fact/decision/preference reuse.** Reusable records must distinguish recording time from stated applicability time and identify explicit correction/supersession relationships. Current-state retrieval must account for authorized corrections, including affected derived recommendations. Historical questions may access superseded material with its status intact. Unknown times remain unknown. Recency or similarity alone must not decide between conflicting independent sources or enlarge user authority.

**Acceptance:** current and “as of” queries give appropriately different results; a premise correction affects dependent answers; unresolved source disagreements stay visible.

**Basis:** S2/S3/S10; benchmark-specific later-wins rules are not adopted as a general policy.

### MC-06 — Preserve scope and current access across memory use

**Extends §§3,7.** Every memory retrieval and worker handoff must operate within explicit library/project/session/role scope. Private worker context is not implicitly shared. Current authorization must be checked on retrieval, rehydration and parent merge; cached eligibility is insufficient. Broader sharing requires the applicable existing authorized workflow. Relevant-but-forbidden content must not leak through excerpts, summaries, counts or graph neighbors.

**Acceptance:** identical vocabulary in two projects does not cause cross-scope leakage. Revoking access between retrieval and merge prevents dependent use while reporting the resulting evidence gap.

**Basis:** current product authority model; S7 motivates checking persistent and transformed inputs. Specific scope policy is a product decision.

### MC-07 — Retain origin and trust through transformations

**Clarifies §§4,7.** Retrieval, worker paraphrase, consolidation, indexing and graph linking must retain enough lineage to distinguish person-authorized constraints, source statements, observations, inference and model-produced text. Storage or repetition must not raise trust. When derivation is lossy or origin cannot be resolved, the result remains advisory. Duplicate derivations from one source must not count as independent corroboration.

**Acceptance:** hostile source instructions remain data after a worker paraphrases and stores them; several summaries of one source cannot establish independent support or alter permissions.

**Basis:** existing untrusted-content rule; S7 supplies a persistent-memory threat case. This is lineage bookkeeping, not a claim of comprehensive taint enforcement.

### MC-08 — Make worker handoffs sufficient for parent decisions

**New precision for §§3,6.** Each worker request must identify its parent work, relevant requirements/revisions, input snapshot, bounded question, applicable constraints, permitted source scope, budget and expected result obligations. Each result must identify findings with evidence references, relevant caveats, unresolved work, conflicts, stop status and usage availability. Size limits must preserve these fields or return an explicit partial/overflow result with a way to obtain remaining permitted detail.

**Acceptance:** a caveat at the end of a large response is retained or explicitly marked omitted; a worker can report a missing prerequisite without inventing an answer. The parent can inspect what information was actually handed off.

**Basis:** S6/S9 motivate omissions and isolated context; the exact packet schema remains open.

### MC-09 — Merge worker results against current parent state

**Clarifies §§4,5.** Worker results are proposals associated with an input snapshot and stable child identity. Before acceptance, the Core must check current requirement/contract revisions, relevant evidence freshness and scope. Duplicate delivery must not duplicate accepted effects or budget reconciliation. Stale, conflicting, partial and failed results remain distinguishable. Useful stale material may be reconsidered explicitly without inheriting its prior closure status.

**Acceptance:** two concurrent results arriving after a parent correction cannot close the old requirement; replaying one response accepts it once. Restart between receipt and merge preserves unresolved status.

**Basis:** existing epoch/reduction/idempotency contracts; S6 motivates coordination failure fixtures. This does not promise exactly-once external execution.

### MC-10 — Reserve shared budgets before parallel dispatch

**Clarifies §6.** Concurrent workers must draw from the same controlling run/pool allowance through serialized or atomic reservations. Acquisition, consolidation, retrieval-model, worker, retry, repair and review calls must all be accounted for. Parent/child attribution must avoid double counting. Unknown usage and uncertain completion must retain conservative reservations until reconciled under the existing recovery policy.

**Acceptance:** N simultaneous workers cannot each reserve the parent's full remaining allowance; interrupted calls remain attributable; parent totals equal child and direct charges without duplicate charges.

**Basis:** existing cost/recovery commitments. S4 motivates end-to-end latency/cost measurement; no extra billing subsystem is prescribed.

### MC-11 — Disclose retrieval coverage and unanswered gaps

**New precision for §§6,7.** The system must distinguish no eligible match, incomplete search, access failure, stale evidence, partial coverage and contradictory evidence. It must not interpret a top-k miss as proof that an event never occurred. Answers and closure decisions must disclose missing required support. Follow-up search is bounded by budget and scope; exhausted search may end in a qualified partial answer or abstention.

**Acceptance:** a task needing three evidence items receives only two: it exposes the missing support and does not claim complete coverage. A source access failure is not reported as factual absence.

**Basis:** existing research-grain semantics; S1/S3 motivate separate retrieval and reading failure diagnosis.

### MC-12 — Evaluate memory in later decisions and measure harm

**Extends §9.** Evaluation must include multi-session tasks in which later actions depend on earlier evidence, corrections and outcomes. Compare optional reusable memory absent, relevant, noisy and outdated while holding current requirements/policy constant. Measure correct recall, update propagation, supported decisions, abstention, regression, total cost and recovery separately. Report both tasks helped and tasks harmed, with denominators and repeated-run uncertainty.

**Acceptance:** a memory feature cannot pass solely on retrieval recall or average success. Its report includes a preservation slice of tasks already solvable without optional history and a chained task slice.

**Basis:** S2/S3/S4/S5; no source's model scores become product acceptance thresholds.

### MC-13 — Consolidate with explicit status and reversible derivation

**New, conditional on automatic reusable-memory consolidation.** Consolidation must produce a versioned proposal or derived view with source references and epistemic status. It must not replace canonical user instructions, original evidence, or verified predicate records. Durable accepted knowledge follows existing promotion rules. When enrichment fails or cannot be traced, original eligible evidence remains usable. Model-generated retrieval keys may improve findability without becoming authoritative claims.

**Acceptance:** a faulty consolidation is withdrawn/rebuilt without losing source history; an inferred user preference cannot silently become a global instruction; a failed enrichment has an original-source fallback.

**Basis:** existing staging model; S1 and local STAGE. This does not require autonomous memory writing or a separate persistent store.

### MC-14 — Withdraw memory across its derivatives

**New, conditional on durable reusable-memory retention.** Memory withdrawal must have defined effects on retrieval eligibility, summaries, embeddings, caches, worker packets and graph-derived views. Rebuilding derivatives must not resurrect withdrawn records as current memory. Historical/audit retention, active in-flight use and physical source deletion must have distinct documented semantics; the product must not claim erased bytes when it only suppresses retrieval.

**Acceptance:** withdraw a record, restart and rebuild derivatives: it remains ineligible for new current-state retrieval. An already-dispatched worker result depending on it is invalidated before acceptance. Any retained audit reference follows the declared retention policy.

**Basis:** product lifecycle inference; S2/S3 motivate semantic forgetting, which is distinct from physical deletion. This is not a legal compliance claim.

### MC-15 — Preserve graph-edge meaning and evidence boundaries

**New, conditional on expanded graph retrieval/memory.** Graph relations must distinguish declared structure, source-stated relations and inferred associations, preserving direction, negation, qualifiers, source version and validity where applicable. Community membership, degree and paths must remain advisory; paths do not create unsupported transitive or causal claims. Reports must identify snapshot and coverage. Invalid enrichment falls back to eligible source/lexical retrieval with degraded coverage visible.

**Acceptance:** “inhibits” cannot become “promotes”; undirected similarity cannot become directed dependency; a stale community report is identified; a two-hop association cannot close a causal claim without required evidence.

**Basis:** local LLM-S2KG/CoACL/STAGE and existing advisory-graph policy. Targeted dependency invalidation stays HARNESS-09 work.

### MC-16 — Bound memory operations as well as model context

**Clarifies §§6,8.** Retrieval expansion, evidence reads, consolidation, index/graph refresh and worker fan-out must have configured resource limits and observable exhaustion outcomes. Active required constraints and source evidence must not be silently evicted to satisfy a cache/storage cap. Cache expiry and derived-index eviction must preserve the distinction between source loss and temporary lookup unavailability. No memory-maintenance loop may silently consume unbounded paid calls.

**Acceptance:** adversarial graph fan-out, repeated irrelevant recalls and an exhausted ephemeral-result cache produce bounded partial/unavailable outcomes without deleting required state or restarting the same failed search indefinitely.

**Basis:** current efficiency/operability goals and S4's cost/latency evaluation; limits are implementation and qualification choices.

## Adoption and placement

Place MC-01/02/10/16 under specification §6; MC-03/04/05/13 under §4; MC-06/07 under §§3,7; MC-08/09 under §§3,5; MC-11 under §§6,7; MC-12 under §9; MC-14 under §§4,8; and MC-15 under §11's conditional graph boundary, with its eventual HARNESS-09 link.

Eleven clauses apply to existing boundaries: MC-01/02/03/06/07/08/09/10/11/12/16. Five are conditional feature contracts: MC-04/05/13/14/15. Implementation may split them into small packets. Spec adoption and implementation qualification are separate decisions; the prior implementation queue remains a proposal.
