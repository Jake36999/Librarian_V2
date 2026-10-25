# Model Invocation Architecture

**Status:** Partial. Compatibility-first foundation, including ADAPT-01 reply
metadata and ephemeral reasoning continuation, is implemented. Trusted request
shaping and route-specific behaviour remain planned in ADAPT-02–11 of the
[unified implementation plan](unified-implementation-plan.md).
**Version:** 1.0 draft  
**Audience:** Core, UI, Obsidian, Cowork, release, and model-qualification
maintainers

## 1. Decision

Librarian will use a small set of trusted, versioned **protocol adapters** and
a large, declarative, signed **model-expectation registry**.

An adapter is responsible for how an already-authorised request is rendered,
sent, streamed, parsed, and normalised for a provider or local runtime. It is
not responsible for deciding what work an agent should do, what authority it
has, which tools it may use, which peer should help, or whether a human
checkpoint may be bypassed.

This distinction avoids an unmaintainable matrix of:

~~~text
model × task kind × role × collaboration pattern × provider
~~~

Instead, the Core compiles task, role, collaboration, route, and model
expectations into one immutable InvocationPlan. The adapter only translates
that plan.

This specification extends
[Model expectations registry](model-expectations-registry.md). It does not
replace the existing [Browser, Obsidian, and Cowork adapter contract](adapter-contract.md):
that document describes client/UI adapters, while this document uses
“protocol adapter” for the model/provider translation layer.

The implementation boundary, primary-source research, and deliberately
deferred protocol work are recorded in
[Model protocol-adapter requirements](model-adapter-requirements.md). This
document supplies detailed requirements; the unified plan is the sequencing
and delivery-status authority. Terms follow [Librarian terminology](terminology.md).

## 2. Goals and non-goals

### Goals

- Make model behaviour explicit, versioned, reproducible, and explainable.
- Keep protocol/model integration modular without accepting executable model
  plugins or arbitrary model-card text.
- Retain the familiar three-position model chooser while making its positions
  semantic role bindings.
- Support hosted APIs, OpenAI-compatible providers, and local runtimes without
  pretending they share the same controls.
- Preserve Librarian's Core-owned policy, vault, writer, index, approval, and
  session guarantees.
- Allow compact non-secret registry data to move between deployments and
  update globally under user control.
- Turn live validation into confirmation of documented expectations rather
  than blind discovery.

### Non-goals

- A public executable plugin marketplace.
- Automatic model switching, automatic promotion, or autonomous escalation of
  permissions.
- A generic prompt that “turns thinking off” across unrelated models.
- A promise that every discovered provider model is tool-capable or reliable.
- Moving credentials, raw provider payloads, hidden reasoning, or user vault
  content into shared registry packs.

## 3. Architecture

~~~text
TaskContract + RolePolicy + CollaborationPlan
                  + RoleRouteBinding
                  + ModelExpectation
                              |
                              v
                      Contract Resolver
                              |
                              v
                     immutable InvocationPlan
                              |
                              v
                     trusted Protocol Adapter
                              |
                              v
                  Provider API or local runtime
                              |
                              v
                       InvocationResult
                              |
                              v
     Core policy, registry, writer, session trace, and UI state
~~~

| Component | Responsibility | Must not do |
| --- | --- | --- |
| TaskContract | Describe the work and hard capability requirements. | Select a provider or grant authority. |
| RolePolicy | Describe authority, budgets, bundles, qualification floor, and checkpoint policy. | Invent a route or broaden permissions. |
| CollaborationPlan | Describe solo/delegated/review/handoff topology and typed artifacts. | Give workers unrestricted shared state. |
| RoleRouteBinding | Bind a vault role to a host, exact model, expectation record, and approved behaviour mode. | Contain a secret or silently replace another role. |
| ModelExpectation | Declare exact route compatibility, parser/template/tool dialect, controls, provenance, and test requirements. | Establish reliability on its own. |
| Contract Resolver | Intersect the preceding contracts and produce one allowed plan or a structured incompatibility. | Spend, reroute, or relax an unmet requirement. |
| Protocol Adapter | Render, invoke, stream, parse, and normalise one allowed plan. | Make policy, write vault state, execute tools, or delegate. |
| Core Runtime | Own budgets, retries, checkpoints, sessions, tools, state writes, and traces. | Open a second mutable Core or bypass the vault coordinator. |

## 4. Scope and storage ownership

| Layer | Scope | Contents |
| --- | --- | --- |
| Signed Core | Installed application | Trusted protocol adapters, parsers, transport implementations, adapter ABI. |
| Signed expectation pack | Global/per-user non-secret cache | Declarative model expectations, provenance, capability families, adapter references, conformance fixtures. |
| Personal host binding | Per user | Endpoint alias, non-secret host settings, model alias to expectation mapping, key reference. |
| Vault role binding | Per vault | Lead/Scribe/Clerk/Helper route selection, behaviour mode, profile constraints, task policy. |
| Qualification evidence | Local/personal evidence store | L0–L3 artifacts, observed metrics, freshness and invalidation state. |
| Session/walk trace | Per vault/session | Exact plan hash, observed route, tool events, checkpoints, safe outcome metadata. |

Credentials remain in the existing personal key source. They are never copied
into a role binding, expectation pack, lockfile, session trace, or vault.

## 5. Canonical contracts

### 5.1 TaskContract

TaskContract describes what work needs to happen. It is independent of a
provider and independent of whether a route can perform it.

~~~yaml
TaskContract:
  version: task_contract_v1
  id: task_...
  kind: research | writing | extraction | classification | review | service
  interaction: inference | structured_output | tool_loop | tts | stt | ocr
  requirements:
    tool_mode: none | optional | required
    grounding: none | preferred | required
    modalities: [text]
    context_class: short | normal | long
    structured_output: optional_schema_id
  output:
    kind: prose | schema | evidence_packet | draft_packet | review_packet
    schema_id: optional
  constraints:
    token_budget: 12000
    output_budget: 4096
    cost_budget_usd: 0.10
    deadline_seconds: 300
    stop_conditions: [budget, checkpoint, missing_evidence]
~~~

Hard requirements are different from preferences. For example, a
tool-required, grounded research task is incompatible with an inference-only
route; a fast inexpensive route may be preferred but cannot substitute for a
missing hard capability.

### 5.2 RolePolicy

RolePolicy is the model-execution projection of the existing AgentProfile. It
is vault-scoped and may narrow permissions but never expand registry, broker,
session, project, or caller authority.

~~~yaml
RolePolicy:
  id: clerk
  role: clerk
  authority: consult | contribute | curate
  qualification_floor: screened
  allowed_tool_bundles: [read]
  budgets:
    token: 0
    output: 4096
    cost_usd: 0.00
    time_seconds: 0
    concurrency: 4
  retry_policy: none | bounded
  failover_policy: never | ask
  checkpoint_policy: ui
~~~

The initial canonical roles are Lead, Scribe, Clerk, and Research Helper.
Reviewer is a valid future role when a distinct review route is useful.

### 5.3 CollaborationPlan

CollaborationPlan belongs to the Core orchestration layer, not the protocol
adapter. It makes the cooperation topology reviewable before work starts.

~~~yaml
CollaborationPlan:
  version: collaboration_v1
  mode: solo | delegate | parallel | review_then_synthesise | handoff
  coordinator_role: lead
  worker_roles: [research_helper]
  parent_walk_id: optional
  artifact_contract: evidence_packet_v1
  ownership: coordinator_only | bounded_shared_read
  stop_conditions: [budget, checkpoint, missing_evidence]
~~~

Workers receive independent bounded walks and return typed artifacts. They do
not share a writable session, copy a Lead's authority, select their own peers,
or negotiate route changes directly with other models.

### 5.4 RoleRouteBinding

RoleRouteBinding replaces positional tiers as the internal source of truth.
Tier 1–3 remains a visible and API-compatible projection through the 2.x
line.

~~~yaml
RoleRouteBinding:
  version: role_route_binding_v1
  role: lead | scribe | clerk | research_helper
  host_id: preset-deepinfra
  requested_model: provider/exact-model-id
  expectation_ref:
    pack_id: librarian-core-models
    record_hash: sha256:...
  behaviour_mode: provider_default | named_mode
  qualification_floor: screened
  enabled: true
  updated_at: timestamp
~~~

Selecting Lead updates only the Lead binding. It must never silently remove
Scribe or Clerk bindings. The binding contains no API key and never grants a
role more authority than its RolePolicy.

### 5.5 ModelExpectation

ModelExpectation is defined in detail in the
[registry specification](model-expectations-registry.md). At resolution time,
the required subset is:

~~~yaml
ModelExpectation:
  identity:
    provider_model_id: provider/exact-model-id
    endpoint_fingerprint: sha256:...
    upstream_revision: optional
  adapter:
    id: openai_chat_v1
    abi_range: ">=1,<2"
  capabilities:
    tool_use: true | false | unknown
    structured_output: true | false | unknown
    parallel_tool_calls: true | false | unknown
    modalities: [text]
  contract:
    template_or_tool_dialect: provider_native
    parser: openai_tool_calls_v1
    tool_result_policy: standard
  native_controls:
    allowed_behaviour_modes: [provider_default]
  provenance:
    source_hash: sha256:...
    reviewed_at: timestamp
~~~

An unknown capability is not false. It allows an experimental route to be
considered when no hard policy blocks it, but it cannot be presented as a
verified recommendation.

### 5.6 InvocationPlan

InvocationPlan is the immutable, non-secret configuration for one provider
attempt. It is created after all policy, capability, qualification, budget,
and checkpoint checks pass.

~~~yaml
InvocationPlan:
  plan_id: plan_...
  walk_id: walk_...
  parent_plan_id: optional
  task:
    contract_version: task_contract_v1
    kind: research
    interaction: tool_loop
    output_contract: evidence_packet_v1
  actor:
    role: clerk
    authority: consult
  collaboration:
    mode: parallel
    artifact_contract: evidence_packet_v1
  route:
    host_id: preset-deepinfra
    endpoint_fingerprint: sha256:...
    requested_model: provider/exact-model-id
  adapter:
    id: openai_chat_v1
    version: 1.2.0
  expectation:
    record_hash: sha256:...
    behaviour_mode: provider_default
  interaction_contract:
    tool_bundle_id: read
    tool_bundle_version: 3
    tool_schema_hash: sha256:...
    structured_output_schema: optional
    allowed_provider_fields: [model, messages, tools, temperature]
  limits:
    token_budget: 12000
    output_budget: 4096
    deadline_seconds: 300
    retry_policy: bounded
  effective_configuration_hash: sha256:...
~~~

The effective configuration hash includes the endpoint fingerprint, exact
provider model/version, adapter ID/version, template/tool dialect/parser,
expectation record hash, selected behaviour mode, tool schema, and structured
output contract. A provider key is never part of this hash.

### 5.7 InvocationResult

InvocationResult is the normalised, redacted adapter outcome. It does not
contain raw HTTP requests, credentials, hidden reasoning, or unbounded
provider diagnostic payloads.

~~~yaml
InvocationResult:
  plan_id: plan_...
  effective_configuration_hash: sha256:...
  status: completed | tool_calls | structured | failed | cancelled
  requested_model: provider/exact-model-id
  observed_model: optional-provider-return-value
  content: optional-final-content
  tool_calls: optional-normalised-proposals
  structured_output: optional-validated-object
  finish_reason: optional
  conformance:
    model_identity: pass | fail | unknown
    parser: pass | fail
    selected_behaviour: pass | fail | unknown
  timing:
    queue_ms: 0
    provider_round_trip_ms: 0
  usage:
    availability: available | unavailable
    prompt_tokens: optional
    completion_tokens: optional
  retry_count: 0
  provider_request_id: optional-redacted-identifier
  failure:
    class: optional
    retryable: false
    user_detail: optional-safe-message
~~~

## 6. Contract resolution

The resolver uses this sequence for every new invocation and every
tool-result continuation:

1. Validate the TaskContract and resolve the RolePolicy.
2. Build or validate the CollaborationPlan.
3. Load the RoleRouteBinding for the actor role. The resolver does not rank
   unrelated routes as an implicit fallback.
4. Check host existence, enabled state, circuit state, host/profile
   concurrency, and exact requested model.
5. Resolve the referenced ModelExpectation and adapter ABI.
6. Intersect hard task requirements with the expectation's declared and
   adapter-tested capabilities.
7. Check role-specific qualification freshness and any required spend or
   route-override checkpoint.
8. Reserve profile and route budgets before provider work starts.
9. Produce and durably record the InvocationPlan.
10. Send the plan to the selected protocol adapter.

If any check fails, resolution returns a structured compatibility result
instead of silently degrading:

| Failure | Example UI action |
| --- | --- |
| No binding | Assign a route to this role. |
| Host unhealthy | Test/retry host or inspect its health. |
| Model identity mismatch | Refresh discovery or choose/requalify an exact model. |
| Tool mode unsupported | Choose a compatible route or an inference-only task. |
| Behaviour mode unsupported | Use provider default or choose a tested route. |
| Qualification stale | Inspect change and run the needed L0/L1/L2 work. |
| Budget unavailable | Reduce work budget or approve more spend. |
| Checkpoint required | Resolve the affected checkpoint. |

No resolver path may silently swap host, model, adapter, behaviour mode, or
qualification floor. A person-approved route change produces a new plan and a
new effective configuration hash.

## 7. Protocol Adapter ABI

### 7.1 Trust boundary

Protocol adapters are first-party trusted code shipped in the signed Core.
V2 initially supports a deliberately finite family:

~~~text
openai_chat_vN
openai_responses_vN
anthropic_messages_vN
local_transformers_vN
vllm_or_sglang_vN
~~~

An expectation pack may select an adapter ID and a declared mode. It may not
ship executable Python, JavaScript, Jinja templates, parser code, or raw
prompt instructions. An unusual template/parser requires a new signed Core
adapter release, not a dynamic registry download.

### 7.2 Conceptual interface

~~~text
AdapterDescriptor
  id, version, ABI range, supported protocols and capabilities

validate(expectation, task_contract) -> CompatibilityResult
render(invocation_plan) -> ProviderRequest or StreamRequest
invoke(rendered_request, cancellation, deadline) -> ProviderEvents
parse(provider_events, invocation_plan) -> InvocationResult
normalise_usage(provider_events) -> safe usage and timing metadata
conformance_cases(expectation) -> L0 and L1 fixture declarations
normalise_error(exception_or_response) -> typed failure
~~~

The adapter receives a fully authorised plan and a scoped host credential
handle supplied by the Core transport. It must not receive direct vault,
SQLite, Writer, filesystem, registry-tool, or peer-agent capabilities.

### 7.3 Adapter rules

- Render only fields explicitly permitted by the InvocationPlan.
- Reject unknown native controls instead of forwarding provider-shaped guesses.
- Treat returned tool calls as proposals; only the Core can validate and
  execute them.
- Preserve streaming/cancellation boundaries and return a typed partial or
  cancelled result when appropriate.
- Normalise provider errors without exposing secrets or raw payloads.
- Never perform route selection, failover, delegation, promotion, or state
  mutation.
- Run outside the VaultWriter and IndexService workers.

## 8. System runtime expectations

### 8.1 Expectations from the adapter's perspective

The Core guarantees that an adapter receives:

- one immutable InvocationPlan;
- one selected host credential handle, never a persisted token value;
- a deadline and cancellation signal;
- bounded retry instructions;
- a known tool and output contract;
- a stable expectation record and adapter version for the life of a walk.

The adapter guarantees that it returns:

- a request/stream derived only from allowed plan fields;
- normalised content, structured output, or tool-call proposals;
- requested/observed model identity when available;
- classified error and retryability information;
- separate queue, provider, and parsing timing where available;
- redacted usage metadata when the provider supplies it.

### 8.2 Runtime constraints

- Plan compilation and registry lookup must be local, bounded, and must not
  open vault SQLite.
- Registry record loading is lazy; normal selection loads an index plus only
  the records required for selected routes.
- Provider latency has no global numeric guarantee. Librarian measures adapter
  overhead, queue time, provider round trip, retries, cancellation, and
  cleanup separately.
- Host and profile concurrency, circuit breakers, budgets, and retries remain
  Core-owned policy.
- Only bounded transient provider failures retry automatically, normally on
  the same plan and route.
- Parser, schema, observed-model, permission, expectation, and qualification
  failures are not incorrectly retried as transient provider failures.
- A running walk pins its plan. An expectation-pack update cannot alter a
  tool-result continuation in the middle of a walk.

### 8.3 Durable events

The Core records ordered, append-only walk events:

~~~text
walk_started
model_request
model_response
tool_call_requested
tool_call_completed | tool_call_refused
checkpoint_created
walk_paused | walk_completed | walk_failed | walk_cancelled
~~~

Every event carries a walk ID, parent walk ID where relevant, timestamp,
effective configuration hash, and safe metrics. Tool events also carry a
durable call ID, so a resumed walk never replays a completed write.

## 9. Model-walk input/output contract

### 9.1 What a model receives

A model receives only a task-local projection assembled by the Core:

~~~text
role briefing and task objective
explicit task and output contract
allowed tool schemas and exit-condition tools
bounded context or artifact excerpts with provenance
current session phase and compact pending-checkpoint state
budget and stop-condition guidance
the immediately relevant tool results or handoff artifact
~~~

It must never receive credentials, hidden tools, unrestricted vault paths,
internal route-ranking rules, another worker's private prompt, direct state
write handles, or authority to decide promotion or model failover.

### 9.2 Interaction modes

| Mode | Expected model output | Core treatment |
| --- | --- | --- |
| Inference | Final prose or bounded answer. | Validate output constraints; finish or stage as policy requires. |
| Structured output | JSON matching an assigned schema. | Strictly validate; permit only declared bounded repair. |
| Tool loop | One or more exposed tool-call proposals or final answer. | Validate name, arguments, IDs, phase, role, broker, budget, and checkpoints before execution. |
| Service | Typed request/result for TTS, OCR, STT, embeddings, or another bounded service. | No agent tool surface; use service-specific expectation and output contract. |

Malformed tool calls are contract failures. The Core may offer a bounded,
explicit repair turn when the contract permits it; it must never guess an
argument, reinterpret an unknown tool, or execute a malformed write.

### 9.3 Tool loop lifecycle

~~~text
resolve task + role + route
  -> preflight requirements, budget, and qualification
  -> create durable walk record
  -> invoke model
  -> validate normalised response
  -> optional tool proposal
  -> Core policy and tool execution
  -> append result to trace
  -> continue, checkpoint, pause, finish, cancel, or fail
~~~

Normal model turns expose only the selected task-sized ToolBundle, including
exit-condition tools. The intended normal range remains small; an audited
macro is the controlled expansion path. Tool execution always follows
existing registry, broker, session, budget, document-lease, writer, and
approval checks.

### 9.4 Cooperation model

| Mode | Core behaviour | Worker result |
| --- | --- | --- |
| Solo | One role owns one walk. | Final output or typed artifact. |
| Delegate | Coordinator creates bounded child walks. | Evidence packet or other declared artifact. |
| Parallel | Workers investigate independent slices. | Separate typed artifacts with provenance. |
| Review then synthesise | Reviewer receives a draft/artifact; Lead decides next action. | Review packet, never an automatic promotion. |
| Handoff | One role completes an artifact contract for another role. | Bounded handoff artifact. |

Typed artifact contracts initially include:

~~~text
evidence_packet_v1
draft_packet_v1
review_packet_v1
~~~

The Lead/coordinator remains responsible for synthesis, checkpoints, and any
promotion-capable action. A child failure becomes a typed failed artifact; it
does not silently route itself to another model or inherit Lead authority.

### 9.5 Walk completion and recovery

~~~yaml
WalkResult:
  walk_id: walk_...
  status: completed | paused | failed | cancelled
  final_output: optional
  artifact_ref: optional
  checkpoint_ids: []
  observed:
    requested_model: ...
    returned_model: ...
    adapter_id: ...
    effective_configuration_hash: ...
    latency_ms: ...
    usage_availability: available | unavailable
    retries: 0
  trace_ref: durable event reference
  error:
    class: optional
    retryable: false
    detail: safe user-facing explanation
~~~

Failure classes are explicit:

~~~text
unsupported_combination
expectation_mismatch
tool_schema_invalid
tool_refused
provider_transient
provider_terminal
budget_exhausted
checkpoint_pending
context_stale
cancelled
~~~

Resume starts from the last durable event. It must not replay a completed
write, reuse an expired checkpoint, or change a route without a new
person-approved plan.

## 10. UX expectations

### 10.1 Preserve the familiar chooser, change its meaning

The current three visible positions remain, but their product meaning becomes:

| Position | Canonical role | Typical work |
| --- | --- | --- |
| 1 | Lead | Interactive, tool-capable coordination and session work. |
| 2 | Scribe | Drafting, revision, and structured writing. |
| 3 | Clerk | Bounded, read-only evidence and retrieval work. |

The header for any active route must show:

~~~text
Role · host · exact model · behaviour mode · qualification · work budget
~~~

Legacy Tier 1–3 is displayed only as a compatibility mapping through 2.x.
All save, migration, and runtime paths use canonical role bindings.

### 10.2 Host and route setup

The progressive setup flow is:

1. Choose a preset provider or an OpenAI-compatible host.
2. Select a personal key source; never echo a secret.
3. Discover models or enter an exact model ID manually.
4. Test the connection.
5. Optionally run a budgeted L1 identity/tool probe after showing cost and
   expected time.
6. Assign the selected route to exactly one role.

Discovery is a provider listing, not a reliability claim. The UI distinguishes
discovered, unprofiled, declared, adapter-tested, and qualified states.

### 10.3 Four independent status dimensions

Do not collapse distinct facts into one green “reliable” badge:

| Dimension | States |
| --- | --- |
| Host health | Unknown, healthy, impaired, offline. |
| Contract knowledge | Unknown, declared, adapter-tested, deprecated. |
| Qualification | Experimental, screened, verified local, verified release, stale. |
| Task compatibility | Ready, experimental, needs action, incompatible. |

Qualification is role-specific. A Clerk tile must never display Lead evidence.
Unknown tool capability remains visibly unknown; only an explicit unsupported
capability blocks a tool-required Lead assignment.

### 10.4 Work budget and model behaviour

The existing effort control becomes **Work budget**. It controls Librarian
limits:

~~~text
steps · helpers · time · output · review · spend
~~~

The UI shows the effective limit as the minimum of Work budget, profile cap,
host cap, and remaining session budget. It does not claim to change native
provider reasoning or cause more distinct models to answer.

**Model behaviour** is a separate control, displayed only when the selected
expectation record permits it:

| State | User-facing meaning |
| --- | --- |
| Provider default | No known safe native control is being sent. |
| Declared | A source documents a control; the adapter mapping is untested. |
| Adapter-tested | Request and parser handling have passed conformance checks. |
| Qualified | Relevant L2/L3 evidence includes this selected behaviour. |

### 10.5 Preflight, checkpoints, and errors

Before a route change or a paid action, show:

~~~text
Task requirements
Role authority
Selected host and exact model
Model behaviour and source/testing state
Qualification/freshness state
Expected cost and consequences
~~~

Structured checkpoints handle experimental overrides, active-session route
changes, cross-model failover, paid qualification, and unsupported behaviour
overrides. Cancel leaves the current binding unchanged.

| Failure | Safe UI action |
| --- | --- |
| Missing or invalid key | Edit the personal key source. |
| Host unavailable | Retry connection or inspect host health. |
| Model changed at provider | Refresh discovery, then select/requalify an exact route. |
| Native control unsupported | Use provider default or choose a compatible route. |
| Evidence stale | Inspect the change and run the required evaluation. |
| Provider circuit open | Wait/retry or explicitly choose another route. |
| Tool mode unsupported | Choose an inference task or a compatible model. |

No error surface exposes credentials, raw provider payloads, or hidden
reasoning.

### 10.6 Service assignments

TTS, OCR, embeddings, and future STT are service assignments, not Lead/Scribe/
Clerk routes. They reuse host, expectation, evidence, and budget vocabulary,
but expose only relevant service controls. Until an STT implementation and
contract exist, the UI must explicitly say “Not available yet” rather than
implying support through a generic model catalog.

## 11. Registry packs, transfer, and updates

### 11.1 Pack shape

The registry favours readable, content-addressed data over a new runtime
database:

~~~text
manifest.json
  pack_id, pack_version, adapter_abi_range, signing_key_id,
  expiry, record_digests, revocations, compatibility metadata

index.json
  normalised route/model key -> record digest, capability bits, pack shard

records/<sha256>.json.zst
  expectation record, provenance, contract, defaults, test requirements
~~~

The Core loads the compact index at startup, resolves records lazily, and
keeps a small LRU cache. Shared protocol/family/template definitions are
referenced by records instead of copied into every model record. At Librarian's
scale, clarity and predictable updates matter more than premature binary
micro-optimisation.

### 11.2 Update and transfer policy

- Every stable Core ships a signed baseline expectation pack for offline use.
- Downloaded packs live in a per-user cache, not inside a vault.
- An update is staged, signature/hash/ABI/expiry checked, then atomically
  activated with rollback available.
- A pack update may be offered globally but must not silently change an active
  route or a running walk.
- A local declarative override is source-cited and labelled
  local_declared/experimental. It does not overwrite curated evidence.
- Export/import transfers a non-secret lockfile.

~~~text
registry-lock.json
  pack ids and exact hashes
  adapter ABI
  expectation-record hashes
  effective configuration hashes
  optional endpoint aliases
~~~

The lockfile does not contain credentials, document content, prompts, query
history, or raw provider responses. An offline deployment continues with its
last valid baseline/cached pack and shows pack age rather than becoming
unusable.

## 12. Invalidation and qualification

Hard compatibility changes include:

- exact provider model/version or endpoint fingerprint;
- adapter ABI/version;
- tool grammar, template, parser, or structured-output contract;
- native reasoning-control mapping;
- security policy.

They invalidate verified evidence, require L0, and queue L1–L3 work behind
the normal spend policy.

Soft/advisory changes include display text, prices, rankings, friendly
recommendations, and unapproved source-card prose. A changed card hash creates
a review item; it never overwrites the active expectation or changes runtime
behaviour.

Model expectations decide compatibility. L0–L3 evidence decides reliability.
An L1 result proves only its declared low-cost conformance scope. It does not
prove long-run tool loops, collaboration, structured output, or release
qualification.

## 13. Security and safety invariants

- The Core is the only vault mutation authority and the only owner of its
  index/writer state.
- Protocol adapters have no direct Markdown, JSONL, session, staging, SQLite,
  broker, or tool-execution capability.
- Every model tool call is only a proposal until the Core validates it through
  registry, role, session, broker, budget, document-lease, and checkpoint
  gates.
- No raw model-card content becomes a system prompt.
- No automatic route/model/adapter/behaviour fallback occurs.
- Collaboration cannot broaden a worker's permissions.
- No agent automatically starts a paid qualification or a service/workbench
  action that requires human confirmation.
- Every completed walk is attributable to an exact route, expectation record,
  adapter version, tool-bundle version, collaboration mode, and effective
  configuration hash.

## 14. Migration and implementation sequence

### Phase A — data and observability

- Add contract types and plan/result tracing without changing provider
  request behaviour.
- Preserve current legacy tiers and current model picker as compatibility
  input.
- Capture requested/observed model, configuration hash, queue/provider
  timing, retry count, safe usage metadata, and outcome class.

### Phase B — canonical route bindings

- Add per-vault Lead/Scribe/Clerk bindings.
- Make the existing three-position UI patch one role at a time.
- Map legacy tiers to bindings once and retain a visible compatibility view.
- Fix host-ID canonicalisation and role-specific readiness before promoting
  new configuration controls.

### Phase C — protocol adapters and expectation packs

- Define the first-party adapter ABI and signed baseline pack/cache.
- Convert catalog facts into a first cohort of 10–15 reviewed expectation
  records.
- Add L0 fixtures for body construction, tool schema, parsing, continuation,
  and forbidden fields.

### Phase D — controlled native behaviour

- Expose Model behaviour only for expectation records with an adapter-tested
  mapping.
- Require L1 conformance before a new route recommendation.
- Keep current Work budget independent of native reasoning controls.

### Phase E — collaboration and services

- Compile CollaborationPlans into bounded child walks and typed artifacts.
- Add review/handoff artifacts before broad multi-agent autonomous flows.
- Define service bindings independently; do not imply STT availability until
  a real service contract exists.

## 15. Acceptance criteria

### System and adapter

- Every provider request originates from a valid immutable InvocationPlan.
- An adapter cannot write vault state or execute a tool.
- Unsupported task/route/behaviour combinations fail before provider spend.
- A plan is pinned across a tool-result continuation.
- Pack updates, rollbacks, expired packs, invalid signatures, and offline
  operation are covered by deterministic tests.

### UX

- A migrated preset host remains visibly selected after reopen.
- Selecting a custom Lead preserves Scribe and Clerk bindings.
- Every role shows its own qualification state.
- Unknown capability is not rendered as unsupported.
- Work budget never claims to set native reasoning.
- Route changes and paid work show clear consequence/checkpoint controls.

### Model walks

- Models receive only task-local tools, context, and allowed choices.
- Every tool proposal passes Core policy gates before execution.
- Worker artifacts are typed, bounded, provenance-bearing, and read-only to
  sibling workers.
- Resumption never replays completed writes.
- Every result records its exact configuration and safe runtime evidence.
