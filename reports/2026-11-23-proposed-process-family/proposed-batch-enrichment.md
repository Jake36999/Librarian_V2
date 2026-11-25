# Proposed to-be mixed-batch enrichment

**Status:** behavioral proposal, 23 November 2026. This is the target counterpart of the corrected [current mixed-batch dispatcher](../2026-11-21-enrichment-baseline/batch-enrichment-current.md). Open the [canvas](proposed-batch-enrichment.canvas), [spec](proposed-batch-enrichment.spec.yaml) or [generated views](proposed-batch-enrichment.views.md).

The same Lead receives the invoking ingestion process's admitted mixed selection. The existing ledger retains every frozen source and folder item in mixed order. This child adds accountable semantic authorship, child-contract review and bounded repair to that existing dispatch boundary. Its [source child](proposed-source-enrichment.md) receives the one currently selected source item; that reference does not create another batch worker, budget or commission.

## Use-case description

| Field | Content |
|---|---|
| Name | Proposed to-be mixed-batch enrichment |
| Goal | Return every admitted source or folder item with actual kind-specific coverage, required outputs, accountable gaps and independent child-contract judgment. |
| Primary actor | The Lead responsible for the invoking parent's commission. |
| Supporting actors | Clerk, Scribe, Oracle, Doctor and scripted Core services; source processing also uses the configured model host and Geo-Grapher. |
| Preconditions | Parent-held specification stored in Core; approved frozen selection; actual processing-start, access and spending grants; qualified role assignments; active writer and existing receipt keys. |
| Trigger | Ingestion invokes or explicitly resumes its admitted mixed enrichment work. |
| Guarantee | Completed sibling work and item identities survive an item failure. Folder metadata earns no document-reading credit. Coverage, publication and independent Source, folder and lens decisions remain distinct. |
| Main scenario | Inherit the commission, check admission, select each frozen item, apply controls, dispatch the selected source or folder chain, update the original ledger, reconcile the packages, obtain the Oracle's scoped verdict and return to the parent. |
| Extensions | No fresh work; missing authority; queued/partial/failed item; cancellation or ceiling stop; critical failure; mapped bounded remedy with independent recheck; unmapped diagnosis and an explicit partial or paused handback. |

The call returns exactly `success`, `partial`, `reused`, `paused` or `escalated`. Success means the required **mixed child outputs** are satisfied; the invoking parent still owns its acceptance decisions and final specification verdict. Reused means no fresh admitted child work, with reconciled receipt states. It never converts unresolved parent obligations into success. Paused and escalated return through the parent, whose commissioner may be the Owner directly or an external tier-0 Overseer; an absent tier-0 agent does not block a user-run process.

## Changes from the corrected current graph

| Current boundary | Proposed change | Responsible actor |
|---|---|---|
| One scripted `process_approved` worker selects `STAGES` or `FOLDER_STAGES` for each item. | Keep that mixed identity, order and accounting; the Lead owns completion against the inherited contract. | Lead directs; Core dispatches and persists. |
| Folder descriptions use legacy model transports and retain provenance/refusal results. | A Clerk directs bounded Scribe inventory work, proofreads it and authors the proposal. Core checks literal provenance, schema and current fingerprints. | Clerk and Scribe own content; Core owns checks and storage. |
| Folder coverage is metadata only. | Keep `folder_validate → folder_describe → folder_data`, actual task states and source content not examined. A finished folder card does not credit its documents as read. | Core records the facts; Clerk explains the proposal's limitations. |
| Source completion is reduced from stage statuses and remaining-part counters. | Preserve actual statuses and separately account for required derivations, conversion, source review and publication in the source package. The mixed Oracle verifies that required child outputs remain accounted for. | Source Clerk/Oracle supply evidence; mixed Oracle judges this child's complete contract. |
| Failure and later decisions commonly return to the orchestrator. | Existing flags become accountable tickets. Accepted mapped remedies run only within actual scope and grants; unmapped diagnosis belongs to the Lead. Independent recheck precedes closure. | Doctor repairs mapped cases; Lead owns unmapped diagnosis; Oracle rechecks. |
| The worker stops on cancellation, interruption or its before-item ceiling. | Preserve those controls and add recorded grant/critical-flag checks at each proposed dispatch or commit boundary. Route outages retain bounded attempts and known or unknown cost rather than silently changing models. | Core enforces recorded rules; Lead decides permitted continuation. |

The current folder audit observed twelve failed folder-item attempts in two batches, all at description, with no successful `folder_data` in that sample. The proposal retains and strengthens the implemented chain; it does not claim its target hierarchy or recovery has already succeeded on those records.

## Authority, recovery and handback

Core stores the parent-authored specification and existing run records. This view introduces no additional runner, specification store, tool schema or runtime API. Semantic folder description, sensitivity findings, organization and explanations belong to the agent authoring the proposal. Core's materialized inventory Data does not transfer that authorship.

Every item dispatch or commit retains actual grant, writer and critical-state checks. A critical integrity finding exits immediately through the Lead's parent route; it does not wait for the final Oracle. Noncritical item failure preserves sibling progress and the original ticket for package reconciliation. A normal pending decision or valid not-applicable output is not automatically a Doctor fault.

The repair branch uses the existing symptom/extension identity, accepted catalogue status, affected records, actual blast radius and attempt allowance. The Doctor does not accept new remedies or decide that a repair is complete. Core repeats affected deterministic checks and the Oracle independently judges the original shortfall and its consequences. Unmapped remedies remain Lead proposals for the parent. A remedy requiring reserved authority or renewed approval of finished partial processing returns paused rather than silently starting a new batch. Returning from repair reconciles the package before a success handback; it does not replace the parent ledger.

Model choice remains adapter- and role-based. Oracle and Doctor currently have the revisable GLM-5.3 assignment, with separate contexts. This proposal does not pin the implementation to that provider/model or introduce silent reassignment. It retains true decision authors, qualified assignments and escalation when independent evidence cannot support closure.

Source, folder and lens accept/reject/defer choices remain with their authorized parent decision owners. The mixed package carries separate worklists, including valid zero-candidate or inapplicable results. This child's Oracle checks mixed accounting and its required outputs; it does not repeat the parent's full final review or take over Source promotion. The parent remains responsible for guarded writes and findability after its actual decisions.

This is a use-case decomposition. Any later executable composition must preserve upward abstraction through action → workflow → pipeline → sprint; a child diagram is not permission to insert a pipeline inside a workflow or create a second execution system.

## Evidence and proposed checks

The preserved current boundary is evidenced by [mixed admission](../../src/resource_librarian/batch.py#L672), [stage selection and item execution](../../src/resource_librarian/batch.py#L784), [item reduction and metadata-only folder coverage](../../src/resource_librarian/batch.py#L883), and [folder stage definitions](../../src/resource_librarian/batch.py#L916). Proposed role ownership follows the [role policy](../../docs/policy/agent-roles-and-authority.md) and existing [requirements baseline](../2026-11-21-enrichment-baseline/requirements-evidence.md). The [source proposal](proposed-source-enrichment.md) owns source-specific conversion, reading, derivation and publication behavior.

Review cases include a mixed source/folder selection, metadata-only success, disabled or failed description, source partial return, source-wide derivation left pending despite full part counts, ordinary item failure with completed siblings, zero fresh work with pending parent decisions, cancellation, unknown cost, missing reserved authority, critical writer failure, accepted in-scope remedy, out-of-scope remedy and unsuccessful independent recheck. These are proposed artifact/behavior checks, not newly executed library runs.
