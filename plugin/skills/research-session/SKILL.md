---
name: research-session
description: How to run any research session in the Librarian vault — the phased walk, how to read the session envelope, and what a refusal means. Use whenever you call the librarian's tools for more than a single lookup.
---

# Running a research session

The librarian is a vault of Sources someone has read, with their evidence attached. Its MCP
server keeps the walk for you, so you do not have to hold it in your head.

## Open a thread first

Call `open_session` with a purpose before doing more than one search toward a goal:

| purpose | when | phases |
| --- | --- | --- |
| `add_project` | the person has a new project to frame and supply | frame → ingest → map → need → search → judge → synthesise → check_out |
| `explore` | a field or question, no project yet | frame → map → need → search → judge → synthesise → check_out |
| `suggest` | read an existing project's current state and suggest from the catalogue | frame → map → search → judge → synthesise → check_out |
| `apply` | you are working on another project and consulting the library | check_in → find → check_out |

The session stays attached to this connection. `close_session` detaches it; `park_session`
pauses it; `resume_session` picks it back up, with its plan, briefs and decisions.

## Read the envelope on every result

Every result inside a session carries `session`: the phase, the open items, the budget left,
and `next`. **Follow `next`.** It names the step the phase is waiting on. When the budget of a
phase is spent, the next call is refused: advance, park, or ask the person.

## Refusals are decisions, not errors

A refused result names its rule (`refused`) and says what to do instead (`detail`). The common ones:

- `PHASE_GATE`: that write opens in another phase; the detail names which.
- `BUDGET_SPENT`: the phase has used its calls; call `advance` or `ask_user`.
- `EVIDENCE_QUOTE_VERIFIED`: a quote is not in the source's text; quote exactly or drop the claim.
- `PERSON_CONFIRMS`: the person must decide; the result carries a question for them.
- `TIER_REFUSED`: the tool is not granted to you; report the gap rather than working around it.

`rules` explains any code. Never work around a refusal by writing files directly.

## How to work

- Fetch and verify rather than recall. `Unknown` is a valid answer where a guess is not.
- Distinguish what a source claims from what you confirmed.
- Search before reading notes one by one (`search`, then `get_note`). A `verdict` of `uncovered` is a
  finding, not a failure: record it in the plan (`update_plan`, `nothing_found`).
- Cover the whole list before going deep on the most interesting item.
- If something blocks you (a rate limit, an unreachable source, a tool that will not run), say so
  plainly and carry on with what you can reach.
- Never classify or describe a source yourself in the research conversation. Descriptions are
  clerk tasks, answered without the thread's framing; if they are waiting, say so.
