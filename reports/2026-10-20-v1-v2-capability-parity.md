# Resource Library → Librarian V2 capability parity

**Purpose:** distinguish what V2 has genuinely carried forward from what is changed, hidden, partial or absent. This is an implementation-and-documentation review, not a request to migrate data or modify either product.

## Verdict

V2 retains the original Resource Library's research method and generally makes it more coherent. It is not yet a complete operational successor: legacy migration is hidden, graph/extraction services are absent, use-learning is non-operational, and the source-engagement workbench is only partially represented.

| Original capability | V2 status | Assessment |
|---|---|---|
| Markdown as source of truth; evidence/information/knowledge separation | **Stronger** | V2 retains editable Markdown/YAML while placing durable captured material in content-addressed `.evidence/`. |
| Typed catalogue, taxonomy, indexes | **Stronger/generalised** | Sources cover repositories, papers, datasets, documents, pages, standards and models; topics, concepts and generated views remain. |
| Constraint-led retrieval, explanation, coverage | **Stronger** | Search keeps constraints, non-generative reads, ranking explanations, caveats and coverage verdicts. |
| Semantic/hybrid retrieval, scenarios and evaluation | **Carried forward** | Lexical/hybrid comparison, vault questions/scenarios and non-mutating candidate evaluation remain available. |
| Surveys, components, access points | **Carried forward/expanded** | Evidence, DIK, structural survey, data-grain search and verified access points replace the older component-store surface. |
| Intake, papers, web fetch and scouting | **Stronger/unified** | GitHub, arXiv, DOI/Crossref, files/PDFs, pages, datasets, OpenAlex/web search, staging, deep read and promotion are consolidated. |
| Staging, provenance, freshness and duplicates | **Carried forward** | Explicit staging plus provenance, freshness and duplicate reports retain the principle of reporting rather than silently editing. |
| Offerings and application records | **Stronger** | They connect to reopenable sessions, projects, evidence quotes, phases and permission modes. |
| CLI/MCP/chat model access | **Stronger** | One registry/policy layer replaces the V1 risk of parallel command surfaces drifting. |
| Obsidian use | **Stronger foundation** | The vault itself is the shared representation; browser and Obsidian hosts work over it instead of syncing proprietary state. |

Focused evidence: `test_v1_export.py`, `test_search_grains.py`, `test_upkeep.py` and `test_dik.py` all passed (26 tests).

## Material gaps and decisions

### 1. Legacy import is technically present but not a user-facing product capability — P0

`src/resource_librarian/v1_export.py` is a careful read-only importer: it stages candidates for review, preserves a whole legacy note as `v1_note` evidence, avoids duplicates and is idempotent. It is not registered as a CLI command or MCP tool, exposed in the UI, or documented in the V2 README. The historical V2 plan said V1 data would not migrate, so this is also a strategy contradiction.

A read-only candidate plan against `D:\Resource-Library` found 500 stageable records:

- 228 repository sources; 31 papers; 23 models; 2 datasets;
- 131 terms and 54 patterns;
- 18 applications and 13 offerings.

It intentionally left out 204 items: 136 untyped/non-catalogued notes, 45 drafts, 18 generated hubs/indexes/queues/templates, plus workflow/canvas/index folders. It also does not turn V1 normalized surveys, queues, external-link records, staged backlog or lens backlog into V2 machine-readable evidence without re-intake.

**Recommendation:** make an explicit product choice. Either release a documented `plan`/`stage` migration workflow with its limits and an evidence-rehydration path, or retire the module and explain the deliberate non-migration stance. Do not leave it as an undocumented escape hatch.

### 2. Graph and community analysis did not transfer — P1

V1's `graph.py` supplied communities, filtered centrality and community reports. V2 has source/concept link navigation, but no graph/community module or registered capability. This is a genuine loss for answering whole-library questions such as “what clusters of capability exist?”

**Recommendation:** restore it as an optional, derived module over V2's indexes/SQLite data so it does not compromise the no-host-service deployment aim.

### 3. Capability digest/import-graph extraction is absent — P1

V1's `digest.py` and `importgraph.py` answered implementation questions such as which files support a capability. V2 has useful components—source-file reading, structure capture and component paths—but no registered `extract`, digest or import-graph service, despite the plan intending one.

**Recommendation:** add a bounded evidence-backed extractor that produces relevant paths, dependencies, revision and source excerpts without turning the vault into an ungoverned snippet dump.

### 4. Use-signal learning is safely disabled rather than operational — P2

V1's `usesignal.py` included readiness checks before use data influenced rank. V2 records applications and search feedback; the latter deliberately logs without changing rank. This is conservative and correct today, but it removes the original path from real use to measured library learning.

**Recommendation:** define a transparent learning-readiness report first. Separate retrieval quality, application outcomes, feedback and abandonment; require declared sample/quality thresholds and review before any ranking adaptation.

### 5. The source-engagement workbench lifecycle is only partial — P2

V1 Mode D linked source engagement, isolation and mandatory documentation before destruction. V2's generic sandbox and constrained claim runner are useful, but a run is not necessarily bound to a source revision or an application record.

**Recommendation:** add an optional “engage source” record connecting a sandbox/claim run to a source/version, project, outcome and application check-out. Preserve generic sandbox use for unconstrained exploration.

## Architecture implication

The V2 plan described a research harness, not a generic all-in-one agent harness. The current co-work ambition can be accommodated if the platform treats the research kernel as stable and co-work capabilities as composable extensions:

```text
Research kernel: vault schema, evidence, intake, search, staging, sessions, policy
Co-work extensions: hosts, models, agents, workflows, sandbox, media, MCP, project controls
```

That boundary makes it possible to restore missing research capabilities as optional modules without turning the core or every vault deployment into a monolith.

## Follow-up order

1. Publish the capability matrix: **ported / changed / optional / deferred / removed**, with rationale.
2. Decide V1 interoperability and expose or retire the existing importer.
3. Restore graph/community analysis and capability extraction as optional modules.
4. Introduce measurable use-learning readiness and source-engagement provenance.
5. Consolidate V1 R&D material into V2-facing architecture, migration and operator documentation.
