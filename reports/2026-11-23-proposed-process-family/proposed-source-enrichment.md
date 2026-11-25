# Proposed to-be source enrichment

**Status:** proposal, 23 November 2026. [Specification](proposed-source-enrichment.spec.yaml). This is the proposed counterpart of the corrected [current Source child](../2026-11-21-enrichment-baseline/source-enrichment-current.md), using the earlier [focused proposal](../2026-11-22-proposed-tobe-enrichment/PROPOSAL.md) as supporting design work.

The child processes the one Source selected by the proposed mixed-batch dispatcher. It inherits the existing commission, accountable Lead, Core-stored specification, qualified assignments, grants and original mixed ledger. The reference describes a component of that admitted process, rather than starting another worker or spending allowance. The mixed dispatcher owns item order and sibling accounting; ingestion owns final Source, folder and independent lens decisions.

## Use-case description

| Field | Content |
|---|---|
| Name | Proposed to-be source enrichment. |
| Goal | Return an independently judged Source package with actual reading, required derivations, draft, publication and remaining decision obligations. |
| Primary actor | The inherited Lead, acting for the invoking mixed dispatcher. |
| Supporting actors | Clerk tier 2 directs Scribe tier 3 tasks; Core performs scripts and mechanical checks; model host serves qualified assignments; Geo-Grapher publishes eligible artifacts; isolated Oracle judges; Doctor uses accepted bounded remedies. |
| Preconditions | One captured Source selected under explicit processing-start authority; admitted specification and grants; current source evidence; writer availability; required outputs and qualified role assignments recorded. |
| Trigger | The mixed dispatcher selects its next Source item. |
| Guarantee | Completed receipts survive failures; missing material receives no reading credit; every required derivation has an explicit state; Source and lens acceptance remain separate parent decisions. |
| Main scenario | Bind inherited authority, validate and parse, assign bounded reading, proofread and reconcile, persist lens proposals, author Data/relations/metadata/draft, conditionally publish, judge the package and hand back the result. |
| Extensions | No admitted item; explicit pause; partial conversion/reading/publication; stage failure; bounded route outage; independent review shortfall; accepted scoped repair and recheck; immediate critical escalation. Exact call outcomes are `success`, `partial`, `reused`, `paused`, `escalated`. |

## Current contract retained and proposed changes

| Corrected current behavior | Proposed addition or responsibility |
|---|---|
| The nine stages are validate → parse → read → lenses → Data → relate → metadata → review → publish. | Keep that order. Clerk owns meaning and synthesis, directs bounded Scribe tasks and submits proposals; Core retains declared scripts, schemas, locators, counters, storage and dispatch. |
| Current Data and limited metadata prefills are scripts. | Clerk authors meaningful organization and inferred field values from evidence. Core validates and stores those proposals; `Unknown` remains valid and acceptance confirms them later. |
| The bounded task pool already exists. | Make Clerk/Scribe responsibility explicit within stages. Dispatch only pending bounded tasks with available permitted input; compatible completed tasks and absent-input gaps pass to evidence accounting without a new model call. Do not create a document-level parallel fork across the sequential stages. |
| Part counts may be complete while a whole-source derivation remains queued. | Record every required part/task and source-wide derivation separately. Oracle assesses the inherited output requirements rather than treating the part counter or enriched status as proof. |
| Returned cleanup error can continue with raw text and remain partial; lost generated anchors can fall back to usable original text and permit complete parsing. | Preserve those cases and add Clerk fidelity review. Deferred routes retain exact returned-error or missing-material gaps; no silent model substitution or fictitious reading credit. |
| Early fetch/OCR partial returns precede provisional projection; a continuing PDF/paper parse writes `.nodes.json` before reading. | Keep that branch location. Provisional catalogue-only or zero-claim artifacts are neither publication nor reading receipts. Oracle receives the actual branch and retained limitations. |
| Publication is conditional and occurs after reading inside this item. | Freshly check current trusted accepted folder assignment, conversion, artifact binding and the declared projection tasks. A Source-note acceptance decision is not a prerequisite. Oracle still judges the resulting package independently. |
| Each paper import creates a candidate database generation and switches the catalog pointer. | Expose copy/import/registration results, candidate checkpoint, catalog WAL and retained old or failed candidates. Cleanup or retention changes require their own accepted maintenance scope. |
| Ordinary failure returns to the caller; general Oracle/Doctor orchestration is not deployed. | Record a ticket using existing origin/flag evidence. Doctor uses only accepted matching remedies within the actual grant and blast radius; Lead owns unmapped diagnosis. Repair re-enters scoped checks and reaches independent Oracle review before completion. |

The Oracle's scope here is the selected Source's content and declared outputs. The mixed dispatcher separately reconciles the original source/folder ledger. Ingestion separately judges its final goal, acceptance decisions and findability obligations. These nested reviews assess different obligations; they do not create repeated commissioning or allow a child to replace its parent's accounting.

Semantic document-relation work uses eligible fully read components. Static repository relations retain their scripted, structurally observed origin. A source-wide or publication gap is retained through later applicable stages and reaches the Oracle; an empty dispatch does not mark a missing task complete.

## Partial work, authority and recovery

The child can return an ordinary noncritical partial item under the inherited handback and item-isolation policy even when final required outputs remain unmet. Those requirements stay explicit in the original parent ledger; the mixed parent can continue unaffected siblings while the commissioning goal remains unsatisfied. An unmet required output cannot become success because other stages completed. Optional rejected lenses, legitimate zero candidates and declared inapplicability remain valid outcomes. Failed items retain completed evidence and their originating flag. An unmapped item shortfall, exhausted bounded repair or deferred new remedy does not by itself become a run-wide escalation.

The proposed dispatch checks enforce the existing grant, route qualification, retry counter and backoff. Lead chooses bounded continuation; Core does not choose a semantic workaround. Unknown model costs remain unknown. Before-item spending checks and these proposed attempt controls are not a hard per-call reservation. A changed model assignment requires actual authorized qualification through the existing adapter mechanism.

Doctor and Oracle currently use GLM-5.3 as configurable role assignments, with separate contexts and independently scoped responsibilities. They are not hard locked to that model. If evidence does not support independent judgment under the selected assignments, the Lead must resolve the assignment or return a truthful pause/escalation.

`UC-D` supplies the existing three-result remedy call contract (`resolved`, `declined`, `escalated`); its prototype body is not asserted to implement this proposed parent-aware routing. General ticket dispatch, independent package judgment and integrated re-entry remain target work. New remedies require acceptance; a diagnosis is not permission to execute one. Reserved authority returns a pause through the parent, which can obtain the Owner's decision without requiring a tier-0 application to be present. Ordinary deferred item corrections return partial work; critical or run-wide trust failures and unsafe out-of-scope intervention escalate.

An unfinished admitted batch may resume compatible pinned work. A finished partial item needs actual re-approval and new batch admission where the existing contract requires it. Re-entry begins with current source/receipt checks, reuses unaffected compatible tasks and performs fresh publication admission; it does not automatically reread, rebuild every graph, prune generations or send an accepted Source through new-source duplicate admission. Critical integrity, data-loss, false-attestation or authority-boundary evidence reaches the Owner immediately through the parent notification path, with tier 0 when present.

## Evidence

The baseline is the corrected [current specification](../2026-11-21-enrichment-baseline/source-enrichment-current.spec.yaml) and [current mixed dispatcher](../2026-11-21-enrichment-baseline/batch-enrichment-current.md). Implementation anchors are [parse, fallback and provisional projection](../../src/resource_librarian/batch.py#L235), [part-count reading completion](../../src/resource_librarian/batch.py#L365), [stages](../../src/resource_librarian/batch.py#L600), [admission and frozen selection](../../src/resource_librarian/batch.py#L672), [mixed execution and receipt reuse](../../src/resource_librarian/batch.py#L784), [publication admission](../../src/resource_librarian/paper_graph.py#L163), [bounded reading pool](../../src/resource_librarian/deep_read.py#L406) and [whole-source derivation records](../../src/resource_librarian/deep_read.py#L533). The [requirements baseline](../2026-11-21-enrichment-baseline/requirements-evidence.md) retains acceptance, revision and authority requirements. This proposal changes no runtime schema or executable process.
