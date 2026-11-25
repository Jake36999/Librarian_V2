# Current mixed approved-batch dispatcher

**Status:** current-code descriptive contract, 23 November 2026. [Canvas](batch-enrichment-current.canvas), [spec](batch-enrichment-current.spec.yaml), [written views](batch-enrichment-current.views.md).

This supplies the mixed `process_approved` boundary referenced by ingestion. One existing worker freezes the approved `source` and `folder` records, then chooses `STAGES` or `FOLDER_STAGES` per item. The source reference describes that item's existing stage sequence; it does not start a second worker, create another run ledger or spend another control-check budget. The source child's loop receives a singleton when shown inside this dispatcher.

## Use-case description

| Field | Content |
|---|---|
| Name | Current approved batch: source and folder-metadata dispatch |
| Goal | Account for every frozen item with its actual kind-specific stages, coverage and remaining decisions. |
| Primary actor | Parent caller through the existing admitted Core batch worker. |
| Supporting actors | Model worker through legacy transports; the source child also includes model host and Geo-Grapher. |
| Preconditions | Existing explicit approval and processing-start authority, active Core/writer, qualified permitted routes and the frozen mixed selection. |
| Trigger | The parent starts or resumes its admitted approved batch. |
| Guarantee | Item failure retains completed sibling work; folder metadata never credits document reading. Finished processing does not accept Sources, folders or lenses. |
| Main scenario | Bind the admitted set, select each item, dispatch its source or folder stages, retain the current item result and return the mixed accounting. |
| Extensions | No work; folder metadata; queued/partial/failed source or folder stages; stop/interruption; run-wide failure. Exact caller outcomes: `success`, `partial`, `reused`, `paused`, `escalated`. |
| Limitations | This is an analytical decomposition of current code. It does not add autonomous tiers, parser-capability checks, Doctor recovery or Oracle conformance review. |

The source path calls [current source enrichment](source-enrichment-current.md). The folder path is explicitly `folder_validate → folder_describe → folder_data`. Description is bounded model work; inventory/provenance checks, storage and Data materialization are Core scripts. Production-disabled description is queued; a failed stage skips the remaining stages for that item. Folder coverage remains **metadata only; source content not examined**, even when the card is enriched.

The inspected cross-library sample had twelve folder-item failures in two batches, all at `folder_describe`, with no successful `folder_data` in that sample. This does not remove the implemented normal path or claim a future failure rate. The DataManagement historical parent did not thereby execute those earlier folder failures; they are evidence for the current-code alternative.

Source: [mixed stage selection and execution](../../src/resource_librarian/batch.py#L784), [item reduction and folder coverage](../../src/resource_librarian/batch.py#L883), [folder stages](../../src/resource_librarian/batch.py#L916), [explicit batch admission](../../src/resource_librarian/batch.py#L672). The original parent ledger remains authoritative throughout.
