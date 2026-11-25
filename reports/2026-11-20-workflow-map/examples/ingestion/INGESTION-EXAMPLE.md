# DataManagement ingestion: observed path and current-code alternatives

Revised 23 November 2026 against the retained run evidence and [graph review](../../../2026-11-22-ingestion-enrichment-graph-review.md). This records the Owner-directed, tier-0-orchestrated ingestion of 96 papers from `E:\DataManagement` into Resource-Library. Its final result was **96 accepted Sources: 93 fully read/published items and three accepted partials**, with their incomplete coverage and publication gaps retained. It does not claim 96 complete graph publications.

The historical [spec](ingestion.spec.yaml), [canvas](ingestion.canvas) and [generated views](ingestion.views.md) describe the parent use case. Its `enrich` reference calls the [current mixed-batch child](../../../2026-11-21-enrichment-baseline/batch-enrichment-current.md), which dispatches Sources to the [nine-stage source child](../../../2026-11-21-enrichment-baseline/source-enrichment-current.md) and folder metadata to its own three-stage chain. These current-code contracts do not add autonomous Lead, Oracle or Doctor loops to this history. The [to-be companion](INGESTION-TOBE.md) separately proposes those responsibilities.

## Boundary and ownership

The system boundary is Librarian. Core inventories, counts, captures evidence, applies declared rules, stores decisions, dispatches stages and checks writer/search facts. The agent owns interpretation, folder descriptions and sensitivity assessment. The historical folder-review lane is labelled **Model worker (legacy transport)**. It records the observed transport without retroactively asserting either the old numeric Clerk slot or the proposed tier-2/tier-3 management split. The bounded source reads remain inside the current child under its **Model worker (legacy transport)** lane. There was no demonstrated autonomous Lead/Clerk/Scribe orchestration in this run.

Hidden/scratch and Owner-excluded material remains withheld. Eligible ownership follows the deepest accepted root. Core submits the affirmative decisions and read barriers in `a7`; Geo-Grapher then applies **all accepted, non-excluded groups**, including own-docs, research-docs and third-party/paper groups. It invokes code/text snapshot ingestion with `reuse_complete=True`, so matching complete snapshots can be reused. This common application happens before `dinput` chooses whether any Source-eligible requested subset remains. The own-code/data/log branch does not call another indexing operation.

Core's actual CLI boundary checks exit status, valid JSON and the pinned version. The returned folder-application JSON identifies graph/snapshot results but omits parser failures; a successful receipt does not attest complete extraction of every language. The former `wholeindex → indexcheck → dindex` capability-verification chain was therefore removed from this current/historical view. Such validation remains proposed in the to-be view.

The [mixed-batch child](../../../2026-11-21-enrichment-baseline/batch-enrichment-current.md) shows `process_approved` dispatching the frozen source/folder set. Folder metadata uses `folder_validate → folder_describe → folder_data`, with its own failures and review obligation. Source reading receives no credit for those metadata cards. Historical enqueue entries saying `queued` are reconciled to current staging/processing state rather than counted as current pending work by themselves.

The default path deliberately follows the recorded **partial** child result and the Owner's explicit partial acceptance. A full-success child return is an alternative; a red extension arrow means departure from that historical default, not necessarily failure. Unexercised guards describe current-code alternatives and are not asserted to have occurred in the DataManagement cohort.

## Historical main scenario

1. **Owner** directs E:\DataManagement ingestion into Resource-Library with pre-read exclusions; later partial acceptance remains an explicit decision.
2. **Tier 0 agent** attaches the folder on the Owner's behalf.
3. **Core** inventories roots, fingerprints and literal folder facts; excludes hidden and scratch content before reading.
4. **Owner** decides purpose and exclusions: 11, 12, 13 and _external remain unread.
5. **Tier 0 agent** submits the Owner's folder decisions with their actual authority and reason.
6. **Model worker (legacy transport)** drafts folder descriptions and sensitivity findings through the historical legacy model transport.
7. **Core** submits affirmative folder decisions and read barriers for group application; acceptance is recorded only after the CLI succeeds.
8. **Tier 0 agent** requests Source queueing per deepest accepted root for third-party, research-docs and own-docs content.
9. **Core** captures immutable source evidence and records each reference result; retains exclusions, duplicates and isolated parser/quarantine failures.
10. **Model worker (legacy transport)** writes neutral descriptions from captured evidence through the legacy model transport.
11. **Core** stages Source evidence and records mixed-batch item identities; folder cards remain distinct from Source content.
12. **Tier 0 agent** submits the Owner-authorized ingestion approvals with executor, decision authority and recorded attestation distinguished.
13. **Tier 0 agent** requests an explicit processing start through the existing curate/person authority; approval alone only queues.
14. **Core** validates the existing curate/person start permission and freezes the approved selection; returns the active run instead of duplicating it.
15. **Core** dispatches the approved mixed batch: Sources use nine stages; folder metadata uses its separate three-stage chain.
16. **Tier 0 agent** accepts 96 Sources under the Owner's direction, retaining 93 fully read/published items and three accepted partials with publication gaps.
17. **Core** applies the guarded Source writer and retains the actual commit/refusal/attempt state; Source acceptance does not accept lenses.
18. **Tier 0 agent** reconciles current Source states, coverage, publication receipts, labels and separate lens decisions; reports the dated cohort truth to the Owner.

The Source acceptance decision remains separate from the independent lens worklist. A Source acceptance does not accept any lens. Pending lens acceptance, rejection or deferment retains its own responsible actor and matters to completion only as required by the parent contract.

## Processing contract and outcomes

Approval queues work. The existing curate/person-authorized start is a separate request; it freezes the approved selection. An already-running batch is returned rather than duplicated. Future delegated start authority is proposed in the to-be view and must not be inferred from the historical agent promotion mode.

The mixed-batch child executes frozen items sequentially and dispatches by item kind. Each source runs **validate → parse → read → lenses → Data → relate → metadata → review → publish**, including publication before the next item. Its bounded task pool provides internal model-call concurrency. Spend observation is not another document worker: the configured ceiling is checked before each item; cancellation is checked between stages. A ceiling is not a hard per-call billing guarantee, and unpriced calls retain unknown cost.

| Child outcome | Historical parent continuation |
|---|---|
| `partial` | Main cohort result: check whether actual partials are permitted; accept only with truthful coverage and publication limits. |
| `success` | Rejoin the same eligibility/decision checks; this alternate does not rewrite the historical 93/3 split. |
| `reused` | Reconcile existing/no-new-work states and remaining decisions without duplicating work. |
| `paused` | Retain completed siblings and distinguish cancellation, interruption, ceiling stop and a pending decision. |
| `escalated` | Report unresolved fault, originating stage and existing flags to the Owner through tier 0. |

Six items were initially partial; three became complete on bounded rereading. Three were accepted at about 95–98% with partial coverage. Re-approving finished partial work and admitting a new batch differs from resuming an unfinished frozen run. A failed/queued required task receives no reading credit. Successful siblings and previous receipts survive isolated input or stage failures.

Publication admission requires the current trusted accepted **folder assignment**, appropriate complete reading/conversion, artifact binding and enabled Geo. It does not require an already accepted Source note. Disabled, stale or refused publication retains the reading and actual publication reason; optional/not-applicable publication does not become a fabricated success.

## Findings, with dates and populations

| Finding | Evidence and correction |
|---|---|
| F1: historical OP1 | On 19 November the enriched cohort was left staged; acceptance occurred on 20 November. This was an unowned/invisible handoff. Later W7 `awaiting_acceptance()` visibility in agenda, status and context must be acknowledged; a backlog alone does not prove the alert remains broken. |
| F2: decision attribution | Historical records may say `by: person` while their reason attributes the Owner's decision and Claude's execution. Separate authority, executor and recorded attestation. Those records alone do not prove impersonation or disprove current agent-actor handling. |
| F3: stale root | `9c0592d` addressed excluded-root interference. OP2 remains: the existing rebuild can have whole-library scope, so a seemingly local retry needs the actual radius. |
| F4: qualification | The shared qualification-store overwrite defect caused 23 `FOLDER_DRAFT_FAILED` refusals and was fixed in `cab623a`. Timeout, parser capability and task refusals have different evidence and must not all use that diagnosis. |
| F5: orchestration | Tier 0 coordinated this run through Core calls. The to-be assigns accountable Lead ownership and independent checking without claiming those roles already ran. |
| F6: retrieval and controls | Sensitive-folder and written-but-not-findable branches were not exercised in this 96-item cohort. Four later cross-library not-findable cases were reported by the 22 November audit. Preserve the already-written note and actual missing query; vectors being off or zero concepts is not a proven common cause. Eight cancellations and zero observed ceiling stops are cross-library audit counts, not DataManagement counts. |

The cross-library audit also reports 750 processed Sources and 689 lenses awaiting decisions. These are dated reported worklist counts, not a permission to accept them or a result of this 96-item run. Its 12 folder-card failures are item attempts across two batches: validation completed, description failed, and no successful `folder_data` execution was observed in that sample.

## Extension and node correspondence

Retained behavior keeps its node ID. Renumbering follows the corrected main scenario; extensions identify graph branches, not new runtime error codes.

| Previous extension or nodes | Corrected location |
|---|---|
| `3a` stale root; `5a` qualification; `6a` sensitive; `8a` per-root queue | Same extension IDs; recovered qualification now rechecks `d2`; held decisions have affirmative/exclude/decline/hold guards. |
| `12a`, `a11`, `a12`, `m1`, `dm` | `enrich` and the current child's parse/read/transport/task-validation boundaries. Model host reports transport; Core validates application task structure/status; semantic interpretation belongs to the worker. |
| `f1`, `j1`, `a13` | Removed misleading document fork/join and post-join publication. `enrich` owns sequential per-item publication. |
| `a14`, `14a` | `a14` is a progress/control note; child stop returns through `15c`. No fake concurrent spend worker. |
| `12b` partial reread | `15e`; new authorized approval/start is distinct from unfinished-run resume. |
| `15a` nobody accepts | `16a`, retaining the dated OP1 episode. |
| `16a` not findable | `17a`, retaining written-but-not-findable state. |
| Newly explicit | Common Geo folder-group application, CLI-only receipt validation, purpose-based Source applicability, mixed source/folder dispatch, isolated capture failures and all five child outcomes. |

## Regeneration and verification

Use the report-local safe renderer from this directory:

```powershell
..\..\..\..\.venv\Scripts\python.exe -B render_corrected.py --commit --png
```

This maintains the saved actor-column style, retained card positions and manual edge attachment sides; it also writes the accepted to-be canvas under `accepted-ingestion-tobe.canvas`. Do not use the prototype's file-writing entry point to overwrite those accepted layouts. Child artifacts have their own renderers; see the mixed-batch companion and `reports/2026-11-21-enrichment-baseline/render_current.py` for source execution, plus `reports/2026-11-22-proposed-tobe-enrichment/render_proposal.py` for the focused target.

The prototype's structural, path, cross-view and reference checks can be run in memory against the actual child contracts. Their generated test tables are diagram consistency scenarios, not newly executed runtime tests. No library processing, acceptance, indexing, service changes or paid calls accompany this documentation correction.

## Source-backed folder-application boundary

The configured Geo wheel matches the inspected source for this path. [Core folder application](../../../../src/resource_librarian/folder_review.py#L577) sends the accepted decision set; [CLI receipt handling](../../../../src/resource_librarian/folder_review.py#L266) checks process/JSON/version, while Geo `apply_review` invokes all non-excluded graph groups and omits its internal parser-failure report from the returned JSON. Snapshot structural completion is not a language-extraction completeness guarantee.
