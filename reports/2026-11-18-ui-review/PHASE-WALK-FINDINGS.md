# Phase walk: every phase, not just Map (2026-11-18)

Tool: [scripts/phase_walk.py](../../scripts/phase_walk.py). It never calls a model.

## The defect class

A session phase has an **exit gate** (`Session.missing`) that tells the model what to do, and a
**tool bundle** (`agent_runtime.BUNDLES`) that is the only thing the in-app lead is offered and
the registry enforces (`TOOL_BUNDLE_REFUSED`). Where a gate asks for a tool its own bundle does
not offer, no model can leave that phase. Map was the first one found; the walk shows it is the
rule, not the exception.

The existing scripted walks (`tests/walks.py`) call the registry without bundle enforcement, so
they pass while the live loop cannot. `phase_walk.py` builds the surface with the live
`Loop.tools()` and enforces it the way the loop does.

## What the tool does

| Check | How | Cost |
|---|---|---|
| GATES | Reads each phase's gate text from source and lists every registered tool it names, against the phase's offered bundle | none |
| PROBE | Forces a session into each phase (appends a `phase` event: the skip hack), then calls each gate tool through the enforced registry and classifies the refusal (`TOOL_BUNDLE_REFUSED`, `PHASE_GATE`, `TIER_REFUSED`, or reachable) | none |
| WALK | A scripted agent walks explore, add_project and suggest end to end on the enforced surface. A blocked step is recorded, performed unenforced, and the walk carries on, so one run lists every blocked phase | none |
| `--prepare DIR` | Builds a vault with parked sessions forced into chosen phases, with the state earlier phases would have left, so a real model can be resumed there through the UI | none to build |

Exit status is 1 when anything is blocked, so it can guard a build.

## Result: 7 of 8 purposes have at least one phase a model cannot leave

Tools a model needs in a phase but is not offered (all three checks combined; the walk is the
authority for the explore family):

| Purpose | Phase | Needs, not offered |
|---|---|---|
| explore / add_project / suggest | **map** | `update_plan` (suggest also `read_project`, only when project access is on) |
| explore / add_project | **need** | `open_brief` |
| explore / add_project / suggest | **search** | `research_round`, `checkpoint` (suggest also `open_brief`, since it has no Need phase) |
| explore / add_project / suggest | **judge** | `decide`, `record_assumptions` |
| explore / add_project / suggest | **synthesise** | `promote_offering` (the person can still promote or decline in Staging) |
| explore / add_project / suggest | **check_out** | `close_brief`, so `close_session` can never succeed |
| add_project | ingest | `update_plan` |
| apply | check_in, find | `update_plan`, `log_use` |
| start_pursuit | inventory, plan, seed | `update_plan`, `record_assumptions`, `task_add`, `ingest`, `queue_source` |
| learn | goal, baseline, focus, practice, consolidate, next | `update_plan`, `understanding_record`, `task_add` |
| add_capability | candidate, assess, propose, install | `update_plan`, `capability_candidates`, `ingest`, `record_assumptions`, `capability_propose`, `capability_install` |

Only **frame** is clean in every purpose that has one (and explore's `create_project` is a
documented alternative, not a gap). The phases with no entry in `BUNDLES` at all (ingest,
check_in, find, inventory, plan, seed, goal, baseline, focus, practice, consolidate, next,
candidate, assess, propose, install) fall back to the `session` bundle, which holds only
`advance`, `ask_user`, `open_session` and similar, so those purposes cannot do any phase work
through the in-app lead.

Scope note: tier-0 agents on MCP (Antigravity, Codex, Claude Code) use the whole registry
without bundles, so they are not affected. This is the in-app chat's lead loop.

**Walk result, explore:** 11 of 23 steps passed on the enforced surface; add_project 12 of 25;
suggest 6 of 20. Every step that failed was `TOOL_BUNDLE_REFUSED`, none was a business-rule
failure, which means the gates themselves are consistent and only the bundles are short.

## Confirmed with a real model (forced into the phase, through the UI and Chat)

Three parked sessions were built with `--prepare`, resumed in the UI, and driven by Chat on the
shared default models (about $0.006 for all three, $0.50 ceiling):

| Phase | What the model did | End state |
|---|---|---|
| need | `advance` refused, asked the person for the need and disqualifiers, then tried `macro_run("open_brief")` (no such macro), `macro_plan`, `update_plan`, `record_assumptions`, and stopped with an accurate statement: "open_brief is not in my tool registry for this session… I've stopped rather than working around the refusal" | still `need`, zero briefs |
| judge | `advance` refused; invented `macro_plan('judge-candidates')`; looked for staged items to decide; never decided | both candidates `undecided` |
| check_out | tried `macro_plan('close_brief')` and `macro_plan('close-out')`, then asked permission to `close_session` with a summary that claims B1 is closed while B1 is open | brief B1 `open`, session open |

Map, run earlier, looped `advance` 15 times. Need and Check-out behaved better (a clear blocker,
or a refused close) only because the model chose to stop or ask. Search and Synthesise were
checked by the tool only, not with a model.

Two more behaviours worth knowing: models reach for `macro_plan`/`macro_run` as a workaround
and invent macro names (the macro list has no `open_brief`, `close_brief` or `decide`), and in
Check-out the model drafted a summary asserting the brief was closed when it was not.

## Other findings from the same runs

- **Hint syntax.** 31 gate hints teach `update_plan(map=...)`, but the tool takes
  `update_plan(fields={...})`. The literal call fails with "missing required argument(s)
  ['fields']". Models usually recover; the hint is still wrong.
- **The guard that would have caught this already exists but is not fed.** `Loop._workflow_preflight`
  stops a turn when a "required action" is not offered, but `required_bundle_actions()` only ever
  returns `create_project` in Frame. Feeding it from each gate's tools would turn 15 refused
  `advance` calls into one clear stop.

## Suggested fixes, in order

1. Add the tools in the table to their phase bundles, and add bundles for the 16 phases that
   have none (the tool's summary is the exact checklist).
2. Make the bundle a derived or checked contract: a test that runs `phase_walk` and fails on any
   blocked phase, so a future bundle edit cannot reintroduce this. (It would fail today, so add
   it with the fix, not before.)
3. Feed `required_bundle_actions` from the gate, so a missing tool stops the turn with a named
   cause. Separately, end a turn after N identical refused `advance` calls.
4. Fix the hint syntax, and reject or guide invented macro names (`macro_plan` could say which
   tool the phase needs instead of listing six unrelated macros).

## Using the tool

```bash
.venv/Scripts/python.exe scripts/phase_walk.py                      # all checks
.venv/Scripts/python.exe scripts/phase_walk.py --check walk         # one check
.venv/Scripts/python.exe scripts/phase_walk.py --prepare C:/tmp/pw-vault --phase need --phase judge
.venv/Scripts/python.exe -m resource_librarian --vault C:/tmp/pw-vault app --port 0
```

Limits: the GATES check reads hint text, so it needs the `IMPLICIT_GATE_TOOLS` and `ONLY_FOR`
tables for gates that do not name a tool or apply to one purpose; the WALK covers explore,
add_project and suggest only (the other purposes are covered by GATES and PROBE); and the
probe checks that a tool is callable, not that a model will find the path.
