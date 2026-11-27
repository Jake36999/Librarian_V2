# M5 acceptance run: the fixed test folder, end to end (27 November)

The fixed test folder `E:\DataManagement\03-Retrieval-Routing-and-Graph-Query-Systems` holds 8 PDFs:
3 in `baseline/` and 5 in `external/`. It was brought into a new library through the Core, from survey to accepted notes. The Owner asked for this run on 27 November ("Run it").

**Result:** all 8 documents were surveyed, queued, captured, read, reviewed, published to the paper graph and accepted. Each accepted note carries its stored paper link. The ledger reconciles with nothing unaccounted.

- Spend: $0.154, from the approved budget.
- Time: 16 minutes.

The run found four faults. Each is fixed in this commit, with a test that fails on the previous code.

## How it was run

- **Library:** a new one at `G:\Librarian-work\m5-acceptance\library` (title "M5 Acceptance", promotion mode `person`). No existing vault was touched.
- **Geo-Grapher:** the wheel built from `feat/per-library-service` at 0dcfb9a (v1.2 receipts). It was installed in a separate runtime, `G:\Librarian-work\geo-runtime-m5\env`. The live `G:\Libraries\_geo-runtime` was not changed.
- **Models:**
  - Clerk and Scribe: DeepInfra `google/gemma-4-26B-A4B-it`.
  - Cleanup role: the default profile, `deepseek-ai/DeepSeek-V4-Flash-0731`.
  - The key was loaded into the run's own process only.
  - `[budget] ceiling_usd = 2.0` was set as a hard stop.
- **Driver:** an in-process `App` with `coordinate=True` (so the vault writer is live, as in the desktop Core). Every call went through `App.person_call`.
- **Person-only steps:** I ran these myself as the person, in this throwaway library: accepting each folder card, approving the sources into the batch, starting the batch, and accepting each read source. In a real library they stay with the person.
- **Script:** `G:\Librarian-work\m5-acceptance\run.py`. Its summary is in [data/summary.json](data/summary.json). It holds counts, paths and note names, and no source content.

**Steps, in order:**

1. `folder_survey`
2. `folder_accept` for each of the 3 cards:
   - `baseline` as research-docs, its suggested purpose;
   - `external` as third-party, its suggested purpose;
   - the root `.` as third-party (its suggestion was own-current).
3. `run_pipeline ingest-folder`
4. `staging_decide approve` for the 8 staged sources
5. `process_approved`
6. `staging_decide accept`, one source at a time
7. `ingestion_ledger`

## What it showed

| Check | Result |
|---|---|
| Folders surveyed / accepted / waiting | 3 / 3 / 0 |
| Documents in accepted reference folders / queued / not queued | 8 / 8 / 0 |
| Sources after the run | 8 accepted, 0 unaccounted (after fix 2) |
| Batch stages | 203 records. Every stage `complete`, except one `relate` that was `not_applicable` (IJES: fewer than two chapters hold substantive claims) |
| Text coverage | `full` for all 8, 5,485 to 15,986 readable words each |
| Publication (v1.2 receipt) | 8 `complete`, `document_id` doc:1 to doc:8, `cite_as` `M5 Acceptance-third-party-papers/doc:N` |
| Stored links (W-CIT-01) | All 8 notes carry `graph_paper` with their own receipt's `cite_as` |
| Stable ids across snapshots | Each publish wrote a new paper-database snapshot (8 in all). The latest holds all 8 under the same doc:1 to doc:8 |
| Findability (W-ACC-02) | All 8 catalogued; no reindex ticket opened |
| Open tickets | none |
| Calls into the Core | 21 person calls, 0 refused |
| Model calls | Clerk: 780 calls, $0.1315. Cleanup (`pdf_to_markdown`): 44 calls, $0.0224 |

**Readable titles (W-INT-01).** Two PDFs carry a real metadata title, and those were used: "Real-Time Text-to-Cypher Query Generation with Large Language Models for Graph Databases" and "Mixture-of-Experts Knowledge Graph...". The five arXiv files have no metadata title, so they read as their file names with underscores as spaces, for example "EXT O3 2405.14831 HippoRAG". The IJES paper is fix 3 below.

## What it found, and fixed

1. **`ingest-folder` was refused in the Core.**
   - The cause: `run_workflow`, `run_pipeline` and `run_resume` ran inside one vault-writer operation. So the pipeline's first orchestrating step, `folder_survey`, was refused with `ORCHESTRATION_CONTEXT`. Every orchestrating step would have been refused the same way.
   - Why the M5.1 test missed it: it ran without a writer.
   - The fix: the three runners are now orchestrators, like `macro_run`. Each step is still its own registry call and its own checked write.
   - Their access-review rows were refreshed: fingerprint and line only, with status and reason unchanged.
   - Tests: `test_ingestion.py::test_the_ingest_folder_pipeline_runs_in_a_core_with_a_vault_writer`, and the orchestrator allow-list in `test_macro_permissions.py`.
2. **The ledger lost every source once it was captured.**
   - A queued item keeps its document as `ref`, but capture moves it to `file`. The ledger read only `ref`, so `sources` was empty and all 8 documents were listed as unaccounted.
   - The fix: it reads `file` too. Re-read on the run's library, the ledger now shows 8 accepted and 0 unaccounted.
   - Test: `test_ingestion.py::test_a_captured_source_is_accounted_for_by_its_file`.
3. **A template placeholder was taken as a title.**
   - The IJES paper's PDF metadata title is the IEEE template's own "Paper Title (use style: paper title)", and the filler filter let it through.
   - The fix: placeholders like this are now filler, so the title falls back to the file name.
   - The note accepted in this run keeps the old title. Its graph document has it too, since Geo-Grapher read the same metadata.
   - Test: added to `test_m5_batch.py::test_a_file_source_gets_a_readable_title_and_keeps_its_name`.
4. **A stored link with a space in its graph label was not a citation.**
   - Graph labels are made from the library's title, and Geo-Grapher's `cite_as` repeats the label as is. So "M5 Acceptance-third-party-papers/doc:4" was refused by `graph_evidence.HANDLE`, which allowed no spaces.
   - Any library with a space in its title had stored links that did not resolve. "Librarian ACCEPT-02 Vault" is one.
   - The fix: the pattern allows inner spaces, but none at the label's edges. Geo-Grapher resolves a label by exact, case-blind match (`graph_router.resolve`), so it takes the label as written.
   - Test: `test_m5_batch.py::test_a_handle_whose_label_holds_a_space_is_a_graph_citation`.

## What this run did not cover

- **Resolving the stored links through the live Geo-Grapher MCP server.** That server connects only when the Core serves over HTTP, and this run drove the Core in process. The match was checked in Geo-Grapher's code and in the Librarian's unit test.
- **The oracle.** None was assigned, so the review went to the Clerk, as `_review_route` does without one.
- **Semantic metadata (W-REA-02).** It is not built; its design is the Owner's decision.
- **Starting the batch inside the pipeline.** It still waits for the commission. In this run the person steps came between the pipeline and the batch.
- **The supervised run in Resource-Library** that the plan's "old paths retire" rule also needs.
