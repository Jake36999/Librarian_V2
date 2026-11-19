# Fixes applied after the stress-test review (2026-11-19)

Nothing here is committed. The review's `FINDINGS.md` is the source; ids below are its ids.

## Fixed

| Finding | Fix | Where | Test |
|---|---|---|---|
| **F-01** "Show 50 more" never passed item 50 | The list reads by `offset`, 50 a call, until it holds as many rows as are shown. Checked live: 50 → 61 | `ui/src/views.ts` | live check; the tool already took `offset` |
| **F-02** macro approval reuse | Reuse (no `checkpoint_id` given) looks at only the **latest** card for that exact plan; it must be approved, unexpired, asked by the same session and caller, and **not already spent** (a finished run is a new decision). A card records its session; naming another session's approved id is refused. One approval runs once at a time (a second caller is told it is executing) | `agent_runtime.run_macro`, `_RUNNING` | `tests/test_macro_permissions.py` (4 new) |
| **F-03** vault pipelines granted writes | The grant covers only actions of the **shipped** workflows a run reaches. A vault-defined workflow or pipeline (accepted once as text, however reached) keeps the normal permission prompts. The menu says so under each vault pipeline | `workflows.granted_actions`, `ui/src/panels.ts` | `tests/test_workflow_grant.py` |
| **F-04** Stop wedged on a question or permission card | `cancel_turn` now also releases that turn's own pending questions (`Waiters.cancel_session`) and denies its own pending permission requests (`Broker.deny_session`, "stopped by a person"). Other sessions' requests are untouched. In the UI, `replay()` forgets the detached "working" node (the `insertBefore` throw) and restores it if a turn is still running | `app.cancel_turn`, `broker.py`, `tools/sessions.py`, `ui/src/chat.ts` | `tests/test_cancel_turn.py`, `tests/test_broker.py` |
| **F-05** question `q1` dropped in another thread | Cards are keyed by thread and question; replay and conversation reset clear them. The reviewer's deterministic repro now reports `bugReproduced: false` | `ui/src/chat.ts` | `repro_q1_collision.mjs` |
| **F-06** `audited` could not close | `close_session` is offered in the audited `reduce` phase (the registry allows it only in reduce, check-out and next, so `manage` is unchanged). `phase_walk.py` now requires the last phase of every purpose to offer it | `agent_runtime.BUNDLES`, `scripts/phase_walk.py` | `tests/test_phase_bundles.py` |
| **F-07** UI smoke | 497×450: below 520px of height the header controls compact (three 34px rows → two 26px rows, header 132 → 67px), and the Modes popover scrolls. `smoke.mjs` updated for the first-visit guide, the paperclip menu and pick pane, and workflows moving to the paperclip. Full smoke passes (3 of 4 runs; one failure was a timing flake in the audit-inspector step, unrelated) | `ui/src/style.css`, `ui/smoke.mjs` | `node run-smoke.mjs` |

Also done, because they were small and in the same files:
- **F-08** (skill registry): table cells and code spans are escaped; a docs address is shown only when it is a plain `http(s)` URL, as text, never a link. `tests/test_skill_registry.py`.
- **F-12** (part): `park_session` is offered in every phase (the budget-spent hint tells the model to use it); the `learn/next` hint now includes the required `note`.
- **F-14** (part): closing the pane ends a pending file pick. `ui/src/pane.ts`, `ui/src/main.ts`.
- **F-16** (part): answering a reopened thread's question in the Plan pane carries the thread on, as the chat card does.

## Not fixed (still open)

- **F-09** `/api/file` symlink escape and the `do_GET` crash (pre-existing, medium).
- **F-10** `notes.safe_name`: Windows reserved names, Unicode stripped, extension lost on long names (pre-existing).
- **F-11** no-progress guard misses alternating refusals, ordinary errors and bad arguments.
- **F-12** (rest): `advance` back from check-out / next.
- **F-13** (rest): at ≤900px the pane overlay still covers Staging after a tab switch.
- **F-14** (rest): picking a note whose name is not unique, or contains `]]`, `|` or `#`, writes an ambiguous or broken wikilink.
- **F-15** chat model filter still lets some image / guard models through.
- **F-16** (rest): the guide is not seeded by `adopt`; `guide-seen` is per origin, not per library; two lens / profile buttons still wrap.

## Notes

- A vault pipeline that needs no prompt, because it only reads, is unaffected by F-03. One that writes now asks, like any other work in Ask mode.
- The in-process claim in F-02 covers one Core. Two processes sharing a vault are still serialised only by the vault writer and the journal.
