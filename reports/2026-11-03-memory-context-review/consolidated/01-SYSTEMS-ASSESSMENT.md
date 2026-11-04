# 1. Consolidated systems assessment

3 November 2026. Evidence snapshot from the preceding reviews, not a new runtime audit.

## Overall finding

Librarian already has most of the foundations needed for a useful evolving knowledge system: durable project/session records, retrieval, evidence, application outcomes, workflows and checks. The priority is to connect them through explicit applicability, revision and evaluation contracts. Adding another memory database alone would not resolve the observed continuity and stale-guidance problems.

The reviewed revisions were Librarian V2 `40ec923f5d7cb5612939b9fc456963b88e0af4a3` and Mark `281dc4166e3350298f9de09ea7dea3d2fbff19aa`. Findings describe reviewed source and selected tests; they do not establish live-vault configuration or production readiness.

## Resource-Library to V2

| Area | What carried over or exists in V2 | Assessment |
|---|---|---|
| Retrieval | Lexical/name/coverage retrieval, optional embeddings, fusion, filters and deterministic explanations | Retain. Measure retrieval and subsequent use separately. |
| Evidence and indexing | Derived SQLite indexes, source/chunk/link representations and provenance | Retain as rebuildable infrastructure; durable evidence identity needs stronger restart/worker continuity. |
| Working context | Desk pins and use signals; audited Session state and bounded projections | Retain. A bounded projection does not guarantee that the complete provider request is bounded. |
| Knowledge graphs | Static structural relationships and advisory communities | Useful navigation. Not a truth-maintenance system or proof that extracted links express causality. |
| V1 community orientation | V1 used community material in orientation; equivalent search-lane integration was not found in V2 | Recover selectively only if a measured task needs it. |
| V1 dependency digest | V1 had transitive import traversal and budgeted dependency digests | Evaluate for code/research dependency tasks; no equivalent integrated V2 path was identified. |
| Data migration | Default active-source migration is selective | Code carry-over is not proof that all historical papers, chats, caches or workflows were imported. |

Exact source locations and migration qualifications are in the [initial comparison](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/REVIEW.md).

## Existing learning capabilities: corrected inventory

The later pass found facilities understated by the initial general-memory review. They are existing assets, not missing features:

- Application records capture needs, sources, outcomes, replacements, suggested lessons and proposed/applied changes.
- Human understanding records capture a person's explanation and confidence; review tasks support later revisiting.
- Validated workflows connect registered actions, outputs and run logs within existing policy boundaries.
- Claim checks test declared repository claims against specific inputs under the current execution policy.
- Project observations, revisions and upkeep records provide change signals.

None alone establishes that a proposed lesson generalizes to a new task. The missing connection is **recorded episode → proposed lesson → qualification → scoped reuse → outcome feedback → revision**. Reuse these facilities when prototyping that connection. See the [corrected inventory and code references](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/EVOLVING-KNOWLEDGE-REVIEW.md).

## What to borrow from Mark

| Mechanism | Useful principle | Qualification |
|---|---|---|
| Working/reusable/archive tiers | Separate attention and retention needs | Tier membership is not truth, access permission or current applicability. |
| Consolidation proposals | Detect candidates, stage changes, retain links and review history | Existing promotion/merge does not demonstrate validated lesson induction. |
| Repository snapshots and coverage | Bind reused artifacts to what was actually inspected | Whole-repository drift is conservative; selective claim dependencies require more work. |
| General maps and project cartridges | Load a bounded overview, then scoped detail | Much of the cartridge roadmap remained planned; do not count it all as delivered. |
| Task DAG ordering | Make dependencies explicit | Topological order alone is not a replication contract. |

Avoid copying three observed weaknesses: destructive age-based deletion in the small legacy prompt-memory file; similarity-based contradiction candidates treated as semantic certainty; and scope assumptions that do not hold on every retrieval fallback. Mark's reviewed fallback lacked several normal-query filters, a static finding rather than a live exploit. Archive score discounts also do not guarantee that archived results rank below every current result.

## Highest-priority gaps

1. **Complete request bounds.** Loop history still accumulates after tool-result clipping. The earlier synthetic probe grew from roughly 140,000 serialized characters at 10 rounds to over 1 million at 200. This is request-growth evidence, not token measurement or accuracy evidence.
2. **Durable evidence continuity.** Loop-local handles help with large results but do not themselves survive worker exit or restart. Reopening must distinguish exact version, changed version, unavailable source and forbidden access.
3. **Structured worker handoffs.** Prose-only answers and clipping can omit caveats, scope and evidence. Parent acceptance needs current requirement revisions, source references, uncertainty and explicit partial/truncated outcomes.
4. **Qualified reuse.** Application logs need a versioned, evidence-linked lesson view before being treated as general guidance.
5. **Selective revalidation.** Source changes should trigger checks of affected uses while preserving unaffected knowledge. Incomplete dependency coverage still requires conservative handling.

## Verification and limitations

Earlier passes reported 84 focused V2 tests, a later set of 59 V2 learning/workflow/upkeep/claim tests, and 28 Mark consolidation tests passing. These are separate historical runs with different scopes; they are not a combined end-to-end learning result. They were not rerun for consolidation.

No proposed evolving-knowledge benchmark has run. Mark's recorded learning evaluation primarily measured artifact completeness, citations, links and compact retrieval output; it does not demonstrate later-task competence.

The named research folder was empty and V2's `papers` folder absent during review. Local research used 59 preserved extracts, including a duplicate PDF, plus selected primary web sources. This is not 59 independent studies or a comprehensive survey. Compiled graphs were used for navigation and checked against source; inferred edges were not treated as implementation proof.

The next research round should test specific missing contracts and useful transfer, while retaining the simpler existing architecture as its baseline.
