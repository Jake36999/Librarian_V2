# G5 measurement plan: Tier A on real audited sessions

**Status:** approved (2026-10-30). The owner approved the task file
(`g5-tasks.json`), the decision rule below and the $8 cap. Part 1 is done;
the pilot is next, and the full run waits for the owner's review of the
pilot.

## What G5 needs

G5 reads: "Session-backed externalized long-horizon state and Tier A work
correctly." HARNESS-01 to -07 implement it, and their tests pass on
fixtures. One done-when has no evidence yet. HARNESS-06 says:

> The share of grains closed by Tier A is measured on real sessions, not
> asserted.

`scripts/tier_a_share.py` measures the share from session logs. On the real
library (`D:/Resource-Library/.librarian-app`) it found 6 session logs, all
`explore`, and no audited session. This plan describes how to produce real
audited sessions and measure them.

## Readiness finding: a real model cannot drive an audited round yet

The loop gives a model a compact tool bundle chosen by the session phase
(`agent_runtime.select_bundle`). The audited phases (`manage`, `preflight`,
`execute`, `audit` and `reduce`) have no bundle. They fall back to the
generic `session` bundle, which holds only open, status, advance, ask,
answer, park, close and create_project.

None of the round's tools is offered to a model: `audit_projection`,
`admit_contract`, `stage_artifact`, `verify_grain`, `audit_targets` and
`reduce_round`. A real model in an audited session today could only advance
and ask. A paid run now would measure that gap, not Tier A.

## Part 1: readiness (unpaid; no approval needed beyond "go")

| Step | Work | Done when |
| --- | --- | --- |
| R1 | Add audited phase bundles. **manage:** `audit_projection`, `update_plan`, `search`, `get_note`, `ask_user`, `advance`. **preflight:** `admit_contract`, `audit_projection`, `advance`. **execute:** `search`, `get_note`, `read_source_file`, `stage_artifact`, `advance`. **audit:** `verify_grain`, `audit_targets`, `advance`. **reduce:** `reduce_round`, `advance`. The person's controls (`set_requirement`, `accept_artifact`, `reject_artifact`, `request_evidence`) stay out of every model bundle. | `select_bundle` returns these per phase, and the person's controls are absent at every agent tier. |
| R2 | A scripted-provider dry run through the real `Loop` and `App`. A scripted model drives one full round with real tool calls: propose, admit, stage, verify a quote grain, audit targets, reduce. | The fixture ends with a verified requirement and an open synthesis, with no paid call. |
| R3 | `scripts/g5_measure.py` does the following, under a hard per-run budget through the delegation ledger: copy the library into a scratch run folder (the real library is never written); create sessions from a predeclared task file; set requirements as the person; drive Lead turns on a chosen route; force one restart mid-session; collect results. | A dry run with the scripted provider produces the full results table. |
| R4 | A closure audit: for each Tier A pass, re-check the statement independently. Quotes are re-located by a separate normalisation, and counts are re-derived from the evidence. List any that do not hold. | It runs on the R2/R3 dry-run output. |

## Part 2: measurement (paid; needs approval)

**Library.** A scratch copy of `D:/Resource-Library/.librarian-app` (124
source notes), taken at the start of the run. Its fingerprint is recorded.

**Routes.** The two Lead routes that passed the L1 tool-continuation probe
(ADAPT-07):
- DeepInfra `deepseek-ai/DeepSeek-V4.1-Flash`;
- DeepInfra `XiaomiMiMo/MiMo-V2.6-Flash`.

Using the qualified routes keeps "the model could not use tools" apart from
"Tier A could not close".

**Tasks.** Eight research tasks, predeclared in
`docs/experiments/g5-tasks.json` before any run, and approved by the owner,
who is the person setting the requirements. Each task names its
requirements and predicates. Together they cover every grain type:

| Grain | Verifier | Example predicate |
| --- | --- | --- |
| quote | `quote.located` | "the claim is quoted from the source's evidence" |
| coverage | `coverage.status` | "the chapters examined are recorded, with the rest named" |
| arithmetic | `arithmetic.reproduces` | "the stated file and module counts reproduce from the survey" |
| findability | `index.findable` | "the cited note is findable by its title and Bottom Line" |
| intake | `evidence.integrity` | "the cited evidence matches its content hash" |
| staging integrity | `target.diff_clean` | "the staged synthesis is unchanged since staging" |
| citation | `citation.resolves` | "every cited evidence id and wiki link resolves" |
| synthesis | none (`human_judgment`) | "a synthesis the person accepts" |

**Drafted task file (2026-10-30).** The draft,
`docs/experiments/g5-tasks.json`, was written after a read-only survey of the
library. Its size:
- 8 tasks;
- 24 requirements: 15 authoritative, 8 human judgment, 1 partial;
- 29 predicates, so 37 grains per route.

It validates against the library: every named source exists, and the
library's evidence store has no record failing its hash.

**The library limits what can be measured.** It holds 102 model notes, 21
pages and 2 documents, and has no repositories, no coverage records and no
claim runs. So `arithmetic.reproduces`, `coverage.status` and
`claim_run.passed` cannot be exercised. The tasks use the other seven Tier A
verifiers, and t6 adds a numeric predicate that no verifier checks, to
measure `no_suitable_tool`.

**Owner decision (2026-10-30): seven verifiers are enough.** The measurement
runs on the library as it is, without ingesting repositories first. The G5
result must state that it covers seven of the ten Tier A verifiers;
`arithmetic.reproduces`, `coverage.status` and `claim_run.passed` stay
measured on fixtures only.

The Lead proposes each contract and its verifier plan. That proposal is
part of what is measured, so the plan is not fixed in advance.

**Design.** It has two stages:
1. **Pilot:** 2 tasks on DeepSeek-V4.1-Flash. It checks cost and
   mechanics. The plan stops here for review if the pilot shows a defect
   rather than a measurement.
2. **Full run:** 8 tasks on each route, so 16 sessions.

Each session is capped at 4 rounds and the phase budgets already in the
Session. One forced restart is made per session, at a random audit or
reduce boundary chosen before the run.

**Measures, predeclared.**

| Measure | Definition |
| --- | --- |
| Tier A share (primary) | Tier A closed grains divided by all grains, by `research_grains.grain_counts` at each session's end. Reported per route and pooled, with a Wilson 95% interval. Fixture results are reported separately and never pooled with these. |
| By grain type | The same share for each verifier, plus the `no_suitable_tool` and `human_accepted` counts. |
| False closures | Tier A passes whose statement does not hold under the R4 closure audit. |
| State correctness | Each forced restart reproduces the session's `state_hash`. The number of invalid histories. |
| Integrity | The number of target audits that came out suspect or violation. |
| Effort and cost | Turns, rounds, refusals by code, tokens and USD, per session. |

**Proposed G5 decision rule (owner to adopt or amend before the run).** G5
is green when all four hold:
1. Every session ends with a valid history, either completed or stopped at
   a declared cap.
2. The R4 audit finds **zero** false Tier A closures.
3. Every forced restart reproduces the state hash.
4. The Tier A share is reported with its interval.

No minimum share is proposed: HARNESS-06 asks for the share to be measured,
not for a target. The owner may add one.

## Budget

These estimates rest on assumptions, and the pilot replaces them with
measurements:
- about 30 turns per session;
- about 8,000 input tokens and 1,000 output tokens per turn (the system
  prompt, a compact bundle and history; the projection keeps history
  bounded);
- the DeepSeek-V4.1-Flash rate card ($0.20 input and $0.60 output per
  million, 2026-10-29).

That gives about $0.07 a session, or about $0.15 with a 2x margin.
MiMo-V2.6-Flash has no checked rate card in the runner yet, so `check-prices`
must record one first.

| Stage | Sessions | Estimate | Proposed hard cap |
| --- | --- | --- | --- |
| Pilot | 2 | about $0.30 | $1 |
| Full run | 16 | about $2.40 | $6 |
| **Total** | 18 | about $2.70 | **$8**, in a new `g5` pool on the delegation ledger, separate from the `claude` pool |

The runner stops at the cap and records the partial results.

## Approvals needed

1. **Part 1** (unpaid code: R1 to R4) can start on a go-ahead.
2. **Before the pilot:** the owner approves the task file, the decision
   rule and the $8 cap.
3. **Before the full run:** the owner reviews the pilot's cost and
   mechanics.

## Risks

- **A model does not follow the audited protocol.** This is recorded as a
  result, with refusal codes and stalled phases. It is not retried away.
  The share counts what Tier A actually closed.
- **Writes to the real library.** None: every session runs on a scratch
  copy.
- **Cost overrun.** Hard caps per stage and in total, enforced by the ledger
  runner.
- **Task bias.** The tasks are fixed before any run, and every grain type
  appears. The share is reported by grain type, so a task set heavy in quote
  grains cannot inflate it unseen.
