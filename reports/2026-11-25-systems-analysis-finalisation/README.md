# Systems analysis of the Librarian and Geo-Grapher

25 November 2026. The approach is to map each system as it is, find where it goes wrong, and then design a preferred version that handles every use case, edge case and failure mode. Each graph comes from a spec, is checked, and records its weaknesses (as-is) or what it handles (to-be). There are no swim-lane canvases (D1).

| Pack | Use cases | Weaknesses | Status |
|---|---|---|---|
| [Librarian, as-is](librarian/as-is/INDEX.md) | 18 | 54, in ten root causes ([findings](librarian/AS-IS-FINDINGS.md)) | `IMPLEMENTED_VERIFIED` / `_OBSERVED`, code at `d9435e1` |
| [Librarian, to-be](librarian/to-be/INDEX.md) | 20 | 51 handled; 3 open with reasons ([handles](librarian/to-be/handles.yaml)) | `PROPOSED_UNACCEPTED` |
| [Geo-Grapher, as-is](geo-grapher/as-is/INDEX.md) | 3 (3 deferred) | 17, in six root causes ([register](geo-grapher/as-is/weaknesses.yaml)) | `IMPLEMENTED_VERIFIED`, code at `e71967a` |
| [Geo-Grapher, to-be](geo-grapher/to-be/INDEX.md) | 4 | all 17 handled ([handles](geo-grapher/to-be/handles.yaml)) | `PROPOSED_UNACCEPTED` |

**Correction round, 26 November** (after ChatGPT's review):
- **The process catalogue is restored** as [`catalogue`](librarian/to-be/views/catalogue.views.md) (UC8.2). It covers reuse, the layer rule as accepted, the manifest against the mandate, the Oracle's dry run, the duplicate check, the Owner's acceptance into the repertoire, and storage in the Core with the digest pinned.
- **New checked tables:**
  - the [data contract](librarian/to-be/data-contract.md) (Medallion and DIK, kept distinct from Geo-Grapher's trust tiers);
  - [authority](librarian/to-be/authority.md) (permissions against reserved decisions, reconciling tier 0's authority with the policy);
  - [ticket routing](librarian/to-be/ticket-routing.md);
  - performance baselines for the [Librarian](librarian/to-be/performance.md) and [Geo-Grapher](geo-grapher/to-be/performance.md);
  - Geo-Grapher's [incremental safety cases](geo-grapher/to-be/incremental-safety.md).
- **Two open gaps closed:** a ticket for each quarantined sibling, and the person's draft kept through a stale revision.
- **Other changes:** the Oracle now checks unchanged children by their receipts' hashes, and pack specs no longer point to themselves.
- **All four packs pass with no warnings.** [VALIDATION.md](VALIDATION.md) says what that does and does not prove.
- **Handoff review** (same day): fifteen fixes for bounded retries, reachable paths, complete handoffs, rechecks, a single owner for drafting remedies, and Geo-Grapher's receipt contract. They are listed at the end of the [adversarial review](ADVERSARIAL-REVIEW.md).
- **Second pass** (DeepInfra readers and reviewers, 19 calls, $0.83 of the $5 allowed):
  - The [regression matrix](REGRESSION-MATRIX.md) traces 224 checked requirements from the 20–24 November research, designs and graphs: 210 preserved, 12 deferred on the record, 2 rejected with evidence, none unresolved.
  - The [adversarial review](ADVERSARIAL-REVIEW.md): 56 findings with verbatim quotes, 39 accepted (23 changes), 17 rejected with reasons.

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
- **Owner decision, from the authority table:** whether to delegate any reserved decision (such as sensitivity review in the test vault) to tier 0. That would change the policy.
- **Open question, from the catalogue:** the accepted layer table allows same-layer components only for workflows; the 20 November UC-C allowed them at every layer.
- **Decisions the performance tables leave open:** retention numbers, bounded concurrency, the target rate for folder descriptions.
- **Decided 26 November:** an unlicensed repository is treated the same as any external source. Its licence status is a label, never a gate. The [ingest sequence by source kind](librarian/to-be/source-kinds.md) shows how a repository and a document differ: their units, their relations, the graph each feeds.

## Out of scope of these packs (deferred, on the record)

The [regression matrix](REGRESSION-MATRIX.md) found requirements that these process packs do not draw. They are deferred here explicitly, each with where it belongs:
- **The diagram-workflow tooling itself:** lens-pack acceptance and lens provenance, problem statements as a required field, and canvas approval and adoption. These are the diagram-workflows proposal's phases P0–P5. The canvas rules are already enforced by the W2 canvas service, which writes the index canvases.
- **Repository boundaries:** no dependency on the retiring MARK XLVIII harness. This is a constraint on the codebase, not a process.
- **Implementation defects reported on 24 November, not drawn as processes:**
  - Geo-Grapher's dependency relations for Python functions;
  - graph search when repository ids are omitted;
  - conversions persisting a source graph;
  - code repositories attached read-only, never opened as libraries.

  Each needs its own check against the code before it is drawn, or fixed.
- **Decisions D2–D4** in [PLAN.md](PLAN.md):
  - archiving superseded specs;
  - the size limit, applied here at 40;
  - sequence diagrams, none drawn yet.
- **Wording: done.** The 14 to-be specs inherited from 24 November were reworded in plain language: 325 titles, problem statements, labels and guards, with structure, ids and reference outcomes unchanged ([`tools/s4_plain_language.py`](tools/s4_plain_language.py) holds the old-code-to-meaning key).
  - Model names were taken out of the labels. The Oracle and Doctor were assigned GLM-5.3 on 24 November; that assignment is revisable and is not part of the design.
- **S6, your review** of the four packs.

## How to regenerate

```powershell
.venv\Scripts\python.exe reports\2026-11-25-systems-analysis-finalisation\render_pack.py --all
```

`--check` writes nothing, and fails if any view is older than its spec. [CANONICAL.md](CANONICAL.md) records which spec replaced which. `tools/` holds the one-off scripts that did S1 and the splits.
