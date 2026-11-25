# Enrichment model verification

**Updated:** 22 November 2026. Scope is the requirements baseline, proposed behavioral integration and supporting documentation. This is not live pipeline or release acceptance. Earlier artifact/test results below retain their original revision scope.

## Approved graph-review amendment checks

The Owner-approved [review](../2026-11-22-ingestion-enrichment-graph-review.md) is reflected in the specs and prose: visible target status, exact conversion fallback, bounded route-outage decisions, late publication admission, separate Source/lens decisions, scoped maintenance and immediate critical-stage exits. The same 34 requirement IDs, 38 numbered broad steps, existing node IDs and old extension IDs remain. Existing tests were not rerun for these documentation/model amendments.

Read-only checks imported the supplied renderer without calling its file-writing entry point. Structural, reference and cross-view checks passed for the amended broad model (195 behavioral nodes, 340 edges, 3,870 scenarios) and focused proposal (86 nodes, 145 edges, 71 scenarios, including UC-D outcome references). Fresh in-memory layouts contain no overlaps. All retries and maintenance continuations rejoin main-flow nodes, avoiding unsupported off-main layout/path cycles. Separate lens routing preserves ordinary authorized-agent decisions and reserved Owner decisions. Final saved-geometry, rendered text-fit and generated-artifact checks belong to the coordinating render pass and its validation files; the counts below describe the prior ownership revision.

## Source and scope

The inspected checkout is `D:\Librarian_V2`, branch `feat/geo-per-library-service`, based on `d9435e1`. Repository Python imports `D:\Librarian_V2\src\resource_librarian`; the pytest source-identity guard also ran.

Authored changes are the role policy, terminology, diagram proposal, forward plan, delivery-log entry and this report directory. Existing owner edits in the 20 November canvases, their accepted replacement, `.obsidian/`, and the starter README were preserved. Rejected continuation artifacts remain isolated.

## Model and artifact checks

- All 34 requirements have current-source evidence and explicit model nodes/extensions. Existing test references are distinguished from fresh results below.
- Independent source/coverage review found no remaining material omission at the model's declared abstraction after corrections for mixed roots, isolated failures, folder metadata, empty acceptance sets, partial coverage, revisions and publication exceptions.
- The supplied `render_spec.py` is imported without calling its file-writing `main`. Its structural validation, path logic, cross-view checks and reference checks pass on the model. It remains unchanged.
- The model has 38 numbered main-scenario steps. Its expanded extension scenarios express departures and conditional rejoins, not all combinations of repeated execution or proof that every guard conjunction is feasible. Exact counts and source/renderer hashes are in [validation.json](validation.json).
- Canvas output uses the existing safe preview then revision/hash-checked commit, with generated-ID ownership, explicit sides and accepted column/card dimensions. Card-overlap checks pass. The flow advances downward or hands across actor lanes; explicit rejoins may return upwards.
- The saved geometry was inspected in the overview and source-stage raster previews. The detailed source-stage preview reports no text overflow. These are deterministic previews, not an Obsidian application screenshot.
- Local report links, node/extension traceability, Markdown diff whitespace and regeneration consistency were checked.
- The initial baseline check resolved 292 local links and all 34 requirement mappings. A scratch canvas retained a moved managed card's position, unknown owner metadata and a manual annotation. Regeneration reproduced identical canvas bytes.

## 22 November ownership correction and execution evidence

The Owner requested the same Core/model correction in the comprehensive canvas as in the focused to-be proposal. Seven existing cards were reassigned: Data organization, metadata, Source acceptance, revision review and meaningful draft progress to Clerk; pause and escalation explanations to Lead. Their cards physically occupy those lanes. All 163 other pre-existing nodes retain their geometry. Six reassigned cards retain their original row; only `revisionapprove` moves one row upward to avoid covering `a18`.

Ten additional cards separate capture description, the Lead's ingestion approval, agent conversion work and the scripted dispatch of submitted acceptance decisions. Core's remaining labels specify scripts, recorded flags, schemas, literal locators, counters, grants, storage or dispatch. A repeat preview preserves the saved canvas bytes. A scratch preview preserves moved-card geometry, nested owner metadata, an unknown root field, a manual annotation/edge and a managed edge's custom metadata/attachment side. These are artifact checks; no runtime implementation was added.

The [observed-run assessment](observed-enrichment.md) and [hashed evidence snapshot](observed-run-evidence.json) inspect two actual completed batches covering seven sources, their retained Data/conversion/graph outputs, accepted notes and historical usage. They show one all-nine-stage success and a newer batch with three enriched and three partial items. Current Data/metadata scripts are distinguished from proposed semantic agent work. A read-only Core handshake returned `2.1.0.dev0`, writer `ready`, lease `held`; it does not pin a Git commit or the historical run build. New model spend was **$0 of the authorized $2**. No enrichment or promotion was executed for this assessment.

Prior ownership-revision checks passed for all 162 declared actor-lane placements, 34 requirement mappings, 314 local links across the baseline and focused proposal, and 41 historical artifact hashes. That revision had 38 numbered steps and 2,712 prototype extension scenarios. Its canvas overlap and source-detail text-overflow checks were empty. Independent review found no material mismatch between the observed-run report, retained evidence and inspected source. The regression results below are the earlier baseline runs; no new runtime tests were necessary for the artifact correction and read-only assessment.

## Focused regression results

### Final routing correction and corresponding proposals, 23 November 2026

The [completion record](../2026-11-23-routing-and-tobe-proposals.md) covers the five corrected generated maps and three new proposed counterparts. Validation now checks edge/card intersections, including endpoint cards, in addition to card overlaps and text fit. The deterministic preview and a finer 500-subdivision cubic check found no intersections in all eight saved canvases. Native attachment sides and wider gutters are used; no routing nodes or waypoint fields were introduced.

The current maps retain their row order, numbered steps, labels and behavior. In the two earlier targets, equivalent local report/end exits and a few deliberate row adjustments keep native curves clear. Their fold proofs preserve original actors, labels, outcomes, guards and extensions; main step/scenario counts remain 24/69 and 23/73. The three new proposed maps have their own source-backed scopes, specs, views and validation. These are artifact checks; the runtime test evidence below remains dated evidence. The manually edited comprehensive canvas was preserved byte-for-byte.

### Completed graph corrections, 23 November 2026

The initial 23 November correction covered both ingestion parents, the comprehensive target integration, the focused to-be enrichment child and a new current-execution Source child. Its checks covered structural/reference agreement, physical lane/text agreement, overlaps, repeat previews and the 34 requirement mappings. Scratch checks preserved manual notes, edges and custom metadata, refused reflow over unreviewed Owner changes and rejected a concurrent-edit commit. These remain evidence of that earlier artifact revision, not a fresh runtime test.

Generated geometry was reflowed where the corrected control structure required it, after checking the saved canvas against its original or last validated generation. This supersedes the earlier revision's fixed-position description above. The accepted actor-column style remains intact.

The latest [current-graph follow-up](../2026-11-23-current-graph-followup.md) updates five linked maps: current ingestion, current mixed-batch dispatch, current Source enrichment, to-be ingestion and focused to-be enrichment. The comprehensive `enrichment-cycle.canvas` contains manual Owner position edits and is preserved; it is not newly regenerated or counted among those five updated maps. The current [validation receipt](../2026-11-23-ingestion-enrichment-validation.json) records this follow-up's artifact checks and scope. No local-link count from an earlier revision is claimed as the current count.

These are diagram/artifact checks. The dated runtime regression results below remain historical; no paid model call or library operation was performed for this correction.

These tests use temporary fixture libraries and scripted dependencies. They do not call paid models or alter live libraries.

```powershell
.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -o faulthandler_timeout=45 tests/test_batch_review_coverage.py tests/test_w7_root_causes.py tests/test_folder_sources.py
```

**44 passed in 7.72 seconds.** This covers source-review outcomes, W7 backlog/attestation/review-route fixes and purpose/root-scoped source queueing.

```powershell
.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider -o faulthandler_timeout=45 tests/test_deep_read.py -k 'not core'
```

**28 passed, 1 deselected in 35.19 seconds.** The deselected case starts a Core; it is part of the incomplete integration evidence below. Total completed focused checks: **72 passed**.

## Core integration checks remain incomplete

A broader selection including `test_core_batch.py`, `test_core_source_batch.py`, `test_core_source_promotion.py` and paper publication did not finish. The initial run produced no output and was interrupted. A diagnostic rerun stalled while the first Core fixture was closing. A later deep-read selection reached the same condition in `test_core_deep_read_copies_schema_and_note_before_clerk_io`.

The 45-second faulthandler samples showed the MCP background worker waiting in `asyncio` event-loop initialization via `socket.socketpair()`/`accept()`, and the main test waiting in `mcp_client.clear_builtin` during `close_runtime`. Both diagnostic runs were interrupted; their progress dots are not counted as completed passes. This identifies the observed blocking stacks without attributing the cause to the environment or declaring a product regression.

No source, test, fixture or lifecycle behavior was changed to make these runs pass. Full Core integration and owner-host acceptance remain open for a later implementation packet or dedicated reproduction.
