# Delegation work-package contract (DELEG-11)

Status: specification, 2026-10-29. Schema:
[`schemas/delegation-work-package.schema.json`](schemas/delegation-work-package.schema.json).
Worked example: [`examples/work-package-ADAPT-05.json`](examples/work-package-ADAPT-05.json).

A work package is the unit of delegated development work. It is finished when
there is **evidence**, not when a worker returns an answer. It makes the
packet fields of plan §3.3 executable, and it adds what §3.3 lacks:
- protected acceptance fixtures;
- environment identity;
- resource ceilings;
- a completion record that the worker does not write.

Claude and Codex fill in the same form. It is development tooling: it grants no
runtime role and creates no second qualification authority.

To check a package:

~~~text
.venv/Scripts/python.exe scripts/check_work_package.py PACKAGE.json [--verify-hashes] [--json]
~~~

`--json` prints one JSON object: `ok`, `errors`, and `conformance` (null for a
schema-invalid package).

The schema checks shapes and enums. The checker enforces the rules that span
several fields:
- an oracle covers a behaviour predicate;
- each `covers` entry names a real predicate;
- no id is used twice;
- no protected target is also writable;
- the evidence behind an acceptance meets the completion rules below.

`--verify-hashes` re-reads each protected target from the completed commit and
compares it with the admitted hash.

The checker also lints admission (DELEG-03):
- the drafter and reviewer come from different model families;
- every check runs under the repository venv;
- `owner_host_gate` is set when a §3.2 Windows file is writable;
- an implementation package names its write targets and its documentation
  consequence.

`conformance()` counts how many of the nine §3.3 fields a package fills; this
is metric M9.

Two tools enforce the package around a delegated call:

~~~text
.venv/Scripts/python.exe scripts/delegate_deepinfra.py --work-package PACKAGE.json ...
.venv/Scripts/python.exe scripts/check_diff_scope.py PACKAGE.json (--worktree BASE | --git RANGE | --patch FILE)
~~~

**The runner, with `--work-package`**, does all of this before any paid call:
- refuses a package that fails the checker;
- refuses an export outside `read_targets` and `write_targets`;
- refuses a pool or task id that differs from the package's;
- takes the per-task budget and call limit from the package;
- records the package hash and its M9 conformance in the receipt.

**The diff-scope guard** runs before a change lands and refuses it for any of
these findings:
- a file outside `write_targets`;
- a forbidden or protected file;
- a deletion, a rename or a binary;
- in test files, a removed test function, fewer assertion lines, or an added
  skip or xfail.

A refused change is not repaired by the worker. The lead may still land it by
hand.

**The controller** (DELEG-06) runs the whole worker-ownership loop:

~~~text
.venv/Scripts/python.exe scripts/delegation_controller.py PACKAGE.json BRIEF.txt
    --model <id> --pool <pool> --total-budget-usd <pool budget> [--agent NAME] [--out-dir DIR]
~~~

1. Admit the package. Owner-host packages stay lead-led.
2. Confirm that each protected fixture has its admitted hash at
   `base_revision`, and that the interpreter and `pyproject.toml` hash match
   `environment`. Then check that every write target can come back whole
   within the worker's output limit. Sizes are estimated as the runner does, at
   3.5 bytes per token. A target that is too large escalates `scope_change`
   before any worktree or paid call; at the default 12,000 tokens, `hosts.py`
   and `app.py` are too large. An output limit above the runner's 16,384 is
   refused on the command line.
3. Create a detached worktree at the base inside `--out-dir`.
4. Run the oracle and regression checks there, to confirm they fail or pass as
   admitted. Otherwise escalate `ambiguity`.
5. Ask the worker for complete replacement files in
   `<<<FILE path>>>`…`<<<END FILE>>>` blocks. The call goes through the runner
   with `--work-package` and `--export-root`, so the ledger, budget and call
   limit apply.
6. Write the files and run the diff-scope guard. Any finding rejects the
   change.
7. Run every declared check with the worktree's `src` first on `PYTHONPATH`.
8. If a check fails, or the reply is truncated or has no file blocks, send the
   failure back. This repeats for at most `max_repair_rounds`.
9. On success, commit the candidate in the worktree. That commit is the
   artifact.

`package.json` in the out directory is the completed record. Every check result
in it is `ran_by: controller`, and the logs sit beside it. The lead reviews
the candidate commit, records the decision with `delegate_ledger.py accept`,
lands the commit, and removes the worktree
(`git worktree remove <out-dir>/worktree`).

Field names follow the runtime harness (`audited-engagement-harness.md` §7.3
`AuditedSubtaskContract` and §7.6 `ExecutionReport`/`AuditReport`). Keeping
the names means HARNESS-02/05/07 can take this record over later, rather than
the two being reconciled.

## The four boundaries

### 1. Admission (`admission`)

The lead writes this part before anything is delegated, and it is not changed
afterwards. A materially changed target, check or budget means a new package.

- **What and where.**
  - `package_id`, `task_id`, `objective` (one sentence);
  - `class`: `implementation` or `exploratory`;
  - `base_revision`, the commit the work starts from.
- **Scope.**
  - `write_targets[]`: the files the worker may change;
  - `read_targets[]`: the files exported to it;
  - `forbidden_targets[]`.
- **Fixtures and behaviour.**
  - `protected_targets[]`: path and sha256 of each acceptance fixture, hashed
    over the committed bytes (`git show REV:path`) so that line-ending
    conversion in a checkout does not change the hash. Changing one
    invalidates completion.
  - `preserve[]`: existing behaviour that must not change.
- **Checks.** Each item in `checks[]` has:
  - an `id`;
  - the exact `command`, run with the repository venv;
  - a `kind`: `oracle`, `regression` or `suite`;
  - `expected_before`: `fail` or `pass`;
  - `covers[]`, the predicate ids it gives evidence for.
- **Predicates.** Each item in `acceptance_predicates[]` has an `id`, a `kind`
  and the `text` of what must hold. Code uses three kinds:
  - `applies_runs`;
  - `behaviour`;
  - `integrates`.

  Research uses four:
  - `source_identity`;
  - `quote_present`;
  - `claim_supported`;
  - `coverage`.
- **Environment.** `environment`: interpreter version, venv path and a
  dependency hash (sha256 of `pyproject.toml` at `base_revision` until there is
  a lock file). A mismatch stops the package for requalification.
  `owner_host_gate` is true when §3.2's Windows files are touched.
- **People and models.** `roles`: drafter model, reviewer model (a different
  family) and merge owner.
- **Ceilings.** `budget`:
  - ledger `pool`;
  - `task_usd`;
  - `max_calls`;
  - `max_repair_rounds`, at most 2;
  - `wall_clock_s`.
- **Stopping and documents.** `stop_conditions[]` and
  `documentation_consequence`.

**Admission rules:**
1. An `implementation` package needs at least one `oracle` check that covers a
   `behaviour` predicate. A generic green suite alone is not admission
   evidence.
2. Preserve failing behaviour or reference outputs before the edit, and
   commit them in `base_revision`. The diff-scope guard then sees only the
   worker's change. In ADAPT-04 and ADAPT-05 the goldens were captured first
   but committed together with the change, so measured from the old base they
   look like worker edits.
3. A task with no defensible acceptance method may still be delegated, but as
   `exploratory`. Its result is never recorded as an accepted implementation.

### 2. Worker ownership (`execution`)

**Who does what:**
- The worker **proposes**: a patch, or anchored findings for research.
- The **controller**:
  - applies the patch in an isolated worktree at `base_revision`;
  - runs the declared checks in the declared environment;
  - feeds failures back, for at most `max_repair_rounds`.
- The hosted model executes nothing.
- Extra context reaches the worker only through the controller, within the
  budget.

`execution.controller` records who did the controller's job:
- `controller`, once DELEG-06 exists;
- `lead`, when the lead follows the same steps by hand, as today.

`execution.repair_rounds` records how many rounds were used.

**Ownership rules:**
- Worker-written tests add evidence. They never replace a check from
  admission.
- A patch that edits a protected target, deletes or renames a test, or weakens
  an assertion fails the package. It is not repaired.

### 3. Evidence-bearing completion (`completion`)

The controller (or the lead acting as controller) records this part. The
worker's prose is not the record.

- **What was produced.**
  - `artifact`: the branch, commit or patch sha256;
  - `base_revision`, checked against admission;
  - `changed_files[]`, each with its sha256.
- **Fixture check.** `protected_targets_intact`: every hash re-checked.
- **Check results.** Each item in `check_results[]` has:
  - the check `id`;
  - its `exit_code`;
  - a `log_ref`;
  - `ran_by`: `controller`, `lead` or `worker_claim`. A `worker_claim` result
    never satisfies a predicate.
- **Predicates.** `predicates{}`: each predicate id is `met`, `unmet` or
  `not_checked`.
- **Cost and calls.**
  - `run_ids[]`: the ledger runs, joined by `--task-id`;
  - `cost_usd`;
  - `repair_rounds`.
- **Gaps and decision.**
  - `unresolved_findings[]` and `declared_gaps[]`;
  - `proposed_disposition`: `accept`, `reject`, `partial` or `escalate`;
  - `recorded_by`.

The lead's final decision goes in the ledger
(`delegate_ledger.py accept RUN_ID --state … --commit …`). Completion is valid
only if all of these hold:
- the base revision matches;
- every protected target is intact;
- every `behaviour` predicate is `met` by a check that a non-worker ran.

### 4. Escalation and resumption (`escalation`, `resume`)

The package returns to the lead with `escalation.reason`, one of:
- `ambiguity`;
- `scope_change`;
- `budget_exhausted`;
- `repeated_failure`;
- `protected_target_change_requested`;
- `environment_mismatch`;
- `uncertain_call`.

A partial answer, a truncated reply (runner exit 3), an unknown network outcome
(ledger `uncertain`) and a verified artifact are different states. None of
them is reported as "done".

`resume` records:
- `last_good_artifact`;
- `open_run_ids[]`, which must be reconciled before a resend;
- `next_action`.

Resume from the artifact, the worktree and the ledger, never from a
conversation summary.

## Mapping from plan §3.3

| §3.3 packet field | Contract field |
| --- | --- |
| task ID and one-sentence objective | `admission.task_id`, `admission.objective` |
| allowed files and forbidden files | `admission.write_targets`, `admission.read_targets`, `admission.forbidden_targets` |
| existing behavior to preserve | `admission.preserve`, `admission.protected_targets` |
| exact test command using the repository virtual environment | `admission.checks[].command`, `admission.environment` |
| expected failure before the patch | `admission.checks[].expected_before` |
| acceptance tests after the patch | `admission.acceptance_predicates`, `admission.checks[].covers` |
| documentation/status consequence | `admission.documentation_consequence` |
| primary model, reviewer model, and human merge owner | `admission.roles` |
| provider/network budget, if any | `admission.budget` |

## Mapping to the runtime harness

| Work package | Harness (`audited-engagement-harness.md`) |
| --- | --- |
| `admission` | `AuditedSubtaskContract` §7.3 |
| `write_targets`, `read_targets`, `protected_targets` | the same names in §7.3 |
| `acceptance_predicates`, `checks` | `acceptance_predicates`, `verifier_plan` |
| `budget`, `stop_conditions` | `budget_reservation`, `stop_conditions` |
| `completion.check_results`, `changed_files` | `ExecutionReport.produced_evidence_refs`, `observed_target_refs` |
| `completion.predicates`, `protected_targets_intact` | `AuditReport.verified_requirement_ids`, `integrity` |
| `escalation`, `resume` | `ExecutionReport.outcome` (`blocked`/`partial`), `recovery_plan` |
