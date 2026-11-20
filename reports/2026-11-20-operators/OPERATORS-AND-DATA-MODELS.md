# Operators and data models for the Librarian and Geo-Grapher (2026-11-20)

The owner's six points (A–F) on database theory, checked against what the two systems store and
offer today, plus what the ACCEPT-02 research run (`dm_equal_objectives_o1_o9_final_report.md`)
found that bears on them.

Evidence tags:
- *measured*: read from the stores or the tool registries.
- *read*: from the code.
- *research*: from the Gemini report; its own tags apply (`corpus`, `outside [verified]`).
- *proposal*: a recommendation, nothing built yet.

## 0. Is it a NoSQL database?

Mostly no, and that helps. *measured*

| Store | What it is | What it holds |
|---|---|---|
| Geo graph store (`code.sqlite`, one per graph) | relational, SQLite | 15 tables, centred on `entities` and `relationships` (a property graph), plus JSON documents in `analysis_results` |
| Geo catalogue (`catalog.sqlite`) | relational, SQLite | graphs, bridges, bridge proposals, merge receipts, the revision ledger |
| Librarian index (`derived/index.sqlite`) | relational, SQLite with FTS5 | note, chunk, link, facet, document, embedding |
| The vault | document store | Markdown notes with YAML frontmatter; staging records as JSON files |

So it is **multi-model**: a graph model and a document model, stored relationally. Your instinct
that we could apply several schemas over the same data is the textbook case for it. The rows
already exist; what is missing is a declared set of views and a query surface over them.

The research run says the same of NoSQL in general: "there is not yet a consensus on the adoption
of a standard to model NoSQL databases" (O6, `Data Modeling and NoSQL Databases.pdf` [p. 23],
*research*, `corpus`, L1). Schema-less storage does not remove the need to model the data.

## A. ANSI-SPARC: three levels

| Level | In our systems today | Gap |
|---|---|---|
| **Internal** (storage) | SQLite stores, snapshot sets, conversions, original files, run logs | — |
| **Conceptual** (one logical model) | Two models: Geo's entity/relationship model, and the Librarian's note content model (`About/Note Content Model.md`, its axes and fields). They share keys only informally: file paths, `cite_as`, declared bridges | No single conceptual schema covers both, and nothing is written down as one |
| **External** (user views) | Geo 3D/List/Matrix; the MCP flat tools; Obsidian notes; Staging; Search | Views are hand-built per screen, not derived from the conceptual schema |

Your sub-categories for external information map to our **strata**: authorship (owner_created /
generated / third_party), trust tier (gold / silver / bronze) and modality. They are a fourth
axis ANSI-SPARC does not have. **Proposal:** treat them as standard view filters at the
external level, for example "only gold, owner-created code".

**Data independence today.** Physical independence is good: the compact in-memory form changed
storage use without changing any frame (byte-identical, *measured* 2026-11-17). Logical
independence is weak: a tool's output shape is its storage shape.

## B. Entity–relationship concepts: what exists

| Concept | Geo-Grapher | Librarian | Gap |
|---|---|---|---|
| Application domain | — | `topic`: "Unfiled" on every read item in three libraries (*measured* today) | **Missing.** O1 is exactly this problem (below) |
| Entity | `entities` row | note, staged item | — |
| Entity type | `kind` (fragment, document, function, class, directory…) | note `type`/`kind` (source/document, concept…) | Kinds are an implicit list, never declared as a type system |
| Attribute | columns (`language`, `rel_path`, `is_test`…) and JSON analyses | frontmatter fields | — |
| Domain (allowed values) | none declared | `axes_for(shape)`: permitted values per field (*read*) | Geo has no attribute domains |
| Relationship | `relationships`: `family`, `subtype`, `direction`, `resolution_status`, `confidence` | `link` (wikilinks); declared links | — |
| Multivalued attribute | `ancestors`, analyses | `aliases`, `secondary_topics` | — |
| Time-varying attribute | snapshots (a version per build) | `captured_at`, revisions, staged revisions | No valid-time on facts, and no "as of" queries |
| Generalisation | containment tree (`parent_id`); helper-tree contraction (which does nothing on 31 of 33 graphs, per Gemini's audit) | topics (flat) | No declared is-a hierarchy for kinds or topics |
| Primary key | `entity_id`: a content hash, itself prefixed `entity:` | note `name` (unique) | — |
| Composite key | `(snapshot_id, entity_id)`, `(snapshot_id, relationship_id)` | — | — |
| Foreign key | `parent_id`; `source_id`/`target_id`; `snapshot_id` | `link.dst` → note name | Wikilink resolution failed 97–100% for workspace documents (Gemini audit, not re-checked) |
| Candidate key | `(repo_id, qualified_name, kind)` and `(repo_id, rel_path, start_line)` are both indexed | `canonical_url`, DOI, file digest | Not declared as keys, so they are not used to find the same thing across libraries or graphs |

**Verdict.** The raw material for a proper ER model is all there. What's missing is (1) declared
domains and types on the Geo side, (2) application domains (topics) actually filled in, and (3)
candidate keys used deliberately.

## C. Relational algebra and SQL: coverage

| Operator | What exists | Assessment |
|---|---|---|
| **Restrict** (σ) | `search_entities(query, kinds)`, `search(query, constraints)`, Geo prune/derive by path | Partial: text and kind only. No predicates on attributes such as `is_test`, `language`, `depth`, `year` or `topic` |
| **Project** (π) | none; every tool returns a fixed shape | Missing |
| **Join** (⋈) | traversal: `find_dependants`, `get_architecture_context`, `paper_get_related`; across graphs `list_bridges` | Partial: fixed paths only. No ad hoc join, for example "documents that mention functions in file X" (`documentary_incidences` holds it) or Librarian claims ⋈ Geo entities |
| **Product** (×) | none | Not worth adding: a join with no predicate covers the rare useful case |
| **Union** (∪) | `federated_search`; the display composition | Partial: results are ranked separately and never set-combined |
| **Difference** (−) and **Intersection** (∩) | Compare (code fingerprints only); `diff-graphs` and `drift-report` (CLI only); `analyze_cross_graphs` | Partial: code-only, and not over arbitrary result sets |
| **Aggregation** (count, group by) | summary counts only | Missing, and it is what reports need |
| **Assertions** | `check_architecture` (Geo rules); `check_notes`, `provenance_check`, `freshness_check`, `verify_source_pages` | Present but scattered, each with its own shape |
| **Triggers** | the file watcher reindexes; workflows run when started | No event → rule → action mechanism |
| **Insert / update / delete** | Librarian: `write_note`, `edit_note`, `note_move`, `archive_note`, `staging_decide` (person- or policy-gated). Geo: graphs are derived (rebuilt from source); a person inserts and deletes declared links, and can prune, copy or delete graphs | Right as it is. Graph facts should change only when their source changes |

**Proposal: one read-only query operator in each system, not raw SQL.**
- **Shape:** a structured query spec. `from` a published view; `where` predicates;
  `select` fields; `join` along a named relationship, incidence or bridge;
  `union`/`intersect`/`except` on result sets by key; `group by` with counts; `order` and `limit`.
- **Execution:** compiled to SQL over **published read-only views** (the external level, A), and
  validated before it runs.
- **Provenance:** every row carries `cite_as`.
- **Why not free text:**
  - an agent writing SQL or SPARQL directly gets the structure wrong often: 2 of 5 first-pass
    agent SPARQL queries had structural bugs and needed a deterministic validator (O6,
    `DSN-S 2025` [pp. 1–2], *research*);
  - the strongest pattern in the corpus compiles queries ahead of time with a model and runs
    them deterministically, and all 5 of its translated queries matched exactly (O6,
    `Leveraging Diverse Software Components with LLMs.pdf` [p. 3], *research*, `corpus`).

  A structured spec gives agents restrict, project and join without that failure mode.
- **Graph facts stay derived:** an "insert" is a declared link or a staged item, as today.
- **Assertions** become saved queries that must return no rows.
- **Triggers** become workflows the Core runs on named events (after a batch, after an accept,
  after a survey), using the existing workflow engine.

## D. Automated forms and reports, model-free

| Part | Proposal |
|---|---|
| Database engine | The existing SQLite stores, plus the published views from A |
| Query system | The structured query operator from C |
| Report generation | Saved queries plus Markdown or table templates, rendered into notes as `views_refresh` already does for topic indexes, and as tables in the UI. A model is optional and only for a narrative paragraph, with RAG over the rows the query returned |
| Forms generator | Forms generated from the content model's fields and domains. The Staging accept form already does part of this. Absent attributes get an explicit "n/a", never an invented value: harmonisation agents stopped fabricating once missing keys got a sentinel (O6, `LLM-based harmonized data ingestion for dataspace.pdf` [pp. 8–11], *research*, `corpus`) |

**A worked example.** The research run's closing table (objective × papers × evidence × limits ×
cost) was assembled by hand from nine reports. As a group-by over readings joined to sources and
topics, the counting and structure would be deterministic, cost nothing, and be reproducible.
A model would still write the narrative columns.

## E. Monitoring integrity and raising flags

The checks exist, but they are scattered and run only on request. **Proposal:** express each as
an assertion (C), run the set after each batch and accept and on a schedule, and show violations
as flags in Health and Staging.

What a first set would have caught this week (*measured* 2026-11-19 and 2026-11-20):

| Rule | Found |
|---|---|
| A read Source's original still matches its digest | 3 Resource-Library documents edited since reading |
| A graph entity belongs to one graph's roots | 19 README files that both the data and docs graphs claim |
| Every read part of a PDF has a page locator | 1 failure in Nonlinear |
| A read item has a topic | 0 of 1,286 in Nonlinear, Resource-Library and Parallax |
| A title is not just the file name | about 98% are |
| A sampled point is found in the original at its locator | 98–100% pass; misses are mostly maths-heavy text |
| No draft is left not-confident, unretried | 104 drafts from before the retry existed |

`reports/2026-11-16-pilot-review/run-scripts/validate_library.py` already runs most of these
read-only. Promoting it to a product tool is the cheapest first step.

## F. Other models: useful views of data we already have?

| Model | Useful? | Needs new data? | Note |
|---|---|---|---|
| **Relational / ER view** | Yes, the base for C–E | No | Views over the existing tables |
| **Dimensional (star schema)** | **Yes, high value** | No | Facts: claims, points, limits, uses, model calls. Dimensions: source, topic or objective, time, authorship, trust tier, model. Gives report matrices, spend per objective and coverage per topic for free |
| **Provenance (W3C PROV: entity, activity, agent)** | **Yes, high value** | Mostly no | The lineage is already recorded: original → conversion → reading → claim → note, with models and persons as agents (usage logs, run logs, evidence ids). It answers "what produced this, and what depends on it" |
| **Temporal / bitemporal** | Yes, medium | No | Snapshots and `captured_at` support "as of" and drift queries |
| **Network / graph** | Already the core | — | Parent/child is the network model's owner–member set |
| **Hierarchical** | Already the globes | — | Folders |
| **Object-oriented** | Medium | No | Kinds as an is-a hierarchy (`function` is-a `code entity` is-a `entity`) would let a restrict on a supertype work |
| **Multilayer network** (O2) | Keep layers apart | No | Merging layers often cannot be reduced: 0 reducible layers on 8 of 13 BioGRID species and others (O2, `1405.0425` [pp. 4–5], *research*). This supports keeping graphs separate and composing them only for display |
| **Triples / RDF over claims** | Low for now | **Yes** | Claims are prose; making triples means a new extraction pass. Automatic equivalence is dangerous: 2.8–21% of `owl:sameAs` links are wrong, and transitive closure merged 177,794 IRIs into one class (O5, *research*, `outside [verified]`). Bridges must stay scoped assertions, as Geo's declared links already are |

## Research takeaways that bear on this work

1. **Bridges stay non-merging assertions.** Name and embedding signals beat graph neural
   networks for alignment across mixed graphs. Cheap CPU methods (PARIS, BERT + whitening + CSLS)
   reach 0.55–0.87 Hits@1 (O5, `2304.03468` [Table 2], *research*, `outside [verified]`). This is
   a model-free first pass for bridge proposals. O5 also designed and costed a 60-pair test
   (about $0.03, not run).
2. **For a model, send a budget-bounded subgraph, not the whole graph.** Prize-collecting
   Steiner tree extraction cut one benchmark's prompts from 100,627 to 610 tokens (O4,
   `2402.07630` [Table 4], *research*). Grouping each node's neighbours beat flat edge lists
   (53.8% against 19.8% on connected-node questions, O4, `2310.04560`). Our `compile_task_packet`
   should follow both.
3. **Offload exact graph computation to code or queries, not the model.** Hallucination on
   large graphs fell from 61.1% to 31.4% when the model wrote code instead (O4, `2407.00379`
   [Table 3]). This is the case for the query operator.
4. **Soft domain classification by a model alone is weak.** Zero-shot classification on large
   taxonomies reached 0.01–0.07 precision (O1, `2405.05136` [p. 6], *research*). Filling topics
   should use a small taxonomy plus the Clerk with evidence, not open-ended labels. That suits
   the pending C6–C9 metadata pass.
5. **The research itself is "mid", as you expected.**
   - The comparison table is careful about provenance and negative results.
   - Most objectives are `corpus-limited` and lean on outside papers.
   - Nothing was run: every "cheapest test" is designed and costed only.
   - Its Level-1 and Level-2 analysis was done by the agent's own sub-agents reading extracted
     text, not from the Librarian's readings.

## Suggested order (proposal)

1. **Published read-only views plus the structured query operator** (restrict, project, join,
   set operations, group by), in both systems, with `cite_as` on every row.
2. **Integrity assertions:** `validate_library` as a product tool, run after batches, with flags
   in Health.
3. **Dimensional reports:** objective or topic × source × evidence matrices, model-free, rendered
   into notes.
4. **Provenance view:** lineage queries over the records we already keep.
5. **Then the metadata pass (C6–C9)**, using a declared topic taxonomy (point 4 above).
