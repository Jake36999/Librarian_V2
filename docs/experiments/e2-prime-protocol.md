# E2' protocol: does managed delegation cut the lead's effort?

Status: designed 2026-10-29. The Stage A0 bases (T06, T07, T10) are prepared
and verified; no arm has run. Task registry:
[`e2-prime-tasks.json`](e2-prime-tasks.json). Effort meter:
`scripts/e2_effort.py`. Origin: the agent-workflow sprint's final report (§6
and §8, experiment E2'), which replaces E2.

## 1. Question

For one task class, oracle-backed behaviour-preserving refactors, the
experiment compares three ways of doing a task by how much of the lead's
effort each one leaves:
- **A, direct:** the lead does the task itself.
- **B, one-shot delegation:** the lead delegates as practised so far.
- **C, managed package:** the lead uses the DELEG-06 controller.

Quality is held equal.

For each task, R is the arm's lead effort divided by the direct arm's lead
effort on the same task, so R(A) = 1. The primary quantity is mean R(C). The
secondary quantities are mean R(B), the paired ratio R(C)/R(B), and escaped
defects.

No result is assumed. Earlier evidence cannot answer this: delegated tasks
were never paired with direct ones, and the one controller pilot measured
feasibility, not effort.

## 2. Design

- **Within-task, three arms.** Every task is done three times from the same
  frozen base, once per arm, each in a fresh lead session and a separate
  worktree. Comparing an arm with itself on the same task removes task
  difficulty from R.
- **Twelve tasks in two strata.** Six large targets (100–154 lines) and six
  medium ones (57–95 lines), chosen by script (see the registry's `survey`):
  - functions outside the §3.2 owner-host files;
  - no writer, network, thread, file-write or subprocess calls;
  - writer-safety code excluded by class.

  Size is a stratum because the sprint's arithmetic predicts that a fixed
  handoff cost defeats small tasks.
- **Arm order.** The six orders of A, B and C are each used twice, assigned by
  seed 2610290 (recorded in the registry). Each arm goes first four times. A
  fresh session carries no conversation, so order guards mainly against the
  operator learning the task and against drift over the days of the run.
- **Staging.**
  - **Stage A0 (feasibility):** T06 (large), T07 and T10 (medium), 9 sessions.
    It checks that the arms run as written, estimates the spread of R, and
    gives the real cost per session.
  - **Stage A:** the other nine tasks, run only if the owner approves after
    A0.
  - **Stage B:** two further task classes, six tasks each. The report puts it
    after Stage A and only if A passes.

## 3. Preparation per task (by the experimenter, before any arm)

Preparation is not measured. All three arms receive the same prepared base,
so preparation cancels out of R.

1. **Base branch.** Create `e2/base/<task>` from master.
2. **Characterization tests.** Add `tests/e2/test_<task>_characterization.py`,
   which pins the target's current behaviour across its branches. These are
   regression checks: they must pass at the base.
3. **Structure oracle.** Generate `tests/e2/test_<task>_structure.py` with
   `scripts/e2_structure.py <task>`, run in the base worktree. It requires:
   - the target is at most `max_target_lines` long;
   - every function the base already had keeps its length, or stays within
     that limit;
   - every new function stays within that limit, so the body cannot simply
     move whole into one helper;
   - the module's public names and its classes' public methods are unchanged;
   - the target's signature is unchanged.

   At the base it fails only on the target's length, so it is the oracle.
4. **Held-out cases.** Write five to twenty extra characterization cases per
   task in `C:\Users\jakem\Librarian-E2-holdout\<task>\`. That folder is
   outside the repository and outside every session's folders; the D: root is
   not writable from the agent sandbox. They are used only for scoring escaped
   defects. A held-out file that needs the repository's fixtures (T10) is
   copied into `tests/e2/` of the arm's worktree to run, and removed after.
5. **Commit and record.** Commit the base on `e2/base/<task>`. Record in the
   registry its sha, the hashes of the two test files' committed bytes, the
   held-out file's hash, and how it was verified, and set `status` to
   `prepared`.

Drafting the characterization and held-out cases may be delegated. Each case
is verified at the base before use:
- every main-file test passes;
- every statement of the target executes, checked by a statement trace of the
  target;
- every held-out case passes.

A drafted expectation that fails at the base is corrected to the base's
actual behaviour after checking the code. Characterization records behaviour;
it does not judge it.

## 4. Running an arm

**Worktree.** Each arm gets a worktree,
`git worktree add C:\Users\jakem\Librarian-E2\<task>-<arm> e2/base/<task>`,
with a `.venv` junction to the main venv. Tests run with `PYTHONPATH=src`, which the
checkout guard requires.

**Session settings.** Every arm runs a new Claude Code session in that folder,
with:
- the same model (claude-opus-5-5) and effort setting for all 36 arms;
- no subagents beyond what the arm's text allows;
- no auto-memory writes. The memory folder's hash is recorded before and
  after.

**The operator.** The operator pastes the arm text, answers only permission
prompts, and records the session id. Any other help counts as a **manual
rescue** and is logged.

**Common text** (the same in every arm; `<…>` comes from the registry):

> Task `<id>`: `<objective>` The target is `<target>` in `<module>`. Behaviour
> must not change. `tests/e2/test_<id>_characterization.py` pins it, and
> `tests/e2/test_<id>_structure.py` states the shape required (currently
> failing). Done means both pass, the full suite passes
> (`PYTHONPATH=src .venv/Scripts/python.exe -m pytest -q`), and the change is
> committed on this branch. Do not edit either test file or anything outside
> `<module>`. Finish with the line `E2-DONE <id>`, or `E2-ABANDON <id>: <reason>`
> if you stop.

**Arm text**, appended:
- **A:** Do the task yourself. Do not delegate to DeepInfra or to subagents.
- **B:** Delegate drafting to DeepInfra as practised:
  `scripts/delegate_deepinfra.py` with
  `--ledger D:/Librarian_V2/tmp/deepinfra-delegation/ledger.json --pool claude --total-budget-usd 8 --task-id <id>-B`.
  Then integrate, test and fix the result yourself.
- **C:** Write a work package and brief for this task
  (`docs/delegation-work-package.md`) with task id `<id>-C`. Run
  `scripts/delegation_controller.py` against the main ledger. Review the
  candidate commit and land it on this branch. If the controller escalates,
  you may finish the task by any means.

**When an arm ends.**
- **Completion:** the arm ends at `E2-DONE`, `E2-ABANDON`, or a hard limit of
  three hours of active time.
- **Usage limits:** a usage-limit pause is resumed in the same session if
  possible. Otherwise the new session id is added to the arm.

## 5. Measurement

Each arm is metered with:

~~~text
scripts/e2_effort.py --session <id> [--session <id>] --ledger D:/Librarian_V2/tmp/deepinfra-delegation/ledger.json --task-id <task>-<arm> --json
~~~

**Primary: lead effort E.** This is the weighted token index of metric M1:
- ordinary input ×1;
- cache creation ×1.60;
- cache read ×0.04;
- output ×3.94.

It is taken over every request in the arm's sessions, including subagents,
and each API response is counted once by message id. **R = E(arm) / E(A)** on
the same task.

**Secondary measures:**
- requests;
- active minutes (gaps of 5 minutes or less are summed);
- wall minutes;
- tokens by component;
- delegate dollars from the ledger, with any open runs;
- shadow dollars;
- manual rescues;
- controller rounds and dispositions (arm C).

**Quality.**
- **Accepted.** An arm's outcome is accepted only if all of these hold:
  - the oracle, the characterization tests and the full suite pass, rerun by
    the experimenter at the arm's final commit;
  - the protected test files are unchanged (`check_diff_scope.py` against the
    base, for every arm).
- **Escaped defects.** These are the held-out cases that fail at the arm's
  final commit.
- **Blinded review.** Qwen3.5-397B, a family different from both the lead and
  the worker, scores each accepted diff with arm labels removed and the order
  shuffled. The rubric covers scope, readability, behaviour risk and naming,
  each scored 1–3. The experimenter adjudicates any score below 2.

**Failures stay in.** An abandoned or unaccepted arm keeps its measured E, so
its R still counts, and it is reported as a failed outcome. If the direct arm
itself fails, that task's R is reported but flagged. It enters the primary
analysis only if the owner decides so before unblinding.

## 6. Analysis and decision rule

**Statistics.**
- Report mean R and median R per arm, pooled and per stratum.
- Each mean gets a 95% t-interval, or a paired bootstrap if the ratios are
  skewed.
- Report R(C)/R(B) paired, success rates and escaped defects.
- With n = 12 the 95% half-width is about 0.64σ. If σ is 0.25, that separates
  R = 0.2 from R = 0.5, but not 0.2 from 0.3. Stage A0 estimates σ.

**Decision rule.** The owner confirmed this rule on 2026-10-29, before any
arm ran.
- **Stop:** mean R(C) is 0.8 or more, or arm C's escaped defects exceed arm
  A's.
- **Narrow:** use the controller only in a stratum whose mean R(C) is 0.5 or
  less.
- **Claim 20/80** for this class only if mean R(C) is 0.2 or less and the
  upper end of its interval is below 0.5.
- **Otherwise:** report the measured gain without a claim.

### Amendments before the first arm (2026-10-29)

These were committed before any Stage A0 arm started. The exact text each arm
receives, and its run record, are in
[`e2-a0-runs.json`](e2-a0-runs.json).

1. **Launch.** Each arm is a fresh linked Claude Code session, started from
   the experimenter's session in the arm's own worktree. All arms run with
   claude-opus-5-5, medium effort and auto permission mode. They share one
   neutral background text that names the run as an experiment and gives no
   arm-specific hint.
2. **Waves.** Arms run in three waves of three. Wave n holds position n of
   each task's seeded order, so within a task the order holds, and at most
   three sessions run at once. Each wave starts after the previous one has
   ended.
3. **Ledgers.** Arms B and C use their own worktree's default ledger, so both
   delegating arms follow the same rule (the controller has no ledger option).
   The meter joins each arm's spend from its own ledger.
4. **Common text.** "Work only inside this folder." was added to the common
   text.
5. **Memory.** Each arm's auto-memory lives under its own project folder, so
   no arm sees this project's memory. None of the nine project folders existed
   before the run. Any memory file found there afterwards is recorded as a
   protocol deviation.

## 7. Threats and controls

| Threat | Control |
| --- | --- |
| Order and learning | Balanced orders; a fresh session per arm; no memory writes, checked by hash |
| Leakage between arms | A separate worktree per arm; held-out cases outside the repository; ledger task ids per arm |
| Model or setting drift | Same model and effort for all arms; the meter lists models used; the run dates are reported |
| Operator help | A fixed arm text; permission prompts only; rescues logged and reported |
| Unequal checking | The experimenter reruns every check at each final commit, whatever the arm claims |
| Prompt cache state | Fresh sessions; cache creation is counted with its weight |
| Small n | Staged design; intervals reported; claims limited to the class and stratum |
| Pricing weights | The weights are the client's fitted Opus 5.5 prices. R is a ratio of the same weights, so a price change scales both sides |

## 8. Cost

**DeepInfra.** About $1–4 for the whole run, from the median 1.7 cents per
call and the pilot's $0.013 per controller round.

**Lead quota.** This is the real cost: 36 sessions for Stage A. The pilot does
not give a per-session figure; A0's nine sessions will. Until then, budget each
arm like one task-sized session of this conversation, which is several hundred
thousand weighted tokens.

**Experimenter preparation.** About twelve characterization, oracle and
held-out sets. Most of the drafting can be delegated, but verification at the
base is lead work.

## 9. Owner decisions before running

1. Confirm the decision rule in §6, or set different thresholds.
2. Approve Stage A0 (three tasks, nine lead sessions), including its quota.
3. Confirm the model and effort setting for all arms.
4. Optional: a fourth arm in which Codex uses its built-in subagents under the
   same text. This tells us whether an external controller pays for a Codex
   lead.

Results go to `reports/<date>-e2-prime/`, with the raw meter output, the run
sheet (task, arm, session ids, outcome, rescues) and the scoring files.
