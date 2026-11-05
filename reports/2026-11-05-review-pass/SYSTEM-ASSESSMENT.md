# Where Librarian V2 stands against its own expectations (2026-11-05)

The yardstick is the plan the project set itself, in
`reports/2026-11-04-master-finalization/`:
- the master plan's wave gates and release-critical path (`03-MASTER-FINALIZATION-PLAN.md`);
- each packet's "done only when" condition (`execution-queue.json`);
- the memory/context contract MC-01 … MC-16 (`02-UNIFIED-REQUIREMENTS-AND-SPECIFICATIONS.md` §2).

Evidence labels: **M** measured here by a re-runnable command; **R** reported by an
earlier document or agent, not re-measured; **U** outside claim, not checked.

## Summary

- **Done:** Waves 1A and 1B are essentially complete. Of the 16 packets, 15 are done,
  each with a test that fails on the code before it and passes after (M). The 16th,
  MF-016, is open. MF-015 is done by the owner's chosen fallback, a permission gate,
  not by a verified disk quota.
- **Not releasable yet:** 9 of the 24 rows that gate publication are done. The rest
  are three kinds of work:
  - owner decisions: MF-002, MF-051;
  - a real Obsidian/Claude host session: MF-001, MF-045;
  - build and release engineering not yet started: MF-043a–f, MF-044, MF-046,
    MF-047.

  MF-035 is in the front-end lane; MF-042 is continuous.
- **Context and memory:** the complete-request bound (MC-01) and durable evidence
  references (MC-03) now hold, and several silent-staleness defects in ingestion are
  closed. Nothing yet carries what dropped context *said* (MC-02), structures what a
  worker hands back (MC-08/09), or measures whether memory helps (MC-12). These are
  scoped in `MEMORY-IMPROVEMENTS.md`.

## Measured state

| What | Result | Label |
|---|---|---|
| Full suite, clean clone of `bce35ef` plus MF-015 | 2,026 passed, 2 skipped, 5 deselected (`reports/2026-11-05-evidence/suite-mf015-py311.json`) | M |
| Hosted CI, every push today from `bc30910` to `47dcf20` | all jobs green on 8 pushes; one needed a rerun for a timing bound (fixed in `47dcf20`) | M |
| Hosted CI on `5e3a6b4` (MF-015, which also carried Codex's `bce35ef`) | all jobs green (run 42052998862) | M |
| Touched tests on Python 3.12 and 3.13 | pass for MF-012, MF-013, MF-014 (clean venvs) | M |
| Packaged adapter smoke (PowerShell 7) | not run here: no `pwsh` on this machine. Hosted `adapters` job is green | M (hosted only) |

## Wave gates

| Wave | Exit gate (abridged) | State | Missing |
|---|---|---|---|
| 0 | Original mixed-client acceptance; liabilities accounted; status docs adopted; CI triaged | **partly**. MF-003 and MF-004 done (M); MF-001, MF-002 open | MF-001 needs the owner in Obsidian with real clients; MF-002 needs the owner's ledger decision |
| 1A | Composer/action truth, CSS/container integrity, legacy oversight, blocked reasons | **met**: MF-005 to MF-010 committed with tests (M) | Real-Obsidian hotkey and theme checks stay a host item (MF-035/045) |
| 1B | Context bound, durable references, ingestion identity, quota/teardown, workflow reconciliation, service cap, V1 snapshot; *live quota evidence still required* | **mostly met**: MF-011 to MF-015 and MF-017 to MF-020 committed (M) | MF-016 (teardown/quarantine) open. Live quota evidence: measured that this Docker Desktop **cannot** cap disk writes; owner chose a permission gate instead (MF-015) |
| 2 | Workers/MCP continuity, correlated services, review bridges, pinned recipes, redesigned UI in source and installed artifacts | **started**: Settings workspace by Codex (`bce35ef`); MF-021 to MF-035 otherwise open | Most of the wave; see the Codex brief for the UI share |
| 3 | Temporal/support/lesson contracts; retrieval experiments; ten benchmark fixtures | **not started** | Outside the release by design (MF-036 to MF-041) |
| 4 | Acceptance refresh, final real-host pass, freeze, signing, publication | **not started** | Depends on everything above |

## The release-critical path (24 rows gate MF-047)

| Row | State | Evidence or blocker |
|---|---|---|
| MF-001 mixed-client acceptance | open | needs a real Obsidian + Claude/Cowork session |
| MF-002 liabilities | open | owner reconciles three uncertain IDs |
| MF-003 status/crosswalk | done | `6b73fd6` (M) |
| MF-004 current CI | done | hosted green on every job (M) |
| MF-005 … MF-010 | done | commits `6b73fd6` … `fd9586c`, each with tests (M) |
| MF-035 installed UI/adapter qualification | open | front-end lane (Codex brief, step 10) plus host checks |
| MF-042 docs/contract reconciliation | ongoing | each packet's §19 entry exists (M). The capability matrix was last changed 2026-10-30 and predates every MF packet |
| MF-043a–f build/release hardening | not started | depends only on MF-004, which is done; **next backend work** |
| MF-044 acceptance/capability refresh | not started | needs MF-035, MF-042, MF-043, MF-051 |
| MF-045 real-host repeat | not started | needs MF-001, MF-044 |
| MF-046 / MF-047 freeze, routes, signing, publication | not started | owner-controlled |
| MF-051 release scope | open | owner decision. Inputs ready: the P1 list below |

## P1 "fix-or-disable" packets: the input MF-051 needs

| Packet | Outcome | Evidence |
|---|---|---|
| MF-011 complete request bound | fixed | `5167969` |
| MF-012 durable references | fixed (note/file reads; search stays ephemeral by design) | `bc30910` |
| MF-013 deep-read fingerprints | fixed | `896369d` |
| MF-014 document text through rename | fixed | `1bbbf6c` |
| MF-015 Docker disk quotas | **fixed by owner-chosen fallback**: uncapped output is its own always-asked permission; no disk-backed cap is enforced | `5e3a6b4`; measurement in §19 |
| MF-016 producer stop and quarantine export | **open** | depends on MF-015; next in its lane |
| MF-017 pinned workflow closure | fixed | `306bc4e` |
| MF-018 step effect reconciliation | fixed (at most once for changing steps unless a person decides; not exactly once) | `d190969` |
| MF-019 service reservations | fixed for TTS; STT has no prices to cap | `d40ea08` |
| MF-020 one byte snapshot | fixed | `5713330` |
| MF-027 review bridges | **open** | needs MF-016, MF-023, MF-024, MF-026 |

## Memory/context contract (MC clauses)

| Clause | State | Evidence and gap |
|---|---|---|
| MC-01 complete request bound | **met for the measured cases** | MF-011: 50/200 rounds on both adapters (M). The estimate is characters/4 plus a 20% margin, not a tokenizer: the uncertainty is stated, not measured per route |
| MC-02 derived context keeps goals, constraints, corrections | **not met** | MF-011 drops whole middle rounds and says how many; nothing records *what* they contained. Session constraints survive through the context header, but corrections and decisions made in dropped rounds do not |
| MC-03 durable evidence | **met for note and file reads** | MF-012 (M). Search results stay ephemeral by design |
| MC-04 procedure reuse (conditional) | not started | MF-023/036/041 |
| MC-05 recording vs validity time (conditional) | not started | MF-036/037 |
| MC-06 scope at read, rehydrate, merge | **partly** | Rehydration rechecks current access and leaks no metadata (MF-012, M). Merge-time checks belong to MF-021 |
| MC-07 lineage survives | **partly** | References keep tool and locator; evidence ids are exact (MF-012 fix, M). No lineage through paraphrase or consolidation |
| MC-08 structured worker packet | **not met** | Helpers return prose plus a reference list (MF-012). No typed caveats, conflicts or usage |
| MC-09 durable, deduplicated merge | not met | MF-021 |
| MC-10 shared allowance | **partly** | TTS cap reserved across processes (MF-019, M). Worker and aggregate budgets: MF-021 |
| MC-11 distinct retrieval outcomes | **partly** | Reference outcomes are distinct (MF-012, M). Search coverage gaps: MF-028/038 |
| MC-12 memory evaluation | not met | MF-041. No measurement yet of whether memory helps or harms |
| MC-13 reversible consolidation (conditional) | not started | MF-036 |
| MC-14 withdrawal (conditional) | **foundation only** | Reference withdrawal survives restart (MF-012, M). Note/source withdrawal through search, vectors and summaries: MF-036 |
| MC-15 typed edges (conditional) | not started | MF-037 to MF-040 |
| MC-16 resource ceilings | **partly** | Context, reference and TTS bounds (M). Fan-out and consolidation ceilings: MF-021/041 |

## Measured versus reported: where documents have drifted

| Document claim | Measured now |
|---|---|
| Master plan MF-004: "Core CI fails its L0/Core suite step on Python 3.11, 3.12 and 3.13" (R, 2026-11-04) | Green on every job since `bc30910` (M). The row is historical. |
| Regression manifest ADAPT-11: oversized results "retrievable only through the originating loop" (R) | Superseded by MF-012 durable references (M). The row describes its own date correctly but is no longer current. |
| `docs/capability-matrix.md` (last changed 2026-10-30) | Predates every MF packet. MF-044 must refresh it; MF-015's limitation must appear there. |

## Process risks seen today

- **A credential fragment appeared in a local tool output.** Here's what happened:
  - A malformed shell line meant to load the DeepInfra key made bash print part of
    the key into a task output file. The file was overwritten, and the method was
    replaced by the delegation script's own key loading.
  - **Rotate the DeepInfra key.**
- **Shared branch publishing.** Pushing `5e3a6b4` also published Codex's local
  `bce35ef`, which nobody had decided to publish. It had passed the full suite in the
  clean clone first. Claude now holds a push whenever unpushed commits from others are
  underneath.
- **Hosted intermittent:** acceptance tests that stop part way through their writes
  (three hosted runs before today). The cause is still unknown. Diagnostics now log
  the cause type and frames (`51ccacf`), and none of the eleven hosted runs since
  then has interrupted.

## Recommended order from here

1. **MF-016 (backend):** finishes Wave 1B's last packet.
2. **MF-043a–f (backend):** the unstarted release-critical build work.
3. **MF-051 (owner):** freeze the scope, using the P1 table above.
4. **Codex brief, steps 0–10:** the Wave 2 UI share; MF-035 is release-critical.
5. **Memory:** the top two scoped improvements in `MEMORY-IMPROVEMENTS.md`, chosen
   only if MF-051 puts MF-021 in scope.
6. **MF-001 / MF-045 (owner with host):** a real Obsidian + Claude session, then the
   final-candidate repeat.
