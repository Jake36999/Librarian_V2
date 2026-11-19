# Budgeted ingestion run: Nonlinear Field Lab (started 2026-11-16)

**Owner's instruction (2026-11-16):** $20 for the main architecture and internal docs, an extra $10 for supporting research docs. Focus on the most recent content, and run sequentially until the funds are spent if the pipeline looks solid. Internal docs are added as Sources, and they keep their own graph section, reasoned over separately and joined by the cross-graph analysis.

**Status: running.** This file is a snapshot. The live numbers are in the library's own logs, listed under "Checking progress" below.

## 1. What had to change first

The pipeline wasn't safe to leave running until the money ran out. These are the code changes, all on `feat/geo-per-library-service`:

| Commit | Change | Why |
|---|---|---|
| `bb4cb32` | The provider's own `estimated_cost` is kept on every call and counted by `[budget] ceiling_usd` | The ceiling counted only OCR and cleanup. Clerk calls logged tokens but no dollars, so a "spend until the funds run out" run would have overspent. |
| `bb4cb32` | `intake_run` stops at the ceiling and leaves the rest queued | Only the batch checked the ceiling; intake didn't |
| `bb4cb32` | Oversized reading points are kept, cut with "…", with the full text kept in the reductions. `points` and `limits` allow 240 characters and ask for equations, numbers and units verbatim. | The pilot discarded points on 8 of 10 papers, and only 43 of its 772 bullets carried math |
| `bb4cb32` | `own-docs` folders become Sources, and folders can be queued newest first | Owner decision above; before this, own docs were only indexed into the graph |
| `7590866` | Cleanup reports its progress only from the calling thread | Found in round 1. A progress report from a worker thread waited on the vault writer while the writer waited on the workers, and the Core froze. The pilot never reached this path because it OCR'd every page. |

**Verification:**
- Full suite in a clean clone with both commits: 2,591 passed, 2 skipped, 0 failed.
- The first suite run (code changes only) hit Windows process-start failures (exit 0xC0000142) late in the run. Re-running those 21 files gave 238 passed.

**Not pushed.** The branch has never been pushed, and it also holds the pilot session's commits.

## 2. Library settings for the run

Settings in `G:\Libraries\Nonlinear Field Lab\.librarian\config.toml` (backup: `config.toml.pre-run-20261116`):
- `[conversion] optical_all_pages = false`. A PDF's own text layer is used, cleaned up where needed, and OCR runs only where a page has no text.
- `[budget] ceiling_usd`:
  - $1 during the check run;
  - $20 for phase A (internal docs);
  - then phase A's spend plus $10 for phase B (research).

  The ceiling counts the library's total spend so far, not each phase's alone.

## 3. Check run (measured, before the full run)

| Set | Documents | Result | Cost |
|---|---|---|---|
| Internal docs, newest Markdown | 5 (about 50 KB) | 5 of 5 enriched | $0.020 (127 calls, all priced) |
| Research, newest PDFs | 2 (18 pages, text layer usable) | 2 of 2 enriched, read 7/7 and 9/9 chunks | $0.015 (about $0.0008 per page; no OCR or cleanup needed) |

**Reading quality:**
- Specific values and conditions are kept; for example "mediator storage decreases 3.278, matter gains 3.116".
- No point was truncated.
- Titles are still filenames and topics are still "Unfiled", as in the pilot. Those fixes (C6–C9 in `CORRECTIONS-SCOPE.md`) work from the stored records and need no re-read.

**Cleanup route, measured on its first PDF:** 3 parts for $0.0017, on DeepSeek-V4-Flash.

## 4. The run

`run-scripts/run_phases.py` drives the run through `run-scripts/run_ingest.py`. Each round:
1. queues the next 25 newest documents of a folder;
2. runs intake on them;
3. approves the Sources that round staged, but only normal-sensitivity ones; anything marked sensitive is held for a person;
4. runs the approved batch and waits for it;
5. logs spend.

**Phase A (internal docs).** All six own-docs roots, starting with `F:\quantule_mapper\docs` (721 Markdown files and 87 PDFs), then the five `colab_jobs` docs folders. Scope is `.pdf` and `.md`.

**Phase B (research).** `F:\quantule_mapper\external research`, PDFs only. That's 105 PDFs after the pilot's 10 and the check's 2; the vendored ROCm Markdown is left out.

**Throughput and projection:**
- Throughput is about 2.5 minutes per document, one document at a time.
- Measured cost is about $0.006 per document so far.
- On those figures, about 910 documents means roughly a day and a half and about $5–8 in total.
- **The $30 is not expected to run out on this library's content.**

**Interruption, round 1:** the deadlock in section 1. The Core was force-quit. That cancelled batch `batch-2026-11-16-828026` with 2 of 24 items done; the batch is resumable. The Core's process was ended after its command line was checked, the library restarted with a takeover, and the batch resumed on the fixed code.

## 5. Checking progress

- **Per round:** `run-scripts/ingest-log.jsonl` in the session scratchpad holds the round log, copied here at the end. It records items queued, approved, held, the batch result and the spend.
- **Spend, call by call:** `G:\Libraries\Nonlinear Field Lab\.librarian\runtime\usage-*.jsonl`, with `usd` on every priced call.
- **The batch:** the `batch_status` tool, or the library's Staging view.

## 6. Validation, and what it found (same day)

`run-scripts/validate_library.py` checks a library against its sources, read-only. It covers the content table, Geo graphs (existence and no leakage between graphs), Source separation by purpose, lineage (originals, digests, conversion binding, page locators) and the fidelity of sampled points against the **original** text at their locators.

**Nonlinear Field Lab, second pass (92 Sources):**

| Check | Result |
|---|---|
| Content table: roots declared and accepted | 52/52 |
| Geo graphs exist with entities; sampled entities belong to their own graph | 5/5 graphs, 125/125 entities |
| Sources only from doc and research roots, never code, data or logs | 92/92 |
| Originals present, digests match, conversions bound to the original's bytes | 92/92, 92/92, 41/41 |
| Every read part of a PDF has a page locator | **38/47**: the 9 below |
| Fidelity of sampled points | internal docs 163/163, research 44/46; median 1.0 of content words found at the locator |
| Papers in Geo-Grapher | **was 0**. Publishing now works: the first paper went to the third-party graph with 9 sections and 113 located claims |

**Fixed because of it** (committed, suite green):
- `335001a`: papers publish after reading, with located claims, agent-mode trust and free text-layer conversions.
- `46b5bbb`: a cleanup that lost page anchors is not used.
- *(pending commit)*: an inherited folder card defers to its accepted parent, and the 9 Sources read from an unmapped cleanup get new keys, so that only they are re-read, from the text layer.

**Prompt and setting change:** the 10 pilot papers re-read under the new reading prompts and settings, for about $0.003 each in Clerk calls. No OCR was repeated.

## 7. Resource-Library (owner, 2026-11-16: the rest of the $30, agent mode)

- **Settings:** promotion mode `agent`, `production_drafting` on and `third_party_graph = "project"`, all as the owner approved. The ceiling is held by `run-scripts/budget_supervisor.py`, which keeps both libraries' combined spend under $30.
- **Surveyed:** Librarian research, knowledge_compiler_engine, ToolSet and Resource-Library itself.
- **Seven folder decisions were overridden** where the suggestion contradicted the approved plan:
  - Librarian research: papers, not own code;
  - its QA archive: excluded;
  - the Resource-Library notes vault: own docs;
  - `internal docs`: own docs, not third-party;
  - `06-Papers\PDF's`: papers, not data;
  - canvases and design: excluded.

  These went through the person route under the owner's approval, so the records say `accepted_by: person`.
- **Accepted and built:** the three exclusions and Librarian research (its papers graph was built).
- **Ingesting now:** Librarian research's 114 PDFs, newest first.
- **Blocked by disk:** D: has 4.7 GB free, and Geo-Grapher refuses to build or publish below 5 GiB. Blocked so far: the Resource-Library notes vault, `internal docs`, `06-Papers\PDF's`, ToolSet, knowledge_compiler_engine, the Librarian_V2 survey, and all paper publishing in this library. `D:\Librarian_V2	mp` takes 58 GB.
- **Boundary leaks caught:** pytest fixture PDFs in a hidden scratch folder were queued as papers. Fixed in `f1398a5`; they were removed, and nothing was spent on them.


**Moved to G: (owner, 2026-11-16).** The vault was moved from `D:\Resource-Library\.librarian-app` to `G:\Libraries\Resource-Library`:
- **Copy:** 7,444 files (1.88 GB), every one hash-verified.
- **Repointed:** the Geo catalog's graph row and the Host's library list; a backup of the list is at `libraries.json.pre-move-20261116`.
- **Old copy:** kept as the hidden `D:\Resource-Library\.librarian-app.moved-to-G-20261116`, which the survey excludes. Delete it when you're satisfied.
- **Orphan found during the move:** an orphaned Geo service from the old-code Core (started before `--parent-pid` existed) held the old folder open. It was identified by its command line and ended.
- **Graphs:** the three blocked overrides were re-applied, and their graphs built on G:.
- **Librarian_V2 surveyed:** 11,308 cards in 42 minutes, which is now disk-bound rather than CPU-bound. `tmp` is excluded and `docs` is own docs. `reports` still needs the plan's own-docs override.

**Blocked: Resource-Library has no working Clerk.** Its bound Clerk route, `Qwen/Qwen3.5-397B-A17B`, is refused by the Core's route gate. So every read queues ("waiting for the clerk model"), and only PDF cleanup has run, at $0.16. The cleanups are stored and will be reused.
- Rebinding needs the tier change, and that requires the person's lead-override checkpoint, because the lead (Seed-2.0-mini) isn't qualified. An agent may not approve that.
- Nonlinear Field Lab's Clerk was bound to `google/gemma-4-26B-A4B-it` by the owner on 2026-11-15; the restore record is `runtime/temp-clerk-binding.json`. Resource-Library has a matching restore record ready.
- **Also blocked behind the Clerk:** the folder checks for ToolSet and knowledge_compiler_engine, and with them their policy acceptance.

## 8. Not covered

- **Catalogue fixes C6–C9** (titles, topics, card sampling, foreign material). They apply to the stored records afterwards.
- **Acceptance into the catalogue** (`Sources/` notes) hasn't been run; records stay enriched in Staging.
- **The DeepInfra account balance doesn't move per call,** so it can't confirm spend at this scale. The usage log is the meter.

## Clerk reasoning effort (2026-11-16, evening)

The owner approved setting the Clerk's reasoning effort to "low". Measured first, on DeepInfra, with `run-scripts/effort_probe.py` (one fixed 190-token passage, 2 calls per setting, under $0.05 in all):

| Model | unset | "none" | "low" |
|---|---|---|---|
| gemma-4-26B-A4B-it (Clerk, scribe) | 120 tokens, $0.000054, 1.8 s | same as unset | 810 tokens, $0.00029, 8.7 s (thinking on) |
| DeepSeek-V4-Flash-0731 (cleanup) | 147 tokens, $0.000037 | same as unset | 720–1043 tokens, $0.00014–0.00020 (thinking on) |
| Qwen3.5-27B (OCR) | ~2100 tokens, $0.0055, 35–59 s (thinks) | 154 tokens, $0.00045, 4.6 s | not run |
| Qwen3.5-397B-A17B | ~1700 tokens, $0.0053 (thinks) | ~118 tokens, $0.00044 | not run |
| MiMo-V2.6-Flash (NFL lead) | 345–810 tokens (thinks) | ~145 tokens | not run |
| Seed-2.0-mini (RL lead) | HTTP 500 ClosedEndpoint | — | — |

On Gemma, "low" switches thinking on and costs about 5x more, so both libraries were set to `[reasoning] clerk = "none"` instead: the same tokens as today, pinned against a change of the provider's default. The Resource-Library Core was restarted to load `87c831b`. The NFL Core still runs older code and ignores the setting until its next restart, which changes nothing because "none" and unset measure the same. GLM-5.3 (`route_review`) is untouched: it reads only `[clerk] reasoning_effort_review`, and its card says unset means max.
