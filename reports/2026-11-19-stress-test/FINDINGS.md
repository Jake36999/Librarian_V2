# Stress-Test Findings (2026-11-19)

Every finding below was reproduced **at least twice** (via live Chrome UI, Playwright, and/or deterministic backend scripts in `tools/`) and checked against baseline `da7bf8a`. Items explicitly listed in Section 4 (*Known and deliberately open*) are omitted here and noted with supporting evidence in [COVERAGE.md](COVERAGE.md).

---

### F-01 — Staging `"Show 50 more"` pager is completely broken (`MAX_LIMIT = 50` hard clamp)

- **Severity:** `blocker`
- **Tag:** `verified`
- **Regression?:** **Yes** (introduced in `3d50b2f`; `da7bf8a` had no `"Show 50 more"` button).
- **Steps to reproduce (reproduced 3× — Pass 1 live UI, Pass 2 live UI, `tools/stress_d_staging.py` ×2):**
  1. Seed a scratch vault with >50 staged sources (e.g. 55 or 61 items via `tools/prepare_ui_vault.py`, or 51 / 500 items in `tools/stress_d_staging.py`).
  2. Open **Staging → Sources → Staged** (`1280×900`) — UI displays `Showing 50 of 61.` and button `Show 50 more`.
  3. Click `Show 50 more`.
  4. Alternatively run `D:\Librarian_V2\.venv\Scripts\python.exe reports\2026-11-19-stress-test\tools\stress_d_staging.py --fast`.
- **Evidence:**
  - Live UI Pass 2 (`http://127.0.0.1:58972/`): clicking `Show 50 more` sent `POST /api/tool/staging_list` with `limit: 100` → HTTP `200`, returned 50 rows starting at the first item (`total: 61`), UI remained stuck at `rowsAfter: 50` and `"Showing 50 of 61. Show 50 more"`.
  - Backend (`stress_d_staging.py` output):
    ```json
    "51":  { "limit50_len": 50, "limit50_total": 51,  "limit100_len": 50, "limit600_len": 50 },
    "500": { "limit50_len": 50, "limit50_total": 500, "limit100_len": 50, "limit600_len": 50 }
    ```
- **Suspected cause:**
  - `ui/src/views.ts:105,273,330-331` implements `"Show 50 more"` by incrementing `this.listLimit += 50` and requesting `staging_list({ kind, status, limit: this.listLimit })` with no `offset`.
  - `src/resource_librarian/registry.py:41,668-671` globally clamps every `limit` argument on every tool call to `MAX_LIMIT = 50` (`bounded = max(1, min(MAX_LIMIT, number))`).
- **Suggested fix:** Add cursor/`offset` pagination to `staging_list` (returning `items`, `total`, `offset`, `has_more`) and have `ui/src/views.ts` fetch the next page (`offset: rows.length, limit: 50`) and append rows, rather than raising `limit` above `MAX_LIMIT`.

---

### F-02 — Macro checkpoint approval reuse has 4 security and correctness bugs

- **Severity:** `high`
- **Tag:** `verified`
- **Regression?:** **Yes** (introduced in `3d50b2f`; `da7bf8a` did not auto-reuse checkpoints when `checkpoint_id` was omitted).
- **Steps to reproduce (reproduced 2× via `tools/stress_c_checkpoints.py`):**
  1. Run `D:\Librarian_V2\.venv\Scripts\python.exe reports\2026-11-19-stress-test\tools\stress_c_checkpoints.py` twice.
  2. The script exercises a write-capable macro (`_stress_write`) across 8 scenarios:
     - **Case 5 (Approve then later cancel):** Approve checkpoint 1 for scope `S`; create & explicitly `cancel` checkpoint 2 for the same scope `S`; call `run_macro` without `checkpoint_id`.
     - **Case 7 (Cross-session hijack):** Session A gets checkpoint approved for scope `S`; Session B (`untrusted-mcp-B`) calls `run_macro` with identical inputs and no `checkpoint_id`.
     - **Case 2 (Re-run after completion):** Complete a macro once; call `run_macro` again for the same inputs without `checkpoint_id`.
     - **Case 8 (Concurrent race):** Approve 1 checkpoint; invoke `run_macro` from 2 threads simultaneously without `checkpoint_id`.
- **Evidence (`tools/stress_c_checkpoints.py` 2nd run):**
  ```json
  "2_same_scope_after_completion": {
    "third_call_status": "completed", "reused": true,
    "detail": "this approved run already completed; nothing was repeated",
    "blocked_from_fresh_rerun": true
  },
  "5_approve_then_later_cancel": {
    "approved_id": "49cda5ec382b89b3", "later_cancelled_id": "2c29ad14a6754693",
    "run_status": "completed", "bypassed_later_cancel": true,
    "note_written_despite_later_cancel": true
  },
  "7_cross_session_approval_reuse": {
    "session_A": "20261119-0030-2d73ae", "session_B": "20261119-0030-162c8d",
    "session_A_scope": "macro:_stress_write:v1:fe62d7f596b64d31",
    "session_B_status": "completed", "session_B_reused_session_A_approval": true,
    "note_written_by_session_B": true
  },
  "8_concurrent_same_approval": {
    "t0_status": "completed", "t0_reused": null,
    "t1_status": "completed", "t1_reused": null,
    "both_ran_not_reused": true, "journal_events": 1
  }
  ```
- **Suspected cause:**
  - `src/resource_librarian/agent_runtime.py:804` (`_checkpoint_scope`) hashes only `macro.id`, `macro.version`, and `inputs` — omitting `session` and `requester`.
  - `src/resource_librarian/agent_runtime.py:947-957` scans `reversed(checkpoints.all())` for **any** `resolution == "approve"` matching `scope`, skipping newer `cancel`/`reject` decisions on the same scope; completed checkpoints have empty `expires_at` so they stay matched forever; and there is no atomic single-use claim lock around checkpoint consumption.
- **Suggested fix:**
  1. Include `session` (and `requester`/caller identity) in `_checkpoint_scope`.
  2. Inspect ONLY the **latest** checkpoint for `scope`; if its resolution is `cancel`/`reject` (or if it is already `completed`), create a fresh pending checkpoint instead of searching older cards or replaying `"already completed"` forever.
  3. Atomically mark an approved checkpoint as `in_progress`/`consumed` under a lock before executing steps so concurrent callers cannot execute twice on one approval.

---

### F-03 — Accepted vault-defined pipelines silently grant arbitrary `contribute` writes in Ask mode without UI disclosure

- **Severity:** `high`
- **Tag:** `verified`
- **Regression?:** **Yes** (introduced in `3d50b2f`; `da7bf8a` had no `workflow_grant` in `Broker`, so Ask mode prompted for every write).
- **Steps to reproduce (reproduced 2× via `tools/stress_b_grants.py`):**
  1. Save a vault workflow + pipeline (`innocent-step` → `write_note`, or nested `innocent-parent` → `hidden-writer` → `write_note`), and accept them (person accepted once, or synced `accepted.json`).
  2. In **Ask** mode, start the pipeline via `App.start_action("innocent-cleanup", {})` (the exact endpoint invoked when a person clicks it in `Paperclip → Run a workflow → This vault's pipelines`).
  3. Inspect `ui/src/panels.ts:203-206` to see what the UI displays before the click.
- **Evidence (`tools/stress_b_grants.py` 2nd run):**
  - Unaccepted vault pipelines ARE safely refused (`PERSON_CONFIRMS`) and omitted from `app.state()["pipelines"]`.
  - Once accepted, `App.start_action` grants EVERY tool in `workflows.granted_actions()` (including nested child workflows via `closure()`):
    ```json
    "accepted_write_note_in_ask_mode": {
      "status": "finished", "permission_requests_fired": 0,
      "file_written_without_ask": true, "granted_tools": ["write_note"]
    },
    "nested_workflow_grant": {
      "status": "finished", "granted_tools": ["write_note"],
      "permission_requests_fired": 0, "nested_file_written_in_ask_mode": true
    }
    ```
  - `Broker._policy(..., granted=True)` returns `"allow"` in Ask mode for `write_note`, `archive_note`, `staging_decide`, `vault_commit`, `vault_push`, `sandbox_run`, `request_raw_source_access`, and `note_move` (only `project_edit` and `sandbox_output` remain in `ALWAYS_ASK`).
  - `ui/src/panels.ts:203-206` renders `"This vault's pipelines"` as bare menu buttons showing only the pipeline name (no step summary, no `Result:` line, no list of granted write tools).
- **Suspected cause:** `App.start_action` grants `workflows.granted_actions(definition)` indiscriminately for vault-defined pipelines just like shipped built-ins, while `ui/src/panels.ts:203-206` omits any disclosure of what tools/writes a vault pipeline will execute.
- **Suggested fix:** Either restrict automatic `workflow_grant` to shipped/read-or-staging-scoped built-ins (requiring normal Ask prompts for vault-defined writes, or placing `vault_push`, `sandbox_run`, `staging_decide`, `archive_note`, `request_raw_source_access` in `ALWAYS_ASK`), AND render each vault pipeline's `purpose` + granted write actions clearly in the `"This vault's pipelines"` menu before the user clicks.

---

### F-04 — `Stop` while waiting on `ask_user` or `Broker` permission wedges Chat (`Stopping…` + `409 Conflict`) and switching sessions throws `Uncaught NotFoundError` (`insertBefore`)

- **Severity:** `high`
- **Tag:** `verified`
- **Regression?:** No (pre-existing in `da7bf8a`, unfixed).
- **Steps to reproduce (reproduced 2× live on `http://127.0.0.1:58972/` — Pass 1 on `ask_user`, Pass 2 on `macro_run` permission prompt):**
  1. Send a Chat prompt that triggers either `ask_user` (Pass 1) or a `Broker` permission card in Ask mode (Pass 2: `macro_run`).
  2. While the inline card is waiting and the `Stop` button is visible, click `Stop` (`POST /api/chat/cancel` → HTTP `200 {"cancelling": true}`).
  3. Observe the button stays stuck on disabled `Stopping…`, and clicking `New conversation` (`POST /api/chat/reset`) fails with `409 Conflict ("the librarian is still answering")`.
  4. Click `Sessions ▾` and switch to another session while `Stopping…` is active.
- **Evidence:**
  - Pass 1 live UI (`ask_user` pending): `Stop` stayed disabled on `Stopping…`; `New conversation` returned HTTP `409`; switching threads logged `Uncaught NotFoundError: Failed to execute 'insertBefore' on 'Node'` at `app.js:902`.
  - Pass 2 live UI (`macro_run` permission pending): clicking `Stop` sent `POST /api/chat/cancel` (`200 {"cancelling": true}`), stayed stuck on disabled `Stopping…`; switching to `20261118-2309-90907d` threw `ConsoleError: Uncaught NotFoundError: Failed to execute 'insertBefore' on 'Node': The node before which the new node is to be inserted is not a child of this node. (http://127.0.0.1:58972/app.js:902)` and left Plan out of sync (`No thread yet`). Only reloading and clicking `Deny` released the turn.
- **Suspected cause:**
  - `src/resource_librarian/app.py:2762-2767` (`App.cancel_turn`) only calls `self._turn_cancel.set()` without releasing/cancelling pending `self.waiters` or `self.broker` waits, so the worker thread remains blocked on `event.wait(600)` holding `self.busy = True`.
  - `ui/src/chat.ts:196-206` (`replay()`) calls `clear(this.log)` without resetting `this.working = null`, so the next `this.append()` at `ui/src/chat.ts:134` (`if (this.working) this.log.insertBefore(el, this.working);`) throws `NotFoundError` because `this.working` was detached.
- **Suggested fix:**
  1. In `App.cancel_turn()`, cancel/deny any active turn waiter (`self.waiters`) and pending turn permission request (`self.broker`) so the blocked tool call exits immediately and clears `self.busy`.
  2. In `ui/src/chat.ts:196` (`replay()`), call `this.working = null` (or `this.setWorking(false)`) before `clear(this.log)`.

---

### F-05 — Cross-session `q1` card-ID collision silently drops blocking questions in Chat

- **Severity:** `high`
- **Tag:** `verified`
- **Regression?:** No (pre-existing in `da7bf8a`, unfixed).
- **Steps to reproduce (reproduced 2× — Pass 2 live real-model `promote_offering`, plus deterministic Playwright `tools/repro_q1_collision.mjs`):**
  1. In one browser tab (without reloading), open or run Session A where a tool asks `q1` (e.g. `open_brief` `BRIEF_REQUIRED`, `ask_user`, or `promote_offering`).
  2. Switch to Session B (via `Sessions ▾` or `New conversation`) where a tool asks its own `q1` (`promote_offering` in Pass 2, or a seeded open `q1` in `repro_q1_collision.mjs`).
  3. Observe that no question card renders in Chat; reload the page and re-open Session B to verify the card immediately appears once `this.cards` is wiped.
- **Evidence:**
  - Pass 2 live UI: After `20261118-2309-d1f9c6` asked `q1` (`open_brief`), switching to `20261118-2309-90907d` caused `promote_offering`'s blocking `q1` (`Promote the offering 'Osquery Brief Synthesis'...`) to never render in Chat, leaving Chat stuck on `promote_offering · running` (~110s) until manual page reload revealed `q1` in Plan.
  - Deterministic Playwright (`node reports\2026-11-19-stress-test\tools\repro_q1_collision.mjs`):
    ```json
    {
      "sidA": "20261119-0033-caf1cd", "sidB": "20261119-0033-a566eb",
      "afterA": { "chatQuestions": ["The librarian is asking · confirmQuestion in Session A?yesno"] },
      "afterB": { "chatQuestions": [], "chatText": "continuing the thread 20261119-0033-a566eb" },
      "afterReloadB": { "chatQuestions": ["The librarian is asking · confirmPromote the offering in Session B?yesno"] },
      "bugReproduced": true
    }
    ```
- **Suspected cause:** `src/resource_librarian/tools/sessions.py:200` numbers questions per-session starting at `q1`, while `ui/src/chat.ts:845,885` keys `this.cards` as `q:${id}` without `sessionId`, and neither `replay()` (`chat.ts:196`) nor `conversation_reset` (`chat.ts:431`) calls `this.cards.clear()`.
- **Suggested fix:** Call `this.cards.clear()` inside `replay()` and `conversation_reset`, AND key question cards by `q:${sessionId}:${id}` in `chat.ts:845,885,467`.

---

### F-06 — `audited` purpose still deadlocks on `close_session` in every phase

- **Severity:** `high`
- **Tag:** `verified`
- **Regression?:** No (pre-existing in `da7bf8a`, missed by `3d50b2f`'s "phase deadlocks fixed" and `scripts/phase_walk.py`).
- **Steps to reproduce (reproduced 3× via `tools/stress_a_phases.py`):**
  1. Run `D:\Librarian_V2\.venv\Scripts\python.exe reports\2026-11-19-stress-test\tools\stress_a_phases.py`.
  2. Walk an `audited` session through `manage → preflight → execute → audit → reduce`, call `reduce_round`, read `session.next`, and attempt `close_session` in `reduce` and after advancing back to `manage`.
- **Evidence (`tools/stress_a_phases.py`):**
  - `reduce:reduce_round` returns: `"next": "round 1 is reduced: advance starts the next round at manage, or close_session naming what is unresolved: R1 (open)"` (and `session.py:1079` returns `"every requirement is accounted for: close_session(summary, gaps)"` when complete).
  - Calling `close_session` in `reduce` fails:
    ```json
    "offered": false, "refused": "TOOL_BUNDLE_REFUSED",
    "detail": "'close_session' is not in this turn's task-sized tool bundle (advance, audit_projection, macro_plan, macro_run, read_result, reduce_round)..."
    ```
  - Calling `close_session` in `manage` fails with `TOOL_BUNDLE_REFUSED`. None of the 5 `audited` bundles (`manage`, `preflight`, `execute`, `audit`, `reduce`) includes `close_session`.
- **Suspected cause:** `src/resource_librarian/agent_runtime.py:553-566` omits `"close_session"` from `BUNDLES["reduce"]` (and `BUNDLES["manage"]`). `scripts/phase_walk.py` missed it because it only checks `Session.missing()` and only walks `explore`, `add_project`, and `suggest`.
- **Suggested fix:** Add `"close_session"` to `BUNDLES["reduce"]` (and consider `BUNDLES["manage"]`), and add `audited` (plus `apply`, `start_pursuit`, `learn`, `add_capability`) and terminal `session.next` closure verification to `scripts/phase_walk.py`.

---

### F-07 — `ui/smoke.mjs` fails on `dbb08b7` (3 regressions) + root cause of pre-existing `497×450` failure diagnosed

- **Severity:** `high`
- **Tag:** `verified`
- **Regression?:** **Yes** for lines 142, 238, 258 (`3d50b2f` + `dbb08b7`); **No** (pre-existing on `da7bf8a`) for line 264 (`497×450`).
- **Steps to reproduce (reproduced 2× on `dbb08b7` via `node run-smoke.mjs` and 2× on `da7bf8a` via `tools/run_smoke_on_base.mjs` + `tools/diag_smoke_497_run.mjs`):**
  1. On `HEAD` (`dbb08b7`), run `Set-Location D:\Librarian_V2\ui; node run-smoke.mjs`.
  2. On baseline `da7bf8a`, run `node reports\2026-11-19-stress-test\tools\diag_smoke_497_run.mjs`.
- **Evidence:**
  - On `dbb08b7`: fails immediately at `ui/smoke.mjs:142`: `Error: expected: the default pane leaves room for the primary workspace` because `openGuideOnFirstVisit()` (`ui/src/main.ts:292-299`) auto-opens `.lib-pane` on fresh libraries. Lines 238 & 258 (`#lib-attach .lib-menuitem:has-text('Projects/')` and `Scroll fixture 120`) are also invalidated because `dbb08b7` moved file browsing out of `#lib-attach` into Document Pane Pick Mode.
  - On `da7bf8a` (`diag_smoke_497_run.mjs`): reproduced exact `Error: expected: paperclip fits and scrolls at 497x450` at `ui/smoke.mjs:264`:
    ```json
    "box":  {"top":191.0625, "bottom":217.0625, "w":420, "h":26},
    "area": {"top":203.34375,"bottom":225.0625, "w":497, "h":21.71875},
    "cs":   {"position":"absolute", "top":"-12.2812px", "bottom":"0px", "maxHeight":"min(512px, 100% - 16px)"},
    "headerH": 132
    ```
    At `497×450` with an active thread, the wrapped `<header>` (`132px`) + session strip + composer consume `428.3px` of the `450px` height, shrinking `main.lib-chatview` (`area`) to **`21.72px`**. `.lib-popover.lib-attach` has `padding: 12px; border: 1px` (`26px` minimum height) + `margin-bottom: 8px`, pushing `box.top` to `191.06 < area.top (203.34)` (`fits: false`).
- **Suspected cause:** `ui/src/style.css:156-166` anchors `.lib-popover.lib-attach` inside `main.lib-chatview` (which collapses to `21.7px` when `<header>` wraps to 3 rows at `497×450`); and `ui/smoke.mjs` was not updated for first-visit Guide auto-open or the paperclip menu refactor.
- **Suggested fix:**
  1. Smallest fix for `497×450` layout: compact `<header>` and `.lib-compose` under `@media (max-width: 600px), (max-height: 520px)` (or single-row horizontal-scroll header) so `main.lib-chatview` keeps usable height, AND anchor `.lib-popover.lib-attach` / `.lib-modes` against `.lib-app` with `max-height: min(32rem, calc(100% - 16px))`.
  2. Update `ui/smoke.mjs` to handle first-visit Guide (asserting Guide opens, then closing pane or adjusting line 142) and test Browse Pick Mode + 120-item scroll in the Document Pane instead of `#lib-attach`.

---

### F-08 — Skill Registry has unescaped Markdown/table/phishing-link injection and breaks its own `/review-staging` row

- **Severity:** `medium`
- **Tag:** `verified`
- **Regression?:** **Yes** (new feature in `dbb08b7`). *(Note: raw HTML / `<script>` / `javascript:` / `data:` XSS is safely blocked by `ui/src/markdown.ts`, verified in live Chrome DOM.)*
- **Steps to reproduce (reproduced 3× — Pass 1 & Pass 2 live UI, `tools/stress_f_backend.py` ×2, `tools/stress_e_playwright.mjs`):**
  1. Open `Paperclip → Open skill registry` in the live UI and inspect the `/review-staging` row in the Skills table.
  2. Run `tools/stress_f_backend.py` and `tools/stress_e_playwright.mjs` with an adversarial server entry (`name: "evil` | on | 99 | <img ...>"`, `docs: "https://ok.example> [CLICK ME](https://phish.example) | [[About/Rules]]\n\n## Injected Heading"`).
- **Evidence:**
  - Live UI (Pass 1 & Pass 2): the 3-column table (`["Command", "Takes", "What it does"]`) splits `/review-staging` across **4 `<td>` cells**: `["/review-staging", "`[source", "lens]`", "Review what waits in staging, a page at a time"]`.
  - Live Chrome DOM (`stress_e_playwright.mjs`):
    - XSS held (`xssExecuted: false`, `imgTags: 0`, `scriptTags: 0`, `<javascript:alert(1)>` rendered as text).
    - Injection confirmed: `links` contained clickable `{"text": "CLICK ME", "href": "https://phish.example"}` and wikilink `{"text": "Rules", "href": "#"}`; `rowCellCounts` broke to `[7, 4, 5]` (3 spoofed columns); and `<https://ok.example>` rendered with literal `<` `>` characters.
- **Suspected cause:**
  - `src/resource_librarian/skill_registry.py:16` contains unescaped `|` in `"[source | lens]"`.
  - `src/resource_librarian/skill_registry.py:61-64` interpolates server `name` and `docs` directly into a Markdown table cell without escaping `|`, `` ` ``, `\n`, `[`, `]`, or validating `docs` is an `http(s)://` URL (and formats `<{docs}>` though `markdown.ts` does not parse `<url>` autolinks).
- **Suggested fix:** Escape `|`, `` ` ``, newlines, and `[[` using the same helper style as `reference.py`, validate `docs`/`homepage` against `^https?://` with no whitespace/control chars and render as `[docs](url)` (plain text otherwise), and escape `[source \| lens]` in `skill_registry.py:16`.

---

### F-09 — `GET /api/file?path=<stem>` bypasses `_visible()` on symlinks, reads outside files, and crashes `do_GET`

- **Severity:** `medium`
- **Tag:** `verified`
- **Regression?:** No (pre-existing in `da7bf8a`).
- **Steps to reproduce (reproduced 2× via `tools/stress_f_backend.py`):**
  1. Create a file outside the vault (`secret_outside.txt`) and a symlink inside `Notes/escape_link.md` pointing to it.
  2. Call `GET /api/file?path=Notes/escape_link.md` (properly returns `403 outside the vault`), then call `GET /api/file?path=escape_link` (no slash, triggering the fallback scan).
- **Evidence (`tools/stress_f_backend.py` ×2):**
  - Server traceback:
    ```
    File "D:\Librarian_V2\src\resource_librarian\app.py", line 4530, in do_GET
      return self._json(200, app.read_file((query.get("path") or [""])[0]))
    File "D:\Librarian_V2\src\resource_librarian\app.py", line 4237, in read_file
      return {**catalogue, "path": path.resolve().relative_to(root).as_posix(), ...
    ValueError: '...\secret_outside.txt' is not in the subpath of '...\api_vault'
    ```
  - Client received `RemoteDisconnected` (no HTTP response) because `do_GET` (`app.py:4560`) only catches `ApiError`, unlike `do_POST` (`app.py:4598`). Worse, `notes.load(path)` (`app.py:4234`) already opened and parsed the outside file before line 4237 raised `ValueError`.
- **Suspected cause:** `src/resource_librarian/app.py:4221-4228` uses `self.vault.root.rglob("*.md")` without calling `self._visible()` or verifying `found.resolve().is_relative_to(root)`.
- **Suggested fix:** Check `found.resolve().is_relative_to(root)` inside the `rglob` loop (skipping symlinks escaping the vault) and catch unexpected `Exception` in `do_GET` to return a clean JSON `500` instead of dropping the connection.

---

### F-10 — `/api/attach` (`notes.safe_name`) accepts Windows reserved device names (breaking `vault_commit`), strips Unicode, and drops extensions on long filenames

- **Severity:** `medium`
- **Tag:** `verified`
- **Regression?:** No (pre-existing in `da7bf8a`).
- **Steps to reproduce (reproduced 2× via `tools/stress_f_backend.py` + `git add` verification):**
  1. `POST /api/attach?name=<fname>&dir=Inbox` with raw bytes for `CON`, `CON.txt`, `NUL.md`, `AUX.pdf`, `PRN.txt`, `café_日本語.txt`, and `("a" * 300) + ".txt"`.
  2. Run `git init && git add -A` in the vault (matching `vault_commit`).
- **Evidence (`tools/stress_f_backend.py` ×2):**
  - Reserved Windows names all returned `HTTP 200` and created `Inbox/CON`, `Inbox/CON.txt`, `Inbox/NUL.md`, `Inbox/AUX.pdf`, `Inbox/PRN.txt`; subsequently `git add Inbox/CON` / `git add Inbox/CON.txt` / `git add Inbox/NUL.md` / `git add -A` all failed with `rc=128`: `error: open("Inbox/CON"): No such file or directory / fatal: adding files failed`.
  - Unicode filename `café_日本語.txt` was mangled to `Inbox/caf_.txt` (`SAFE_NAME = re.compile(r"[^A-Za-z0-9 &_.,()'+-]")`).
  - 304-char filename `aaa...a.txt` was truncated to 150 `'a'` characters, **dropping the `.txt` extension**.
- **Suspected cause:** `src/resource_librarian/notes.py:213-218` (`safe_name`) strips all non-ASCII letters, never rejects/prefixes Windows reserved device stems (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`), and truncates the whole string `[:150]` rather than preserving `suffix`.
- **Suggested fix:** Preserve the file extension when truncating (`stem[:150 - len(suffix)] + suffix`), prefix/rename Windows reserved stems (`_CON.txt`), and allow Unicode word characters (`\w` minus OS-illegal punctuation) instead of ASCII-only `A-Za-z0-9`.

---

### F-11 — No-progress guard has 3 false negatives and 1 false positive

- **Severity:** `medium`
- **Tag:** `verified`
- **Regression?:** **Yes** (new mechanism in `3d50b2f`).
- **Steps to reproduce (reproduced 3× via `tools/stress_a_phases.py`):**
  1. Run `D:\Librarian_V2\.venv\Scripts\python.exe reports\2026-11-19-stress-test\tools\stress_a_phases.py`.
- **Evidence (`tools/stress_a_phases.py`):**
  ```json
  "no_progress_guard": {
    "fn_alternating_refusals": { "stopped": "", "provider_calls": 13, "evaded_guard": true },
    "fn_repeated_ordinary_errors": { "stopped": "", "provider_calls": 9, "evaded_guard": true },
    "fn_repeated_bad_args": { "stopped": "", "provider_calls": 9, "evaded_guard": true },
    "fp_160_char_truncation_collision": { "equal_despite_diff_after_160": true },
    "control_identical_advance": { "stopped": "no_progress", "provider_calls": 4 }
  }
  ```
- **Suspected cause:** `src/resource_librarian/loop.py:296-308,1310` tracks only a single consecutive signature (`last_sig == sig`), ignores non-refusal errors (`error: "invalid_arguments"` and tool exceptions/errors where `refused` is absent), and truncates `detail[:160]` (colliding distinct refusals with long shared prefixes).
- **Suggested fix:** Include `invalid_arguments` and ordinary `error` outcomes in `_no_progress_signature`, hash the full detail string instead of truncating at 160 chars, and detect small cycles (e.g. rolling window of last 8 calls with ≥4 identical or repeating 2-step ABAB failure patterns).

---

### F-12 — Remaining phase-bundle and gate-hint gaps (`learn/next` `task_add` hint, `park_session`, backwards `advance`)

- **Severity:** `medium`
- **Tag:** `verified`
- **Regression?:** No (pre-existing, missed by `3d50b2f`'s bundle/hint cleanup).
- **Steps to reproduce (reproduced 3× via `tools/stress_a_phases.py`):**
  1. Run `D:\Librarian_V2\.venv\Scripts\python.exe reports\2026-11-19-stress-test\tools\stress_a_phases.py`.
- **Evidence (`tools/stress_a_phases.py`):**
  - **`learn/next` gate hint breaks schema:** `session.py:940` outputs `"review dates as tasks - task_add(text='Review: <concept>', due=..., heading='Understanding')..."`, omitting required `note`. Calling `task_add` verbatim per the hint fails: `"error": "invalid_arguments", "detail": "missing required argument(s) ['note']"`.
  - **`park_session` missing from every active-phase bundle:** `session.py:1073-1074` tells the model when budget is spent `"only advance, park_session, ask_user and update_plan still work here"`, yet in `map` (and all other active phase bundles) `"park_session_offered_in_map": false`, `"park_in_map_refused": "TOOL_BUNDLE_REFUSED"`.
  - **Cannot go backwards from terminal phases:** `"back_from_check_out": {"advance_offered_in_check_out": false, "refused": "TOOL_BUNDLE_REFUSED"}` and `"back_from_learn_next": {"advance_offered_in_next": false, "refused": "TOOL_BUNDLE_REFUSED"}`.
- **Suspected cause:** `src/resource_librarian/session.py:940` (missing `note=` in hint) and `src/resource_librarian/agent_runtime.py:503-539` (`park_session` omitted from active bundles; `advance` omitted from `check-out` and `next`).
- **Suggested fix:** Update `session.py:940` to `task_add(note='<concept>', text='Review: <concept>', due=..., heading='Understanding')`, add `advance` to `check-out` and `next`, and either include `park_session` in active bundles (or when `budget_left() == 0`) or remove it from the spent-budget hint.

---

### F-13 — `Modes` popover clips above viewport at `640×450` / `497×450`, and `768×1024` Document Pane covers `Staging`

- **Severity:** `medium`
- **Tag:** `verified`
- **Regression?:** Partial — `Modes` overflow was pre-existing in `da7bf8a`; `768×1024` overlay hiding `Staging` is worsened by `3d50b2f` auto-opening the Guide pane on first visit.
- **Steps to reproduce (reproduced 2× — Pass 2 live browser + `tools/stress_e_playwright.mjs`):**
  1. At `640×450` (200% zoom equivalent) or `497×450`, click `Modes: Ask ▾` and inspect `.lib-popover.lib-modes` bounding box.
  2. At `768×1024` with the Document Pane open, click the `Staging` tab in the header.
- **Evidence:**
  - `stress_e_playwright.mjs` (`modes_popover_clip`): at both `640×450` and `497×450`, `top: -89.5, height: 350.2, clippedTop: true, maxHeight: "none", overflowY: "visible"` (Pass 2 live browser: `y = -114.09px` at `640×450`).
  - `stress_e_playwright.mjs` (`pane_768_covers_staging`): at `768×1024` after clicking `Staging`, `paneRect: { x: 0, y: 95.94, w: 768, h: 928.06 }`, `centerElementInsidePane: true, paneClosed: false` — the pane obscures 100% of `Staging`.
- **Suspected cause:**
  - `ui/src/style.css:171` sets no `max-height` or `overflow-y: auto` on `.lib-popover.lib-modes`.
  - `ui/src/style.css:63-65` makes `.lib-pane` `position: absolute; inset: 0; z-index: 5` at `max-width: 900px`, and switching primary nav tabs (`Chat` → `Staging` / `Search`) does not dismiss the overlay pane.
- **Suggested fix:** Add `max-height: min(28rem, calc(100vh - 120px)); overflow-y: auto;` to `.lib-popover.lib-modes`, and automatically close the Document Pane when switching primary views (`Staging`/`Search`) under the `≤900px` overlay breakpoint.

---

### F-14 — Pick Mode leaks state when closing the pane and generates broken/ambiguous wikilinks

- **Severity:** `medium`
- **Tag:** `verified`
- **Regression?:** **Yes** (new feature in `dbb08b7`).
- **Steps to reproduce (reproduced 2× live in Pass 1 & Pass 2 on `http://127.0.0.1:58972/`):**
  1. Click `Paperclip → Link a note or folder from the library` (Document Pane opens in Pick Mode).
  2. Click the pane close button (`✕`), then reopen the Document Pane.
  3. Also pick `Notes/SubA/SharedName.md` (when `Notes/SubB/SharedName.md` also exists) and `Notes/edge]]hash#tick\`note.md`.
- **Evidence:**
  - Closing the pane (`✕`) and reopening left Pick Mode active (`pickBannerAfterReopen: true`, `cancelBtnAfterReopen: true`); clicking `Cancel` cleared it.
  - Picking `Notes/SubA/SharedName.md` inserted `[[SharedName]]` (ambiguous with `Notes/SubB/SharedName.md`).
  - Picking `Notes/edge]]hash#tick\`note.md` inserted `[[edge]]hash#tick\`note]]` (breaking wikilink syntax).
- **Suspected cause:** `ui/src/pane.ts:126` clears `this.pick` only on view change (`if (view !== "Browse") this.pick = null`), not when the pane is closed (`main.ts` `showPane(false)`). `ui/src/pane.ts:315,329` unconditionally emits `` `[[${e.name}]]` `` instead of checking uniqueness or special wikilink characters.
- **Suggested fix:** Add a `cancelPick()` hook called by `showPane(false)` and library switch; emit vault-relative path (`[[Notes/SubA/SharedName|SharedName]]` or path code span when `]]`/`|`/`#` appear) when basenames collide or contain wikilink syntax characters.

---

### F-15 — Chat model filter still leaks 8 `FLUX-*` image models (and `Llama-Guard`), while unanchored `NOT_CHAT_NAME` hides valid chat models

- **Severity:** `medium`
- **Tag:** `verified`
- **Regression?:** **Yes** (incomplete fix in `3d50b2f`).
- **Steps to reproduce (reproduced 2× — Pass 1 live UI + `tools/stress_f_backend.py` ×2):**
  1. Open Composer `Model ▾` or `Settings → Models & services → Choose the Lead model` on DeepInfra.
  2. Run `tools/stress_f_backend.py` (`test_not_chat_regex_audit`).
- **Evidence:**
  - Live UI (Pass 1): 8 `black-forest-labs/FLUX-*` image-generation models still appeared in the filtered chat model list, and Composer's `Model ▾` picker lacks the `"Show all"` toggle that Settings has.
  - `stress_f_backend.py`:
    - `catalog_potential_leaks`: `Llama-Guard-4-12B - deepinfra` (modality `""`).
    - `unprofiled_non_chat_leaking_past_NOT_CHAT_NAME`: `black-forest-labs/FLUX-1-schnell`, `black-forest-labs/FLUX-1.1-pro`, `stabilityai/sdxl-turbo`, `Qwen/Qwen3-Reranker-8B`, `Qwen/Qwen3-Embedding-8B`, `ByteDance/SDXL-Lightning`, `meta-llama/Llama-Guard-4-12B`, `google/imagen-3`.
    - `unprofiled_legit_chat_hidden_by_NOT_CHAT_NAME`: `Snowflake/arctic-instruct`, `bosonai/higgs-llama-3-70b`, `org/watts-llm-7b`, `org/potts-chat-8b`, `org/gasr-chat-7b`, `mistralai/Voxtral-Small-24B-2507`.
- **Suspected cause:** `ui/src/panels.ts:219-222` misses `flux|sdxl|rerank|imagen|guard|embed` (unanchored) in `NOT_CHAT_NAME`, while using unanchored substrings `tts`, `asr`, `higgs`, `arctic`, `voxtral` without word/token boundaries.
- **Suggested fix:** Add token boundaries (`(^|[-_/.])(...)(?=[-_/.]|$)`) for `tts`, `asr`, `embed`, `rerank`, `flux`, `sdxl`, `imagen`, `guard`, remove overbroad brand names like `arctic`/`higgs` when not paired with `-embed`/`-audio`, and expose the `"Show all"` toggle in the Composer Model picker as well.

---

### F-16 — Guide, `adopt`, auto-continue parity, and minor wrapping leftovers

- **Severity:** `low`
- **Tag:** `verified`
- **Regression?:** **Yes** (`3d50b2f` / `dbb08b7` new features & incomplete wrapping fixes).
- **Steps to reproduce (reproduced 2× via `tools/stress_f_backend.py`, Pass 1 live UI, and `ui/src/chat.ts` / `ui/src/main.ts`):**
  1. Run `tools/stress_f_backend.py` (`test_init_adopt_and_tool_ref`): adopt an existing folder via `content_roots.apply_adopt(...)` and inspect generated files.
  2. Compare `ui/src/chat.ts:861` (Chat question card) vs `ui/src/chat.ts:943-953` (Plan pane question box) and inspect Plan after answering a reopened thread's question in Chat (Pass 1).
  3. Inspect `localStorage` key `librarian:guide-seen` (`ui/src/main.ts:293-296`) and `Settings → Methods & lenses` / `Agent profiles` at `1280×900` (Pass 1).
- **Evidence:**
  - `stress_f_backend.py` ×2: `adopt_has_guide: false, adopt_has_tool_ref: false, adopt_has_rules: false` (`apply_adopt` creates only `.librarian`, unlike `init`).
  - `ui/src/chat.ts:943-953`: answering a reopened thread's question via the Plan panel does **not** call `this.hooks.resend("Carry on from my answer.")` (unlike the Chat card at `chat.ts:861`), and answering via the Chat card left Plan's `Waiting for you` card stale until a subsequent tool updated Plan (Pass 1).
  - `ui/src/main.ts:293,296`: `librarian:guide-seen` is origin-scoped (`http://127.0.0.1:<port>`), so switching libraries on one Core suppresses the guide for library 2 while restarting with `--port 0` re-opens it on every new port.
  - Pass 1 live UI at `1280×900`: `Methods & lenses` (`history-sources`, `source-assessment` `Accept`) and `Agent profiles` (`History…`) still wrap onto 2 lines.
- **Suggested fix:** Have `apply_adopt` optionally seed `About/Rules.md`, `About/Tool Reference.md`, and the starter guide (non-destructively, just like `init`); key `guide-seen` by library ID/path (`guide-seen:${vault_path}`); unify the answer handler between Chat and Plan (refreshing `session_status` and auto-continuing when `!out.resumed`); add `white-space: nowrap` on the remaining lens/profile action buttons.
