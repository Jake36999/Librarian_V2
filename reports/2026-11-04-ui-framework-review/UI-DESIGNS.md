# Interaction and CSS isolation specifications

2026-11-04 · designs for the [gap matrix](UI-REVIEW.md) at HEAD `40ec923`. These are proposed changes, not implemented features. Use existing `Api`, `App.state`, local component fields and DOM. Never derive authoritative closure, ownership, paid-call settlement or execution containment in the browser.

## D1. Existing-payload projection contract

All requests use current authenticated `Api.get/post/tool`. On refresh replace existing component state from the Core; transient pending flags only prevent duplicate clicks. No frontend store or new backend schema. Name private CSS properties `--lib-*`; do not reuse host theme tokens as writable application state.

| Surface | Existing payload / operation | Projection rule |
|---|---|---|
| Operations summary | `/api/state`: `busy`, `actions`, `vault_lease`, `shutdown`, `active_profile_runs`; `/api/meta.non_secret_health`: `vault_lease`, `lease`, `writer`, `index`, `watcher`, `shutdown` | Separate transport connected from Core/worker health. Render actual reported strings; unknown remains unknown. Do not infer all healthy from HTTP 200 or `index:'ready'`. |
| Editor protection | `/api/documents`: `leases[{path,editor,dirty,expires_in,baseline}]` | Show path, editor and last reported expiry, not an independent lease lock. Baseline behind disclosure; do not expose a release/override action without current person authority. |
| Index diagnostic | person tool `index_status`: notes/chunks/document_chunks/embeddings/unparsed/duplicate_names/built_at/stale | Label “Index snapshot”; never percent complete or rebuild ETA. Calling it may queue behind rebuild; keep shell interactive and allow dismissing the diagnostic. |
| Embeddings/service issues | acceptance result `embedding_warnings[{stage,error,next}]`, `promotion.steps`; note metadata `needs_attention`; `/api/services`; `/api/library.doctor` | Present accepted note and derived-vector failure separately. Model availability, historical test and current job state differ. No live embedding-job count exists. |
| Session lifecycle | `session_status`: audit, completion, predicate_inspector, plan, history, questions; `audit_projection`: requirements, contract, contract_skeleton, stall, recent_events, accounting | Load selected session only; correlate responses with session ID/epoch. Cancel display of old response after switching. Preserve omissions and `fits:false`; never reconstruct dropped events. |
| Reply review | `reply_reviewed`: held/unchecked/challenged/not_extracted/over_limit/status | Advisory comparison to cited notes. No reply ID, exact source revision or checked-span receipt exists yet. Display association as unavailable instead of guessing. |
| Execution | GET `/api/claims/runs`: runs/docker; POST `/api/claims/run {id}`; person tools engagement_plan/engagement_open/engagement_start/engagement_close and returned checkpoints | Claim Run always Docker; Workbench host execution must remain a separate explicit choice. Show current result fields only. Future NAT quarantine receipts are a dependency, not fields to invent. |

For health fetches use `Promise.allSettled`, render individual successes and failures, no serial health gate before loading chat. When mounted and visible, a single bounded refresh timer (e.g. 5s design default) may update meta/documents; stop it on dispose/hidden view, prevent overlapping fetches, refresh on checkpoint/resync and focus. No polling claim of millisecond-accurate state. Manual Refresh always available. Failure leaves “Last reported …; update unavailable”, not a green current status. Never poll model discovery or paid qualification in this timer.

### DOM hierarchy

```html
<div class="librarian-root" data-lib-layout="wide">
  <div class="lib-app">
    <header class="lib-header">…navigation…</header>
    <section class="lib-operations" aria-label="Operations">
      <p role="status" aria-live="polite">…changed summary only…</p>
      <button aria-expanded="false" aria-controls="lib-operations-detail">Operations details</button>
      <div id="lib-operations-detail" hidden>…health, leases, failed actions…</div>
    </section>
    <div class="lib-body">…current view and document pane…</div>
  </div>
  <dialog class="lib-dialog lib-settings" aria-labelledby="lib-settings-title">…</dialog>
</div>
```

The markup is illustrative; instance IDs must be unique, including separate mounts in Obsidian. Summaries persist across Chat/Search/Staging. Healthy detail is collapsed; failure/required-decision count is visible. Use text/status icons as well as colour. Escape closes the innermost owned overlay; it never clears operational faults.

## D2. Action/state truth tables

### Composer, cancellation and retained input

| State / gesture | Request | Visible result / input handling |
|---|---|---|
| idle + nonempty draft + Send/Enter | `/api/chat {text}` once | Keep exact draft/attachment references until admission succeeds; pending Send disabled. |
| admission fails / transport ambiguous | No automatic retry | Retain draft and references. Say rejected if known; say submission outcome unknown on transport loss. Refresh canonical state before proposing resubmission; no exactly-once claim. |
| admission succeeds | No second request | Clear only the submitted snapshot. If user edited while awaiting admission, preserve new edits; never clear a later draft. |
| busy + Enter in composer | None | Keep draft; tell user current reply is active. Do not overload keyboard Send as Cancel. |
| busy + explicit Stop | `/api/chat/cancel {}` once | “Stopping reply…” until stopped/turn_done or refreshed idle state. Retain next draft. |
| cancel rejection/failure | None automatically | Retain active state and show failure, restore Stop enabled. |
| attaching/removing reference | Existing attach and local reference insertion/removal | “Remove reference” removes the message reference; uploaded Inbox file remains. No silent file deletion. |

Separate `submit()` from `cancelReply()` and keep the small pending snapshot within App. UI checks reduce duplicate input; server remains authority. Avoid changing provider behavior or retrying uncertain writes.

### Checkpoints and honest decisions

| Label | Current operation | Must not imply |
|---|---|---|
| Mark reviewed; retry manually | `/api/checkpoints/resolve {id,choice:'retry_after_review'}` | Opening a diff, replaying a write, clearing a dirty lease. Preserve existing explanatory text. |
| Wait | Resolve the declared `wait` choice | Guaranteed automatic retry or a running watcher. Explain “Records wait; inspect the original action.” |
| Cancel decision / Cancel operation | Resolve declared cancel | Cancelling all work or undoing already-applied bytes. Use the scope shown by the Core. |
| Approve execution decision | Resolve approve checkpoint only | Running a command. Existing engagement_start must subsequently be called by a person with matching checkpoint_id. No auto-execution on resolution SSE. |
| Open note to review | `/api/file` + current openNote hook | A byte diff or retry. Keep separate from Mark reviewed. |

Cards show human-readable evidence first: type/scope, path if supplied, reason and consequence; raw JSON in a `details` block. Button default styling follows `row.default`, not array order. Disable a pending decision, retain card on failure, refetch after success. Do not manufacture a path by parsing arbitrary prose.

### Settings, modes, library and model mutations

| Control | Pending / success | Failure / warning |
|---|---|---|
| Permission mode radio | Disable group while POST `/api/mode`; repaint from returned/current state | Restore last confirmed mode, show error; no stuck optimistic radio. Unique radio name per mount. |
| Effort slider | Show proposed level with pending state; confirm via `/api/effort` result | Restore last confirmed level and tooltip; do not imply budget saved. |
| Clear selection | POST `/api/tiers {tiers:[]}`; only then announce cleared | Preserve confirmed assignment and show failure. Do not require right-click. |
| Clear service | POST `/api/services {slot,provider:'',model:''}` | Service stays confirmed until success. Keep service scope distinct from all chat roles. |
| Profile model | `ingest {ref:'model:provider:model'}` | Label “Stage model profile”; not an L1 probe or qualification. |
| Switch library | POST switch, reload on success | 409 offers “Switch; leave work running”. It may finish, fail or wait; disclose timeouts, not guaranteed completion. |
| Forget library | POST forget, refetch on success | Keep row and show rejection; never swallow errors or imply folder deletion. |
| Open in other host | Existing URL/hook | Label “Open library in …”; no promise of carrying draft/session state. |

Role selection uses explicit Lead/Notes/Small tasks focus rather than implicit click order. Continue to POST the current ordered tiers representation; replacement constructs a complete proposed array from the last confirmed tiers. Server override and qualification rules remain unchanged. Clearing middle role must not silently assign a later role to it; either rebuild a valid prefix with an explicit consequence confirmation or retain current clear-all semantics with truthful copy. Slot service picker remains distinct. Touchcancel and movement cancel long-press timers; long press must suppress the subsequent click.

## D3. Audited session oversight

Always render a lifecycle banner **before** the inspector's empty-requirements return. Derive legacy/invalid from `predicate_inspector.legacy/invalid`, `audit.legacy/invalid` or loaded `audit_projection.session.legacy_history/invalid_history`; do not infer from display status alone. Read-only means disable actions that mutate that history and label the scope; plain chat reset remains possible. Empty history can still be read-only.

| Session state | Primary presentation | Allowed next action |
|---|---|---|
| legacy or invalid | “Read-only audit history” and reason; preserve transcript | “Start new audited session” calls existing open_session with purpose audited and explicit question, then attach. No promise to carry authority or verify old content. Fork only if independently proven by backend contract. |
| stale closure | Requirement ID/revision, current status, old statement/result labelled historical | Inspect current file, request evidence, or revise requirement as person. Never turn old pass green. |
| blocked requirement | “Requirement blocked”; show actual reason when present in live tool result | “Revise and reopen requirement”; other requirements may still progress. No “resume whole run” promise. |
| open normal | Compact counts + next action | Expanded details only when selected; stop auto-expanding every unchecked predicate. |
| closed | Outcome and authoritative/person-acceptance distinction | Inspect; use current backend reopening tools deliberately. |

`session.history` is phase history, not tool-result history. A live `tool_result.result.stalled.reason` can explain the current stop, but no general durable stop-reason field is returned on reopen. `_EVENT_KEYS` in audit_projection omits reason and source; on resume without a live reason show “Detailed stop reason is not exposed here.” A visible count from projection.stall may reset after a reduction; never reconstruct a missing “8” or hardcode the default as observed history. Exact historical stall reasons are a payload limitation under this UI-only scope.

For stale provenance show `audit.external_edits[]` as path, source and epoch. Label it “Changes recorded for this session”. List stale requirements separately: current invalidation is epoch-wide. Do not draw unsupported path→requirement edges. “core_check” explains the source of reconciliation, not proof that only this path affected a predicate.

### Requirement revision form

Load `audit_projection.requirements[rid]` for raw predicate text/verifier bindings and current revision, paired with session_status inspector for current result/subject. Use a `<form class="lib-requirement-edit">` with labelled requirement text, predicates and closure; show current named verifier bindings read-only by default. Save via existing person `set_requirement {requirement_id,text,closure,predicates,verifiers}` and current session ID. **Always preserve full predicates and verifier parameter objects** on a text-only edit. Omitting them currently writes empty values, not a patch. Do not downgrade authoritative closure just to reopen. Refresh session_status and projection; display returned revision and stale prior evidence. There is no revision-CAS argument on set_requirement: pre-save reread detects known changes but is not atomic concurrency protection; disclose that limitation and never claim CAS. No new ledger.

### Progressive inspection

Requirements use summary rows: ID/text/current status plus number of stale/unchecked predicates. Selected requirement expands; each predicate shows exact statement, bound subject, verifier/strength, contract integrity and person decision separately. Preserve `details.open` by stable ID during redraw. Request evidence and accept/reject remain existing person tools. The actual result's `contract_integrity` should be shown instead of interpreting any pass as complete verification. Contract skeleton is an on-demand `audit_projection` disclosure labelled “Proposed contract, not admitted”; no automatic admit button. `fits:false` shows narrowing guidance; omit nonexistent skeleton. Structured refusals show code+human next step, `details` in collapsed labelled content, with no generic “done” fallback for a refusal.

## D4. Provenance and execution

### Compare what is available

Source revision review offers “Compare current note and proposed sections”: fetch current `/api/file`, display its exact returned text alongside item.sections/edited proposal fields. Retain staged_revision and revision tokens already issued by staging_show; bytes fetched separately are not automatically bound to the same token. Reload reviewed item after changes and keep the existing stale refusals. Label **“Proposed sections; final merged Markdown preview unavailable”**. Do not compute a client merge and present it as exact prepared write bytes.

Taxonomy review lists current topic map and proposal membership/refile choice side by side. New name/refile edits invalidate any local comparison display. The Core prepared acceptance plan is not in the UI response, so label this a semantic comparison, not an exact per-file diff. Keep “Reload topics (discards edits)” explicit and preserve partial-acceptance warnings. A byte-exact final source/taxonomy diff is outside UI-only scope until the existing contract actually exposes prepared bytes; no endpoint extension is silently specified here.

Search keeps depth, source state and advisories separate from claim truth. Desk/Agenda show origin note and due/pin status; add entry links to existing pane/menu methods without creating a task store. Host note-opening callbacks should explicitly preserve the existing Desk-touch intent if desired; do not infer a touch from a view-only host callback.

### Reply review

Render a compact advisory summary and expandable challenge rows with claim text, verdict, counterquote/reason, openable note reference and existing run_id/input when present. Keep “unchecked” distinct from contradicted. Since events lack reply identity, label a separate “Reply review (association not supplied)” region when association cannot be established; never pin to the latest assistant bubble based only on arrival order. Do not persist this as a new authoritative challenge store. NAT-10 is the dependency for exact turn/revision binding and bounded checked-span coverage.

### Claim Run / Workbench truth table

| Existing condition | Required display/action |
|---|---|
| Docker status not yet fetched | “Execution availability not checked”; refresh on explicit review opening. No green ready badge. |
| `/api/claims/runs.docker` reports unavailable | Visible explanation and refresh; disable “Run claim input in Docker”. Never offer silent host fallback. Existing endpoint returns a reason string; do not invent docker.available boolean. |
| Claim Run permitted | Show claim/source/input and “Docker container; no network” as visible text, then person POST /api/claims/run. No automatic run on review receipt. |
| Could not run / timeout | Show exact verdict/detail/version/evidence handle as returned; label cleanup “not reported” unless supplied. No “replicated” interpretation. |
| Workbench non_isolated_host_exec chosen | Dedicated visible “Runs on this host; network isolation is not enforced” and explicit confirmation through current person/checkpoint path. Never reuse Docker-only copy. |
| Workbench checkpoint approved | “Decision recorded; run not started”; user explicitly invokes matching engagement_start with checkpoint ID. |
| Output/timeout quarantine receipt unavailable | “Quarantine/cleanup status not exposed”; preserve raw result disclosure. Do not claim safe import, verified stop, or resource quota enforcement. NAT-04/05 backend packets remain outside this UI implementation. |

A small Execution disclosure can use current engagement person tools and existing schemas from `/api/tools`; it is not an agent orchestration console. No Docker process was run during this review. Do not probe Docker on every chat state refresh: docker_status itself can take time.

## D5. CSS and spatial isolation

### Naming and boundaries

Rename shared UI class tokens to `lib-*` in DOM, CSS, event selectors and tests in one change. Existing `.lib-*` stays; retain only host-owned adapter tokens `librarian-view`, `view-content`, `librarian-host`, `host-obsidian` at integration boundaries. Prefix state modifiers too (`lib-is-open`, not `.open`); otherwise host `.error` or `.active` still matches. Include `chat.ts`, `views.ts`, `settings.ts`, `pane.ts`, markdown/speech/attach emitters when migrating; changing main/panels alone is insufficient. Appendix inventories enumerate the requested files and CSS surface, including tokens not emitted there.

Scope both roots and dialogs: `.librarian-root .lib-dialog`, `.librarian-root .lib-dialog::backdrop`, `.lib-app …`. The settings dialog is a **sibling** of .lib-app today, so merely prefixing all rules with .lib-app would lose its styling. Native showModal moves painting to top layer, not DOM ancestry; a rooted dialog selector still matches. Scope `.host-obsidian` to `.librarian-root.host-obsidian` and its app child. Never write global `dialog`, `button`, `input`, `*`, `:root` rules in the shared stylesheet.

Add local control baselines including `height:auto`, `min-height:0`, `max-height:none`, normal wrapping, margin, line-height, box-sizing and flex behavior; give intentional icon dimensions in the owned classes. Avoid broad `all:initial` resets that destroy native semantics. Prefixing reduces incidental incoming class matches; it does not defeat arbitrary `!important` host selectors. Define that support boundary and test targeted realistic theme rules. The model picker fix already survives hostile `.popover/.card/.grid !important`; preserve it rather than restoring those names.

### Container layout

Use native ResizeObserver to set `data-lib-layout` on the mounted root from its **client width**, and maintain a local width only (view convenience, not an application state store). CSS queries that attribute; container queries may additionally be used where supported. Observe disconnect on dispose. Initial layout happens before persisted pane preferences; interpret saved width against current root.

- Wide >=1000px: split chat/document, main at least 360px and document at least 300px; clamp saved split to the actual available width. Keyboard separator exposes value/min/max; Left/Right adjusts bounded pixels and persists only on deliberate interaction.
- Compact 600–999px: one primary work area and an explicit Document overlay. Header wraps within the leaf; side lists stack. Never overlay a task unexpectedly merely because desktop preference was open.
- Narrow <600px: query on its own row, filters below; stacked staging list/detail with explicit Back to items; model cards one column; toolbar actions wrap with primary Send reachable. These thresholds are design defaults, not validated ergonomics constants.
- Dialog width <= `min(680px, rootWidth - 24px)` using a root property written by observer. Cap height to available leaf height and viewport; one dialog body scroller and fixed close/header. A top-layer modal must not visually spill across an unrelated editor without an explicit host-wide design decision.
- Popovers stay within root and chosen anchor, flip/clamp on resize and content load; `100vw/60vh/68vh` alone is insufficient. Set max-height from available root space. Single vertical scroll owner per chat/view/pane; evidence/code may scroll locally. Keep composer outside chat log scroll; no nested full-page scroll traps.

Shared narrow layout must work inside wide browser/Obsidian windows; placement migration is not a substitute. Persist desktop split preference separately from transient mobile overlay visibility using the existing localStorage convenience mechanism. A resize or session update must not overwrite the user's current draft/focus.

## D6. Keyboard ownership and navigation

Popover: trigger owns aria-controls/expanded, activation focuses first usable item **after content loads**, closed focus returns to trigger only if focus was within the closing surface. Nonmodal popover does not trap Tab; Tab leaving it closes predictably. A modal dialog uses native showModal focus containment and cancel behavior. Do not implement a second focus trap around native dialogs. Rooted Escape dispatch closes only the innermost open surface; prevent default/stop propagation only when actually handled and focus belongs to that surface. Ignore keys from unrelated host leaves. Obsidian capture-phase shortcuts may run first; real-host acceptance remains required.

Tabs implement roving tabindex and Left/Right/Home/End with matching panel relationships, or stop claiming tab semantics. Keep radio names and all IDs mount-unique. Pane menu gets equivalent focus-return and key handling, with owned listeners removed in dispose; delayed requests check mounted/session generation before writing to DOM. Inactive overlapped content cannot retain actionable focus.

Keep Chat/Staging/Search as primary workspace tabs; add labelled links to existing Sessions, Decisions, Plan, Desk and This week. Place high-frequency task queue actions in a Work actions disclosure, separate from permission modes. Keep route/qualification internals behind details while visibly retaining selected role/model and any blocking warning. Settings gets a recognisable label/icon. This is navigation over current methods and payloads, not a new routing/store layer.
