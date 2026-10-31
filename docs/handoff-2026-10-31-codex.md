# Handoff to Codex: remaining plan tasks, then the UI

Date: 2026-10-31. From: Claude (this session's work, REMED-01 to -06 and the
REMED-08 pilot). Master is at `6d471ad`, about 70 commits ahead of
`origin/master`. **Do not push**: the owner pushes.

## How work is done here

- **The plan** is `docs/unified-implementation-plan.md`. Task definitions are
  in §10.1 (REMED-01 to -08, UX-01). Deferrals and rejections are in §12. The
  progress log is §19, appended at the end of the file: one entry per task,
  with a status table, what changed, what was tested, and what was not.
- **Per task:** implement; add tests; run the full suite; append the §19
  entry; commit. End each commit message with
  `Co-Authored-By: <your model> <noreply@...>` (Claude used
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`).
- **The full suite** takes about 10 minutes, so run it in the background:
  `./.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`. Last result:
  1,919 passed, 2 skipped, 5 deselected.
- **Evidence rules** (from the owner's standing notes):
  - prefer measured to reported;
  - say what was run and what was not;
  - keep speculation apart;
  - never relax a check to make a number better.
- **Paid model calls** need the owner's explicit approval, a declared plan
  and a cap. The G5 ledger is `tmp/g5/ledger.json`: shared delegation ledger,
  schema 2, pool `g5`, cap $8, about $5.45 committed.

## Gotchas met in this session

- **Shell patches.** Python patches written through a bash heredoc turn `\n`
  into real newlines. Write patch scripts to a file, or use direct edits.
- **Hidden folders.** `vault.safe_relative()` refuses hidden folders
  (`.librarian/`, `.evidence/`). For paths the audit rules already validated,
  use `vault.root / rel`.
- **Missing files.** `coordination.fingerprint()` returns the string
  `"missing"` for an absent file; it does not raise. Audit events record a
  deletion as `""` (`audit_events.MISSING`).
- **Docker.** Docker Desktop must be started by hand for live Workbench
  checks (`scripts/workbench_live_check.py`). The test suite never needs it.

## What is done

REMED-01 to -05 are complete, each with a §19 entry:
- adopted-library validation;
- grouped search;
- closure lifecycle: drift reconciliation, verified only through the person's
  named verifier, legacy histories;
- Workbench output and helper limits, live-checked on Docker;
- per-dispatch paid-call reservations.

REMED-06 is implemented and committed (`4742baa`): predicate ids, a contract
skeleton, refusal details and stall parking. Its "a bounded pilot shows less
wasted effort" condition is waiting on REMED-08.

## REMED-08 pilot: in progress, needs the owner's decision first

The plan is `docs/experiments/remed08-pilot-plan.md`; the owner approved its
slices, decision rule and caps. Measures come from
`scripts/remed08_measures.py --baseline <run> --candidate <run>`.

- **Canary** (`tmp/g5/remed08-canary`): passed. 19 calls were each reserved
  and settled at metered cost.
- **DeepSeek control** (`tmp/g5/remed08-deepseek`): complete.
  - Tier A 28/37 (0.757), against 19/37 in the baseline.
  - 19 refused calls, against 41.
  - 10.1 calls per Tier A closure, against 17.2.
  - The guard held: 0 false closures, 8/8 histories valid, 8/8 restarts, and
    every verified predicate through the person's named verifier.
  - One stall park (t8 R2).
- **MiMo primary: 3 of 8 tasks.**
  - `tmp/g5/remed08-mimo` holds t1 and t2; `tmp/g5/remed08-mimo-2` holds t3,
    with t4 to t8 recorded as not started.
  - Each run was stopped by a provider timeout at 120 s, on 2 of 123 calls.
    The REMED-05 rule stops the whole run on any uncertain outcome.
  - Refused calls so far: 10, against 693 for the same three tasks in the
    baseline.
- **The owner's open decision.** Should an uncertain call stop only its own
  session, rather than the run? Its charge stays at the full reservation, an
  upper bound, so the cap still holds. If yes:
  - change `PaidDispatch` in `scripts/g5_measure.py` so `blocked` ends the
    task, not the run;
  - add a test in `tests/test_paid_dispatch.py`;
  - log the rule change in §19;
  - run MiMo t4 to t8 within the $1.20 left in MiMo's cap.

  If no, report the pilot as it stands.
- **Still to do either way:**
  - write the results into `reports/2026-10-30-g5-measurement.md` beside the
    32/74 and 25/74 runs, with the decision rule's outcome and the confound
    statement from the plan;
  - add the §19 entries for REMED-08 and for REMED-06's exit;
  - the two `uncertain` ledger entries (`g5-6f67e1617aea`, `g5-6cc14337750d`)
    are for the owner to reconcile with `scripts/delegate_ledger.py
    reconcile`. Do not reconcile them yourself.

## Remaining plan tasks: complete these, in this order

About 50 of the plan's 70 tasks are done and 20 are open. Before starting
each task:
- read its row in the plan for scope, dependencies and its "done only when"
  condition, which is the exit test;
- check §19 in case part of it is already logged; the count above matched
  status rows only.

Then follow the per-task routine above. A task needing paid calls, real
hardware or a decision is stopped at that point and put to the owner.

**1. Finish what is in flight.**
- **REMED-08.** Get the owner's decision on MiMo timeouts (see above), finish
  the pilot, then write its report and §19 entries.
- **REMED-06.** Close it in §19 once the pilot's decision rule is judged.

**2. Required work, in this order.**

| # | Task | Instructions |
| --- | --- | --- |
| 1 | BASE-03 | Reconcile the implementation-status headers and sequencing references in the release queue, adapter docs, registry docs and harness docs with what §19 records. Docs only. Every "done" claim must point at a commit or a §19 entry. |
| 2 | BASE-04 | Write one shared vocabulary table: roles, slots, qualification levels, behaviour states, work budgets, session outcomes and execution tiers. Take each term from the code (for example `audit_events.VISIBLE` and `session_outcome`), then point other docs at the table instead of repeating it. |
| 3 | BASE-05 | A task-level regression manifest: for each task's tests, the command, environment identity, fixture category and expected state. Generate it from the test files where possible, so it cannot drift. |
| 4 | REMED-07 | Measure real model-request size over long sessions; the projection does not replace history, and the bytes `providers._request` sends are the measure (`PaidDispatch` records `sent_bytes`). Derive the capability manifest from the effective dispatch context: profile, routes, roots. Publish a registered / offered / admitted matrix for audited bundles. Inject retry and cancel faults with virtual time. Confirm the existing cancellation; do not rebuild it. Unpaid: use scripted providers. |
| 5 | INDEX-02 | Move the first behaviourally coherent batch of direct `engine_for` callers onto `with_engine` / `with_index`, keeping transaction and error behaviour identical. Tests before and after each batch. |
| 6 | INDEX-03 | The next bounded batch of serving tools, grouped by shared target domain rather than by line count. |
| 7 | INDEX-04 | The remaining serving paths. Remove the runtime direct fallback where the Core is active, and document any path that is intentionally offline. |
| 8 | INDEX-05 | Windows-oriented stress fixtures for concurrent reads, writes and WAL, from the browser, Obsidian, Cowork, an agent, a refresh, a checkpoint and the writer. They must be deterministic enough for the suite; put anything slow behind the `slow` marker. |
| 9 | ROUTE-03 | A canonical vault-scoped `RoleRouteBinding`: role or slot, then host, exact model, expectation record, adapter and qualification. Migrate the existing route settings onto it without changing which model any role uses. |
| 10 | ROUTE-04 | Make readiness, model tiles, selection APIs, migration and save/reopen behaviour role-specific and driven by the binding. Needs ROUTE-03. |
| 11 | UX-01 | A per-predicate inspector: for each predicate, the bound subject, statement, staleness, and authority versus acceptance, projected from existing Session state. Use the existing person tools; add no new ledger. The building blocks exist: predicate ids (`requirements[rid]["ids"]`), `audit_events.summary`, `named_by_person`, `known_fingerprints` and `drift`, and the projection's `contract_skeleton`. It also starts the UI work below. |
| 12 | ACCEPT-02 | A fresh Windows acceptance pass on the repository artifact: Host lifecycle, Obsidian dirty documents, two clients, and the rest of its row. It needs the real desktop app and Obsidian, so prepare the checklist and run what can be run; the owner does the hands-on parts. Record exactly what was run. |

**3. Experimental: only with the owner's go-ahead.**
- **HARNESS-08.** Evaluate a Tier B Clerk audit against state-only and Tier A
  variants on predeclared fixtures, including the semantic advisory checker:
  extract, isolate the source, compare. It needs held-out human labels and
  negative controls. It stays advisory and never closes authoritatively. Any
  paid calls need a plan and a cap first, as in
  `docs/experiments/remed08-pilot-plan.md`.
- **DELEG-06.** Its pilot is built (`scripts/delegation_controller.py`).
  Further work needs a measured case for it.

**4. Deferred or optional: do not start without a recorded decision.**
- **HARNESS-09:** targeted invalidation. Only with a measured benefit; see the
  §12 deferrals.
- **DEPLOY-05:** a structural index.
- **CORE-04B:** a path that runs without the Core.

**5. Blocked externally.** RELEASE-02 and RELEASE-03 (the freeze, signed
build, real-host acceptance and publication) run only after the owner's R0
decision and the SI/LC entry gates, and only against a frozen revision. Do not
start them.

**Owner decisions, not tasks:**
- R0 release: REMED-01, -02 and -04 are done; the SI/LC entry gates remain;
- whether to build the development-agent profile;
- a size quota for the sandbox `/landing` folder (noted under REMED-04).

## Then: review and update the UI

UX-01 is the planned UI work. For the wider review, these are the audited
features the UI does not yet show:
- legacy and invalid history states (`legacy_history`);
- `core_check` edits that made a closure stale;
- stall parks and their reasons;
- structured refusal `details`;
- the contract skeleton.

Every such view should project existing state rather than create a new source
of truth. Real-host acceptance remains a separate gate.
