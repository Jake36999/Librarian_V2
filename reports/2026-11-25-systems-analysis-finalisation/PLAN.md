# Finalising the systems-analysis graphs: review and plan

25 November 2026.

This document reviews every diagram made for the Librarian's systems analysis between 20 and 24 November, then plans the finished set: one pack for the current state (as-is), one for the proposed state (to-be). It is a plan, not a change. Nothing here has been built, moved or committed.

**What the graphs are for** (Owner, 25 November). The Librarian and Geo-Grapher already do a lot of things; they don't yet do them well. Seen from a systems-analysis stance, the graphs should expose the exact weaknesses and logical gaps that have to close before the runtimes are clean and the parts work together. The order is:
1. map everything as it is;
2. find where it goes wrong;
3. design a preferred version that handles every use case and edge case, and each identified failure mode.

So each as-is graph records its weaknesses and gaps beside its paths, and each to-be graph names the failures it handles. The Librarian goes first, then Geo-Grapher.

**Why now.** In hindsight, too much of the work went into large swim-lane canvases. The compact views generated beside them were the useful output. [`compose.views.md`](../2026-11-20-workflow-map/examples/ingestion/compose.views.md) is the reference: a Mermaid activity diagram of 35 nodes, a generated written use case, a lane load, a decision tree and a test table, all from one spec.

## 1. What exists

### 1.1 Inventory

There are 22 active specs (corrected from 20 during S1), all rendered by `render_spec.py` or a wrapper around it. The folder `2026-11-21-isolated-incomplete-examples/` holds 109 more specs; it is quarantined and left out of everything below.

In the *Views* column: M = Mermaid activity diagram, W = written use case, D = decision tree, T = test table.

| Process | As-is spec (status) | Nodes | To-be specs, oldest first | Nodes |
|---|---|---|---|---|
| Activation: who starts work and how | `2026-11-24/…/librarian-current-activation` (`IMPLEMENTED_VERIFIED`, d9435e1) | 73 | `2026-11-24/…/librarian-context1-tier0-delegated`, `…context2-external-project-mcp`, `…context3-human-platform-ui` (`PROPOSED_UNACCEPTED`) | 41, 34, 37 |
| Process composition | — (UC8's as-is text in USE-CASES.md only) | — | `examples/ingestion/compose` (UC-C) → `2026-11-24/…/librarian-process-composition-tobe` | 35 → 34 |
| Ingestion (capture) | `examples/ingestion/ingestion` (historical DataManagement run, re-scoped by other sessions to "observed path and current-code alternatives") | 62 | `examples/ingestion/ingestion-tobe` → `2026-11-23/proposed-ingestion` → `2026-11-24/…/librarian-ingestion-tobe` | 107 → 145 → 58 |
| Batch enrichment (the approved batch) | `2026-11-21-enrichment-baseline/batch-enrichment-current` | 31 | `2026-11-23/proposed-batch-enrichment` → `2026-11-24/…/librarian-batch-enrichment-tobe` | 59 → 37 |
| Source enrichment (9 stages) | `2026-11-21-enrichment-baseline/source-enrichment-current` | 53 | `2026-11-21/enrichment-cycle` (an as-is/to-be hybrid) → `2026-11-22/proposed-tobe-enrichment` → `2026-11-23/proposed-source-enrichment` → `2026-11-24/…/librarian-source-enrichment-tobe` | 195 → 90 → 113 → 57 |
| Geo-Grapher graph building | `2026-11-22-geographer-graph-building` | 36 | — | — |
| Doctor (repair) | — (as-is: tier 0 repairs by hand) | — | `examples/ingestion/doctor` (UC-D) → `2026-11-24/…/librarian-doctor-tobe` | 22 → 26 |
| Learning a remedy | — | — | `examples/ingestion/learn` (UC-L) | 10 |
| Research a brief (UC2) | — (pictured only in `ingestion-and-research-run.canvas`) | — | — | — |
| Verify claims (UC3), cite the graph (UC4), oracle (UC-O), reorganise (UC6), see other models (UC7) | — | — | — (UC-O exists only as prose, proposal §10) | — |

Views generated: all 20 have M, W and D. Only 4 have T (compose, doctor, learn and geographer graph building); the other renderers dropped the test table.

### 1.2 What worked

- **Spec first.** Every diagram comes from a `.spec.yaml`, and the deterministic checks caught real errors: guards on activities, misnumbered extensions, missing outcomes on references, false parallelism.
- **References between processes** (`kind: ref`), with a check that each call handles every outcome of the process it calls. The 24 November family is properly a tree of parent and child processes.
- **Status labels.** The 24 November set marks each model `IMPLEMENTED_VERIFIED` or `PROPOSED_UNACCEPTED`. The as-is enrichment baseline was reviewed against the code and found accurate (antgrav review, 21–23 November).
- **Evidence.** The as-is specs cite code and observed runs; the to-be specs cite research and policy.

### 1.3 What went wrong

1. **Swim-lane canvases took the effort.**
   - The canvases are 1,660 × 2,200 pixels at the smallest and 8,540 × 25,990 at the largest.
   - Producing them needed edge-routing code, overlap and overflow checks, PNG renders, "presentation proofs", and 30+ `.bak` files from repeated re-layout.
   - None of it makes the analysis more correct. The Mermaid view of the same spec is readable at a glance and is generated in under a second.
2. **Diagrams too large to read.**
   - Four specs exceed 100 nodes (195, 145, 113, 107).
   - Five of the current canonical ones exceed 50 (73, 62, 58, 57, 53).
   - `compose.views.md` reads well at 35. Past about 40 nodes, a process should be split into a parent and children joined by references, which the 24 November family already started doing.
3. **Generations without a canonical marker.**
   - Ingestion to-be exists three times, source enrichment to-be four times, batch to-be and doctor twice each.
   - Only the 24 November README says which is current. The older files still read as live.
4. **Only part of the course's four views.**
   - Use case diagrams exist only hand-written, in USE-CASES.md and INGESTION-EXAMPLE.md, and not for the current processes.
   - Test tables appear in 4 of 20.
   - No state diagrams: the lifecycle of a staged item (queued → captured → staged → approved → enriched or partial → accepted) is the single most useful one, and it was never drawn.
   - No composition tree: action → workflow → pipeline → sprint.
5. **Stale and drifting.**
   - `librarian-current-activation.spec.yaml` was corrected at 08:56 on 25 November (`deep-read-staged` as a plain workflow; folder review kept apart from source intake). Its views, canvas, PNG and validation are from 02:18, so they show the uncorrected spec.
   - Tier names drift: policy now reads tier 2 = Clerk, tier 3 = Scribe (`docs/terminology.md`, uncommitted), but the 20–21 November specs say Clerk (tier 3) and Helper (tier 2).
6. **Coverage gaps.**
   - Research (UC2), verify claims (UC3), cite the graph (UC4) and the oracle (UC-O) have no activity specs at all, as-is or to-be.
   - Geo-Grapher graph building has an as-is spec but no to-be.
7. **Ten renderers.** `render_spec.py` plus nine wrappers (`render_corrected`, `build_artifacts`, `render_current`, `render_preview`, `build_geographer_graph`, `render_proposal`, `build_family`, `build_and_validate_diagrams`, `validate_followup`), each adding its own views and checks.
8. **Uncommitted.**
   - Every folder from 21 November on is untracked: the baseline, Geo graph building, both proposed families, and reconstruction-and-offering.
   - So are 23 changes under `examples/ingestion/`, and the terminology and policy edits.
   - None of this is backed up.

## 2. The finished set

Two packs, **as-is** and **to-be**, with the same structure, so every to-be graph has an as-is counterpart to compare against, or is marked new.

### 2.1 The graphs in each pack

| # | Graph | Question it answers | Form | Source |
|---|---|---|---|---|
| G1 | **Use case diagram** (system context) | Who interacts with the Librarian, for what goals, and which use cases include or extend others | Mermaid: actors outside a system-boundary subgraph; include and extend as dashed edges | One `use-cases.yaml` index per pack |
| G2 | **Process composition tree** | Which processes are built from which: sprint → pipeline → workflow → action | Mermaid tree | As-is: compiled from the shipped YAML processes by the manifest builder (proposal §11.7). To-be: from the specs' references. |
| G3 | **Per use case, four views** (the course set) | How it flows; what exactly happens; every path; how we would test it | Mermaid activity diagram (at most ~40 nodes; larger processes are split into parent and child by reference), written use case in the nine-field template, decision tree, test table with boundary values | The use case's `.spec.yaml` |
| G4 | **State diagrams** for the entities that carry state | What states an item can be in, and what moves it between them | Mermaid `stateDiagram-v2` | As-is: the status values in the code (staging items, sessions, folder decisions, offerings). To-be: the proposals. |
| G5 | **Sequence diagrams**, only where the order of messages between actors is the point | Who calls whom, in what order | Mermaid `sequenceDiagram` | Hand-written from the spec. For two cases: tier 0 working through MCP (Context 2), and publishing a paper to Geo-Grapher. |
| G6 | **One index canvas** per pack | Where everything is | Obsidian canvas: one card per graph, linking to its views, grouped by G1–G5 | Generated |

**Swim-lane canvases stop being produced.** The existing ones are kept as they are, marked archived. Lanes stay in the spec, because they carry the actor of every step, and Mermaid can show them as subgraphs when wanted.

### 2.2 The use cases in each pack

In priority order. "Keep" means an existing spec is canonical; "split" means it is canonical but over ~40 nodes; "new" means none exists.

| Use case | As-is | To-be |
|---|---|---|
| Activation (UC0) | Split `librarian-current-activation` (73) into parent plus UI, folders, MCP children, after re-rendering it | Keep the three contexts and `librarian-process-composition-tobe` |
| Ingestion (UC1) | Keep `ingestion` as the historical trace. **New:** a general current ingestion, so the as-is is not one run's story. | Split `librarian-ingestion-tobe` (58) |
| Batch enrichment (UC1b) | Keep `batch-enrichment-current` | Keep `librarian-batch-enrichment-tobe` |
| Source enrichment (UC1c) | Split `source-enrichment-current` (53) | Split `librarian-source-enrichment-tobe` (57) |
| Geo graph building (UC1d) | Keep `geographer-graph-building` | **New** |
| Research a brief (UC2) | **New**, from the 20 November run and the session code | **New** |
| Verify claims (UC3) | **New** (the claim review as it runs) | **New** (with the oracle) |
| Cite the graph (UC4) | **New** | **New** |
| Doctor (UC-D), learn (UC-L) | **New:** the as-is is "tier 0 repairs by hand", drawn honestly | Keep `librarian-doctor-tobe`; fold UC-L into it or keep it as its child |
| Oracle (UC-O) | — (as-is: the audited session's Tier A/B checks, drawn as that) | **New**, from proposal §10 |
| Compose (UC8 / UC-C) | **New**, from `workflows.py` save, validate and run | Merge UC-C into `librarian-process-composition-tobe` |
| Reorganise (UC6), other models (UC7) | Deferred | Deferred |

**State diagrams (G4)**, as-is and to-be:
- a staged item;
- a session (open, parked, closed, and its phases);
- a folder decision;
- an offering (draft → staged → promoted).

### 2.3 Rules for every graph

- **Size.** An activity diagram has at most ~40 nodes. A larger process is split into a parent and children joined by references.
- **Status.** Every spec carries `status`: `IMPLEMENTED_VERIFIED`, `IMPLEMENTED_OBSERVED` or `PROPOSED_UNACCEPTED`, plus `supersedes:` when it replaces an older one. As-is and to-be are never mixed in one spec, which is the fault the antgrav review found in `enrichment-cycle`.
- **Terms.** Actor names come from `docs/terminology.md` as it stands, with tiers 2 = Clerk and 3 = Scribe once that edit is accepted. The renderer checks each lane name against a list drawn from it.
- **Fresh.** Views are regenerated whenever a spec changes. The validator records each spec's hash, and the pack's index flags any view older than its spec.
- **Traceable.** Each to-be use case has a short delta table: what changes from its as-is counterpart, and which open point (OP1–OP16) or proposal section it answers.

## 3. Steps

| Step | What | Done when |
|---|---|---|
| **S0. Secure the work** | Commit the untracked diagram folders and the examples changes, by explicit path. Re-render `librarian-current-activation` so its views match its corrected spec. Leave the quarantined folder out. | The work since 21 November is in git; the activation views are newer than their spec |
| **S1. Mark what is canonical** | Add `status` and `supersedes` to every active spec, per 1.1. Mark the older generations superseded in place. Moving them to an archive folder is an Owner decision (D2). | Each process has exactly one canonical as-is and one canonical to-be, or a marked gap |
| **S2. One renderer** | Fold the useful checks from the nine wrappers into `render_spec.py`: reference parity, status, tier-name check, size limit, freshness. Add G1, G2, G4 and the index (G6). Make the test table and boundary values part of every views file. Retire the wrappers. | One command renders a whole pack. Every views file has all four views. The wrappers are deleted or archived. |
| **S3. The as-is pack** | Split the four oversized as-is specs. Write the new ones: general ingestion, UC2, UC3, UC4, UC-D as-is, compose. Write the as-is state diagrams. | Every as-is row in 2.2 has a spec of at most ~40 nodes per diagram that passes the checks |
| **S4. The to-be pack** | Split the oversized to-be specs. Write Geo graph building, UC2–UC4 and UC-O. Merge UC-C. Write the to-be state diagrams. | The same, for the to-be rows |
| **S5. Compare and index** | A delta table per use case; the G1 diagrams and composition trees for both packs; the index canvases | Every to-be element traces to an as-is element or is marked new, with its OP or proposal section |
| **S6. Owner review** | Walk the two packs side by side | The Owner accepts the as-is pack as current, and marks which to-be graphs are accepted as the plan |

**Status, 25 November.**
- **S0 done.** D5 was settled with it: the Owner approved S0, and with it the commit of the other sessions' terminology and policy edits.
- **D1 decided:** no swim-lane canvases.
- **S1–S4 done** for the Librarian and Geo-Grapher; see [README.md](README.md).
- **S5 mostly done.** Each to-be use case's `handles` table is its delta against the as-is, and each pack has its index canvas. A side-by-side delta page is not written.
- **Open:** S6 (the Owner's review) and D2–D4.

**Cost.** S0–S2 and S5 need no model. The as-is specs in S3 come from code and run records. The to-be specs in S4 come from the existing proposals. A Clerk-tier model may draft first versions of the new specs, lane by lane, per the proposal's §8, but every spec passes the deterministic checks before it counts.

## 4. Decisions for the Owner

1. **D1. Decided 25 November: yes.** Stop producing swim-lane canvases, keep the existing ones as archived, and make the Mermaid views and one index canvas per pack the deliverable.
2. **D2.** Move superseded specs and their artifacts into an `archive/` folder per report, or mark them superseded in place and leave them. A move is reversible, but it changes paths other documents link to.
3. **D3.** The size limit (~40 nodes per activity diagram), and splitting into parent and children by reference above it.
4. **D4.** Which G5 sequence diagrams to draw, if any, beyond the two proposed.
5. **D5.** Commit the work since 21 November now (S0), before anything else changes it. This includes the uncommitted terminology and policy edits, which are another session's. Committing them is the Owner's call or that session's.
