# Research objectives: one equal set (2026-11-18)

Merges (a) Antigravity's categorized plan (Tracks A-F) and (b) the domain-assignment and
weighting notes from the Claude review of `E:\DataManagement`. Nothing here has been
executed. `E:\DataManagement` was only read; no model, vault or config changes came from this file.

## Why the two inputs were rebalanced

| Source of tilt | What it did | Correction here |
|---|---|---|
| Antigravity plan | Tracks A-C "Priority 1", D "Priority 2", E "selective"; the MoE and weighting papers sat in the last track | No priority labels. Every objective gets the same budget, depth, template and reporting slot |
| Antigravity plan | One success test, "strengthens Geo-Grapher", framed the whole plan | Geo-Grapher's invariants become a **shared constraint filter** applied to every objective, not the lens of three of them |
| Antigravity plan | Deferred books and the 6 off-domain papers to save budget | Off-domain papers are the negative class for domain classification (O1). They get **title and abstract level** reading for all objectives, same as everything else |
| Claude notes | Built around the owner's weighting question | That question is one objective (O2) among nine, and O9 holds the expensive route on the same terms as the cheap ones |
| Both | Read depth differed by paper (abstract-only vs full) | One fixed depth rule (below) |

## Shared constraints (a filter on every objective, not a goal)

A transformation or method only counts as **viable** for a library if it respects all of:
1. **Boundary and provenance**: `owner_created` / `third_party` / `generated` stay separable; every claim carries a `cite_as` handle.
2. **Determinism**: the same input gives the same graph or ranking, or the nondeterminism is named and bounded.
3. **Token and cost budget**: delivery stays inside packing budgets; spend stays inside the library ceiling.
4. **Model access**: works through hosted APIs (tier 0-2 and the helper tiers), or says plainly that it needs model internals and what access.

A finding of "not viable under these constraints" is a valid, reportable outcome for any objective.

## The objectives

Each is investigated with the **same template** (Question, Claim to test, Evidence needed,
Negative outcome that would count, Cheapest empirical test).

### O1. Domain assignment and classification
- **Question**: how can nodes and documents be given domain membership (soft, multi-label) reliably and auditably?
- **Methods in scope**: ontology and rule alignment, embedding similarity, graph community detection, LLM-assisted enrichment, zero-shot KG classification.
- **Needs**: a hand-labelled set (about 6-8 domains) taken from this corpus, including off-domain papers as negatives, and a classifier audited against it.
- **Provisional corpus fit**: metadata-enrichment, harmonized-ingestion, zero-shot KG, SciKG survey, interdomain-rule, latent-variable matching papers.

### O2. Multi-layer weighting and clustering
- **Question**: how should nodes be weighted per domain layer and clustered across layers?
- **Candidate form to test, not assume**: per-layer weight = membership x within-layer centrality x source quality, with retraction and `third_party` flags.
- **Also**: pruning noisy nodes in large graphs, statistical dependency models (network and spatial autoregression, latent Markov, score matching) as method sources.

### O3. Query-time routing and retrieval granularity (system-level expert routing)
- **Question**: can a router over graph layers, retrieval granularity and helper tiers, with models as black boxes, deliver the benefit usually attributed to mixture-of-experts?
- **Provisional corpus fit**: the MoE-KG-RAG paper, NL-to-graph-query work, uncertainty-aware composition.

### O4. Graph-to-text linearization and token-budgeted delivery
- **Question**: which conversions between graph structure and bounded text or embeddings lose the least structure?
- **Provisional corpus fit**: MoE-KG-RAG linearization, large-KG subgraph extraction, compressed multi-encoder embeddings, Text-to-Cypher.

### O5. Cross-graph alignment and bridge scoring
- **Question**: which entity and relation alignment methods score candidate bridges well without turning bridges into automatic equivalence?
- **Provisional corpus fit**: KRL_Match, PWGM, probabilistic many-to-many matching, X-NeSyL, KGGCN.

### O6. Schema, ETL, metadata enrichment and drift safeguards
- **Question**: which LLM-assisted schema and enrichment patterns cut manual maintenance without hallucinated fields or silent drift?
- **Provisional corpus fit**: the 3-stage enrichment paper, ETL review, RDB-to-document migration, NL-to-schema, cross-model query translation, JSON vs XML serialization.

### O7. Storage, indexing, join factorization and deterministic sync
- **Question**: which storage, index, join and linearization techniques support incremental, content-addressed graph stores?
- **Provisional corpus fit**: many-to-many join papers, GraphMap, vector-index cost models, Z-curve and R*-tree, NoSQL engineering papers.

### O8. Orchestration, telemetry contracts, uncertainty and evaluation rigor
- **Question**: which schema-contract, scheduling, uncertainty-propagation and evaluation-validity patterns transfer to multi-tier agent pipelines?
- **Provisional corpus fit**: YANG/NETCONF telemetry, Petri-net scaling, epoch scheduling, WoT composition, dynamic-capabilities and cross-sectional-research methodology.

### O9. Model-level mechanisms
- **Question**: do open MoE models specialise experts by domain on this material, and would adapters or fine-tuning plus an asynchronous graph-and-transformer arrangement beat O1-O3?
- **Same rules as the others**: a desk study plus the cheapest empirical test designed and costed (here, per-domain expert-activation recording on an open MoE). **No GPU is rented and nothing is trained in this phase**, exactly as no other objective runs its empirical test yet.
- **Provisional corpus fit**: the two MoE gating and expert-extraction papers (**corpus-thin**; flagged below).

## Equal-treatment protocol

1. **Same depth rule**: every assigned paper gets Level 1 (abstract, introduction, conclusion). A fixed K per objective gets Level 2 (methods and results), where K = the smallest assignment count across objectives, capped at 5. Level-2 papers are chosen by a written rubric applied blind to which objective is favoured; ties break alphabetically.
2. **Same budget share**: $1.00 per objective (owner, 2026-11-18), plus a shared reserve of $1.00 for labelling and verification, so the library ceiling is $10.00. This is an allocation rule, not a cost estimate: the `intake_run(limit=3)` pilot sets real per-paper cost first, and every objective is held to the same $1.00 cap.
3. **Same order and truncation**: objectives run in parallel. If budget runs short, **all** objectives are cut to the same depth, never the later ones.
4. **Assignment by rubric, then audited**: papers get a primary objective plus optional secondary tags; a sample of assignments is checked against the labelled set, as any classifier would be.
5. **Same evidence floor**: each objective aims for the same minimum number of independent sources (proposed 8). Where the corpus has fewer, it is **flagged corpus-limited**, and may be topped up from outside literature tagged `external`, rather than reported on less evidence.
6. **Same exclusions, applied uniformly**: the 2 retracted papers (and their duplicates) give zero claims. Papers read by Antigravity without a text layer carry the marker "read by Antigravity, not Librarian-converted" and give no claims until verified.
7. **Evidence tags**: each claim is `corpus` (cited), or `outside` tagged verified, plausible or unverified. Corpus claims are third-party assertions, not facts. An empty search is not evidence of absence, because this corpus was hand-collected and is skewed toward databases and networking.

## Same report for every objective

Fixed sections, fixed order, same length cap:
1. Question and claim tested.
2. Sources: counts by read level, with corpus-limited flag.
3. Findings, each with `cite_as`.
4. What did not work or is not viable (a required section, may say "none found").
5. Fit against the four shared constraints.
6. Cheapest empirical test, with a cost estimate, not run.
7. What would change the conclusion.

A single comparison table closes the set: one row per objective, identical columns (sources, evidence strength, negative findings, constraint fit, test cost). Rows appear in numeric order, no ranking and no priority column.

## Provisional corpus coverage (to be confirmed by the assignment rubric)

Rough counts from Antigravity's file groupings and the Claude abstract pass: O6, O7, O8 are
well covered (about 10-13 papers each); O1, O2, O5 have about 6-10; **O3, O4 and O9 are thin
(about 2-6)**. Thin coverage is reported as thin. It is not padded with weakly related papers,
and not treated as a reason to rank the objective lower.

## Owner gates carried over from Antigravity's plan (unchanged by this file)

Model bindings and qualification, the `purpose` field on the attached root, session write
approval, and the extensionless PDF. No paid call (`intake_run`, `delegate`, `dispatch_plan`)
runs before the owner accepts this set.

## Decisions for the owner

1. Are nine objectives the right set, or should any be split or merged?
2. ~~Equal budget split~~ **Settled by the owner: $1.00 per objective, $10.00 ceiling including a $1.00 shared reserve.**
3. May thin objectives (O3, O4, O9) be topped up from outside literature, tagged `external`?
