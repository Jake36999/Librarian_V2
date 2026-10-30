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
