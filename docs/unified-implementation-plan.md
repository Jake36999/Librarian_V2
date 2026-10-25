# Librarian V2 unified implementation plan

**Status:** Living sequencing authority; partially implemented. The progress
log in §19 is the source-backed delivery record.
**Version:** 1.2.1
**Prepared:** 2026-10-24. Amended the same day after source checks of v1.0
and v1.1, including the [blind-spot verification](../reports/2026-10-24-architecture-blindspot-verification.md).
§16 records the v1.1 changes and §17 the v1.2 changes; §18 is the ordered
list of first tasks.
**Scope:** All remaining V2 implementation work identified across the original
remediation plan, the 2026-10-23 system review, the model-adapter work, the
AuditedEngagement specification, the two 2026-10-24 reviews, and current
source inspection.

**Shared references:** [terminology](terminology.md) defines product and
delivery terms used here. The [regression manifest](regression-manifest.md)
records the checkout, command, fixture class, and expected invariant for each
work packet.

## 1. Executive decision

Librarian V2 does not need another broad architecture phase. It needs a
disciplined delivery sequence that closes the known runtime and configuration
boundaries before adding new control-plane abstractions.

The implementation order is:

~~~text
trustworthy baseline
  -> Core lifecycle and state P0s
  -> canonical route and configuration truth
  -> parallel prerequisites:
       safe existing-directory adoption
       real model request shaping and durable route evidence
  -> session-based long-horizon state and Tier A verification
  -> evidence-gated Tier B, trust propagation, and derived graph work
  -> release qualification and Windows acceptance
~~~

The plan deliberately changes the earlier direction in four places:

1. **AuditedEngagement reuses Session infrastructure.** It becomes a bounded
   Session purpose with typed events and a Core-owned append path. It does not
   create a competing event store, replay system, or generic orchestration
   framework.
2. **Model adapters become real protocol adapters before more registry
   infrastructure is added.** Rendering and parsing move behind trusted
   first-party adapters. Declarative expectation records select reviewed enums;
   they never carry templates or executable prompt logic.
3. **Research work is first-class even when it cannot auto-complete.**
   Externalized state, resumability, staged partial closure, and Tier A
   integrity land before authoritative closure or a costly LLM audit.
4. **Old “complete” claims are corrected before release work proceeds.**
   Existing systems may be implemented, partial, planned, or externally
   blocked. A design document alone is never completion evidence.

This document supersedes the sequencing portions of:

- docs/release-implementation-queue.md;
- the recommended order in reports/2026-10-23-system-attention-deployment-and-runtime-review.md;
- Phases A–F of docs/audited-engagement-harness.md; and
- Phases A–E of docs/model-invocation-architecture.md.

Those documents remain the detailed requirements sources. Their status headers
and cross-links were reconciled by BASE-03; later task-specific changes must
keep them consistent with this plan and the regression manifest.

## 2. Evidence, current baseline, and planning rules

### 2.1 Evidence at plan creation (2026-10-24)

This table is the source-inspection baseline that informed the plan. It is not
the live delivery status; consult §19 and the regression manifest for later
implementation evidence.

| Area | Current evidence | Planning consequence |
| --- | --- | --- |
| Host process liveness | host.py, coordination.py, and cli.py still use os.kill(pid, 0). On Windows (Python 3.11.3) it reports an **exited** child as alive while a handle to it is held, so stop waits the full 15 s. The skip in the real-child test is **not** sandbox PID virtualisation. Under the repository venv, `.venv\Scripts\python.exe` is a redirector that starts the base interpreter as a child: Popen PID 1748 vs Core PID 38624, measured on the owner's host. The guard `_child_pid_is_reliable` therefore skips exactly the launch path `Librarian.bat` and the Host use. With the base interpreter the test runs and fails (`test_host_lifecycle.py:95`). | Release blocker. The lifecycle test must exercise the venv-redirector launch path rather than skip it (CORE-02). It can be closed on the owner's Windows host today. |
| Test provenance | Bare system Python imports D:\Resource-Library\.v2. The repository virtual environment imports D:\Librarian_V2\src. | Only repository-venv or source-identity-checked results are valid release evidence. |
| SQLite ownership | IndexService and routed helpers exist, but 41 current direct engine_for calls remain in tool-serving paths. | Add a targeted AST guard, migrate callers in bounded batches, then stress test. Do not claim one-owner SQLite until all serving paths are covered. |
| Route truth | Profiles constrain legacy tiers but do not bind roles to an exact route. Readiness is not per role, unknown tool support is coerced to false, and lead selection can replace Scribe/Clerk positions. | Close configuration truth before growing route qualifications or assigning long-horizon roles. |
| Adapter pack hardening | Per-record hashing, strict recursive pack validation, visible load status, and unique synthetic call IDs are already present in the current working tree. | Preserve and test this work; do not schedule duplicate repairs. |
| Adapter behavior | Providers still render and parse all requests. Usage, request metadata, and reasoning continuation are dropped. Clerk and OCR retain bypass transports. | The next adapter work must change real request/render/parse behavior while preserving legacy fixtures. |
| Session foundation | session.py supplies append-only hash-chained replay, phases, budgets, and questions, but appends outside VaultWriter. | Reuse its event/replay model after introducing a Core-owned session-event append seam. |
| Adoption | Create/Adopt/Attach and a content-root contract do not exist yet. | Do not feed arbitrary existing document trees into model/harness context as if they were Librarian notes. |
| MCP server process | `mcp_server.serve` opens the vault in the stdio process with no writer, IndexService, document leases, or vault lease (`mcp_server.py:217-231`). With no writer, `Registry.call` runs `invoke()` directly (`registry.py:360-366`). The Cowork/Claude Code plugin launches this process (`plugin/.mcp.json`). The CLI already proxies to the active Core and refuses a direct fallback (`cli.py:39-91`). | Contract violation (`adapter-contract.md`: MCP "must not open vault SQLite files directly or bypass the writer queue"). MCP writes also skip Obsidian dirty-note protection. **P0, CORE-04.** |
| Writer preconditions | `VaultWriter` enforces a compare-and-swap precondition (`coordination.py:582-594`), but no caller in `src/` passes one. | After a document lease's quiet window, or for edits made without the plugin, an agent's read-modify-write silently overwrites human edits. **CORE-05.** |
| Interrupted writes | The writer records each operation before mutating and again after, but nothing reconciles start-only records at startup. | Multi-target operations (for example promotion) can be left half-applied without notice. **CORE-06.** |
| Shutdown and walk streaming | Turns already run on a background thread, with sequence-stamped SSE, `?since=` replay, client reconnect, and cooperative cancel. But `close_runtime` never cancels the active turn (`app.py:384-400`). Cancel cannot interrupt an in-flight provider call (up to the host timeout, default 120 s). Replay is an in-memory 500-event buffer (`app.py:97`). | Covered by CORE-02, CORE-07, and ADAPT-04. Do not rebuild the job/streaming model. |
| External-edit detection | `VaultWatcher` already polls `(mtime_ns, size)` of all visible Markdown every 0.35 s and treats deletions as edits; `Index.refresh()` re-reads changed files on every routed read. | Scope the watcher before large adopted trees (DEPLOY-02); feed external edits to sessions (HARNESS-02). |
| Tool surface and prompt cost | App turns are bundled (at most 12 tools; the helper uses `HELPER_TOOLS`). A bare `Loop` without `use_tool_bundles` offers all 130 tools (16,921 schema tokens). A first bundled turn is about 1,358 system-prompt tokens plus 1,241 schema tokens. History is already compacted: the last 6 results go whole, older ones are cut to 700 characters. | Make bundles the default and add handles for oversized results (ADAPT-11). Cache-stable ordering (ADAPT-09). |
| Service transports | OCR (`ocr.py:59-61`) and `api:local` embeddings (`embed.py:101-137`) use their own transports and bypass `HostLimiter`. STT and TTS are DeepInfra-only. | ADAPT-06. |
| Reasoning replay | DeepSeek's thinking-mode documentation requires `reasoning_content` to be passed back after a tool call (HTTP 400 otherwise); `providers.py` always drops it. DeepSeek V4.1 Flash is a reviewed lead route. | ADAPT-01 and ADAPT-07 test this route first. |
| Verified local regression | The repository venv ran test_host_lifecycle.py, test_model_invocation.py, and test_qualification_jobs.py: 33 passed, 1 skipped, and the skip is the launcher issue above. A full-suite run on the owner's host (base interpreter with `PYTHONPATH=src`) gave 891 passed, 1 skipped, 1 failed (Host stop). | A narrow baseline, not a release sign-off. BASE-05 records the full suite under the repository venv. |

### 2.2 Planning-status vocabulary

Every planned or existing item must have exactly one delivery status:

| Status | Meaning |
| --- | --- |
| implemented | Source code and focused deterministic tests exist. It may still need system or release evidence. |
| partial | Some code exists, but a stated invariant, integration path, or acceptance test is missing. |
| planned | Specification or review exists; no accepted implementation is claimed. |
| blocked externally | Completion needs approved provider budget, protected signing material, or a real target environment. |
| retired | Explicitly not part of V2. |

The words ready, qualified, verified, and complete retain their existing
product meanings and must not be substituted for these delivery statuses.

### 2.3 Non-negotiable delivery rules

- Run every test through the repository virtual environment or an explicit
  source-identity guard. Bare pytest is not release evidence.
- Do not reset, discard, or overwrite the existing dirty worktree. First
  inventory and separate the service/adapter foundation from subsequent work.
- Do not commit pre-existing or other-contributor changes merely to make a
  baseline. Prepare reviewable commit groups, then commit only groups whose
  ownership and maintainer approval are explicit.
- Every task has one bounded behavior change, explicit files/ownership,
  deterministic tests, a documentation/status update where needed, and an
  independently reviewed result.
- No task may silently broaden a role, route, tool, write root, vault access,
  provider parameter, or model-failover authority.
- A model-proposed code change is not accepted until a deterministic regression
  suite and a different reviewer validate it.
- Work that needs a provider call is budgeted and opt-in. L0 fixtures must
  cover the normal development loop.
- A task can be split further if its changed files cross more than one
  authority boundary or if its tests cannot state a single failure mode.

## 3. Task sizing and delegation model

### 3.1 Task sizes

| Size | Intended scope | Typical completion evidence |
| --- | --- | --- |
| Small | One isolated behavior, normally one to three modules plus focused tests. | A regression test reproduces the old fault and proves the new behavior. |
| Medium | One coherent boundary change, normally three to ten modules, migration/test fixtures, and one documentation update. | Unit, integration, compatibility, and failure-path tests demonstrate the boundary. |
| Experimental medium | A medium task with an explicit measurement or kill criterion. | A recorded comparison determines whether it advances, remains opt-in, or is removed. |

No task below is intentionally larger than medium. If it grows beyond that
definition, it must be split before implementation.

### 3.2 Candidate development delegation lanes

These assignments concern development work packets, not Librarian runtime role
selection. They are hypotheses about useful specialization, not claims that any
listed route is already qualified for every product role.

| Lane | Candidate primary | Independent reviewer | Best-fit work |
| --- | --- | --- | --- |
| Core and state | zai-org/GLM-5.3 | Qwen/Qwen3.5-397B-A17B | Cross-file Core refactors, route bindings, session integration, lifecycle and test design. |
| Protocol and model behavior | deepseek-ai/DeepSeek-V4-Pro | zai-org/GLM-5.3 | Adapter render/parse, continuation behavior, protocol fixtures, route evidence, and DeepSeek-specific expectation review. |
| Adoption and corpus safety | Qwen/Qwen3.5-397B-A17B | zai-org/GLM-5.3 | Create/Adopt/Attach, workspace-document indexing, dedupe fixtures, structural context, and UX/state documentation. |
| Cross-cutting review | Rotate the non-primary model | Human maintainer | Diff review, test-gap review, source/documentation consistency, and regression interpretation. |

DeepSeek-V4-Pro MUST NOT be the sole authority for DeepSeek-specific behavior.
Its changes require provider documentation, deterministic fixtures, and a
different reviewer. The same independence rule applies to every listed model.

**Execution environment.** A delegated or sandboxed agent may not be able to
run the Windows lifecycle path. Any task that touches `host.py`,
`coordination.py`, `connection.py`, `cli.py`, `mcp_server.py`, or the writer is
accepted only after the full suite has run under the repository venv on the
owner's Windows host, with the real-child Host test executing rather than
skipped.

### 3.3 Work-packet contract

Every delegated packet must specify:

~~~text
task ID and one-sentence objective
allowed files and forbidden files
existing behavior to preserve
exact test command using the repository virtual environment
expected failure before the patch
acceptance tests after the patch
documentation/status consequence
primary model, reviewer model, and human merge owner
provider/network budget, if any
~~~

Agents must not bundle unrelated refactors, reformat unrelated files, edit
release records, publish artifacts, use user credentials, or change model
assignments without a task-specific checkpoint.

## 4. Critical-path gates

~~~text
G0  Baseline is attributable and documentation is honest.
G1  Core lifecycle, single-Core vault access for every client (Browser,
    Obsidian, CLI, MCP), write preconditions, and SQLite ownership are enforced.
G2  Route/slot selection is canonical and UI truth matches runtime truth.
G3  Existing documentation roots can be safely adopted or attached.
G4  Adapter requests are shaped by trusted code and route evidence is durable.
G5  Session-backed externalized long-horizon state and Tier A work correctly.
G6  Optional Tier B, trust propagation, and derived graph work clear evidence gates.
G7  Frozen source passes release, Windows, adapter, and rollback acceptance.
~~~

| Gate | Blocks | Does not block |
| --- | --- | --- |
| G0 | Any claim based on an ambiguous checkout or undocumented worktree state. | Read-only design/review work. |
| G1 | Mutation-capable harness work, stable desktop release, and multi-client claims. | Isolated adapter fixture work with no vault mutation. |
| G2 | Role-specific qualification, cohort growth, accurate model picker behavior, and harness role mapping. | Transport-neutral adapter metadata work. |
| G3 | Using adopted external documents as writable/harness context. | Existing Librarian-vault research. |
| G4 | Enabling model-specific behavior or making reliability claims beyond L0/basic L1. | Conservative provider-default use. |
| G5 | Default Tier B audit, authoritative long-horizon completion, and policy learning from harness results. | Standard research and staged partial work. |
| G6 | Stable release claims for optional advanced features. | Release of a conservative Core if those features remain explicitly unavailable. |
| G7 | Publication. | Internal development and approved evaluation. |

## 5. Wave 0 — establish an attributable baseline

BASE-01 and BASE-02 establish the attributable execution baseline and must
finish before behavior-changing work starts. BASE-03 through BASE-05 may run
in parallel with an explicitly isolated behavior task after BASE-02; they must
finish before their respective documentation, static-guard, or release gates.

| ID | Size | Scope and deliverable | Dependencies | Candidate lane | Done only when |
| --- | --- | --- | --- | --- | --- |
| BASE-01 | Small | Inventory the dirty worktree. Separate the existing service/STT/adapter foundation into coherent reviewable change groups without resetting or losing any user work. | None | Core and state | A manifest lists each changed/new file, intended feature, owner, tests, and whether it is baseline or later work. Reviewable commit groups are prepared; a pre-existing group is committed only with explicit ownership and maintainer approval. This includes the 2026-10-24 pack-hardening and synthetic-ID fixes and the four review reports. |
| BASE-02 | Small | Add a source-identity preflight to developer/test paths and Doctor. It reports executable path, imported package path, repository root, and rejects or warns on the stale sibling checkout. | BASE-01 | Core and state | The repository venv succeeds, and its redirector-to-base-interpreter launch is recognised as the repository interpreter. A fixture that imports the stale `D:\Resource-Library\.v2` checkout is detected with an actionable message. |
| BASE-03 | Small | Reconcile implementation-status headers and sequencing references in the release queue, adapter docs, registry docs, and harness spec. Add links to this plan. | BASE-01 | Adoption and corpus safety | Every affected document uses the status vocabulary from section 2.2 and no document says all V2 implementation is complete. |
| BASE-04 | Small | Define one shared vocabulary table for roles, slots, qualification levels, behavior states, work budgets, session outcomes, execution outcomes, and audit outcomes. | BASE-03 | Core and state | The table is referenced by implementation docs; ambiguous terms such as Helper, screened, and round are removed or defined. |
| BASE-05 | Small | Create a task-level regression manifest that records command, environment identity, fixture category, and expected state for every later task. | BASE-02 | Core and state | CI/local documentation runs the same commands; a review can identify which checkout produced each result. |

## 6. Wave 1 — close the Core runtime and configuration blockers

### 6.1 Host lifecycle and process identity

| ID | Size | Scope and deliverable | Dependencies | Candidate lane | Done only when |
| --- | --- | --- | --- | --- | --- |
| CORE-01 | Medium | Introduce one platform-aware process-identity helper and persist a process-instance identity with every connection/lease record. On Windows it checks an opened process handle/creation-time identity rather than `os.kill(pid, 0)`; on other supported systems it uses safe platform behavior. Replace duplicated liveness logic in host.py, coordination.py, and cli.py. | BASE-02 | Core and state | Unit tests cover live, exited-but-handle-held, inaccessible, reused-PID, invalid PID, and a stale record whose PID was recycled. No production liveness check calls `os.kill(pid, 0)` directly. The published Core PID remains the connection record's authority, including through the venv redirector. |
| CORE-02A | Medium | Add an explicit Host shutdown phase record: admission closed, active chat turns and queued actions cancelled/parked, writer drained, index closed, lease released, process exited or forced. `close_runtime` must stop admitting work and park state before closing shared resources; today it only flushes the writer (`app.py:384-400`). Preserve the existing published-Core-PID adoption and replace `_child_pid_is_reliable` so the real-child test runs under the repository venv redirector. Until ADAPT-04B makes provider calls abortable, report the provider-active stop bound as the host timeout rather than promising a figure. | CORE-01 | Core and state | Tests cover idle, provider-active, writer-busy, queued action, force-stop, and stale lease cleanup. The real-child test executes under the repository venv redirector and passes on the owner's Windows host. |
| CORE-03 | Medium | Define a Context-owned, Core-owned session-event append sink. Migrate session append callers in loop, broker, app, intake, pace, staging, and session tools while retaining an explicit offline/direct compatibility mode for non-Core tooling. The sink preserves session hash chaining and sends Core events through writer authority. | CORE-01 | Core and state | Existing session replay and hash verification remain byte-compatible for migrated fixtures; concurrent event/write ordering and direct-mode compatibility are tested. |
| CORE-02B | Small | Add a durable interruption checkpoint after the session-event sink exists. Define a folded parked/interrupted Session state, append it through CORE-03 before drain, and expose a resume action. | CORE-02A, CORE-03 | Core and state | An interrupted active session reopens as parked/interrupted with its last committed work intact; no synthetic event is ignored by `Session.apply()`. |
| CORE-04A | Medium | **MCP constrained Core RPC.** `mcp_server.py` never constructs a Vault, Registry, SQLite connection, writer, or read-only direct mode. It discovers a compatible live Core using CORE-01 identity and proxies every vault operation through a dedicated authenticated Core RPC that preserves `caller_kind=mcp`, constrained tier/role, connection session, and broker authority. It must not reuse `/api/tool/<name>` or `cli._call_active_core`, which represents a human `curate` call. If no Core is available, it returns `CORE_REQUIRED` rather than falling back to direct vault access. | CORE-01, CORE-02A | Core and state | With a running Core, MCP writes go through the Core writer, honour an Obsidian dirty-note lease, and produce a write-conflict checkpoint. A curate-only tool attempted through MCP is refused. A recorded-but-unreachable Core and absent Core both refuse safely. Cowork session, phase, and budget behaviour is unchanged. |
| CORE-04B | Medium | **Managed MCP bootstrap.** Add the optional no-Core path only through the same Host/Core bootstrap used by the desktop product, wait for its published compatible connection record, then use CORE-04A's constrained RPC. It never starts a second mutable owner and never exposes direct state access. | CORE-04A, CORE-02B | Core and state | MCP starts or attaches one coordinated Core, then proxies; startup failure leaves no lease/process orphan and returns an actionable refusal. |
| CORE-05A | Medium | Define `WriteIntent` target resolution and opaque revision tokens for replace-existing writes. A token is bound to vault, canonical target, caller/session, and observed fingerprint; it is never a raw fingerprint or transferable handle. Inventory promotion/staging paths and declare their actual write targets before claiming CAS coverage. | CORE-03 | Core and state | Every selected replace-existing write schema accepts only its appropriate revision token; new-file writes remain token-free; unresolved/multi-target operations are explicitly refused or declared before mutation. |
| CORE-05B | Medium | **Revision preconditions.** Apply CORE-05A's resolved targets and revision tokens to `edit_note`, `write_note`, `update_project`, and the selected promotion paths, passing preconditions to `VaultWriter.submit(...)`. A stale revision or watcher-observed external edit creates a write-conflict checkpoint instead of overwriting. | CORE-05A | Core and state | An external edit between read and write raises `PreconditionChangedError` and creates a conflict checkpoint. New-file writes are unaffected; source-reading tokens cannot authorize an unrelated Markdown write. |
| CORE-06 | Small | **Interrupted-operation reconciliation.** After acquiring the vault lease and before mutation admission, scan the writer's operation log for start records without a finish record. Use an idempotent dedicated recovery checkpoint/disposition keyed by operation ID, caller, and target set; record empty-target cases. Nothing is auto-repaired. | CORE-02B, CORE-05A | Core and state | A crash fixture between multi-target steps produces one stable non-mutating recovery checkpoint on next start, not a new duplicate on every restart. |
| CORE-07 | Small | **Epoch-aware stream resynchronization.** Keep the Hub deliberately ephemeral. When `?since=` is before the retained window or belongs to a prior Core epoch, `/api/events` emits `resync_required` with the current epoch and canonical session/state snapshot or reattach instructions; it does not pretend session logs reproduce arbitrary global SSE events. | CORE-03 | Core and state | A reconnect after 600 events and one after a restart receives one deterministic resync signal and can restore the current state without duplicate tool/action execution. |

CORE-03 is intentionally early because both durable adapter tracing and
AuditedEngagement need it. It does not yet introduce an AuditedEngagement
purpose.

### 6.2 SQLite ownership

| ID | Size | Scope and deliverable | Dependencies | Candidate lane | Done only when |
| --- | --- | --- | --- | --- | --- |
| INDEX-01 | Small | Add an AST/static architecture test with a narrow documented allowlist. It rejects direct Index or engine_for construction in Core-serving tool paths outside IndexService compatibility code. | BASE-05 | Core and state | The test identifies the current direct callers and prevents newly introduced ones without blocking legitimate offline/migration code. |
| INDEX-02 | Medium | Migrate the first behaviorally coherent batch of direct engine_for callers to with_engine or with_index, keeping transaction and error behavior unchanged. | INDEX-01 | Core and state | The batch's unit and integration tests pass; no call in the selected modules remains on the allowlist. |
| INDEX-03 | Medium | Migrate the next bounded batch of serving tools, selected by shared target domain rather than line count. Most remaining callers hand an Engine to a domain function that also calls the clerk or the network (`taxonomy.propose`, `scout.sweep`, `ranking.benchmark`). Such calls can neither run whole on the index worker nor take the engine out of it, so first add an engine proxy that runs each engine call on the IndexService worker. Never use `with_engine(ctx, lambda e: e)`. | INDEX-02 | Core and state | The AST allowlist shrinks and the selected workflows preserve output/approval semantics. |
| INDEX-04 | Medium | Migrate remaining serving paths, remove the runtime direct fallback where Core is active, and document any intentionally offline-only exceptions. | INDEX-03 | Core and state | The static guard is green with no serving-path exceptions; offline tooling has an explicit non-Core mode. |
| INDEX-05 | Medium | Add Windows-oriented concurrent read/write/WAL stress fixtures for browser, Obsidian, Cowork, agent, refresh, checkpoint, and writer activity. | INDEX-04, CORE-02 | Core and state | No SQLITE_BUSY, cross-thread use, lost write, or false lease state occurs under repeated stress; checkpoints occur only through IndexService. |

### 6.3 Canonical roles, routes, and picker truth

Quick user-visible correctness fixes should land before the larger binding
migration. They must preserve the existing three-position UX.

| ID | Size | Scope and deliverable | Dependencies | Candidate lane | Done only when |
| --- | --- | --- | --- | --- | --- |
| ROUTE-01 | Small | Change lead selection to patch only the Lead assignment. Preserve Scribe and Clerk assignments and legacy tier order. | BASE-02 | Core and state | Migrate → choose a lead → save → reopen retains all three positions. |
| ROUTE-02 | Small | Normalize seeded-host aliases once at the host-registry boundary and render capability state as supported, unsupported, or unknown. | ROUTE-01 | Core and state | A migrated preset route remains visibly selected; unknown tool support is selectable as experimental rather than rendered false. |
| ROUTE-03 | Medium | Add a canonical vault-scoped RoleRouteBinding: role/slot → host → exact model → expectation record → adapter → qualification. Legacy tiers become a read/write compatibility projection. | ROUTE-01, ROUTE-02 | Core and state | Lead, Scribe, Clerk, research_helper, OCR, TTS, STT, and embeddings resolve one canonical binding; no path chooses an unrelated tier secretly. |
| ROUTE-04 | Medium | Make readiness, model tiles, selection APIs, migration, and save/reopen behavior role-specific and binding-driven. | ROUTE-03 | Core and state | Evidence qualified for Clerk never qualifies Lead; changing one slot cannot erase another; custom OpenAI-compatible host behavior is explicit per service slot. |
| ROUTE-05 | Small | Add cross-role route/qualification regression fixtures and a UI/API snapshot for the three-position picker plus service slots. | ROUTE-04 | Core and state | Tests prove selected role is the route that actually executes and that all readiness labels match the active binding. |

## 7. Wave 2 — make adapters change real requests safely

This wave may start transport-neutral work after G0, but it must not enable a
route-native behavior until G2 and the corresponding continuation probe pass.

### 7.1 Transport metadata and durable evidence

| ID | Size | Scope and deliverable | Dependencies | Candidate lane | Done only when |
| --- | --- | --- | --- | --- | --- |
| ADAPT-01 | Medium | Extend the neutral provider reply/envelope without breaking Provider.chat callers. Preserve observed model, finish reason, safe usage, request ID where available, and an ephemeral reasoning-continuation field. Detect "empty content with `finish_reason=length`" as a typed output-budget failure rather than an empty answer. | BASE-05 | Protocol and model behavior | Existing provider fixtures remain compatible; metadata is redacted. A fixture following DeepSeek's thinking-mode rule replays `reasoning_content` after a tool call, drops it on a non-tool turn, and never persists it. |
| ADAPT-02 | Small | Add a per-call observed-model identity verdict: matched, absent, mismatched, or not-applicable. | ADAPT-01, ROUTE-03 | Protocol and model behavior | A mismatch is a typed compatibility outcome, traceable and policy-gated rather than merely logged. |
| ADAPT-03 | Medium | Persist redacted model_request and model_response session events through CORE-03. Record plan/configuration hashes, route, adapter ABI, timing, retry/failure class, and available usage; exclude raw payloads, prompts, keys, and hidden reasoning. | CORE-03, ADAPT-01 | Protocol and model behavior | A resumed session contains durable non-secret route evidence and no sensitive sentinel leaks in serialization tests. |

### 7.2 Trusted render/parse adapters

| ID | Size | Scope and deliverable | Dependencies | Candidate lane | Done only when |
| --- | --- | --- | --- | --- | --- |
| ADAPT-04 | Medium | Extract OpenAI-compatible rendering/parsing from providers.py into a trusted OpenAIChatAdapter while leaving transport/authentication in Provider. | ADAPT-01 | Protocol and model behavior | Golden fixtures prove byte-identical request bodies and normalized replies for all current supported calls. |
| ADAPT-04B | Small | **Cancellable transport.** The provider transport accepts the turn's cancel event and honours it during a request (streaming, or bounded read timeouts with retry inside the deadline), so CORE-02A can stop a provider-active turn promptly. | ADAPT-04 | Protocol and model behavior | A cancel during a slow fake response returns a typed `cancelled` result within the stated bound; normal calls keep their current timeout semantics. |
| ADAPT-05 | Medium | Extract the Anthropic equivalent into AnthropicMessagesAdapter with the same legacy-compatibility standard. | ADAPT-04 | Protocol and model behavior | Existing Anthropic fixtures are byte-identical where semantics are unchanged; errors remain typed. |
| ADAPT-06 | Medium | Route Clerk chat and OCR chat calls through the invocation/transport boundary; remove the production runtime-is-none bypass while retaining explicit test fakes. OCR and `api:local` embedding calls also go through the per-host `HostLimiter`. A host can be marked `local`, so a background `embed.sync()` yields to an interactive turn on the same machine. | ADAPT-04, ADAPT-05, ROUTE-03 | Protocol and model behavior | A static test rejects direct chat-completions or embeddings URL construction outside approved transports; Clerk/OCR preserve their structured-output repair semantics; a local-host fixture shows chat, OCR, and embedding calls sharing one concurrency limit. |
| ADAPT-07 | Small | Extend L1 into a two-step tool continuation probe: tool proposal → tool result → final answer. Include model-identity result, tool-call ID uniqueness, and required replay behavior. The first budgeted run covers the two reviewed DeepInfra routes and records whether each returns `reasoning_content` in a tool loop. | ADAPT-01, ADAPT-04, ROUTE-04 | Protocol and model behavior | A route cannot become screened for tool work on a one-shot tool proposal alone. Both reviewed routes have a recorded continuation result. |

### 7.3 Dialect vocabulary and prompt boundary

| ID | Size | Scope and deliverable | Dependencies | Candidate lane | Done only when |
| --- | --- | --- | --- | --- | --- |
| ADAPT-08 | Medium | Implement dialect vocabulary v1 as first-party interpreted enums: reasoning replay policy, output headroom, tool-call-in-content detection, tool-schema compatibility, tool-result ID/shape constraints, and reviewed sampling profile. | ADAPT-04 through ADAPT-07 | Protocol and model behavior | Packs contain only strict declarative values; unsupported values fail closed; the two reviewed routes retain provider-default behavior until their exact expectation record and probe permit a change. |
| ADAPT-09 | Medium | Refactor prompt assembly into a stable provider-cacheable prefix plus volatile per-turn state. Move vault-derived and retrieved quotations out of the system instruction channel into clearly delimited lower-priority context. | ADAPT-04, ROUTE-04 | Protocol and model behavior | Prompt-injection fixtures prove retrieved text cannot act as a system instruction; cache/input-token and behavior measurements are recorded before a route-specific layout is enabled. |
| ADAPT-10 | Medium | Build an expectation-record authoring flow through existing staging: source/model card → proposed declarative record → human review → pack update. | ADAPT-08 | Adoption and corpus safety | Model-card claims remain provenance-linked, no executable/template field can enter a pack, and a rejected draft changes no route behavior. |
| ADAPT-11 | Small | **Tool surface default and oversized results.** `Loop` uses tool bundles by default, so a caller that forgets `use_tool_bundles` cannot expose the full 130-tool registry. Tool results above a size threshold (`read_source_file`, `get_note`, `search`) return a bounded projection plus a content-addressed handle for the full text, instead of up to 16,000 characters held for 6 steps. | ADAPT-09 | Protocol and model behavior | A bare-`Loop` fixture offers no more than the bundle cap. A 50,000-character read produces a bounded result whose full text stays retrievable by handle. Existing history-compaction tests still pass, and prompt-token measurements are recorded before and after. |

ADAPT-10 intentionally defers signed/sharded global pack distribution. The
current Core artifact is the controlled distribution boundary until there is a
real multi-deployment update need.

## 8. Wave 3 — existing-directory deployment and corpus safety

The first objective is safe adoption and searchable documents, not a knowledge
graph.

| ID | Size | Scope and deliverable | Dependencies | Candidate lane | Done only when |
| --- | --- | --- | --- | --- | --- |
| DEPLOY-01 | Medium | Implement a read-only Create / Adopt / Attach survey. Report canonical root identity, case rules, existing .librarian collision, Git/Obsidian presence, content/exclusion candidates, symlinks/junctions, Markdown file count (used to budget the watcher), and survey fingerprint. | BASE-04, INDEX-04 | Adoption and corpus safety | Survey itself writes nothing; unrelated .librarian is a hard stop rather than a reuse target. |
| DEPLOY-02 | Medium | Add compare-and-apply adoption with a versioned content-root manifest and CAS survey fingerprint. Default Adopt creates operational state only; Attach remains root read-only. `VaultWatcher` is scoped to the approved document roots, honours the manifest's excludes, and backs off on large trees; today it scans every visible Markdown file every 0.35 s. | DEPLOY-01, CORE-02 | Adoption and corpus safety | A changed tree invalidates the plan; adopted docs remain byte-identical except explicitly approved state files; no user documents are hidden beneath .librarian; a 20,000-file fixture tree keeps watcher CPU within a recorded budget while still detecting edits and deletions. |
| DEPLOY-03 | Small | Give unfrontmattered Markdown within an adopted root the virtual workspace_document identity and a dedicated search scope. | DEPLOY-02, INDEX-04 | Adoption and corpus safety | Existing project documentation is searchable to eligible agents without frontmatter rewrites or accidental source-shape assignment. |
| DEPLOY-04 | Medium | Implement dedupe layers one through four: canonical path/file identity, byte hash, normalized text hash, and logical external identity. | DEPLOY-02, DEPLOY-03 | Adoption and corpus safety | Obsidian move/rename retains document identity; exact and formatting-only duplicates are explainable; no automatic merge/delete occurs. |
| DEPLOY-05 | Medium, deferred | Add a disposable structural heading/block/link index and shallow explainable context fallback. | DEPLOY-04, G4 | Adoption and corpus safety | Malformed documents fall back to ordered blocks; derived edges never rewrite Markdown; evaluation proves value before graph-depth or semantic enrichment work begins. |

Near-duplicate LSH, community/centrality work, learned context selection, and
automatic semantic graph enrichment remain deferred until DEPLOY-05 has an
evidence-backed need.

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

## 10. Wave 5 — product integration and release readiness

This wave verifies completed V2 capabilities together rather than starting new
features.

| ID | Size | Scope and deliverable | Dependencies | Candidate lane | Done only when |
| --- | --- | --- | --- | --- | --- |
| ACCEPT-01 | Medium | Build end-to-end acceptance fixtures for research intake, evidence/staging/promotion, V1 import, profiles/bundles/macros/checkpoints, Browser/Obsidian/Cowork lifecycle, service slots, Workbench execution labeling, and manual ranking. | G1 through G4 | Cross-cutting review | Each workflow has success, refusal, recovery, and no-mutation-on-failure coverage. |
| ACCEPT-02 | Medium | Run a fresh Windows acceptance pass on the repository artifact, including Host lifecycle, Obsidian dirty documents, two-client coordination, adopted roots, Docker and honest non-Docker fallback. | ACCEPT-01, CORE-02, DEPLOY-04 | Adoption and corpus safety | Results are stored with OS/Obsidian/Docker versions and include a successful rollback rehearsal. |
| ACCEPT-03 | Small | Reconcile capability matrix and V1/V2 parity report from actual passing acceptance evidence. Mark feature drops, temporary exclusions, and explicitly deferred V3 work. | ACCEPT-01 | Cross-cutting review | Product documentation no longer implies parity where only a design or partial integration exists. |
| RELEASE-01 | Small | Refresh the release queue so R0–R5 begin only after G0–G5 are satisfied. Preserve its external approval requirements and add source-identity/lifecycle gates. | BASE-03, ACCEPT-03 | Core and state | R0 no longer assumes the V2 implementation is complete. |
| RELEASE-02 | Medium, blocked externally | Execute R0 freeze, R1 lock/wheelhouse, and R2 role/route qualification only against a frozen revision and approved credentials/budgets. | RELEASE-01, G5 | Cross-cutting review | L0–L3 evidence, exact route/adapter fingerprints, cost record, and expiry are retained. |
| RELEASE-03 | Medium, blocked externally | Execute R3 signed artifact build, R4 real Windows/adapter acceptance, and R5 manual publication/rollback cadence. | RELEASE-02, ACCEPT-02 | Cross-cutting review | Signed artifacts, verification, rollback, operator documentation, and release-owner approval exist. |

## 11. Parallelism and merge discipline

The following work may run concurrently once prerequisites are met:

| Parallel lane | May run together | Must not overlap in files or authority |
| --- | --- | --- |
| Core lifecycle | CORE-01/02 and INDEX-01 design/test preparation | host/coordination/cli changes must have one owner. |
| Client boundary | CORE-04 (MCP) after CORE-01; CORE-05 after CORE-03 | CORE-04 shares the `cli.py`/`connection.py` helper with CORE-01, so same owner. CORE-05 touches write tools that INDEX-02..04 also migrate, so coordinate batches by module. |
| Picker quick fixes | ROUTE-01/02 | Do not run simultaneously with ROUTE-03 migration in app.py/UI binding code. |
| Adapter metadata | ADAPT-01 | It can run while Index migration proceeds, but not concurrently with broad provider renderer extraction. |
| Adoption survey design | DEPLOY-01 test/design work | Apply/index integration waits for IndexService ownership migration. |
| Harness design correction | HARNESS-01/02 | Runtime code begins only after CORE-03 and ROUTE-04. |
| Release acceptance fixtures | Fixture planning only | Live release testing waits for applicable gates. |

Each merged task must leave the shared tree green for its declared test subset.
A later task may not depend on uncommitted, undocumented behavior from another
lane. Medium changes should be merged as isolated commits only after their
reviewer and acceptance tests pass.

## 12. Explicit deferrals and scope limits

The following items are not on the critical path and must not delay the
preceding gates:

- third-party plugin marketplace, publisher PKI, third-party UI runtime, and
  arbitrary executable plugins;
- global signed/sharded/compressed expectation-pack distribution before the
  Core-bundled pack and staging authoring flow demonstrate a need;
- automatic traffic canaries, automatic ranking adoption, or automatic model
  switching;
- a generic behavior-tree framework or a second engagement event store;
- Tier B as a default auditor before the comparative evaluation passes;
- semantic graph enrichment, community/centrality analysis, near-duplicate
  automatic merging, or learned graph-token selection;
- provider-native reasoning controls for a route that lacks a reviewed
  expectation record and two-step continuation evidence;
- claims of Docker isolation for non-Docker host execution;
- release qualification based only on model cards, one-shot probes, or a
  provider's catalog tile.

## 13. Decision gates for optional work

### 13.1 Tier B audit go/no-go

Before HARNESS-08 starts, the owner records the fixtures, target failure modes,
budget, and the exact benefit/cost margin. The experiment compares:

~~~text
state only
state plus Tier A
state plus Tier A and Tier B
~~~

Tier B remains non-default if it does not show a material improvement in
predeclared false-completion or user-correction measures without an
unacceptable cost, latency, or interference increase. It must never become an
authority for promotion or a substitute for human judgment.

### 13.2 Per-model behavior enablement

A dialect change is enabled for one exact route only when all are true:

1. An expectation record cites a reviewed provider/model source and exact
   route assumptions.
2. Trusted first-party adapter code interprets its declarative enum.
3. L0 render/parse fixtures pass.
4. L1 passes the two-step continuation probe, including observed-model
   identity and tool-result replay behavior where relevant.
5. The route's qualification evidence records the adapter/configuration
   fingerprint and the user can see the applied behavior.
6. A failure falls back to a checkpoint or provider default; it never silently
   switches routes or native controls.

### 13.3 Existing-directory adoption

Adopt or Attach becomes generally available only after a byte-preservation
fixture proves that a Git/Obsidian documentation tree remains intact, an
unrelated .librarian collision halts safely, and workspace_document search
works without frontmatter injection.

## 14. Definition of done for the plan

The unified plan is complete only when:

1. This document is linked from the existing planning documents and their
   obsolete sequencing statements are replaced with status-accurate language.
2. Every task has a living owner, status, dependency, test command, and merge
   evidence in the task tracker or release record.
3. G0 through G5 are objectively green before optional advanced work is
   described as implemented.
4. All user-visible configuration states describe the exact host/model/role
   that will execute.
5. Existing project documents can be adopted or attached without alteration or
   Obsidian invisibility.
6. At least one reviewed route genuinely uses a model-specific, tested adapter
   behavior rather than only an observability wrapper.
7. Long-horizon research work can safely persist and resume partial state
   without a duplicate log or false semantic completion.
8. Any stable release claim is backed by frozen artifact, Windows, adapter,
   provider-qualification, and rollback evidence.

## 15. Source reconciliation record

This plan synthesizes, but does not blindly adopt, the following inputs:

- The original V1/V2 remediation plan and its compatibility invariants.
- The 2026-10-20 executive, model/deployment, and capability-parity reviews.
- The 2026-10-23 system attention, deployment, and runtime review.
- The model-expectation, model-invocation, and service-adapter work already
  present in the working tree.
- The AuditedEngagement specification and its supplied research-corpus caveats.
- reports/2026-10-24-chatgpt-transcript-review.md.
- reports/2026-10-24-harness-and-adapter-plan-review.md.
- reports/2026-10-24-architecture-blindspot-verification.md (added in v1.1).
- The current-source verification recorded in section 2.1.

Review recommendations were treated as evidence to reconcile, not instructions
to copy verbatim. In particular, this plan does not duplicate adapter-pack
repairs already present, does not build a second Session store, does not assign
Clerk a mutation-capable Executor role, and does not assume a cheaper Executor
is a cost saving.

## 16. Changes in v1.1

v1.0's structure, gates, vocabulary, sizing, role mapping, and Session-reuse
decision are kept. v1.1 adds or corrects only the following. Each item is
backed by a source reference in §2.1 or the blind-spot verification report.

| Change | Where | Why |
| --- | --- | --- |
| Corrected the Host-test diagnosis: the skip is the venv redirector, the production launch path, not sandbox PID virtualisation | §2.1, CORE-02 | Measured Popen PID 1748 vs Core PID 38624 under `.venv`. Skipping hides the configuration users run. |
| Added the MCP proxy-or-lease task | §2.1, G1, CORE-04, §11 | `mcp_server` writes beside the Core, against the adapter contract, and bypasses Obsidian dirty-note protection. v1.0 had no task for it. |
| Added read-fingerprint write preconditions | §2.1, G1, CORE-05 | The writer's compare-and-swap exists but is never used; stale reads overwrite human edits. |
| Added interrupted-operation reconciliation | §2.1, CORE-06 | Start-only operation records are never surfaced. |
| Added durable event replay | §2.1, CORE-07 | The replay buffer is 500 in-memory events. |
| Shutdown must cancel and checkpoint the active turn; stop latency is bounded honestly | CORE-02 | `close_runtime` only flushes the writer. |
| Abortable provider transport | ADAPT-04 | Cancel cannot interrupt an in-flight provider call today. |
| Empty-reply output-budget failure; DeepSeek reasoning-replay fixture | ADAPT-01 | Reasoning tokens can exhaust `max_tokens`; DeepSeek documents mandatory replay after tool calls. |
| First continuation probe on the two reviewed routes | ADAPT-07 | DeepSeek V4.1 Flash is reviewed, but its replay behaviour is unrecorded. |
| Service transports share the host limiter, with a `local` host class | ADAPT-06 | OCR and `api:local` embeddings bypass `HostLimiter`. |
| Bundles by default; oversized-result handles | ADAPT-11 | A bare `Loop` exposes 130 tools (16,921 tokens); the recent-result window can reach about 24k tokens. |
| Watcher scoped to adopted roots | DEPLOY-01, DEPLOY-02 | A whole-vault poll every 0.35 s will not scale to large docs trees. |
| `external_edit` session event | HARNESS-02 | Epoch invalidation needs this input; the watcher already detects edits. |
| Composition closure | HARNESS-05 | Per-call checks alone can allow a prohibited two-step outcome. |
| Closure per research grain, using existing verifiers; checkpoint initiation | HARNESS-06 | Moves research value into Tier A with exact predicates. Agency evidence favours letting the person initiate. |
| Execution-environment acceptance rule | §3.2 | Lifecycle work must be proven where the redirector path runs. |
| Baseline committed in groups | BASE-01 | The uncommitted tree holds the adapter foundation and the 2026-10-24 fixes. |

Deliberately **not** added, after the source check:

- **A new background-job model.** Turns are already background threads with
  SSE replay and cancel.
- **A new intent log.** The writer's operation log is one; it lacks only
  reconciliation (CORE-06).
- **A new local-compute semaphore abstraction.** The existing per-host limiter
  is extended instead (ADAPT-06).
- **A tool-schema compaction programme.** Schemas are about 1,240 tokens per
  bundled turn. ADAPT-09's cache-stable prefix and ADAPT-11 address the larger
  costs.

## 17. Changes in v1.2

v1.2 (ChatGPT) splits several v1.1 tasks after a source check. v1.2.1
(Claude) completes the cut-off edit: §17–§18 and the ADAPT-04B row. The
references to v1.1's §16–§17 in §16 still describe v1.1.

| Change | Where | Why |
| --- | --- | --- |
| MCP uses a dedicated constrained Core RPC, not `/api/tool/<name>`; no Core means `CORE_REQUIRED`, never direct access | CORE-04A | `/api/tool` calls `person_call`: `curate` tier, `caller_kind="person"`, broker removed (`app.py:1928-1938`). Reusing it would escalate an MCP agent. v1.1's suggestion to reuse `cli._call_active_core` was wrong. |
| An optional no-Core MCP start goes through the Host bootstrap | CORE-04B | One mutable owner, started the same way as the desktop product. |
| Shutdown split into resource ordering and a durable interrupted state | CORE-02A, CORE-02B | The interrupted checkpoint needs the session-event sink (CORE-03) first. |
| The session-event sink migrates every existing append caller, keeping an offline mode | CORE-03 | Session events are appended from loop, broker, app, intake, pace, staging, and tools. |
| Write preconditions use opaque revision tokens bound to target and caller, with target resolution first | CORE-05A, CORE-05B | A raw fingerprint is transferable; multi-target and promotion writes must declare targets before CAS coverage is claimed. |
| Reconciliation is idempotent and runs before mutation admission | CORE-06 | A start-only record must not create a new checkpoint on every restart. |
| SSE gaps get a `resync_required` signal instead of replay | CORE-07 | Hub events are global, not only session events, so the session log cannot reproduce them. |
| PID-reuse protection persists a process-instance identity | CORE-01 | A recycled PID must not read as a live Core. |
| Cancellable transport split out | ADAPT-04B | It is referenced by CORE-02A and is a separate, small change. |

## 18. Start here: the first tasks in order

Each item follows the work-packet contract (§3.3) and the execution-environment
rule (§3.2). Items on the same line may run in parallel. Each must not touch
another's files.

1. **BASE-01 → BASE-02.** Inventory and commit the baseline in groups on a work
   branch. Add the source-identity preflight, which must recognise the venv
   redirector as the repository interpreter, not as a stale checkout.
2. **CORE-01**, with **ROUTE-01** in parallel. One Windows-safe
   process-identity helper. Lead selection that patches only the Lead slot.
3. **CORE-02A.** Shutdown phases and ordering; make the real-child test run
   under the venv redirector and pass on the owner's host.
4. **CORE-03 → CORE-02B**, with **ROUTE-02** in parallel. The writer-owned
   session-event sink, then the durable interrupted state; alias
   normalisation and tri-state capability display.
5. **CORE-04A**, with **INDEX-01** in parallel. MCP through a constrained Core
   RPC; the static SQLite-ownership guard.
6. **CORE-05A → CORE-05B**, with **ADAPT-01** in parallel. Revision tokens and
   preconditions; reply metadata, usage, reasoning continuation, and typed
   output-budget failure.
7. **CORE-06 and CORE-07**, then **INDEX-02..04** in module batches coordinated
   with CORE-05B, then **ROUTE-03 → ROUTE-05**. CORE-04B follows CORE-02B
   when a managed MCP start is wanted.

G1 is green only when steps 1–6, CORE-06, and INDEX-04 are merged with their
acceptance tests passing on the owner's Windows host.

## 19. Progress log

Branch `v2-unified-plan`. Each row is merged only after its tests pass under
the repository venv on the owner's Windows host. Delegated work is recorded
with its primary model and reviewer (§3.2).

| Task | Status | Commit | Evidence and notes |
| --- | --- | --- | --- |
| BASE-01 | implemented | `ad02715`, `f213fc6`, `1fd49c3` | Baseline in three groups; [manifest](../reports/2026-10-24-baseline-manifest.md). Found and fixed: ChatGPT's UI changes existed only in the built bundle, not in `ui/src`. |
| BASE-02 | implemented | `a467710` | `doctor` source-identity check; the test run refuses a stale checkout. |
| ROUTE-01 | implemented | `77315cc` | `POST /api/lead` keeps positions 2–3. Reviewed by Qwen3.5: no defects. |
| CORE-01 | implemented | `f014b2f` | `process_identity`; **the real-child Host stop test passes**. Drafted with GLM-5.3, reviewed by Qwen3.5 (one finding fixed: a recycled own-PID lease row skipped the stale-lease safeguard). |
| CORE-02A | implemented | `1a8adf6`, `4cfc6eb` | Shutdown phases; the real-child test runs under the venv redirector. Reviewed by GLM-5.3 (admission race and post-lease write fixed). Also fixed a pre-existing hang: the App never stopped the MCP manager it created, so a failing test with an App hung pytest at exit. |
| CORE-03 | implemented | `4873894` | Session appends, rewinds and branches go through the Core writer; direct mode kept offline. |
| ROUTE-02 | implemented (display) | `7a48f0c` | Tri-state tool support; seeded-host aliases compared as one in the tile. Server-side identity rewrite moved to ROUTE-03, because lead overrides are keyed by host id. |
| CORE-02B | implemented | `3015bc2` | A thread cut off by a stop is parked with an "interrupted" note; `resume_session` continues it. |
| INDEX-01 | implemented | `557126c` | AST guard; the debt list only shrinks. |
| INDEX-02 (batch 1) | partial | `8ccce9b` | 4 call sites migrated (43 → 39). Drafted with DeepSeek-V4-Pro and narrowed in review; see INDEX-03 for the engine proxy the rest need. |
| (found) writer wait | superseded | `6b02142` → `8a34cc7` | Pre-existing, reproduced on master: in a coordinated Core a question asked inside a writer operation held the writer, so the person's answer queued behind it until the 600 s timeout. `6b02142` served the queue during the wait, which broke linearity (review P1, below). `8a34cc7` replaces it: the question is recorded inside the operation and waited on after it. |
| CORE-04A | implemented | `d177d55` | `mcp_server` holds no vault state and forwards every call to `POST /api/mcp/call`. The Core runs it as an agent: tier capped at `contribute`, broker kept, `caller_kind="mcp"`, questions returned rather than awaited. No, stopped, unreachable or non-loopback Core gives `CORE_REQUIRED`. Security review by DeepSeek-V4-Pro: its token/origin concern was already covered by `do_POST`'s checks and is now pinned by a test; its session concern is not an escalation, because `resume_session` already attaches any session. |

| (review) four P1 gaps | implemented | `8a34cc7` | From ChatGPT's 2026-10-24 review of this branch; each finding was reproduced in code before it was fixed. **Session bypass:** without an attached writer a session write is direct only offline (this process holds the lease, or no live Core does); after this process's Core stopped, or beside another process's live lease row, it is refused with `CORE_REQUIRED`. **Writer linearity:** no operation waits for a person; `_ask` registers its waiter, records the question, and the registry finishes the wait after the writer returns (`PERSON_WAIT`); an ask nested in a macro leaves its question open. **Late work at shutdown:** person and MCP calls are admitted and counted under the admission lock and drained within the grace; waiters and the broker are terminal after a stop. **PID reuse:** the identity is exact (raw Windows FILETIME; Linux boot id and start ticks), and the Host start path that used the PID alone now passes it. Reviewed by GLM-5.3 and Qwen3.5: one finding fixed (a stop dropped an answer delivered just before it); a remaining offline-writer race is documented in `SessionStore._through_core`. |
| CORE-05A | implemented | `119ded6` | `revisions.py`: a `WriteIntent` (targets, the note it replaces, files that must still be missing) resolved and canonicalised before the broker asks, and opaque HMAC-signed revision tokens bound to vault, canonical path, session, caller kind and fingerprint. `get_note` issues one for the exact bytes it read; each write returns the next, minted inside the writer operation. Agent and MCP callers must bring one to replace an existing note (`REVISION_REQUIRED`); one issued for anything else is refused (`REVISION_REFUSED`); a person's own action needs none. Inventory below. |
| CORE-05B | implemented | `119ded6` | `edit_note`, `write_note(mode="replace")` and `update_project` pass their revision as the writer's precondition; an edit made since the read raises `PreconditionChangedError` and becomes a `write_conflict` checkpoint, offline too. `archive_note` and `promote_offering` declare their targets. Reviewed by DeepSeek-V4-Pro: one finding fixed (a replace on a note missing at resolution needed no revision, so a note another write made in between was replaced unread; it now carries a still-missing precondition). |
| ADAPT-01 | implemented | `48b61a8` | Provider replies now preserve only safe observed-model metadata, usage/request IDs where present, finish reason, and ephemeral reasoning continuation for a live tool-result continuation. The metadata is redacted before tracing or persistence; an empty `length` reply is a typed output-budget failure. |
| CORE-06 | implemented | `c264b9a` | Core startup scans the writer log before admitting mutation, creates an idempotent recovery checkpoint for a start-only operation, handles a partial crash tail safely, and fails closed on a malformed complete record. |
| CORE-07 | implemented | `5708c39` | The Hub stamps events with a Core epoch and authoritative sequence/timestamp. A stale/missing epoch, expired replay, or cursor ahead emits one `resync_required`; the browser refreshes canonical state rather than replaying an action. |
| INDEX-03 (batch 1) | partial | `2e95158` | A callback-only `IndexGateway` keeps SQLite-owned objects inside `IndexService`; intake, queued intake, taxonomy proposal, Scout sweep, and ranking compare/benchmark now release the index worker before Clerk/network/durable-file phases. Static debt shrank 39 → 33. Core-backed regression cases cover the gateway, admission order, Clerk release, proposal, sweep, comparison, and benchmark persistence. |
| ROUTE-03A | implemented | `b6ef33b` | Strict vault-scoped `agents/routes.json`, one-time legacy migration, explicit inheritance, preserved independently selected positions, and serialized picker/service metadata updates. Focused migration/App/service tests: 60 passed; store tests: 8 passed at that commit. |
| ROUTE-03B / ROUTE-05 (chat) | partial | `14837a2` | Chat, background Clerk/Scribe, and helper execution resolve canonical bindings; default profiles and custom profiles can explicitly choose a route slot. Host endpoint changes refuse execution; an unavailable background role queues instead of blocking Lead or borrowing another route. Role-store validation, restart projection repair, temporary offline mutation leases, and role-specific qualification regressions included. Full suite: 1,016 passed, 2 skipped, 1 deselected. Service dispatch and per-role picker readiness remain open. |
| BASE-02 (browser smoke) | implemented | `c6d189e` | Browser smoke now launches the repository venv/source tree, strips inherited real credentials from the scripted demo, waits for completed picker writes, and terminates its own Windows process tree. Previously it could exercise the stale editable checkout. The refreshed current-policy demo passes the complete browser smoke walk. |
| ROUTE-03C / ROUTE-04/05 (routing) | implemented | `4e56ca7` | Services dispatch canonical bindings, share hosted concurrency with chat, and reject stale/late routes. Picker readiness is per role; custom OCR/embedding hosts are explicit. Transport extraction/cancellation remains ADAPT-06. |
| INDEX-03 (authoring/Session batch) | partial | `86941d3` | 16 direct construction sites migrated; debt 33 → 17. Real-Core fixtures cover writer/index separation, schema refresh and a full offering walk. Other serving-path families and WAL stress remain open. |
| Macro writer-wait follow-up | implemented | `5b3be1f` | Macro orchestration runs outside the writer; individual mutations and checkpoint creation remain serialized. Ask/Deny/Plan gates are retained; changed plans invalidate old approvals. Automatic macro resume is not claimed. |

**CORE-05 write inventory.** CAS coverage is claimed only where a token is
checked:

| Write | Targets declared | Revision checked | Notes |
| --- | --- | --- | --- |
| `edit_note`, `update_project` | the note | yes | Always replace an existing note. |
| `write_note` | the note | when it replaces | A new note needs none, but must still be missing when the write runs. |
| `archive_note` | the note and its `Archive/` place | no | A move of the librarian's own note; nothing is rewritten in place. |
| `promote_offering` | the `Offerings/` destination | no | Creates only; the staged draft is the librarian's own state under `.librarian/`. |
| `staging_decide` | selected paths | agents/MCP replacing source notes | Revision/import/concept/single-topic paths declare visible targets; all accepts snapshot staged JSON. New-source and mixed/batch topic promotion, plus lens-store ownership, remain partial. See `staging-write-safety.md`. |
| `refile_source`, `views_refresh` | source and generated-view plan | no new caller-read token | Exact dispatch-time bytes/dependencies are prepared before approval and rechecked per write; not a claim of prior caller review. |
| `create_project`, other writers | registry best-effort | no | Unchanged. |

**Behaviour change in CORE-05:** an agent or MCP client must read a note
(`get_note`) before replacing it, and pass back the `revision`; the
refusal says so. Tool cards for the three tools say it too.

**CORE-04A behaviour changes, confirmed by the owner (2026-10-24):** Ask-mode
MCP writes wait for a person in the Librarian window, and MCP sampling is no
longer used for clerk tasks. Options ChatGPT's review raised, not adopted
yet:

- Return a structured `approval_pending` result with a resume token in Ask
  mode, instead of holding the MCP call for up to ten minutes.
- Either build **CORE-04C** (a Core-to-host sampling callback) or show a
  visible "Core clerk required; MCP sampling unavailable" state in the plugin.
- Give `CORE_REQUIRED` a one-click "open or start Librarian for this vault"
  recovery path in the plugin.

**Known limits and follow-ups from the review:**

- The macro permission-wait gap is closed by the continuation below: control
  flow stays outside the writer and each mutation queues separately. Broker
  authority is retained rather than broadening an approved macro into a
  blanket permission grant. Persistent automatic macro resume remains open.
- ROUTE-03/04 service dispatch and per-role picker readiness are implemented
  in the routing continuation below. Dedicated service transports remain;
  their unification/cancellation and local compute scheduling belong to ADAPT-06.
- INDEX-02: commit real-Core context tests for the batch-1 migrations before
  expanding the batch.
- G1 (Core lifecycle) has its known P1s, recovery, and event-resynchronization
  slices implemented. It remains unclosed until INDEX-04 and the planned
  Windows concurrency/WAL stress fixture prove the remaining direct index
  callers cannot bypass ownership.

Full suite under the repository venv after CORE-05: 959 passed, 2 skipped, 1 deselected.
Focused CORE-06/07 and INDEX-03 commands are recorded in the regression manifest; the
full suite was also re-run after INDEX-03. **Next in §18 order:** ROUTE-03–05, then
the remaining INDEX-03/04 batches and adapter request-shaping work.

### Routing continuation, 2026-10-25

The three-position picker and its existing APIs remain the selection workflow.
After the one-time migration, `agents/routes.json` is authoritative for chat
assignments. `app.json` tiers are a compatibility projection: startup repairs
that projection after an interrupted multi-file save; it does not silently
adopt an unrelated later edit as a new route. Use `/api/tiers` or `/api/lead`
to change assignments. Existing corrupt binding stores fail closed and are
never silently regenerated. Model choices remain non-secret and vault-scoped.
Legacy local-server URL overrides are pinned to the corresponding custom Host,
including after clearing/reselecting through the old picker. An explicit host
ID always keeps its identity even when its spelling matches a provider preset.
Historical qualification under a bare provider namespace is not silently
promoted into canonical-host evidence: an affected route may require a matching
probe again. Existing deliberate Lead overrides remain compatibility choices.

Profiles can select an existing slot using `route_policy.binding_role`, exposed
as **Model route slot** in the profile editor. This changes model selection,
not the task role, permissions, budgets, or qualification identity. For example,
an `analyst` task using the Scribe slot still needs analyst evidence; a Lead
profile using that slot must satisfy Lead qualification for that exact model.
Tests cover both cases. A custom profile without an identifiable slot receives
an actionable configuration error rather than a silently chosen model.

Review findings addressed: fractional revision coercion, service-to-chat
inheritance, incomplete direct bindings, loss of an explicit helper assignment,
projection divergence after restart, offline check-then-write ownership races,
Lead pricing applied to other profiles, broken Clerk/Scribe spillover into
Lead, stale background endpoints, and preset aliases missing price cards or
legacy provider allow-lists. These were reviewed by the Codex route-mapping
agent and independently checked against code/tests. The suggestion to make
slot selection change the qualification role was rejected: it would let a
custom task borrow qualification from a different role. No paid provider call
was needed for this packet; no new DeepInfra spend was incurred.

Final verification of `14837a2`: **1,016 passed, 2 skipped, 1 deselected** in
305.20 seconds under the repository venv. The expanded routing/App/profile
group passed **85 tests** during development. `npm.cmd run build` and the full
`npm.cmd run smoke` browser walk passed. The complete final Python output is
retained locally at `tmp/route03-full-2026-10-25-03.log`; the focused and full
commands are recorded in the regression manifest.

### Service routing and readiness continuation, 2026-10-25

Canonical bindings now select OCR, TTS, STT and embedding execution, including
custom OpenAI-compatible OCR/embedding hosts. Native speech stays restricted
to its reviewed DeepInfra API. A selected route uses the host credential
reference and shared HostLimiter, refuses stale/disabled/deleted endpoints,
and discards responses that return after a stop or reassignment. Outstanding
service IO is visible during stop. Legacy vectors migrate once; clearing the
embedding slot cannot silently restore them from the legacy search setting.
Custom embedding representation namespaces include endpoint identity.

Readiness is passive and per task role, with canonical binding errors shown
separately from historical qualification. The existing three-position picker
is retained. Connections adds explicit custom-host OCR/embedding assignment;
service cards do not show chat-role qualification. New fixtures cover
credential references, shared concurrency, stale endpoints, shutdown,
restart, custom host name collisions, and Clerk-vs-Lead evidence separation.
The operator contract is in `docs/role-routing.md`.

Verification: the development full suite passed **1,028 tests, 2 skipped,
1 deselected** in 329.30s. The expanded routing/App group passed **84 tests**;
the final service-specific group passed **38 tests**, including the additional
custom-host/local-encoder collision fixture. UI build and the expanded browser
smoke walk passed. The final combined full run follows the next ownership
batch, so these counts are not a claim that all release gates have closed.
ADAPT-06 is still partial: service
HTTP transports are not extracted/cancellable and local CPU work is not yet
prioritized. INDEX-04/05, staging write intents,
remaining adapter work, deployment adoption/dedupe, and the Session harness
remain open. The macro permission wait is closed in the next continuation.
No new paid provider calls were made.

### Ownership and macro-wait continuation, 2026-10-25

All four authoring and twelve Session direct-index construction sites have
been migrated to callback access. The static serving-path debt falls from
**33 to 17**. Note/project Markdown writes and Session appends remain on the
writer; SQLite work stays on IndexService. Queries return copied ordinary
data, never an Engine, cursor, or connection. Brief drafting, outside search,
claim review and Scribe IO run after their index callbacks return. Project
validation refreshes the content model before using its cached schema.

Real-Core fixtures exercise authoring, task triage, reflection, project edits,
a complete source-to-offering Session walk, and the separation of Clerk IO
from the index worker. A closed index refuses creation before Markdown is
written. The focused expanded suite passed **116 tests**. Final combined
verification of `4e56ca7`, `86941d3` and `5b3be1f` passed **1,039 tests,
2 skipped, 1 deselected** in **338.19s**, using the repository venv with
`-o faulthandler_timeout=60`. The full output is retained locally at
`tmp/ownership-macros-full-2026-10-25-01.log`. The expanded browser smoke walk
passed again against the final runtime. No live/paid provider calls were made.

The macro writer-wait issue is fixed without auto-allowing its contained
tools. `macro_run` orchestrates outside the writer while checkpoint creation
and individual mutations remain serialized. Broker requests cannot hold the
writer, partial work survives a later denial, changed plans require renewed
approval, and external tools cannot become orchestrators. The rationale and
manual-recovery limits are documented in `docs/macro-runtime.md`. This is an
execution-boundary fix, not implementation of AuditedEngagement or automatic
exactly-once resume.

Still open: the remaining 17 index compatibility sites and ownership/WAL
stress gate; staging/promotion multi-target intents and revision handling;
adapter shaping/cancellation/continuation probes; directory adoption/dedupe;
Session-based harness; and integrated release acceptance. The source
promotion helpers mutate several notes and generated views, so their index
migration must be paired with the target inventory rather than wrapping the
whole promotion in an index callback. G1 remains unclosed.

### Selected staging safety continuation, 2026-10-25

Source revision acceptance now declares its destination and consumes the
existing bound revision token for agent/MCP replacement. The Staging view
passes both destination and staged-record review tokens without changing the
Accept workflow. Stale review refuses with a write-conflict checkpoint; form
edits survive until an explicit reload. Legacy explicit person calls remain
compatible, with dispatch-time checks rather than an invented prior read.
Staged-record fingerprints protect the permission/queue interval, including
retargeting; new concept/import targets must not have appeared in that interval.
Sensitive revisions cannot use the old shortcut around sensitivity review.
Staged IDs and embedded identities are validated before file access/acceptance.

Selected acceptance and deep-read lookups now use Core callbacks: file writes
remain on VaultWriter, SQL on IndexService, and Clerk IO outside its callbacks.
Static direct-index debt falls **17 → 14** construction sites. New-source/topic
promotion intentionally retains its compatibility engine until attachment,
concept, topic and generated-index write targets are fully planned. This is
not INDEX-04 completion. The inventory, compatibility choices and remaining
multi-write race limits are in `docs/staging-write-safety.md`.

Focused staging/revision/coordination/ownership verification initially passed
**56 tests**; the expanded combined group with deep-read, recovery and upkeep
passes **122 tests**. UI build and the expanded browser smoke walk passed.
Final full-suite verification of `90b1945` passed **1,060 tests, 2 skipped,
1 deselected** in **349.00s**. No live/paid model calls were made. G1, complete
promotion safety, adapter work, adoption/dedupe, Session harness and integrated
release acceptance remain open.

### Upkeep ownership continuation, 2026-10-25

All five direct-index construction sites in upkeep tools and the model-catalog
status lookup now use Core callbacks. Freshness and revision-pinned repository
file retrieval copy their query results before network requests; duplicate
comparison and provenance checking process copied rows outside the worker.
D/I/K rebuilding snapshots source rows, then writes derived records and staged
revisions on VaultWriter. Legacy domain Engine/connection callers retain their
explicit offline path. No source promotion implementation was wrapped wholesale
in an index callback.

The static debt count falls **14 → 8**. Remaining construction sites are batch
(2), graph/extract compatibility paths (2), catalog adoption (1), staging
new-source/topic promotion (1), and taxonomy refiling/view generation (2).
This count is construction sites, not concurrent connections or a claim of
fully enforced ownership. Separate desk/lens stores and Windows WAL stress
remain INDEX-05 work. Real-Core fixtures reject a second index, trace SQL only
on the Core worker, call back to the index during network/provenance work, and
assert derived writes occur on the writer.

Both slices are committed in `90b1945` on `v2-unified-plan`. Final combined
verification used the repository venv with `-o faulthandler_timeout=60`:
**1,060 passed, 2 skipped, 1 deselected in 349.00s**. The full output is retained
locally at `tmp/staging-upkeep-full-2026-10-25-02.log`. The expanded browser
smoke and TypeScript/bundle build passed against the final code. These are
scripted/deterministic checks, not new hosted-model qualification or stable
release acceptance. Nothing was pushed.

Next is the remaining ownership/promotion inventory and migration, then the
adapter completion tasks in §7. Directory adoption/dedupe and the Session-based
harness remain subsequent gates, not completed features. The source-kind
mutation inventory is in `docs/staging-write-safety.md`.

### Taxonomy and generated-view continuation, 2026-10-25

The two taxonomy direct-index construction sites now use Core callbacks;
static debt is **8 → 6**. `refile_source` and `views_refresh` resolve a bounded
file/dependency inventory before permission approval. Prepared source bytes
remain invocation-local, rather than being re-read and silently substituted
after a wait. Render-only topic/master helpers run on IndexService; visible
file writes remain on VaultWriter. Each write checks the destination,
taxonomy dependency and human lease again. Mid-round conflicts retain completed
work and include its declared paths in checkpoint evidence, even when the
short checkpoint title cannot hold them. No new log/reducer/daemon was added.

Single-item topic acceptance uses the same boundary, including its staged
review token in Settings. Partial acceptance is retained on the existing
staged record and can be explicitly finished after review/restart without
adding the taxonomy row twice. Changed approved wording/row is not trusted;
re-proposing topics cannot replace partially applied person work. Existing
person-only topic authority, ordinary permission modes and the option not to
file sources remain intact. Mixed/multi-item topic accepts and new-source
promotion retain their legacy engine path and remain unfinished.

Settings now surfaces structured rewrite refusals instead of always claiming
success, retains an errored review form until explicit reload, and retires its
old handlers while reload fetches new proposal tokens. Alias cells cannot add
unapproved taxonomy rows; generated filename collisions fail before mutation.
The public control flow and model picker are unchanged. These are backend
metadata plans, not the Session harness or adapter request shaping.

Implementation is committed as `fc58af2`. The expanded focused group passed
**145 tests**; the browser build and expanded smoke walk passed. Final full
verification passed **1,084 tests, 2 skipped, 1 deselected in 345.72s**, using
the repository venv with `-o faulthandler_timeout=60`. The generated output is
retained locally at `tmp/taxonomy-ownership-full-2026-10-25-01.log`.
G1, the six remaining
construction sites, Windows stress, full promotion safety, adapters,
adoption/dedupe, harness and integrated release acceptance remain open. The
mutation inventory and non-atomic/crash limits are recorded in
`docs/staging-write-safety.md`. No live/paid provider call was made.
Nothing was pushed. Next ownership work is the batch validation/readiness
lookups and source/catalog promotion; graph/extract still retain explicit
offline construction branches. Windows stress and runtime fallback enforcement
must follow before claiming the single-owner index gate complete.
