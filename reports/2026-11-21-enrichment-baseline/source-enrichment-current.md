# Current source-enrichment child process

**Status:** descriptive execution contract checked and amended on 23 November 2026. This is an analysis diagram of existing source processing, not another executable workflow. Open the [canvas](source-enrichment-current.canvas), [specification](source-enrichment-current.spec.yaml) or [generated views](source-enrichment-current.views.md).

The [current mixed-batch dispatcher](batch-enrichment-current.md) calls this source-only detail for the selected frozen Source item. It accounts separately for folder metadata through `folder_validate → folder_describe → folder_data`, in the original mixed-item order. This source view is not the complete `process_approved` contract. Its controls describe the same admitted worker, not a second start, budget check or worker created by the diagram reference. The bounded model-task pool is internal to stages. Publication happens last inside each Source item's processing, before a separate Source acceptance decision.

The detail can summarize a source-only subset. When referenced by the mixed dispatcher, its selected subset is the one current Source item, so its inner continuation has no additional item and the outer dispatcher retains the original mixed order.

## Use-case description

| Field | Content |
|---|---|
| Name | Current source enrichment: scripted stages and legacy model tasks |
| Goal | Account for the admitted source subset with actual stage, reading and publication records, then return it to the parent for separate acceptance/recovery decisions. |
| Primary actor | The current mixed-batch dispatcher through the Core's already admitted batch services. |
| Supporting actors | Model workers using the existing legacy Clerk/cleanup/OCR transports, model host and Geo-Grapher. The generic worker lane does not assert a deployed autonomous tier hierarchy. |
| Preconditions | Explicit approval and processing-start authority; an admitted/frozen batch and selected Source item; existing access, qualification and writer constraints. The mixed dispatcher retains folder metadata and the original authoritative ledger. |
| Trigger | The parent begins or resumes its explicitly admitted source work. |
| Guarantee | Recorded outcomes preserve complete, partial, queued, inapplicable and failed work. Reading counters, publication and later acceptance stay distinct. A batch's enriched label is its status reduction, not independent verification of content. |
| Main scenario | Bind the admitted subset, check per-item controls, then validate → parse → read → lenses → Data → relate → metadata → review → publish, account for the item and continue the frozen set. |
| Extensions | Empty selection; cancellation/ceiling/interruption; conversion fallback and gaps; individual failed stages; inapplicable or partial publication; aggregate partial result or run-wide failure. The five call outcomes are `success`, `partial`, `reused`, `paused`, `escalated`. |
| Open limitations | Current reading completion follows remaining-part counters and can coexist with an unfinished source-wide derivation. No general autonomous Lead/Scribe orchestration, run-wide Oracle judgment or Doctor ticket loop is claimed. |

## Boundary and ownership

Core owns scripted fetch/extraction, literal structure, Data materialization, limited metadata prefills, schemas, literal quote/page checks, counters, declared status reduction, writer operations and storage. Model workers own generated text, readings, lens proposals, inferred relations, sensitivity judgments and Bottom Line drafts. A transport label is not a new tier definition. The to-be maps separately assign Clerk tier 2 and Scribe tier 3 responsibilities.

Data and metadata stage names do not imply model calls. Existing Data construction assembles kind-specific structure and recorded readings. Metadata currently copies limited literal Data facts and lists missing required fields. Broader semantic organization and metadata inference in the to-be proposal are additional agent responsibilities.

Conversion failures preserve current fallback behavior: a returned cleanup error may leave parse partial while raw extraction is usable; unusable generated page anchors retain that conversion unused and can still allow complete parsing from original mapped text. Missing OCR pages remain uncredited. Uncaught stage exceptions fail the item while other frozen items can continue. There is no proposed outage circuit breaker or autonomous model substitution in this current view.

Parsing also performs a free provisional paper projection. For a PDF or paper whose parse did not return early, `_parse` writes `.librarian/derived/paper-graph/<hash>.nodes.json` with `text_layer=False` before chunking and reading. That artifact can be catalogue-only or contain no reading claims. A partial full-text fetch or partial OCR returns before this write; a later no-text result can occur after it. The `preproject` card therefore sits before reading, while early partial returns bypass it. A provisional file on disk is not a successful publication or a reading receipt. Later `publish` rebuilds the projection using available completed reading; moved/quarantined or unfinished sources can leave provisional artifacts behind.

Publication requires actual complete reading, an eligible persistent conversion and a current trusted accepted **folder** assignment. Late `FOLDER_STALE`, missing folder approval, disabled Geo and caught publication errors leave a gap without erasing reading. Acceptance of the Source note is not a publication prerequisite. Existing legacy publications created before today's gate require separately scoped reconciliation, not a claim that the current gate permits unread publication.

The `publish` card is one Geo-Grapher CLI call with material side effects, not a claim of one cross-database atomic transaction. Geo-Grapher creates a new `papers-native-<uuid>.sqlite`, copies the previous active paper database when present, imports into that candidate, checkpoints the candidate paper DB and conditionally switches the catalog pointer. Previous generations and a candidate left by failure can remain on disk. The catalog itself uses WAL; the import path does not explicitly checkpoint it. WAL presence is not by itself evidence of corruption or failed publication. `dpubresult` records the call's actual outcome, including failures in these internal phases.

Source and lens outputs remain independently staged. The parent owns subsequent decisions; a valid zero-lens result does not invent a backlog. The source subset's outcome never replaces its parent's mixed source/folder ledger. The current before-item ceiling and between-stage cancellation checks are not a hard per-call monetary reservation.

## Evidence and representation

The [observed-run assessment](observed-enrichment.md) and [hashed retained evidence](observed-run-evidence.json) cover full and partial examples from 20 November, including malformed `terms` answers, exact receipt reuse, later partial acceptance and separate graph-publication results. The [cross-library review](../2026-11-22-ingestion-enrichment-graph-review.md) qualifies the broader audit counts and legacy cases.

Relevant implementation: [stage functions and provisional projection](../../src/resource_librarian/batch.py#L235), [declared stages](../../src/resource_librarian/batch.py#L600), [explicit start/frozen set](../../src/resource_librarian/batch.py#L672), [sequential execution/reuse](../../src/resource_librarian/batch.py#L784), [folder stages](../../src/resource_librarian/batch.py#L916), [status reduction](../../src/resource_librarian/batch.py#L883), [Data construction](../../src/resource_librarian/dik.py#L349), [publication admission](../../src/resource_librarian/paper_graph.py#L163) and [Geo-Grapher's paper import](F:/uv-data/Geo_Grapher/src/geographer/library_papers.py#L74).

The canvas retains the supplied actor columns, card dimensions, node colors, numbered main scenario, guarded extensions and explicit edge attachment sides. Its generic model-worker lane names the observed execution transport without rewriting historical records as the proposed tiered management process.
