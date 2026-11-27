# Work another agent can take (27 November 2026)

These are self-contained pieces another agent can do, such as Codex or Antigravity. Claude stays on M5's remaining items (semantic metadata, the batch started by the pipeline, the planted cases, folder descriptions) and on review.

Each brief names its files, what done looks like, and what to leave alone. Briefs 1 and 2 matter most. They extend the regression audit of 27 November (`reports/2026-11-27-regression-audit/README.md`) to the parts it did not cover.

## Rules for every brief

- **The order of authority** (Owner, 27 November; implementation plan §0). The Librarian was built over three months against its own specifications. The systems-analysis packs were drawn from it in the last week of November, to map, fix and optimise it. Where they differ:
  1. the existing specifications come first: the Research Pipeline requirements and addendum of 30 September (`D:\Resource-Library\internal docs\chatgpt-review\`, `D:\Resource-Library\.v2\docs\`), each library's Note Content Model, `docs/policy/`, and `docs/unified-implementation-plan.md`;
  2. then the code and its tests;
  3. then the packs.
- **Nothing is lost.** This is a hardening pass. Never remove a capability, setting, workflow, adapter, or level of analysis or process detail. A new check that could refuse something allowed today ships in report mode. Before a commit, run `scripts/regression_audit.py` against the commit before yours and account for every difference.
- **Branch and room:** work on your own branch or worktree. Make clean clones and scratch folders under `G:\Librarian-work`, because C: and D: are nearly full. Run tests with `TMP`/`TEMP` and `--basetemp` on G:.
- **Hands off Claude's files in flight:** `src/resource_librarian/batch.py`, `intake.py`, `staging.py`, `tools/staging.py`, `standard/stages.yaml`, `tests/test_m5_batch.py`, `tests/test_ingest_service.py`, `docs/proposals/implementation-plan-2026-11.md`. A loss you find in one of these goes in your report for Claude to restore; don't edit them.
- **The house rules:**
  - full suite in a clean clone before a commit;
  - a §19 entry in `docs/unified-implementation-plan.md` for Librarian changes;
  - explicit-path commits;
  - never force-push;
  - never push to `master` or merge into it: that is the Owner's decision.
- **Tests:** list only `tests/test_*.py` when running pytest, because `tests/ui_demo_core.py` serves forever. Wrap long runs in `timeout`.
- **No paid model calls** in these briefs, unless the Owner approves them.

## 1. The branch against `master`: find and restore any regression or loss

The audit of 27 November covered only M0–M5 (`04acfe4..3ac06bb`, 21 commits). This brief covers the rest of the branch and the branch's relation to `master`.

**Scope:**
- **Part A, the branch since it left `master`.** `feat/geo-per-library-service` is 165 commits ahead of `master`, from the merge base `c4eb76f` (12 November): 274 files, 36,649 lines added and 1,172 deleted.
  - Run `scripts/regression_audit.py` with `inventory` on the merge base and on the branch head, then `compare` and `deletions`. Its docstring gives the commands.
  - Account for every difference. Use the commit that made it (`git log -S`, `git blame`) and its §19 entry, and classify it as:
    - **intended:** the commit or §19 says so, and nothing is lost;
    - **lost:** a capability, setting, message, path or level of detail removed with no recorded reason;
    - **unclear:** a question for the Owner.
  - Then read every hunk with deletions in the changed modules, as the 27 November audit did (its report shows the method). The inventory does not see behaviour inside a function whose signature is unchanged.
  - Also check that the libraries' saved state still loads under the branch: `.librarian/` in `G:\Libraries\*` and `E:\Librarian ACCEPT-02 Vault`. That covers checkpoints, effort settings, role assignments and saved workflows. Read only; copy anything you test on to G: first.
- **Part B, the `master` commit the branch lacks.** `master` has `f8dc6b8`, "Librarian: Phase 6–8 code, architecture and guides" (15 November), which is not on the branch.
  - List what it adds that the branch lacks. For example: `docs/access-model.md`, `docs/WAVE_L_FOLDER_REVIEW.md`, `docs/phase8/*`, `docs/library-notes/Content authorship.md`, and any code.
  - List what it deletes that the branch keeps. For example: `docs/experiments/*`, `docs/handoff-2026-10-31-codex.md`, `docs/model-adapter-cohort-2026-10-23.md`.
  - For each item, say whether a merge in either direction would lose it, and propose how the two are reconciled. Do not merge.
- **Restoring a loss:**
  - outside Claude's files in flight: on your own branch (`audit/branch-vs-master`), with a test that fails before the restore and passes after;
  - in one of Claude's files: in the report, with the exact lines and the commit that removed them.

**Done when:**
- `reports/2026-11-27-branch-vs-master-audit/README.md` classifies every difference, with its commit;
- each restoration has its test, and the full suite passes in a clean clone;
- Part B's reconciliation is a list of Owner decisions, each with a recommended answer.

**Read first:** `reports/2026-11-27-regression-audit/README.md` and the docstring of `scripts/regression_audit.py`.

## 2. The original specifications against the to-be packs (read-only)

The 27 November audit found that semantic metadata had been specified on 30 September, more precisely than in the to-be step built from it. This brief checks every to-be step the same way, before M5–M7 build any more of them.

**For each spec in `reports/2026-11-25-systems-analysis-finalisation/librarian/to-be/`, and each entry in its `handles.yaml`,** find:
- the original specification clause:
  - the Research Pipeline requirements of 30 September, §3–§4;
  - the Requirements Addendum (R1 onward) and the Parity Ledger of 1 October;
  - the Finalisation Assessment;
  - the starter `About/Note Content Model.md` and `Source Documentation Standard.md`;
  - `docs/policy/`;
  - the sections of `docs/unified-implementation-plan.md`;
- the code that implements it.

**Output:** a table of to-be step | original clause | code | verdict. The verdict is one of:
- **agrees;**
- **the pack is less precise:** give what the original adds;
- **diverges:** an Owner question;
- **no original specification.**

Order it by what is built next:
1. source-reading, batch-enrichment, source-intake and ingestion (M5);
2. doctor and oracle (M6);
3. research, study-topic and verify-claims (M7).

**Done when:** `reports/2026-11-27-spec-vs-pack/README.md` has the table, a short list of divergences for the Owner, and each verdict cites its clause and file. Change no code, no pack and no spec.

## 3. The Obsidian plugin and the Web UI, before and after (read-only unless a loss is found)

The 27 November audit compared the Core, not the plugin or the UI's behaviour.

- **Obsidian plugin:** compare `obsidian/src` at `04acfe4` and at the branch head, then at the merge base `c4eb76f`. Cover commands, views, settings, the Core API calls they make, and the messages they show. Check that `obsidian/dist` is built from the head source (`npm run build` in a scratch copy, then compare).
- **Web UI:** do the same for the Web UI source, `ui/src/` (built by `ui/build.mjs` into `src/resource_librarian/ui/app.js`). Cover each view, button and API call. The smokes in `ui/` show how to drive it against a scratch library: `m1a-smoke.mjs`, `folders-smoke.mjs`, and the `phase8-*` smokes.
- **Restoring a loss:** a loss outside Claude's files in flight is restored on your own branch, with a smoke or unit test.

**Done when:** `reports/2026-11-27-ui-plugin-audit/README.md` lists every removed or changed command, view, call and message, each classified intended, lost or unclear, and any restoration is tested.

## 4. Geo-Grapher: incremental group application (G4), and paper-database growth measured (G5, measure only)

**Repository:** `F:\uv-data\Geo_Grapher`, on its own branch. Nothing here conflicts with Claude's work.

- **G4 (GT1; W-FOL-01, W-FOL-02):** a folder decision changes its own group only. Done when every row of `reports/2026-11-25-systems-analysis-finalisation/geo-grapher/to-be/incremental-safety.md` passes, and one group is touched per accept. M6 needs this.
- **G5, measurement only:** the M5 acceptance run published 8 papers and left 8 paper-database snapshots, 9.7 MB in all (`G:\Librarian-work\m5-acceptance\library\.librarian\geographer\graphs\`; read only).
  - Measure snapshot growth per publish, and the disk per graph across `G:\Libraries` (read only).
  - Write down the crash-recovery, rollback, WAL-checkpoint and compare-and-swap cases the plan requires before anything is pruned.
  - Do not prune or delete anything: retention is the Owner's decision, and the default keeps everything.
- **Run the regression audit there too:** Geo-Grapher has no `regression_audit.py`. Before committing G4, compare the public API, CLI operations and MCP tools before and after, and account for every difference.

**Done when:**
- G4's rows pass, with the suite and its hosted CI green;
- the G5 measurement is in `reports/2026-11-27-geo-g5-measurement/README.md` in the Librarian repository.
