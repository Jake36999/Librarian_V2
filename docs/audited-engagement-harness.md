# Librarian V2 audited-engagement harness and evidence-control specification

**Status:** Proposed implementation specification
**Version:** 1.0
**Date:** 2026-10-24
**Audience:** Core, runtime, model-routing, vault, Obsidian, browser, Cowork,
security, QA, and release maintainers

## 1. Decision

Librarian will add an opt-in, bounded **AuditedEngagement** mode for work whose
requirements can be checked against durable, inspectable state. It will use a
Manage–Execute–Audit loop, but it will remain one execution mode inside
Librarian rather than becoming the default for chat, research, or open-ended
writing.

The implementation must preserve these product properties:

- The normal research and co-work experience stays available for exploratory
  synthesis, brainstorming, and other work without an authoritative closure
  carrier.
- A model never becomes the authority for a vault mutation, promotion, route
  change, or human decision merely because it declares a task complete.
- The Core, VaultCoordinator, VaultWriter, IndexService, policy broker, and
  structured checkpoints remain the authority boundaries.
- All new durable state is non-secret, versioned, replayable, and written by
  the active Core through the writer queue.
- Evidence, constraints, and state changes remain inspectable by a person in
  the browser and Obsidian experiences.

This document is a design and implementation contract. It does not claim that
the described behaviour is already implemented.

## 2. Normative language, scope, and related specifications

The terms **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are
normative.

This specification extends, but does not replace:

- [Product contract](product-contract.md)
- [Model invocation architecture](model-invocation-architecture.md)
- [Model expectations registry](model-expectations-registry.md)
- [Qualification](qualification.md)
- [Workbench](workbench.md)
- [System attention, deployment, and runtime review](../reports/2026-10-23-system-attention-deployment-and-runtime-review.md)

The existing Workbench Engagement record remains the authority for
source-bound code execution and Docker or non-isolated host execution.
AuditedEngagement is a general work-control record. It MAY reference a
Workbench Engagement, but it does not replace, broaden, or weaken the
Workbench execution approval model.

### 2.1 Goals

- Make long-running, mutation-capable work resumable without carrying opaque
  model history across rounds.
- Require pre-mutation evidence and deterministic environmental feasibility
  checks before state-changing work.
- Make completion contingent on an evidence-appropriate audit, not an
  Executor self-report.
- Bound Executor cognitive load through a small task-specific tool surface and
  a bounded, explainable context capsule.
- Preserve human agency through explicit constraints, inspectable evidence,
  meaningful checkpoints, and non-rubber-stamp resolution controls.
- Protect Core and vault authority when imported, adopted, or external content
  is present in an agent context.
- Provide route- and role-specific cost, reliability, audit, interruption, and
  recovery evidence for later qualification and product decisions.

### 2.2 Non-goals

- Replacing ordinary Librarian conversation with a multi-round harness.
- Treating a durable file or database change as proof that an interpretation,
  synthesis, or recommendation is semantically correct.
- Autonomous goal expansion, self-authored permanent policies, self-approved
  promotion, or automatic model failover.
- Requiring a full semantic knowledge graph, a trained graph selector, or a
  generic behaviour-tree framework before the first safe implementation.
- Storing chain-of-thought, raw provider requests or responses, credentials,
  unredacted prompts, or unrestricted user-document copies in engagement
  traces.
- Turning paper-specific experimental values into product invariants.

### 2.3 Terminology

| Term | Meaning |
| --- | --- |
| AuditedEngagement | An opt-in Core-owned record coordinating a bounded set of requirements, contracts, evidence, audits, and checkpoints. |
| Manager | A non-mutating planning invocation. It proposes one next decision or contract from compact, persisted state; it has no direct environment interface. |
| Executor | A role-bound agent turn that can use only the contract's policy-eligible tools through the normal Core broker. |
| Auditor | A read-only verifier. Tier A is deterministic; Tier B is a fresh-context LLM assessment when policy requires it. |
| Requirement | A stable-ID statement of intended work, constraints, closure class, acceptance predicates, and verifier. |
| Closure carrier | A durable and inspectable artifact used to verify a requirement, such as a file fingerprint/diff, staged record, citation check, test result, or SQLite row. |
| State epoch | A monotonic version of the engagement's constraints and premises. It prevents stale audits from being reused after relevant human input or change. |
| Context capsule | A bounded, redacted set of contract facts, target-state metadata, evidence references, and selected source excerpts assembled for one fresh Executor or Auditor context. |
| Trust zone | Provenance and policy-exposure labels applied to inputs and outputs. A zone does not imply truth, reliability, or malicious intent. |
| Integrity | Whether work stayed within the contract's protected targets and audit constraints. Integrity is separate from semantic correctness. |
| Standard session | Existing Librarian chat/research behavior. It can create staged work and checkpoints but does not imply AuditedEngagement closure semantics. |

## 3. Research-to-product decisions

The design uses the supplied literature as input, but deliberately separates
transferable patterns from source-specific findings.

| Input | Product decision | Boundary on the claim |
| --- | --- | --- |
| LongHorizon-Harness Manage–Execute–Audit loop | Adopt a bounded, state-first round controller for eligible work. | It is optional and does not prove a gain on every task or route. |
| LongHorizon cost inversion between tested backbones | Meter Manager, Executor, and Auditor tokens, latency, retries, and cost by exact role and route. | Do not assume a stronger model always reduces total cost or that a hybrid pairing is superior. |
| LongHorizon negative transfer on hidden/undurable closure | Add an Auditable Closure Gate before the mode starts. | Long task duration alone is not sufficient for admission. |
| ReflectiChain feasibility and cognitive-load observations | Use deterministic checks against the actual vault, leases, tool health, and budget; keep Executor instructions compact. | Do not substitute a learned world model for real Core state or hard-code the paper's reflection thresholds. |
| STAGE bounded graph context | Use a budgeted context assembler that protects contract and target evidence before graph-derived context. | Its 512-token budget and graph-depth values are experiments, not Librarian defaults. |
| KDRAR small candidate-set result | Start with a profile-configurable cap of five Executor action tools after hard policy filtering. | API recommendation is not a proof that five is universally optimal for privileged tools. |
| LLM-assisted combinatorial optimisation | Require explicit constraints, acceptance predicates, and verifier strength. | An executable artifact can still omit a meaningful constraint. |
| Structural/semantic dual-graph research | Add a future derived structural fallback for adopted Markdown roots. | It is a Librarian adaptation, not a claim that a zero-LLM parser reproduces the paper's results. |
| Industrial soft sensors | Use cheap, versioned runtime quality signals to trigger attention. | They are advisory heuristics, not proof of correctness or an authorization mechanism. |
| AgentAI lifecycle work | Make interruption cooperative at durable operation boundaries. | Do not promise an unmeasured Windows stop latency or require a generic behaviour-tree framework. |
| Human-agency and pedagogy studies | Use evidence-first interrogation cards for consequential ambiguity and preserve user-authored constraints. | Do not force a debate card for every low-risk mechanical action or claim a particular UI proves better reasoning. |
| Agentic-RAG security research | Enforce trust-zone policy at the broker and retain auditable provenance. | Zone handling is a Librarian security design, not a substitute for normal platform security controls. |

## 4. Release gates and compatibility prerequisites

AuditedEngagement MUST NOT be enabled as a general mutation-capable workflow
until the following existing P0 boundaries are demonstrably complete.

| Gate | Required condition | Why it is a prerequisite |
| --- | --- | --- |
| Host lifecycle | The real-child Host stop regression is repaired; phase telemetry proves idle, active, writer-busy, checkpoint, force-stop, and crash-recovery paths clean up Core state. | An engagement must be safely interrupted without a false-live Core or lease. |
| SQLite ownership | Only IndexService opens vault SQLite in serving paths; static and concurrent stress tests enforce this. | Audited evidence and state reduction cannot be trustworthy if adapters or tools race the index. |
| Vault coordination | Every engagement write uses the active Core, VaultWriter, target fingerprints, and document leases. | A separate writer would defeat protected-target audits. |
| Canonical role routing | Lead, Scribe, Clerk, Helper, OCR, TTS, STT, and embeddings resolve through role or slot to exact host, exact model, expectation record, and qualification. | Manager, Executor, and Auditor traces must identify the route actually used. |
| Existing-root adoption | Create, Adopt, and Attach semantics plus a content-root manifest are available before adopted folders are treated as harness context. | The harness must not make arbitrary project documents disappear, acquire a false schema, or become invisible in Obsidian. |
| Route evidence | Model invocation traces contain non-secret route, adapter ABI, expectation hash, configuration hash, latency, retry, failure, and usage-availability fields. | Evaluation must distinguish a harness failure from a route or transport failure. |

Normal sessions, existing macros, source staging, Workbench Engagements, legacy
tiers, and the familiar model picker MUST continue to work through 2.x while
these gates are completed. Legacy tiers are a compatibility projection; they
MUST NOT become a second authority for a live AuditedEngagement route.

## 5. Product modes and the Auditable Closure Gate

### 5.1 Modes

| Mode | Appropriate work | Persistent completion claim |
| --- | --- | --- |
| Standard session | Exploration, research, brainstorming, open synthesis, ordinary drafting, or a task without inspectable closure. | No AuditedEngagement completion claim. Existing staging and approval rules still apply. |
| Plan-only engagement | A user wants a requirement ledger, estimates, and checkpoints but no bounded execution/audit loop. | Produces a plan or staged proposal only. |
| AuditedEngagement | Bounded work with declared requirements, durable closure carriers, acceptance predicates, and a permitted verification path. | Only a clean state-reducer transition may mark an authoritative requirement complete. |
| Workbench-linked AuditedEngagement | Audited work that uses a separately approved source-bound Workbench Engagement. | Source execution follows Workbench isolation and close rules in addition to this specification. |

The user MAY explicitly choose a mode. In automatic mode selection, the Core
MUST select AuditedEngagement only after the deterministic closure gate passes.
A request that cannot pass MUST remain a Standard session or Plan-only
engagement; the system MUST NOT invent a closure carrier to make the task look
auditable.

### 5.2 Closure classes

Every Requirement MUST declare one closure class.

| Closure class | Meaning | Completion rule |
| --- | --- | --- |
| authoritative | A deterministic or directly inspectable state carrier can establish the declared acceptance predicate. | May be completed after the required Tier A and, where policy requires, Tier B audit. |
| partial | The system can verify progress or provenance but cannot verify the full intended result. | May stage evidence and report partial progress; it MUST NOT declare final completion. |
| human_judgment | The result depends on interpretation, preference, contested evidence, or another human semantic decision. | The system prepares an evidence-first checkpoint; a person resolves or retains alternatives. |

A citation existence check, a validated database record, a test result, and a
file diff are examples of authoritative carriers only for the predicates they
actually test. A staged research summary normally remains partial or
human_judgment unless its exact claim coverage and resolution rule are
separately specified.

### 5.3 Auditable Closure Gate

Before admission, the Core MUST verify all of the following without invoking a
model:

1. The request names an existing project/session and a permitted caller.
2. Each Requirement has a stable ID, a closure class, constraints, an
   acceptance predicate, verifier type, and evidence-retention policy.
3. Each authoritative requirement identifies at least one inspectable closure
   carrier and its verification method.
4. Proposed targets are canonical, within an approved DocumentRoot or managed
   state root, and compatible with the task's write policy.
5. The requested role routes, qualification floor, budgets, tool capabilities,
   and host health are compatible with the work.
6. A required human decision is represented as a checkpoint, not an instruction
   buried in the Manager or Executor prompt.
7. The work can be bounded by maximum rounds, time, cost, target count, and
   writer operations.
8. The selected trust-zone policy permits the requested action.

The gate returns one of:

~~~text
ADMIT
REQUIRE_PLAN_REFINEMENT
REQUIRE_HUMAN_CLOSURE
REJECT_POLICY
REJECT_ENVIRONMENT
~~~

A successful gate states only that the engagement is eligible for controlled
execution. It does not establish that the task is feasible in a domain sense,
that its constraints are complete, or that the anticipated result is correct.

## 6. Authority model

### 6.1 Control-plane topology

~~~text
Person / Browser / Obsidian / Cowork
                |
                v
      active Librarian Core and checkpoint API
                |
    +-----------+------------------------------+
    |                                          |
    v                                          v
AuditedEngagement controller             VaultCoordinator
    |                                          |
    |                                  VaultWriter / IndexService
    |
    +--> Manager invocation: plan only, no environment tools
    |
    +--> deterministic compiler and preflight
    |
    +--> Executor invocation: bounded brokered tool bundle
    |
    +--> Tier A audit: deterministic, target-scoped
    |
    +--> Tier B audit: fresh-context, brokered read-only tools
    |
    +--> deterministic state reducer and checkpoint store
~~~

The active Core owns every transition. Browser UI, Obsidian, Cowork, CLI,
models, macros, packs, and helpers MUST use the Core API and its writer,
broker, session, and policy boundaries.

### 6.2 Effective authority

Before every provider request and every tool proposal, the broker MUST compute
effective authority as the intersection of:

~~~text
caller permission
AND role/profile permission ceiling
AND canonical role-to-route binding
AND engagement state and current state_epoch
AND session phase
AND contract read/write targets
AND selected tool bundle
AND current trust-zone restrictions
AND document lease and VaultCoordinator state
AND cost/time/output/concurrency budgets
AND unresolved checkpoint policy
~~~

No component may widen this intersection. Semantic ranking, compatibility
recommendations, model-card expectations, or a Manager recommendation may
select among already eligible options; they MUST NOT grant a tool, target,
route, or permission.

### 6.3 Role responsibilities

| Actor | May do | Must not do |
| --- | --- | --- |
| Person | Author/lock constraints, choose mode, resolve checkpoints, approve writes or promotions where required, inspect evidence, stop work. | Be silently replaced in a human_judgment closure. |
| Manager | Read compact persisted state, requirements, redacted audit reports, budget/route availability, and propose EXECUTE, ASK, DONE, or BLOCKED. | Open vault files, call tools, mutate state, declare authoritative completion, or alter route/policy. |
| Contract compiler | Validate and normalize the Manager proposal using deterministic policy and live Core state. | Infer missing semantic constraints or silently repair an incompatible plan. |
| Executor | Read declared context and use the contract's brokered tools; return structured execution evidence. | Expand its target/authority, bypass a checkpoint, or self-complete a requirement. |
| Tier A auditor | Compare deterministic target state and writer events with the contract. | Use a model, mutate any target, or claim semantic completeness beyond deterministic checks. |
| Tier B auditor | Read the capsule, required evidence, contract, and target state with read-only tools; identify gaps, scope drift, or ambiguity. | Receive raw Executor reasoning, mutate state, or promote content. |
| State reducer | Apply typed transition rules after valid audit results. | Treat model text as an unvalidated state transition. |

## 7. Durable data contract

All records in this section MUST be JSON-schema validated, versioned, and
written through VaultWriter. They belong in a versioned engagement store under
Librarian operational state, never in user-authored Markdown by default.
References to user documents remain paths plus fingerprints; the records MUST
NOT copy document bodies unless a separate evidence-retention policy permits a
protected snapshot.

The names below are intentionally distinct from the existing provider-level
TaskContract in model_invocation.py. That type describes a single model
invocation. This specification introduces the higher-level
AuditedSubtaskContract.

### 7.1 AuditedEngagement

~~~text
AuditedEngagement =
  schema_version
  engagement_id
  project_id
  session_id
  source_engagement_id?            # optional Workbench Engagement link
  created_by
  created_at
  updated_at
  mode                            # plan_only | audited
  state                           # see section 8
  state_epoch
  admission_result
  purpose
  role_bindings                   # manager, executor, auditor route snapshots
  work_budget
  constraint_ledger_ref
  requirement_refs
  current_round_id?
  current_contract_id?
  context_policy_ref
  trust_zone_summary
  policy_correction_refs
  event_log_ref
  last_audited_checkpoint_ref?
  completion_summary?
~~~

The engagement captures immutable route snapshots for each started round. A
route change requires an explicit host/model override or failover checkpoint,
creates a new round binding, and is never silently applied to an in-flight
continuation.

### 7.2 Requirement and constraint ledger

~~~text
Requirement =
  requirement_id
  text
  owner                            # human | system policy | imported plan
  closure_class                    # authoritative | partial | human_judgment
  status                           # open | active | satisfied | partial |
                                   # stale | untrusted | blocked | superseded
  constraint_ids[]
  acceptance_predicates[]
  verifier                         # deterministic | test_or_solver |
                                   # evidence_check | llm_assessment | human
  verification_strength            # exact | bounded | advisory | human
  closure_carriers[]
  dependency_ids[]
  created_epoch
  last_verified_epoch?
  evidence_refs[]
  unresolved_remainder?
~~~

~~~text
Constraint =
  constraint_id
  version
  text
  authority                        # user_locked | policy | accepted_plan
  scope                            # engagement | requirement | contract
  hard                             # true | false
  source_refs[]
  created_epoch
  supersedes?
  status                           # active | superseded | invalidated
~~~

A user-authored or user-locked constraint MUST NOT be rewritten by a model.
A model MAY propose a new constraint as a checkpoint option, with a clear
source and consequence, but it cannot apply it.

### 7.3 AuditedSubtaskContract

~~~text
AuditedSubtaskContract =
  schema_version
  contract_id
  engagement_id
  round_id
  state_epoch
  proposed_by                      # manager route and invocation ref
  executor_role
  executor_route_binding
  intent
  requirement_ids[]
  constraint_ids[]
  read_targets[]                   # canonical path or immutable evidence refs
  write_targets[]                  # canonical path, operation class, target hash
  protected_targets[]              # target snapshots audited for integrity
  preconditions[]
  pre_mutation_evidence_refs[]
  acceptance_predicates[]
  verifier_plan
  action_tool_bundle
  action_tool_limit
  context_capsule_ref
  trust_zone_policy
  checkpoint_requirements[]
  budget_reservation
  stop_conditions[]
  recovery_plan
  contract_hash
~~~

The contract is immutable after preflight. A materially changed target,
constraint, route, tool bundle, context policy, or state epoch requires a new
contract. The contract MUST express a bounded action, not a vague goal such as
"make the project better."

### 7.4 EvidenceSnapshot

~~~text
EvidenceSnapshot =
  snapshot_id
  engagement_id
  contract_id
  target_ref
  captured_at
  captured_by
  state_epoch
  content_fingerprint
  metadata_fingerprint
  source_zone
  retention_class                  # hash_only | protected_copy | external_ref
  protected_evidence_ref?
  size_bytes
  capture_reason                   # pre_mutation | pre_audit | post_audit
~~~

A mutation contract whose acceptance or recovery depends on before-state
evidence MUST acquire all required pre-mutation snapshots before its first
write. A hash-only snapshot is sufficient only when the original target remains
available and a full copy is not needed to establish the stated predicate.
Large or sensitive material MUST follow the configured retention policy; the
harness MUST NOT copy it merely for convenience.

### 7.5 ContextCapsule

~~~text
ContextCapsule =
  capsule_id
  engagement_id
  contract_id
  state_epoch
  assembler_version
  total_token_budget
  reserved_contract_tokens
  reserved_target_tokens
  reserved_evidence_tokens
  graph_context_budget
  source_refs[]
  fragment_refs[]
  selection_reasons[]
  excluded_refs[]
  capsule_hash
  created_at
~~~

The capsule stores references and bounded excerpts according to retention
policy, not raw chat history. It MUST include its exact selection reasons so a
person can see why a source was provided to a model.

### 7.6 ExecutionReport and AuditReport

~~~text
ExecutionReport =
  report_id
  engagement_id
  contract_id
  round_id
  executor_route_binding
  started_at
  ended_at
  outcome                          # completed_work | partial | blocked |
                                   # cancelled | failed
  operation_refs[]
  observed_target_refs[]
  produced_evidence_refs[]
  declared_gaps[]
  retry_summary
  runtime_trace_ref
~~~

~~~text
AuditReport =
  report_id
  engagement_id
  contract_id
  round_id
  audit_tier                        # A | B
  auditor_route_binding?            # Tier B only
  state_epoch
  status                            # complete | partial | failed |
                                   # needs_human | blocked
  integrity                         # clean | suspect | violation
  verification_strength
  verified_requirement_ids[]
  unverified_requirement_ids[]
  verified_facts[]
  evidence_refs[]
  scope_drift_findings[]
  constraint_findings[]
  target_diff_refs[]
  audit_trace_ref
  created_at
~~~

An AuditReport is evidence about named requirements at a named state epoch. It
MUST NOT become a free-form global verdict on the vault or project.

### 7.7 RuntimeQualitySignal

~~~text
RuntimeQualitySignal =
  signal_id
  engagement_id
  round_id
  state_epoch
  kind
  value
  threshold_or_rule_version
  severity                          # info | watch | intervene
  input_hashes[]
  observed_at
  recommended_action                # continue | audit | replan | pause |
                                   # checkpoint
  resolution?
~~~

RuntimeQualitySignal values are calibrated heuristics. They may trigger
attention, but never independently allow a mutation, promotion, model
failover, or skipped required audit.

### 7.8 InvalidationEvent and policy corrections

~~~text
InvalidationEvent =
  event_id
  engagement_id
  state_epoch
  cause_type                        # user_constraint_change | user_rejection |
                                   # failed_audit | target_edit | source_change
  cause_ref
  affected_refs[]
  dependency_rule
  actor
  reason
  created_at
~~~

~~~text
PolicyCorrection =
  correction_id
  engagement_id
  requirement_id?
  constraint_id
  rejected_action_pattern
  trigger_evidence_ref
  permitted_recovery_action
  created_epoch
  expires_at?
~~~

Policy corrections are typed, bounded, and auditable. At most five active
corrections MAY be rendered in a capsule, and each MUST cite the governing
constraint or evidence. They are not self-modifying model policy and cannot
override the constraint ledger.

## 8. State machine and transition invariants

### 8.1 Engagement states

~~~text
DRAFT
  -> ADMISSION_PENDING
  -> READY
  -> MANAGING
  -> PREFLIGHT
  -> EXECUTING
  -> DETERMINISTIC_AUDIT
  -> LLM_AUDIT
  -> REDUCING
  -> READY | WAITING_FOR_USER | PAUSED | COMPLETED |
     PARTIALLY_COMPLETED | BLOCKED | FAILED | INTERRUPTED | CANCELLED
~~~

A state transition is valid only when a durable EngagementEvent records the
prior state, event type, actor, state epoch, input references, result, and
resulting state.

### 8.2 Main round

~~~text
1. Manager:
   persisted state + compact audit/evidence summaries
   -> EXECUTE | ASK | DONE | BLOCKED and, for EXECUTE, proposed contract

2. Contract compiler and deterministic preflight:
   proposed contract + real Core/vault/lease/route state
   -> PASS | REJECT_INFEASIBLE | REQUIRE_CHECKPOINT

3. Executor:
   fresh bounded context + contract + policy-eligible tool bundle
   -> durable operations + structured ExecutionReport

4. Tier A deterministic auditor:
   pre/post protected-target state + VaultWriter events + verifier plan
   -> AuditReport(integrity, deterministic findings)

5. Tier B LLM auditor when required:
   fresh bounded audit context, no raw Executor trajectory
   -> AuditReport(status, evidence, gaps, scope findings)

6. Deterministic reducer:
   validated reports + current state epoch
   -> state/requirement update or a checkpoint
~~~

The Manager may propose DONE. The reducer MAY reach COMPLETED only if every
authoritative Requirement has the specified clean verification evidence at the
current epoch. A Manager declaration, Executor self-report, or green runtime
quality signal is insufficient.

### 8.3 Terminal and recovery behavior

| Situation | Required result |
| --- | --- |
| Provider transient failure | Preserve completed writer operations, record the typed failure, apply bounded retry or pause according to the contract. |
| Provider permanent, parser, model identity, permission, or schema failure | Do not retry blindly and do not fail over silently. Pause or create the applicable route/checkpoint decision. |
| Document lease begins during a multi-step contract | Stop before the next write to that document, preserve completed work, and create a document-conflict checkpoint. |
| Protected target changes outside the allowed writer operation | Tier A reports suspect or violation. Completion is blocked until a person resolves the conflict or a new contract/audit is created. |
| Audit attempts a write | Record integrity violation, revoke the report's ability to complete requirements, and stop the audit episode. |
| User changes a relevant constraint | Increment the state epoch, invalidate affected derived records, and return to READY or WAITING_FOR_USER. |
| Host stop/cancellation | Stop admission, reach a durable safe boundary, write INTERRUPTED state, and present a resume decision. |
| Unbounded or ambiguous closure | Remain partial, plan-only, or waiting for human judgment; do not manufacture completion. |

## 9. Contract compilation and deterministic preflight

### 9.1 Manager output is a proposal, not a command

The Manager receives only:

- the current requirement and constraint summaries;
- the current state epoch;
- redacted audit outcomes and evidence references;
- current route availability and remaining work budget;
- unresolved checkpoints and stop conditions; and
- the prior policy correction summaries.

It does not receive direct vault tools, shell tools, network tools, or raw
Executor chat. It returns a typed object with exactly one action:

~~~text
EXECUTE(contract proposal)
ASK(checkpoint proposal)
DONE(closure rationale)
BLOCKED(reason and missing dependency)
~~~

The compiler validates all model-proposed identifiers against persisted state.
Unknown targets, tools, requirement IDs, constraints, evidence IDs, and
checkpoints are rejected rather than inferred.

### 9.2 Preflight checks

The deterministic preflight MUST check, at minimum:

| Check | Failure outcome |
| --- | --- |
| Current Core owns the mutable vault lease. | Reject environment. |
| Engagement and contract state epochs match. | Discard contract and re-manage. |
| Requirement and constraint IDs exist and are active. | Reject contract. |
| Read/write targets resolve canonically within approved roots. | Reject policy. |
| Read targets exist and match required fingerprints where specified. | Reject infeasible or require re-plan. |
| Write targets are permitted, not under an active document lease, and have valid preconditions. | Create conflict checkpoint or reject infeasible. |
| Required pre-mutation snapshots are durable before any write. | Reject contract. |
| Selected route, adapter ABI, expectation record, profile, qualification, tool health, and host health meet the contract. | Reject or request route/checkpoint decision. |
| Budget reservation fits remaining time, token, cost, writer-operation, and round limits. | Require user budget decision or reject. |
| Trust-zone policy allows the requested read/write/execution combination. | Reject policy or require checkpoint. |
| Tool bundle contains no more than the configured action-tool cap and every member is broker-eligible. | Reject contract. |
| Required verifier is available. | Mark closure partial or block before execution. |

The result MUST be labelled **environment_feasible** when it passes. It MUST
NOT be labelled semantically correct, constraint-complete, secure, or
guaranteed to succeed.

### 9.3 Pre-mutation evidence lock

For each existing mutable target, the compiler determines whether a
before-state artifact is required by recovery, audit, or acceptance policy.

When it is required:

1. Core captures an EvidenceSnapshot and writes a durable event.
2. Core validates the target's current fingerprint and document lease.
3. Only then can the Executor receive a mutation-capable contract.
4. Before each later write step, broker and writer recheck target scope, lease,
   preconditions, and state epoch.

The protected target set is contract-specific. The system MUST NOT hash an
entire vault to judge audit integrity: unrelated Obsidian activity must not
cause a false violation for an independent document.

## 10. Context and tool-surface control

### 10.1 Budgeted context assembler

A ContextCapsule uses a profile- and route-configurable hard token budget. The
assembler MUST reserve space in the following order:

1. Immutable contract fields, active hard constraints, acceptance predicates,
   target fingerprints, and stop conditions.
2. The target artifact's minimum necessary content or a safe reference.
3. Required evidence and provenance references.
4. The target's own local context.
5. Direct explicit links, citations, structural parent/child or adjacent
   blocks, and approved related documents.
6. Optional semantic/graph-derived context, ordered by explainable relevance.

Later tiers MUST NOT evict contract facts, target state, or mandatory evidence.
The assembler records omitted sources and the reason, allowing a person or
Manager to request a narrowly scoped expansion.

The first implementation SHOULD use deterministic, explainable selection:
explicit links, citation relationships, heading/section proximity, lexical
match, and existing search evidence. It MUST NOT claim to implement a trained
graph-conditioned selector unless one is actually trained, versioned, and
qualified.

### 10.2 Executor action-tool bundle

The default AuditedEngagement Executor bundle MUST expose at most five ranked,
policy-eligible **action tools**. Required terminal controls such as
complete, report_blocked, request_checkpoint, and a controlled
request_bundle_expansion do not count toward this action-tool cap, but remain
fully brokered.

The selection process is:

1. Apply hard filters: role, profile, session phase, trust zone, target scope,
   lease state, host/tool availability, budget, and unresolved checkpoints.
2. Rank only surviving action tools using task and contract relevance plus
   versioned compatibility evidence.
3. Choose up to the profile's configured cap, initially five.
4. Record each offered tool, rank reason, excluded tool, and bundle hash in
   the trace.
5. Require a structured checkpoint and a new contract before expansion beyond
   the cap.

Semantic and keyword weights, co-use data, and candidate counts are
calibration inputs. They MUST be versioned and evaluated per corpus/profile;
they do not grant authority and are not a universal five-tool theorem.

Ordinary Librarian tool bundles remain governed by existing product policy.
This cap applies only to the AuditedEngagement Executor unless later
evaluation justifies a broader change.

### 10.3 Compact Executor instructions

Executor instructions SHOULD contain a short task contract, tool outcomes,
constraints, stop conditions, and an explicit structured report format. They
MUST NOT carry lengthy reflection histories, full vault dumps, raw Manager
reasoning, or a growing transcript of failed attempts.

Richer reflection, multi-agent debate, or domain-specific prompts require a
versioned expectation/profile record and L2 or higher evidence for that exact
route and role. No general prompt rule such as "disable thinking" may be
invented for a model family without a reviewed expectation record and adapter
support.

## 11. Execution semantics

### 11.1 Fresh context and durable operations

Each Executor round starts in a fresh provider context built from the
contract's capsule. The executor may read its current contract and selected
tool results, but it does not receive previous raw trajectories.

The system retains:

- contract, bundle, route, adapter ABI, expectation hash, and configuration
  hash;
- operation IDs, target paths, preconditions, results, and fingerprints;
- bounded redacted tool arguments/results as allowed by trace policy;
- timestamps, queue delay, retry/failure class, and usage availability; and
- structured ExecutionReport and audit evidence references.

The system MUST NOT retain or relay hidden reasoning, raw provider bodies,
credentials, or unrestricted prompt content in the engagement store.

All mutations—including macro steps—MUST be offered to the same broker and
VaultWriter used by ordinary Core operations. A macro expands to traceable
registered operations before it begins; it cannot hide a write, bypass a
checkpoint, or promote content.

### 11.2 Model and route behavior

An Executor, Manager, or Tier B Auditor route is resolved through the
canonical role/slot binding:

~~~text
role or slot
  -> Host ID
  -> exact provider model ID
  -> expectation record
  -> protocol adapter
  -> role-specific qualification state
~~~

The route binding is persisted in the round. A route mismatch, missing observed
model identity, unsupported adapter behavior, or required qualification
failure is a typed failure. It cannot be repaired by silently selecting a
different position, tier, host, or model.

Librarian work budget remains separate from route-native model behavior:

- **Work budget** controls Core-side turns, action attempts, delegated work,
  audit work, time, and cost.
- **Model behaviour** exposes provider-native thinking, reasoning, template,
  or sampling controls only when the exact expectation record and trusted
  adapter permit them.

The UI and trace MUST show which one influenced a round.

## 12. Audit model

### 12.1 Tier A deterministic audit

Tier A always runs after a mutation-capable contract and before any Tier B
assessment. It compares the contract, before-state snapshots, writer
operations, watcher events, and after-state snapshots.

Tier A MUST check, when applicable:

- every observed mutation is within an allowed write target and allowed
  operation class;
- the Auditor broker did not invoke a mutation-capable operation;
- target preconditions and postconditions are present;
- file/config/document schema checks pass;
- required evidence, citations, fingerprints, IDs, and staged records exist;
- deterministic tests, solvers, or validators named in the contract ran and
  their result references match the accepted state;
- protected target state did not change outside writer operations;
- active document leases or external edits did not invalidate the target
  comparison; and
- no budget, phase, or checkpoint violation occurred.

Tier A returns integrity:

| Integrity | Meaning | Reducer behavior |
| --- | --- | --- |
| clean | Protected state and deterministic checks agree with the contract. | Eligible for the next required verifier. |
| suspect | State changed unexpectedly, evidence is incomplete, or a concurrent edit prevents a reliable conclusion. | Cannot complete; pause, re-plan, or create a checkpoint. |
| violation | A disallowed mutation, audit write, policy breach, or protected-target breach occurred. | Cannot complete; create incident/invalidation evidence and require resolution. |

Tier A establishes integrity and the exact deterministic predicates it checked.
It does not infer that an open-ended conclusion is true.

### 12.2 Tier B read-only LLM audit

Tier B is invoked only after Tier A is clean and only when the verifier plan
requires semantic/evidence assessment. It receives a fresh audit capsule:
the requirements, constraint ledger, contract, Tier A result, named target
state, evidence excerpts/references, and Executor's structured report. It MUST
NOT receive raw Executor reasoning.

Tier B uses a dedicated read-only broker profile. The audit route SHOULD be
independent from the Executor when a qualified alternative exists. If the same
route is used, the report MUST declare same-route audit so the UI and later
evaluation can account for correlated error.

Tier B MUST explicitly assess:

- whether each named requirement has evidence at the stated verification
  strength;
- scope narrowing or constraint reinterpretation;
- unsupported claims, contradictory evidence, or unresolved ambiguity;
- whether a human_judgment closure remains unresolved; and
- whether the described result exceeds the actual closure carrier.

A Tier B conclusion is an evidence-bound report, not a promotion action.

### 12.3 Conditional audit policy

Tier B is mandatory when any of the following applies:

- a Requirement asks for semantic synthesis, claim coverage, conflict
  resolution, or a human-jurisdiction recommendation;
- a result will be promoted to a canonical note, external system, or
  consequential Workbench application;
- a sensitive or untrusted input materially informed the result;
- a required deterministic verifier is unavailable or only bounded;
- the contract is terminal and policy marks its risk as high; or
- a RuntimeQualitySignal requests audit intervention.

Tier B MAY be skipped only when all requirements completed in the round have
exact deterministic verification, the profile permits deterministic closure,
Tier A is clean, and the skip is recorded. A skipped Tier B never upgrades a
partial or human_judgment closure to authoritative.

The selection policy MUST be measured before optimization. In particular, the
system records how often Tier A and Tier B each intercept false completion or
integrity defects; it MUST NOT adopt a universal skip threshold from a paper
or anecdote.

## 13. State reduction, epochs, and provenance invalidation

### 13.1 Deterministic reducer

Only the reducer may alter Requirement status. It validates:

- AuditReport schema and contract/round/epoch references;
- integrity and verification strength;
- all completion predicates for the relevant closure class;
- the absence of a newer state epoch;
- unresolved mandatory checkpoints; and
- all required durable evidence references.

The Manager is invoked after reduction to propose the next step if work
remains. It does not participate in applying the transition.

### 13.2 Epoch invalidation

The Core increments state_epoch when:

- a person answers an ASK or modifies a locked constraint;
- a human edit changes a protected target or a requirement's premise;
- a person rejects/revises a staged result;
- a required source/evidence item changes or is withdrawn; or
- an audit violation makes previously accepted derived state unsafe to reuse.

The invalidation engine follows typed dependency edges from the changed
constraint, target, evidence, or source. It marks only dependent records
stale or untrusted pending re-audit. It MUST NOT downgrade unrelated
requirements simply because an answer occurred elsewhere in the engagement.

For every invalidation:

- preserve original source and historical audit record;
- create a durable InvalidationEvent;
- record the traversal bound and any cycle encountered;
- exclude invalidated material from default premise retrieval;
- allow a person to inspect it, restore it only through a new review, or
  keep it as a superseded alternative; and
- require a new contract or audit before it can support authoritative
  completion again.

A model can flag a possible dependency issue, but deterministic rules or a
human decision create the authoritative invalidation event.

## 14. Runtime quality signals and interruptibility

### 14.1 Runtime quality signals

The first implementation SHOULD emit deterministic, low-cost signals such as:

| Signal | Inputs | Possible response |
| --- | --- | --- |
| stall | Repeated normalized tool signatures, repeated validation failures, no protected-target progress, or a bounded retry loop. | Pause, re-plan, or request review. |
| environment drift | Missing target, changed fingerprint, active document lease, unavailable tool, host breaker, or budget pressure. | Re-run preflight, pause, or checkpoint. |
| evidence coverage | Requirement-declared evidence slots versus structured evidence refs actually present. | Tier A, Tier B, or human review. |
| scope mismatch | Contract target/operation class versus a proposed operation. | Broker refusal and integrity finding. |
| optional semantic drift | A versioned retrieval/embedding diagnostic against constraints. | Advisory audit/re-plan trigger only. |

An embedding similarity score, action-loop entropy score, citation-to-claim
ratio, or numeric threshold requires a formula version, test corpus, false
positive/negative analysis, and profile/route calibration. It MUST remain
advisory until those conditions are met. Green signals never prove correctness.

### 14.2 Cooperative interruption

AuditedEngagement uses a small explicit round controller with safe boundaries;
it does not require a third-party generic behaviour-tree framework. The
controller has Sequence, Fallback, Retry, and cancellation semantics where
they are useful, while retaining a simple Core-owned state machine.

A shared cancellation token MUST be checked:

- before and after every provider call;
- before every brokered tool proposal and after every returned result;
- before and after Tier A and Tier B audit;
- before state reduction; and
- before admission of the next round.

When Host stop begins:

1. Core marks the host and affected engagements draining; no new admission is
   allowed.
2. Queued jobs are parked or cancelled according to their resumability policy.
3. Streaming provider requests are cancelled where the transport supports it.
4. The controller reaches the next durable operation boundary.
5. VaultWriter flushes or rolls back the active atomic operation.
6. Core records an INTERRUPTED checkpoint with last completed state, contract,
   operation, and recovery information.
7. Core drains writer work, closes index resources, releases the vault lease,
   and exits or records the last completed shutdown phase before a force stop.

The product MUST distinguish paused, interrupted, blocked, failed, and
cancelled. Resume is permitted only from a durable checkpoint after a fresh
preflight. No fixed sub-second or two-second stop promise is made until
Windows lifecycle measurements establish an enforceable service objective.

## 15. Trust zones and indirect-instruction defense

### 15.1 Zone labels

A source, chunk, evidence item, tool result, cross-agent message, and context
capsule may carry one or more labels:

~~~text
user_authored
managed_librarian_state
adopted_workspace
untrusted_external
sensitive
~~~

These describe provenance and policy exposure. They do not establish that
content is true, harmless, user-approved, or safe to execute. An adopted
workspace is not automatically trusted merely because it is local.

Labels propagate into derived items as an auditable union unless a separate,
reviewed transformation explicitly changes the policy classification. A source
document's embedded instructions are always data; they cannot define system
policy, grant a tool, alter a route, or persuade the broker to bypass a
checkpoint.

### 15.2 Broker enforcement

If untrusted_external material materially informs an Executor contract, the
default authority is read, extract, and stage only. In that same execution
episode, the broker MUST deny:

- shell or code execution;
- document or settings mutation;
- credential access;
- host/model/profile/route changes;
- external MCP actions;
- content promotion; and
- any write not explicitly approved through a separate scoped contract.

A person may create a separate, explicit, reviewed contract that names the
input sources, output targets, required evidence, and checkpoint. The new
contract is a new decision boundary; it does not retroactively make the
external content trusted.

All denials record the relevant trust zone, policy rule, source reference, and
non-secret reason. Guardrail text in a prompt is not a substitute for this
broker enforcement.

## 16. Brownfield documents, structural context, and deduplication integration

AuditedEngagement does not implement directory adoption, but it depends on the
deployment contract in the system-attention review.

### 16.1 Content-root invariants

For an adopted or attached documentation tree:

- .librarian remains operational state only. User-authored project documents
  MUST remain visible outside it for Obsidian.
- Existing files are not moved, rewritten, frontmatter-normalized, or assigned
  a research shape merely because of folder names.
- Markdown lacking a Librarian shape receives the virtual,
  root-scoped workspace_document identity for search and context purposes.
- The deployment manifest records canonical root identity, access mode,
  includes, excludes, scan fingerprint, and origin.
- Attach mode is read-only for Librarian. Any generated visible workspace is a
  separately selected user location.

The harness may read an approved content root only through Core-owned index and
document services. It MUST honor its read-only/read-write mode, document
leases, and source zone.

### 16.2 Derived structural fallback

A later derived-index phase SHOULD build a disposable structural graph for
adopted Markdown without mutating user files:

~~~text
file
  -> ordered heading / section / paragraph / list-block nodes
  -> parent-child edges
  -> before-after edges
  -> explicit wikilink/citation edges
  -> optional continuation edges with extraction provenance
~~~

Malformed headings or unfamiliar files MUST fall back to ordered block
segments rather than being dropped. Semantic concept links, if added, remain
separate derived edges with source locations, extraction version, and
confidence. They do not overwrite structural relations or become canonical
evidence by themselves.

Context retrieval prioritizes direct evidence and semantic links when present,
then uses target-local structural parent/child, sibling, and continuation
relations as an explainable fallback. It begins shallow and expands only under
the capsule budget. This is a product adaptation informed by dual-graph
research; it does not claim to reproduce a particular paper's parser,
accuracy, memory, or depth result.

### 16.3 Dedupe contract

The adoption/index layer supplies the harness with stable document references
using these reviewable identities:

1. Canonical path, case rules, resolved symlink/junction behavior, and where
   available volume/file identity for move detection.
2. Exact byte hash.
3. Versioned normalized-text hash.
4. Canonical external identity, such as DOI, canonical URL, repository remote
   plus pinned revision, or explicit frontmatter ID.
5. Near-duplicate candidate groups, never automatic merge decisions.

An engagement records the actual document/reference identity used in a
contract, not only a display title. Near-duplicate suggestions require human
resolution and cannot silently collapse evidence provenance.

## 17. Human co-work experience

### 17.1 Delegation and constraint control

At engagement start, the UI presents:

~~~text
Goal
Requirements and closure class
Locked constraints
Named targets and permitted effects
Role routes and qualification state
Work budget versus route-native model behaviour
Expected evidence, checkpoints, and closure limitations
~~~

A person may edit or lock the constraints before delegation. The UI clearly
states whether a result can be auto-completed, only staged, or requires human
judgment. It must not imply that an LLM audit is an objective certification.

### 17.2 Interrogation checkpoints

For material ambiguity, conflicting evidence, high-impact promotion, a
constraint change, or an incompatible proposed action, the checkpoint UI MUST
present an evidence-first knowledge artifact:

~~~text
Question or constraint in dispute
Pre-state and proposed post-state diff
Two or three materially distinct, evidence-grounded options when available
Supporting and conflicting source references
Consequences, verification strength, and unresolved uncertainty
Actions: choose | edit constraint | request evidence | keep separate | defer
~~~

The system SHOULD encourage independent user framing before a consequential
semantic decision, but it MUST permit deferral and MUST NOT force an
artificial debate for straightforward low-risk mechanics. Routine deterministic
checks use concise confirmation controls.

### 17.3 Runtime panel

An active engagement panel shows:

- goal, current requirement, state, and current state epoch;
- Manager, Executor, and Auditor exact routes, adapter/expectation versions,
  qualification state, and whether the audit is same-route;
- queued, running, paused, blocked, and interrupted status;
- current cost/time/token/round usage and reserved remaining budget;
- target/diff/evidence links and current integrity;
- runtime quality signals as warnings, never as opaque correctness scores;
- next action and the exact reason a checkpoint, pause, or refusal occurred;
  and
- explicit Pause, Stop, Resume, and Inspect controls.

Browser/Obsidian closing never automatically terminates Core or an engagement.
Host Stop remains an explicit user-controlled action with the interruption
semantics in section 14.

## 18. Observability, retention, and privacy

### 18.1 Trace fields

Engagement traces are durable, append-only, non-secret operation evidence.
They SHOULD align with familiar GenAI telemetry names where useful and include:

~~~text
gen_ai.provider.name
gen_ai.operation.name
gen_ai.request.model
gen_ai.response.model
gen_ai.usage.input_tokens                # when safely available
gen_ai.usage.output_tokens               # when safely available
error.type

librarian.engagement_id
librarian.round_id
librarian.role_slot
librarian.route_binding_hash
librarian.adapter_abi_version
librarian.expectation_record_hash
librarian.invocation_config_hash
librarian.work_budget
librarian.qualification_level
librarian.contract_hash
librarian.context_capsule_hash
librarian.tool_bundle_hash
librarian.state_epoch
librarian.audit_tier
librarian.integrity
librarian.queue_ms
librarian.provider_latency_ms
librarian.retry_count
librarian.failure_class
~~~

The trace MUST NOT contain API keys, secret references, raw provider payloads,
hidden reasoning, full prompt text, unrestricted document text, or browser
session credentials. Content references and redacted bounded excerpts follow
the vault retention policy.

### 18.2 Evaluation metrics

Every evaluated engagement records, by exact role/route/profile:

- admission outcome and closure class;
- completion, partial completion, interruption, recovery, and user-abandon
  outcomes;
- requirement-level false-completion interception by Tier A and Tier B;
- integrity violations, conflicts, broker refusals, and invalidations;
- Manager/Executor/Auditor token, time, cost, retry, queue, and failure shares;
- context size, offered action-tool count, bundle expansions, and tool outcome
  distribution;
- checkpoint type, time to resolution, resolution choice, and rework;
- user edits and independent external edits that affected protected targets;
- route/model identity mismatches; and
- retention/trace redaction checks.

Cost estimates are estimates, not provider invoices, unless reconciled to a
provider source under an explicit accounting policy.

## 19. Implementation architecture and module mapping

This is an implementation map, not authorization to bypass existing contracts.

| Area | Primary implementation location | Required change |
| --- | --- | --- |
| Engagement schemas, events, state reducer | New audited_engagement.py or similarly scoped Core module | Define records in section 7, validated transitions, durable event store, replay, and epoch checks. |
| Contract compiler and preflight | New engagement_contracts.py plus policy/broker integration | Compile Manager proposals, perform section 9 checks, and reserve budgets. |
| Tier A and Tier B audit | New engagement_audit.py | Implement target-scoped deterministic audit and fresh-context read-only audit orchestration. |
| Provider invocation | model_invocation.py and existing provider path | Reuse immutable InvocationPlan, canonical route binding, adapter ABI, and redacted trace fields; do not overload provider TaskContract. |
| Agent loop | loop.py and agent_runtime.py | Add a narrow engagement execution adapter and cancellation checks; do not rewrite ordinary Loop behavior. |
| Broker, rule, and checkpoint controls | Existing rules/broker integration and checkpoints.py | Enforce authority intersection, add engagement checkpoint types, and surface typed refusals. |
| Vault/lease/write state | coordination.py | Reuse VaultCoordinator, DocumentLeases, VaultWriter, atomic writes, precondition fingerprints, and operation logging. |
| Indexing and reads | index.py and Core API | Keep IndexService as owner; no direct SQLite or adapter connections. |
| Quality signals | quality.py or a narrowly named engagement-quality module | Produce versioned advisory signals with no authorization effect. |
| Provenance and invalidation | provenance.py, facts.py, staging.py | Add typed dependency edges, invalidation events, default retrieval exclusion, and human inspect/restore flows. |
| Trust zones | intake.py, evidence handling, broker/rules, sandbox.py | Stamp inputs/outputs and enforce episode-scoped authority reductions. |
| Brownfield context | adoption/init, notes.py, index.py, search.py | Add content roots, workspace_document fallback, structural derived index, and layered dedupe before harness reliance. |
| Host lifecycle | host.py | Complete phase telemetry and interruption/force-stop cleanup before enabling mutation-capable engagements. |
| Browser/Obsidian/Cowork | shared UI, adapter contract, checkpoints | Render mode entry, ledger, evidence/diff, interrogation, runtime panel, and dispose/cancellation behavior. |

The first delivery SHOULD use simple explicit state-machine functions and
JSON-schema validation. A generic graph/BT/orchestration framework is deferred
until repeated implementations demonstrate a need for one.

## 20. Rollout plan

### Phase A — Preconditions and no-op foundations

1. Repair Host stop/liveness behavior and add phase-level lifecycle tests.
2. Enforce IndexService-only SQLite ownership with static AST guard and
   concurrency tests.
3. Complete canonical role/slot route binding and role-specific readiness.
4. Land adoption plan/apply/content-root safety and workspace_document search
   fallback.
5. Add schemas, event store, state replay, and read-only UI inspection without
   starting live engagement execution.

**Exit:** An empty/draft engagement can be created, replayed, inspected, and
cancelled without mutating user content or selecting a different runtime path.

### Phase B — Admission, plan-only, and deterministic evidence

1. Implement closure-class schema and Auditable Closure Gate.
2. Implement Manager proposal parsing, deterministic compiler, preflight, and
   budget reservation with scripted test routes.
3. Implement snapshots, protected target sets, Tier A audit, state reducer,
   state epochs, and targeted invalidation.
4. Add plan-only engagement UI and simple low-risk interrogation checkpoints.

**Exit:** Scripted and deterministic fixtures prove that impossible,
under-specified, stale, or un-auditable work cannot become a mutation contract.

### Phase C — Bounded Executor and safe recovery

1. Bridge the existing loop through an engagement adapter with fresh context,
   action-tool cap, contract hash, and cancellation checks.
2. Route all executor writes through broker/VaultWriter with precondition and
   document-lease checks.
3. Persist redacted execution events and recover from provider failures,
   document conflicts, cancellation, and restart.
4. Add Tier B read-only audit with no raw Executor trajectory transfer.

**Exit:** A qualified route can execute narrow file/staging/index fixtures;
only clean required audit evidence changes requirement state.

### Phase D — Trust, user agency, and Workbench integration

1. Add trust-zone labels, propagation, broker enforcement, and evidence
   staging for untrusted external input.
2. Add evidence-first interrogation cards for conflict, promotion, route,
   constraint, and sensitive-source decisions.
3. Link source-bound AuditedEngagement rounds to the existing Workbench
   approval/isolation/close record without weakening Docker or host-execution
   policy.
4. Add bounded policy correction and provenance invalidation UI.

**Exit:** Poisoned or ambiguous input cannot acquire write/execution authority;
a person can interrogate, defer, or preserve competing evidence.

### Phase E — Brownfield context and evidence-calibrated optimization

1. Build read-only structural parsing and fallback retrieval for adopted roots.
2. Add layered dedupe/move identity and explainable context selection.
3. Tune capsule budgets, action-tool cap, Tier B conditions, and runtime
   signals using offline fixtures and recorded engagement outcomes.
4. Update qualification and release artifacts with evidence for the exact
   roles/routes used.

**Exit:** An adopted documentation corpus is useful without mutation, graph
context is bounded and inspectable, and any optimized policy has measured
evidence rather than a copied paper threshold.

### Phase F — release qualification

1. Complete browser, Obsidian, and Cowork handshake/lifecycle checks.
2. Run deterministic L0 suites on every change and controlled L1–L3 route
   qualification on release candidates.
3. Publish operator, security, interruption, retention, adoption, recovery,
   and rollback documentation.
4. Ship initially behind an explicit per-vault feature flag and a reversible
   update path.

**Exit:** Stable release claims are backed by clean lifecycle, concurrency,
security, role-route, and cross-adapter regression evidence.

## 21. Test and evaluation contract

### 21.1 Deterministic L0 tests

L0 must cover at least:

- schema validation, unknown field rejection, migration, and replay;
- every allowed and forbidden state transition;
- closure gate acceptance/rejection and no accidental fallback to audited mode;
- contract hash and immutable route/bundle/constraint binding;
- preflight path, lease, fingerprint, route, budget, trust-zone, and verifier
  failures;
- pre-mutation snapshot ordering;
- target-scoped Tier A clean, suspect, and violation scenarios;
- prohibition of audit writes and out-of-scope Executor writes;
- selective epoch invalidation, cycle bounds, and default exclusion of invalid
  premises;
- no secrets, raw request bodies, hidden reasoning, or full prompt content in
  trace serialization;
- cancellation at every safe controller boundary;
- canonical role/slot binding without tier leakage; and
- normal Loop, macro, picker, and Clerk behavior remaining unchanged outside
  an engagement.

### 21.2 Concurrency, filesystem, and lifecycle tests

The release matrix must simulate:

- Lead, Clerk, Obsidian dirty editing, browser reads, index refresh, writer
  mutation, and WAL checkpoint activity together;
- document-scoped lease conflict during an Executor macro;
- unrelated note edits during a protected-target audit;
- host stop while idle, queued, streaming, writer-busy, in Tier A, in Tier B,
  and waiting for a person;
- crash/force-stop with stale connection/lease diagnostics;
- adopted Git/Obsidian trees, junctions, unknown .librarian collisions, files
  moved by Obsidian, and plan-to-apply changes; and
- untrusted input attempting instructions that request writes, secrets, tools,
  routing changes, or promotion.

### 21.3 Controlled model evaluation

Do not deploy policy changes by inferred traffic splitting. Evaluate
route/profile combinations offline and through explicit user-controlled
selection.

The minimum comparative matrix is:

| Variant | Purpose |
| --- | --- |
| Standard single-session | Establish current behavior/cost baseline. |
| Externalized state only | Isolate the benefit of persisted, compact state. |
| State plus Tier A audit | Measure deterministic integrity benefit and overhead. |
| State plus Tier A/B audit | Measure semantic/evidence review benefit and audit cost. |
| State plus audit plus constraint ledger | Measure whether more structure helps or overloads exact route/domain pairs. |

For each variant, test at least:

- exact qualified lead/executor/auditor route combinations;
- an all-open-weight configuration where supported;
- a separate frontier-lead/open-executor hypothesis only as an experiment, not
  an assumed improvement;
- mutation work with authoritative closure;
- partial/human-judgment research work that should remain outside automatic
  completion;
- provider outage, retry, interruption, external edit, and stale-ASK cases;
  and
- low, medium, and high work budgets while keeping native behavior controls
  explicit and constant unless under test.

Release decisions must examine measured benefit, token/cost share, recovery
rate, false-completion interception, user intervention, and route qualification
rather than mean score alone.

## 22. Acceptance criteria

The feature is ready for general opt-in only when all are true:

1. No AuditedEngagement mutation occurs outside the active Core, VaultWriter,
   target lease, and IndexService authority boundaries.
2. An un-auditable task cannot be silently given an authoritative completion
   status.
3. Every started round records its exact roles, routes, adapter ABI,
   expectation/configuration hashes, state epoch, bundle, and non-secret
   outcome evidence.
4. A pre-mutation evidence requirement is durable before the first write.
5. Tier A detects out-of-scope writes, audit writes, stale target state, and
   missing deterministic verification, and blocks completion.
6. Tier B cannot mutate or promote content and never receives raw Executor
   reasoning.
7. A relevant ASK answer or user edit selectively invalidates dependent state;
   stale audit evidence cannot complete a current-epoch requirement.
8. An untrusted input cannot use its content to gain write, execution,
   credential, route, or promotion authority in the same episode.
9. Host stop/restart and Core crash leave an explicit durable state, clean
   lease/index cleanup, and a truthful user-visible recovery status.
10. Existing normal sessions, picker positions, legacy tiers, macros, staging,
    Obsidian editing, and Workbench execution retain their documented behavior.
11. Any graph/context, quality-signal, tool-cap, or audit-skipping optimization
    has a versioned evaluation artifact and may be rolled back.
12. The release documentation distinguishes implemented behavior from planned
    behavior and names the remaining qualification limits.

## 23. Research basis and interpretation limits

This specification was informed by the locally supplied corpus. The following
references support patterns and cautions; they do not independently certify a
Librarian implementation.

| Reference | Design input used | Important limit |
| --- | --- | --- |
| Long horizon harness paper, pp. 4–15 and Appendix B.2 | MEA separation, evidence before mutation, read-only audit, token-share telemetry, selective closure, stale ASK handling. | Cost/score results are benchmark/backbone/task specific; Manager and Auditor shares are measurements, not targets. |
| LLM Planning against Semantic-Execution Drift / expanded ReflectiChain paper | Constraint fidelity, feasibility framing, cognitive-load caution. | Simulator studies and proxy metrics do not prove a universal prompt or embedding threshold. |
| Thought Management System for long-horizon, goal-driven LLM agents | Hierarchical task/persistence ideas. | Its autonomous goal-expansion posture is intentionally not adopted. |
| Advances in LLM-Assisted Combinatorial Optimization | Constraint omission risk and verifier separation. | Formal/solver verification applies only where the artifact has an appropriate verifier. |
| Text-attributed dual-graph paper | Structural plus semantic context fallback, source-location preservation, generic-term caution. | Its own text and Table 4 disagree on a claimed structural-parsing delta; this specification relies on the table's qualitative direction, not the 14.6-point prose claim. |
| STAGE | Bounded context and shallow/deep graph trade-offs. | 512 tokens, graph depths, and memory figures are dataset/hardware parameters. |
| KDRAR | Small candidate sets, compatibility evidence, semantic plus keyword retrieval. | Its 0.7/0.3 weights and top-five result are from APIBENCH-Q API recommendation, not privileged agent-tool proof. |
| Industrial Agentic AI | Soft-sensor/Sense–Infer–Control analogy. | It does not validate Librarian-specific signal formulas or thresholds. |
| AgentAI survey | Interruptibility and modular control-flow direction. | It does not establish a Windows stop-latency guarantee. |
| Homo agenticus and organizational LLM-agent study | Agency loops, interrogation, persistent/shared knowledge artifacts, and traceability. | Organizational/case evidence informs UX hypotheses rather than proving a card layout. |
| Pedagogy-first LLM study | Active comparison/flipped interaction caution against passive answer acceptance. | It does not guarantee higher-order reasoning outcomes. |
| Agentic-AI cybersecurity and age-of-reasoning surveys | Least privilege, zones, validation, oversight, and governed memory direction. | The exact trust-zone and invalidation state machine is Librarian's design choice. |

Before a phase is released, its implementation and experiments MUST update this
section or the linked qualification/release artifact with the actual evidence,
known deviations, and unresolved limits.
