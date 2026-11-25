# Proposed to-be enrichment

**Status:** behavioral proposal amended under the Owner-approved [graph review](../2026-11-22-ingestion-enrichment-graph-review.md). No runtime implementation or process promotion.

The proposed enrichment gives the Lead ownership, Clerks responsibility for directing Scribes and authoring/reconciling proposals, and an isolated Oracle/Doctor loop for judging and repairing the result. The Core performs scripted extraction, validation, counting, persistence and dispatch; it does not own semantic proposals. It preserves all nine source stages and separately accounts for complete reading and required derived outputs. Source acceptance remains a named downstream obligation.

| Read or open | Purpose |
|---|---|
| [Proposal and comparison](PROPOSAL.md) | The proposed process, changes from the current mechanism, source evidence, stage/role mapping and review criteria |
| [Proposed to-be enrichment canvas](proposed-tobe-enrichment.canvas) | One actor-column activity map following the supplied ingestion examples |
| [Generated views](proposed-tobe-enrichment.views.md) | Use-case diagram, activity flow, written scenario, extensions, decision tree and scenario test table |
| [Behavior specification](proposed-tobe-enrichment.spec.yaml) | Editable proposal using the supplied activity-spec format, not executable process YAML |
| [Validation](validation.json) | Structural, cross-view/reference, geometry and rendering checks |

[Overview preview](overview.png) and [reading/derivation detail](reading-and-derivations.png) are reading aids. Open the canvas for all guards, reference outcomes and full-size text.

The boundary is deliberate: ingestion supplies captured and approved source work; this process enriches it and returns its actual result. The parent retains its original mixed-batch ledger and separately handles folder metadata, accepted-note revision entry, Source acceptance/promotion and findability. The [earlier baseline](../2026-11-21-enrichment-baseline/README.md) remains supporting evidence.

The amendments make conversion fallback and Clerk fidelity review explicit, distinguish bounded provider outages from task refusals, freshly admit late folder/artifact publication and expose immediate critical-stage exits. A lost-anchor cleanup can fall back to usable original text and complete parsing; returned cleanup errors retain partial status. Reused reading does not bypass publication checks. The handback records separate Source/lens decision worklists and owners; existing-publication maintenance stays in the parent. All five terminal outcomes remain unchanged.

The accepted actor-column style and separately maintained Doctor, Learn and Compose examples remain the references. No model assignment, library data, live Core or runtime source was changed.

To regenerate these proposal artifacts with the repository environment:

```powershell
.venv\Scripts\python.exe -B reports\2026-11-22-proposed-tobe-enrichment\render_proposal.py
```

The authoring script reuses the supplied `render_spec.py`, the earlier report's layout/preview helpers and the existing safe canvas service. It writes only this report's proposal artifacts. Passing those checks establishes internal consistency, not execution or acceptance of the proposed process.
