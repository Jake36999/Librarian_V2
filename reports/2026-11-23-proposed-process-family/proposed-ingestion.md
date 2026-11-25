# Proposed to-be ingestion

**Status:** behavioral proposal, 23 November 2026. [Canvas](proposed-ingestion.canvas), [specification](proposed-ingestion.spec.yaml), [generated views](proposed-ingestion.views.md). This is the parent of the proposed [mixed-batch dispatcher](proposed-batch-enrichment.md), whose Source branch calls [source enrichment](proposed-source-enrichment.md).

The corrected [current ingestion](../2026-11-20-workflow-map/examples/ingestion/ingestion.canvas) supplies the observed operations and their real boundaries. The [existing ingestion target](../2026-11-20-workflow-map/examples/ingestion/accepted-ingestion-tobe.canvas) supplies the previously reviewed authority and recovery requirements. This new revision composes those requirements with an explicit mixed dispatcher and includes the folder-card decisions that a source-only handoff could hide.

## Use-case description

| Field | Content |
|---|---|
| Name | Proposed to-be ingestion: accountable mixed processing and separate decisions |
| Goal | Fulfil a commissioned ingestion goal with truthful processing, graph coverage, independent decisions and required findability. |
| Primary actor | Owner directly, or tier-0 Overseer acting within the Owner's mandate; the tier-1 Lead owns execution. |
| Supporting actors | Clerk tier 2, Scribe tier 3, independent Oracle, scoped Doctor, scripted Core, model host and Geo-Grapher. |
| Preconditions | Permitted roots, exclusions, outputs and acceptable partials are explicit; start/spending and decision grants identify actual actors and reserved Owner choices. |
| Trigger | The Owner or Overseer commissions the Lead with a bounded specification. Core stores that specification within the existing Librarian state. |
| Guarantee | Completed evidence survives partial work and refusals. Folder access, reading, Source acceptance, independent lens decisions and graph publication retain their own states. Unmet required work is handed back truthfully. |
| Main scenario | Commission, survey, propose and apply folder decisions, reconcile eligible work, capture, approve and explicitly start the mixed child, resolve independent decision worklists, apply guarded writes, check retrieval and obtain the Oracle's parent verdict. |
| Extensions | Reserved or stale folder decisions; capability/coverage shortfalls; capture or queue gaps; no new work; mixed partials; cancellation or ceiling stop; held writes; retrieval failures; mapped repair or unmapped Lead diagnosis. Owner-directed entry and handback work without an Overseer. |

## Changes from the corrected current graph

| Current boundary | Proposed behavior and owner |
|---|---|
| Tier 0 coordinates the observed run. | Lead owns direction and correction within the commission. Clerk directs bounded Scribe work; the Overseer can delegate in support of its own external task. |
| Common folder application can rebuild all accepted groups and its receipt omits parse failures. | Geo returns explicit group, coverage, parser and version evidence. Compatible unchanged snapshots are reused and affected groups are identified. Core validates receipts mechanically; Lead judges quality against the allowance, followed by independent final Oracle review. This reporting and bounded group application require integration. |
| Approve, start and accept are different operations. | Each retains its actual actor and grant. A delegated run proceeds inside its existing authority; reserved or missing authority returns to the Owner. |
| `process_approved` contains both source and folder cards. | The parent calls one mixed child, preserves the original ledger and accounts for all kind-specific outcomes. Source-item detail does not create another worker, store or commission. |
| Folder enrichment does not examine its documents. | Folder metadata goes through its own review and current-fingerprint application. It receives no document-reading credit. Newly requested document scope returns to reconciliation under actual authority. |
| Processing completion leaves separate decisions. | Source, folder-card and lens worklists each name their actor, status and remaining obligation. Held or deferred decisions remain visible; no new work does not imply that all decisions are settled. |
| Failures often return to the external orchestrator. | Existing flags become accountable tickets. Doctor executes only matching accepted remedies within their actual radius; unmapped diagnosis belongs to Lead. Oracle judges revised evidence independently and does not issue worker orders. Critical findings immediately reach the actual specification owner. |

The Oracle's parent review concerns the commissioning goal, decisions, access, required findability and final accounting. It uses the source and batch verdicts as evidence instead of repeating their entire reviews. The source Oracle judges required evidence and derivations; the batch Oracle judges the original mixed ledger and cross-item obligations.

Later Folders-review application uses the same proposed group-receipt and quality contract as the initial application. Required lens decisions have an explicit ordinary Clerk or reserved Owner route, followed by scripted recording of accept/reject/defer. A permitted deferral can satisfy the recorded scope; an unresolved required decision remains a held obligation. Neither path silently rewrites Source acceptance.

After reading repair, an explicit re-entry check distinguishes resuming compatible unfinished admitted work from re-approving an affected finished-partial subset. The latter returns through actual approval and start admission. It retains the original parent ledger and previous batch evidence, and does not recapture an existing Source.

## Compatibility and unresolved implementation work

The activity-spec format and accepted actor-column notation are unchanged. Composition remains action → workflow → pipeline → sprint. These diagrams define behavioral responsibilities, not another executable scheduler, runtime specification schema or storage service.

The Doctor references retain the existing [UC-D contract](../2026-11-20-workflow-map/examples/ingestion/doctor.spec.yaml) and [remedy catalogue](../2026-11-20-workflow-map/examples/ingestion/remedy-catalogue.yaml). Original remedy correspondence refers to the reviewed `ingest-papers-tobe` use case; this report revision does not register new catalogue keys or authorize a proposed remedy. General ticket/specification enforcement and revised delegated tools remain implementation work. Oracle and Doctor currently use GLM-5.3 through revisable role adapters.

Paper publication retains its current trusted accepted-folder prerequisite and explicit reading/artifact admission; Source-note acceptance is a separate later decision. Database-generation retention or cleanup is a separately authorized maintenance process with verified active references, not an automatic side effect of this proposal. Metadata proposals retain `Unknown` when evidence is insufficient.

Primary evidence: [folder application](../../src/resource_librarian/folder_review.py#L577), [current receipt checks](../../src/resource_librarian/folder_review.py#L280), [mixed batch execution](../../src/resource_librarian/batch.py#L784), [folder decision boundary](../../src/resource_librarian/staging.py#L919), [guarded Source acceptance](../../src/resource_librarian/staging.py#L956), and the [current graph correction record](../2026-11-23-current-graph-followup.md).
