# Geo-Grapher Graph Building Across Folder Review and Librarian Enrichment (As-Is)

**Date:** 22 November 2026  
**Scope:** As-is activity model of Geo-Grapher's graph-building process (`geographer` wheel `0.2.0`) and how it currently interacts with Librarian's folder ingestion and 9-stage enrichment pipeline. Source-backed from `src/resource_librarian/` (`folder_review.py`, `batch.py`, `paper_graph.py`, `geo_service.py`), installed Geo-Grapher source (`workspace_init.py`, `folder_review.py`, `pipeline.py`, `treesitter.py`, `library_papers.py`, `graph_catalog.py`, `pipeline/stage3_build_db.py`), and the three-library audit in [2026-11-22-libraries-ingest-enrichment-audit.md](../2026-11-22-libraries-ingest-enrichment-audit.md).

## Artifacts

| Artifact | Purpose |
|---|---|
| [Activity Canvas](geographer-graph-building.canvas) | Actor-column Obsidian canvas (`44` nodes, `40` edges, `0` overlaps, `0` text overflow) |
| [Behavior Specification](geographer-graph-building.spec.yaml) | Editable activity spec in the `render_spec.py` schema (18 numbered steps, 10 extensions, 11 paths) |
| [Generated Views](geographer-graph-building.views.md) | Mermaid swimlane diagram, written use case, lane load, decision tree, 11-path test table, and cross-view check (`0` problems, `0` flags) |
| [Visual Preview](overview.png) | Deterministic raster preview of the saved canvas geometry |
| [Validation](validation.json) | Structural, cross-view, overlap, text-overflow, and revision checks |

---

## Key Finding: Only Half of Graph Building Happens During Enrichment

Although ideally woven into Librarian's enrichment pipeline, Geo-Grapher's graph building is currently split into **two disconnected, serial, cold-start CLI subprocesses**:

1. **Phase I — Code / Docs / Data / Logs Graph Building (`apply-folder-review`, Steps 1–7):**  
   Runs **upstream during folder acceptance** (`FolderReview.accept` / `accept_by_policy`), **before** any source is queued, captured, or enriched. It invokes `python -m geographer apply-folder-review --catalog catalog.sqlite` (14,400 s timeout), builds `code.sqlite` snapshots across **every reviewed group in the library**, and stops before source enrichment begins.
2. **Phase II — Paper Graph Building (`write_artifact` + `import-library-paper`, Steps 8–18):**  
   Bolted onto **Stage 2 (`parse`)** and **Stage 9 (`publish`)** of `batch.py`. During Stages 3–8 (`read → lenses → data → relate → metadata → review`), **Geo-Grapher is never consulted**, and **lenses, chapter relations, and metadata proposals are never projected** into any graph. At Stage 9, for each fully read, fully converted PDF, Librarian spawns a separate `python -m geographer import-library-paper` subprocess that clones the **entire prior paper SQLite database** into a brand-new `papers-native-<uuid>.sqlite`, loads 1 paper, rebuilds full-corpus FTS/read models, and updates `catalog.sqlite`.

---

## Shared Weaknesses With the Ingestion Process

Your suspicion is directly confirmed by the code and the `G:\Libraries` logs. Geo-Grapher's graph building reproduces almost every structural weakness identified in [ingestion.canvas](../2026-11-20-workflow-map/examples/ingestion/ingestion.canvas), plus several storage-layer equivalents:

| Weakness | How It Appears in Ingestion (`ingestion.canvas`) | How It Appears in Geo-Grapher Graph Building | Observed Evidence in `G:\Libraries` |
|---|---|---|---|
| **OP1 — Missing final hand-off & post-build verification** | Papers read into staging, never accepted into Source notes (`15a`), with no alert. | `publish` records `publish: complete` with **no check** that claims/concepts are non-zero, that `catalog.sqlite-wal` is checkpointed, that `serve-graphs` sees the update, or that the Source note is accepted (`17a`). | **48 published NFL PDFs** live in paper graphs with no Source note; **12 unread RL PDFs** published with `0` claims; **72 NFL papers** have `0` concepts; `Resource-Library/catalog.sqlite-wal` sits **1.67 MB uncheckpointed**. |
| **OP2 — Whole-library blast radius on local changes** | One stale root blocks unrelated folder decisions (`3a`). | `FolderReview.accept` re-surveys every non-excluded root (`2a`), and `apply-folder-review` loops over **every reviewed group** (`a5`). Worse, `pipeline.ingest` is called **without `previous_snapshot_id`**, so any 1-file edit triggers a full Stage 1–3 rebuild and appends an unpruned snapshot. | **77.23 GB** across 30 graphs (`19.53 GB` on `quantule_mapper-docs`, `12.76 GB` on `Resource-Library-docs`, **191 snapshots** on `quantule_mapper-data`). `FOLDER_STALE` also fires **inside enrichment `publish`** (`41×` in NFL, `12a`). |
| **O(N²) copy-on-write generation bloat** | *(Not visible in `ingestion.canvas`)* | `library_papers.py:78-84` clones the **entire** prior `papers-native-*.sqlite` via `old.backup()` for **every single paper** and never prunes old generations (`a15`). | **96 retained DB copies = 872.7 MB** for a **15.96 MB** active DataManagement DB (**55× amplification**); **63 copies = 256.2 MB** for an `8.97 MB` NFL DB (**29× amplification**). |
| **Opaque failure swallowing & partial-loop split state** | Qualification loss surfaced only as generic `FOLDER_DRAFT_FAILED` (`5a`). | `folder_review.cli()` hides raw stderr in `~/.config/.../geographer-cli.log` and raises generic `GEOGRAPHER_CALL_FAILED`. In `apply-folder-review` (`4a`), failure on group *k* leaves groups `1..k-1` committed. In `batch._publish` (`14a`), `ValueError`/`OSError` is caught into generic `publish: partial`. | **12× `GEOGRAPHER_CALL_FAILED`** on `folder-accept` across all 3 libraries (`5` NFL, `3` Parallax, `4` RL); `GROUP_STRATUM_CONFLICT` in Parallax. |
| **Silent partial extraction marked `complete`** | Partial chunks required manual inspection (`12a`/`12b`). | `treesitter.extract_fallback` fails with `No module named 'tree_sitter'` (`FallbackUnavailable`) and UTF-8 errors, logs `parse_failures_json`, and still publishes `status='complete'` (`5b`). | **85** NFL, **730+** Parallax, and **345+** RL files (including `Librarian_V2/ui/src/*.ts` and `obsidian/src/*.ts`) failed AST parsing silently. |
| **No enrichment weaving / zero cross-graph synthesis** | Tiers 1–2 absent; orchestration sits outside Core workflows. | Code graphs run before enrichment; paper graphs run after enrichment; Stages 3–8 never query Geo-Grapher; **lenses, chapter relations, and metadata are never projected**; **0 cross-graph bridges** are created (`a10`, `a17`). | `bridges = 0`, `bridge_proposals = 0`, `artifact_justifications = 0` across all 3 libraries. |
| **Wasted `code.sqlite` builds on non-code folders** | *(Not modeled)* | `apply-folder-review` runs `PythonExtractor` on `docs`, `data`, and `third-party-papers` groups alike (`a5`). | `Resource-Library-third-party-papers` has a **2.41 GB `code.sqlite`** despite **0 papers**; `Librarian research-third-party-papers` has a **1.85 GB `code.sqlite`**. |

---

## Regenerating

```powershell
.venv\Scripts\python.exe -B reports\2026-11-22-geographer-graph-building\build_geographer_graph.py
```
