# E2' Stage A0 results: managed delegation did not save lead effort

Date: 2026-10-29. Protocol:
[`docs/experiments/e2-prime-protocol.md`](../../docs/experiments/e2-prime-protocol.md),
pre-registered in `fc6f654` before any arm ran. Run record:
[`docs/experiments/e2-a0-runs.json`](../../docs/experiments/e2-a0-runs.json).
The data behind every figure is in [`data/`](data/).

## Answer

On all three Stage A0 tasks, both delegating arms cost the lead more than
doing the task directly. Quality was the same in all nine arms.

| | Mean R | Median | 95% interval (t, n = 3) |
|---|---|---|---|
| B, one-shot delegation | **1.46** | 1.55 | 0.78 to 2.13 |
| C, managed package | **2.51** | 2.67 | 0.96 to 4.06 |

R is the arm's lead effort divided by the direct arm's lead effort on the same
task. Lead effort is metric M1's weighted token index (§5 of the protocol).
Arm C cost 1.58 to 1.96 times arm B on each task (mean 1.71).

**Under the decision rule the owner confirmed** (stop if mean R(C) is 0.8 or
more), the result is **stop for this class**. Even the lower end of arm C's
interval (0.96) is above the threshold. Stage A0 was meant as a feasibility
stage, and n = 3 is small, but every task points the same way. Running the
other nine tasks of this class (Stage A) would very probably reach the same
decision, so **I recommend not running Stage A for this class**. Section 5 says
what would be worth testing instead.

## 1. Per task and arm

| Task | Arm | Lead requests | Weighted index | R | Shadow $ | Wall min | DeepInfra | What happened |
|---|---|---|---|---|---|---|---|---|
| T06 (`validate_release_lead`, 103 lines) | A | 12 | 142,082 | 1 | 0.71 | 13.3 | – | Direct refactor |
| | B | 16 | 163,592 | 1.15 | 0.81 | 12.2 | 1 call, $0.029 | Draft integrated by the lead |
| | C | 26 | 258,739 | 1.82 | 1.29 | 24.4 | 0 calls | Controller escalated before any call; lead finished by hand |
| T07 (`coerce`, 95 lines) | A | 10 | 95,108 | 1 | 0.47 | 11.6 | – | Direct refactor |
| | B | 20 | 158,834 | 1.67 | 0.79 | 12.8 | 1 call, $0.004 | Draft integrated by the lead |
| | C | 27 | 254,153 | 2.67 | 1.27 | 22.1 | 1 call, $0.038 | Controller accepted round 0; lead restored two dropped comments |
| T10 (`_qualification_fingerprints`, 67 lines) | A | 13 | 129,328 | 1 | 0.64 | 11.8 | – | Direct refactor |
| | B | 24 | 200,692 | 1.55 | 1.00 | 13.3 | 1 call, $0.001 | Draft integrated by the lead |
| | C | 42 | 392,363 | 3.03 | 1.95 | 30.6 | 0 calls | Controller escalated before any call; lead finished by hand |

All nine arms ran on claude-opus-5-5 at medium effort, each in a fresh session
and its own worktree, and each ended with `E2-DONE`. No arm needed a manual
rescue, no arm wrote auto-memory, and no ledger has an open run.

## 2. Quality was equal

The experimenter checked every arm at its final commit:
- each changed only its allowed module;
- both protected test files are byte-identical to the base;
- the structure oracle and the characterization tests pass;
- every held-out case passes (T06 20, T07 8, T10 5), so there are **no escaped
  defects in any arm**;
- the full suite passes in all nine arms: T06 1,618, T07 1,603 and T10 1,583
  passed, 2 skipped. They ran three at a time.

  During its own run T10-C saw one intermittent failure of an unrelated test
  (`tests/test_core_catalog.py`) under load. It did not recur in these nine
  runs. It is noted as a possible flaky test, not an arm defect.

**Blinded review.** Qwen3.5-397B, a family different from both the lead and
the worker, scored the nine diffs with arm labels removed and the order
shuffled (seed 29102026). Seven changes scored 3 on every criterion. The three
points lost were adjudicated against the code:
- **T06-B and T06-A, behaviour risk 2.** The reviewer flagged a subscript
  `lead["endpoint"]` where the original used `.get`. It cannot raise: an
  earlier check in the same ordered table returns a failure unless `endpoint`
  is a dict, and the loop stops at the first failure. This is order coupling
  worth a comment, not a behaviour change. The characterization and held-out
  tests agree.
- **T07-C, scope 2.** A missing space after `=` in an untouched line, which is
  cosmetic. T06-B also leaves a duplicate `return None`.

No adjudicated defect in any arm.

## 3. Why the controller did not delegate in two of three tasks

Arm C escalated before any paid call in T06 and T10. The cause was the same in
both, and it is a design limit, not chance:
- The controller asks the worker for **complete replacement files**.
- The runner caps worker output at **16,384 tokens**.
- `app.py` (T10) is about 245 KB, roughly 60k tokens, and `hosts.py` (T06) is
  about 74 KB, roughly 18k tokens, so neither can come back whole.
- In T06 the lead set a larger output limit, the runner refused it, and the
  controller reported "repeated_failure" instead of rejecting the setting at
  admission. In T10 the lead saw the limit and stopped.
- `registry.py` (T07) is about 36 KB, which fits. That is the only task where
  the controller delegated, and it was accepted in round 0.

So **the controller as built cannot delegate changes to large modules**, and
those are the changes where delegation could help most.

A second defect cost arm C effort in T07: in a fresh worktree the runner's
ledger folder did not exist and `ledger_lock` does not create it. The first
controller run failed before any call, and the lead created the folder and
reran.

## 4. Why delegation cost more even when it worked

The direct arms were small: 10 to 13 lead requests, 95k to 142k weighted
tokens and about 12 minutes each. Delegating added fixed work every time:
- writing the brief (B);
- writing a work package and brief and running the controller (C);
- reading the result;
- running the suite again;
- landing the change.

That fixed work was larger than the whole direct task. This is the handoff-cost
arithmetic in the sprint report (§6): when the handoff cost is a large
fraction of the direct effort, R cannot fall below 1, whatever the worker's
quality. T07-C is the cleanest case, because the controller worked as designed
and the candidate was accepted in round 0. Even so, R was 2.67.

Each arm also starts from a fresh session, so arm C pays to read the work-package
contract cold every time. A practised lead would pay less, but that would not
reverse an effect of this size.

## 5. What this does and does not show

**It shows** that, for small behaviour-preserving refactors (57–154-line
targets) with an oracle already in place, delegation through either the
one-shot runner or the managed controller costs the lead more than doing the
work. It also shows that the controller cannot handle modules over about 60 KB.

**It does not show** what happens on larger tasks, where the fixed handoff cost
is a smaller share. Testing that needs the controller to accept edits rather
than whole files first, and a task class whose direct cost is several times
the handoff cost. The sprint's arithmetic suggests at least 80 minutes of
direct work.

**Recommendations:**
1. Stop delegating small refactors. Do them directly.
2. Fix the two controller defects: create the ledger folder, and validate the
   output limit at admission. Both are small.
3. Before any further experiment, decide whether larger tasks are worth
   pursuing at all. If they are, the controller needs edit-based output (for
   example search-and-replace blocks checked by the scope guard) and a new
   task class with a large direct cost. That is a new pre-registered stage,
   not Stage A.

## 6. Cost of Stage A0

- **Lead:** 1.79M weighted tokens across the nine arms, or $8.95 in shadow
  dollars (A $1.83, B $2.61, C $4.51).
- **DeepInfra:**
  - arms: $0.072;
  - preparation: $0.060;
  - blinded review: $0.026.

## Data

| File | What it is |
|---|---|
| `data/effort.json` | Meter output per arm: requests, tokens by component, weighted index, active and wall time, ledger spend |
| `data/analysis.json` | R per task and arm, means, medians, intervals, C/B ratios |
| `data/fast_checks.json` | Per-arm scope, protected hashes, oracle and characterization, held-out results |
| `data/suites.json` | Full-suite result per arm at its final commit |
| `data/review_scores.json`, `data/review_key.json` | Blinded review scores and the unblinding key |
