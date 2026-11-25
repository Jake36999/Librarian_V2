# Enrichment baseline and proposed comprehensive integration

**Status:** comprehensive target model amended under the Owner-approved [graph review](../2026-11-22-ingestion-enrichment-graph-review.md), 22 November 2026. This work records existing requirements and proposed integration. W1b runtime implementation has not started.

The model preserves the current ingestion and enrichment operations while locating the missing agent coordination, scripted Core services, delegated authority, fault-ticket routing, Oracle and Doctor integration. The source-backed baseline governs the model; a diagram does not replace those requirements.

## Review the baseline and linked models

| Artifact | Purpose |
|---|---|
| [Requirements and evidence](requirements-evidence.md) | 34 requirements with source/test evidence, current-versus-planned boundaries and explicit model-node traceability |
| [Proposed comprehensive canvas](enrichment-cycle.canvas) | End-to-end target integration in the accepted actor-column style; its title/note distinguish it from a historical execution trace |
| [Model notes](model-notes.md) | Nine-field use-case description, source/target roles, stage semantics, old extension correspondence and ticket responsibilities |
| [Generated views](enrichment-cycle.views.md) | Use-case diagram, activity diagram, written scenario, extensions, lane load, decision tree and scenario test table, derived from the same model |
| [Behavior specification](enrichment-cycle.spec.yaml) | Editable behavioral model using the supplied activity-spec format; not executable process YAML |
| [Verification](verification.md) | Artifact checks, focused regression results and incomplete Core-test evidence |
| [Observed enrichment](observed-enrichment.md) | Actual completed full/partial batches, retained outputs, model-call evidence and current-versus-proposed ownership |
| [Current mixed-batch dispatcher](batch-enrichment-current.md) | Existing approved-batch dispatch in frozen mixed-item order, including the Source branch and folder_validate → folder_describe → folder_data |
| [Current source-enrichment child](source-enrichment-current.md) | Source-only scripted/model detail called by the mixed dispatcher for its selected Source item; not the complete process_approved contract |

The [23 November follow-up](../2026-11-23-current-graph-followup.md) corrects the current-execution views and their linked parents. The comprehensive target canvas contains manual Owner position edits and is preserved during this follow-up; it is not replaced by the current mixed-batch or Source-only views.

The later [routing correction and proposed family](../2026-11-23-routing-and-tobe-proposals.md) resolves remaining edge/card crossings in the five generated maps and provides a to-be counterpart for each of the three current-state boundaries. Wider native gutters preserve actor/card widths, colors and current processing order. The comprehensive canvas's manual geometry remains unchanged.

The generated views include the prototype's expanded extension scenarios and are large. Begin with the baseline, canvas and model notes. The scenario table is a conditional branch/rejoin inventory, not an exhaustive execution proof or a new process implementation.

## Decisions recorded

- The role order is Overseer at tier 0, Lead at tier 1, Clerk at tier 2 and Scribe at tier 3. Semantic alignment does not swap legacy numeric configuration fields.
- Tier 0 may delegate on the user's behalf and use Librarian's DeepInfra agents to support its active external task. The model retains explicit authority, budgets and reserved person decisions while showing where current person-only APIs need integration.
- Specifications belong within the Core. This report is authoring and review material; it does not establish another runtime specification store.
- Agents own interpretation, proposals and decisions. Core performs scripted extraction, checks, counters, storage and dispatch. The 22 November correction moves Data/metadata proposals and acceptance to Clerk, and pause/escalation explanations to Lead; model conversion has an explicit Clerk/Scribe path. Storage and tool invocation do not transfer authorship to Core.
- Faults are tickets with existing refusal/extension identifiers, tiered flags, evidence and accountable actors. The previous four-bit proposal is superseded.
- GLM-5.3 is the current assignment for both Oracle and Doctor. The adapter/role mechanism keeps either assignment revisable. Their contexts remain separate; independent review still requires reconciliation if the worker uses the same route.

These decisions are reflected in [role policy](../../docs/policy/agent-roles-and-authority.md), [terminology](../../docs/terminology.md), [the diagram proposal](../../docs/proposals/diagram-workflows.md) and [the continuation plan](../../docs/proposals/plan-forward-2026-11.md).

## Requirements preserved

The cycle includes native reference capture, mixed folder purposes, source-eligible root queueing, metadata-only folder batches, approval separate from processing start, and the full source sequence: **validate → parse → read → lenses → data → relate → metadata → review → publish**.

The branches retain partial/failed/queued/stale outcomes, exact completion reuse, source changes, isolated item failures, cancellation, spending stops, captured-only acceptance, accepted-note revisions, sensitivity and promotion policy, true actor attestation, guarded writes, derived indexes and findability. Paper-graph success remains conditional on the actual document, conversion, reading and accepted assignment. A disabled or refused publication is not silently called enriched.

The approved amendments add explicit conversion fallback, Clerk fidelity review, bounded route-outage decisions, immediate critical-stage exits, late folder/artifact publication admission, independent Source/lens worklists and scoped existing-publication reconciliation. Returned cleanup errors retain their partial status; lost generated anchors can fall back to usable original text and complete parsing when no other gap remains. Reused reading does not bypass current publication prerequisites. Maintenance uses accepted-note revisions or explicitly re-approved partial work, without new-source duplicate admission or an unchecked upgrade of generated claims.

The cross-library audit qualifies observed paths: twelve folder-item description failures in two batches, late stale/awaiting-folder publication gaps, and four written-but-not-findable notes. Historical queue-ledger entries, current decision backlogs, publication and Source acceptance are separate populations/states. Independent lens decisions are separately owned; pending work is not automatically a fault or authorization to accept it.

General tickets, delegated run envelopes, specification ownership enforcement and Oracle/Doctor execution are target integration. The model identifies their interfaces to the existing mechanisms and does not claim they have been deployed.

## Canvas preservation and previews

The initial baseline left the 20 November examples unchanged. The Owner subsequently authorized correcting both ingestion and enrichment maps. Their generated flow geometry is updated where the revised sequence requires it, after verifying the saved canvas against its original or last validated generation. The existing preview/revision/hash-checked commit service preserves manual content and unknown metadata; actor columns, card dimensions, colors and explicit edge sides retain the accepted style. Default regeneration preserves saved geometry. `--reflow-generated` allows a deliberate structural revision only when the saved canvas matches its previous validation receipt, so unreviewed Owner edits are not overwritten.

[Overview preview](overview.png) and [source-stage detail](source-stages.png) are deterministic raster previews of the saved canvas geometry. They are reading aids; the canvas retains all labels and guards at full size.

To regenerate this report's model outputs with the repository environment:

```powershell
.venv\Scripts\python.exe -B reports\2026-11-21-enrichment-baseline\build_artifacts.py
.venv\Scripts\python.exe -B reports\2026-11-21-enrichment-baseline\render_preview.py
```

The scripts write only this report's artifacts through the existing canvas service. The supplied prototype renderer, runtime code, tool schemas, role assignments, live Cores and library data are unchanged.
