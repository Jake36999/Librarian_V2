# Tracks for delegated sprints (28 November 2026)

The remaining work as five tracks, one file each, each split into sprints an agent can take on its own. They replace `reports/2026-11-28-delegation-briefs.md`, which they cover.

**The aim (Owner, 28 November):** bring the Librarian to where it can work on itself, with tier 0 reviewing. Each improvement it makes to itself then compounds. Track D is that loop. Tracks A to C clear what it stands on.

| Track | File | What | Depends on | Owner gate |
|---|---|---|---|---|
| A | [track-a-ui-smoke.md](track-a-ui-smoke.md) | The UI smoke's audited-inspector timeouts | nothing | none |
| B | [track-b-geo-storage-publication.md](track-b-geo-storage-publication.md) | Geo-Grapher: G4 integration, G5's one active paper database, W-PUB-02 | G4 (`b39897f`) | pushing G4 |
| C | [track-c-authority-commission.md](track-c-authority-commission.md) | M2's commission record and M3's one consolidated question | nothing | the design |
| D | [track-d-self-maintenance.md](track-d-self-maintenance.md) | M6: the Doctor, remedies and the repertoire, and the Librarian working on its own code | C for unattended runs | each remedy installed |
| E | [track-e-research.md](track-e-research.md) | M7: research fitted to a brief | B3, the oracle (M4) | always-on review (D6) |

**Order:**
- A, B and C can run at once, as they touch different files and repositories.
- D's first sprints (the inventory and the design) can start at once, and its execution sprints follow C.
- E follows B3.

## Rules for every sprint

1. **Read first:**
   - `reports/2026-11-27-delegation-briefs.md` ("Rules for every brief");
   - the implementation plan's §0 and §2 (`docs/proposals/implementation-plan-2026-11.md`);
   - `reports/2026-11-27-regression-audit/README.md`.
2. **The order of authority:**
   1. the existing specifications: the Research Pipeline requirements and addendum of 30 September, each library's Note Content Model, `docs/policy/`, and the unified plan;
   2. then the code;
   3. then the systems-analysis packs, which map them.

   A to-be step extends the code it maps. Where a pack and a specification disagree, the specification holds, and the difference goes to the Owner.
3. **Nothing is lost.**
   - Before committing, run `scripts/regression_audit.py` (`inventory` on your base and your result, then `compare` and `deletions`), and account for every difference.
   - A new check that could refuse something allowed today ships in report mode first.
4. **Working room:**
   - work on your own branch, in your own clone or worktree under `G:\Librarian-work`;
   - never leave uncommitted edits in `D:\Librarian_V2`;
   - run tests with `TMP`/`TEMP` and `--basetemp` on G:, listing only `tests/test_*.py`.
5. **The house rules:**
   - the full suite in a clean clone before each commit;
   - a §19 entry in `docs/unified-implementation-plan.md`;
   - explicit-path commits;
   - never force-push, merge into `master`, or push without the Owner's word.
6. **Hosted CI:** wait for the run to finish and read its result. A started run is not a passing one.
7. **Money:** no paid model calls without the Owner's approval. Load keys in-process from `D:\Resource-Library\.utility\.env`, and never print them.
8. **Live libraries** (`G:\Libraries\*`, `E:\Librarian ACCEPT-02 Vault`): read only, unless the Owner supervises. Back up `.librarian/` first.
9. **End of each sprint:** report what you did, what you verified (with the commands), what you did not verify, and anything for the Owner. A tier-0 reviewer (Claude) checks it against the sprint's "done when" before it is merged.

## The state these tracks start from

- **The branch:** `feat/geo-per-library-service` at `102bb7e`, pushed and green on hosted CI.
- **Done:** M0 to M5's implementation. The planted cases, the acceptance runs and the regression audit are recorded in §19.
- **Geo-Grapher:** `feat/per-library-service` at `0dcfb9a` (v1.2 receipts) is pushed. G4 (`feat/g4-incremental-groups`, `b39897f`, in `G:\Librarian-work\geo-grapher-g4`) is reviewed but neither pushed nor merged.
- **For the Owner, open:**
  - the public `master` reconciliation (later);
  - the spec audit's decisions D1–D6 (`reports/2026-11-27-spec-vs-pack/README.md` §3);
  - the Resource-Library run's leftovers.
