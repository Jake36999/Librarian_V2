# Proposed ingestion with Lead ownership, independent Oracle review and bounded Doctor recovery

Revised 22 November 2026. The [spec](ingestion-tobe.spec.yaml), [accepted canvas](accepted-ingestion-tobe.canvas) and [generated views](ingestion-tobe.views.md) describe a **proposed parent integration**. The [historical example](INGESTION-EXAMPLE.md) records the separate DataManagement run. The corrected responsibilities follow the [approved graph review](../../../2026-11-22-ingestion-enrichment-graph-review.md); they do not claim that the complete autonomous process is already implemented.

The Owner can commission the Lead directly, or an external tier-0 Overseer can do so on the Owner's behalf. Tier 0 remains able to use Librarian and delegate work to its DeepInfra agents for other projects within actual authority. Its absence does not block a direct user run. Lead owns execution and correction; Oracle independently judges and rechecks. Oracle does not coordinate jobs or issue worker orders.

## Roles, specification and composition

The [23 November routing correction](../../../2026-11-23-routing-and-tobe-proposals.md) preserves this model's 24 numbered steps and 69 scenarios. Six equivalent local reporting/end cards and deliberate placement changes keep the native curves clear; [the presentation proof](ingestion-tobe.presentation-proof.json) preserves the original actors, labels, outcomes and guarded transitions. The new [three-part target family](../../../2026-11-23-proposed-process-family/README.md) is a separate proposal derived from the corrected current decomposition.

| Actor | Responsibility |
|---|---|
| Owner / tier 0 | Define or approve the goal, required outputs, scope, grants and budgets; make reserved decisions. Tier 0 commissions, reviews and returns the result when present. |
| Lead, tier 1 | Own completion, direction, dispatch requests, bounded correction and the final truthful handoff to the recorded specification owner. |
| Clerk, tier 2 | Interpret evidence, propose descriptions and semantic decisions, check claims/synthesis, investigate unexplained mismatches and direct Scribes. |
| Scribe, tier 3 | Perform bounded reads/writes under the Clerk; detailed tasks live in the enrichment child rather than duplicated parent cards. |
| Core | Store the agent/Owner-authored specification inside Librarian, inventory/count, apply explicit rules and decisions, validate authority/structure/grounding, persist evidence and dispatch registered work. |
| Oracle | Judge specified obligations independently, including repaired obligations; return a verdict to the specification owner. |
| Doctor | Match an existing failure shape and execute only an accepted, authorized bounded remedy; return all declared outcomes. |
| Model host / Geo-Grapher | Return transport results / graph or publication results; their response alone does not establish semantic success. |

The agreed hierarchy is **action → workflow → pipeline → sprint**. Compose existing registered components upward at their actual layer. This parent use case connects several processes; it is not evidence of a second runtime engine, a separate spec store or a pipeline embedded inside an action/workflow. Doctor and Oracle currently use GLM 5.3 through revisable role adapters; the graph does not hard-lock their model selection.

The fault register is a routed ticket service using existing flags, refusal codes, extension evidence and responsible actors. Waiting decisions and legitimate rejected optional outputs are not automatically repair faults. Existing legacy transport labels do not define current role tiers.

## Main scenario

1. **Owner** states the ingestion goal, roots, pre-read exclusions, required outputs, permitted partials and budget; grants only the intended authority.
2. **Tier 0 agent** commissions the Lead on the Owner's behalf and supplies the agent-authored obligations for independent Oracle review.
3. **Lead (tier 1)** owns execution against the commissioned specification; asks Core to store its version, grants and actual specification owner.
4. **Core** inventories roots, fingerprints and literal facts; excludes hidden/scratch content before reading and resolves deepest-root ownership.
5. **Lead (tier 1)** binds the Owner's exclusions, purpose constraints and decision grants to the eligible worklist.
6. **Clerk (tier 2)** interprets folder purpose, proposes descriptions and judges sensitivity; may direct bounded Scribe tasks.
7. **Lead (tier 1)** makes normal folder decisions within grant and preserves the Owner's explicit reserved decisions; supplies actual actors/reasons for Core to apply.
8. **Core** submits affirmative folder decisions and read barriers for group application; acceptance is recorded only after the CLI succeeds.
9. **Core** queues Source-eligible third-party, research-docs and own-docs inputs per deepest accepted root; retains enqueue history.
10. **Core** reconciles literal eligible counts with current staging/processing state and the parent mixed-item ledger.
11. **Core** captures immutable evidence and per-reference outcomes; isolates parser/quarantine failures and preserves successful siblings.
12. **Clerk (tier 2)** writes neutral evidence-based Source descriptions, directing Scribes only for bounded drafting.
13. **Core** stages Source records and records their parent ledger keys; folder metadata retains folder_validate, folder_describe and folder_data with separate review.
14. **Lead (tier 1)** approves the staged selection within the ingestion grant; supplies the actual authority, executor and reason to the approval action.
15. **Lead (tier 1)** requests explicit processing start for the approved set within its recorded grant.
16. **Core** validates start authority and freezes selection/settings; returns the existing active run instead of dispatching another.
17. **Core** runs the source-enrichment child; each item owns all nine ordered stages including publication before the next item.
18. **Core** reconciles returned Source states with the original mixed-item ledger; issues separate Source and lens worklists with owner, current state and remaining decision.
19. **Lead (tier 1)** makes affirmative Source acceptance decisions only within grant, for full or explicitly permitted partial outputs; no lens is accepted implicitly.
20. **Core** applies the guarded Source writer and retains the actual commit/refusal/attempt state; Source acceptance does not accept lenses.
21. **Oracle** judges the parent specification using deterministic evidence and independent semantic review, including separate decision obligations and actual partial results.
22. **Lead (tier 1)** hands one truthful result package and Oracle verdict to the recorded specification owner.
23. **Tier 0 agent** reviews the Lead's result and independent verdict against the commissioned specification.
24. **Lead (tier 1)** returns the result to the Owner directly or with the tier-0 reviewed report, retaining all remaining decision owners and limitations.

The direct-Owner route joins Lead execution at `a3` and returns through `ownerreport` and the shared Core delivery receipt, bypassing tier-0 commissioning/review/reporting. A held folder decision reaches the Owner directly when no overseer exists. All pause/escalation packages go to the actual specification owner, with critical findings immediately notified to the Owner/overseer.

## Approval, execution and output boundaries

Ingestion approval queues work. A separate explicit processing-start request must be authorized; Core freezes the approved set and returns an existing active run instead of creating a second one. Today's curate/person start is existing behavior. Delegated Lead start is proposed integration and must have an explicit grant; agent promotion mode alone does not provide it.

The parent keeps its original mixed-item ledger, current staging/processing states and separate Source/lens worklists. Historical queue keys are enqueue history. The actual folder-application boundary applies every accepted non-excluded group, including document and paper groups, before purpose-specific Source intake. Own-code/data/log purposes therefore account for the **same common application receipt** without making another Geo indexing call or entering Source capture/acceptance. Folder metadata retains its separate three-stage processing/review contract; a source-only enrichment child gives those cards no source-reading credit. A child no-work result reconciles current decisions before a reused end.

The `enrich` reference calls [proposed source enrichment](../../../2026-11-22-proposed-tobe-enrichment/PROPOSAL.md), with these complete outcomes:

| Child outcome | Parent continuation |
|---|---|
| `success` | Check the actual coverage/publication contract, then reconcile decision worklists. |
| `partial` | Preserve per-item gaps; permit acceptance only for explicitly allowed partials. Required partial reading may request accepted R4; required publication-only gaps need their own diagnosis/authority, not an automatic reread. |
| `reused` | Reconcile existing/no-new-work states and separate decisions without duplicate processing. |
| `paused` | Return actual cancellation, interruption, before-item ceiling stop or pending decision with completed siblings and the continuation point. |
| `escalated` | Return unresolved fault with originating stage, existing flags and evidence to the actual specification owner. |

The child owns each frozen item's **validate → parse → read → lenses → Data → relate → metadata → review → publish** sequence before the next item. Its task pool supplies bounded internal concurrency. Publication is not a post-batch join. Spend checks occur before items, cancellation between stages; unknown cost remains unknown. Transport completion, valid structured task output and semantic adequacy are separate facts.

Publication requires the accepted/current/trusted **folder assignment**, actual required reading/conversion, matching artifact and enabled Geo. Source acceptance comes later and is not a publication prerequisite. A Source may be accepted with explicitly permitted partial coverage without a false complete-graph claim. Separate lens accept/reject/defer obligations remain explicit; zero candidates, optional rejection and not-applicable outputs can be valid.

The actual accepting actor appears before Core records/applies an affirmative decision. Person mode, sensitivity, interrupted promotion or absent authority requires an Owner decision. `x3` has approve/apply, exclude, decline and hold guards; `x7` has accept, decline and hold guards. Decline/hold never reaches the guarded writer. A written note failing a required query stays written; its actual failed retrieval remains visible.

## Current folder application and proposed quality evidence

`a7 → applygroups → applicationreceipt → dfolder` preserves the existing common application boundary. Geo-Grapher ingests supported code/text for all accepted non-excluded groups and can reuse matching complete snapshots. Core currently checks CLI exit, JSON and version; the returned folder JSON omits parser failures. This is why a successful current receipt cannot establish parser-capability or language-coverage completeness.

The target's `indexcheck → dindex` is a **proposed common evidence gate after application**, not a second indexing call and not an existing Core check. It requires additional registered diagnostic evidence absent from today's CLI response. Missing or unacceptable required evidence goes to the Lead's held outcome. Successful quality evidence allows `dinput` to choose the requested Source subset; non-Source purposes keep their common receipt and proceed to parent Oracle review.

Application-stage stale recovery uses the separate `r1application` call site for the same scoped R1 remedy; its real library-wide radius and three UC-D outcomes remain explicit.

## Recovery and independent checking

Every Doctor reference calls [UC-D](doctor.spec.yaml) and handles **resolved**, **declined** and **escalated**. `resolved` means the accepted bounded remedy and independent verification succeeded, then the caller checks fresh evidence. It is not authority to bypass a gate.

| Call | Matching problem and fresh rejoin |
|---|---|
| `r1` / `r1application`, R1 | Survey-stage recovery re-enters inventory `a4`; application-stage recovery re-enters the authorized application `a7` after its scoped resurvey/reapply remedy. The actual radius can cover the whole library; a local grant cannot silently permit that work. |
| `r2`, R2 | Confirmed lost qualification: re-enter `d2`. Provider timeout, invalid task output and missing parser capability retain their own diagnoses. |
| `r3`, R3 | Matching per-root queue defect: re-enter `a8` and scripted count reconciliation. Clerk investigates unexplained mismatch first. |
| `r4`, R4 | Required partial reading: re-enter `enrich`, then fresh `d5` coverage/publication checks. Finished partial work requires authorized reapproval/new admission; unfinished-run resume is distinct. |
| `r5`, R5 | Candidate index obligation: re-enter `d7`. R5 is not proof reindexing fixes every Bottom-Line/content miss. Clerk diagnoses unmapped content gaps; concepts/vectors are not fabricated or switched on to force success. |
| `r6`, R6 | Mapped final shortfall: Oracle rejudges at `a18`. Unmapped evidence goes through Clerk scouting and Lead correction, then Oracle review. |

The Lead coordinates tier-0-requested correction (`x11`, `x12`); Oracle judges the changed evidence (`x13`). If required obligations remain unmet, the run pauses rather than claiming success. Compensation is an explicit authorized decision when applicable; this diagram adds no automatic rollback. New remedies remain proposed until accepted through the established learning/catalogue process. The [remedy catalogue](remedy-catalogue.yaml) requires matching extension keys/rejoin references or documented legacy aliases after this numbering change.

## Correspondence with the accepted earlier map

Retained behavior keeps its node IDs. The following table preserves extension lineage while the main scenario is numbered consecutively.

| Previous target extension / node | Corrected location |
|---|---|
| `4a` stale root | `4a`: `r1 → a4`; `8a`: `r1application → a7` after its scoped remedy. Shared remedy, separate call sites and actual scope remain explicit. |
| `6a` qualification | `5a`, `r2 → d2`. |
| `6b` held folder | `6a`, with explicit Owner approve/exclude/decline/hold and a direct-Owner path. |
| `9a` queue mismatch | `10a`, Clerk diagnosis then matching R3 and count recheck. |
| `13a`, `a12`, `a13`, `m1`, `dm` | Source child transport, task-validation and semantic worker boundaries. |
| `f1`, `j1`, `a15` | Removed misleading document fork/join and post-join publication; `enrich` owns the sequential per-item stages. |
| `14a`, `a14` | Child before-item spend control and `17c` paused result; cancellation/interruption remain distinct reasons. |
| `13b` partials | `17e`, R4 reading-only; `17a` returns partial and `17g` isolates publication-only shortfall. |
| `16a` person acceptance | `19a`, now includes sensitivity, interruption and absent grant; Source/lens worklists remain separate. |
| `17a` not findable | `20a` candidate R5; `20b` unmapped content/retrieval diagnosis. |
| `18a` / `18b` final shortfall | `21a` mapped / `21b` unmapped. |
| `20a` tier-0 correction | `23a`, Lead coordinates and Oracle only judges. |
| New route/admission branches | `1a`, `22a` direct Owner; ingestion approval `14a`; start authority `15a`; capture/folder outcomes and all five child returns explicit. |

The old six-turn historical / two-turn target figures depended on the earlier graph. Updated generated lane-load and scenario counts describe these corrected representations; they measure diagram control returns, not observed token cost or proven runtime orchestration.

## Dated evidence and remaining integration

The historical cohort ends with 96 accepted Sources, 93 fully read/published and three accepted partials. Four not-findable notes, 750 processed Sources and 689 lens decisions, eight cancellations and zero ceiling stops are later cross-library audit reports with different populations. They do not rewrite F6's historical sample. W7 added `awaiting_acceptance()` visibility to agenda/status/context; backlog size alone does not demonstrate that current handoff alert is defective. Written-but-not-findable, unread legacy publication reconciliation and old projection repair retain their own bounded scope; ordinary ingestion does not automatically rebuild or reread every graph.

Existing scripts, stage ordering, start/permission gates, writer and current visibility are distinct from the proposed integrated Lead/Clerk/Scribe assignment, independent Oracle loop, Doctor remedy wiring and delegated grants. Dependency installation, global retention cleanup, production backlog decisions and live graph repair remain separate work.

## Regeneration and verification

From this directory use:

```powershell
..\..\..\..\.venv\Scripts\python.exe -B render_corrected.py --commit --png
```

The report-local renderer updates **accepted-ingestion-tobe.canvas**, preserving accepted actor-column dimensions, retained card geometry and manual edge attachment sides. The prototype's ordinary entry point would write the superseded `ingestion-tobe.canvas` name and reset saved layout; use its validation/path/reference functions in memory only when checking these corrected parents.

The historical parent calls the [current mixed-batch child](../../../2026-11-21-enrichment-baseline/batch-enrichment-current.md), which references the source child rendered by `reports/2026-11-21-enrichment-baseline/render_current.py`; the focused target uses `reports/2026-11-22-proposed-tobe-enrichment/render_proposal.py`. Their exact five-outcome contracts and UC-D's three outcomes must all be loaded for parent reference checks. Generated scenarios/tests establish graph consistency; they are not newly executed runtime tests. No library processing, paid calls, acceptance or live service changes accompany these graph corrections.

The corrected [remedy catalogue](remedy-catalogue.yaml) tracks current extension IDs and explicit rejoin gates. Its entries remain proposed, including the application-stage R1 correspondence; no remedy was promoted or executed by this diagram revision.
