# Proposed comprehensive ingestion and enrichment integration

The enrichment model covers one complete cycle: a requested reference or folder becomes captured evidence, staged work, a bounded enrichment attempt, and an explicitly accepted library result, or an accounted pause, rejection, failure or escalation. It preserves the existing ingestion contract while showing where Leads, Clerks, Scribes, the Oracle and the Doctor would take over coordination currently performed by tier 0. A lower tier-0 turn count is useful only when the full contract survives.

The model and its generated views are analysis artifacts. Specifications belong within the Librarian Core; this report is neither a deployed specification store nor another execution authority. The current model choice for both Doctor and Oracle is GLM-5.3 through the adapter and role-assignment mechanism. Their contexts remain separate and their assignments remain revisable. Review independence from the worker still needs a suitable assignment when that worker uses the same route. See [role and specification policy](../../docs/policy/agent-roles-and-authority.md#specifications-and-fault-tickets) and [model assignments](../../docs/policy/agent-roles-and-authority.md#models-are-assigned-to-roles-not-bound).

The title and `targetcontract` note identify the canvas as a proposed integration, not an execution trace. The approved [graph review](../2026-11-22-ingestion-enrichment-graph-review.md) supplies the latest amendments. Its cross-library evidence qualifies specific paths without converting historical transport labels or aggregate backlogs into proof of deployed orchestration.

## Use case description

| Field | Content |
|---|---|
| Use case name | Proposed comprehensive ingestion and enrichment integration |
| Brief description | Preserve captured evidence and derive knowledge under an explicit specification, then accept and verify the required artifacts or account for the remaining work. |
| Primary actor | Owner, directly or through a tier-0 Overseer acting under current or standing direction. |
| Supporting actors | Lead, Clerk, Scribe, Oracle, Doctor, model host and Geo-Grapher. Librarian is the system boundary; Core supplies scripted services within it. |
| Preconditions | A running Core; permitted source scope; explicit spending and action authority; qualified assignments for the work actually attempted. Planned run-wide coordination is distinguished from the existing operations below. |
| Trigger | A direct or delegated enrichment request, an authorized continuation, explicitly requested accepted-Source rereading, or scoped existing-publication reconciliation. |
| Success guarantee | Every requested item is accounted for. Required Sources or revisions are accepted with true coverage and provenance and are findable. Independent lens decisions are satisfied only where specified. Folder metadata retains its purpose/access decisions; applicable required graph obligations are checked separately. Excluded and withheld content stays protected. Permitted gaps receive a partial outcome. |
| Main success scenario | The numbered scenario in the [generated views](enrichment-cycle.views.md#written-use-case). |
| Extensions | The guarded departures, conditional rejoins, pauses, partial results and escalations in those same generated views and [the single canvas](enrichment-cycle.canvas). |
| Open questions and assumptions | Core persistence/API details for specifications and tickets; execution integration for delegated starts and run-wide permissions; semantic-role migration from legacy numeric fields. GLM-5.3 is the current revisable Doctor/Oracle assignment. A worker/reviewer assignment collision must be reconciled before claiming independent review. |

## Scope and guarantees

- Capture preserves evidence, provenance, quality findings and the reason for any quarantine. A queue entry, a captured source, a folder inventory and a Source note are different records. Exact duplicates and screened-out references leave an accounted outcome rather than entering another enrichment cycle. See [capture and deduplication](../../src/resource_librarian/intake.py#L545) and [queue settlement](../../src/resource_librarian/intake.py#L953).
- An attached folder's metadata review does not demonstrate that its documents were read. The metadata-only folder batch has its own three stages and records source content as not examined. Native reference ingestion remains available without enabled Geo folder intake. See [folder intake](../../src/resource_librarian/intake.py#L857), [folder stages](../../src/resource_librarian/batch.py#L916) and [folder scope](../../docs/WAVE_L_FOLDER_REVIEW.md).
- Approval queues a source; starting its processing is a separate operation. A batch reserves exactly the approved set at its start. Later approvals wait for another run. An already-running batch is reported rather than started again. See [batch contract](../../src/resource_librarian/batch.py#L4) and [batch start](../../src/resource_librarian/batch.py#L672).
- Evidence capture, full reading, enrichment, acceptance, writing and findability remain distinct. Acceptance may retain captured or partial coverage where the current contract permits it; such a note must not be reported as fully enriched. The run's specification states which coverage its success guarantee requires. See [acceptance states and coverage](../../src/resource_librarian/staging.py#L75).
- The same Core remains responsible for the writer, index, leases and registry gates. A long model or network task does not hold the writer, and a closed Core is not permission for a background worker to open an independent write path. See [batch commits](../../src/resource_librarian/batch.py#L70).

## Roles and entry paths

The target lanes use the owner's roles: tier 0 Overseer, tier 1 Lead, tier 2 Clerk and tier 3 Scribe. A Clerk proofreads, checks claims, synthesises and directs Scribes; a Scribe performs bounded reading and writing tasks. Current Python identifiers such as `clerk_endpoint` and legacy numeric settings describe the existing implementation. Their presence does not establish that the new responsibility split is already enforced. See [agent tiers](../../docs/policy/agent-roles-and-authority.md#agent-tiers).

### Core services and proposal ownership

The Owner's 22 November correction applies to this comprehensive map as well as the narrower to-be proposal: a swim lane names the actor responsible for the work, even when that actor calls a Core tool. Core storage does not make Core the author of a specification, description, metadata proposal or acceptance decision. See [Core services and agent ownership](../../docs/policy/agent-roles-and-authority.md#core-services-and-agent-ownership).

Core performs declared scripts: inventories, AST/text/PDF extraction, hashes, schemas, literal quote/page locators, receipt and attempt counters, stored permission checks, persistence, writer/index operations and dispatch. A stage implemented by a Python helper can still contain model work; its helper location is not its intellectual owner.

| Work in this map | Responsible actor | Core service |
|---|---|---|
| Neutral capture description and separate optional fit | Clerk (`capturedescribe`) | Fetch and preserve evidence, deterministic facts and per-reference outcomes (`a10`). |
| Model transcription or cleanup | Clerk plans and proofreads; Scribe performs bounded conversion (`conversionplan`, `conversionwork`, `conversionreview`). | Scripted extraction (`a17`), then schema/hash/locator checks and persistence (`conversioncheck`, `dconversion`, `conversiongap`). A review receipt is not a new Core judgment of fidelity. |
| Data organization, metadata and source-package reconciliation | Clerk (`a23`, `a25`, `a26`), with bounded Scribe drafts where useful | Supply scripted structure and store the submitted records/results. Unknowns and actual coverage remain visible. |
| Ingestion approval and Source/revision acceptance | Lead chooses ingestion approval (`dagentingestion`); Clerk submits ordinary authorized acceptance (`a33`, `revisionapprove`); Owner chooses reserved decisions. | Check recorded grants/modes and persist the real decision/actor; enforce guarded writes. Permission alone is not an approval. |
| Meaningful progress, realignment, pause and escalation explanations | Clerk (`dprosebound`) or Lead (`drealign`, `paused`, `escalation`) | Enforce attempt counters, persist checkpoints/tickets and route recorded flags. |
| Scope and remedy fit | Oracle judges scope; Doctor diagnoses and selects an accepted remedy. | Dispatch on their recorded verdicts and check registered resources, permissions and counters (`dscope`, `dremedy`). |

These are responsibility corrections to the behavioral model. They do not claim the planned role hierarchy or new orchestration has been implemented in the runtime.

Tier 0 may hand a specification to a Lead or use Librarian's DeepInfra agents to parallelise work for another project, within granted permissions and budgets. A person can also initiate the same capability directly through the Lead, without a tier-0 agent. Results return to the specification's owner; sub-run specifications only narrow their parent. A person-started task must not wait for an absent outside agent to finish it. See [delegation and completion](../../docs/policy/agent-roles-and-authority.md#who-finishes-the-work) and [review ownership](../../docs/policy/agent-roles-and-authority.md#review-is-kept-apart-from-the-work).

The current `process_approved` and `batch_cancel` tools are curate-only. The existing start gate must therefore be visible when mapping a delegated ingestion run. A Core-owned run envelope can eventually carry authorised execution through that gate, but neither this model nor tier 0's permission to delegate changes the present registry check. The target is an explicit authorised path, not an agent impersonating a person. See [batch tools](../../src/resource_librarian/tools/batch.py#L9) and [planned envelopes](../../docs/policy/composition.md#permission-for-a-run).

## The nine enrichment stages

The current source batch runs the following stages in declaration order. Folder metadata uses a separate `folder_validate → folder_describe → folder_data` chain. See [stage declarations](../../src/resource_librarian/batch.py#L600) and [folder stage declarations](../../src/resource_librarian/batch.py#L949).

Stage names do not all denote model calls. The [observed-run assessment](observed-enrichment.md) checks actual completed batches and retained outputs. Current Data construction assembles records from scripted structure and previously read claims; current metadata processing copies a limited fact from Data and lists missing fields. The Clerk's broader semantic Data/metadata proposals in this model are proposed responsibility, not evidence that those stages already invoke another model. The runtime's legacy endpoint labels also do not prove the proposed Clerk/Scribe hierarchy is deployed.

| Stage | Preserved mechanism and proposed ownership |
|---|---|
| Validate | Refuse an already-held note or a source with neither captured evidence nor a file. |
| Parse | Core fetches and extracts/maps text. Clerk directs Scribe conversion and reviews fidelity; Core checks fields, hashes and anchors. Returned cleanup errors retain `partial` with usable original extraction. Unmapped cleanup stays unused; original page-mapped text can yield `complete` if no other gap remains. Missing required material stays partial/queued; uncaught failures retain the wrapper's failed status. |
| Read | Read the whole source in bounded, resumable parts. Each part produces located points, limits and terms, plus grounded lens candidates where warranted. Missing model answers do not count as reading. |
| Lenses | Record the lenses actually staged during reading. Each lens remains a separate proposal for review; enrichment does not accept it. Nothing read means this stage is not applicable. |
| Data | Clerk owns meaningful organization of kind-specific records, using scripted inventories and current-text evidence: repository components, document chapters/readings, model records or dataset access records. Core constructs and stores declared records. Missing components or partial document coverage remain visible. |
| Relate | Keep static relations for non-document records; relate document chapters from their readings. A single part or insufficient substantive claims can make this stage not applicable. An unavailable model queues the work; another stated limitation makes it partial. |
| Metadata | Clerk proposes evidence-based values and reports required fields still Unknown; Core validates/stores the submission. Unknown metadata is a review prompt, not evidence that less content was read. Acceptance confirms the proposals. |
| Review | Obtain the Bottom Line draft and check its grounding and reading coverage. Distinguish an absent answer, an ungrounded answer, a refused or failed answer, and a grounded draft marked low confidence for a person. |
| Publish | For PDFs, project the completed reading and its located claims into the accepted folder's paper graph. Publication runs last and does not replace source acceptance. Non-PDF publication is not applicable. |

Stage implementations: [validate and parse](../../src/resource_librarian/batch.py#L187), [read and review](../../src/resource_librarian/batch.py#L357), [lenses and Data](../../src/resource_librarian/batch.py#L433), [relations and metadata](../../src/resource_librarian/batch.py#L500), [publication](../../src/resource_librarian/batch.py#L569). The quote-grounded lens chain, blind challenge, discard log and independent lens acceptance are described in [deep reading](../../src/resource_librarian/deep_read.py#L1).

The stage wrapper matters as much as the chain. A `failed` stage stops that item; it does not undo another item's work. A `partial`, `queued`, `skipped` or `stale` stage is recorded and the wrapper continues to later stages. Their own implementations decide whether anything useful is applicable. The final item becomes `partial` if one of those incomplete states remains; it becomes `failed` after a failed stage, otherwise `enriched`. `not_applicable` does not create partial coverage. A batch can finish while individual items remain partial or failed. See [stage execution](../../src/resource_librarian/batch.py#L803) and [item completion](../../src/resource_librarian/batch.py#L883).

`folderobserved` qualifies the separate folder chain: the cross-library audit reports twelve failed folder-item attempts in two batches, all stopping at `folder_describe` (`FOLDER_PROVENANCE` or `FOLDER_DRAFT_FAILED`), with no successful `folder_data` invocation in that sample. This is evidence about those attempts, not a claim that the implemented chain is absent or can never succeed.

### Proposed bounded route-outage handling

`conversionoutage` and `readoutage` distinguish 429/timeout/unavailable transport from invalid JSON, grounding refusal and missing required task answers. Core records existing codes, attempt counts, retry-after and priced/unpriced usage, and defers equivalent failed-route calls. Lead chooses a bounded same-route retry, continuation with actual fallback/gaps, or pause. `dconversionretry` and `dreadretry` enforce the existing grant, qualification, backoff and remaining allowance before re-entering main parse/read; compatible completed work is reused. A changed model needs an authorized qualified assignment and changed route identity, never an implicit substitute. This is target coordination around existing task outcomes, not a newly implemented outage service.

The Core guard applies at every dispatch/commit. Explicit critical branches leave each source-stage result and the folder/revision/write paths before subsequent work. The final Oracle review is not the first opportunity to report a critical integrity, false-attestation or authority violation.

## Publication and native ingestion

A PDF's graph artifact is prepared during parsing but is published only after the reading and review stages. Publication requires complete reading, a full conversion and an accepted, current folder assignment trusted under the library's promotion policy. A stale artifact or folder assignment cannot be accepted merely because a conversion exists. See [projection during parse](../../src/resource_librarian/batch.py#L272), [publication stage](../../src/resource_librarian/batch.py#L569) and [publication admission](../../src/resource_librarian/paper_graph.py#L163).

There is a specific current distinction for native ingestion: a non-PDF produces `publish: not_applicable`; a PDF whose artifact does not reach full conversion can also produce `not_applicable`. For a fully converted, fully read PDF, disabled Geo returns `disabled`, which the batch records as `publish: partial`. A missing accepted folder similarly leaves an explicit publication gap. Native capture, reading and acceptance remain available, but the model must not silently turn these PDF publication gaps into `enriched` or claim that graph publication happened. See [publication outcomes](../../src/resource_librarian/batch.py#L576) and [disabled or unaccepted folder](../../src/resource_librarian/paper_graph.py#L167).

`a27`/`dpubkind` freshly check folder/artifact admission before Geo work; `a28`/`dpubresult` preserve a late stale-folder, artifact mismatch, returned refusal or caught publication error. A **folder assignment** must be accepted, not the Source note: current publication precedes Source acceptance. The cross-library stale-folder and awaiting-folder cases therefore belong at this late boundary as well as at survey. Four reported written-but-not-findable notes qualify `35a`; vectors being off and absent concept links are observations, not proof that any one remedy will repair retrieval.

Compatible reading can be reused without asserting that an old publication remains admissible. `a15` preserves source/representation/recipe/route receipt matching; publication additionally checks affected projection/artifact compatibility and current folder authority/fingerprints. Existing completion keys do not encode every policy or assignment change. That stronger target admission does not retroactively invalidate or upgrade historical receipts by itself.

### Existing-publication reconciliation

Extension `4e` starts with read-only `maintenanceinventory`, Clerk assessment and a bounded Lead plan. Core checks actual resource radius, accepted registered components, grants and counters before any write. Accepted Sources needing reading recovery use `noteread` and the existing separately governed revision path. A committed maintenance revision rejoins `dinput` with its request retained. Finished unaccepted partials return to actual ingestion approval/new-batch admission; unfinished work resumes its authorized pinned run. No accepted Source is routed through new-source duplicate validation.

Compatible complete reading may instead support guarded `maintenanceproject` and fresh `maintenancegeo` admission. Old zero-concept graphs require evidence/projection assessment; they do not justify invented concepts, automatic rereading or full-group rebuilds. Reprojection preserves generated, source-stated and inferred labels and original-page/claim-verification limits. Active graph registrations and the true rebuild radius remain explicit; no generation deletion or WAL maintenance is authorized by this path. Oracle judges the scoped result, and unresolved/uncatalogued/code-change cases retain their existing Owner/Lead escalation boundaries.

### Separate Source and lens decisions

`a31` exposes Source, folder and lens worklists with actual state and responsible actor. `dacceptkind` routes a requested independent lens decision through `dlensauthor`: an authorized ordinary agent decides at `lensreview`; person-mode, sensitive or reserved cases go to `lensperson`. Core applies only the recorded accept/reject/defer decision through existing gated staging. This preserves [current mode/sensitivity rules](../../src/resource_librarian/staging.py#L956) without inventing an Owner-only gate. A Source decision never decides a reasoning instruction. Deferred obligations remain visible to the final Oracle. A backlog alone is neither a fault nor permission to accept it.

## Review boundaries

Three activities must remain identifiable in the same cycle:

1. **Source enrichment review** produces a grounded Bottom Line and checks full-reading coverage. Its result is part of the source's processing record. See [batch review](../../src/resource_librarian/batch.py#L377).
2. **Report claim review** judges an individual claim against its supplied passage in a separate context. It does not establish that every source in an ingestion was captured, read, accepted and indexed. See [claim review](../../src/resource_librarian/clerk.py#L338) and [existing review foundations](../../docs/proposals/diagram-workflows.md#104-what-exists-already).
3. **The planned Oracle** checks the run's success guarantee and extensions, using deterministic checks first, then bounded model judgment where needed. It reports evidence-bearing verdicts and never performs the Doctor's repairs. A remedy returns to the Oracle for rechecking. See [review policy](../../docs/policy/agent-roles-and-authority.md#review-is-kept-apart-from-the-work).

## Existing extension correspondence

These identifiers belong to the accepted [to-be ingestion spec](../2026-11-20-workflow-map/examples/ingestion/ingestion-tobe.spec.yaml). The comprehensive model retains their failure meanings and records any expanded stage's correspondence; renumbering alone must not imply a new remedy or runtime capability.

The approved amendment retains all pre-existing comprehensive node IDs, 38 numbered main steps and old extension IDs. New direct extensions include maintenance `4e`, independent lens decision `31c` and critical/transport departures at their main-stage boundaries. Nested conversion, folder and revision outcomes inherit their enclosing extension instead of introducing off-main extension numbers. No new remedy ID or fault taxonomy follows from these additions.

| Existing extension | Shape and responsibility preserved |
|---|---|
| `4a` | Another root is stale: catalogued Doctor investigation; current whole-library rebuild radius can require the Owner. |
| `6a` | Qualification lost: diagnose the existing qualification/route failure, never bypass it or silently substitute an unqualified route. |
| `6b` | Sensitive subfolder: Owner decision, relayed by tier 0 when present. |
| `9a` | Survey/queue count mismatch: reconcile accepted roots and queue evidence before capture. |
| `13a` | A read task did not answer or a page remains partial: preserve the actual coverage and waiting reason. |
| `13b` | Incomplete document processing: bounded retry of remaining work, with exact completion reuse. |
| `14a` | Spend ceiling: pause for the Owner's budget decision; never enlarge it autonomously. |
| `16a` | Person-mode acceptance: alert the Owner and wait for their acceptance. |
| `17a` | Written result not findable: bounded index repair only when catalogued and admitted. |
| `18a` | Oracle shortfall at a mapped extension: Doctor remedy, followed by Oracle recheck. |
| `18b` | Unmapped misalignment: Clerk investigation and Lead realignment, or escalation when outside authority. |
| `20a` | Overseer's review needs another pass: send the specification and evidence back for judgment and bounded correction; the Oracle does not execute instructions as a worker. |

The old Doctor example says the Core automatically rolls back a failed remedy. The governing [compensation rule](../../docs/policy/composition.md#what-a-process-may-contain) instead shows an undo for a person's decision. The comprehensive model follows that rule and retains any failed remedy's evidence; it must not introduce automatic compensation. See the historical wording at [Doctor `x4`](../2026-11-20-workflow-map/examples/ingestion/doctor.spec.yaml).

## Ticket routing and decisions

The fault register is the planned ticket service: existing failures and extensions, their evidence and tiered flags, the actor responsible, attempted remedies and the Oracle's recheck. Flags describe the problem and handling responsibility; they do not grant permissions or encode a new numeric severity scheme. Existing diagnostic invariant labels can accompany a ticket without becoming a universal bitmask. See [fault ticket policy](../../docs/policy/agent-roles-and-authority.md#specifications-and-fault-tickets).

| Existing class or condition | Responsible actor | Result or escalation |
|---|---|---|
| Mapped failure with an accepted, bounded remedy | Doctor, within granted scope | Run the remedy through registered actions; Oracle rechecks before resolution and rejoin. |
| Unmapped failure or misalignment | Lead; Clerk investigates and directs bounded Scribe tasks | Realign within the specification, propose a remedy for later acceptance, or escalate. |
| Critical security, data loss or authority boundary crossed | Owner and tier 0, when present | Report immediately; no repair loop grants wider authority. |
| Sensitive content, spending without approval, person-mode promotion or another reserved decision | Owner | Pause the affected operation; tier 0 or Lead relays the concrete decision. |
| Outside a run envelope but within the mandate | Planned Oracle scope judgment | Evidence-bearing allowance reported with the run; current broker checks remain until implemented. |
| Outside mandate, uncertain scope or uncatalogued repair | Orchestrating tier 0 or Owner; Lead for owned work | Escalate or retain a visible pause. A Doctor diagnosis alone is not authority to proceed. |
| Passed run or resolved ticket | Specification owner | One handback with the verdict, evidence and remaining limitations. |

The reserved-decision row is a checkpoint, not a defect to repair. A direct user run uses the same human boundary without inventing a tier-0 dependency. The future ticket service must reuse current refusal/evidence and actor distinctions; its Core persistence and general routing are not deployed by this analysis.

## State and integrity acceptance

The single model and its views must retain these acceptance conditions:

- Every queued or staged source has an accounted outcome, with provenance and actual coverage. Folder metadata is never counted as a read document. A finished batch is never substituted for acceptance or findability.
- Resume uses the pinned run and admitted inputs. Reusable stage completions match evidence/source identity, attached and cleaned bytes, the recipe chain and model route. Source changes during a stage make that completion stale. Dependencies rerun affected later stages. See [identity and keys](../../src/resource_librarian/batch.py#L122) and [reuse and stale results](../../src/resource_librarian/batch.py#L803).
- Cancellation and the spend ceiling stop processing with a durable resumable record. A changed staged-item decision is not overwritten by the worker. A closed writer cannot trigger a direct write fallback. See [active-item guard](../../src/resource_librarian/batch.py#L116), [run stops](../../src/resource_librarian/batch.py#L784) and [interrupted writer handling](../../src/resource_librarian/batch.py#L867).
- General workflow replay preserves exact reachable definitions and handles a dispatched write with no result as `outcome_unknown`, requiring a person's choice. That runner guarantee is distinct from the existing batch's stage-key resume logic; neither should be claimed as an implemented replacement for the other. See [workflow run contract](../../src/resource_librarian/workflows.py#L23).
- Acceptance records the actual person or agent, honors sensitivity and promotion mode, and keeps partial coverage. Interrupted promotion has its own person-review checkpoint. See [acceptance preparation](../../src/resource_librarian/staging.py#L569).
- Actor lanes, guarded branches, extension endings/rejoins, reference outcomes and tests remain projections of one model. Existing canvas geometry and owner edits survive production rendering through the safe canvas service. A structural validator pass does not establish that the modeled responsibility or authority is correct. See [four-view contract](../../docs/proposals/diagram-workflows.md#3-the-four-views-and-how-they-check-each-other) and [canvas contract](../../docs/proposals/diagram-workflows.md#9-phases).
