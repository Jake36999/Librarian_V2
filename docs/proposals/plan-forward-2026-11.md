# The plan forward, November 2026

**Status:** proposal (rank 5 in `docs/policy/README.md`). Owner direction, 20 November 2026. It becomes plan work, entered in `docs/unified-implementation-plan.md`, only once the owner accepts a workstream.

**Inputs:**
- [the workflow map and use cases](../../reports/2026-11-20-workflow-map/USE-CASES.md): open points OP1–OP16, each measured against that day's runs;
- [operators and views](operators-and-views.md);
- the owner's notes of 20 November;
- a look through the owner's earlier harness, MARK XLVIII / JARVIS, for tools this system lacks. It was read on 20 November 2026 at commit `281dc41`.

## 0. Boundary: nothing depends on MARK XLVIII

The owner is retiring MARK XLVIII and may move or delete it. The Librarian takes no dependency on it, now or later:
- **No imports, no runtime calls, no shared files and no test fixtures** from it.
- **No path into it in code or in any document a person must follow.** Where this proposal names a MARK module, it is a historical source, not a location to visit.
- **Copy, never link.** Anything we reuse is copied into this repository with its tests, under a short header: "adapted from the owner's MARK XLVIII, `<module>`, commit `281dc41`, MIT, 2026". From then on it is ours to change, and it is tested here.
- **Designs are recorded here, in our own words** ([Appendix A](#appendix-a-the-designs-we-would-adopt)), so nothing is lost if the source goes.

## 1. What MARK XLVIII brings

MARK XLVIII was built to be run from Obsidian, and it solved several problems we are about to face. Each piece below was read in its code and in its own developer handbook. The code is the owner's own and MIT-licensed.

| Piece | What it does | Use here |
|---|---|---|
| `core/canvas_document.py` (206 lines, standard library only) | Parses and validates JSON Canvas 1.0. Keeps unknown fields and node types. Computes content revisions and proposal hashes. Never replaces a malformed canvas with an empty one. | **Lift.** The base for every canvas the Librarian writes |
| `core/canvas_layout.py` (375 lines, standard library only) | Deterministic, rectangle-aware layouts with profiles: `plan` (lanes), `tasks`, `dependency` (topological layers, cycle report), `evidence`, `relationship`. Nodes a person moved stay pinned. | **Lift.** Lays out the workflow map, plans and evidence chains |
| Safe canvas flow (`actions/jarvis_canvas.py`) | Inspect, then preview, then a base revision and proposal hash, then explicit confirmation. The write happens only if the revision still matches, after a backup, as an atomic commit, followed by a reindex. | **Adopt the flow.** It matches our stage-then-promote rule |
| `core/canvas_index.py` | Cross-canvas tables of files, nodes, edges and references: which canvases share a note | **Adapt.** It must sit behind our IndexService (INDEX-01: no new direct SQLite) |
| Canvas planning engine (`actions/canvas_plan.py`, 3,063 lines) | A canvas compiles into a workflow. Each node is both a step and its own prompt. Leading `key: value` lines are directives. A role maps to a step type, and an unknown role falls back to the least-privileged type. Approval is bound to a fingerprint of the human-authored content. It also has a critique-and-refine loop, branch fan-out, context inherited from sibling branches, and per-node deliverables as acceptance criteria. | **Adopt the design, not the code.** The code is tied to OpenClaw and MARK's model router. We compile into our own YAML workflows instead |
| `jarvis_dual_orchestrator/v1` step schema | Steps carry `depends_on`, `risk_tier`, `side_effects`, `requires_confirmation`, `retry_policy`, `acceptance_criteria`, `negative_constraints`, `compensation` and `on_failure`. Targets are a closed set generated from the capability schema. | **Adopt the fields our workflows lack:** dependencies (ours are linear plus `each`), side-effect class, acceptance criteria and compensation |
| `core/capability_schema.py` | One stable capability shape. The scattered lists of tools, roles and dispatch targets read from it instead of each keeping its own copy. | **The lesson for OP15/OP16.** Our registry already does this for tools, but phases and bundles still keep their own copies |
| Obsidian document contract (`Templates/JARVIS-Obsidian-Workflow-Templates/SCHEMA.md`) | Typed relation fields: `parent`, `depends_on`, `blocks`, `derived_from`, `supports`, `contradicts`, `related`, `supersedes`, `superseded_by`. Also permission and approval fields. | **Seed vocabulary** for typed relations (workstream 5) |
| Agent builder templates (START, agent, if/else, note, end) | Node types for drawing an agent workflow by hand | **Node vocabulary** for hand-drawn workflow canvases (workstream 2) |
| Vault change awareness (`core/vault_activity.py`) | A journal of external edits with structural diffs. A write receipt, registered before each write, separates the system's own changes from the owner's. The next turn gets bounded "what changed" context, labelled as having no authority. | **Input** to change-impact detection (workstream 3), beside our writer's log |
| Process trace (`core/process_events.py`) | A redacted operational event log, with a tool that answers what the system **did**, separate from what it **can** do | **Already partly ours** (activity and audit events). The did/can split is worth copying |

MARK's handbook also records the same bug classes we met on 20 November:
- A step that names no target succeeded silently; MARK now refuses it at compile time.
- A role silently ran on the wrong model route, like our `route_review`.
- Its principle is "targeting is a visible recommendation, never a silent default".
- Multi-branch model decomposition succeeded about 2 times in 6, which is why its validators refuse malformed plans instead of repairing them.

## 2. Workstreams, in order

Each workstream names what it closes, what it reuses, and how we will know it is done.

### W1. Workflows as data

**Closes:** OP6, OP15, OP16.

The modular action library the owner described exists: `workflows.py` runs YAML actions, workflows and pipelines. What remains:
1. Phases declare their exit gate, bundle and tail tools as data. `Session.missing` and `BUNDLES` read that data, instead of each phase living as `if p == ...` branches.
2. The 6 agent macros become YAML workflows. `macro_run` becomes running a workflow.
3. The workflow schema gains `depends_on` (a DAG, not only a sequence), a `side_effects` class, `acceptance_criteria` and an optional `compensation` step, after the dual-orchestrator schema.
4. A check that every tool a gate or a refusal names is offered in that phase (OP6), generated from the same data.

**Done when:**
- `scripts/workflow_map.py` reads the declarations directly instead of forcing sessions into phases;
- `phase_walk` reports no blocked phase;
- the macros run as workflows with unchanged tests.

### W2. Canvas service, and canvas ⇄ workflow

**Closes:** the owner's request to see and draw workflows.
1. Lift `canvas_document.py` and `canvas_layout.py`, with their tests, into `resource_librarian/canvas/`. All canvas writes go through preview, then a hash-checked commit, with a backup.
2. The workflow map writes its canvas with the `dependency` and `plan` layouts.
3. **Canvas → workflow.** A hand-drawn canvas, using the agent-builder node types and `key: value` directives, compiles into a YAML workflow:
   - unknown roles get the least privilege;
   - a node that names no target is refused at compile time;
   - approval is bound to the canvas fingerprint.
4. **Workflow → canvas.** Every shipped workflow and pipeline can be opened as a canvas.

**Done when:** one of the shipped workflows can be drawn by hand, compiled, approved and run, and the run matches the YAML original.

### W3. Change-impact detection

**Closes:** agenda item 5, and the operators-and-views proposal, section 3.

A pipeline over existing actions:
1. **What changed:** Geo's snapshot diff, the writer's log with write receipts, and original digests.
2. **Its blast radius:** `find_dependants`, documentary mentions, lineage and bridges.
3. **Run only the checks** whose subjects are in that radius.
4. **Flag** each finding, with the change that caused it.

B5's finding applies here: compare fingerprints by range, not item by item. It needs no model.

**Done when:** a one-function change reruns only the tests and claim checks that reach it, and a weekly full run finds nothing the targeted runs missed.

### W4. Published views, then the query surface

**Closes:** OP14, and the owner's points A–F.
1. Publish read-only, pre-computed views of what we already hold:
   - relational/ER (entities, attributes, keys);
   - document;
   - provenance (lineage);
   - temporal (snapshots).
2. The query surface is a validated, read-only spec compiled to SQL over those views, never model-written SQL. Start with restrict, project, join, semi-join, anti-join and group-by.

**Done when:** an agent can ask "papers in O1 and O5 with no Source note" (anti-join) and get a correct, bounded answer without free text.

### W5. Relations as checked claims, with trust tiers

**Closes:** OP10–OP12, and the owner's note on enrichment and relations.
1. **Propose.** Enrichment proposes candidate relations between items, many to many. They climb the ladder of granularity:
   - within a document: which section introduces, precedes or summarises another, mostly derived from the outline;
   - against our own material;
   - against outside material.

   Vector similarity proposes candidates; it never asserts a relation.
2. **Distil.** Merge duplicates and drop links made by common words.
3. **Check.** Each relation becomes a claim, "A relates to B as R", with evidence on both sides. It is verified by the same claim-review machinery as an offering's claim. The type R comes from the document contract's vocabulary plus code relations (calls, imports, implements).
4. **Score and tier.** Each relation gets a score on a range from its evidence and verdict. Declared thresholds map the score to gold, silver or bronze.
5. **Report placement.** A report's "where it lands in our code" becomes a claim citing a code entity, not summary prose (OP10).

**Done when:** doc-to-code links carry a type and a tier, and the word-match links fall out at the distil step.

### W6. Organisation workflow

**Closes:** OP2 and OP13.

A light YAML pipeline for reorganising folders:
1. Propose groups (by folder code, topic or cluster).
2. The person approves the plan.
3. A dry run.
4. Moves, each logged with an undo.
5. Re-survey only the touched folders.

It is paired with Geo-Grapher rebuilding only the groups a decision touches. That half is Geo-side work.

**Done when:**
- the DataManagement PDFs can be regrouped, with their Source notes and graph documents still resolving;
- an edit to `D:\Librarian_V2` no longer blocks a decision in another folder.

### W7. Research-session fixes

**Closes:** OP1, OP3–OP5, OP7–OP9.
- An enriched-but-unaccepted backlog shows on the agenda and in the Lead's context.
- A synthesis per brief, so a multi-question brief gives each report its own "Together" and "Unknowns".
- Research rounds stop surfacing folder cards and the library's own design notes as candidates for an outside-corpus brief.
- A phase's budget is counted per visit.
- Claim review on by default, on the library's review route, also inside the Core.
- The cause of the "unchecked" reviews found, now that they record their reason.

### W8. Topic filing, then the visuals

- **Topic filing.** A multi-label pass over the 363 Unfiled notes in Resource-Library. B4 shows a model's single-label answer is a draft, not a filing.
- **Visuals.** A link node (the "knot on the string") for many-to-many links carrying metadata, a time slider over snapshots, and heat cells in the Matrix.

## 3. Decisions for the owner

1. Accept the order W1 → W8, or reorder. W1 comes first because W2, W3 and W7 each get cheaper once phases are data.
2. Copying MARK's two canvas modules into the Librarian (W2). They are standard library only and MIT-licensed. They would be copied with their tests under the boundary in section 0, ideally before the repo is moved, though a move to another disk changes nothing but where we copy from.
3. Making claim review default-on in every library (W7). It costs one Clerk call per claim.

## Appendix A. The designs we would adopt

Recorded so that this proposal stands without the MARK repo.

**Safe canvas writes.**
1. Parse the canvas without loss: unknown fields and node types survive, and a malformed file is reported, never replaced by an empty one.
2. Preview the change. The preview returns the geometry before and after, a base revision (a hash of the current content) and a proposal hash.
3. A person confirms.
4. Commit only if the revision and the proposal both still match. Otherwise the change is a conflict, and a new preview is needed.
5. Write a unique backup, then an atomic replace, then reindex.

**Positions a person set are kept.**
- Nodes outside the system's own ID prefix, unknown node types and explicitly pinned nodes are never moved.
- A committed layout stores its geometry. A managed node whose position later differs from that record was moved by a person, and is pinned from then on.

**Layout profiles.**
- `plan`: left-to-right lanes: source, plan, action, review, blocked, complete.
- `tasks`: status lanes with bounded grids.
- `dependency`: top-to-bottom topological layers, with cycles reported.
- `evidence`: the dependency layout, for lineage.
- `relationship`: a stable clustered grid.

New nodes are placed near an anchor and moved until nothing overlaps. Default edge labels such as "next" are hidden.

**A canvas compiles to a workflow.** Every node is at once a workflow step and the complete instruction for whoever runs it.
- **Directives.** Leading `key: value` lines on a node are directives (`role`, `target`, `scope`, `depends_on`, `branch`, `deliverables`, a recommended model). The first line that is not a directive starts the instruction.
- **Roles.** A role maps to a step type through a fixed table. An absent or unknown role becomes the least-privileged step (read-only reasoning), so a canvas can never create a step with side effects by accident.
- **Refused at compile time:**
  - a step with side effects that names no target;
  - a cycle;
  - an unknown target;
  - a missing anchor (exactly one workflow node is required).
- **Approval** is bound to a fingerprint of the human-authored content. Any edit re-opens approval, and a recommendation left unedited counts as accepted.
- **Critique before approval.** A second pass judges the whole plan (approve, caution, re-review, reject). A deterministic check also escalates ordering errors, such as a verification wired before the step it verifies. Re-review loops a bounded number of times; caution and reject bring the person in.
- **Branches** group independent parts into columns. Each node receives a short, deterministic preamble: the goal, its branch's purpose, and one line per sibling branch. Declared deliverables become that node's acceptance criteria.

**Step fields our workflow schema lacks.**
- `depends_on`, which makes a DAG rather than a sequence;
- `risk_tier`;
- `side_effects` (none, local read, local write, external write);
- `requires_confirmation`;
- `retry_policy`;
- `acceptance_criteria`;
- `negative_constraints`;
- `compensation` (a registered undo);
- `on_failure`.

**Typed relations, from MARK's note contract.**
- `parent`, `depends_on`, `blocks`;
- `derived_from`, `supports`, `contradicts`, `related`;
- `supersedes`, `superseded_by`.

**Change awareness.**
- A write receipt (the expected content hash) is recorded before each system write. A later file event that matches it is the system's own change; anything else is the person's. When unsure, the edit is treated as the person's, so it is never hidden.
- The next turn gets a bounded list of what changed (8 events, 1,800 characters), marked as reference with no authority, and is acknowledged once used.
