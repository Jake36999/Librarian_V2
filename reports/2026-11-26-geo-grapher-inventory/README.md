# Geo-Grapher: G6 agent-interface inventory and four-defect triage (26 November 2026)

- **Brief:** [2026-11-26-delegation-briefs.md §2](../2026-11-26-delegation-briefs.md) (read-only code inspection; no production code changed by this report)
- **Baseline inspected:** Geo-Grapher `feat/per-library-service` at `e71967a` (`F:\uv-data\Geo_Grapher`), Librarian `feat/geo-per-library-service` at `b583f03` (cloned to `G:\Librarian-work\librarian-delegated` on `antigravity/delegated-2026-11-26`)
- **Targets compared against:**
  - GT6 (`query-graph`): [`reports/2026-11-25-systems-analysis-finalisation/geo-grapher/to-be/query-graph.spec.yaml`](../2026-11-25-systems-analysis-finalisation/geo-grapher/to-be/query-graph.spec.yaml) and [`docs/proposals/implementation-plan-2026-11.md`](../../docs/proposals/implementation-plan-2026-11.md)
  - GT5 (`federated-search`): [`reports/2026-11-25-systems-analysis-finalisation/geo-grapher/to-be/federated-search.spec.yaml`](../2026-11-25-systems-analysis-finalisation/geo-grapher/to-be/federated-search.spec.yaml)
  - Four deferred defects listed in [`reports/2026-11-25-systems-analysis-finalisation/README.md`](../2026-11-25-systems-analysis-finalisation/README.md) (`t4/recon-25`, `t4/recon-26`, `t4/recon-29`, `t4/recon-30`)

---

## 1. G6 Inventory: Phase 6–7 & v1.1 contracts vs. GT6 (`query-graph`)

| Requirement / capability (GT6 & v1.1) | Status | Code & contract evidence (`F:\uv-data\Geo_Grapher`) | Gap / note |
|---|---|---|---|
| **Discover readable graphs (`list` / `G-QRY-01`):** return readable graphs' labels and kinds, **paged** | **partly** (`list_graphs` **exists**; paging & lightweight labels-only view **missing**) | `src/geographer/graph_router.py:359-388` (`GraphRouter.summary`), `src/geographer/graph_server.py:110` (`list_graphs`) | Returns all permitted non-disabled graphs with full snapshot/profile metadata; `list_graphs` takes `{}` with no `cursor`/`limit` paging (`G-QRY-01`). |
| **Search one graph by its label (`search`) & whole-graph default scope** | **exists** | `src/geographer/agent_requests.py:47-61,185-188,228,261-265`, `src/geographer/graph_server.py:58-95` | Flat tools (`search_entities`, `get_entity_content`, `get_architecture_context`, `find_dependants`, `check_architecture`, `find_similar_code`, `inspect_relationship_witnesses`) accept labels or IDs and fill `snapshot_id`, `budget`, and `whole_graph()` server-side. |
| **Label/alias resolution & consumer read permission (`dgraph`, `refused`, `e_refused`)** | **exists** | `src/geographer/graph_router.py:95-121` (`permit`, `enforce_reader`, `resolve`), `src/geographer/agent_requests.py:262-265` | Resolves `graph_id`, unambiguous case-insensitive `label`, or single-graph default; unknown/ambiguous/unavailable errors list up to 12 readable `label (graph_id)` choices. |
| **Ranked search pagination (`rank` — `offset` / `next_offset`)** | **exists** | `src/geographer/agent_requests.py:52,336,359-364`, `src/geographer/graph_server.py:69,94` | Flat `search_entities` supports `offset` (`0..200`), returns `search_hits_omitted`, `completeness.truncated`, and `next_offset` when hits remain. |
| **Read an entity's content (`content`)** | **exists** | `src/geographer/agent_requests.py:229-245,300-315,365-374` | Reads entity source or documentary fragment text; supports `start_line`/`end_line` and `agent_scent` default `context_ranges`. |
| **Oversize handling (`dsize` / `parts` / `G-QRY-02`):** return item's outline and handles of its parts instead of failing | **missing** | `src/geographer/graph_router.py:558-561`, `src/geographer/agent_requests.py:17-22,200-205,405-414,471-479` | `_fit` trims paged bundles down to 1 item then raises `RESULT_TOO_LARGE: one item exceeds this connection's max_result_chars`; `agent_requests.enforce_cap` and `call_code` raise `BUDGET_TOO_SMALL` / `RESULT_TOO_LARGE`; `bounded_context` degrades context down to `focus_only` then raises `BUDGET_TOO_SMALL`. No outline + part-handle fallback exists (`G-QRY-02`). |
| **Read a requested part (`part`):** fetch a part handle after outline fallback | **missing** (manual line range **exists**) | `src/geographer/agent_requests.py:53,230-236` (`get_entity_content` `start_line`/`end_line`) | Callers can request explicit line ranges if known, but there is no part-handle API matching `parts` (`G-QRY-02`). Note: paper tools separately provide `paper_get_outline` / `paper_get_section` (`graph_server.py:97-107`). |
| **Architecture context (`context`)** | **exists** | `src/geographer/agent_requests.py:246-248,417-478`, `src/geographer/graph_server.py:66-67` | `get_architecture_context` with bounded degradation (`bounded_context`) and explicit `degraded` markers. |
| **Cite entity by handle (`cite`, `e1`)** | **exists** | `src/geographer/agent_requests.py:199-218,270-288,328`, `contracts/v1.1/ACTOR_SCHEMA.md` | Accepts `label/entity:<id>` or canonical ID, maps scoped aliases within connection/snapshot, and attaches `cite_as` on every entity. |
| **Token accounting, profile ceilings, `GreedyPacker`, v1.1 contracts** | **exists** | `contracts/v1.1/{ACTOR_SCHEMA.md,PACKING_ADDENDUM.md,geographer.wire.d.ts}`, `src/geographer/packing.py:11-78`, `src/geographer/task_packets.py:13-22` | `PROFILE_CEILINGS` (`tier3_leaf`: 1200, `tier2_forager`: 1800, `tier1_lead`: 32768), `TokenCounter` (`o200k_base`), whole-envelope recount, and `packer-v2-incremental` ship and pass contracts. |
| **Read-only / untrusted source boundary & task packet compilation (`compile_task_packet`)** | **exists** | `src/geographer/graph_server.py:74,95,111-116`, `src/geographer/task_packets.py:38-116+`, `src/geographer/graph_router.py:564-566` | All MCP tools declare `readOnlyHint=True`; source content is marked untrusted; `compile_task_packet` compiles snapshot-bound packets within profile ceilings. |

**GT6 Summary:** Search, label resolution, consumer access enforcement, paginated search, token-budget accounting, profile ceilings, `compile_task_packet`, and canonical `cite_as` handles **exist**. Two GT6 weaknesses remain open: **`G-QRY-01`** (unpaged `list_graphs` returning full metadata — graded **partly**) and **`G-QRY-02`** (missing structural outline + part-handle fallback `parts`/`part` when a single code entity exceeds budget — graded **missing**).

---

## 2. G6 Inventory: Phase 6–7 vs. GT5 (`federated-search` & bridge review)

| Requirement / capability (GT5) | Status | Code evidence (`F:\uv-data\Geo_Grapher`) | Gap / note |
|---|---|---|---|
| **Choose 2–8 graphs, query & budget (`choose`, `dvalid`, `invalid`, `e_refused`)** | **exists** | `src/geographer/graph_router.py:572-580`, `src/geographer/graph_server.py:130` | Enforces 2–8 distinct graph IDs/labels, reader permissions, budget bounds (`256/2048..32768`), and profile ceilings (`check_profile`), refusing out-of-bounds calls with explicit error messages. |
| **Search each readable graph whole & select envelopes (`search`)** | **exists** | `src/geographer/graph_router.py:587-657`, `src/geographer/federation.py:1-47+` | Searches each graph via `_whole(gid, snapshot_id)`, collects `full`/`compact` envelopes, and uses `pc-mckp-v1` selection without global cross-graph re-ranking. |
| **Return per-graph rankings, omission reasons & accepted bridges (`answer` / `G-FED-01`)** | **partly** (rankings & omission reasons **exist**; inline accepted bridges **missing**) | `src/geographer/graph_router.py:616-638`, `src/geographer/graph_router.py:123-127` (`bridges`), `src/geographer/graph_server.py:117` (`list_bridges`) | `federated_search` returns per-graph `results`, `omitted` (`GRAPH_UNAVAILABLE`, `budget_compact_only`, `budget_omitted`, `no_relevant_hits`), `ranking`, and `selection`, **but does not include accepted bridges inline** — callers must invoke `list_bridges(graph_ids)` separately. |
| **Check whether accepted bridges relate results (`dbridged`)** | **partly** (separate `list_bridges` **exists**; no automatic inline signal in `federated_search` **missing**) | `src/geographer/graph_router.py:123-127`, `src/geographer/graph_server.py:117` | A caller can inspect accepted bridges and their staleness state via `list_bridges(graph_ids)`, though `federated_search` itself carries no inline bridge field (`G-FED-01`). |
| **Propose bridge candidates with witnesses (`propose` / `G-FED-02`)** | **exists** | `src/geographer/bridges.py:125-255+`, `src/geographer/graph_catalog.py:526-546` (`propose_bridges`), `src/geographer/graph_router.py:505-523`, `src/geographer/graph_server.py:118-129` | Exposed read-only via MCP `analyze_cross_graphs(mode='bridge_candidates')` (`status='unreviewed'`) and persisted as pending `bridge_proposals` via `propose_bridges` and HTTP `POST /api/graphs/bridge-proposals` (`G-FED-02` candidate generation exists). |
| **Oracle Tier A witness check before decision (`check`)** | **missing** | `src/geographer/graph_catalog.py:561-575` (`review_proposal`) | `review_proposal` accepts/rejects directly on operator rationale (`owner_decision=True`) with no automated Oracle Tier A witness check before the decision. (`analyze_cross_graphs` checks impacts/witnesses separately.) |
| **Decide candidates (`decide`, `ddecide`):** Owner decision or standing policy (`G-FED-02`) | **partly** (Owner decision + persisted rejection/acceptance **exists**; standing-policy auto-accept **missing**) | `src/geographer/graph_catalog.py:45,84,561-585+`, `src/geographer/graph_router.py:123-153`, `src/geographer/graph_server.py:117,478-485` | Catalog & HTTP routes (`/api/graphs/bridge-proposals/{proposal_id}`) store pending proposals, record `accepted`/`rejected` + bounded rationale (`review_proposal`), create declared `bridges`, and track `artifact_states` staleness (`lineage.py`). MCP exposes read-only `list_bridges` / `analyze_cross_graphs` only, and no standing-policy auto-approval exists yet. |
| **Relate graphs' results through bridges (`compare`, `e1`)** | **exists** (via `cross_graph` & `list_bridges`) | `src/geographer/cross_graph.py`, `src/geographer/graph_router.py:123-127,443,524-537`, `src/geographer/graph_server.py:117-129` | `list_bridges` returns accepted bridges + `lineage.state`, and `analyze_cross_graphs` (`bridge_impact`, `theory_conformance`, `evolution_diff`, `clone_candidates`) relates entities across bridged graphs with witness inspection (`inspect_relationship_witnesses`). |

**GT5 Summary:** Bounded 2–8 graph `federated_search` (`pc-mckp-v1`), unreviewed bridge candidate scoring, catalog/HTTP `bridge_proposals` review workflow, declared `bridges`, `cross_graph` analysis, and `lineage.py` staleness tracking **exist** — significantly further along than the as-is baseline assumptions in `G-FED-01` and `G-FED-02`. The remaining GT5 gaps are: (1) inline accepted bridges in `federated_search` (`answer`/`dbridged` -> **partly**), (2) an Oracle Tier A witness gate before bridge proposal decisions (`check` -> **missing**), and (3) standing-policy auto-acceptance (`decide`/`ddecide` -> **partly**).

---

## 3. Triage of the four deferred defects

### Defect 1: Dependency relations for Python functions (`t4/recon-25`)
- **Verdict:** **confirmed**
- **Verdict scope:** **Confirmed** for flat MCP outgoing traversal and default-filtered `candidate` Python call edges; **not reproduced** for direct static incoming function calls (which *are* extracted and returned).
- **Evidence:**
  - Direct static Python `calls` edges between functions **are** extracted by `src/geographer/extract.py` and queryable in `src/geographer/service.py`. In a read-only in-memory reproduction against Geo-Grapher (`F:\uv-data\Geo_Grapher`):
    - Flat MCP `find_dependants` on `callee` returned incoming callers `caller` and `decorated`.
    - Strict `service.query('find_dependants', ..., direction='outgoing')` on `caller` returned `callee`.
    - Strict `service.query('get_architecture_context', ...)` on `caller` returned 2 relationships.
  - However, two concrete behaviors cause flat MCP callers to miss Python function dependencies:
    1. **Flat MCP `find_dependants` is hardcoded `incoming` only:** `src/geographer/agent_requests.py:249` sets `direction='incoming'`, and `src/geographer/graph_server.py:48-50` rewrites tool guidance to state `"this form is incoming only"`. An agent using the flat MCP tool cannot inspect outgoing dependencies of a Python function.
    2. **`candidate` edges are dropped by `DEFAULT_FILTER`:** Decorated functions (`src/geographer/extract.py:468`: `"candidate" if getattr(node, "decorator_list", []) else "exact"`), uncertain attribute/member lookups (`src/geographer/dispatch.py:73`), and bound method receiver dispatch (`src/geographer/dispatch.py:112`) are typed `resolution_status='candidate'`. `src/geographer/analysis.py:15` sets `DEFAULT_FILTER = {..., "resolution_statuses": ["exact"], ...}`, which `src/geographer/agent_requests.py:246-249` copies for flat `get_architecture_context` and `find_dependants` (in contrast to `src/geographer/task_packets.py:56`, which explicitly passes `['exact', 'candidate']`). In our live repro, strict `get_architecture_context` with `DEFAULT_FILTER` excluded the `candidate` decorated edge.

### Defect 2: Search when repository IDs are omitted (`t4/recon-26`)
- **Verdict:** **not reproduced**
- **Verdict scope:** **Not reproduced** on flat MCP `search_entities` or `federated_search`; strict programmatic `service.py` requests intentionally reject an explicit empty `repo_ids: []` on multi-repo snapshots.
- **Evidence:**
  - `src/geographer/agent_requests.py:185-188` defines `whole_graph(ctx)` returning all snapshot `repo_ids` when more than one repository is present, and `src/geographer/agent_requests.py:228` passes `repo_ids=whole_graph(svc._context(sid))` for flat `search_entities`.
  - `src/geographer/graph_router.py:568-570,599-603` uses `_whole(gid, snapshot_id)` identically inside `federated_search`.
  - Covered by Geo-Grapher's regression test (`tests/test_folder_groups.py:200-228`) and verified in a live read-only multi-repo reproduction where flat `search_entities(graph_id, query)` returned entities from both member repositories (`['m.py.alpha_fn', 'n.py.beta_fn']`).
  - Strict programmatic calls (`src/geographer/service.py:298-303`) intentionally raise `INVALID_REQUEST: Select repo_ids explicitly in a multi-project snapshot` only when `repo_ids: []` is explicitly supplied against a multi-repository snapshot.

### Defect 3: Conversions persisting a source graph (`t4/recon-29`)
- **Verdict:** **not reproduced**
- **Verdict scope:** **Not reproduced** anywhere in Librarian conversions, batch parsing, deep reading, indexing, or paper projections.
- **Evidence:**
  - **Conversions persist text & receipts only:** `src/resource_librarian/conversions.py` stores only markdown conversions under `.librarian/conversions/<id>.md`, manifest entries in `.librarian/conversions/index.json`, and evidence records — no source graph is built or stored.
  - **`graphify-out` excluded across all discovery/indexing paths:** `src/resource_librarian/credentials.py:32` (`generated_path`), `src/resource_librarian/folder_sources.py:32` (`SKIP_DIRS`), `src/resource_librarian/index.py:351` (`Index.upsert`), and `src/resource_librarian/workspace_documents.py:135` all explicitly exclude `graphify-out`.
  - **Rebuildable paper projection vs. published graph:** `src/resource_librarian/paper_graph.py:153-160` (`write_artifact`) writes only a rebuildable `.librarian/derived/paper-graph/<sha256>.nodes.json` projection during batch parsing (`src/resource_librarian/batch.py:275-281`), keeping claims empty until reading completes and never writing a source graph (publication happens only in Stage 9 after full reading + an accepted current folder).
  - **`deep_read` persists no graph:** `src/resource_librarian/deep_read.py` stores only chunk reading points, limits, terms, and staged lens candidates on the staged item.

### Defect 4: Attached repositories kept read-only, never opened as libraries (`t4/recon-30`)
- **Verdict:** **confirmed**
- **Verdict scope:** Two-part rule — attached-repository read-only enforcement holds (**not reproduced** as a write leak), **but** preventing code repositories from being opened/adopted directly as Librarian libraries is **not enforced** in code (**confirmed**).
- **Evidence:**
  - **Attached roots are enforced read-only:** `src/resource_librarian/content_roots.py:160-184` (`apply_attach`) records attached folders strictly as `"access": "read_only"` inside the library's `.librarian/content-roots.json` without touching the attached folder; `src/resource_librarian/vault.py:133-147`, `src/resource_librarian/projects.py` (`FOLDER_READ_ONLY`), and `src/geographer/folder_review.py:135` (`read_only=True`) enforce read-only access.
  - **Direct opening/adoption of a `.git` repository as a library is still permitted:**
    - `src/resource_librarian/init.py:48-99` (`init`) checks only `if vault.exists(): raise Refusal("VAULT_EXISTS", ...)` and creates `About/`, `Indexes/`, `.evidence/`, and `.librarian/` inside any folder without checking for `.git` or code-repository markers.
    - `src/resource_librarian/deploy_survey.py:5,175,311-321` detects `out.git = os.path.lexists(root / ".git")` yet documents `"Adopt: the folder already holds documents (a Git repository, an Obsidian vault, a docs tree)"` and sets `modes["adopt"]["possible"] = True` for Git repositories.
    - Confirmed on disk in `F:\uv-data\Geo_Grapher\.gitignore:51-54`: `# Librarian vault folders created when the repo was opened as a library (2026-11-12); never commit.` ignoring `.librarian/`, `/About/`, `/Indexes/`.

---

## 4. Recommended follow-up

1. **GT6 (`G-QRY-01`, `G-QRY-02`):** Add cursor/limit paging + lightweight summary mode to `list_graphs`, and implement outline + part-handle fallback (`parts`/`part`) when a single code entity exceeds connection token or character budgets.
2. **GT5 (`G-FED-01`, `G-FED-02`):** Include accepted bridges (between requested `graph_ids`) inline in `federated_search` responses, and integrate Oracle Tier A witness checks + optional standing-policy rules into bridge proposal review.
3. **Confirmed triage items (`t4/recon-25`, `t4/recon-30`):** Add an explicit opt-in `direction` / `include_candidates` control on flat `find_dependants` / `get_architecture_context` (under report mode / non-breaking defaults), and address `init` / `deploy_survey` adoption of `.git` code repositories (directing callers to read-only `attach` instead). Per [2026-11-26-delegation-briefs.md](../2026-11-26-delegation-briefs.md), any new check that could refuse currently allowed repository-adoption behavior must **ship in report mode first**; acceptance of this inventory records the finding with that qualification and does not settle the eventual enforcement decision.
