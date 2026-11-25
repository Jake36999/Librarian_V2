# Observed enrichment: completed runs and retained outputs

**Assessed:** 22 November 2026. The Owner authorized inspection of prior enrichment or a new run costing up to $2. Two completed 20 November batches provide a full case and a mixed full/partial case. No new enrichment, model calls or spending were needed: **$0 new model spend**.

This assessment reads the actual run logs, staging records, conversions, Data records, paper-graph artifacts, accepted Source notes and model-usage ledger in `G:\Libraries\Resource-Library`. The [evidence snapshot](observed-run-evidence.json) records paths, hashes, receipts, acceptance history and attribution limits. Current source inspection explains the scripted/model boundary; it is distinguished from observed execution below.

## Actual executions

| Run | UTC execution on 20 November | Observed result | Model usage within its time window |
|---|---|---|---|
| [batch-2026-11-20-3b62fc](G:/Libraries/Resource-Library/.librarian/runs/batch-2026-11-20-3b62fc.jsonl) | 07:49:06–07:50:41 | One item enriched; nine fresh stage-completion receipts; 8/8 reading parts. | 40 calls; $0.007969 reported. |
| [batch-2026-11-20-d297e0](G:/Libraries/Resource-Library/.librarian/runs/batch-2026-11-20-d297e0.jsonl) | 13:47:27–14:02:05 | Six selected items accounted for: three enriched, three partial. | 182 calls; $0.039595 reported. |

The single-source case is *A BigData-Machine Learning system for Monitoring Road Surface Condition*. Its nine stages all returned `complete`. The retained Data artifact contains two chapter records and one document-order relation; the relate stage added zero further relations. Lenses completed with zero staged candidates. Completion therefore does not require inventing a lens or semantic relation where none is produced.

The six-item reread finished with these results. Fractions count reading parts/chunks, not independently verified PDF pages.

| Source | Read parts | Item result | Retained publication result |
|---|---:|---|---|
| Postgres | 2/2 | Enriched | Complete |
| G-Retriever | 20/21 | Partial | Partial: reading incomplete |
| Simple HHEA | 15/15 | Enriched | Complete |
| OLMoE | 43/44 | Partial | Partial: reading incomplete |
| NoSQL Z-Curve | 10/10 | Enriched | Complete |
| MoE-KG recommendation | 17/18 | Partial | Partial: reading incomplete |

This reread has **42 fresh stage-completion events**, rather than 54. Validation was reused for all six items; parsing and metadata were also reused for the three partial items. Matching completion keys link the missing fresh events to older receipts. The retained item status and a fresh stage invocation are different evidence. This agrees with the [existing reuse rules](../../src/resource_librarian/batch.py#L803).

## A concrete unresolved failure

Each of the three partial items records a `terms` task refused after its response failed JSON parsing. The read stage remained `queued` with its task-specific reason and actual coverage. Later applicable stages still ran; Data, review and publication retained their partial outcomes. A successfully drafted Bottom Line did not make the incomplete reading complete. These are format/structured-output failures recorded by the task layer; they are not evidence that the provider declined the subject matter.

The model-usage ledger labels those provider calls `completed`, while the task receipts subsequently record parsing refusals. A Doctor/Oracle loop must consume the task and stage evidence as well as transport telemetry. Retrying a known failed part and proving that it completed is a useful concrete recovery case; this assessment does not establish or execute a new remedy.

All seven original PDFs, Data artifacts and accepted notes exist. All seven retained graph hashes match their applicable receipts. Four graph artifacts report `full_conversion`; the three partial cases retain `catalogue_only` artifacts. Graph receipts explicitly limit original-page and claim verification. File existence, a matching artifact hash and complete processing counters do not independently prove the source's claims.

## Acceptance happened separately

All seven staging records now say `accepted`, and their promotion records say `catalogued`, with recorded write/index/findability steps successful. The six reread items were accepted at 14:04:54–14:05:00 UTC, after their batch finished. The earlier single-source item was accepted at 13:42:36 UTC.

Acceptance history records `by: person`; the reasons cite the Owner's instruction and say Claude applied it. Those records describe a decision attributed to the Owner and an agent applying it, rather than proving that a person clicked a particular control. The three partial Source notes preserve their partial coverage. Acceptance did not retroactively complete their reading or enrichment publication. Findability here is the recorded promotion result; no fresh search or promotion was performed for this assessment.

## Scripted work and model work

The observed ledger contains calls for PDF cleanup, points, limits, terms, lens derivation, chapter relations, sensitivity and Bottom Line drafting. Historical routes were `deepseek-ai/DeepSeek-V4-Flash-0731` for cleanup and `google/gemma-4-26B-A4B-it` for the legacy Clerk transport. These names are observations of those runs, not changes to role assignments or evidence about the current Doctor/Oracle binding.

| Stage | Existing mechanism supported by receipts and current source | Consequence for the maps |
|---|---|---|
| Validate | Scripted identity, evidence and duplicate checks. | Core service. |
| Parse | Scripted fetch/extraction/page mapping, with paid model cleanup where used. | Separate scripted extraction from model transcription/cleanup. The proposing to-be Clerk/Scribe roles do not make Core the author of converted text. |
| Read | Bounded model tasks; scripts check schemas, literal support, receipt identities and coverage. | Agent reading/interpretation, Core mechanical checks and storage. The proposed Clerk/Scribe management hierarchy remains proposed. |
| Lenses | Model derivation occurs during reading; the named stage records the resulting proposals/counts. | Agent owns selection and reasoning; Core persists actual dispositions. Zero candidates can be valid. |
| Data | Scripts assemble chapter/component records from structure and existing reading claims. The inspected records use headings or fixed page runs, with document-order relations. | Retain Core's scripted materialization. Broader meaningful organization proposed for Clerk is additional agent responsibility, not an observed extra model call. |
| Relate | Model chapter-relation work when applicable; static/document-order relations already exist separately. | Distinguish inferred relations from scripted structure; zero additional relations can be valid. |
| Metadata | Current code copies a missing language value from Data where available and checks required-but-missing fields. It does not invoke a general semantic metadata model. | Core retains literal prefills/schema checks. The to-be agent owns interpreting evidence and proposing additional values/Unknowns. “Content model” here names a content schema. |
| Review | Model drafts and sensitivity work, with scripted grounding/coverage checks. | Agent owns the prose and judgment; recorded draft success does not override incomplete reading. |
| Publish | Scripted applicability/admission and graph publication with actual reading/conversion prerequisites. | Separate publication from Source acceptance and from an Oracle's semantic verdict. |

Relevant source: [parse](../../src/resource_librarian/batch.py#L198), [read/review](../../src/resource_librarian/batch.py#L357), [lenses/Data](../../src/resource_librarian/batch.py#L433), [relations/metadata](../../src/resource_librarian/batch.py#L500), [publication](../../src/resource_librarian/batch.py#L569), [Data construction](../../src/resource_librarian/dik.py#L349), and [model usage](../../src/resource_librarian/usage_log.py#L20). The module called `clerk` is a legacy implementation label; it does not itself demonstrate the Owner's tier-2/tier-3 responsibility split.

## Effect on the proposed process

The [comprehensive canvas](enrichment-cycle.canvas) and [focused to-be proposal](../2026-11-22-proposed-tobe-enrichment/PROPOSAL.md) retain the nine stages, exact reuse, partial coverage, item isolation and separate acceptance/publication. Their agent lanes describe proposed responsibility. Core retains scripted derivations and enforcement; model interpretation, semantic proposals and explanations belong to the assigned agent.

These observed batches do not demonstrate a general autonomous Lead handoff, a Clerk managing a separate Scribe role, run-wide Oracle conformance review, or catalogued Doctor recovery. Those remain target integration around mature existing processing. The `terms` failures provide a specific case against which a later scoped recovery proposal can be assessed.

## Evidence limits and cost

The two windows contain $0.047564 of historical reported model usage in total. Every included row has a price and input-token count, and no other recorded batch overlaps either window. The usage rows have no run/item IDs, so timestamp correlation cannot establish an exact per-run bill or exclude unrelated calls. These historical costs are not charged against the newly authorized $2; this assessment made zero model calls.

An authenticated, read-only `/api/meta` check on 22 November returned Core `2.1.0.dev0`, protocol `2`, writer `ready` and vault lease `held` for Resource-Library. It exposes no Git commit and does not establish the precise code build used on 20 November. No service was started/restarted, no role assignment or budget was changed, and no library item was written. This is execution-record and retained-output assessment, not an independent verification of the papers' claims or a new end-to-end test.
