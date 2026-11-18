# Fixes applied after the review rounds (2026-11-18)

Nothing here is committed. Evidence: `scripts/phase_walk.py` exits 0 (133 probes, 0 unreachable,
0 hint mismatches; scripted walks 23/23, 25/25, 22/22 on the enforced surface), targeted pytest
batches pass (202 + the new tests), `tsc` passes, and the real model was run through each
previously blocked phase on a scratch library (about $0.018 in total).

## Backend

| Fix | Where | Test |
|---|---|---|
| Every phase's bundle now offers the tools its gate asks for: Map `update_plan`; Need `open_brief`; Search `research_round`, `checkpoint`; Judge `decide`, `record_assumptions`; Synthesise `promote_offering`; Check-out `close_brief`, `update_plan` | `agent_runtime.BUNDLES` | `tests/test_phase_bundles.py` |
| 16 phases that had no bundle (ingest, check-in, find, inventory, plan, seed, goal, baseline, focus, practice, consolidate, next, candidate, assess, propose, install) now have one, so apply, start_pursuit, learn and add_capability can work in the app | `agent_runtime.BUNDLES` | same |
| Tool cap raised 12 to 16: the cap clips from the end, so adding the gate tools would have silently dropped `read_result`, `macro_run`, `macro_plan` in Map, Search and Judge (the other session's warning, confirmed) | `MAX_BUNDLE_TOOLS` | same (per-purpose clipping test) |
| `suggest` opens its brief in Map (`open_brief` is gated to map/need) and reads the project there | `required_bundle_actions` | same |
| `capability_candidates` was on the "upkeep" list hidden during sessions, yet the candidate phase's own card asks for it | `loop.UPKEEP_TOOLS` | same |
| 22 gate hints taught `update_plan(map=...)`; the tool takes `update_plan(fields={...})`. All now match | `session.py`, `tools/sessions.py` | `test_gate_hints_use_the_syntax_update_plan_accepts` |
| A turn ends after 4 identical refusals in a row (or a repeatedly "stayed" `advance`) with the cause, instead of running to the 80-step cap | `loop.py` | `tests/test_loop.py` |
| A queued Clerk draft now carries the real reason (e.g. the route is not yet qualified) | `staging.review` | `tests/test_staging.py` |
| Asking for an approved macro again without the checkpoint id reuses the approval instead of minting another card; a different plan still asks | `agent_runtime.run_macro` | `tests/test_macro_permissions.py` |

## UI (`ui/src`, bundle rebuilt)

- The Clerk message shows the real reason, and the item is reloaded after a queued draft, which removes the stale-revision write conflict (`views.ts`).
- "(Choose models)" is a real button; the stale quality banner ("Next: the batch cleans it") is replaced by "At capture… The batch has since run" once every batch stage is complete.
- Lists that hold more than one page say "Showing 50 of N" with a "Show 50 more" button (the Queued list silently showed 50 of 93).
- The ⏻ menu closes on Escape and outside click (`main.ts`).
- Chat role pickers hide embedding, image, video and speech models, with a "Show all" toggle (`panels.ts`).
- Dark-mode contrast: `Open original` and note links drawn as buttons (Libraries, Browse > Desk) no longer keep the browser's light button face; dialog search inputs match the other inputs (`catalogue.ts`, `style.css`).
- Staging kind tabs wrap instead of pushing the view sideways on a narrow screen.
- Plan pane lists each written note once. Wrong "Settings → Library" pointers now name the real sections.
- Checkpoint cards show their id and fold the raw JSON under "Details". A `no_progress` stop is explained in chat.

## Guidance, hints and the guide note

- **Workflow hints and outcomes** (`ui/src/workflows.ts`, one source for every workflow): in Modes → Queue an action, what a workflow does is now the hover hint, and what it leaves behind is a visible **"Result:"** line (for example "Every queued source moves to Staging → Sources, Captured, to review. Nothing joins the library until you accept it."). The form for a workflow that needs input (weekly review) shows both.
- **Every shortcut is explained** in Settings → Commands & shortcuts: each of the 15 commands now says what it does and, for workflows, its result, with the live queue status beneath it.
- **A guide in every new library.** `About the Librarian and how to use it.md` is written to the library root at creation (`starter/`). It explains the pages, how a source becomes part of the library, the workflows, permission modes and the folder layout, then links with ordinary `[[wikilinks]]` to the formal notes in `About/`: Rules, Tool Reference, Note Content Model, Source Documentation Standard, Topics, Domain Register, Domain Packs, and the two recommendation notes. A new generated `About/Tool Reference.md` lists every registered tool by tier from the registry (the API reference; it cannot drift). Tests: `tests/test_guide_note.py` (the guide exists, every link resolves to a note in the library, the reference covers every tool).
- **The note pane opens on the guide the first time a browser opens a library**, if the guide exists and the pane was never opened or closed on purpose. Following a link opens that note in the pane (checked live). Older libraries have no guide, so nothing opens for them; Obsidian is left alone.
- The platform documentation that ships with the Librarian (`docs/`: operator guide, agent guide, product contract) is **not** copied into libraries. The guide points at it by name; linking to it from inside a library would mean shipping those files into every vault, which is your call.

## Live check with a real model (scratch libraries, forced into each phase)

| Phase | Before | After |
|---|---|---|
| Map | `advance` refused 15 times | `update_plan` done, `advance` moved to Need |
| Need | stopped: "open_brief is not in my tool registry" | `open_brief` done, moved to Search |
| Search | blocked by the tool set | `research_round` and `checkpoint` ran (43 calls) |
| Judge | invented a macro, never decided | `decide` ×2, `record_assumptions`, moved to Synthesise |
| Synthesise | could not promote | `promote_offering` asked the person, wrote the offering, moved to Check-out |
| Check-out | drafted a closing summary the session could not honour | `close_brief` and `close_session` done; thread closed |

## Not fixed, and why

- **UI smoke fails at `paperclip fits and scrolls at 497x450`.** It is in HEAD, not from these changes: the chat header gained controls (11-15, 11-17) after that test's last update (11-05), so at a 450px-high window the attach list no longer fits. Needs a layout decision (shorter header on short screens, or let the list overlay).
- **Search tiles for sessions and staging are still inert**, and the Suggest-sources form still has its "text" field and silent success. Both need a design choice about what a click or confirmation should do.
- **Lens Accept / Reject / Defer are still not sticky.** Layout change.
- **No UI for the library budget ceiling** and **the shared chat-model defaults still propagate between libraries.** Both are product decisions.
- **The Clerk route still needs a qualification run before background work can use it.** The reason is now shown; there is still no button that runs it.
- **Content-quality items** (truncated claims, duplicate concept usages, plural/casing concept duplicates, stray `</function>` text, reopen not clearing a closed summary, activity-search date): confirmed by the other session but not touched here.
- Three bundles declare tools the loop hides while a session works (`filters` in Frame, `provenance_check` in Judge, `draft_offering` in Check-out). Harmless, not gate-required.
