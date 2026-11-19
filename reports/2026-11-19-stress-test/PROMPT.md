# Stress-test round for Librarian V2 (review only)

You are the reviewer for a full stress-test round. Your job is to **find what is broken, unsafe,
inconsistent or fragile, and prove it**, not to fix it. Treat every claim in this brief, and in the
earlier reports, as something to check rather than something to trust.

## 0. Ground rules (read first)

- **Review only.** Do not edit, commit or push anything under `D:\Librarian_V2`. If you need to try a
  change, make a throwaway git worktree outside the repo (`git worktree add <tmp> <ref>`), never
  switch branches in the shared checkout (another agent may be working in it).
- **Do not touch** the ACCEPT-02 library or its Core, `E:\DataManagement`, or any running Core you
  did not start. Run `python -m resource_librarian host status` (from `D:\Librarian_V2` with
  `.venv\Scripts\python.exe`) to see which Cores exist, and leave them alone.
- **Work only in scratch libraries you create** in your own temp folder:
  `.venv\Scripts\python.exe -m resource_librarian init <dir> --name "<name>"`, then start a Core
  with `.venv\Scripts\python.exe -m resource_librarian --vault <dir> app --port 0` (it prints its
  URL; stop it by its port when done; a stopped Core can leave a stale lease, which needs
  `--takeover` only after you have confirmed that process is gone).
- **Spend cap.** Add `[budget]` / `ceiling_usd = 0.5` to each scratch library's
  `.librarian/config.toml` before any model call. Keep your total model spend under **$3**. Report
  what you spent (the vault's usage log, or `usage_log.budget(vault)`).
- **Do not change Settings → Models & services, effort, or any shared default.** Chat-model and
  effort changes also update the defaults of every other library on this machine. A new library
  inherits the current ones, which is all you need.
- Never print or store API keys. Models are reached through the keys already in the environment.
- Windows + Git Bash quirks: use `MSYS_NO_PATHCONV=1` for anything with a leading `/api/...`;
  heredoc Python turns `\n` into real newlines, so write files with the editor tools instead;
  a Core's loopback API needs the owner connection record (`resource_librarian.connection.load`)
  and the header `X-Librarian-Token`.
- For the browser, use the real Chrome extension or the built-in browser; both can reach
  `127.0.0.1`. Do not click through anything on a library that is not yours.

## 1. What changed (the surface under test)

Branch `feat/geo-per-library-service`, baseline `da7bf8a`, two commits to review:
`git diff da7bf8a..dbb08b7 --stat` and `git log da7bf8a..dbb08b7`.

1. **Phase deadlocks fixed.** Each phase's tool bundle (`agent_runtime.BUNDLES`) now offers the tools
   its exit gate (`Session.missing`) asks for; 16 phases of other purposes gained bundles;
   `MAX_BUNDLE_TOOLS` is 16; `suggest` opens its brief in Map; `capability_candidates` left the
   upkeep list. A turn now ends after 4 identical refusals (`loop._no_progress_signature`,
   stop reason `no_progress`). Gate hints use `update_plan(fields={...})`.
2. **Clerk / staging / macros.** A queued Clerk draft carries its reason; the page reloads the item
   after it. `run_macro` reuses an approved checkpoint for an identical plan when no
   `checkpoint_id` is given.
3. **Permission grants.** `Broker` honours `ctx.extras["workflow_grant"] = {"label", "tools"}`: a
   workflow a person starts (`App.start_action`, tools = `workflows.granted_actions`) and the
   approved ingestion batch (`batch.STAGE_TOOLS`) run in Ask mode without a question per write.
   Deny, Plan, a tool set to Ask, `ALWAYS_ASK` (`project_edit`, `sandbox_output`) and publication
   review still apply.
4. **UI.** The paperclip menu now holds Attach, "Link a note or folder" (opens the pane on Browse
   in pick mode), "Open skill registry" (`GET /api/skills`, a generated page in the pane) and "Run
   a workflow"; Modes holds only the permission mode. Workflow hints plus visible "Result:" lines
   and per-shortcut explanations come from `ui/src/workflows.ts`. Folder cards move to an Accepted
   filter; lists show "Showing N of T" and "Show 50 more"; chat model pickers hide non-chat
   models; many contrast/wrapping fixes; an answered question on a reopened thread auto-continues.
5. **Guide.** A new library gets `About the Librarian and how to use it.md` at its root and a
   generated `About/Tool Reference.md`; the note pane opens on the guide on a browser's first visit.
6. **Tooling.** `scripts/phase_walk.py` (gates, probe, scripted walks, `--prepare` to park sessions
   in a phase) and tests `test_phase_bundles.py`, `test_guide_note.py`, `test_workflow_grant.py`,
   `test_skill_registry.py`.

Prior reports (read them, then try to break their conclusions): `reports/2026-11-18-ui-review/`
(`PAGE-REVIEW.md`, `PHASE-WALK-FINDINGS.md`, `SESSION-REPORT-ASSESSMENT.md`, `FIXES-APPLIED.md`).

## 2. Method

For every finding: **reproduce it twice**, say how (exact steps, URL/viewport, command, input),
paste the evidence (output, DOM/JS result, log line, test), and tag it
`verified` (you reproduced it) / `plausible` (cause read, not reproduced) / `unverified`.
Say whether it **regressed** (check against `da7bf8a` in a throwaway worktree) or was already there.
Rank: **blocker** (data loss, unsafe, cannot proceed) / **high** / **medium** / **low**. Report
negative results too ("tried X, held"). An empty search is not evidence of absence.

## 3. Areas to stress (go deep; be adversarial)

**A. Phases and the model walk**
- Run `scripts/phase_walk.py` (all checks) and `.venv\Scripts\python.exe -m pytest tests/test_phase_bundles.py -q`.
  Then go beyond them: the scripted WALK only covers explore, add_project and suggest. Build walks
  for **apply** (tier consult), **start_pursuit**, **learn**, **add_capability** and **audited**, and
  run each end to end on the enforced surface.
- With a real model (use `--prepare` to park sessions in a phase, resume them through the UI, give
  directive prompts) drive **every phase of every purpose**, including going back (`advance` with a
  target), re-visiting a phase (budget halves), parking and resuming, rewind and branch, effort
  levels, and a profile whose `allowed_bundles` is restricted.
- Look for the next deadlock class: a tool offered but phase-gated (`PHASE_GATE`), offered but
  hidden by `narrowed()` (e.g. upkeep tools: `filters` in Frame and `provenance_check` in Judge are
  declared but dropped), tier mismatches, bundles clipped by the 16-tool cap with an extra required
  action, hint text that names a tool or argument shape the schema rejects.
- **No-progress guard:** try to produce false positives (a legitimate repeated refusal, a model
  waiting on a person) and false negatives (alternating calls, repeated *ordinary errors* that are
  not refusals, `ask_user` loops, a model that never calls `advance`).

**B. Permission grants (security-critical; think like an attacker)**
- Can an agent's own call ever carry a grant? Can a grant outlive its run, leak to another thread,
  another session, another library, a concurrent run, or a Core restart? (`batch.start` copies
  `ctx.extras`; `start_action` mutates the extras dict after the Context exists.)
- A grant covers `workflows.granted_actions(definition)`, which includes **vault-defined**
  pipelines and workflows. A definition file in the vault (agent-written?) naming write tools would
  authorise them the moment a person clicks it in "This vault's pipelines". Test whether a
  vault-origin definition can name `write_note`, `staging_decide`, `project_edit`, `sandbox_run`,
  `request_raw_source_access` and similar, and what actually happens. Decide whether the click is
  informed consent (does the menu show the steps?).
- Mode changes mid-run (Plan, then Auto), cancelling, resuming, Core shutdown during a run, a tool
  switched to Deny/Ask mid-run, `publication_review` taint, and the interaction with the
  `PERSON_CONFIRMS` / `promotion.mode` gates. Confirm nothing in the approved batch can accept a
  source or promote anything by itself.
- Try the 98-note scenario: approve many sources for ingestion, start the batch from the UI and as
  an agent through MCP (`process_approved`), in Ask mode, and count every permission request.
- `Broker._policy` is also called by `set_mode` for pending requests without a grant: check
  consistency.

**C. Checkpoints and macros**
- The approval-reuse change in `run_macro`: same scope twice, an expired approval, an approval of a
  plan whose inputs changed, two approved cards for one scope, a completed run re-asked, concurrent
  asks, an approval made by a different session. Can an approval be reused for something it was
  not given for? Also re-check the original loop (model asks again without the id).

**D. Staging, folders, Clerk**
- Staging pager ("Show 50 more") with 0, 1, 50, 51, 500 items; status filters; selection/ticks
  surviving a reload; stale revisions (Draft then Accept, two tabs, an external edit); the Clerk
  reason text for every refusal kind (route unqualified, key missing, host disabled, endpoint
  changed); the Accepted/Waiting folder filter after accept, re-survey and accept-policy.
- The approved batch itself: interrupt, resume, cancel, a failing stage, a source with no text
  layer, an extensionless file, 200 items; confirm only a problem is reported.

**E. UI, every page, every state**
- Pages: Chat, Staging (all seven kinds and every status), Search (every scope/intent, empty, long,
  special-character and `<script>` queries), Settings (all 12 sections), Models, Sessions,
  Checkpoints, library menu, ⏻ menu, the document pane (Note, Browse, Plan, This week), the
  paperclip menu, the Modes menu.
- Viewports 375x812, 497x450, 768x1024, 1280x900, 2124 wide; light and dark; keyboard only (Tab
  order, focus traps, Escape on every popover and dialog); reduced motion; zoom 200%.
- **Pick mode** (paperclip > Link a note): start it then switch pane tabs, close the pane, open a
  note by a link, switch library, press Cancel, pick a folder, pick from Recent, pick while a
  session is running; a file name containing `]]`, `|`, `#`, backticks or unicode; the Obsidian host
  path (`opts.openNote`), which must not break.
- **Skill registry** (`/api/skills`, rendered by `markdown.ts`): it prints a server's `docs` /
  `homepage` as `<url>` straight from a server definition. Try `javascript:`, `data:`, very long
  and HTML-bearing names/URLs; confirm the renderer sanitises links and text. Try it with the `mcp`
  extra absent and with a failing server.
- **Guide and first visit:** two tabs, cleared storage, a library made before this change (no guide),
  `init` into a folder that already has files or a vault of the same name, `adopt` and `attach`
  flows (do they get a guide?), a very old browser profile, the pane already saved closed.
- The earlier fixes: the ⏻ menu Escape/outside click, `Open original`, white search inputs in the
  dark dialog, queued-list cap, Written de-duplication, quality banner after cleanup, kind tabs at
  375px, chat model picker filtering (does a legitimate chat model ever get hidden? both `NOT_CHAT_*`
  regexes in `panels.ts`).
- The auto-continue on an answered question: can it fire twice, fire on a question that did resume,
  fire in a different thread, or run up cost?
- Known pre-existing UI smoke failure: `paperclip fits and scrolls at 497x450` (`ui/smoke.mjs`
  line 264). Reproduce on `da7bf8a`, find the real cause, propose the smallest fix.

**F. Backend, API and boundary**
- Every `/api/*` route you can find: missing/invalid token, wrong Origin/Host, oversized bodies,
  path traversal in `/api/file?path=`, `/api/files?dir=`, upload file names (`/api/attach`),
  Unicode and reserved Windows names, symlinks, a note named `..`.
- `init` / `adopt` / `attach` into awkward folders; the generated `About/Rules.md` and
  `About/Tool Reference.md` (large, special characters, a tool card containing `[[`, `|`, HTML).
- Concurrency and recovery: two tabs on one library, SSE reconnect, a Core killed mid-write, stale
  leases, a permission request nobody answers (timeout parks the session), the Host's per-user Core
  versus a standalone `app`.
- Packaging: confirm the built wheel/bundle includes the starter note and `reference.py`
  (`pyproject.toml` package-data), the plugin/Obsidian host mounts the same UI bundle, and
  `ui/build.mjs` output matches committed `src/resource_librarian/ui/*`.

**G. Real-model behaviour**
- With the default chat models, run the same tasks several times (variance), across tasks that
  need each phase, and watch for: invented tool or macro names, stray `</function>` / `</tool_call>`
  text persisted into chat, fake closure summaries, repeated tool calls, mis-shaped arguments
  (`record_assumptions` with the literal `tool`), cost per task.
- Confirm the hint and gate texts are enough for the model to find the path without a nudge.

**H. Regression sweep**
- Run the full suite (`.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --ignore=tests/ui_demo_core.py`,
  about 16 minutes; 2,702 should pass), `npm run check` and `npm run build` in `ui/`, and the UI
  smoke scripts. Diff the built bundle against a clean rebuild.

## 4. Known and deliberately open (do not report as new; add evidence if you can)

Inert Search tiles for `sessions`/`staging` scopes; the Suggest-sources form's "text" field and
silent success; Lens Accept/Reject/Defer not sticky; no UI for the library budget ceiling; shared
chat-model defaults propagate between libraries; no button to run a Clerk qualification; the
content-quality items (truncated claims, duplicate concept usages, casing/plural concept
duplicates, stray `</function>` text, reopening a closed session not clearing its summary,
activity-search date quirk); `filters` / `provenance_check` / `draft_offering` declared in bundles
but hidden by the loop; `record_application`'s refusal hint still teaches the old
`update_plan(no_application=...)` syntax (its access review would go stale if edited); the
`docs/` platform documentation is not copied into libraries.

## 5. Deliverable

Write to `D:\Librarian_V2\reports\2026-11-19-stress-test\` (create it; add only files there):

- `SUMMARY.md`: the top 10 findings by severity, a one-paragraph verdict on each of the six changes
  in section 1 (safe to keep / keep with fixes / revert), what you spent, and what you did not get to.
- `FINDINGS.md`: one entry per finding: id, title, severity, tag, regression?, steps, evidence,
  suspected cause (file:line), suggested fix.
- `COVERAGE.md`: a matrix of areas A-H against what you tried, what held, what broke, what was skipped.
- Any scripts you wrote (`tools/`), so the next round can re-run them.

Finish by listing every process you started and confirming you stopped it, and every scratch
folder you created. Do not commit.
