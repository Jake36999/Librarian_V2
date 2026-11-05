# Brief for Codex: the next UI/UX wave (2026-11-05)

You are continuing the front-end work on Librarian V2, starting from your Settings
redesign (`bce35ef`). Work through the remaining UI/UX fixes and improvements in this
brief, in order. Claude keeps working on the backend in the same checkout at the same
time. When you both have significant progress, the owner will run an integration pass.

## 1. Shared checkout: rules that keep us out of each other's way

We share **one working tree and one git index** at `D:\Librarian_V2`, on `master`.

- **Commit only your own files, by explicit path:**
  `git add <your files>` then `git commit -m "..." -- <your files>`. Never use
  `git add -A`, `git add .`, `git commit -a` or a bare `git commit`. Run
  `git diff --cached --name-only` first; unstage anything that isn't yours with
  `git restore --staged <file>`.
- **Never** stash, `git checkout --`, `git reset --hard`, revert another's files,
  or force-push. Pull nothing: commits from both of us land in the same tree.
- **Yours:**
  - `ui/src/*` and `ui/smoke.mjs`;
  - `obsidian/src/*`, plus `obsidian/dist/*` and
    `src/resource_librarian/ui/app.js`/`app.css` (generated: rebuild with
    `npm.cmd --prefix ui run build` and commit them with their sources);
  - `reports/2026-11-05-settings-qa/` and a new `reports/2026-11-05-ui-wave/`.
- **Claude's:**
  - Python under `src/resource_librarian/`, and `tests/` (except UI-contract
    tests you must extend, such as `tests/test_obsidian_adapter_contract.py`);
  - `docs/unified-implementation-plan.md` and `reports/2026-11-05-evidence/`.
  - If a packet needs a backend change, write what you need into
    `reports/2026-11-05-ui-wave/BACKEND-ASKS.md` rather than editing Python.
- **Your progress log:** keep it in `reports/2026-11-05-ui-wave/LOG.md`, one entry per
  packet: what changed, files, tests run, commit. Claude folds it into §19 at
  integration.
- **A failing backend test you didn't touch** is probably Claude's work in progress.
  Note it in your LOG and don't fix it.

## 2. Rules the tests enforce (keep them passing)

- **Vanilla TypeScript, DOM and CSS only.** No React, Vue, Tailwind or component
  libraries, and no new state store. Use the existing endpoints (`/api/state`,
  `/api/meta`, `/api/documents`, `/api/keys`, `/api/library`, `/api/tool`,
  `/api/tool-setting`, …).
- **Namespacing (MF-007):** every class is `.lib-*`. Use `cls()`/`sel()` from
  `ui/src/dom.ts` (`h()` applies `cls()` for you). Ids come from `claimInstance()`,
  so two mounts never collide.
- **Width follows the Librarian root, not the window (MF-008).** No
  `@media (...width...)`, no `vw` units. Use `@container librarian (max-width: …)`
  and `cqi`.
- **Overlays:** focus moves in, Escape closes them and is consumed only when they are
  open, focus returns to the trigger, and `dispose()` releases listeners and
  observers.
- **Hotkeys:** never bind keys Obsidian owns. Don't act while focus is in an editor or
  text field. In Obsidian, offer commands through `addCommand`.
- **Contract strings:** `tests/test_obsidian_adapter_contract.py` reads strings in
  `ui/src/main.ts` and `obsidian/src/main.ts`. Don't reword what it asserts.
- **Truth:** never fake progress, charges, diffs or receipts the backend doesn't send.
  Where the data isn't available, say it isn't (see
  `reports/2026-11-04-ui-framework-review/UI-PACKETS.md`, "Backend-dependent work").

Before each commit, run:

```bash
npm.cmd --prefix ui run build
```

```bash
npm.cmd --prefix ui run smoke
```

```bash
.venv\Scripts\python.exe -m pytest -q tests/test_obsidian_adapter_contract.py
```

## 3. Read first

1. `reports/2026-11-04-ui-framework-review/UI-REVIEW.md`, `UI-DESIGNS.md`,
   `UI-PACKETS.md`: your framework review and its packets UI-01 … UI-13.
2. `reports/2026-11-04-master-finalization/03-MASTER-FINALIZATION-PLAN.md` and
   `execution-queue.json`: the MF ids below, with their dependencies and done
   conditions.
3. `reports/2026-11-05-settings-qa/IMPLEMENTATION.md`: what `bce35ef` delivered.
4. Your own notes from the review session, in
   `C:\Users\jakem\Documents\Codex\2026-11-04\help-me-set-up-web-app\outputs\`
   (`settings-redesign-plan.md`, `research-synthesis.md`,
   `librarian-research-assessment.md`, the screenshots).

**Already done; don't redo:**
- MF-005 to MF-010 (UI-01 composer and Stop, UI-02 truthful feedback, UI-03 CSS
  isolation, UI-04 root-width layout, the minimum overlay lifecycle, UI-07 legacy
  histories, UI-08 stop reasons and revision forms);
- your Settings workspace (`bce35ef`).

## 4. The work, in order

### Step 0: reconcile `bce35ef` against the queue

For each of MF-031, MF-032, MF-033 and MF-034a/b/c, check the packet's **done**
condition in `execution-queue.json` against what `bce35ef` does. Record met, partly
met or not met, with evidence (file:line, smoke step), in
`reports/2026-11-05-ui-wave/STATUS.md`. Then do only what is left.

### Step 1: MF-025, focus, keys, tabs, splitter and touch (UI-05/06)

- Async overlays take focus once their content loads; Escape is owned and restores the
  trigger.
- Native modal trap; unique mounts; no leaked listeners.
- Arrow, Home and End keys move between tabs.
- A keyboard-operable, bounded splitter.
- On touch, `touchcancel` and dragging suppress clearing; `prefers-reduced-motion` is
  respected.
- Check that your new Alt+Shift shortcuts and the Obsidian commands follow the same
  ownership rules.

### Step 2: MF-031, role-explicit model selection (UI-11), whatever `bce35ef` left

- Explicit Lead / Notes / Small tasks selectors. They preserve untouched slots and the
  current override gate.
- Clearing is truthful about prefix and fallback; a service clear never posts tiers.
- Shared-default effects are labelled. Some chat-model and effort choices write
  defaults that libraries without their own choices inherit: say so; don't label
  everything "this library".

### Step 3: MF-033, simplify providers, tools and project access, whatever is left

- Provider summary and detail views; saving a key is separate from testing a
  connection, and nothing runs a paid probe automatically.
- Tool permissions expand on demand.
- A clear project read/write hierarchy, and the label "Context for chat replies".
- **New permission to surface (backend MF-015, being committed now):**
  `sandbox_output`. It decides whether a sandbox or Workbench run may keep the files it
  writes; nothing caps the disk while it runs. It is asked in every mode, Auto
  included, unless the person sets it to Allow; allowing the run never covers it.
  - Show it on the permissions page with Allow / Ask / Deny, set through
    `/api/tool-setting` with `{"tool": "sandbox_output", "setting": …}`.
  - Suggested copy: "Keep files a sandbox or Workbench run writes. Nothing limits
    their size while the run is going; they are checked afterwards."
  - Make its permission-request card readable. Its arguments are `writes_to`,
    `while_running` and `after_the_run`.

### Step 4: MF-034a, navigation (UI-12)

- A visible pane view switch: **Note | Browse | Plan | This week**. On a narrow pane,
  a labelled "View:" selector; tabs where there is room.
- The `⋮` menu holds only actions on the open note (Open in Obsidian, Rename or move,
  Copy path) and appears only when a note is open.
- Read aloud sits with the note actions and shows an obvious playing or stopped state
  with an accessible label.
- An empty Plan pane collapses instead of taking half the screen.
- Settings and Choose models stay reachable from Chat, Staging and Search (check what
  `bce35ef` already did).

### Step 5: MF-034b, Staging (Review) redesign

- **Purpose:** state it at the top, for example "Review captured material before
  adding it to this library".
- **Header:** count badges on the sub-tabs. Say whether a count covers all pending
  items or only the current filter. The filter and Refresh go on one toolbar row.
- **Layout:** a narrow queue, a central review area and a roomy evidence pane on a
  wide root, so the form and the evidence are no longer three crushed columns.
  Selecting an item makes its evidence available without replacing an unrelated open
  note.
- **Actions:** a clear hierarchy, with one-line explanations of what each action
  commits to. "Approve for ingestion" (process it) and "Accept as captured" (publish
  as is) are different commitments; keep both, and explain them.
- **Bulk:** bulk **defer** and bulk **approve for processing**, through the existing
  per-item decisions with their current revisions, each reporting its own outcome.
  **Never bulk accept or publish**, and never let fewer clicks imply evidence was
  examined.
- **Libraries:** keep the active library unmistakable, and keep queue position when
  switching libraries.
- **New backend states to show (MF-013, MF-020, already on master):**
  - a deep read whose earlier progress is stale. The UI already says so in
    `views.ts`; check the wording fits the redesign. `deep_read` results now carry
    `stale` and `text_changed`.
  - batch stages recorded `stale` ("the item's source changed while this stage ran"),
    listed under `processing.not_examined`.

### Step 6: MF-034c, Search redesign

- The query and the Search button take the full first row; the scope, type and date
  filters go on a second row.
- No truncated placeholder or scope label at the root widths the smoke test uses.

### Step 7: MF-026, operations and derived failures (UI-09)

- SSE connection state is shown separately from the writer, index, watcher and lease
  states.
- Accepted Markdown survives a visible embedding failure.
- Snapshots never fake progress; a failed update keeps its last-reported time.
- Polling is bounded, non-overlapping and disposed.

### Step 8: visual polish from the screenshot review

- Give recessed containers (queue lists, evidence readers, model cards) a slightly
  different surface tint, and give secondary buttons a subtle fill, so controls stand
  out from static text.
- Keep the warm palette; don't add a big new colour set.
- Remove the duplicated library name in the header (the `[Library ▾]` plus the same
  name as plain text).
- Contrast cannot be judged from screenshots: check the text and control contrast
  ratios you change.

### Step 9: new backend results the UI should present (already on master)

- **Workflow and pipeline runs:** a run paused with `reason: "outcome_unknown"`
  (MF-018) carries `options: ["retry", "applied"]`. Offer the person those two
  choices, which call `run_resume` with `choices: {<step key>: "retry"|"applied"}`.
  Explain them: "the step was sent but its result was never recorded; check, then
  send it again or record it as done". Only a person may answer.
- **Macros:** `status: "outcome_unknown"` with `next_action.options`. The person runs
  the macro again with the same `checkpoint_id` and `unknown_step`.
- **Text-to-speech spend (MF-019):** `spent_usd` now includes reservations still held
  for calls whose outcome is unknown. Label it "spent or held".
- **Sandbox run results:** `output.kept` (MF-015) and `notes` say when no files were
  kept because output wasn't permitted. Show that instead of an empty file list.
- **Index stats (MF-014):** `orphaned_document_chunks` counts attachment text that is
  waiting for an ambiguous move to settle. If shown at all, it belongs in Diagnostics.

### Step 10: MF-035, installed UI and adapter qualification (required)

Do the in-repo part:
- the packaged smoke (`ui/packaged-smoke.mjs`) against the built wheel;
- the installed CSS and JS containment checks;
- artifact hashes and protocol recorded in your LOG.

Leave the real-Obsidian hotkey and mixed-host checks as a named, open host-acceptance
item. Mocked rendering never counts as a real-host success.

### Not yours, for now

- MF-027 (reply-review identity, exact staged previews, Claim Run Docker preflight)
  needs backend payloads first (MF-016, MF-023 and MF-024, in Claude's lane). Don't
  build UI for receipts or diffs that aren't sent yet.

## 5. Validate as hypotheses

The research you gathered supports these changes as hypotheses; it doesn't prove them.
When Steps 4–6 are in, run a short task check with a fresh profile and record it in
your LOG:
- find Settings from Staging;
- resolve a missing-model warning from Review;
- explain the difference between processing and accepting;
- find a staged item's source evidence;
- tell pane navigation from note actions.

Record completion and the obstacles. Don't claim usability improved without it.

## 6. When you stop

Leave `reports/2026-11-05-ui-wave/STATUS.md` current: each packet as done (with its
commit), partly done or not started, and anything waiting on the backend. Then tell
the owner you're ready for the integration pass.
