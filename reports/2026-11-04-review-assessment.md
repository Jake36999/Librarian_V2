# Assessment of the recent work and the 3 November review sessions

Date: 2026-11-04. By: Claude. At: `40ec923` (master, in sync with `origin/master`).

**Scope.** Three things were checked:
- the recent commits, `97cebd7` to `40ec923` (REMED-08, REMED-07, ACCEPT-02);
- the three session transcripts in `docs/Development transcripts/` (-5, -meta6 and -7);
- the reports those sessions left in `reports/2026-11-03-*`, `reports/2026-11-04-*` and `docs/proposals/`.

**Evidence labels:** **M** is measured by script on this machine, **S** is read in source at the cited line, and **R** is reported by an agent and not re-checked. No runtime code changed. The master-finalization generator was corrected (see the last section).

## Summary

The recent work holds up: the suite passes and the pilot's numbers reproduce from raw data. The review findings checked are accurate. Hosted CI is red, and the system is not release-ready. Codex's corrections to the master plan were right, and they are now applied. Codex had stated that the G5 and delegation pools must not be merged. The generated plan nonetheless funded development drafting from the G5 pool's remaining $2.42, and that allocation is corrected too.

## Recent work

| Claim | Check | Result |
| --- | --- | --- |
| Full suite passes | ran it at `40ec923` | **M** 1,939 passed, 2 skipped, 5 deselected. A re-run in a clean clone at `40ec923`, with a fresh environment and CI's install step (`pip install -e ".[dev]"`), gave the same result with exit code 0 and no tracked changes. So the hosted failures do not reproduce from a clean checkout on Python 3.11; MF-004 needs the CI job logs. The command, environment, exit code and complete output are in [suite-40ec923-clean.json](2026-11-04-evidence/suite-40ec923-clean.json) and [suite-40ec923-clean.log](2026-11-04-evidence/suite-40ec923-clean.log). |
| Hosted CI | GitHub Actions API | **M** Core CI fails at its "Run L0/Core suite" step on Python 3.11, 3.12 and 3.13, at `40ec923` and on every push since 2026-10-29. Wheel smoke and adapters pass. The cause (a credential-file ACL assertion and file/index tests) is **R**: the job logs need repository authentication. |
| REMED-08, MiMo: Tier A 6→10/37, refusals 881→54, calls per Tier A 72.3→22.5, `max_turns` stops 5→0 | `scripts/remed08_measures.py` over all three MiMo run folders | **M** all reproduce |
| REMED-08 cost $0.879, 3 uncertain calls | G5 ledger | **M** 527 calls: 524 completed, 3 uncertain, $0.87900 |
| Admission guard held | same script | **M** 0 invalid histories, 0 false closures, 0 restart failures, 0 verified predicates without the person's named verifier |
| ACCEPT-02 evidence retained | every cited path | **M** all exist; one checklist item open (real Claude/Cowork with Browser and Obsidian on one Core) |
| REMED-07 request sizes | §19 entry | **R** not re-run here |

**One caveat on REMED-08 (M).** Three of MiMo's 8 sessions ended in stall parks: t4 (0/4 Tier A), t5 (1/5) and t6 (0/5). Each had 6 to 8 refused calls with no progress. Part of the waste reduction is therefore failing sessions stopped early, which is the intended trade; the Tier A rise shows it is not all of it. In each of those sessions the proposal named every requirement, so a park took the whole session and left no independent work.

## The DeepInfra delegation dispute (transcript -5, from line 1725)

**M**, from `tmp/deepinfra-delegation/ledger.json`. Every call in Codex's `shared` pool is dated 2026-10-28, the day the owner challenged it: 11 calls, $0.1551861. No call has been recorded since, so REMED-07, REMED-08 and the ACCEPT-02 work all ran on Codex's own quota.

Codex's admission that its earlier "delegation" was its own internal sub-agents was accurate. Its commitment to delegate going forward is not borne out by the ledger.

## The review findings

Codex re-checked six findings. Claude re-checked these against source (**S**), and every one holds:

| Finding | Source | What the code does |
| --- | --- | --- |
| NAT-01 | `deep_read.py:236` | Progress resets only when the chunk count changes, so edited text with the same count keeps old reads. |
| NAT-02 | `index.py:479`, `index.py:431` | A vanished path's document-role chunks (attachment text, kept on ordinary refresh) are deleted before identity reconciliation, and nothing carries them to the new path. |
| NAT-06 | `workflows.py:603`, `workflows.py:712` | Resume checks the outer digest; nested workflows load by current name. |
| NAT-07 | `workflows.py:699` | The action runs before its completion is recorded. |
| NAT-10 | `reply_review.py:39`, `reply_review.py:50` | Notes are matched by basename, so same-named notes collide. |
| NAT-11 | `tts.py:242` to `tts.py:264`, `tts.py:120` | Spend is checked, the request sent, then the cost recorded, with no reservation in between; the spend log is per user and shared by all vaults. |
| NAT-13 | `batch.py:548` | Resume keys on (item, stage) with no content identity. |
| G01 | `ui/src/main.ts:555` | The draft is cleared before the server accepts it. |
| G02 | `ui/src/main.ts:176`, `ui/src/main.ts:548` | Enter while busy cancels the running reply. |
| G04 | `obsidian/dist/styles.css` | The shipped Obsidian bundle has 40 unscoped `dialog` rules, including `dialog *` and `dialog button`. |

**Probably overstated.** MEM-01, "no proven final request ceiling", is true. But REMED-07 measured 27,470 and 28,529 bytes at 50 rounds, so it is a missing guarantee, not an observed overflow.

**Status reconciliation.** The master report shows BASE-03 to -05 (`99bff07`), INDEX-02 and -03, INDEX-05 (closed 2026-10-28) and ROUTE-03 and -04 (`b6ef33b`, `4e56ca7`) as delivered. That is correct. The 2026-10-31 handoff note listed them as open; it was wrong, because its count matched exact table rows and missed combined status rows.

**Research claims.** Outside tools are cited against pinned upstream commits, which is good provenance. They do not carry verified, plausible or unverified tags, and paper findings cite sections but rarely pages. The owner's correction against heavyweight frameworks carried through: the unified specification excludes Temporal, XTDB, LangGraph, a CWL runner, GraphRAG, Anki, React, Vue and Tailwind.

## Corrections applied to the master finalization set

The four documents, `execution-queue.json` and `validation.json` are generated by `reports/2026-11-04-master-finalization/build_report.py`, so the generator was corrected and the set rebuilt. The pre-correction files are kept outside the repository. Validation after the rebuild:
- 556 links and 251 line anchors checked, with no errors;
- the dependency graph is acyclic;
- the SQL DDL is valid;
- 75 packets, against 50 before.

1. **Release coupling (M).** 45 of 50 packets gated publication (MF-047), because MF-044 depended on the MF-041 benchmark experiment. Now:
   - a new MF-051, "Freeze the selected release scope", records each P1 packet as fixed or disabled, each optional track as in or out, and experiments as outside the release;
   - MF-044 depends on MF-035, MF-042, MF-043 and MF-051;
   - MF-035 depends on MF-005 to MF-010 and MF-051.

   Publication is now gated by 24 of 75 packets, exactly those marked `required`.
2. **Delegation budget (M).** The plan treated the $10 to $12 delegation cap as unauthorised. It also allocated development drafting from the G5 measurement pool's $2.42. Now:
   - development delegation draws on pool `shared` ($12.00 budget, $0.1551861 committed, $11.8448139 remaining, one uncertain entry);
   - G5 stays for measurement, including any approved MF-041d trial;
   - the owner's approvals are cited at transcript -5 lines 2121 and 2171, where Codex's review cited line 1929, which is unrelated.
3. **Oversized packets.** MF-021 (3 slices), MF-027 (3), MF-034 (3), MF-036 (5), MF-041 (4, the paid trial with its own approval) and MF-043 (6) are split. Each slice is dispatched and merged on its own; the parent is the umbrella.
4. **Release role and evidence.** Every packet now records five fields:
   - its release role: `required`, `fix-or-disable`, `if-selected` or `outside release`;
   - its roadmap stage, 1 to 7, following Codex's roadmap;
   - the condition under which it blocks a release;
   - its fallback;
   - its evidence state, including which findings were re-checked on 2026-11-04.
5. **Notes recorded in the packets.** MF-004 now records hosted CI as observed red, MF-011 carries the REMED-07 measurement, and MF-010 notes the whole-session stall parks.

## Recommended order

1. Owner approval of the corrected set, then MF-003 updates the canonical plan.
2. MF-004: restore hosted CI. It has been red since 2026-10-29, and it is the clearest release blocker.
3. MF-001: the real Claude/Cowork, Browser and Obsidian mixed-traffic check.
4. Daily-use P1 fixes in small, isolated changes, starting with MF-005 (draft loss, Enter cancels) and MF-007 (dialog CSS in Obsidian).
5. Delegation through `scripts/delegate_deepinfra.py --pool shared`, so that the ledger records it.
