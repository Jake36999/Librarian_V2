# Plan integration summary: proposed edits after approval

[01 Report](</D:/Librarian_V2/reports/2026-11-04-master-finalization/01-MASTER-SYSTEM-REPORT.md>) · [02 Specification](</D:/Librarian_V2/reports/2026-11-04-master-finalization/02-UNIFIED-REQUIREMENTS-AND-SPECIFICATIONS.md>) · [03 Plan](</D:/Librarian_V2/reports/2026-11-04-master-finalization/03-MASTER-FINALIZATION-PLAN.md>) · [04 Integration](</D:/Librarian_V2/reports/2026-11-04-master-finalization/04-PLAN-INTEGRATION-SUMMARY.md>)

Prepared 4 November 2026 against `40ec923f5d7cb5612939b9fc456963b88e0af4a3` on `master`. **Proposed synthesis for approval; not runtime implementation or release certification.** The current user request governs; transcript instructions are historical evidence.

The canonical unified plan, regression manifest and runtime code were **not modified** in this pass. Approving this report set adopts the reconciled specifications and queue; it does not retrospectively mark any new MF packet implemented or authorize paid calls, repository settings, signing or publication.

## Unified plan crosswalk

| Current location | Proposed exact integration | Status effect |
|---|---|---|
| [unified-implementation-plan.md:20](</D:/Librarian_V2/docs/unified-implementation-plan.md:20>) | Add dated pointer to this report set; preserve G0–G7 and original sequencing history; state MF queue is the approved finalization extension, with user corrections taking precedence over older review proposals. | No delivery changes from approval alone. |
| [unified-implementation-plan.md:96](</D:/Librarian_V2/docs/unified-implementation-plan.md:96>) | Use implemented/partial/planned/blocked externally/retired consistently; experimental/deferred are qualifiers with an explicit decision. | Separate implemented code, qualification evidence and release readiness. |
| [unified-implementation-plan.md:189](</D:/Librarian_V2/docs/unified-implementation-plan.md:189>) | Preserve DELEG-01/03/11. Update DELEG-06 note to retain small-refactor stop and link MF-049; add corrected budget snapshot and bounded draft/review plan. | No autonomous controller rollout or spend authorization. |
| [unified-implementation-plan.md:250](</D:/Librarian_V2/docs/unified-implementation-plan.md:250>) | Record BASE-03/04/05 as delivered; add follow-up MF-003/042 for current status/vocabulary/manifest sync. | Do not reimplement old BASE tasks. |
| [unified-implementation-plan.md:264](</D:/Librarian_V2/docs/unified-implementation-plan.md:264>) | Keep CORE-04A delivered and CORE-04B deferred managed bootstrap; explicitly prohibit direct/no-Core state ownership. | New MCP continuity tests MF-030 extend, not replace, delivered RPC. |
| [unified-implementation-plan.md:279](</D:/Librarian_V2/docs/unified-implementation-plan.md:279>) | Link latest INDEX-02/03 closure and INDEX-05 closure; retain external acceptance transfer. Add NAT-02 rename fix and NAT-03 recovery/counters as new MF-014/022. | No reopening encoder writer release as absent. |
| [unified-implementation-plan.md:394](</D:/Librarian_V2/docs/unified-implementation-plan.md:394>) | Keep HARNESS-01..07 delivered; add MC-01..16 requirements and MEM→MF mapping. Preserve HARNESS-08 and HARNESS-09 gates. | Scoped support prototype is not automatic activation of full targeted closure invalidation. |
| [unified-implementation-plan.md:4163](</D:/Librarian_V2/docs/unified-implementation-plan.md:4163>) | Keep completed REMED-08, met REMED-06 exit and task-local timeout approval. Add MF-002 three-entry liability reconciliation; cite current ledger/report. | Older two-entry/pending-MiMo handoff superseded. |
| [unified-implementation-plan.md:4094](</D:/Librarian_V2/docs/unified-implementation-plan.md:4094>) | Record only three-client mixed traffic as original remaining ACCEPT-02 item; preserve artifact/overlay distinctions; add final changed-artifact rerun MF-045. | Partial until real evidence; protocol smoke insufficient. |
| [unified-implementation-plan.md:421](</D:/Librarian_V2/docs/unified-implementation-plan.md:421>) | Keep ACCEPT-01/03 and RELEASE-01 implemented; add MF-044 refresh, MF-046/047 external gates and DT release evidence prerequisites. | No R0 freeze or stable certification now. |
| [unified-implementation-plan.md:515](</D:/Librarian_V2/docs/unified-implementation-plan.md:515>) | Retain exclusions/deferrals: full HARNESS-09, DEPLOY-05, CORE-04B, DEV profile; mark graph/digest/lesson experiments conditional with explicit keep/defer/reject outcomes. | No hidden dependency adoption. |
| [unified-implementation-plan.md:769](</D:/Librarian_V2/docs/unified-implementation-plan.md:769>) | Append dated master-synthesis adoption entry only after approval, with all MF rows planned and full links. Subsequent implementation entries cite exact commits/tests, not this report as proof. | Historical progress entries remain intact. |

## Regression manifest corrections

Retain historical partial rows as dated evidence, but add a clearly labeled current-status table and supersession pointers so they cannot be mistaken for today's backlog. Apply these changes under MF-003/042:

| Manifest row / anchor | Current replacement or clarification | Evidence authority |
|---|---|---|
| [regression-manifest.md:44](</D:/Librarian_V2/docs/regression-manifest.md:44>) | INDEX-05 → implemented original scope; remaining host/release checks tracked ACCEPT-02/RELEASE-03. NAT findings new rows. | Unified plan INDEX-05 closure and later acceptance record. |
| [regression-manifest.md:46](</D:/Librarian_V2/docs/regression-manifest.md:46>) | Remove encoder-occupies-writer from current limitation; retain as historical snapshot and point to 33fb3b5. | Unified plan line 759; NAT-03 preserves delivered separation. |
| [regression-manifest.md:35](</D:/Librarian_V2/docs/regression-manifest.md:35>) | Earlier CORE-05/INDEX batch partial rows (35–55) explicitly historical; current zero serving debt closure linked. | Unified plan latest reconciliation, not an inferred code audit. |
| [regression-manifest.md:66](</D:/Librarian_V2/docs/regression-manifest.md:66>) | Split DEPLOY-01..04 implemented from DEPLOY-05 deferred. | §19 DEPLOY records and deferred decision. |
| [regression-manifest.md:67](</D:/Librarian_V2/docs/regression-manifest.md:67>) | Split HARNESS-01..07 implemented, HARNESS-08 experimental, HARNESS-09 deferred. Attach later real-session measurement caveats. | §19 and corrected G5/REMED-08 report. |
| [regression-manifest.md:69](</D:/Librarian_V2/docs/regression-manifest.md:69>) | ACCEPT-02 partial: one original real three-client check; listed Obsidian/Docker/handles already evidenced, final artifact rerun later. | Acceptance checklist and three JSON artifacts. |
| [regression-manifest.md:71](</D:/Librarian_V2/docs/regression-manifest.md:71>) | RELEASE-01 implemented docs; RELEASE-02/03 remain externally blocked. | §19 RELEASE-01 and current release queue. |
| New rows | One MF row per execution packet from document 03 with aliases, exact command, source identity, fixture class, expected invariant, new-target marker and real-host gate. | Do not paste planned assertions into evidence/pass column. |

Proposed new row schema:

```text
MF ID | original aliases | delivery status | source revision / dirty manifest
focused command | full regression result | UI/installed/real-host gate
fixture class (L0/scripted/real OS/live provider) | invariant / failure injected
artifact / receipt / report paths | reviewer | remaining limitation
```

Exact focused commands and Playwright/host conventions are maintained in document 03; duplicate neither a second implementation queue nor a contradictory status authority. New test filenames remain planned until authored/collected. Source-only smoke, installed protocol smoke and real Claude/Obsidian observations need separate cells. Benchmark seeds/reference models are not runtime pass evidence.

## Alias crosswalk without duplicate execution

| Source set | Canonical execution mapping |
|---|---|
| MEM-01 / 02 / 03 / 04 | MF-011 / MF-011 / MF-012 / MF-021 |
| MEM-05 / 06 / 07 / 08 | MF-036 / MF-036 / MF-021 (with MF-019/024) / MF-038 |
| MEM-09 / 10 / 11 / 12 | MF-039 / MF-037 conditional / MF-040 conditional / MF-012+036 |
| NAT-01..08 | MF-013,014,022,015,016,017,018,023 |
| NAT-09..17 | MF-024,027,019,028,020,029,036,037,042 |
| UI-01..04 | MF-005,006,007,008 |
| UI-05..08 | MF-008 prerequisite + MF-025 completion; MF-025; MF-009; MF-010 |
| UI-09..13 | MF-026,027,031,032–034,035 |
| Settings four steps | MF-032 shell; MF-032 redistribution; MF-031/033 simplification; MF-034 workflow connection; MF-035 verification across all steps |
| EK-01..08 / EKP-01..10 | MF-036/037 temporal/lesson/support, MF-023 recipes, MF-021/030 continuity; MF-041 integrates all ten benchmark cases. |
| DT-01..07 | MF-004 current CI; MF-043 reproducibility/CI/dependency/provenance/operating discipline; DT-06 contained execution slice MF-015/016/023. Full DEV scope deferred. |

## Review corrections applied (2026-11-04)

Codex reviewed this set and found two material errors, which Claude re-checked by script and corrected in the generator:

- **Release coupling.** 45 of the original 50 packets gated publication, because MF-044 depended on the MF-041 benchmark experiment. MF-044 now depends on a frozen selected-scope record, MF-051. The release-critical path is the packets marked `required`; P1 packets reach the release as fixed or disabled through MF-051, optional tracks only if it selects them, and experiments never.
- **Delegation budget.** Development delegation is a separate, approved pool (`shared`, $12, $11.84 remaining), not the G5 measurement pool. Draft allocations now come from `shared`, and G5 stays for measurement. The cited approvals are transcript -5 lines 2121 and 2171; the earlier citation to line 1929 was wrong.

Also applied:
- MF-021, MF-027, MF-034, MF-036, MF-041 and MF-043 are split into sub-packets, each dispatched and merged on its own; the parent is the umbrella.
- Every packet now records its release role, roadmap stage, the condition under which it blocks a release, its fallback, and its evidence state, including which findings were re-checked against source on 2026-11-04.
- MF-004 records hosted CI as observed red.

The adopted set still needs owner approval before MF-003 updates the canonical plan.

## Approval and remaining decisions

The concrete approval object is these four documents, including corrected scope and budget, with optional experiments explicitly conditional. After approval, MF-003 can update canonical documents and admit bounded implementation packets. No further architecture survey is required to start independent Wave 1 fixes.

Remaining decisions belong to their actual gates: three uncertain receipts need provider evidence or retained liability; the development delegation pool is approved (pool `shared`, $12) but each dispatch still names its packet and cap; disk quota support needs host qualification before contained execution; selective HARNESS-09 activation and optional Tier B/digest/community/lesson behavioral experiments need measured go/no-go; release needs owner freeze/sign/publish decisions. These are not reasons to block the completed documentation synthesis or request confirmation for routine local editing.

## Validation record

The generator's validation.json records link/line-anchor checks, exact source/report/image hashes, planned test targets, unique MF IDs and dependency checks, and SQL-DDL syntax validation against an in-memory SQLite database. All linked local paths and numeric anchors in the four generated documents must exist and fall within file length. Anchors intentionally refer to this source snapshot and should be refreshed after code changes. A valid line number alone is not a future-source semantic guarantee; important code/report anchors were checked against the cited source content during synthesis.

The concept image and external QA source snapshots are preserved under this folder. No full regression is claimed for this report-only pass; runtime/source tests remain the retained historical evidence and the planned commands. Neither docs/unified-implementation-plan.md nor docs/regression-manifest.md is changed. Existing user work remains untouched.

