# Canonical specs (S1)

25 November 2026. Each process now has one canonical spec per state, held in a pack, or a marked gap. [`tools/s1_canonical.py`](tools/s1_canonical.py) did the following:
- copied each canonical original into its pack under the pack's id, with `status`, `use_case` and `supersedes`;
- marked every one of the 22 active originals with `superseded_by` (and `status` where it had none). It inserted those two lines after the original's `diagram:` line and changed nothing else.

[`tools/s1_actor_names.py`](tools/s1_actor_names.py) then gave the copies the actor names of [docs/terminology.md](../../docs/terminology.md). Nothing was moved or deleted (D2 is open).

The same use case has the same id in both packs, so `librarian/as-is/ingestion` and `librarian/to-be/ingestion` are counterparts.

| Process | As-is (pack: `librarian/as-is`) | To-be (pack: `librarian/to-be`) | Superseded generations |
|---|---|---|---|
| UC0 Activation | `activation` ← `2026-11-24…/librarian-current-activation` (to split, S3) | `activation-overseer`, `activation-external-project`, `activation-web-ui` ← the three 24 November contexts | — |
| UC8 Compose | gap (new in S3) | `compose` ← `librarian-process-composition-tobe` | `examples/ingestion/compose` (UC-C) |
| UC1 Ingestion | gap: a general current ingestion is new in S3. The observed trace of 19–20 November (`examples/ingestion/ingestion`) stays as its evidence, `IMPLEMENTED_OBSERVED` | `ingestion` ← `librarian-ingestion-tobe` (to split, S4) | `examples/ingestion/ingestion-tobe`, `2026-11-23…/proposed-ingestion` |
| UC1b Batch enrichment | `batch-enrichment` ← `2026-11-21-enrichment-baseline/batch-enrichment-current` | `batch-enrichment` ← `librarian-batch-enrichment-tobe` | `2026-11-23…/proposed-batch-enrichment` |
| UC1c Source enrichment | `source-enrichment` ← `…/source-enrichment-current` (to split, S3) | `source-enrichment` ← `librarian-source-enrichment-tobe` (to split, S4) | `enrichment-cycle` (an as-is and to-be hybrid), `proposed-tobe-enrichment`, `proposed-source-enrichment` |
| UC-D Doctor | gap (new in S3: tier 0 repairs by hand) | `doctor` ← `librarian-doctor-tobe` | `examples/ingestion/doctor` (UC-D) |
| UC-L Learn a remedy | — | `learn` ← `examples/ingestion/learn` | — |
| UC2 Research, UC3 Verify claims, UC4 Cite the graph, UC-O Oracle | gaps (new in S3) | gaps (new in S4) | — |
| UC1d Geo graph building | `geo-grapher/as-is/graph-building` ← `2026-11-22-geographer-graph-building` | gap (new) | — |

**Archived, not deleted (D1).** Every `.canvas` and `.png` beside the superseded and copied specs is kept as it is and is no longer regenerated. That covers the 24 November diagrams, the enrichment baseline, the proposed families and `examples/ingestion`. The old renderers (`build_and_validate_diagrams.py`, `build_artifacts.py`, `render_current.py`, `render_preview.py`, `build_geographer_graph.py`, `render_proposal.py`, `build_family.py`, `render_corrected.py`, `validate_followup.py`) are retired: [`render_pack.py`](render_pack.py) replaces them for the packs, and `render_spec.py` remains its tree logic.

**What the checks found on the copies.**
- No structural or reference errors.
- Every lane failed the actor check until the renames. The drifted names included "Tier 0 agent", "Human user", "Librarian UI", "Specification owner", "Model worker (legacy transport)", and three combined lanes ("In-app Lead / Model worker", "Lead / Clerk / Scribe", "Clerk & Model Host").
- Four diagrams are over the 40-node limit and are split in S3 and S4: as-is activation (72) and source enrichment (51); to-be ingestion (58) and source enrichment (57).
