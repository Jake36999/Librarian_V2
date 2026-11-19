# Handover to the main workflow (2026-11-19)

What landed on `feat/geo-per-library-service` (Librarian) and `feat/per-library-service` (Geo-Grapher), mostly on
2026-11-18 and 2026-11-19, with the reports behind it. Pull both branches before starting the next item, so nothing
here is built twice.

- **§1** how the agent workflow was unblocked through the UI.
- **§2** what changed in the two UIs, and what is still open there.
- **§3** every report written by Claude and by Gemini (Antigravity), with where each stands.
- **§4** decisions that are the owner's. **§5** the open work, in the order I would do it. **§6** working notes.

Three cautions before reading on:
- **Finding ids collide.** "F-01" means a different thing in the stress test, the agent review and the workflow
  review. This file writes **ST-F01** (stress test), **AR-F01** (agent review) and **WF-D1** (workflow review).
- **Test numbers are from my last runs in this session.** I did not re-run the suites while writing this file.
- **Evidence tags.** *verified* = I read the code or ran it; *plausible* = consistent with the code, not run;
  *not checked* = I did not look. Gemini's claims carry the tag of my own check, not its confidence.

## State at handover

| | Librarian (`D:\Librarian_V2`) | Geo-Grapher (`F:\uv-data\Geo_Grapher`) |
|---|---|---|
| Branch and head | `feat/geo-per-library-service` at `593f56c` | `feat/per-library-service` at `541ce01` |
| Pushed | yes | yes (`42a4474..541ce01`) |
| Hosted CI | Core CI passed on `593f56c` (run 44563662822, 16 min 56 s); the three pushes before it passed too | not checked |
| Last local suites | full suite 2715 passed at `d1a08bb`; Geo-launcher tests 63 passed at `593f56c`; UI smoke passes | Python 923 passed, 1 skipped; graphs browser suite 42/42; main browser suite 37/38 (the known "search hides stale matches while a newer query is pending"); unit 58/58 |
| Deployed to the four libraries | Cores keep the code they started with; I did not restart any onto `593f56c` | wheel at `42a4474` (what the agent review tested); `541ce01` **not** deployed |

**Uncommitted in the Librarian tree** (the working tree is shared: another agent may edit it, so commit explicit
paths only):
- Modified: `docs/agent-guide.md` (adds "Managing Cores"), `reports/2026-11-12-progress/LIBRARY-ACCESS-API-SCOPE.md`,
  `reports/2026-11-17-ui-review/UI-REVIEW.md`, `reports/2026-11-19-stress-test/GEO-GRAPHER-REVIEW-ASSESSMENT.md`.
- Untracked: all of `reports/2026-11-19-agent-review/`, `2026-11-17-openclaw-scope/`, `2026-11-18-capability-tests/`,
  `2026-11-18-research-objectives/`, most of `2026-11-16-pilot-review/` and `2026-11-17-ui-review/`, and
  `2026-11-19-stress-test/GEO-GRAPHER-DESIGN-REVIEW.md` and `tools/`. This file too.

---

## 1. Unblocking the agent workflow through the UI

### 1.1 The defect

The in-app lead is offered only the current phase's compact tool bundle (`agent_runtime.BUNDLES`), and the
registry refuses anything else (`TOOL_BUNDLE_REFUSED`). Each phase also has an exit gate (`Session.missing`) that
tells the model what to call. Where a gate asked for a tool its own bundle left out, no model could leave that phase.

- **Seen live first in Map.** A model called `advance` 15 times in a row ("stayed: the phase is not finished") until
  the person pressed Stop. The "calls left" counter never moved, because refused advances cost no budget, so only the
  80-step turn cap bounded the spend.
- **Then shown to be the rule.** 7 of 8 session purposes had at least one phase a model could not leave, and 16
  phases had no bundle at all, so `apply`, `start_pursuit`, `learn` and `add_capability` could not work in the app.
- **Why the old walks missed it.** `tests/walks.py` calls the registry without bundle enforcement.

### 1.2 What was changed (commit `3d50b2f`, 2026-11-18)

| Fix | Where |
|---|---|
| Each bundle now offers what its gate asks for: Map `update_plan`; Need `open_brief`; Search `research_round`, `checkpoint`; Judge `decide`, `record_assumptions`; Synthesise `promote_offering`; Check-out `close_brief`, `update_plan` | `agent_runtime.BUNDLES` |
| 16 phases with no bundle now have one (ingest, check-in, find, inventory, plan, seed, goal, baseline, focus, practice, consolidate, next, candidate, assess, propose, install) | same |
| Tool cap 12 to 16. The cap clips from the end, so the new gate tools would have silently dropped `read_result`, `macro_run`, `macro_plan` | `MAX_BUNDLE_TOOLS` |
| `suggest` opens its brief in Map; `capability_candidates` is no longer hidden as "upkeep" in sessions | `required_bundle_actions`, `loop.UPKEEP_TOOLS` |
| 22 gate hints taught `update_plan(map=...)`; the tool takes `update_plan(fields={...})`. All match now | `session.py`, `tools/sessions.py` |
| A turn ends after 4 identical refusals in a row, with the cause, instead of running to the step cap | `loop.py` |
| A queued Clerk draft carries its real reason (for example "route not yet qualified"); the page reloads the item after it, which removes a stale-revision write conflict | `staging.review`, `ui/src/views.ts` |
| Asking again for an approved macro without the checkpoint id reuses the approval instead of minting another card | `agent_runtime.run_macro` |

### 1.3 How it is checked now

- **`scripts/phase_walk.py`** never calls a model. It reads each phase's gate text, forces a session into each
  phase, calls each gate tool through the **enforced** surface (`Loop.tools()`), and walks `explore`, `add_project`
  and `suggest` end to end. Exit status is 1 when anything is blocked, so it can guard a build. Result: 133 probes,
  0 unreachable, 0 hint mismatches; scripted walks 23/23, 25/25, 22/22.
- **`tests/test_phase_bundles.py`** covers per-purpose clipping and that every gate hint uses syntax `update_plan`
  accepts.
- **Real model, scratch library, every previously blocked phase:** about $0.018 in total.

### 1.4 Second round: Gemini's stress test (against `da7bf8a..dbb08b7`)

Gemini found the `3d50b2f` deadlock fix held for 7 of 8 purposes (`audited` still could not close, ST-F06) and
listed ten top defects, five of them regressions from `3d50b2f` or `dbb08b7`. Fixed in `d1a08bb` (2026-11-19):

| Id | Defect | Fix |
|---|---|---|
| ST-F01 | "Show 50 more" never passed item 50 (it raised `limit`, the tool caps a call at 50) | reads by `offset` |
| ST-F02 | Macro approval reuse could bypass a later cancel, be hijacked by another session, block re-runs, and race | latest card only; same session and caller; not already spent; one run per approval at a time |
| ST-F03 | A vault-defined pipeline, once accepted, got arbitrary `contribute` writes in Ask mode with no disclosure | the workflow grant covers only shipped workflows; the menu says so under each vault pipeline |
| ST-F04 | Stop while waiting on a question or permission card wedged Chat | `cancel_turn` releases that turn's own waiters and denies its own permission requests |
| ST-F05 | Question `q1` in a second thread was silently dropped | cards keyed by thread; replay and reset clear them |
| ST-F06 | `audited` could not call `close_session` in any phase | offered in `reduce`; `phase_walk` now checks every purpose's last phase |
| ST-F07 | `ui/smoke.mjs` broken on `dbb08b7`, and a 497x450 paperclip failure | header compacts below 520 px of height; smoke updated; passes 3 of 4 runs (one timing flake) |
| ST-F08 | Skill registry rendered raw server text (table and link injection) | cells and code spans escaped; docs addresses shown as plain `http(s)` text only |

Parts of ST-F12, ST-F14 and ST-F16 were fixed in the same commit (see §2.3).

### 1.5 The permission model changed (commit `dbb08b7`)

Starting a workflow is now the permission for its own steps. The broker takes a scoped `workflow_grant` from the
run's own context, set for a workflow a person starts and for the approved ingestion batch (exactly the tools its
stages call), so Ask mode no longer asks once per write. Deny, Plan, a tool set to Ask and the always-ask tools
still apply, and an agent's own calls never carry a grant. ST-F03 closed the one hole in this (vault-defined
pipelines). Tests: `tests/test_broker.py`, `tests/test_workflow_grant.py`.

### 1.6 What can still block an agent or a newcomer

| Id | Problem | State |
|---|---|---|
| AR-F02 | ACCEPT-02's Lead model is the placeholder `lead-m` and 404s. It sits in that library's own `.librarian/app.json`, not in a code default. Nothing warns when a configured model id does not exist | not changed; owner decision (§4) |
| AR-F03 | An Ask-mode MCP write blocks for up to 600 s (the client gives up at 180 s) and the "Permission needed" card shows only in Chat | *plausible*; a pending-approval badge is a UI change, not done |
| AR-F10 | Staging has no "Add source" of its own; intake runs through Chat | *not checked*; not done |
| ST-F11 | The no-progress guard misses alternating refusals, repeated ordinary errors and repeated invalid arguments | not fixed |
| ST-F12 (rest) | `advance` back from check-out and next is still not offered | not fixed |
| WF-D1 to D6 | Workflow output, paused-run recovery, false success counts (§3.3) | newest Gemini report; spot-checked only |

---

## 2. Updates to the UI, and fixes

### 2.1 Librarian UI (`ui/src`, bundle rebuilt into `src/resource_librarian/ui/`)

**`3d50b2f` (2026-11-18)**
- Workflows explain themselves: the hover hint says what a workflow does, a visible "Result:" line says what it
  leaves behind (one source of truth, `ui/src/workflows.ts`). All 15 shortcuts in Settings are explained.
- **A guide in every new library:** `About the Librarian and how to use it.md` at the library root, linked to a
  generated `About/Tool Reference.md` and the formal notes. The note pane opens on it the first time a browser opens
  a library that has one. Older libraries have none, so nothing opens for them. The platform docs in `docs/` are
  not copied into libraries (the owner's call).
- Fixes: the close menu dismisses on Escape and outside click; capped lists say "Showing 50 of N" with a "Show 50
  more" button (the Queued list silently showed 50 of 93); the stale "the batch cleans it" quality banner is replaced
  once cleanup has run; chat model pickers hide embedding, image, video and speech models (with "Show all"); dark-mode
  contrast on `Open original` and note links; Staging kind tabs wrap on a phone; the Plan pane lists each written
  note once; wrong "Settings → Library" pointers name the real sections; checkpoint cards show their id with the raw
  JSON folded.

**`dbb08b7` (2026-11-18)**
- The paperclip menu is the one place for what a person brings in: "Link a note or folder" (opens Browse in the
  right-hand pane), "Run a workflow" (moved out of Modes, which now holds only the permission mode), and "Open skill
  registry" (the plugin's `/` commands, skills and agent, installed servers with a docs link, built from `/api/skills`).
- An answered question on a reopened thread (for example "Extend by 50 calls") carries the thread on.

**`d1a08bb` and `593f56c` (2026-11-19)**
- The library's own Geo-Grapher shows in Settings as a service (running, starting, failed, not set up) with a Start
  button. A hand-added stdio `geo-grapher` entry is never launched, because the name is reserved for the Core's service.
- `593f56c`: Geo's "Add folder" works inside a library's Geo. The Core passes each attached project folder that
  still exists as a browse root, and only while project access is on (AR-F05). Geo reads those folders and never
  writes to them. With none attached, Geo's page says how to attach one.
- Earlier in the stretch: Close menu per Core (close Geo-Grapher or the whole library) and a Geo-Grapher stopped from
  outside no longer reported as running (11-17, `7bed242`, `f4e8a4e`); MCP status shows a library-owned server by
  its endpoint, never its token (11-18, `da7bf8a`); a library's agents reach its own Geo-Grapher service (11-18,
  `0fa91f4`).

### 2.2 Geo-Grapher UI (`frontend/src`)

The owner's direction was: two jobs (explore a graph; build and use tools), a graph-first layout, and a Build panel.
Gemini's design review of the old screen and my own are in §3.

| Commit | Change |
|---|---|
| `bb5c708`, `fa33b96` (11-19) | More room for the canvas; every floating panel dismissible; one top bar; a canvas tool rail; a zoom slider; a right panel with modes (Inspect, Graphs, Build) |
| `f6b9e78` (11-19) | Build mode: add a folder with a folder map. Unlicensed sources are labelled, never gated |
| `42a4474` (11-19) | Build operators: per-folder **role override**; **Keep only / Remove** with counts first, producing a new derived graph and never changing the source; **Compare**; **declared links** (add and remove); per-graph **accent colours**. Neon single-colour threads: one colour fading from the source to show direction, a small arrow and metadata on hover, including declared links |
| `541ce01` (11-19) | The review fixes below |
| `3fc17d3`, `b4deea5`, `a3dd77d` (11-17) | Content-coloured nodes, faded cross-folder links, three graphs loaded at most, a compact in-memory form (59k entities: 750 to 182 MB) |

Geo-Grapher fixes from the agent review (`541ce01`), each tagged with its agent-review id:
- **AR-F01** an empty catalogue no longer freezes on "Opening project graphs…"; it explains and offers Add folder.
- **AR-F13** "Reveal nearby detail" no longer overlaps the canvas help (reproduced at 1440, 768 and 375 px, then gone).
- **AR-F14** Inspect wraps long ids and fits its five tabs.
- **AR-F19** the curve count includes documentary links. **AR-F20** (part) Escape closes the Legend.
- **AR-F23** (part) the sheet's close button no longer stretches.
- **AR-F15** the Build tab names the Box select tool and can start a cut from a selected file or folder.
- **AR-F08** (part) declared links say "declared by a person, not checked against the code".
- **AR-F04, AR-F06** Geo MCP: opt-in `--text-content` (or `GEOGRAPHER_MCP_TEXT_CONTENT=1`) also returns each result as
  JSON text, and the hub's tool descriptions no longer name arguments the flat tools reject. The empty `content`
  default is deliberate (it avoids doubling tokens), so I did not change it.
- After an ingest, the panel says where the new graphs went ("added 3 graphs… check one to show it").

### 2.3 Not fixed in either UI

- **Librarian:** AR-F03 approval badge, AR-F09, AR-F10 Staging intake, AR-F12 Search filters, AR-F17, AR-F18, AR-F21,
  AR-F24, AR-F25 (*not checked*); ST-F09 (`/api/file` symlink escape and a `do_GET` crash), ST-F10 (`safe_name`
  accepts Windows reserved names that break `vault_commit`), ST-F13 (at 900 px or less the pane overlay still covers
  Staging after a tab switch), ST-F14 (rest: ambiguous wikilinks for duplicate names or names containing `]]`, `|`
  or `#`), ST-F15 (some image and guard models still reach the chat picker), ST-F16 (rest: `adopt` does not seed the
  guide, `guide-seen` is per origin).
- **Geo-Grapher:** click an arc to jump to a declared link's target (AR-F08), pre-disable Compare when graphs have no
  fingerprints (AR-F16), Matrix header wrapping and Light-theme contrast (AR-F20), first-search latency of 71 s on a
  65k-entity graph (AR-F07, *not checked*), and the MCP shapes in AR-F06: `search_entities` hits omit `rel_path`,
  `compile_task_packet` rejects ids, `federated_search` ordering.

---

## 3. Reports

All paths are under `reports/`. **Authorship** is from my session logs (files a Claude session wrote) and from the
owner's statement that Gemini ran the reviews. Gemini's files link with `file:///` paths and carry no Claude session
write.

### 3.1 Written by Claude (me, and earlier Claude sessions)

| Report | What it is |
|---|---|
| `2026-11-19-agent-review/ASSESSMENT.md` | Checks every agent-review finding against the code; what I fixed; the owner decisions. **Start here for AR ids** |
| `2026-11-19-agent-review/PROMPT.md` | The brief for Gemini's review and live test of both products |
| `2026-11-19-stress-test/FIXES-APPLIED.md` | What `d1a08bb` fixed from the stress test, and what stays open |
| `2026-11-19-stress-test/GEO-GRAPHER-DESIGN-REVIEW.md` | My design review of the Geo-Grapher workspace (19 findings, P0 0, P1 6, P2 10, P3 3) against the owner's new direction, including the relational-operator mapping that became the Build tab |
| `2026-11-19-stress-test/GEO-GRAPHER-REVIEW-ASSESSMENT.md` | Gemini's Geo-Grapher claims, each measured live at 1440x900 and tagged verified or not checked |
| `2026-11-19-stress-test/PROMPT.md` | The brief for the stress-test round |
| `2026-11-18-ui-review/FIXES-APPLIED.md` | Every fix behind `3d50b2f`, with where and which test |
| `2026-11-18-ui-review/PHASE-WALK-FINDINGS.md` | The phase-deadlock class, the `phase_walk.py` tool, the table of blocked phases. **The reference for §1** |
| `2026-11-18-ui-review/PAGE-REVIEW.md` | Every Librarian page walked live (bugs B1 to B9, inconsistencies), read-only |
| `2026-11-18-ui-review/SESSION-REPORT-ASSESSMENT.md` | Checks the Antigravity session's bug reports against code and a live scratch library (about $0.006) |
| `2026-11-18-research-objectives/RESEARCH-OBJECTIVES.md` | One equal set of research objectives, merging Antigravity's plan with my review of `E:\DataManagement`. Nothing executed |
| `2026-11-18-capability-tests/CAPABILITY-AND-RECALL.md` | Search and recall measured after the large-sample acceptance (hit@5 of 0.97 to 1.00 on the libraries' own questions) |
| `2026-11-17-ui-review/` | `UI-REVIEW.md` (items 1 to 4 fixed, item 5 scoped, the **deploy and rollback procedure for the Geo wheel**), `ROUND-1.md`, `DIAGNOSTICS-AND-REQUIREMENTS.md`, `GPU-RENDERING-OPTIONS.md`, `VIEW-INDEX-SPIKE.md` and `spike/` |
| `2026-11-17-openclaw-scope/` | `OPENCLAW-INTEGRATION-SCOPE.md` (OpenClaw as a coding sub-agent foundation, not ingested) and `PARALLAX-GRAPH-PLAN.md` (graph split rules) |
| `2026-11-16-pilot-review/` | `PILOT-REVIEW.md` (ten-paper pilot, and Gemini's blind review checked), `INGESTION-RUN.md` (the budgeted run), `AUDIT-FIXES.md` (Gemini's audit: fixed and left), `FOLDER-CHANGE-HARDENING.md`, `STORAGE-AND-SPEED-OPTIMISATION.md`, `RESOURCE-LIBRARY-BOUNDARIES.md`, `PRE-RESUME-CHECK.md`, `run-scripts/` |
| `2026-11-12-progress/` | `PROGRESS-REPORT.md` (status against the MF plan) and `LIBRARY-ACCESS-API-SCOPE.md` (one local service for any agent session) |

### 3.2 Written by Gemini (Antigravity)

| Report | Scope | My verdict |
|---|---|---|
| `2026-11-19-stress-test/SUMMARY.md`, `FINDINGS.md`, `COVERAGE.md`, `tools/` | Adversarial review, areas A to H, of `da7bf8a..dbb08b7`; no product edits; spend $0.063888 | Findings ST-F01 to ST-F16 are *verified* by Gemini and I fixed the ones in §1.4. `FIXES-APPLIED.md` records the rest |
| `2026-11-19-agent-review/SUMMARY.md`, `REVIEW-UI-UX.md`, `INFERABILITY-SCORECARD.md`, `LIVE-TEST.md`, `evidence/` | UI, UX and inferability review plus a live test of both products; findings AR-F01 to AR-F25; spend $0.004896 new ($0.043281 cumulative on a $10 ceiling) | Assessed finding by finding in `ASSESSMENT.md`. Confirmed and fixed: AR-F01, F05, F13, F14, F19; partly: F04, F06, F08, F15, F16, F20, F23. **Corrected:** AR-F02 is one library's placeholder, not a default; AR-F11 (no Desk) is probably a discoverability gap, not a missing feature (the Desk section is in the note pane's ⋮ menu but only appears with a project session open; not checked in a browser); "list did not refresh" (AR-F16) was a misreading. The 95.3% inferability score (85 controls) only measures controls that were visible |
| `2026-11-19-agent-review/WORKFLOW-REVIEW.md` | All 15 standard workflows and pipelines, 14 run live on sandbox data; no new spend | Written after `ASSESSMENT.md` (16:27 against 16:00). **Not yet assessed as a whole.** Spot-checks in §3.3 |
| Cited in my reports, not stored in this repo | Pilot "blind review" parts 1 and 2 and the audit of the three libraries (checked in `PILOT-REVIEW.md`, fixed in `AUDIT-FIXES.md`); the Antigravity bug reports on the `Uni` library (`SESSION-REPORT-ASSESSMENT.md`); the Antigravity research plan, Tracks A to F (`RESEARCH-OBJECTIVES.md`) | as stated in each |

### 3.3 `WORKFLOW-REVIEW.md`: what I checked in source for this handover

I read the code behind its main claims. I did not run any workflow.

| Claim | Check |
|---|---|
| WF-D1: every paperclip workflow discards its output and the finished chip disappears | *verified in source*: `ui/src/main.ts:465-471` stores only id, name, status, steps and reason on `action_done`; there is no result field |
| WF-D2: `each` with `on_error: continue` counts refused items as done (`deep-read-staged` reported `read: 5` on 0 of 5; `ingest-cited` reported `ingested: 1` on a failed citation) | *verified in source*: `workflows.py:825` sets `count` to `len(results)` with no success split. The live counts are not re-run |
| WF-D3: `deep-read-staged` from the UI is always refused on third-party sources | *plausible*: `app.py:3014` starts the action at tier `contribute`, and `read_access.guard` lets `deep_read` through only for a person or a batch run. Not run |
| WF-D4: reasoned pipelines always pause with "no routing model is configured" for UI-configured models | *verified in source*: `tools/workflows.py:13-23` reads `extras["router"]`, then `config.toml` `[routing]` or `[clerk]`, then `clerk_fallback`. The UI's Clerk is `extras["clerk"]` (`app.py:2638-2643`) and is never read. Whether the paused chip can be resumed from the UI: *not checked* |
| `review-staged` skips previously queued items | *verified in source*: `review-staged.yaml:11` filters on `item.reviewed is false`, not `drafted` |
| The skill registry and Health contradict each other about Geo-Grapher | *verified in source*: `app.py:3068` reads the global `enabled` flag, and `doctor.py:106` tests `enabled_here` before the library-owned check. The on-screen contradiction was not reproduced |
| MCP `run_workflow` in Ask mode hangs 3+ minutes on a read-only workflow, duplicates permission cards on reload, then parks the session without a reason | *not checked* |
| Read-only tools (`list_workflows`, `run_list`) refused under `BUDGET_SPENT` | *not checked* |
| Only 5 of 15 workflows have a UI entry point | *plausible* (`QUEUED` list in `app.py`); not counted by me |

---

## 4. Decisions that are the owner's

1. **Deploy** the Geo-Grapher `541ce01` wheel to the four libraries and restart each Core onto `593f56c`? The
   procedure and rollback are in `2026-11-17-ui-review/UI-REVIEW.md`. Without the Core restart, AR-F05 stays broken
   (a Core keeps the code it started with). I would restart only Cores that are not in use.
2. **Browse roots** for a library's Geo: are "project folders attached to the library, with project access on" the
   right set? I chose them as the nearest existing, person-approved allowlist.
3. **Antigravity config:** add `--text-content` to the arguments in
   `C:\Users\jakem\.gemini\config\plugins\geo-grapher\mcp_config.json` so Geo tools return readable text there. Not edited.
4. **Claude config:** `~/.claude.json` points the `librarian` tool at `F:/uv-data/Geo_Grapher`, a code repository the
   agent guide says never to use as a library (AR-F22). Not edited.
5. **ACCEPT-02's model:** set `.librarian/app.json` `tiers[0].model` from `lead-m` to a real model so Chat works
   there (AR-F02).
6. **Librarian UI work** (AR-F03 approval badge, AR-F10 Staging intake): `ui/src` is shared with other agents, so
   say who does it.
7. **Commit the reports?** Everything in §3 marked untracked exists only in the working tree.

## 5. Open work, in the order I would do it

> **Done later the same day** (see the plan's §19 entry "Workflows report what they did"):
> - items 1 to 6: WF-D1 to WF-D4, the review-staged filter, the reflection's reason, AR-F02,
>   AR-F03, AR-F10, ST-F09 to ST-F12;
> - from §3.3: the MCP `run_workflow` wait, the Health and registry contradiction, and
>   inspection under a spent budget.
>
> Item 7 (Geo-Grapher) was done after that, in Geo-Grapher `e71967a`:
> - declared-link jumps (AR-F08) and Compare pre-disabled without fingerprints (AR-F16);
> - Matrix headers and Light bubbles (AR-F20) and the three MCP shapes (AR-F06);
> - the first-search latency (AR-F07): 73 s to 6.2 s on the 65k-entity graph, from a query plan
>   in `service.source_of`.
>
> **Correction to its commit message:** the Python suite count is 929 passed and 2 skipped, not
> 1041. The 153 rerun tests were added to the 888, but most of them were already among the 888.
> The wheel is **not** deployed to the libraries.

1. **Triage `WORKFLOW-REVIEW.md`.** The paperclip workflows are the user-facing half of the agent workflow, and WF-D1
   (nothing visible happens) and WF-D2 (false success counts) are both confirmed in source. Fix the counts first: a
   workflow that reports success on a failure is worse than one that shows nothing.
2. **Surface a workflow's result and its paused state** in the UI (WF-D1, WF-D4), and wire `_router` to the
   UI-configured Clerk.
3. **A pending-approval badge** outside Chat (AR-F03) and a Staging "Add source" (AR-F10).
4. **Warn when a configured model id does not exist** (AR-F02's product gap).
5. **ST-F09, ST-F10** (the symlink escape and Windows reserved names): pre-existing and security-adjacent.
6. **ST-F11, ST-F12 rest** (no-progress guard, `advance` back from check-out).
7. **Geo-Grapher:** declared-link traversal, Compare pre-disable, the three MCP shape gaps, Matrix headers and
   Light-theme contrast, first-search latency.

## 6. Working notes

- **Shared tree.** ChatGPT or Codex may edit the same checkout. Commit explicit paths, run evidence from a clean
  clone, and report (do not fix) its failures.
- **Cores.** Agents start, restart and stop Cores and recover stale leases (`docs/agent-guide.md`, "Managing Cores").
  `host status` first; leave Cores you did not start alone. When I last looked (earlier today) the managed ACCEPT-02
  Core was stopped (the review stopped the one it restarted) while an external one ran at port 62047; I have not
  re-run `host status` since.
- **Test commands.** Librarian: `.venv\Scripts\python.exe -m pytest`, never passing `tests/ui_demo_core.py` (it serves
  forever); `node run-smoke.mjs` in `ui/`; `scripts/phase_walk.py`. Geo-Grapher: its Python suite, `npm run test:unit`,
  and Playwright (`playwright.config.cjs`, and `playwright.graphs.config.cjs` on port 8775 against
  `scripts/qa_graph_workspace_server.py`).
- **Windows quirks.** Heredoc Python turns `\n` into real newlines in this shell, so write scripts with the editor
  tools; wrap long commands in `timeout`; use `MSYS_NO_PATHCONV=1` for `/api/...` paths.
- **Geo wheel deploy.** Clean `git archive` plus the built `frontend/dist`, `uv build --wheel`, reinstall into
  `G:\Libraries\_geo-runtime\env`, restart each library's Geo. Exact commands and the rollback wheel are in
  `2026-11-17-ui-review/UI-REVIEW.md`.
