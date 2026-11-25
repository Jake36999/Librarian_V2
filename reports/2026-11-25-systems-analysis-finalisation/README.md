# Systems analysis of the Librarian and Geo-Grapher

25 November 2026. The approach is to map each system as it is, find where it goes wrong, and then design a preferred version that handles every use case, edge case and failure mode. Each graph comes from a spec, is checked, and records its weaknesses (as-is) or what it handles (to-be). There are no swim-lane canvases (D1).

| Pack | Use cases | Weaknesses | Status |
|---|---|---|---|
| [Librarian, as-is](librarian/as-is/INDEX.md) | 18 | 54, in ten root causes ([findings](librarian/AS-IS-FINDINGS.md)) | `IMPLEMENTED_VERIFIED` / `_OBSERVED`, code at `d9435e1` |
| [Librarian, to-be](librarian/to-be/INDEX.md) | 19 | 48 handled; 6 open with reasons ([handles](librarian/to-be/handles.yaml)) | `PROPOSED_UNACCEPTED` |
| [Geo-Grapher, as-is](geo-grapher/as-is/INDEX.md) | 3 (3 deferred) | 17, in six root causes ([register](geo-grapher/as-is/weaknesses.yaml)) | `IMPLEMENTED_VERIFIED`, code at `e71967a` |
| [Geo-Grapher, to-be](geo-grapher/to-be/INDEX.md) | 4 | all 17 handled ([handles](geo-grapher/to-be/handles.yaml)) | `PROPOSED_UNACCEPTED` |

**Each pack holds:**
- **G1** a use case diagram;
- **G2** the composition of processes;
- **G3** for each use case, the four views: Mermaid activity diagram, written use case, decision tree, and test cases with boundary values;
- **G4** state diagrams;
- an index and an index canvas.

Weaknesses link to their evidence, and as-is and to-be use cases pair by id.

## Reading order

1. [The Librarian's findings](librarian/AS-IS-FINDINGS.md): ten root causes, each with the rule the to-be must meet.
2. The two Librarian indexes, side by side. The as-is index's root-cause table counts how much of each cause the to-be handles.
3. Geo-Grapher's root causes:
   - **GT1 rebuild instead of change**: full snapshots, a full database copy per paper, nothing ever pruned; 77.2 GB for 30 graphs;
   - **GT2 status says more than was done**: complete over parse failures and empty papers;
   - **GT3 two stores, no stored link**: 48 published papers have no Source note;
   - **GT4 durability**: no WAL checkpoint;
   - **GT5 graphs stay islands**: no bridges;
   - **GT6 an agent interface that answers too much or nothing**.

## What is open

- **Owner decisions** (Librarian):
  - may a person's own surface skip the Broker (`W-ACT-05`);
  - correct the attester on the 96 notes of 20 November (`W-ACC-04`).
- **No to-be element yet** (Librarian):
  - a ticket for each quarantined sibling (`W-INT-02`);
  - keeping a person's draft through a stale-revision conflict (`W-ACC-01`).
- **Decisions D2–D4** in [PLAN.md](PLAN.md):
  - archiving superseded specs;
  - the size limit, applied here at 40;
  - sequence diagrams, none drawn yet.
- **Wording.** The 24 November to-be specs were split and relabelled only. Their wording leans on rule and workstream codes (Rule-15, OD-05, MC-10, NAT-13) and needs a plain-language pass before review.
- **S6, your review** of the four packs.

## How to regenerate

```powershell
.venv\Scripts\python.exe reports\2026-11-25-systems-analysis-finalisation\render_pack.py --all
```

`--check` writes nothing, and fails if any view is older than its spec. [CANONICAL.md](CANONICAL.md) records which spec replaced which. `tools/` holds the one-off scripts that did S1 and the splits.
