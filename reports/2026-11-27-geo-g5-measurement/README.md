# Geo-Grapher G5 Paper-Storage & Snapshot Growth Measurement (Read-Only, 27 November 2026)

**Scope:** Strictly read-only filesystem `stat()` inspection, `.librarian/runs/*.jsonl` stream scanning, `.librarian/staging/source/*.json` scanning, and scratch-copied read-only `catalog.sqlite` inspection across **5 libraries** (`m5-acceptance`, `Resource-Library`, `Parallax`, `Nonlinear Field Lab`, `E:\Librarian ACCEPT-02 Vault`).
**Non-destructive constraints observed:** **0** writable SQLite opens on live stores, **0** WAL checkpoints, **0** deletions, and **0** retention-policy changes on any live library. Note that `E:\Librarian ACCEPT-02 Vault\.librarian\geographer\catalog.sqlite` records `C:\Users\jakem\Librarian ACCEPT-02 Vault\...` paths internally (from its originating host location; `C:\Users\jakem\...` is outside the sandbox (`WinError 5`), while all files under `E:\Librarian ACCEPT-02 Vault\.librarian\geographer\graphs\` were measured directly on `E:\`).

---

## 1. Per-Library Active vs. Retained Storage Breakdown (`.sqlite`, `-wal`, `-shm` Separate)

At time of measurement, `G:\` (checked at `G:\Libraries\Resource-Library`) had `256,042,332,160` B total capacity, `154,987,630,592` B used, and `101,054,701,568` B (`~101.05 GB`) free.

| Library | Code DBs (`code.sqlite` / `-wal` / `-shm` B) | Active Paper DBs (`#`: `.sqlite` / `-wal` / `-shm` B) | Retained Paper DBs (`#`: `.sqlite` / `-wal` / `-shm` B) | Other Files (`#` / B) | Publish Events (`runs/*.jsonl`) | Max Receipt–`mtime` Δ |
|---|---|---|---|---|---|---|
| `m5-acceptance` (`G:\Librarian-work\m5-acceptance\library`) | `2`: `524,288` / `0` / `0` | `1`: `1,843,200` / `0` / `32,768` | `7`: `7,774,208` / `0` / `229,376` | `0` / `0` | `8` (`1:1` match) | `0.82 s` |
| `Resource-Library` (`G:\Libraries\Resource-Library`) | `17`: `32,242,814,976` / `41,232` / `491,520` | `2`: `18,485,248` / `0` / `65,536` | `106`: `910,761,984` / `0` / `3,473,408` | `15` / `480` | `108` (`1:1` match) | `0.94 s` |
| `Parallax` (`G:\Libraries\Parallax`) | `7`: `16,881,381,376` / `0` / `229,376` | `0`: `0` / `0` / `0` | `0`: `0` / `0` / `0` | `5` / `160` | `0` (`1:1` match) | — |
| `Nonlinear Field Lab` (`G:\Libraries\Nonlinear Field Lab`) | `6`: `32,594,702,336` / `0` / `196,608` | `3`: `10,739,712` / `0` / `98,304` | `69`: `263,389,184` / `0` / `2,260,992` | `6` / `192` | `72` (`1:1` match) | `0.94 s` |
| `E:\Librarian ACCEPT-02 Vault` | `20`: `5,558,272` / `94,792` / `655,360` | `14`: `12,464,128` / `0` / `65,536` | `32`: `20,246,528` / `0` / `1,048,576` | `2` / `64` | `46` (`1:1` match) | `0.90 s` |
| **Grand Total (`5` libraries, `20` paper-active graphs)** | **`52`**: `81,724,981,248` / `136,024` / `1,572,864` | **`20`**: `43,532,288` / `0` / `262,144` | **`214`**: `1,202,171,904` / `0` / `7,012,352` | **`28`** / `896` | **`234` (`1:1`)** | **`<= 0.94 s`** |

Key observation:
- Across all `234` `papers-native-*.sqlite` files (`1,245,704,192` B combined), only **`43,532,288` B** (`3.49%`) belongs to the **20 active** paper databases pointed to by `catalog.sqlite`, while **`1,202,171,904` B (`96.51%`)** plus **`7,012,352` B** of `-shm` sidecars sits in **214 retained** prior generations (**`28.62x`** aggregate storage amplification over active DBs).

---

## 2. Per-Graph Generation Series & Publish-Order Correlation

Every paper-active library exhibits an **exact `1:1` correlation** between the `N` `"stage": "publish"` records in `.librarian/runs/*.jsonl` and the `N` `papers-native-*.sqlite` files sorted by `mtime` (`max_dt <= 0.94 s` across all `234` generations). In every graph, `catalog.sqlite`'s active `paper_database` equals generation `#N` (the newest file), and file size increases monotonically on every publish in all multi-publish cohorts (`>= 2` generations) because each publish runs `old.backup(conn)` before inserting the new document.

| Library | Graph Label (`graph_id`) | Gens (`N`) | Active DB (`.sqlite` B) | Retained DBs (`N-1`: `.sqlite` B) | Retained `-shm` B | Total All Gens (`.sqlite` B) | Amp Ratio (`Total / Active`) | Mean Growth / Publish (B) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `Resource-Library` | `Resource-Library-DataManagement-third-party-papers` (`g_6c285e54da402a91d0f927e5`) | `96` | `16,736,256` | `898,371,584` | `3,112,960` | `915,107,840` | `54.68x` | `171,126.6` |
| `Nonlinear Field Lab` | `Nonlinear Field Lab-third-party-papers` (`g_a9124b8702db1b37fe89d040`) | `63` | `9,408,512` | `259,256,320` | `2,031,616` | `268,664,832` | `28.56x` | `147,456.0` |
| `Resource-Library` | `Resource-Library-Librarian research-third-party-papers` (`g_50866a6f700ab56477ba24a2`) | `12` | `1,748,992` | `12,390,400` | `360,448` | `14,139,392` | `8.08x` | `116,177.5` |
| `m5-acceptance` | `M5 Acceptance-third-party-papers` (`g_23ea902314b31769801651bc`) | `8` | `1,843,200` | `7,774,208` | `229,376` | `9,617,408` | `5.22x` | `196,022.9` |
| `Nonlinear Field Lab` | `Nonlinear Field Lab-third-party` (`g_2d94786a1c873083843c88bd`) | `7` | `946,176` | `3,801,088` | `196,608` | `4,747,264` | `5.02x` | `94,890.7` |
| `E:\Librarian ACCEPT-02 Vault` | `DM-09-MoE-Mechanisms-external` (`g_c9863b15487afc6ff64b8a92`) | `5` | `1,396,736` | `3,182,592` | `131,072` | `4,579,328` | `3.28x` | `217,088.0` |
| `E:\Librarian ACCEPT-02 Vault` | `DM-04-Graph-Linearization-external` (`g_cc3dd6635a8f3af939742796`) | `5` | `1,429,504` | `3,072,000` | `131,072` | `4,501,504` | `3.15x` | `249,856.0` |
| `E:\Librarian ACCEPT-02 Vault` | `DM-05-Entity-Alignment-external` (`g_ad6b155f18fab11d07382d9e`) | `5` | `1,314,816` | `2,813,952` | `131,072` | `4,128,768` | `3.14x` | `221,184.0` |
| `E:\Librarian ACCEPT-02 Vault` | `DM-08-Orchestration-Eval-baseline` (`g_9a68586e8b16ddeadc0a5d55`) | `5` | `1,015,808` | `2,613,248` | `131,072` | `3,629,056` | `3.57x` | `141,312.0` |
| `E:\Librarian ACCEPT-02 Vault` | `DM-06-Schema-ETL-baseline` (`g_59669a18f966d9c95d51d2fb`) | `5` | `1,101,824` | `2,289,664` | `131,072` | `3,391,488` | `3.08x` | `197,632.0` |
| `E:\Librarian ACCEPT-02 Vault` | `DM-01-KG-Classification-external` (`g_bf77416335f71eb485482dac`) | `4` | `1,224,704` | `2,162,688` | `98,304` | `3,387,392` | `2.77x` | `256,682.7` |
| `E:\Librarian ACCEPT-02 Vault` | `DM-03-Query-Routing-external` (`g_ee6a4b1bca9219caf1522de9`) | `3` | `983,040` | `1,073,152` | `65,536` | `2,056,192` | `2.09x` | `276,480.0` |
| `E:\Librarian ACCEPT-02 Vault` | `DM-07-Storage-Sync-baseline` (`g_0f293ec4cf498a39cb1b381b`) | `3` | `868,352` | `1,011,712` | `65,536` | `1,880,064` | `2.17x` | `221,184.0` |
| `E:\Librarian ACCEPT-02 Vault` | `DM-02-Multilayer-Weighting-external` (`g_3fd397fa30afb8328a103c8a`) | `3` | `598,016` | `794,624` | `65,536` | `1,392,640` | `2.33x` | `124,928.0` |
| `E:\Librarian ACCEPT-02 Vault` | `DM-07-Storage-Sync-external` (`g_4130d279ef4554f476051923`) | `2` | `696,320` | `446,464` | `32,768` | `1,142,784` | `1.64x` | `249,856.0` |
| `E:\Librarian ACCEPT-02 Vault` | `ACCEPT-02 Testing Library-DataManagement-baseline` (`g_1b2d94d0a79987dfa563eb9e`) | `2` | `520,192` | `425,984` | `32,768` | `946,176` | `1.82x` | `94,208.0` |
| `E:\Librarian ACCEPT-02 Vault` | `DM-02-Multilayer-Weighting-baseline` (`g_e0ab9702af4e21206431ff55`) | `2` | `520,192` | `360,448` | `32,768` | `880,640` | `1.69x` | `159,744.0` |
| `Nonlinear Field Lab` | `Nonlinear Field Lab-quantule_mapper-docs` (`g_01dcacd594418860e29508c8`) | `2` | `385,024` | `331,776` | `32,768` | `716,800` | `1.86x` | `53,248.0` |
| `E:\Librarian ACCEPT-02 Vault` | `ACCEPT-02 Testing Library-DataManagement-external` (`g_8daf20e7826dde6eb4072258`) | `1` | `348,160` | `0` | `0` | `348,160` | `1.00x` | `0.0` |
| `E:\Librarian ACCEPT-02 Vault` | `DM-03-Query-Routing-baseline` (`g_f4e21f8c23ad6e510dc60e48`) | `1` | `446,464` | `0` | `0` | `446,464` | `1.00x` | `0.0` |

Note on `staging/source/*.json`: `8/8` (`m5-acceptance`), `1/584` (`Resource-Library`), `0/775` (`Nonlinear Field Lab`), `0/91` (`Parallax`), and `63/96` (`E:\Librarian ACCEPT-02 Vault`) retained explicit `papers-native-*.sqlite` strings in source cards, whereas `.librarian/runs/*.jsonl` retained the complete `234 / 234` publish sequence across all libraries.

---

## 3. Estimated $O(N^2)$ Growth Projections (Explicitly Labeled Estimates)

**Observed cohort size:** `5` libraries overall, `20` paper-active graphs across `4` libraries, and `234` cumulative publishes. The two largest single-graph cohorts used to parameterize the **Estimated** forward projections below are `Resource-Library-DataManagement-third-party-papers` (**cohort `N = 96`**, initial generation `479,232` B, mean step growth `171,126.6` B/publish) and `Nonlinear Field Lab-third-party-papers` (**cohort `N = 63`**, initial generation `266,240` B, mean step growth `147,456.0` B/publish). These projections are **estimates** assuming unpruned full-DB copy-on-publish growth at the observed linear per-paper size delta and excluding `-wal`/`-shm` sidecars.

| Parameterized Cohort (Observed `N`) | Target Publishes (`N`) | **Estimated** Active DB Size | **Estimated** Cumulative Unpruned Size ($O(N^2)$) | **Estimated** Retained Unreferenced Bytes | **Estimated** Amplification Ratio |
|---|---|---:|---:|---:|---:|
| `Resource-Library-DataManagement` (cohort `N = 96`) | `100` | `17.42 MB` | `895.00 MB` | `877.58 MB` | `51.4x` |
| `Resource-Library-DataManagement` (cohort `N = 96`) | `250` | `43.09 MB` | `5,446.12 MB` (`~5.45 GB`) | `5,403.03 MB` | `126.4x` |
| `Resource-Library-DataManagement` (cohort `N = 96`) | `500` | `85.87 MB` | `21,587.66 MB` (`~21.59 GB`) | `21,501.79 MB` | `251.4x` |
| `Resource-Library-DataManagement` (cohort `N = 96`) | `1,000` | `171.43 MB` | `85,956.97 MB` (`~85.96 GB`) | `85,785.53 MB` | `501.4x` |
| `Nonlinear Field Lab-third-party-papers` (cohort `N = 63`) | `100` | `14.86 MB` | `756.53 MB` | `741.67 MB` | `50.9x` |
| `Nonlinear Field Lab-third-party-papers` (cohort `N = 63`) | `250` | `36.98 MB` | `4,656.13 MB` (`~4.66 GB`) | `4,619.15 MB` | `125.9x` |
| `Nonlinear Field Lab-third-party-papers` (cohort `N = 63`) | `500` | `73.85 MB` | `18,528.26 MB` (`~18.53 GB`) | `18,454.41 MB` | `250.9x` |
| `Nonlinear Field Lab-third-party-papers` (cohort `N = 63`) | `1,000` | `147.57 MB` | `73,920.51 MB` (`~73.92 GB`) | `73,772.94 MB` | `500.9x` |

Implication for `G:\` (`~101.05 GB` free): a single unpruned paper graph approaching `~1,000` sequential paper publishes under copy-on-publish consumes `~74–86 GB` of unreferenced prior generations alone (more than half of remaining free space on `G:\`). Adding a retention policy (or switching to single active mutable paper storage with transactional rollback) caps steady-state paper storage near `(1 + K) * active_size` where `K` is the retained rollback count.

---

## 4. 11-Row Incremental Safety Matrix & G4/G5 Gate Mapping

Reference: `reports/2026-11-25-systems-analysis-finalisation/geo-grapher/to-be/incremental-safety.md`. All 11 safety cases are implemented on Geo-Grapher local branch `feat/g4-incremental-groups` (`G:\Librarian-work\geo-grapher-g4` at `de97dbe504469f17901caeecbf6e211301f26553`, `de97dbe`, branched from `0dcfb9a`) with opt-in pruning disabled by default (`allow_prune=False` / `keep_last=None`), while live libraries on `G:\`, `E:\`, and `m5-acceptance` remain untouched under G5 read-only measurement.

| Row | Safety Case | Implementation Scope / Module | Default Behaviour | Disposable-Store Acceptance Test (`tests/test_incremental_safety.py`) | Gate / Owner Decision Status |
|---:|---|---|---|---|---|
| 1 | A file is deleted | **G4** (`incremental.py`, `folder_review.py`, `receipts.py`) | Active snapshot drops entities + records tombstones; pinned prior snapshot retains old entities | `test_row1_delete_file_records_tombstone_and_preserves_pinned_snapshot` | Implemented & tested in G4 |
| 2 | A file is renamed or moved | **G4** (`folder_review.py`, `graph_catalog.py`, `bridges.py`) | Content-SHA 1:1 unique match writes `entity_identity_map`; ambiguous duplicates stay unaliased | `test_row2_unique_rename_preserves_resolution_and_pinned_history_while_duplicates_stay_ambiguous` | Implemented & tested; **Owner criterion decision open** (snapshot-scoped map vs literal `entity_id`) |
| 3 | The parser version changes | **G4** (`incremental.py`, `pipeline.py`, `folder_review.py`) | Parser/normalizer mismatch invalidates normal-form reuse; forces full reparse and records both versions | `test_row3_parser_version_bump_reparses_all_files_and_records_both_versions` | Implemented & tested in G4 |
| 4 | A write is interrupted | **G4** (`store.py`, `pipeline.py`, `graph_catalog.py`, `folder_review.py`) | Single SQLite `atomic_transaction` + `publication_tickets`; dead-PID crash leaves active snapshot untouched & reconciles `'aborted'` | `test_row4_interrupted_write_rolls_back_snapshot_and_records_ticket`, `test_publication_boundary_crash_after_snapshot_commit_before_catalog_update` | Implemented & tested across real killed subprocesses |
| 5 | Snapshots / paper generations are retained or pinned | **G4 + G5** (`folder_review.py:prune_snapshots`, `library_papers.py:prune_paper_generations`, `graph_catalog.py`) | Pruning is **disabled by default** (`allow_prune=False`); explicit opt-in preserves active + rollback + pinned | `test_rows5_and_11_retention_disabled_by_default_and_explicit_prune_keeps_pinned_and_rollback`, `test_row8_and_11_paper_cas_retry_preserves_both_concurrent_imports_and_double_conflict_refuses` | Opt-in implemented & tested in disposable stores; **Owner retention policy `K` pending** |
| 6 | Two applications at once | **G4** (`locks.py`, `folder_review.py`) | Per-group non-blocking lock refuses second same-group apply (`GROUP_LOCKED`); `bounded_concurrency_slot` + `catalog_write_lock` allow distinct groups in parallel | `test_row6_same_group_refused_concurrently_and_different_groups_run_in_parallel`, `test_row6_cross_process_parallel_different_groups_share_catalog` | Implemented & tested across parallel OS processes |
| 7 | The disk is short | **G4 + Paper** (`folder_review.py`, `library_papers.py`) | Pre-write 5 GiB reserve check (`DISK_RESERVE`) against delta/paper size refuses before writing | `test_row7_disk_reserve_refuses_group_and_paper_before_writing` | Implemented & tested in G4 |
| 8 | Graph row changed during paper import | **G4 / Paper** (`library_papers.py`, `graph_catalog.py`) | Catalog CAS (`paper_database IS ? AND snapshot_id IS ? AND profile_json=?`) retries once, then raises `PAPER_CAS_CONFLICT` with zero orphans | `test_row8_and_11_paper_cas_retry_preserves_both_concurrent_imports_and_double_conflict_refuses`, `test_row8_double_cas_conflict_refuses_cleanly` | Implemented & tested in G4 |
| 9 | A paper import is interrupted | **G4 / Paper** (`library_papers.py`, `graph_catalog.py`) | Candidate tracked in `paper_import_staging`; dead-PID cleanup removes only unreferenced dead staging candidates, preserving active + legacy files | `test_row9_interrupted_paper_import_cleans_only_dead_staging_preserves_active_and_legacy` | Implemented & tested across killed subprocess |
| 10 | Other groups refer to what changed | **G4** (`folder_review.py`, `bridges.py`, `lineage.py`) | Cross-group references resolve dynamically at read time; `target_groups` leaves siblings intact and handles moves/exclusions without stale membership | `test_row10_and_target_groups_preserve_siblings_run_lineage_sweep_and_handle_moves` | Implemented & tested in G4 |
| 11 | Retention numbers not yet decided | **G4 + G5** (`folder_review.py`, `library_papers.py`) | Safe default keeps all snapshots and paper generations (`disabled=True`) with zero automatic deletion on live or test stores | Covered alongside Row 5 in `test_rows5_and_11_*` and `test_row8_and_11_*` | Default safe behaviour verified; **Owner policy decision pending** |

---

## 5. Verification Before Commit

- **G5 live-store guard:** **0** live SQLite databases opened writable, **0** WAL checkpoints, **0** live files deleted, and **0** retention settings changed.
- **Geo-Grapher G4 (`G:\Librarian-work\geo-grapher-g4`, `feat/g4-incremental-groups` at `de97dbe`):**
  - Targeted G4 + core groups (`test_incremental_safety.py`, `test_folder_groups.py`, `test_library_paper_publication.py`, `test_receipt_contract.py`, `test_lineage.py`): **`94 passed`**.
  - Full unit suite in isolated scratch venv (`tests -m "not integration" -rs`): **`978 passed, 3 failed [test_qa_cleanup.py mklink /J Access is denied in sandbox], 5 skipped, 2 deselected`**; unsandboxed `tests/test_qa_cleanup.py` **`7 passed in 0.28s`** (`981 / 981` runnable unit tests pass; hosted CI pending push authorization).
  - Public surface diff vs `0dcfb9a`: **`0` removed** modules/symbols/CLI subcommands/HTTP routes/MCP tools; `git diff 0dcfb9a -- contracts/` is **empty**; frontend `npm ci && npm run build` **`✓ built in 672ms`**.
- **Librarian clean-clone checks (`audit/branch-vs-master`):**
  - `scripts/regression_audit.py compare`: `0 difference(s) to account for; 0 tool(s) added` (`201 tools, 172 modules, 98 routes, 86 rules`).
  - Clean-clone `pytest tests/test_*.py`: **`2933 passed, 2 skipped, 5 deselected in 768.19s (0:12:48)`** (`0` failed).
