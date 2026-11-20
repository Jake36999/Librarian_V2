# Operators and views across data models

**Status:** proposal (rank 5 in `docs/policy/README.md`). Owner direction, 2026-11-20. Follows
`reports/2026-11-20-operators/OPERATORS-AND-DATA-MODELS.md`, which assessed what exists.

The stores are relational, so relational algebra is valid by definition. But we also want to read
the same rows as a graph, a hierarchy, a star schema, a lineage, a timeline or a set of
documents. This page defines **one general set of operators** with a precise meaning in each
model, so an operator means the same thing whichever view an agent or a person is in.

## 1. The common ground: everything is a set of typed records

Every view reduces to:
- **items**: an entity, a note, a claim, a model call or a snapshot, each with a **key**, a
  **type**, **attributes** and **provenance** (`cite_as`, authorship, trust tier);
- **links** between items: a relationship, a containment, a wikilink, a derivation, a declared
  bridge or an incidence, each with a **type**, a **direction** and attributes of its own.

A link is itself an item with a key. That is what lets many-to-many relationships and
hyperedges carry metadata (section 5).

An **operator** takes one or more item sets (plus the links between them) and returns an item set.
Every result row keeps its `cite_as`; no operator invents an item.

## 2. The general operators

### 2.1 The six you named, and their cross-model meaning

| Operator | General definition | Relational | Graph | Document (notes) | Dimensional | Provenance | Temporal |
|---|---|---|---|---|---|---|---|
| **Restrict** (σ) | Keep the items that satisfy a predicate on their attributes | `WHERE` | node/edge filter | frontmatter filter | **slice** (one dimension value) and **dice** (several) | activities or entities of a kind | items valid in a window |
| **Project** (π) | Keep chosen attributes; drop duplicates that result | `SELECT cols` | node fields | chosen fields or sections | choose measures and dimensions | choose the lineage fields | — |
| **Join** (⋈) | Pair items whose keys, or a link between them, match | `JOIN ON` | follow one edge type (one hop) | wikilink resolution | fact ⋈ dimension | `wasDerivedFrom` / `wasGeneratedBy` | join *as of* a time |
| **Product** (×) | Every pairing | `CROSS JOIN` | — | — | — | — | — |
| **Difference** (−) | Items in A not in B, by key | `EXCEPT` | graph difference | notes in A, not B | — | — | **what changed between two times** |
| **Intersection** (∩) | Items in both, by key | `INTERSECT` | common subgraph | shared notes | — | common ancestors | unchanged between two times |

Product stays out of the user-facing set: a join with no condition covers the rare real case.

### 2.2 Operators you did not list that we need

**Set and shape**

| Operator | Definition | Why we need it |
|---|---|---|
| **Union** (∪) | Items in either, by key | Federated search across graphs, as a real set |
| **Rename** (ρ) | Give an attribute or set another name | Join a graph and a note set without name clashes |
| **Extend** | Add a computed attribute (`pages = end - start`) | Report columns, scores |
| **Distinct** | Remove duplicate keys | After projections and unions |
| **Order / top-k / sample** | Sort, keep the first k, sample n with a seed | Ranked results, reproducible audits |
| **Nest / unnest** | Group a list into one item, or spread a list into items | Multivalued attributes (`aliases`, `secondary_topics`) |
| **Coalesce / sentinel** | Fill a missing attribute with an explicit `n/a`, never a guess | Forms and reports; the research run found sentinels stop fabrication |

**Aggregation and analysis**

| Operator | Definition | Why we need it |
|---|---|---|
| **Group and aggregate** (γ) | Count, sum, min, max, mean or distinct-count per group | Every report and matrix |
| **Pivot / unpivot** | Turn values into columns, or back | Objective × source matrices |
| **Roll-up / drill-down** | Move up or down a dimension's hierarchy (paper → topic → domain; file → folder → repository) | Dimensional views, and the globes |
| **Window** | Aggregate over neighbouring rows (running totals, previous version) | Spend over time, drift |

**Join variants**

| Operator | Definition | Why we need it |
|---|---|---|
| **Semi-join** (⋉) | Items of A that have a match in B, keeping only A's attributes | "Documents that mention any function in file X" |
| **Anti-join** (▷) | Items of A with no match in B | Gaps: sources with no topic, code with no docs |
| **Outer join** | Keep unmatched items with `n/a` | Coverage tables |
| **Division** (÷) | Items of A related to *every* item of B | "Papers covering all of O1, O4 and O5" |
| **Theta join** | Join on a condition other than equality | Overlapping page ranges, nearby lines |

**Graph and lineage**

| Operator | Definition | Why we need it |
|---|---|---|
| **Traverse / k-hop** | Items reachable in up to k steps over chosen link types | Context, dependants |
| **Transitive closure** | Everything reachable | Impact (blast radius, section 3), lineage |
| **Path** | One or all paths between two items, with their links | "How is this claim connected to that function?" |
| **Pattern match** | Subgraphs that fit a small template | "A function, documented, tested, called by a third-party repo" |
| **Neighbourhood aggregate** | Group and aggregate over each item's neighbours | Degree, fan-in hubs (the homonym noise Gemini's audit found) |
| **Lineage / impact** | Walk derivation links backwards (what produced this) or forwards (what depends on this) | Provenance view, integrity |

**Time**

| Operator | Definition | Why we need it |
|---|---|---|
| **As-of** | The items as they were at time or snapshot t | Reproducible reports |
| **Diff(t1, t2)** | Added, removed and changed items between two times | Drift, change detection |
| **Interval join** | Join on overlapping validity | Facts true at the same time |

**Constraints and events**

| Operator | Definition | Why we need it |
|---|---|---|
| **Assertion** | A saved query that must return no items; its result is the violations | Integrity rules |
| **Trigger** | An event (after batch, accept, survey, snapshot) that runs a named assertion or workflow | Monitoring without asking |
| **Insert / update / delete** | Unchanged: person- or policy-gated writes through staging; graph facts stay derived from their sources; declared links are a person's insert | — |

### 2.3 How agents get them

As one **read-only, structured query** per system (a validated spec, not raw SQL), compiled to SQL
over published views and checked before it runs. Each operator above is a field or a step of that
spec. The research run is why it should not be free text: 2 of 5 first-pass agent SPARQL queries
had structural bugs and needed a deterministic validator (O6).

## 3. Smart detection: check the blast radius of a change, not everything

The owner's question was whether a smart detection tool beats running every check on a schedule.
**Yes**, and the parts exist. It is the trigger, transitive-closure and assertion operators above,
put together:

1. **What changed.**
   - Code and documents: Geo's snapshot diff (`diff-graphs`, `drift-report`) and the folder
     fingerprints the survey already computes.
   - Library records: staging and note writes (the writer's log lists the targets of every write).
   - Originals: the digests recorded at reading.
2. **What depends on it.** Transitive closure over the right links:
   - code: Geo's `find_dependants` over calls, imports and reads;
   - prose about the code: `documentary_incidences`;
   - library records: the provenance lineage (original → conversion → reading → claim → note →
     offering);
   - other graphs: declared bridges.

   Through ASTs the Geo side already knows which function changed, not only which file.
3. **What to run.** Only the assertions and tests whose subjects fall in that set:
   - a changed function reruns the tests that reach it (Geo knows test entities: `is_test`);
   - a changed original re-checks the claims cited from it;
   - a re-read source re-checks the offerings that cite it.
4. **Flags.** Each violation becomes a flag on the item, with the change that caused it.

It costs no model calls, it scales with the size of the change, and it replaces "run everything
nightly". A full run stays as a weekly backstop.

## 4. Which views the current visuals can show

The ball-and-thread vocabulary (globes for containment, coloured threads with direction, node
colour, the Matrix and List views) covers more than it first seems.

| Model | Fits today? | How it maps | What would be new |
|---|---|---|---|
| Hierarchical | **Yes** | Globes inside globes | — |
| Graph / network | **Yes** | Threads | — |
| Relational / ER | **Mostly** | Entity types as node colour, relationships as threads; the Matrix shows one relation as a grid | Keys and attribute lists in Inspect |
| Object-oriented (is-a) | **Partly** | Containment already means part-of. Showing is-a the same way would conflate the two | A second nesting style (outline globes, or a toggle between part-of and is-a) |
| Provenance (lineage) | **Partly** | Directional fading threads already show direction | A layered left-to-right layout for derivation chains |
| Many-to-many with metadata | **Partly** | A thread per pair works until hubs appear. Gemini's audit found 918 edges on one symbol | A **link node** (a small knot or bead on the thread) that carries the metadata and bundles the pairs, i.e. a hyperedge |
| Dimensional (star) | **Hard** | Aggregates are numbers, not objects; the Matrix is the nearest thing | Pivot tables, heat cells in the Matrix, and globe size or colour driven by a measure |
| Temporal | **Hardest** | Nothing shows time | A time slider over snapshots; ghosted items that disappeared; threads that fade in when they first appear |
| Triples / semantic claims | **Partly** | Threads | Predicate labels on threads; a lot of label clutter to manage |

**Semiotic view.** The owner wants to move from symbols (code entities) to signs (what a node
*means* in a domain). In visual terms, the same item can carry different **signifiers** per view:
- **colour** for its domain or topic, which needs topics filled in (C6–C9);
- **shape** for its type;
- **size** for a measure;
- **halo** for its integrity flags;
- **thread style** for the kind of link (derivation, mention, call, declared).

The investigator's pinboard is the right picture: pins (items), string (links), notes pinned to
string (link nodes with metadata), and colour-coded cards (types). Most of it is already built.
What's missing is the knot on the string, the time axis and the measures.
