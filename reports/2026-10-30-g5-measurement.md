# G5 measurement: Tier A on real audited sessions

**Date:** 2026-10-30. **Plan:** [g5-measurement-plan.md](../docs/experiments/g5-measurement-plan.md). **Tasks:** [g5-tasks.json](../docs/experiments/g5-tasks.json), approved by the owner. **Runner:** `scripts/g5_measure.py` at `fcac2b4`…`beafaf8` plus the audit fix in this commit.

## Result

| Route | Sessions | Grains | Closed by Tier A | Share | 95% interval | Spend |
| --- | --- | --- | --- | --- | --- | --- |
| DeepSeek-V4.1-Flash | 8 | 37 | 20 | 0.541 | 0.384–0.690 | $0.71 |
| MiMo-V2.6-Flash | 8 | 37 | 12 | 0.324 | 0.196–0.485 | $1.65 |
| **Pooled** | **16** | **74** | **32** | **0.432** | **0.326–0.546** | **$2.37** |

These shares come from real sessions on a copy of the owner's library
(`D:/Resource-Library/.librarian-app`), with metered spend. They are not
fixture results.

**Scope.** Seven of the ten Tier A verifiers can be exercised on this library
(owner decision). `arithmetic.reproduces`, `coverage.status` and
`claim_run.passed` are measured on fixtures only.

## The decision rule

The owner approved this rule before the run:

| Condition | Result |
| --- | --- |
| 1. Every session ends with a valid history, completed or stopped at a declared cap | **Met.** 16 of 16 histories are valid. Sessions stopped at the turn cap (9), idle (4) or settled (3). |
| 2. Zero false Tier A closures in the closure audit | **Met.** 32 of 32 closures hold. 20 were re-checked by independent code; 12 were re-run by the same code (8 findability, 4 schema), which shows they reproduce but no more. |
| 3. Every forced restart reproduces the state hash | **Met.** 15 of 15 restarts reproduced it. One session settled before its restart point (DeepSeek t6). |
| 4. The share is reported with its interval | **Met.** See the table above. |

By the approved rule, **G5 can be closed**. Closing it is the owner's
decision.

**A correction made before this verdict.** The run's own audit reported 8
false closures. All 8 were `index.findable` re-runs that answered "the index
is not available to this check": the runner had called the audit without an
index. That was the runner's omission, not a closure that failed.

The audit was re-run offline with an index of each session's library. Each
original audit is kept beside the corrected one (`closure_audit_original` in
each `results.json`). The runner now audits after the App closes, with an
index.

## Closures by verifier (pooled)

| Verifier | Passes / results | Re-check method |
| --- | --- | --- |
| quote.located | 17 / 22 | independent |
| index.findable | 11 / 18 | rerun |
| boundary.staged | 5 / 5 | independent |
| citation.resolves | 4 / 5 | independent |
| schema.valid | 4 / 7 | rerun |
| evidence.integrity | 2 / 5 | independent |
| target.diff_clean | 1 / 3 | independent |

"Passes / results" counts every result the verifier recorded. The closure
audit checks the latest pass for each predicate, so its totals differ.

## What the run showed besides the share

- **Admission is where models struggle.** There were 254 contract or plan
  refusals (`AUDIT_EVENT_INVALID`), 87 phase-budget refusals and 38 scope
  refusals. Nine sessions hit the 12-turn cap. The Core refused what it
  should, and no refused contract ran.
- **A question loop.** MiMo asked 115 questions in t5, each answered with the
  fixed reply, at a cost of $0.33. The repeated-question guard catches only
  identical questions, and these varied.
- **Many contracts.** MiMo opened 7 contracts in t8 and 4 in t6, most of them
  never audited. Both sessions reached the turn cap with few closures.
- **`no_suitable_tool` was not exercised.** Neither model's contract ever
  addressed t6's partial requirement, so its no-verifier predicate was never
  planned or left unplanned at admission.
- **No synthesis was accepted.** No person reviewed the staged drafts during
  the run, so every human-judgment grain stayed open. That is by design.

## Cost

| Stage | Spend |
| --- | --- |
| Pilots 1–5 (pilot 1 estimated, 2–5 metered) | about $0.55 |
| Full run (metered) | $2.37 |
| **Total** | **about $2.92 of the $8 cap** |

## Limits

- One library, eight tasks and two inexpensive routes. The interval is wide,
  and the share depends on the task mix.
- Twelve closures were re-run rather than independently re-checked.
- Seven of ten verifiers.
- The fixed answer to questions is a protocol choice. A person answering
  live might change the sessions.

---

## Corrections after the Codex review (2026-10-30)

The text above is kept as written. A code review
([REVIEW.md](2026-10-30-code-review/REVIEW.md)) reproduced six defects, and
one error in this report.

**Error in this report.** "`no_suitable_tool` was not exercised: neither
model's contract ever addressed t6's partial requirement" is wrong. MiMo's
contracts `round-2-model-notes` to `round-4-model-notes` address R1. They
planned `quote.located` for its numeric predicate, and results V6–V11 are
quote passes against it. That is the defect below in real data: a quote pass
does not establish that the context lengths match. R1 ended `partial`. The
headline count is unchanged.

**What weakens this run's assurance.**
- **Wrong subjects could close a requirement.** A predicate's verifier was
  bound, but not its subject (which evidence, which note), so a real quote
  from another source could verify it. The closure audit re-checked the
  model's chosen subject, so it could not catch this.
- **A later contract could inherit an earlier contract's results.** It could
  also replace a verified draft without the verification going stale.

Neither could be detected by this run's checks. "Zero false closures" was
true of what the audit could see, not a guarantee.

**Checked after the fixes, on this run's saved histories.** The task file now
binds a subject to every predicate. Against those exact bindings, **all 29
subject-taking passes used the intended subject**, with no swaps, including
between the two pages of t2, t3 and t7. The other 3 of the 32 closures check
the contract itself. So 32/74 holds in substance. The assurance was missing at
the time, and is now enforced.

**Protocol notes.**
- The forced restart happened after turn 2, not at a randomly chosen audit or
  reduce boundary as the plan described.
- The Wilson intervals treat grains as independent, but grains within a
  session, and the same task across routes, are not. Read them as nominal.
- "Settled" sessions (3) all settled as `failed`. None completed.

**Recommendation.** Re-run the measurement under the fixed code and the bound
task file before relying on G5 for a release. Whether G5 stays closed
meanwhile is the owner's decision.

---

## Re-run under the fixed code (2026-10-30)

The owner asked for a re-run after the Codex fixes (`a9be71b`). It used the
same 8 tasks and two routes, with every predicate's subject now bound in the
task file, and spend was reserved before each call against the shared $8
ledger. Results are in `tmp/g5/rerun-*` (local).

| Route | Grains | Closed by Tier A | Share | 95% interval (nominal) | Spend |
| --- | --- | --- | --- | --- | --- |
| DeepSeek-V4.1-Flash | 37 | 19 | 0.514 | 0.359–0.666 | $0.69 |
| MiMo-V2.6-Flash | 37 | 6 | 0.162 | 0.077–0.311 | $1.09 |
| **Pooled** | **74** | **25** | **0.338** | **0.240–0.451** | **$1.78** |

**The decision rule.** All four conditions are met:
1. 16 of 16 histories are valid.
2. 0 of 25 closures are false. Every subject-taking pass matched the
   person's binding, and every closure held on re-check: 14 independently
   re-checked, 11 re-run (8 findability, 3 schema).
3. 16 of 16 forced restarts reproduced the state hash.
4. The share is reported with its interval.

**Why the share fell (0.432 to 0.338).** Almost entirely MiMo (0.324 to
0.162); DeepSeek held (0.541 to 0.514). MiMo repeatedly called
`admit_contract` with no `verifiers` argument at all, 597 times across
sessions. Each time it was refused with "the person named quote.located for
…; plan exactly that verifier". It never added the parameter, and spent its
preflight budget. Admission refusals rose from 254 to 616 in total.

The stricter rules did what they should: no closure got through on the wrong
subject or another contract's result. The cost is that a model which cannot
follow the plan format closes less.

**A usability fix, recommended rather than made.** When the person has named a
predicate's verifier and subject, the plan entry is fully determined.
Admission could fill an omitted entry from the person's binding (never
overriding a different one), as the Codex review suggested for mechanical
fields. This would change product behaviour, and a later measurement would
show its effect.

**Cost.** This re-run cost $1.78. The ledger stands at $4.70 of the $8 cap.

**Stops.** 6 idle, 5 at the turn cap, and 5 settled as `failed`. No session
completed with every requirement closed, because the synthesis
requirements stay with the person by design. Several authoritative ones
failed or stayed open.

---

## REMED-08 targeted re-measurement (completed 2026-11-02)

The owner approved the predeclared slices, thresholds and caps in
[`remed08-pilot-plan.md`](../docs/experiments/remed08-pilot-plan.md). The
candidate contains the REMED-01--06 changes through `4742baa`; result saving
and measures use `6d471ad`, and the owner-approved task-local timeout policy
used for MiMo t4--t8 is `8b3844c`. This is therefore a measurement of the
current build, not an ablation of REMED-06.

| Route | Build | Tier A | Share (95% Wilson) | Refused calls | Calls / Tier A | $ / Tier A | At `max_turns` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MiMo-V2.6-Flash | fixed-code baseline | 6/37 | 0.162 (0.077--0.311) | 881 | 72.3 | $0.18142 | 5/8 |
| MiMo-V2.6-Flash | candidate | 10/37 | 0.270 (0.154--0.430) | 54 | 22.5 | $0.03315 | 0/8 |
| DeepSeek-V4.1-Flash | fixed-code baseline | 19/37 | 0.514 (0.359--0.666) | 41 | 17.2 | $0.03654 | 0/8 |
| DeepSeek-V4.1-Flash | candidate | 28/37 | 0.757 (0.599--0.866) | 19 | 10.1 | $0.01862 | 0/8 |

The MiMo candidate is assembled, without duplicated placeholders, from
`tmp/g5/remed08-mimo`, `remed08-mimo-2` and `remed08-mimo-3`. The DeepSeek
candidate is `tmp/g5/remed08-deepseek`. `scripts/remed08_measures.py` accepts
repeated run folders and rejects duplicate measured task rows, so the split
run remains reproducible.

### Predeclared decision rule

| Condition | Result |
| --- | --- |
| Admission guard | **Met.** 16/16 histories valid; 0/38 false closures; 14/14 restarts that reached the forced-restart point reproduced the state hash (MiMo t4 settled and t7 timed out before that point); 0/19 verified reductions bypassed the person's named verifier. |
| MiMo refused calls at most 440 | **Met:** 54. |
| MiMo calls per Tier A below about 72 | **Met:** 22.5. |
| MiMo sessions at `max_turns` fewer than 5 | **Met:** 0. |
| DeepSeek candidate interval overlaps 0.359--0.666 | **Met:** overlap is 0.599--0.666. |
| DeepSeek refused calls no more than 82 | **Met:** 19. |

The rule passes. REMED-06's bounded-pilot exit condition is met: the current
build used less wasted effort while the declared admission guard held.

### What changed and what did not

MiMo's refused calls fell from 881 to 54. Its refusal kinds were 29
`CONTRACT_SCOPE` and 25 `BUDGET_SPENT`; the baseline had 611
`AUDIT_EVENT_INVALID` refusals, chiefly the omitted-verifier loop. Model calls
fell from 434 to 225, and questions from 19 to 4. The candidate parked eight
MiMo requirements after bounded no-progress loops; DeepSeek parked one. These
parks explain part of the reduced work and are the intended REMED-06 trade.

The confound declared before the run remains: REMED-01--06 and `c0f7736`
all separate this candidate from the baseline. In particular, filling an
omitted plan entry from the person's binding targets the same MiMo failure.
The result supports the current build and REMED-06's exit rule; it does not
attribute the improvement to one change.

### Paid-call accounting and interruptions

| Slice | Dispatches | Settlement | Committed spend |
| --- | ---: | --- | ---: |
| DeepSeek canary | 19 | 19 completed | $0.02622 |
| DeepSeek control | 283 | 283 completed | $0.52131 |
| MiMo primary | 225 | 222 completed, 3 uncertain | $0.33147 |
| **Pilot total** | **527** | **524 completed, 3 uncertain** | **$0.87900** |

The shared G5 ledger stands at $5.57623 of $8.00, leaving $2.42377. Three
MiMo requests timed out and retain their full reservations:
`g5-6f67e1617aea`, `g5-6cc14337750d`, and `g5-889befbf09d1`. None was
reconciled. After the first two stopped whole runs, the owner approved a
conservative task-local policy: an uncertain call stops its task, retains the
whole reservation, and later tasks may use only the remaining caps. The t7
timeout demonstrated that policy; t8 then ran and was saved normally.

Eight tasks per route remain a small, correlated sample. Two MiMo sessions
ended before their forced restart, and three retained upper-bound rather than
metered charges. Those limits do not change the declared rule's outcome.
