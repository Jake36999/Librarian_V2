# Librarian terminology

**Status:** Normative vocabulary for V2 documentation and implementation.
The [unified implementation plan](unified-implementation-plan.md) remains the
delivery-status authority.

## Authority and execution

| Term | Meaning | Must not be confused with |
| --- | --- | --- |
| Core | The single mutable authority for one vault: coordinator, writer, index service, leases, session append path, and policy boundary. | A browser, Obsidian adapter, Cowork/MCP process, or CLI client. |
| Registry tier | `consult`, `contribute`, or `curate`: the maximum tool authority of a caller. | A model-picker position, model quality level, or work budget. |
| Role slot | A semantic assignment: `lead`, `scribe`, `clerk`, `research_helper`, `ocr`, `tts`, `stt`, or `embeddings`. | A legacy positional tier. |
| Legacy position | The existing three-picker compatibility projection: Lead, Scribe, Clerk. | The canonical vault-scoped role-to-route assignment. |
| Assign (a model to a role) | Choose the route a role uses. Always revisable; qualification is evidence for that route at that time. **Say "assign", never "bind"** in prose, UI and agent instructions (owner, 2026-11-20): "bind" was read as permanent. The stored record is still `RoleRouteBinding` in code. | A permanent commitment, or a rule for later sessions. |
| Agent tier | 0 = Overseer, an outside agent (Codex, Claude, Antigravity…) working on the owner's behalf, including using Librarian for another project; 1 = Lead; 2 = Clerk; 3 = Scribe. Clerks proofread, check claims, synthesise and direct Scribes; Scribes perform many small reading and writing tasks. See [policy/agent-roles-and-authority.md](policy/agent-roles-and-authority.md). | A registry tier (`consult`/`contribute`/`curate`), trust tier (`gold`/`silver`/`bronze`), or legacy numeric configuration field. |
| Route | One host plus exact provider model, protocol adapter, expectation record, and qualification evidence. | A provider family or catalogue tile. |

## Model evidence and controls

| Term | Meaning | Must not be confused with |
| --- | --- | --- |
| Capability state | `supported`, `unsupported`, or `unknown`. `unknown` means unassessed and may be experimental; it is not `unsupported`. | Qualification. |
| Qualification | `unavailable`, `experimental`, `screened`, `verified_local`, or `verified_release`, based on route- and role-specific evidence. | Evidence freshness. |
| Evidence freshness | `current`, `advisory_stale`, or `hard_invalid`. A hard compatibility dependency invalidates qualification; a soft change produces advisory stale evidence until rechecked. | A route's qualification level. |
| Work budget | Librarian's universal ceiling for time, turns, tools, delegation, output, and spend. | A provider's hidden reasoning or thinking setting. |
| Native behaviour | A route-specific provider control permitted only by a reviewed expectation record and matching qualification evidence. | A generic effort slider or an instruction embedded in a pack. |
| Invocation plan | The immutable, non-secret resolved contract a trusted adapter may render and validate. | Authority to choose a route, invoke a tool, or alter policy. |

## Durable work state

| Term | Meaning | Must not be confused with |
| --- | --- | --- |
| Session state | `open`, `parked`, or `closed`. A parked session has durable partial work and may be resumed; it is not complete. | A provider chat thread or an SSE connection. |
| Execution outcome | A bounded result such as completed, refused, failed, cancelled, interrupted, or needs-person. It describes an attempt. | Audit integrity or semantic closure. |
| Audit integrity | `clean`, `suspect`, or `violation`, determined by a deterministic or approved audit. | Whether a research conclusion is true. |
| Closure state | `open`, `partial`, `verified`, or `human_judgment`. Only exact/bounded deterministic evidence may produce `verified`; synthesis remains human judgment. | Session closure. |
| Checkpoint | A structured, visible decision or conflict record that blocks only its affected operation until resolved or expired. | Silent model policy prose. |
| Audited session | An opt-in Session purpose ("AuditedEngagement") with phases manage → preflight → execute → audit → reduce. Its requirements, contracts and verifier results are typed Session events. | A separate engagement store, log or job system. |
| Session reduction | The deterministic fold of validated Session events that alone changes requirement status. It replays identically from the same event prefix. | A model's declaration that work is done, or a separate reducer component. |
| Tier A audit | Deterministic, target-scoped checks: protected-target diff, schema, citation, quote location, arithmetic, claim run, index. | Tier B, or any LLM judgment. |
| Tier B audit | An experimental, read-only LLM assessment by Clerk. It is non-default until HARNESS-08's go/no-go and never upgrades a partial or human_judgment closure on its own. | Tier A, or human acceptance. |
| Human accepted | A person accepted a specific artifact or interpretation revision. It is recorded with provenance. | `verified` closure, or proof that a claim is true. |

## Composition

Adopted by the owner, 21 November 2026, from [the diagram-workflows proposal](proposals/diagram-workflows.md) (section 12.1). The rules that use these words are in [policy/composition.md](policy/composition.md).

| Term | Meaning | Must not be confused with |
| --- | --- | --- |
| Process | Any one action, workflow, pipeline or sprint. | A run, which executes a pinned copy of a process; or a session. |
| Action | The smallest defined step an agent follows to complete a task, carried out by one registered tool (possibly one bounded model call). | A step, which is one use of an action inside a process. |
| Workflow | A named sequence of actions (and workflows, without a cycle), invoked as one step. | A session, or a pipeline. |
| Pipeline | A sequence of workflows and actions, with routing, concurrency and spend gates. | A sprint, or a batch run. |
| Sprint | A sequence of pipelines toward one Owner objective, with its own success guarantee and budget. Named, not yet built. | A session's phase, or a calendar period. |
| Order | action → workflow → pipeline → sprint. A process is built only from processes earlier in the order, or of its own kind without a cycle; never from a later one. | Any kind of tier. |
| Layer | A process's position in the order: L0 action, L1 workflow, L2 pipeline, L3 sprint. | An agent tier, registry tier, trust tier, or a Tier A/B audit. |
| Component | A process used inside another process. | A step, which is one use of a component at one place. |
| Parent process | The process made when processes are combined: an action's parent process is a workflow, a workflow's a pipeline, a pipeline's a sprint. | The caller of a run (a run has a caller; a process has parents). |
| Definition | The YAML text of a process (`workflows.Definition` in code). | The process itself. |
| Step | One use of a component at one place in a process, with its own id and arguments. | The action it uses. |
| Side effects | What a step can touch, least to most: `none`, `local_read`, `external_read`, `local_write`, `external_write`. Derived from the action's registry spec; a declared class may overstate, never understate. `external` means the action reaches beyond the vault. | A permission, or a registry tier. |
| Acceptance criteria | Conditions on a step's own result (`is`, `in`, `empty`, `at_least`). A result that misses one fails the step. | A test suite, or an oracle's specification. |
| Compensation | A step's declared undo: one registered action. It is shown when a later step fails, and never run automatically. | A retry, or a rollback the runner performs. |
| Manifest | A process's compiled description (JSON): its component tree, its actions in order with their declared properties, a roll-up, and its digest. Generated, never edited. | The process's definition, or a diagram spec. |
| Mandate | What a parent process allows its components: highest tier, effects, outside access, a deny list. | A role's registry tier. |
| Repertoire | The set of accepted processes, shipped and promoted, that new work is composed from. | A library (a vault), or the remedy catalogue. |
| Mount | The subset of the repertoire a role may use. | A role's permissions, or its prompt. |
| Promote (a process) | Add it to the repertoire: validated, accepted by the Owner, digest-pinned. | Promoting an offering into the vault, which is a separate act. |

## Use cases and diagrams

Adopted 21 November 2026 ([diagram-workflows](proposals/diagram-workflows.md), section 12.2).

| Term | Meaning | Must not be confused with |
| --- | --- | --- |
| Use case | An actor's goal and everything that can happen in pursuing it, written in the nine-field template. | A diagram, or a process. |
| Spec (diagram spec) | The behaviour of one use case: lanes, typed nodes, guarded edges and outcomes, represented as `.spec.yaml` in the examples. Specifications belong within the Core; report copies and rendered views are authoring or review artifacts. | A process's definition. Linking the two through `implements: <spec id>` is proposed, not current runtime enforcement. |
| Main success scenario | The numbered happy path: one actor per step, "Actor + verb + object". | A test, or a run. |
| Extension | A path leaving the main success scenario at a numbered step (`13b`), ending with "rejoin at N" or "the use case ends". | A refusal code. An extension id is the *place*; a refusal code is the *shape*. |
| Outcome (of a use case) | `success`, `resolved`, `learned`; neutral `reused` and `used once`; or `paused`, `declined`, `escalated`. | An execution outcome, which describes one attempt. |
| Reference (`ref`) | A node that calls another use case and handles each of its outcomes. | A link, or a wikilink. |
| Lane | A column of an activity diagram holding one actor's steps. | A role slot, or a model. |
| Tier-0 turn | One return of control to tier 0; consecutive tier-0 steps are one turn. Graded: 2 ideal, 3 expected, 4 rusty, 5–10 bad. | A model call, or a chat turn. |

## Review and failure handling

Adopted 21 November 2026 ([diagram-workflows](proposals/diagram-workflows.md), sections 10 and 12.3–12.4). The authority rules are in [policy/agent-roles-and-authority.md](policy/agent-roles-and-authority.md).

| Term | Meaning | Must not be confused with |
| --- | --- | --- |
| Owner | The person who runs the library; the only actor whose decisions are reserved. | Tier 0. |
| Worker | The role doing a task: a Lead, Clerk, Scribe or assigned helper. | The oracle, which judges the task. |
| Oracle | The role that judges a run's output against its specification. It never executes or repairs. It runs Tier A checks before any Tier B review. | The worker, the doctor, or a Tier B audit on its own. |
| Doctor | The role that repairs a failure at a mapped extension point, by a catalogued remedy within its blast radius, then hands back to the oracle. | The oracle, or tier 0. |
| Verdict | The oracle's judgement: a claim with its evidence. It can be rebutted, and is itself re-checked. | A fact, or an instruction to the worker. |
| Symptom | What is observed at an extension point: refusal code, shape, evidence. | The root cause. |
| Root cause | The answer at the end of the "why?" chain. | A proposed solution. |
| Remedy | A workflow in the doctor's catalogue, keyed by use case, extension and symptom, with a declared scope and rejoin. | A one-off fix, or a code change (that escalates). |
| Remedy catalogue | The doctor's accepted remedies and their case history. | The repertoire, or the model catalogue. |
| Blast radius | What a change or a remedy can touch: the union of its actions' declared effects, followed through dependants, lineage and bridges. | A guess. |
| Escalation | A failure handed back to tier 0 unresolved; a counted failure of the use case. | A pause for the Owner's decision. |
| Fault register | A ticket service for failures and misalignments, carrying evidence, existing failure/extension identifiers, tiered flags, the responsible actor, repair history and re-checks. Existing diagnostic labels may be attached; a fixed four-bit mask does not define the service. | A score, confidence, agent tier or permission grant. |
| Fault ticket | One tracked failure or misalignment, assigned according to the existing routing and authority rules until its repair is checked or its required decision is recorded. | A new authority to repair, or proof of resolution from a worker's assertion alone. |

## Delivery status

| Status | Meaning |
| --- | --- |
| implemented | Source code and focused deterministic tests exist; system or release evidence may still be required. |
| partial | Some code exists, but an invariant, integration path, or acceptance test remains missing. |
| planned | A requirement exists but no accepted implementation is claimed. |
| blocked externally | Completion requires a protected credential, signing material, provider budget, or target environment. |
| retired | Explicitly excluded from V2. |

`experimental` and `deferred` are qualifiers, not statuses: each needs an
explicit decision (keep, defer or reject) recorded with its gate.

### Release roles and evidence states (master finalization queue)

| Term | Meaning |
| --- | --- |
| required | The row gates publication (MF-047), always. |
| fix-or-disable | A P1 defect in a shipped capability. It blocks a release only if the capability ships enabled with the defect unfixed; otherwise the capability is disabled or stated as a limitation, through the MF-051 scope record. |
| if-selected | Optional work that gates a release only when MF-051 selects it. |
| outside release | Experiments and decisions that never gate a release; each runs on its own approval. |
| observed | Seen happen, in a real host or a hosted service. |
| source-supported | Shown by the code at a cited line; "re-checked" says when and by whom. |
| process | A documentation, acceptance or decision task with no defect claim. |
| proposal | A design or experiment not yet built. |

Do not use `ready`, `qualified`, `verified`, or `complete` as substitutes for a
delivery status.
