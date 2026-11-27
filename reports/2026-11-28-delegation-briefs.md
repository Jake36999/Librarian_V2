# Work to hand off (28 November 2026)

**Superseded the same day by the tracks in [2026-11-28-tracks/](2026-11-28-tracks/README.md)**, which cover these briefs as sprints.

Claude moves to review. These briefs hand the remaining implementation to other agents (ChatGPT/Codex, Antigravity, or a tier-1 model). Claude reviews each result against its brief's "done when" before anything is merged.

## Rules for every brief

The rules of `reports/2026-11-27-delegation-briefs.md` hold, unchanged.
- **The order of authority:** the existing specifications, then the code, then the packs.
- **Nothing is lost.** Run `scripts/regression_audit.py` against your base and account for every difference.
- **Working room:** your own branch or worktree, with scratch under `G:\Librarian-work`.
- **The house rules:**
  - the full suite in a clean clone;
  - a §19 entry;
  - explicit-path commits;
  - never force-push, merge into `master`, or push without the Owner's word.
- **Hosted CI:** after a push, wait for the run to finish and read its result. A started run is not a passing one.
- **No uncommitted edits in the main checkout** (`D:\Librarian_V2`). The Resource-Library agent left edits there; work in your own clone.
- **Review:** Claude reviews the result. Report what you did, what you verified, and what you did not verify.

Base for Librarian work: `feat/geo-per-library-service` at its latest pushed commit, `2325595` or later.

## 1. Diagnose the UI smoke's audited-inspector timeouts (Librarian, investigation then fix)

`node ui/run-smoke.mjs` (the main UI smoke, `ui/smoke.mjs` against `tests/ui_demo_core.py`) now runs end to end. Its harness fix and two M1a expectation updates are committed. It still times out (30 s) in the audited predicate inspector steps:
- the "Request evidence" refresh;
- the mocked `AUDIT_EVENT_INVALID` refusal view.

**Bisect so far.** The script `G:\Librarian-work\tmp\smoke_at.sh <commit>` runs the smoke at one commit. It uses that commit's code, the harness `actor` fix, and the current `ui/smoke.mjs`, and writes `G:\Librarian-work\tmp\smoke-<commit>.log`.

| Commit | Result |
|---|---|
| `04acfe4` (before the plan) | 56/56, pass |
| `9b1bd87` (M2), `b78a079` (M4.1), `3ac06bb` | 56/56, pass |
| `3d89b94` (M5 planted cases) | 56/56, pass (once) |
| `b17a6ff` (M5 folder draft step) | fail at 54 |
| `75d9e3c` (folder decisions) | fail at 46 |
| `3f61202` | fail at 54, twice |

The failing steps render a refusal the smoke itself mocks, which a commit adding a tool and a pipeline step should not affect. The listing tools are no slower (measured). It may be timing-sensitive.

**To do:**
- Repeat `3d89b94` and `b17a6ff` three times each, to separate a flake from a regression.
- If it is a regression, find the cause from the Core's HTTP log and the page's network trace (Playwright trace), and fix it in the code, not by lengthening timeouts.
- If it is timing, say what makes it slow.

**Done when:** the smoke passes at the branch head three times in a row, and the cause is stated in the §19 entry.

## 2. G5: one active paper database (Geo-Grapher)

The Owner decided (27 November): fix the growth first, and delete nothing meanwhile.
- **The problem:** each paper publish copies the whole paper database. Resource-Library's DataManagement graph keeps 96 generations, 915 MB for a 16.7 MB active database (55x), and grows quadratically (`reports/2026-11-27-geo-g5-measurement/README.md`).
- **The goal:** a publish inserts into the one active database, transactionally, so rollback and pinned history are kept by snapshot records rather than full copies.
- **Base and constraint:** build on G4 (`feat/g4-incremental-groups`, `G:\Librarian-work\geo-grapher-g4`, `b39897f`). It rewrites `library_papers.py`, and it is not merged yet. Keep the receipt contract (v1.2) unchanged for the Librarian.
- **The plan's G5 gates come first:** crash recovery, rollback, the WAL checkpoint, the disk reserve sized to the paper, and the compare-and-swap retry.
- **No pruning of existing generations:** retention is still the Owner's decision.

**Done when:** the G5 gates pass; a 100-paper synthetic graph grows linearly (measured); and the Librarian's M5 tests pass against a wheel built from it.

## 3. W-PUB-02: publish an unreviewed PDF into the library's own papers group (Geo-Grapher, then the Librarian)

A PDF added without folder review (Inbox, a URL) never publishes: `paper_graph.publish_artifact` returns `awaiting_accepted_folder`. Geo-Grapher's `import-library-paper` accepts only an existing reviewed folder group whose stratum's authorship matches the paper's.
- **Geo-Grapher:** a library-level papers graph, per authorship stratum, that a library may create and publish into, with the same scope checks (the paper's original under the library, not a credential or generated path).
- **The Librarian:** use it when no accepted folder card covers the PDF. The paper's authorship comes from the staged item. Where it is unknown, the PDF is not published and says why.
- **Base:** after item 2, on the same G4 base.
- **The Owner's decision behind it:** the spec audit's D2 recommends publishing. The Owner chose to fix the M5 gaps, W-PUB-02 included, on 27 November.

**Done when:** an Inbox PDF that is read in full is published with a v1.2 receipt and a stored link; one of unknown authorship is not, with a named reason; and both suites pass.

## 4. G4: integration, once the Owner approves pushing it

G4 (`b39897f`) has been reviewed: all 11 safety rows are tested, no function or parameter was removed, and it passes 987, with its 3 failures environmental. The Owner accepted snapshot-scoped rename aliases, but has not yet approved pushing or merging G4. When they do:
- push it for Geo-Grapher's hosted CI and read the result;
- merge it into `feat/per-library-service`, and build the wheel;
- in the Librarian, send `target_groups` from `folder_review.accept` and `accept_by_policy` (`folder_review.py`, around the `_apply` request), so one decision applies one group;
- re-run `tests/test_m5_planted.py` and the folder suites against the new wheel.

**Done when:** one group is touched per accept, measured in a test, with both suites and both hosted CIs green.

## 5. M2: the commission record (Librarian, design-heavy)

This is the next implementation milestone, and what M5's last done-when waits on. Tier 0's instruction becomes a recorded commission that the person approves once. Within it, tier 0 may approve staged sources and start the batch for a named scope, and anything outside it is held on the agenda.
- **The specification:**
  - the implementation plan, M2 item 1;
  - the authority table, `reports/2026-11-25-systems-analysis-finalisation/librarian/to-be/authority.md` (proposed);
  - the policy, "High risk when no tier 0 oversees";
  - the existing permission envelope (`Broker.envelope`, `request_envelope`).
- **Build on what exists:**
  - `ingestion_begin` already holds the decision for any caller but the person, so a commission becomes the third case there;
  - M3's consolidation (one question per overseen run) uses the same record.
- **Who decides what:** the design is yours to propose and the Owner's to accept, because it changes who may decide high-risk steps. Start with a written design, reviewed by Claude before any code.

**Done when:** the plan's M2 done-when holds, and a commissioned `ingest-folder` with `start_batch` runs to the batch with at most 2 tier-0 turns, measured.

## For the Owner, still open

- **Public `master` reconciliation:** decide later.
- **The spec audit's decisions D1–D6** (`reports/2026-11-27-spec-vs-pack/README.md` §3). The recommendations are in the review entry of §19.
- **The Resource-Library live run's leftovers:**
  - three Lead tickets and three folder cards for the held DataManagement folder;
  - the agent's uncommitted report, `reports/2026-11-28-resource-library-supervised-run/README.md`.

  Keep them or clear them.
