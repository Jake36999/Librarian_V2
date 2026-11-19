# Librarian V2 — Workflow Execution, Output Quality, UI Completeness & System-State Review

- **Date:** 2026-11-19
- **Librarian V2 revision:** `d1a08bb` (`feat/geo-per-library-service`, untouched)
- **Sandbox vault:** `C:\Users\jakem\Librarian ACCEPT-02 Vault` (served on `http://127.0.0.1:62047/` during testing; stopped cleanly afterwards; original 4 Cores untouched)
- **Model spend during this round:** `$0.000` new spend (ACCEPT-02 cumulative spend unchanged at `$0.043281` / `$10.00` ceiling)
- **Scope:** All **15** standard Librarian workflows and pipelines (`13` workflows + `2` pipelines) — 14 executed live on sandbox data, 1 (`sync-vault`) inspected read-only to avoid committing/pushing git state — plus live Web UI verification of all 5 paperclip workflows, paused-run state, MCP permission handling, and system-state visibility.

---

## Executive Verdict

The **underlying durable workflow engine** ([`workflows.py`](file:///D:/Librarian_V2/src/resource_librarian/workflows.py)) has solid foundations: YAML validation (`CLOSED_ACTION_REGISTRY`), closure pinning (`MF-017`), durable `dispatch`/`done` logging (`MF-018`), clean memoized resume via `run_resume`, and honest extraction-quality diagnostics on PDF intake.

However, **in live use both agents and Web UI users hit severe end-to-end failures**:

1. **Every workflow launched from the UI's paperclip menu silently discards its output** — `app.js` drops `event.result` on `action_done` and deletes finished chips immediately, leaving zero results, errors, or run history visible anywhere in the UI.
2. **Three batch workflows report false success counts (`on_error: continue` + `steps.<id>.count`)** — `deep-read-staged` reported `read: 5` when **0/5** succeeded (all 5 refused with `THIRD_PARTY_ROUTE_REQUIRED`), and `ingest-cited` reported `ingested: 1` when its only citation was a nonexistent arXiv ID that **failed and was quarantined**.
3. **Every reasoned pipeline (`clear-enrichment-backlog`) always pauses with `"no routing model is configured"`** for any user who configured models via the Web UI — `_router()` only checks legacy `config.toml`, ignores `ctx.extras["clerk"]`, and Settings has **no routing-model control** anywhere.
4. **Paused workflows become dead-end UI chips with no recovery path** — they show non-interactive text (`clear-enrichment-backlog · paused: no routing model is configured`), never appear in `Checkpoints`, offer no route picker / resume / cancel / dismiss controls, and **stay stuck in the UI forever even after `run_resume` finishes the run**.
5. **Only 5 of 15 standard workflows are reachable in the UI**, optional parameters are stripped, there is no run-history or YAML viewer, and **system state is fragmented and contradictory** across `Skill registry`, `Tools & integrations`, `Health & diagnostics`, `Staging`, and `Chat`.

---

## 1. Workflow-by-Workflow Execution & Output Quality Matrix (All 15 Standard Definitions)

| # | Name | Kind | In UI (`📎`)? | Tested Run ID / Method | Backend Status | Actual Outcome & Output Quality Assessment |
|---|---|---|---|---|---|---|
| 1 | `review-conversation` | Workflow | Yes | `20261119-160048-review-conversation-3c96`, `162043-de6a`, `162043-8afe` | `finished` | **Mixed / Poor score calibration.** Found right top-2 papers on multi-term routing/IVFPQ query (with honest `read_depth: "partial 0/16"`), **but** normalized BM25 gave **`rank: 1.0` and `0.9839`** to unrelated yield-curve finance & BIM MEP papers on an absent physics query (`"superconducting quantum teleportation error correction"`) for matching only `'error'`. Meanwhile, a 6/6 exact match (`BIM MEP electrical switch socket classification`) got `verdict: "uncovered"` (because it matched `Reading Notes` / `caveat`), identical to the absent query (`rank: 1.0` + `verdict: "uncovered"`). UI also forces manual `text` entry instead of reading the active thread, and discards all output. |
| 2 | `review-due` | Workflow | Yes | `20261119-160146-review-due-0d56` | `finished` | **Clean on empty state (`opened: [], skipped: [], remaining_due: 0`).** UI gives zero confirmation that `0` due concepts were found. |
| 3 | `weekly-review` | Pipeline | Yes | `20261119-160214-weekly-review-9d5a` | `finished` (misleading) | **Broken / silent empty draft.** Gathered `agenda`, `activity`, `desk` for `ACCEPT-02 Dirty Target` (all empty), called `reflection_draft` -> returned **`{"draft": "", "ok": false, "drafted_by": ""}`** with **no error reason**, yet both `draft-reflection` and `weekly-review` reported `status: "finished"`. UI omits `since` input and shows zero output. |
| 4 | `clear-enrichment-backlog` | Pipeline | Yes | `20261119-160234-f6bd` (empty), `162245-98c9` (live PDF + `run_resume`) | `finished` (empty) / `paused` (live) | **Strong intake quality; broken router wiring & dead UI recovery.** On queued `EXT_O1_1810.08473_From_Louvain_to_Leiden.pdf`, `intake_run` staged it cleanly and emitted actionable PDF diagnostics (`25 pages`, `quality: cleanup`, `"194 words broken across lines, bare page numbers"`). Pipeline then **always pauses** at `next[0]` (`"no routing model is configured"`) because [`tools/workflows.py:13-23`](file:///D:/Librarian_V2/src/resource_librarian/tools/workflows.py#L13-L23) ignores UI-configured models. Backend `run_resume(choices={"next[0]": "review"})` succeeded cleanly, reusing memoized intake, but the UI chip remained stuck as `paused` permanently. |
| 5 | `deep-read-staged` | Workflow | Yes | `20261119-160241-deep-read-staged-8a1b` | `finished` (false success!) | **Critically broken in UI + false success reporting.** Finished in `0.3s` claiming **`outputs: {"read": 5}`**, when **0/5** were read: all 5 `deep_read` calls were refused with `THIRD_PARTY_ROUTE_REQUIRED` because [`app.py:3014`](file:///D:/Librarian_V2/src/resource_librarian/app.py#L3014) starts UI actions at agent tier `contribute` (not `curate`, and without `_batch_run`). Because `workflows.py:825` sets `count = len(results)` including errors under `on_error: continue`, 5 refusals became `read: 5`. |
| 6 | `gather-agenda` | Workflow | No | `20261119-162038-eaf3` (`project=""`), `162041-d881` (`ACCEPT-02 Dirty Target`) | `finished` | **Accurate & structured** (`48` undated tasks extracted cleanly with `note`, `path`, `text`, `due: null` across vault; `0` for `ACCEPT-02 Dirty Target`). Unreachable in UI; calling via MCP `run_workflow` in `Ask` mode **blocks for 3 minutes and times out** despite being 100% read-only. |
| 7 | `gather-activity` | Workflow | No | `20261119-162041-gather-activity-9563` (`-7d`, `project=""`) | `finished` | **Accurate & structured** (`since` ISO cutoff, `uses: []`, `6` timestamped `write_note` entries with session ID, path, and phase). Unreachable in UI. |
| 8 | `gather-desk` | Workflow | No | `20261119-162042-gather-desk-2221` | `finished` | **Accurate** (`{"project": "ACCEPT-02 Dirty Target", "working_set": []}`). Unreachable in UI. |
| 9 | `draft-reflection` | Workflow | No | `20261119-162046-draft-reflection-6196` (non-empty 48 tasks + 6 writes) | `finished` (misleading) | **Two output defects.** (a) [`tools/sessions.py:2047`](file:///D:/Librarian_V2/src/resource_librarian/tools/sessions.py#L2047) only reads `("overdue", "today", "this_week")`, silently dropping `later` and all `48` `undated` tasks so `Tasks:` rendered blank. (b) Clerk failed qualification and silently queued task `995237f835f7d62e.json`, yet `reflection_draft` stripped `drafted.problems` and returned `ok: false, draft: ""` under `status: "finished"`. |
| 10 | `review-item` | Workflow | No | `20261119-162045-review-item-f871` (`ext-o3-2403-14403-adaptive-rag-59c0ea`) | `finished` | **Honest diagnostic output (best error clarity).** Returned `draft.status: "queued"` with exact root cause: `"clerk profile cannot use this route: agent profile 'clerk' requires screened qualification for role 'clerk'; this route is experimental (missing)"` — contradicting Staging UI's generic `"Choose a tier 3 model"` hint. Unreachable in UI. |
| 11 | `review-staged` | Workflow | No | `20261119-162045-review-staged-d897` (`limit=5`) | `finished` | **Broken filter logic (`reviewed: 0` when undrafted items exist).** `ext-o3-2403-14403-adaptive-rag-59c0ea` has `reviewed: true, drafted: false` (because an earlier review queued to clerk). [`review-staged.yaml:11`](file:///D:/Librarian_V2/src/resource_librarian/standard/workflows/review-staged.yaml#L11) filters `when: {from: item.reviewed, is: false}` instead of `drafted: false`, permanently skipping previously queued items. Also uses `on_error: continue` + `steps.review.count`. |
| 12 | `run-queue` | Workflow | No | `20261119-162049-51ce` (empty) + inside `162245-98c9` (1 PDF) | `finished` | **High-quality output.** Cleanly returned `{results: [], still_waiting: 0}` when empty, and staged `EXT_O1_1810.08473_From_Louvain_to_Leiden.pdf` with clear `quality` diagnostics (`cleanup`, `pages: 25`, `signs`, `next`). Unreachable directly in UI (only via `clear-enrichment-backlog`). |
| 13 | `ingest-cited` | Workflow | No | `20261119-162049-ingest-cited-16fe` (scratch note: 1 non-academic URL + 1 invalid `arXiv:9999.99999`) | `finished` (false success!) | **Good URL/identifier parsing; false success count.** `record_trace` accurately extracted both links and filtered `identifier_kind in [arxiv, doi]` (`cited: 2`). `ingest` properly quarantined nonexistent `arXiv:9999.99999` (`state: "failed"`), **but** `ingest-cited` finished reporting **`{"cited": 2, "ingested": 1}`** due to `steps.papers.count` counting failed iterations. |
| 14 | `flag-sensitive` | Workflow | No | `20261119-162531-flag-sensitive-15b0` (reverted immediately) | `finished` | **Clean & exact** (`outputs: {"sensitivity": "review"}`, cleanly reverted via `staging_flag(..., sensitive=False)`). Unreachable as a workflow in UI. |
| 15 | `sync-vault` | Workflow | No | Read-only YAML + `show_workflow` validation (not executed) | `valid: true` (`tier: contribute`) | Runs `gitignore_ensure` -> `vault_commit` -> `vault_push` (when `committed: true`). No UI trigger, no dry-run/preview step, and requires `contribute` tier rather than `curate`. |

---

## 2. Root-Caused Defects (Exact Code Evidence)

### Critical Defect 1 — Paperclip Workflows Silently Discard All Output in UI
- **Where:** [`ui/app.js:8366-8378`](file:///D:/Librarian_V2/src/resource_librarian/ui/app.js#L8366-L8378), [`ui/app.js:8491-8512`](file:///D:/Librarian_V2/src/resource_librarian/ui/app.js#L8491-L8512), [`app.py:3039-3040`](file:///D:/Librarian_V2/src/resource_librarian/app.py#L3039-L3040)
- **What happens:** Core streams `action_done` with full `"result": action.result`, but `app.js:8371` copies only `{ id, name, status, steps, reason }`, dropping `event.result` completely. `paintChips()` (`app.js:8492`) only renders `status === "running" || status === "paused"`. Because fast workflows finish in `30–300ms`, the chip disappears immediately and `chat.handle` ignores `action_done`. `GET /api/actions` returns `404`.
- **User impact:** All 5 paperclip workflows (`review-conversation`, `review-due`, `weekly-review`, `clear-enrichment-backlog`, `deep-read-staged`) produce **zero visible output, zero completion feedback, and zero error reporting**, directly contradicting the menu's `Result:` descriptions.

### Critical Defect 2 — Systemic False-Success Counting Under `each` + `on_error: continue`
- **Where:** [`workflows.py:820-827`](file:///D:/Librarian_V2/src/resource_librarian/workflows.py#L820-L827), [`workflows.py:874-880`](file:///D:/Librarian_V2/src/resource_librarian/workflows.py#L874-L880)
- **What happens:** Under `on_error: continue`, failed/refused/quarantined iteration results are appended to `results`, and `count` is computed as `len(results)` with no `succeeded`/`failed` split.
- **Affected workflows:** `deep-read-staged` (reported `read: 5` on `0/5` successes), `ingest-cited` (reported `ingested: 1` on `0/1` successes), and `review-staged` (`reviewed: count`).

### Critical Defect 3 — `deep-read-staged` Always Refused on Third-Party Sources When Started From UI
- **Where:** [`app.py:3014`](file:///D:/Librarian_V2/src/resource_librarian/app.py#L3014), [`read_access.py:103-128`](file:///D:/Librarian_V2/src/resource_librarian/read_access.py#L103-L128)
- **What happens:** Despite the comment `"# A person started this workflow"`, `start_action()` creates `Context(tier="contribute", ...)` without `_batch_run`. `read_access.guard()` requires `tier == "curate"` or `_batch_run` for `deep_read` on third-party files, so every staged PDF fails with `THIRD_PARTY_ROUTE_REQUIRED`.

### Critical Defect 4 — Pipeline Router Ignores UI-Configured Models & Paused Chips Are Dead Ends
- **Where:** [`tools/workflows.py:13-23`](file:///D:/Librarian_V2/src/resource_librarian/tools/workflows.py#L13-L23), [`ui/app.js:8496-8511`](file:///D:/Librarian_V2/src/resource_librarian/ui/app.js#L8496-L8511), [`app.py:3004-3043`](file:///D:/Librarian_V2/src/resource_librarian/app.py#L3004-L3043)
- **What happens:**
  1. `_router(ctx)` only reads `ctx.extras["router"]` (never set by `app.py`) or legacy `config.toml` `[routing]`/`[clerk]` — ignoring `ctx.extras["clerk"]` from `Settings -> Models & services`.
  2. Settings has **zero** UI control or search hit for `"routing"` (`Find a setting` -> `"No matching settings."`).
  3. When `clear-enrichment-backlog` pauses, the UI renders a static `<span class="lib-chip">clear-enrichment-backlog · paused: no routing model is configured</span>` with **no route chooser (`done`/`flag`/`review`), no resume button, no cancel/dismiss button**, and nothing in `Checkpoints`.
  4. Even after resolving the run via backend `run_resume` (`status: "finished"`), `self.actions["63cf26cf"]` stays `paused` in `/api/state` and the stale chip never clears.

### High Defect 5 — Read-Only MCP `run_workflow` Hangs for 3+ Minutes in `Ask` Mode, Duplicates Permission Cards, and Silently Parks the Session
- **Where:** [`tools/workflows.py:86`](file:///D:/Librarian_V2/src/resource_librarian/tools/workflows.py#L86), [`app.py:2979-2986`](file:///D:/Librarian_V2/src/resource_librarian/app.py#L2979-L2986), [`broker.py:211-226`](file:///D:/Librarian_V2/src/resource_librarian/broker.py#L211-L226)
- **What happened live:**
  1. Calling MCP `run_workflow(name="gather-agenda", inputs={"project": ""})` (100% read-only) triggered an `Ask` permission prompt because `run_workflow` is statically tagged `effect="write"`.
  2. Because `mcp_call` blocks synchronously on `broker.check` (`600s` timeout > `180s` MCP client timeout), the MCP client timed out at 3 minutes while the Core waiter stayed hung for ~10 minutes.
  3. In the UI, **switching to `Staging` showed zero badge/dot on `Chat`**, reload produced **two duplicate `Permission needed` cards** for `ab65aad8`, and when the request expired only the second card updated (`Nobody answered.`) while clicking `Deny` on the first card returned **`HTTP 404` (`Could not answer: no pending request 'ab65aad8'`)**.
  4. Expiration automatically parked session `20261119-1556-8f7865` with **zero explanation** in `Chat`, `Sessions`, or `Plan`.
  - Evidence: [`ui-paused-chip-and-dup-permission.png`](file:///D:/Librarian_V2/reports/2026-11-19-agent-review/evidence/ui-paused-chip-and-dup-permission.png)

### High Defect 6 — Contradictory MCP Health & Hidden System State Across UI Panels
- **MCP contradiction (verified visually & in code):**
  - `Skill registry` displays `geo-grapher · on · 22 tools` AND `semantic-scholar · on · 0 tools` — because [`app.py:3068`](file:///D:/Librarian_V2/src/resource_librarian/app.py#L3068) reads global `enabled` and ignores per-library `library_enabled` ([`mcp_client.py:644`](file:///D:/Librarian_V2/src/resource_librarian/mcp_client.py#L644)).
  - `Settings -> Review & promotion` reports `Enabled external servers: geo-grapher (connected)`.
  - `Settings -> Tools & integrations` shows `Semantic Scholar · Enable here`.
  - Yet `Settings -> Health & diagnostics` reports **both** `mcp: geo-grapher · installed; not enabled in this library` AND `mcp: semantic-scholar · installed; not enabled in this library` — because [`doctor.py:106-107`](file:///D:/Librarian_V2/src/resource_librarian/doctor.py#L106-L107) checks `mcp.json` / `enabled_here()` before checking `live[name]["library_owned"]`.
  - Evidence: [`ui-workflows-health-contradiction.png`](file:///D:/Librarian_V2/reports/2026-11-19-agent-review/evidence/ui-workflows-health-contradiction.png)
- **Additional hidden/misleading system state:**
  - **68 queued clerk tasks** in `.librarian/queue/clerk/` are completely invisible anywhere in the UI (and `Staging` blames `"Choose a tier 3 model"` instead of reporting the actual qualification failure: `"requires screened qualification for role 'clerk'; this route is experimental (missing)"`).
  - **Vault spend vs dollar ceiling** (`$0.043` / `$10.00`) is absent everywhere (only TTS shows a service cap: `"spent or held $0.02 of its $2.00 cap"`).
  - **Top model pill** (`1 lead-m · preset-deepinfra`) displays no broken-route warning even though `lead-m` 404s.
  - **Queue/staging/due counts** (`0 queued`, `5/6 staged`, `0 due review tasks`) are buried inside `Settings -> Commands & shortcuts` rather than surfaced on a status bar or workflow panel.
  - **Read-only MCP tools refuse under `BUDGET_SPENT`:** `list_workflows` and `run_list` were refused on session `20261118-1742-40fd2e` (`budget_left: 0`) even though they are read-only inspection calls.

---

## 3. UI Completeness & System-State Assessment

| Capability / State Dimension | Available in UI? | Verdict & Gap |
|---|---|---|
| Standard workflows & pipelines (`15` total) | **5 of 15** (`QUEUED` hardcoded in [`app.py:87`](file:///D:/Librarian_V2/src/resource_librarian/app.py#L87)) | 10 workflows (`gather-*`, `draft-reflection`, `review-item`, `review-staged`, `run-queue`, `ingest-cited`, `flag-sensitive`, `sync-vault`) have no UI entry point. |
| Optional workflow parameters (`since`, `limit`, `max_chunks`) | **No** ([`app.py:4346-4348`](file:///D:/Librarian_V2/src/resource_librarian/app.py#L4346-L4348)) | Only inputs without defaults are prompted; users cannot adjust `weekly-review`'s `since` window or `clear-enrichment-backlog`/`deep-read-staged` batch limits. |
| Workflow output display & run history (`run_list`, `run_status`, `show_workflow`) | **No** | Zero output rendering for `/api/actions`, `GET /api/actions` is `404`, no history panel, no YAML inspection, no `save_workflow` / `accept_workflow` UI. |
| Paused pipeline recovery (`run_resume` with choices) | **Chat tool-call only (`outcome_unknown`), NOT for `/api/actions` or routing pauses** | `app.js:1002` only handles `outcome_unknown` from chat `tool_result`; paused routing runs from `📎` cannot be resumed, chosen, cancelled, or dismissed in UI. |
| Session phase & call budget | **Clear** (`Document Pane -> Plan`) | Well presented (`◐ Frame · 26 calls left`, 7-phase track, `NEXT:` hint), except automatic session parking from unanswered permissions gives no reason. |
| Core runtime health (`Writer`, `Index`, `Watcher`, `Vault lease`) | **Clear** (`Settings -> Health & diagnostics`) | Clear when Core is healthy, but undermined by the false `mcp: geo-grapher` check. |
| Clerk queue, vault spend vs cap, route qualification health | **Hidden / Misleading** | 68 clerk tasks invisible; vault dollar spend invisible; Staging gives wrong fix instruction for clerk qualification failure. |

---

## 4. Prioritized Fix Recommendations

1. **Surface `/api/actions` outputs, errors, and run history in the UI** (`app.js:8366-8378, 8491-8512` + `GET /api/actions` / `run_list`): preserve `event.result`, render a completion/error card (or collapsible result drawer) for finished/failed actions, and link each run to its outputs (e.g. suggested sources list, weekly reflection draft with an `Accept reflection` button calling `reflection_accept`, or counts of succeeded vs failed items).
2. **Make paused pipeline runs actionable and sync `self.actions` with `RunStore`** (`app.py`, `app.js:8496-8511`): add route-choice + `Resume` / `Cancel` controls on paused chips (or surface paused pipelines inside `Checkpoints`), and update/clear `self.actions` when `run_resume` completes a run.
3. **Wire `_router(ctx)` to configured Core/UI endpoints** (`tools/workflows.py:13-23`): check `ctx.extras.get("clerk")` (or a dedicated Settings routing-model slot) before falling back to `config.toml`.
4. **Fix `each` + `on_error: continue` accounting** (`workflows.py:820-828`): track `succeeded`, `failed`, and `errors` separately so `deep-read-staged`, `review-staged`, and `ingest-cited` never count refused or quarantined items as completed.
5. **Fix `deep-read-staged` tier/capability from UI** (`app.py:3014`) and **`review-staged` filter** (`review-staged.yaml:11` -> filter on `drafted: false` rather than `reviewed: false`), plus surface `drafted.problems` in `reflection_draft` (`tools/sessions.py:2063`) and include `undated` / `later` tasks when requested or summarize counts clearly.
6. **Fix `Ask`-mode MCP ergonomics & Chat notification hygiene**: classify `run_workflow` read/write effect from its target workflow closure, fail/return `needs_person` cleanly on non-interactive MCP calls instead of hanging past client timeout, add a pending-permission badge on `Chat`, and deduplicate permission cards on reload (`app.js`).
7. **Unify system-state indicators**: fix `doctor.py:106` (`library_owned` check before `enabled_here`), fix `app.py:3068` (`library_enabled` & `connected` in `skill_registry`), surface the `.librarian/queue/clerk/` depth and true qualification error in `Staging`, expose vault dollar spend vs ceiling, and exempt read-only inspection tools (`list_workflows`, `run_list`, `run_status`) from `BUDGET_SPENT`.
