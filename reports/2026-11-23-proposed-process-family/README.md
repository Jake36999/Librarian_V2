# Proposed to-be process family

**Status:** proposed behavioral revision, 23 November 2026. The three maps follow the corrected current boundaries and use the existing accepted activity-spec and canvas notation. They do not implement runtime orchestration or authorize live processing.

| Corrected current graph | Proposed counterpart | Responsibility |
|---|---|---|
| [Ingestion](../2026-11-20-workflow-map/examples/ingestion/ingestion.canvas) | [Proposed ingestion](proposed-ingestion.canvas) · [notes](proposed-ingestion.md) | Commission, folder access and indexing, intake, actual start authority, independent decisions, guarded promotion and final parent review. |
| [Mixed-batch dispatch](../2026-11-21-enrichment-baseline/batch-enrichment-current.canvas) | [Proposed mixed batch](proposed-batch-enrichment.canvas) · [notes](proposed-batch-enrichment.md) | Original mixed ledger, kind-specific dispatch, folder metadata, item isolation and mixed-result review. |
| [Source enrichment](../2026-11-21-enrichment-baseline/source-enrichment-current.canvas) | [Proposed source enrichment](proposed-source-enrichment.canvas) · [notes](proposed-source-enrichment.md) | Nine source stages, required evidence and derivations, agent proposals, conditional publication and independent package review. |

The parent calls the mixed child; its Source branch calls source enrichment for the selected item. Children inherit the same commission, Lead, grants and ledger. They return `success`, `partial`, `reused`, `paused` or `escalated` with evidence. Neither child settles the parent's independent acceptance decisions.

Lead owns direction. Clerk owns interpretation, synthesis, semantic proposals and proofreading, directing bounded Scribe work. Core runs scripts, checks literal constraints, stores specifications/results and dispatches admitted operations. Oracle judges independently; Doctor applies accepted mapped remedies within verified scope. Owner and Overseer routes retain their actual authority. Role adapters keep the current Oracle/Doctor assignment revisable.

The existing [accepted ingestion target](../2026-11-20-workflow-map/examples/ingestion/accepted-ingestion-tobe.canvas), [focused source target](../2026-11-22-proposed-tobe-enrichment/proposed-tobe-enrichment.canvas) and [comprehensive integration](../2026-11-21-enrichment-baseline/enrichment-cycle.canvas) remain lineage references. Manual Owner edits in the comprehensive canvas are preserved. These three new proposals provide corresponding views of the corrected current decomposition rather than silently replacing the earlier target artifacts.

Specs, written views, previews and validation accompany each map. Validation covers artifact consistency and saved geometry; it does not certify live-library health or runtime implementation.

The [completion record](../2026-11-23-routing-and-tobe-proposals.md) links the corrected and proposed artifacts. [Family validation](validation.json) records the three generated models. Local reporting exits repeat the same report and outcome where needed to keep native canvas edges clear. The per-model presentation proofs fold those copies back to identical actors, labels, guards and outcomes; they add no execution steps. Actor columns remain 400 pixels wide and activity cards remain 360 × 150; gutters use a 600-pixel pitch to accommodate return edges.

To regenerate the proposed family with the repository environment:

```powershell
.venv\Scripts\python.exe -B reports\2026-11-23-proposed-process-family\build_family.py
```

The existing renderer supplies all activity, scenario and tree views. The report builder uses the existing revision/hash-checked canvas service. It checks the presentation proof before generation, preserves saved geometry on repeat preview and refuses unresolved preview edge/card intersections.
