# Proposed to-be enrichment

**Status:** behavioral proposal amended under the Owner-approved [graph review](../2026-11-22-ingestion-enrichment-graph-review.md), 22 November 2026. Diagram amendments do not constitute executable-workflow acceptance or a runtime change.

The Lead owns an enrichment run from its authorized source handoff to one evidence-bearing result. Clerks direct bounded Scribe work, proofread the returned evidence and author the source proposals. The Core executes declared scripts, validates mechanical constraints and persists results. It does not interpret source content or own the proposals. The Oracle judges the result against the specification, and the Doctor repairs mapped failures through accepted remedies. Tier 0 delegates and reviews the handback instead of repeatedly coordinating the reading.

The existing nine-stage source chain remains intact: **validate → parse → read → lenses → data → relate → metadata → review → publish**. The proposal changes its ownership, completion accounting and recovery. It retains the grounding, lens derivation, kind-specific records and resumability already built.

Open the [proposed to-be enrichment canvas](proposed-tobe-enrichment.canvas), its [generated written and diagram views](proposed-tobe-enrichment.views.md), or the [editable behavior specification](proposed-tobe-enrichment.spec.yaml). [Validation](validation.json) records the artifact checks. The visual method follows the supplied [ingestion map](../2026-11-20-workflow-map/examples/ingestion/ingestion.canvas) and [accepted to-be ingestion map](../2026-11-20-workflow-map/examples/ingestion/accepted-ingestion-tobe.canvas).

## Process boundary

The [23 November routing correction](../2026-11-23-routing-and-tobe-proposals.md) keeps this proposal's 23 numbered steps and 73 scenarios. One equivalent critical-report/end pair and deliberate placement changes make its native attachment curves clear; [the presentation proof](proposed-tobe-enrichment.presentation-proof.json) preserves actors, labels, outcomes and guarded transitions. A separate [new target family](../2026-11-23-proposed-process-family/README.md) follows the corrected ingestion → mixed-batch → source decomposition.

When called by ingestion, the child inherits the parent's existing commission, bounded specification, Lead and admitted source selection through `parentbind`. It returns the package through `parentreturn` to that invoking parent, which owns Source/lens decisions and the final Owner/tier-0 handoff. The standalone commissioning and review branches are not extra parent-call turns. Partial and no-work results likewise return to the caller without settling the parent's outstanding obligations.

**Input:** captured source work handed over by ingestion under explicit approval, source access, spending and processing-start authority. A directly requested user run and a tier-0-delegated run use the same capability.

**Output:** an enrichment package containing located readings, actual coverage, qualified lens proposals, kind-specific Data and Information, metadata proposals, a grounded source draft, conditional paper publication, and the Oracle's verdict. Each failed, partial or deferred item remains accounted for. Separate Source-acceptance and lens-review worklists name their decision owners and current states.

Folder survey, purpose decisions, enumeration, capture and deduplication remain upstream in ingestion. Source acceptance, guarded note promotion and findability remain the parent's separately authorized next steps. Enrichment does not quietly perform those decisions or report that staged material is already in the library. Existing backlog visibility remains part of the handoff ([staging.py:213](../../src/resource_librarian/staging.py#L213)).

This is the **source-enrichment branch** of the approved work. The current batch can contain both sources and folder metadata cards; its frozen set must still account for both. Folder cards continue through their separate metadata-only branch, without being credited as source reading. Accepted-note rereading retains its staged-revision path; it must not be sent through new-source duplicate validation. These boundaries remain as established in the [requirements baseline](../2026-11-21-enrichment-baseline/requirements-evidence.md).

The parent retains the original mixed-batch ledger while this child receives its source subset. Re-admitting a repaired subset never replaces that parent accounting. An empty or already settled selection returns an explicit no-source-work result without dispatching a nonexistent item or claiming fresh enrichment.

Existing-publication reconciliation also belongs to the parent. It inventories historical evidence, obtains a scoped Lead plan and actual authority, then chooses accepted-note revision, re-approved partial work or compatible-reading reprojection. It does not send accepted Sources through new-source duplicate checks. See the [comprehensive maintenance path](../2026-11-21-enrichment-baseline/model-notes.md#existing-publication-reconciliation). This child returns `success`, `partial`, `reused`, `paused` or `escalated`; none implies Source/lens acceptance.

## What changes from the current process

| Current mechanism | Proposed to-be behavior | Reason |
|---|---|---|
| Enrichment stages exist as coded batch operations. | The Lead owns a process composed from accepted actions and workflows; Core services execute its declared scripts and enforce recorded grants. | Gives the work an accountable agent while preserving the existing execution services. |
| Approval queues work; starting the batch is currently a person/curate action. | The Core validates explicit run-start authority once. A permitted delegated run uses that authority; missing or reserved authority goes to the Owner. | Delegation must be possible without impersonating a person or asking again inside an approved envelope. |
| Model tasks already use a bounded pool, chiefly through the legacy Clerk transport. | Clerks explicitly assign bounded reading and writing to Scribes, proofread returned evidence and own synthesis. | Makes the intended role hierarchy responsible for the existing work. Parallelism itself is not presented as new. |
| A part counts as read after its required tasks complete. A whole-source pass can still be queued after all parts are counted read. | Track part coverage and each required derivation separately. The run cannot pass solely because the part counter is full. | Prevents a completed reading counter from concealing unfinished reasoning or source-wide work. |
| The lens chain already grounds, challenges, screens and reconciles candidates. | Preserve that chain and make the Clerk responsible for its disposition and source-wide reconciliation. | Protects transferable reasoning quality; a rejected optional lens remains a normal outcome. |
| Data records are assembled from structure/readings; current metadata copies limited Data facts and lists missing fields. Chapter relations and source review can invoke models. | The assigned agent authors semantic organization, values and prose. Core retains scripted record construction, literal prefills, validation and storage. | Keeps interpretation with the agent while preserving existing scripted derivations. A stage named metadata is not automatically a model call. |
| Familiar failures commonly return to the orchestrating agent. | The Core records a ticket; mapped, accepted remedies go to the Doctor and independent Oracle recheck. Unmapped problems belong to the Lead. | Routine recovery stays below tier 0 within bounded authority. |
| Existing source review is a Bottom Line/coverage operation. | An isolated Oracle additionally judges the whole enrichment package and returns one verdict to its specification owner. | Source drafting and judging run completion are different acts. |

The existing mechanisms are evidenced in [batch.py:4](../../src/resource_librarian/batch.py#L4), [stage declarations](../../src/resource_librarian/batch.py#L600), [the bounded reading pool](../../src/resource_librarian/deep_read.py#L406), and [whole-source completion recording](../../src/resource_librarian/deep_read.py#L533). The specific completion gap is visible where [batch reading reports complete from remaining parts](../../src/resource_librarian/batch.py#L365).

The [observed-run assessment](../2026-11-21-enrichment-baseline/observed-enrichment.md) checks completed 20 November batches and their retained outputs. It distinguishes actual scripted/model work, full and partial outcomes, later acceptance and time-correlated model usage. This proposal's autonomous Lead/Clerk/Scribe coordination and general Oracle/Doctor recovery remain target behavior.

## Agent ownership and scripted services

The agent completing a proposal owns its interpretation, field choices and explanations. In this scenario the Clerk owns the source, Data and metadata proposals, with bounded drafting delegated to Scribes. Another process may assign that authorship to a different agent. Passing a proposal through a Core tool does not transfer authorship to the Core, and Core-owned specification storage does not make the Core the specification's author.

| Work | Agent responsibility | Scripted Core responsibility |
|---|---|---|
| Parsing and conversion | Clerk directs conversion and reviews fidelity against originals; Scribe transcribes or cleans content and states limitations. | Extract/map original text, check fields/hashes/literal anchors, retain actual statuses and persist the reported review verdict. |
| Data and lenses | Agent chooses meaningful organization, claim placement, reasoning stances and proposal/discard explanations. | Extract literal AST/outline structure, construct records from submitted values, check schemas/references, persist the proposals and provenance. |
| Metadata | The proposing agent interprets evidence, selects field values and explains Unknowns. | Prefill mechanically extractable facts, validate declared field names/types and persist the agent's proposal. |
| Package and correction | Clerk assembles and reconciles the content; Lead chooses and explains corrections, pauses and escalations; Oracle judges conformance. | Supply counters/receipts, reduce statuses under declared rules, check grants and remaining allowances, store checkpoints/tickets and dispatch notices. |

The canvas assigns those responsibilities to their actual actors. Core-lane decisions represent scripted status switches or stored policy checks; they do not make semantic judgements for the agents.

## Use case description

| Field | Content |
|---|---|
| Use case name | Proposed to-be enrichment |
| Brief description | Authorized captured source work becomes grounded, fully accounted enrichment outputs, independently judged and handed back for the next acceptance decision. |
| Primary actor | Owner, directly or through a tier-0 Overseer acting under current or standing authority. |
| Supporting actors | Lead, Clerk, Scribe, Oracle, Doctor, model host and Geo-Grapher. Librarian is the system boundary; Core services are its scripted execution and storage component. |
| Preconditions | Source work is captured and ingestion approval is explicit; required access and spending are authorized; a Core is active; suitable qualified assignments are available or the run pauses visibly. |
| Trigger | The Owner or tier 0 hands the enrichment capability a bounded goal and authorized source work. |
| Success guarantee | Required reading and derivations are accounted for against the same input/recipe/route identities; claims and relations retain their origin and evidence; required outputs are present, or legitimate inapplicability is recorded; the Oracle's result and the separate acceptance obligation return to the specification owner. Permitted gaps return a partial outcome. |
| Main success scenario | The 23 numbered actions in the [generated views](proposed-tobe-enrichment.views.md#written-use-case). |
| Extensions | The generated guarded branches cover missing authority, stage failures, incomplete reading or derivation, conditional publication, bounded repair, unmapped failure, critical escalation and the Overseer's final recheck. Each terminates or rejoins explicitly. |
| Open questions and assumptions | Core-owned specifications, manifest/envelope, tickets and independent-review direction remain W1b/W9 integration. Approval to amend these graphs does not register executable components or expand runtime grants. |

## How the work is divided

The **Lead** narrows the parent specification into an enrichment run, chooses accepted components and owns completion. It does not leave routine coordination for the Overseer. It returns the actual result, including uncertainty and work that remains.

The **Clerk at tier 2** organizes bounded tasks, proofreads source fidelity, reconciles readings across parts, directs lens derivation, proposes Data organization and metadata values, synthesizes supported relations and produces the source draft and package. The **Scribes at tier 3** perform assigned reading, drafting, transcription and cleanup. They receive approved source material rather than the finding project's assumptions or unrestricted access to unrelated graphs.

The **Core** performs scripted work: AST/text extraction, schema and literal quote-location checks, hashes, reference integrity, receipt/counter updates, declared status reduction, budget/stop checks, dependency and permission checks, persistence and dispatch. Agents own the meaning of their findings and the content they propose. Model/network work does not hold the writer. The existing pool bounds independent model tasks; the nine source stages retain their dependency order. This proposal does not draw all stages or all sources running concurrently ([stage execution](../../src/resource_librarian/batch.py#L803), [task runner](../../src/resource_librarian/clerk.py#L1654)).

The **Oracle** judges conformance to the specification from isolated evidence. Its semantic verdict is a claim, not a command or a universal factual verification. A model judgement does not independently upgrade advisory or human-judgment material into deterministic truth. The **Doctor** executes only accepted catalogued remedies within actual scope, then returns evidence to Oracle rechecking. Both currently use GLM-5.3 in separate contexts; either can be reassigned through the existing adapters and role-selection mechanism. A worker/reviewer assignment collision must be reconciled before claiming independent review.

## Reading and derived knowledge

Part reading retains located source-stated points, stated limits, quoted term usages and candidate reasoning stances. Quote-location and grounding checks establish support in the source; they do not prove that every source claim is externally true ([deep reading contract](../../src/resource_librarian/deep_read.py#L1)).

The lens chain remains **perspective → attention → blind challenge → role → probe → synthesis**. The challenger receives the passage and unlabelled alternatives, not the worker's explanation of which candidate should pass. Topic-like, ungrounded or unsafe candidates are discarded with reasons. A legitimate rejection, none found, or inapplicable result is not automatically a fault ticket. Qualifying lenses stay separately staged; accepting a Source does not accept a reasoning instruction ([lens chain](../../src/resource_librarian/deep_read.py#L18), [lens stage](../../src/resource_librarian/batch.py#L433)).

Whole-source reconciliation stays distinct from part extraction. The existing pass uses a bounded accumulated-claim listing and sampled support, rather than reading a whole PDF in a single call. The proposed Clerk records the material actually considered, corroborates claims across appropriate distinct parts, reconciles repeated lenses and resolves probes answered elsewhere. When the specification needs more coverage than that bounded pass supplies, it directs additional bounded work and retains the gap until it completes. An unavailable pass is queued, not silently finished ([pass bounds](../../src/resource_librarian/deep_read.py#L779), [source-wide pass](../../src/resource_librarian/deep_read.py#L785)).

Data remains kind-specific: repository components and static structure, document chapters, model records or dataset access records. Core scripts extract literal structure; agents own semantic organization and claim placement. Document relations are **inferred from read components**, citing their supporting records. Repository structure is **structurally observed**, not a claim of observed runtime behavior. This proposal does not turn those relations into W5's checked gold/silver/bronze relations ([Data stage](../../src/resource_librarian/batch.py#L444), [relations](../../src/resource_librarian/dik.py#L383), [repository structure](../../src/resource_librarian/dik.py#L501)).

The source draft retains the kind's actual contract: a specific Bottom Line, supported contents/access points, transferable capability, evidence and explicit unread material. Required sections differ for papers, repositories, models and other kinds. Metadata remains a proposal and `Unknown` remains valid; a project's intended application belongs downstream in its own Offering/Application. See the [Source Documentation Standard](../../src/resource_librarian/starter/About/Source%20Documentation%20Standard.md) and [Note Content Model](../../src/resource_librarian/starter/About/Note%20Content%20Model.md).

## Completion and repair

Core scripts record **part coverage**, **required derivation receipts**, **kind-specific output statuses**, **source-review status** and **publication**, applying declared reduction rules. The Clerk assembles and explains the source package from those records; the Oracle judges whether its content meets the specification. These are behavioral requirements, not a new record schema. Reuse needs identical evidence/source bytes, relevant recipes and qualified model routes. Source changes invalidate affected work; completed unrelated items survive. A failed stage stops only its item. Partial, queued, skipped and stale results remain visible while later applicable stages can still produce useful outputs ([completion keys](../../src/resource_librarian/batch.py#L122), [item reduction](../../src/resource_librarian/batch.py#L883)).

Initial processing accounts for every frozen source before noncritical run-level remediation. This preserves the current isolation between items. The Doctor repairs only the affected work; a finished partial item needs explicit re-approval/new authorized processing, while an unfinished run resumes its pinned inputs. The permission gate is not bypassed by calling a restart a repair.

### Conversion fallback and route incidents

`conversionwork → conversionreview → conversioncheck` separates Scribe generation, Clerk fidelity judgment and Core mechanical checks. `dconversion` preserves distinct continuations:

| Result | Continuation |
|---|---|
| Usable mapped representation with appropriate Clerk review | Continue with actual complete/partial coverage. |
| Returned cleanup error/refusal, including a provider error left unretried | `conversiongap` retains `partial`, its cause and usable original extraction. |
| Lost generated anchors with usable original page-mapped text | `conversionfallback` keeps generated text unused and reads originals; parse can be `complete` when no other gap remains. |
| Missing required representation/material or no readable text | Keep partial/queued gaps and no invented reading credit; later applicable work can use available evidence. |
| Uncaught stage/writer failure or critical violation | Retain failed status or take the immediate critical path, respectively. |

This preserves [current parse/OCR distinctions](../../src/resource_librarian/batch.py#L235). A raw-text fallback does not establish original-page verification or independent truth of a paper's claims.

Transport incidents are not structured-output refusals. `dreadtransport`/`dread` and `dconversion` route 429/timeouts/unavailable providers to `readoutage`/`conversionoutage`. Core records existing codes, attempt counts, retry-after and known/unpriced usage, deferring equivalent failed-route calls. Lead chooses a bounded same-route retry, retained gaps/fallback or pause. Scripted retry gates enforce current qualification, authority, backoff and remaining counters before main-flow re-entry; completed matching tasks are reused. This is proposed bounded coordination, not an existing generalized outage service. Model reassignment needs authorized qualification and a changed recorded route, never a silent substitute. Invalid JSON and grounding refusal stay task-layer evidence even when transport completed.

The target dispatch/commit guard and explicit critical exits from every source-stage result route critical findings immediately to the Owner/tier 0. Waiting for the final Oracle is insufficient. A normal denial or unavailable route is not automatically a critical fault.

| Existing class of issue | Responsible actor and proposed handling |
|---|---|
| Required reading/derivation/output still missing, with an accepted mapped remedy | Core records the ticket and evidence; Doctor applies the admitted remedy; Oracle independently rechecks before resolution and exact rejoin. |
| No accepted remedy or an unmapped misalignment | Clerk scouts; Lead re-aligns within the specification or escalates. A proposed new remedy needs Owner acceptance before joining the catalogue. |
| Missing or reserved start, sensitivity, spending or promotion authority | Owner decides the concrete request. Authority already granted inside the run is not requested again. |
| Critical security, data loss, false attestation or authority-boundary breach | Owner and tier 0, when present, are notified immediately. This rule applies at every dispatch/commit, not only the final Oracle review. |
| Exhausted allowance, no progress, uncertain scope or a code change needed | Hand back the unresolved ticket with evidence; preserve the completed and partial work. |

Doctor references use the existing **UC-D outcome contract**: `resolved`, `declined`, `escalated`. A resolved call means the remedy was independently rechecked; declined pauses; escalation remains an unresolved failure. The old prototype's automatic-rollback wording is superseded by [composition policy](../../docs/policy/composition.md#what-a-process-may-contain): compensation is shown for a person's decision. The reference does not authorize automatic undo or imply that proposed catalogue workflows already exist.

Normal checkpoints and repair tickets remain distinct. Outside-envelope calls follow the existing proposed Oracle scope judgement: only an in-scope request already inside the parent's mandate may receive a recorded allowance; reserved/always-ask decisions and uncertain or excess scope retain their escalation. This proposal adds no numeric severity scheme or blanket privilege.

Paper publication remains last and conditional. Non-PDF publication is inapplicable. A fully read PDF whose artifact is not a full conversion can also be inapplicable with limitations recorded. `a17`/`dpublication` freshly check artifact/projection compatibility and an enabled, accepted, current, trusted **folder assignment**; `a18` revalidates during the call. Source acceptance is not a publication prerequisite. Late `FOLDER_STALE`, `awaiting_accepted_folder`, disabled Geo, stale artifacts and returned/caught errors retain distinguishable publication gaps; uncaught preparation errors retain the wrapper's failed-stage outcome. None erases reading or becomes graph success ([publication stage](../../src/resource_librarian/batch.py#L569), [admission](../../src/resource_librarian/paper_graph.py#L163)).

Compatible reading receipts remain reusable while publication is checked against current prerequisites. Existing keys do not explicitly encode every folder/policy change; stronger compatibility/admission is a target requirement, not a claim that historic results are already invalidated. Parent maintenance may reproject existing compatible full evidence without repeating reading, while preserving generated/source-stated/inferred labels and verification limits. Old zero-concept graphs do not justify invented concepts or unscoped rebuilds.

## Preserved stages and proposed ownership

| Existing stage | Model steps | Proposed responsibility |
|---|---|---|
| validate | 5 | Core source/input/control validation and exact receipt reuse |
| parse | 6 and extension 6b | Core scripted extraction/AST/page mapping; Clerk-directed Scribe conversion with Clerk fidelity review; preserve returned-error partial and possibly complete original-text fallback |
| read | 7–11 | Clerk-directed Scribe tasks, Core receipt checks, blind lens work and separately accounted source-wide reconciliation |
| lenses | 10–12 | Clerk owns semantic selection and the lens proposal; Core persists submitted proposals, dispositions, citations and discard history |
| data | 13 | Clerk proposes semantic organization and claim placement; Core supplies scripted structure, record construction, validation and storage |
| relate | 14 | Clerk synthesizes supported relations; Core validates/commits them |
| metadata | 15 | The proposing Clerk selects and explains field values/Unknowns; Core checks fields and stores the proposal |
| review | 16 | Clerk produces grounded, kind-specific source prose; this is not the Oracle |
| publish | 17–18 | Core admits applicable artifacts; Geo publishes and reports its actual result |

At step 19 the Clerk assembles and reconciles the source package using Core counters/receipts. Steps 20–23 add independent judgment and one handback. `a21`, `partialreport` and `delivered` preserve separate Source/lens decision states and named owners; the parent applies its requested acceptance/reject/defer decisions through existing policy. Enrichment accepts neither. A direct user run receives the same package without a tier-0 dependency. Optional lens rejection, zero candidates and valid inapplicability remain normal outcomes.

## Implementation boundaries and review criteria

Executable composition follows **action → workflow → pipeline → sprint**. Source-enrichment workflows contain registered actions; run-level routing, review and repair are composed in the containing pipeline. The same enrichment workflows can serve ingestion or another authorized parent process. A pipeline never defines an action or workflow. This behavioral use case spans those handoffs and does not assign an executable layer merely by drawing a card. Several current stage functions are private Python helpers; W1b must expose appropriate registered seams and state declarations before they become declarative components. All calls still pass through the existing registry, Core writer/index, phase/profile/broker gates and run records.

The missing integrations are Core-owned run specifications and manifests, delegated start/envelopes, the Clerk/Scribe responsibility split, explicit required-derivation completion evidence, fault tickets, generalized Oracle/Doctor attachment and a single terminal handback. The current bounded reading, lens chain, Data/relations, metadata, source review, publication, stage receipts and backlog signals are preserved foundations.

The proposal is ready to consider for implementation when:

- Required whole-source work cannot remain queued behind a full part-reading counter without a visible gap.
- Legitimate inapplicability, rejected optional lenses and unknown metadata remain valid, while missing required answers remain unfinished.
- No noncritical source failure prevents other frozen sources completing their first attempt; targeted repair reuses only matching receipts.
- Source-stated, structurally observed and inferred material remains distinguishable and cited.
- A mapped failure follows an accepted remedy, independent recheck and authorized rejoin; uncatalogued, critical and reserved cases reach their proper actors.
- The initiating tier 0 agent normally hands over and receives one result, without repeating worker tasks. That coordination target never overrides coverage or authority requirements.
- Enrichment success never conceals the subsequent Source/lens acceptance obligations or claims that a missing graph publication occurred.

These are acceptance criteria for future implementation, not claims that the proposed pipeline has run. The approved amendments change behavioral artifacts while preserving the accepted visual style. Runtime code, model assignments and libraries are unchanged.
