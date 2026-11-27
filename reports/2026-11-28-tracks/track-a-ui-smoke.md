# Track A: the UI smoke, end to end

**Why:** the main UI smoke, `node ui/run-smoke.mjs` (`ui/smoke.mjs` against `tests/ui_demo_core.py`), is the only end-to-end check of the Web UI. A harness bug hid it for an unknown time, and it now runs again: the harness fix and two M1a expectation updates are in `102bb7e`. It still times out in the audited predicate inspector steps. Until it is green it cannot guard the other tracks.

**Repository:** Librarian, on `feat/geo-per-library-service` at `102bb7e` or later.

## Sprint A1: flake or regression

**What is known.** `G:\Librarian-work\tmp\smoke_at.sh <commit>` runs the smoke at one commit, using that commit's code, the harness `actor` fix and the current `ui/smoke.mjs`. It writes its log to `G:\Librarian-work\tmp\smoke-<commit>.log`.

| Commit | Result |
|---|---|
| `04acfe4`, `9b1bd87` (M2), `b78a079` (M4.1), `3ac06bb` | 56/56, pass |
| `3d89b94` | 56/56, pass (once) |
| `b17a6ff` | fail at step 54 |
| `75d9e3c` | fail at step 46 |
| `3f61202` | fail at step 54, twice |

Every failure is a 30 s timeout in the audited inspector: the "Request evidence" refresh, or the view of a refusal the smoke itself mocks. The listing tools are no slower (measured). `b17a6ff` only added a tool (`folder_draft_pending`) and a pipeline step.

**To do:**
- Repeat `3d89b94` and `b17a6ff` three times each.
- Record a Playwright trace (`context.tracing`) of a failing run, and the demo Core's request log.

**Done when:** the report says whether it is a flake or a regression. For a regression, it names the first bad commit; for a flake, what the timing depends on.

## Sprint A2: the fix

- Fix the cause in the code (Core, UI or demo harness), not by lengthening timeouts.
- If the smoke depends on wall-clock timing, make it wait on the state it checks.

**Done when:** the smoke passes three times in a row at the head, the cause is in the §19 entry, and the full suite and hosted CI are green.

## Sprint A3, optional: run the smoke routinely

- Add the smoke to a documented local check, in `docs/agent-guide.md`. Hosted CI is optional (the Owner, 26 November), so offer it only if it is cheap.
- Record in the guide that a stale harness hides failures, as `ui_demo_core.person_call` did.
