# Audit Report: Ingest & Enrichment Logs (`G:\Libraries`) vs. Created Graphs

**Date:** 22 November 2026  
**Scope:** Strictly read-only inspection of all three libraries under `G:\Libraries` (`Nonlinear Field Lab`, `Parallax`, `Resource-Library`), their ingest/enrichment logs, staging/quarantine/vault state, and **both** sets of graphs created:
1. **Geo-Grapher knowledge graphs** (`.librarian/geographer/catalog.sqlite`, `code.sqlite`, `papers-native-*.sqlite`, and `.librarian/derived/paper-graph/*.nodes.json`).
2. **Workflow / process graphs (canvases)** in `reports/2026-11-20-workflow-map/`, `reports/2026-11-21-enrichment-baseline/`, and `reports/2026-11-22-proposed-tobe-enrichment/`.

No vault state, SQLite database, Core service, or model route was modified during this audit.

---

## 1. Executive Summary & Cross-Library Scorecard

Across `G:\Libraries`, **94 enrichment batches** (`1,426` item-stage runs covering `1,310` unique items), **48,448 Core writer operations**, and **49,248 model calls (\$10.26 reported spend)** were executed between **15 and 21 November 2026**.

| Metric | Nonlinear Field Lab | Parallax | Resource-Library | Total |
|---|---:|---:|---:|---:|
| Attached content roots | 56 | 56 | 77 | 189 |
| Folder staging cards (total) | 1,584 | 15,543 | 12,861 | 29,988 |
| `folder-sources.json` entries | 862 (`862` queued) | 92 (`92` queued) | 501 (`473` queued, `28` skipped-dup) | 1,455 |
| Staged sources (total) | 775 | 91 | 584 | 1,450 |
| — `accepted` (Vault `Sources/*.md`) | 240 | 49 | 363 | 652 |
| — `enriched` (unaccepted backlog) | **491** | **2** | **160** | **653** |
| — `partial` (unaccepted backlog) | **39** | **3** | **55** | **97** |
| — `staged` / `queued` (unapproved) | 4 | **37** | 6 | 47 |
| — `failed` | 1 | 0 | 0 | 1 |
| Promotion: `catalogued` / `written but not findable` | 239 / **1** | 49 / 0 | 360 / **3** | 648 / **4** |
| Enrichment batches (`runs/batch-*.jsonl`) | 43 | 4 | 47 | 94 |
| Batch item completions (`enriched` / `partial` / `failed`) | 762 / 138 / 2 | 51 / 3 / 0 | 396 / 64 / 10 | 1,209 / 205 / 12 |
| User cancellations / Budget-ceiling stops | 7 / 0 | 0 / 0 | 1 / 0 | 8 / 0 |
| Model calls (`runtime/usage-*.jsonl`) | 26,368 | 2,081 | 20,799 | 49,248 |
| Reported model spend (USD) / Unpriced calls | \$5.1993 / 0 | \$0.3187 / **110** | \$4.7403 / 4 | \$10.2583 / 114 |
| Staged lenses (`accepted` / total) | **0** / 312 | **0** / 51 | **0** / 326 | **0** / 689 |
| Quarantine JSON records | 100 | 4 | 27 | 131 |
| Staged PDFs (`accepted` / `enriched` / `partial`) | 78 (24 / 45 / 9) | 0 | 136 (96 / 0 / 40) | 214 (120 / 45 / 49) |
| Derived paper-graph `.nodes.json` (`full` / `catalogue_only`) | 148 (136 / 12) | 0 | 136 (126 / 10) | 284 (262 / 22) |
| Geo-Grapher catalog graphs (total) | 6 | 7 | 17 | 30 |
| Geo-Grapher paper DBs (active docs / claims / concepts) | 3 DBs (72 / 6,751 / **0**) | 0 | 2 DBs (105 / 8,794 / 7,292) | 5 DBs (177 / 15,545 / 7,292) |
| Geo-Grapher total SQLite disk footprint | **30.61 GB** | **15.72 GB** | **30.89 GB** | **77.23 GB** |

### Headline Findings

1. **OP1 (Unaccepted Enriched Backlog) Is Still Live Across All Three Libraries:** Although `E:\DataManagement` (96 papers in Resource-Library) was accepted on 20 November, **750 processed sources (`653 enriched` + `97 partial`) remain stranded in staging** across the three libraries—including **48 published PDFs in Nonlinear Field Lab** that exist in live Geo-Grapher paper graphs without accepted Source notes.
2. **All 689 Derived Lenses Sit Unreviewed:** Enrichment extracted **689 staged lenses** (`312` NFL, `51` Parallax, `326` Resource-Library), and **0** have been accepted or rejected.
3. **100% Failure Rate for Folder-Metadata Batch Enrichment (`0/12`):** Every batch attempt on folder cards failed at `folder_describe` (`2/2` `FOLDER_PROVENANCE` in NFL; `10/10` `FOLDER_DRAFT_FAILED` in Resource-Library); none ever reached `folder_data`.
4. **Severe Geo-Grapher Disk & Integrity Anomalies:** The 30 Geo-Grapher graphs occupy **77.23 GB** on disk—driven by multi-snapshot `code.sqlite` bloat (up to **19.53 GB** for a single `docs` graph due to OP2 full-group rebuilds), **180 retained `papers-native-*.sqlite` generations** (up to **55×** storage amplification in DataManagement), an uncheckpointed **1.67 MB WAL** on `Resource-Library/catalog.sqlite`, **12 unread PDFs published with 0 claims** in `Resource-Library-Librarian research-third-party-papers`, **0 concepts** across all 3 Nonlinear Field Lab paper graphs, and widespread `No module named 'tree_sitter'` parse failures in code graphs.
5. **Major Gaps Between Workflow Canvases and Actual Logs:**
   - [ingestion.canvas](file:///d:/Librarian_V2/reports/2026-11-20-workflow-map/examples/ingestion/ingestion.canvas) models only the cleanest 96-paper cohort (`E:\DataManagement`) and claims extension `16a` (`written but not findable`) was *"never exercised (anticipated)"*—yet actual logs contain **4 real `written but not findable` notes** (1 in NFL, 3 in Resource-Library).
   - [enrichment-cycle.canvas](file:///d:/Librarian_V2/reports/2026-11-21-enrichment-baseline/enrichment-cycle.canvas), [accepted-ingestion-tobe.canvas](file:///d:/Librarian_V2/reports/2026-11-20-workflow-map/examples/ingestion/accepted-ingestion-tobe.canvas), and [proposed-tobe-enrichment.canvas](file:///d:/Librarian_V2/reports/2026-11-22-proposed-tobe-enrichment/proposed-tobe-enrichment.canvas) depict multi-tier orchestration (Lead, Clerk/Scribe split, Oracle, Doctor, tickets), whereas **0% of actual ingest/enrichment calls** used those roles (`99.3%` ran through legacy `clerk`, `cleanup`, and `ocr`, with `100%` of accepts/approves still recorded `by: "person"` despite `promotion.mode = "agent"`).

---

## 2. Library-by-Library Audit of Actual Ingest & Enrichment Logs

### 2.1 Nonlinear Field Lab (`G:\Libraries\Nonlinear Field Lab`)

- **Activity window:** 15–20 November 2026 (`28,850` unique Core writer ops; active ingestion/enrichment 15–17 Nov; 240 sample accepts on 18 Nov).
- **Configuration ([config.toml](file:///G:/Libraries/Nonlinear%20Field%20Lab/.librarian/config.toml)):** `promotion.mode = "agent"`, `folders.production_drafting = true`, `conversion.optical_all_pages = false`, `services.ocr = "deepinfra:Qwen/Qwen3.5-27B"`, `budget.ceiling_usd = 8.2469`.
- **Ingest & Folder Review:**
  - `56` content roots (`38` data, `6` own-docs, `6` logs/transcripts, `2` third-party, `2` research-docs, `1` own-current, `1` root).
  - `862` entries in `folder-sources.json` (all `queued`), `1,584` folder staging cards, `100` quarantined records (`70` moved when `external_validation/papers` was relocated on 16 Nov; `12` duplicate `README.md`; `1` capture crash `KeyError: '/DescendantFonts'` on `Design and Simulation of All-Optical OR Logic Gate.pdf`).
  - `operations.jsonl` records `5` `folder-accept` failures (`GEOGRAPHER_CALL_FAILED`), `1` `folder-batch-approve` refusal (`FOLDER_BATCH: ambiguous classification needs individual review`), and `3` `mcp` refusals (`TIER_REFUSED`).
- **Enrichment Runs (`43` batches, `batch-2026-11-15-2ff42f` to `batch-2026-11-17-f22783`):**
  - `902` item completions across `792` unique items: `762 enriched`, `138 partial`, `2 failed`.
  - **All 7 cancellations** were manual (`cancelled after <item>: read/parse`); `0` budget-ceiling stops.
  - **2 stage failures** were both folder-metadata cards (`batch-2026-11-16-529761`): `folder_validate` succeeded (`2`), then `folder_describe` threw `ValueError: FOLDER_PROVENANCE: description contradicts its inventory` (`2`).
  - **Dominant partial causes in batches:**
    - `publish[partial]`: **`41` `FOLDER_STALE`** (`batch-2026-11-16-38120a`, `c17c48`) and **`27` `awaiting_accepted_folder`** (`batch-2026-11-16-9f8181`, `38120a`, `f66f28`) — happening *inside enrichment*, not at folder survey!
    - `read[queued]` (`36`) and `review[queued]` (`36`) waiting on the Clerk model; `data[partial]` (`45`, e.g., `0 of 1 chapters opened`); `relate[partial]` (`15`, fewer than two fully read chapters); `parse[partial]` (`11`, including OCR `26 of 27 required pages` in `batch-2026-11-17-97efbc`).
- **Model Usage & Spend:** `26,368` calls totaling **\$5.1993** (`0` unpriced):
  - `clerk` (`google/gemma-4-26B-A4B-it`): `25,484` calls (\$4.6485) — top tasks: `terms` (4,875 / \$1.57), `points` (4,754 / \$0.80), `limits` (4,723 / \$0.71), `lens_perspective` (3,950 / \$0.59), `sensitivity` (1,798), `bottom_line` (1,717).
  - `cleanup` (`deepseek-ai/DeepSeek-V4-Flash-0731`): `846` `pdf_to_markdown` calls (\$0.4799).
  - `ocr` (`deepinfra:Qwen/Qwen3.5-27B`): `26` `page` calls (\$0.0706).
  - `scribe`, `research_helper`, `lead`: `4` calls each (`qualification` probes only; \$0.0001 total).
- **Current Backlog & Promotion State:**
  - Only **240** of `775` staged sources are `accepted` (all accepted on 18 Nov with `by: "person"`, reason `"owner in chat 2026-11-18: accept a large sample to the catalogue (agent override..."`).
  - **491 `enriched` + 39 `partial` = 530 processed sources sit unaccepted** (mostly `F:\quantule_mapper\docs`: 483 enriched + 34 partial; `external research`: 5 enriched + 5 partial).
  - **1 promoted note is `written but not findable`:** `PHASE_C_OPTION_B_N96_TRACE_20260625_003926` (`findability: ok=False`, missed `"not in the top 5 for its Bottom Line"`, `vectors: off`, `concepts linked: []`).

### 2.2 Parallax (`G:\Libraries\Parallax`)

- **Activity window:** 15–20 November 2026 (`2,057` unique Core writer ops; active ingestion/enrichment 17–18 Nov).
- **Configuration ([config.toml](file:///G:/Libraries/Parallax/.librarian/config.toml)):** `promotion.mode = "agent"`, `folders.production_drafting = true`, `services.ocr = "deepinfra:Qwen/Qwen3.5-397B-A17B"`, `budget.ceiling_usd = 2.2794`.
- **Ingest & Folder Review:**
  - `56` content roots (`29` data, `18` third-party, `4` own-docs, `2` research-docs, `1` logs/transcripts, `1` own-current, `1` root).
  - **`15,543` folder staging cards** and **`15,546` folder DIK records** generated from attached `F:\network_management` trees, yet only `92` files queued in `folder-sources.json` (all Markdown/text docs, **0 PDFs**).
  - `operations.jsonl` records `3` `folder-accept` failures (`GEOGRAPHER_CALL_FAILED`) and `1` `folder-survey` entry still left in `status: "running"`.
- **Enrichment Runs (`4` batches, `batch-2026-11-17-7e56a9` to `batch-2026-11-18-69b7e5`):**
  - `54` item completions (`51 enriched`, `3 partial`, `0 failed`, `0` cancellations/budget stops).
  - Stage profile: `validate`/`parse`/`read`/`lenses`/`data`/`metadata` `54/54 complete`; **`relate` `54/54 not_applicable`**; **`publish` `54/54 not_applicable`** (no PDFs).
  - Partial reasons (`3`): `1` `review[queued]` and `2` `review[partial]` (`"the clerk answered, but its Bottom Line did not rest on the source's own words"` in `batch-2026-11-18-69b7e5`).
- **Model Usage & Spend:** `2,081` calls totaling **\$0.3187**, with **`110` failed & unpriced calls**:
  - On 16 Nov, `openai/gpt-oss-120b` failed **110/110** Clerk folder calls (`55` `sensitivity` + `55` `folder_brief`, ~40s timeout each, `outcome: "failed"`, `usd: None`) before the library switched to `google/gemma-4-26B-A4B-it` (`1,965` calls, \$0.3186).
  - `lead`, `scribe`, `research_helper`: `4` qualification probes each (\$0.00).
- **Current Backlog & Promotion State:**
  - `49` accepted (`49/49 catalogued`, `0` not-findable; all `by: "person"`, 18 Nov sample accept), **`37` stuck in `staged`** (never approved/enriched, mostly `F:\network_management\docs`), `3 partial`, `2 enriched` unaccepted.

### 2.3 Resource-Library (`G:\Libraries\Resource-Library`)

- **Activity window:** 6–21 November 2026 (`17,541` unique Core writer ops; two main waves: 16–17 Nov internal docs + `Librarian research`, and 20 Nov `E:\DataManagement` 96-paper ingestion + research brief).
- **Configuration ([config.toml](file:///G:/Libraries/Resource-Library/.librarian/config.toml)):** `promotion.mode = "agent"`, `folders.production_drafting = true`, `folders.third_party_graph = "project"`, `clerk.model = "deepseek-ai/DeepSeek-V4-Flash-0731"`, `clerk.route_review = "deepinfra:zai-org/GLM-5.3"`, `budget.ceiling_usd = 19.4703`.
- **Ingest & Folder Review:**
  - `77` content roots (`35` data, `20` research-docs, `9` third-party, `8` own-docs, `3` own-current, `1` own-legacy, `1` root).
  - `12,861` folder staging cards; `501` entries in `folder-sources.json` (`473` queued, `28` skipped as byte-identical to Nonlinear Field Lab PDFs).
  - **Queue leak observed:** `3` test fixture PDFs inside a hidden scratch directory (`E:/Librarian research/.gg-w4-final-temp/pytest-of-jakem/.../p.pdf`) entered `folder-sources.json` before hidden folders were filtered, and were later quarantined (`27` quarantine records total).
  - `operations.jsonl` logs `4` `folder-accept` `GEOGRAPHER_CALL_FAILED` errors, `3` `FOLDER_STALE` refusals, and `3` DeepInfra `HTTP 429` errors.
- **Enrichment Runs (`47` batches, `batch-2026-11-16-b15a73` to `batch-2026-11-20-faca2a`):**
  - `470` item completions across `464` unique items: `396 enriched`, `64 partial`, `10 failed`, `1` manual cancellation (`batch-2026-11-16-b15a73`), `0` budget-ceiling stops.
  - **All 10 stage failures** were folder-metadata cards (`batch-2026-11-16-c6ba20`): `10` `folder_validate: complete` → `10` `folder_describe: failed` (`ValueError: FOLDER_DRAFT_FAILED`).
  - **DeepInfra HTTP 429 rate limits during `parse`** left `3` `parse[partial]` items on 20 Nov (`batch-2026-11-20-d8c19c` and `f011a3`), falling back to raw extraction.
  - **Two sharply divergent PDF cohorts (`136` total staged PDFs):**
    1. **`E:\DataManagement` (96 PDFs, 20 Nov):** `96/96 accepted` (`by: "person"`, reason citing Owner chat instruction applied by Claude); `93 full` / `3 partial` (JSON-parse refusal on `terms` task in `G-Retriever`, `OLMoE`, `MoE-KG recommendation`); `93 publish: complete` / `3 publish: partial`.
    2. **`E:\Librarian research` (40 PDFs, 16 Nov):** **All 40 remain `partial` and unaccepted**, with `read=queued, review=queued` (`batch-2026-11-16-b15a73`, `b6902d`) — yet **`12` of these unread PDFs have `publish: complete`** (published on 16–17 Nov before `batch.py`'s full-reading gate was added!), `21` have `publish: partial`, and `7` have `publish: not_applicable`.
- **Model Usage & Spend:** `20,799` calls totaling **\$4.7403** (`4` unpriced failed/cancelled):
  - `clerk` (`google/gemma-4-26B-A4B-it` + 2 `zai-org/GLM-5.3` qualification calls on 21 Nov): `19,084` calls (\$3.2813).
  - `cleanup` (`deepseek-ai/DeepSeek-V4-Flash-0731`): `1,359` `pdf_to_markdown` calls (\$0.7328).
  - `lead` (`XiaomiMiMo/MiMo-V2.6-Flash` + 2 failed `Seed-2.0-mini` qualification calls): `331` calls (\$0.7205) — **327 of these were downstream `explore`/`research` calls (UC2), not ingest/enrichment**.
  - `scribe`: `21` calls (\$0.0056) — `4` qualification + `17` `scribe:offering` (UC2).
  - `research_helper`: `4` qualification probes (\$0.00).
- **Current Backlog & Promotion State:**
  - `363` accepted (`360 catalogued`, **`3 written but not findable`**), **`160 enriched` + `55 partial` = 215 unaccepted** (65 `Librarian_V2/reports`, 40 `Librarian research` PDFs, 21 `Resource-Library/06-Papers`, 16 `Librarian_V2/docs`, 13 `10-Models`, 10 `Aletheia_project/DEV_TOOLS`, etc.), plus `4 staged` and `2 queued` (no file).
  - **3 `written but not findable` notes:** `DeepInfra Model-to-Service Match - Capability Test Results`, `gemma-4-26B-A4B-it`, and `Qwen2.5-72B-Instruct` — all 3 failed `not in the top 5 for its Bottom Line` with `vectors: off` and `concepts linked: []`.

---

## 3. Comparison Against the Geo-Grapher Knowledge Graphs Actually Created

### 3.1 Paper-Graph Pipeline Reconciliation (Logs vs. Derived Artifacts vs. Geo-Grapher vs. Vault Notes)

| Library & Paper Graph | Staged PDFs | Derived `.nodes.json` (`full`/`cat`) | `publish: complete` | Active Geo Paper DB Docs | Geo Claims / Concepts | Accepted PDF Notes | Discrepancy / Integrity Finding |
|---|---:|---:|---:|---:|---:|---:|---|
| **Nonlinear Field Lab** (3 paper graphs) | **78** | **148** (`136`/`12`) | **72** | **72** (`2` + `7` + `63`) | 6,751 / **0** | **24** | **48 published papers lack accepted Source notes (live OP1).** All 3 paper DBs have **0 concepts** (predate concept projection). **70 extra** `.nodes.json` files remain from quarantined moved PDFs (`148` vs `78`). |
| — `g_01dcacd5` (`quantule_mapper-docs`) | — | — | — | 2 | 128 / **0** | — | 2 DB generations (`0.68 MB`). |
| — `g_2d94786a` (`third-party`) | — | — | — | 7 | 489 / **0** | — | 7 DB generations (`4.53 MB`). |
| — `g_a9124b87` (`third-party-papers`) | — | — | — | 63 | 6,134 / **0** | — | **63 DB generations (`256.22 MB` for an `8.97 MB` active DB — 28.6× amplification).** |
| **Parallax** (`Parallax-third-party-papers`) | **0** | **0** | **0** | **0** | 0 / 0 | **0** | Consistent: no PDFs ingested; paper graph is empty (`code.sqlite` stub `0.29 MB`). |
| **Resource-Library** (2 active paper graphs) | **136** | **136** (`126`/`10`) | **105** | **105** (`93` + `12`) | 8,794 / 7,292 | **96** | **Two broken/mismatched invariants below.** |
| — `g_6c285e54` (`DataManagement-third-party-papers`) | 96 | 96 | 93 (`3` partial) | **93** | 8,794 / 7,292 | **96** (`93` full, `3` partial) | Matches logs cleanly on document count (`93`), **but** retains **96 DB generations (`872.71 MB` for a `15.96 MB` active DB — 54.7× amplification)**, and its `catalog.sqlite` registration sits inside an uncheckpointed **1.67 MB `-wal` file**. |
| — `g_50866a6f` (`Librarian research-third-party-papers`) | 40 | 40 | **12** (`21` partial, `7` n/a) | **12** | **0 / 0** | **0** | **12 unread PDFs (`read=queued`) were published with 0 claims and 0 concepts** on 16 Nov and remain live in the graph; all 40 PDFs are still `partial` and unaccepted. |

All 5 active `paper_database` pointers in `catalog.sqlite` (when read **with WAL**) match the newest `papers-native-*.sqlite` generation on disk.

### 3.2 Code & Document Geo-Grapher Graphs: Storage Bloat, OP2 Snapshot Explosion, and Parse Failures

Across the 3 libraries, Geo-Grapher maintains **30 graphs consuming 77.23 GB**, of which **76.08 GB is `code.sqlite`** (including graphs for non-code `docs` and `third-party` folders):

| Library | Graph Label (`graph_id`) | `code.sqlite` | Snapshots | Entities (est. max rowid) | Sample `tree_sitter` Parse Failures | Notable Issue |
|---|---|---:|---:|---:|---:|---|
| **Nonlinear Field Lab** | `quantule_mapper-docs` (`g_01dcacd5`) | **19,534.84 MB** | 27 | 593,849 | 0 | **19.5 GB for a `docs` graph**; repeated snapshots from OP2 full rebuilds. |
| **Nonlinear Field Lab** | `quantule_mapper` (`g_9e25f09e`) | **8,492.61 MB** | 12 | 355,635 | 85 | Missing `tree_sitter` module. |
| **Nonlinear Field Lab** | `quantule_mapper-data` (`g_faa08842`) | **2,895.39 MB** | **191** | 129,501 | 0 | **191 accumulated snapshots** on a `data` folder. |
| **Parallax** | `third-party-docs` (`g_0d9873a7`) | **9,903.29 MB** | 33 | 826,846 | **248** | **9.9 GB** + missing `tree_sitter`. |
| **Parallax** | `network_management` (`g_e748050e`) | **5,022.09 MB** | 4 | 303,488 | **479** | **553 total sample parse failures** (479 `tree_sitter`, plus UTF-8 `UnicodeError` on text files). |
| **Resource-Library** | `Resource-Library-docs` (`g_75924e75`) | **12,760.85 MB** | 29 | 672,311 | 52 | **12.8 GB** for vault docs. |
| **Resource-Library** | `ToolSet-third-party` (`g_79b5af76`) | **5,743.01 MB** | 6 | 449,389 | **218** | Missing `tree_sitter`. |
| **Resource-Library** | `Librarian_V2` (`g_fb90389c`) | **3,404.99 MB** | 6 | 198,531 | **56** | **TypeScript files (`ui/src/*.ts`, `obsidian/src/*.ts`) failed AST parsing** (`No module named 'tree_sitter'`). |
| **Resource-Library** | `Librarian_V2-docs` (`g_6f028f4d`) | **2,482.86 MB** | 19 | 137,686 | 0 | 2.5 GB for markdown docs. |
| **Resource-Library** | `Resource-Library-third-party-papers` (`g_06997b93`) | **2,412.53 MB** | 4 | 171,406 | 0 | **2.4 GB `code.sqlite`** despite **0 papers** in this paper graph! |
| **Resource-Library** | `Librarian research-third-party-papers` (`g_50866a6f`) | **1,849.00 MB** | 8 | 118,769 | 7 | **1.85 GB `code.sqlite`** on a paper folder (likely indexed `.gg-w4-final-temp` / code inside research folder). |

*(Additional smaller graphs bring the totals to 6 graphs / 30.61 GB in NFL, 7 graphs / 15.72 GB in Parallax, and 17 graphs / 30.89 GB in Resource-Library. `geographer.log` also records recurring `anyio.ClosedResourceError` SSE writer errors: 16 in NFL, 12 in Parallax, 60 in Resource-Library.)*

---

## 4. Comparison Against the Workflow Graphs (Canvases) Created

Comparing the actual `G:\Libraries` execution logs against all four workflow canvases in `reports/`:

1. [ingestion.canvas](file:///d:/Librarian_V2/reports/2026-11-20-workflow-map/examples/ingestion/ingestion.canvas) (as-is DataManagement)
2. [accepted-ingestion-tobe.canvas](file:///d:/Librarian_V2/reports/2026-11-20-workflow-map/examples/ingestion/accepted-ingestion-tobe.canvas) (to-be ingestion)
3. [enrichment-cycle.canvas](file:///d:/Librarian_V2/reports/2026-11-21-enrichment-baseline/enrichment-cycle.canvas) (comprehensive baseline)
4. [proposed-tobe-enrichment.canvas](file:///d:/Librarian_V2/reports/2026-11-22-proposed-tobe-enrichment/proposed-tobe-enrichment.canvas) (proposed to-be enrichment)

### 4.1 Side-by-Side Fidelity Matrix

| Process Aspect | Observed Reality in `G:\Libraries` Logs | `ingestion.canvas` (as-is) | `accepted-ingestion-tobe.canvas` | `enrichment-cycle.canvas` (baseline) | `proposed-tobe-enrichment.canvas` |
|---|---|---|---|---|---|
| **9 source stages** | Exact order confirmed across 94 batches (`validate → parse → read → lenses → data → relate → metadata → review → publish`). | **Inaccurate:** collapses all 9 into 3 cards (`a11`, `a12`, `a13`). | **Inaccurate:** same 3-card collapse (`a12`, `a13`, `a15`). | **Accurate** (steps 16–28), though Core lane interleaves unrelated cards visually. | **Accurate** (steps 5–18), cleanly scoped to enrichment. |
| **Execution concurrency & `publish` timing** | Sequential item loop; spend checked **before each item**; `publish` runs as stage 9 **inside** the per-item loop. | **Inaccurate:** parallel fork `f1` with spend tracking; `a13` Geo-Grapher placed *after* join `j1`. | **Inaccurate:** repeats `f1` parallel fork and post-join `a15` Geo-Grapher. | **Accurate** (`a14`–`dmore` sequential loop; `a27`–`a28` inside loop). | **Accurate** (`a5`–`dmore` sequential loop; `a17`–`a18` inside loop). |
| **Approval vs. batch start** | `approve` only queues (`by: person`); `process_approved` (`by: curate`) starts each batch separately (`94` explicit starts). | **Missing:** `a10` approve jumps straight to `f1`. | **Missing:** `a11` approve jumps straight to `f1`. | **Accurate:** separates `a11` approval from `a12`/`startperson` start. | **Accurate:** treats approval as precondition, `a4`/`ownerstart` as start gate. |
| **Folder-metadata batch chain** | **0/12 succeeded** (`2` `FOLDER_PROVENANCE` in NFL, `10` `FOLDER_DRAFT_FAILED` in RL); `0` reached `folder_data`. | **Absent.** | **Absent.** | **Over-optimistic:** shows `fv → fd → fdata` as an established operational path without noting 0% observed completion. | **Scoped out** cleanly (noted as parent responsibility). |
| **Actor / tier execution** | **100%** of ingest/enrichment model work ran via legacy `clerk`, `cleanup`, and `ocr`. **0** Lead, Scribe, Oracle, Doctor, or ticket runs during ingest/enrichment. | **Mostly accurate** (Tier 0 + Core + Clerk + Model host + Geo-Grapher), though uses old `Clerk (tier 3)` label. | **Purely aspirational (to-be).** | **Misleading visually:** puts `data` (`a23`), `metadata` (`a25`), conversion (`conversionplan`/`work`/`review`) in Clerk/Scribe lanes and half the canvas in Oracle/Doctor/Lead with no visual as-is/to-be distinction. | **Explicitly to-be** (labeled proposal; cleanly separated from as-is). |
| **Actor attestation (F2)** | `652/652` accepts and `1,314/1,314` approves recorded `by: "person"`, even under `promotion.mode = "agent"`. | **Accurate** (documented as Finding F2 in `INGESTION-EXAMPLE.md`). | **To-be fix** ("attested as the policy"). | **Partially accurate** (claims true actor attestation via W7 code fix, though historical library data is still `by: "person"`). | **Scoped out** (acceptance is downstream). |
| **OP1 unaccepted backlog** | **750 processed sources** (`491+39` NFL, `2+3` Parallax, `160+55` RL) + **689 lenses** still stranded unaccepted. | **Narrow:** treats OP1 as resolved after DataManagement 96/96 accept; misses the other 750 stranded sources. | **Addresses OP1** via `x6` agenda alert (`16a`). | **Accurate** (`a31` backlog visibility), though doesn't reflect the 689 unaccepted lenses backlog in practice. | **Accurate** (names acceptance obligation in `a21`/`delivered`). |
| **`written but not findable` (`16a` / `35a`)** | **4 real occurrences** (`1` NFL, `3` RL), all failing Bottom-Line top-5 search with vectors off and 0 linked concepts. | **Inaccurate claim in companion doc:** `INGESTION-EXAMPLE.md` Finding F6 states `16a` was *"never exercised (anticipated)"*. | Models `17a` → Doctor `R5` (unimplemented). | Models `35a` → ticket (accurate trigger, unimplemented repair). | **Scoped out** (downstream promotion). |
| **Budget ceiling (`14a`) vs. user cancel** | **0 budget stops** ever triggered across all 94 batches; **8 manual cancellations** occurred. | Models `14a` ceiling reached; **omits manual cancellation**. | Models `14a` ceiling reached; **omits manual cancellation**. | **Accurate:** `14a` covers cancelled, interrupted, and ceiling stop together. | **Accurate:** `5b` covers cancelled, interrupted, and spending stop. |

### 4.2 Real Failure Modes in `G:\Libraries` Logs Missing or Misplaced in the Workflow Graphs

1. **`FOLDER_STALE` and `awaiting_accepted_folder` during enrichment `publish` (`68` times in Nonlinear Field Lab):**
   - `ingestion.canvas` (`3a`) and `accepted-ingestion-tobe.canvas` (`4a`) place stale-root failures **only** during initial folder survey.
   - In real execution (`batch-2026-11-16-38120a`, `c17c48`, `9f8181`), `FOLDER_STALE` (`41×`) and `awaiting_accepted_folder` (`27×`) fired at **stage 9 (`publish`)** inside enrichment batches, turning 68 otherwise-read PDFs into `partial`. (`enrichment-cycle.canvas` `28a` and `proposed-tobe-enrichment.canvas` `17b`/`18a` capture this generically, while `ingestion.canvas` misses it completely.)
2. **`GEOGRAPHER_CALL_FAILED` on `folder-accept` (`12` times across all 3 libraries):**
   - Observed in NFL (`5`), Parallax (`3`), and Resource-Library (`4`) during `folder-accept` operations, alongside `88` `anyio.ClosedResourceError` SSE errors in `geographer.log`. `ingestion.canvas` has no failure branch on `a7` ("accepts the remaining subfolders by policy"); `enrichment-cycle.canvas` adds `7a` (`dfolderapplied → ticket`).
3. **Provider HTTP 429 Rate Limits & Unpriced Batch Model Failures:**
   - Resource-Library hit DeepInfra `HTTP 429` during `pdf_to_markdown` (`3` `parse[partial]` items on 20 Nov) and `core` calls (`3`).
   - Parallax logged **`110` consecutive failed & unpriced `openai/gpt-oss-120b` calls** on 16 Nov (~40s timeouts) during `sensitivity` and `folder_brief`.
   - None of the canvases distinguish transient rate-limiting (`429`) or provider-wide route failure from per-chunk partial answers (`12a`/`13a`).
4. **Capture / Extraction Parser Crashes & Temp-Folder Queue Leaks:**
   - `KeyError: '/DescendantFonts'` crashed PDF capture in Nonlinear Field Lab (`queued-99f04cbb3c`), leaving a `failed` staged source with `file: ""`.
   - Hidden `.gg-w4-final-temp/pytest-*` files leaked into `Resource-Library/folder-sources.json` and into `Librarian research` graph indexing.
5. **Pre-Gate Unread PDF Publication & Missing Concept Projection:**
   - Because `Librarian research` PDFs were published on 16 Nov before the full-reading gate, **12 unread PDFs** sit permanently in `g_50866a6f` with **0 claims / 0 concepts**, and all **72** NFL papers sit in Geo-Grapher with **0 concepts**. None of the workflow canvases model a *schema/gate-evolution backfill* or *stale-generation graph rebuild* loop for already-published papers.

---

## 5. Summary Recommendations

1. **Resolve the Live Production Backlogs & Graph Inconsistencies in `G:\Libraries`:**
   - **Triage the 750 unaccepted processed sources** (`530` in NFL, `5` in Parallax, `215` in Resource-Library — plus `37` unapproved staged sources in Parallax and `689` unreviewed lenses) using the Core's acceptance/review tools.
   - **Re-read & republish the 40 `Librarian research` PDFs** in Resource-Library to replace the 12 zero-claim documents in `g_50866a6f`, and decide whether to re-publish Nonlinear Field Lab's 72 PDFs so their paper graphs gain concept links.
   - **Investigate the 4 `written but not findable` notes** (`PHASE_C_OPTION_B_N96_TRACE_20260625_003926`, `DeepInfra Model-to-Service Match - Capability Test Results`, `gemma-4-26B-A4B-it`, `Qwen2.5-72B-Instruct`)—all failed Bottom-Line top-5 search with `vectors: off` and no linked concepts.
   - **Fix `folder_describe` batch enrichment** (0/12 success across `FOLDER_PROVENANCE` and `FOLDER_DRAFT_FAILED`) before relying on the folder-metadata batch path.
2. **Address Geo-Grapher Storage & Extraction Defects:**
   - **Install/enable `tree_sitter` in `_geo-runtime`** so TypeScript/JS files (including `Librarian_V2/ui/src/*.ts` and `obsidian/src/*.ts`) stop failing AST extraction.
   - **Add snapshot/generation retention & WAL checkpointing** in Geo-Grapher: `77.23 GB` across 30 graphs (with `191` snapshots on a data folder, `19.5 GB` on a `docs` graph, `96` retained cumulative paper-DB copies = `873 MB` for a `16 MB` DB, and an uncheckpointed `1.67 MB` catalog WAL) is unsustainable and directly linked to OP2 full-group rebuilds.
3. **Align the Workflow Canvases With Observed Reality:**
   - Update `INGESTION-EXAMPLE.md` / `USE-CASES.md` to reflect that `written but not findable` (`16a`) **has occurred 4 times**, `FOLDER_STALE` occurs during `publish` (not just survey), and `GEOGRAPHER_CALL_FAILED` / `HTTP 429` are real observed failure modes.
   - Keep **as-is** and **to-be** canvases strictly separated: use [2026-11-22-proposed-tobe-enrichment](file:///d:/Librarian_V2/reports/2026-11-22-proposed-tobe-enrichment/README.md) as the scoped to-be enrichment proposal, rather than treating [enrichment-cycle.canvas](file:///d:/Librarian_V2/reports/2026-11-21-enrichment-baseline/enrichment-cycle.canvas) as an as-is representation of how `G:\Libraries` actually ran.
