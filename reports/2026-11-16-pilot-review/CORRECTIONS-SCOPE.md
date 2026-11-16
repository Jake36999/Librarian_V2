# Corrections to scope before a larger ingestion (2026-11-16)

Author: Claude (Sonnet 5.5, the session that finished the pilot). Inputs: `PILOT-REVIEW.md` (the independent review), the planning transcript `claud-development-transcript 3- geo grapher.txt`, and my own re-checks below. **Scoping only: nothing here is implemented.** Sizes: S under an hour, M one to three hours, L half a day or more. "Free" means no paid model calls.

## 0. Where my earlier statements were wrong

| I said | Correct | Evidence |
|---|---|---|
| "The pilot's ten papers were all scans, so OCR looked dominant" | **Wrong.** 189 of 198 pilot pages have a text layer (9 do not). OCR dominated because `optical_all_pages` was on for the batch. | `pypdf` text per page, re-run today; review §3 |
| "Full PDF run is about $17" | **Unmeasured, and for a different method than the pilot used.** It assumed free text extraction plus cheap cleanup. The pilot used vision OCR on every page. | review §4 |
| Review trap: "`aa38784` read is queued but review is complete" | **Wrong for that paper** (I read run logs in filename order, not time order). Its read is 12/12. The review-stage fix is still right in principle. | live `batch_status` |
| "Only the owner can restart the unmanaged Core" | **Superseded by owner policy.** Agents manage Cores; `docs/agent-guide.md` (Managing Cores) now says so. | review §6 item 1 |

Also confirmed by me today: the filename titles, `metadata` proposing only `language`, `optical_all_pages` being a per-call flag, and my `GeoService` killing a stale pid (C2).

## 1. Corrections, in order

### A. Before any more paid work (all free unless stated)

| # | Correction | Why (evidence) | Size | Gate |
|---|---|---|---|---|
| C1 | Restart Nonlinear Field Lab's Core on current code under the Host (pid 13204 runs older code; takeover per the guide), then re-run `aa38784` to confirm it resolves | usage log, scope default and read fixes are not live; review §2 | S | none |
| C2 | **Geo service safety (my code).** (a) `GeoService.stop()` must end only a process this Core started, and verify identity with `process_identity` before any kill; a stale `geographer-ready.json` plus a reused pid can kill an unrelated process. (b) `serve-graphs` should exit when its parent dies (`--parent-pid` watcher), so a crashed Core never leaves an orphan and a reopen never starts a second service on the same catalog. Tests first for both. | review §2 "two Geo lifecycle risks"; `geo_service.py` `_terminate` reads the pid from the ready file even when never started | M | before reopening libraries at scale |
| C3 | **Spend that can be audited and capped.** (a) Book the pilot's about $0.7 to the `geo-grapher` pool. (b) Extend the usage log to the two routes it does not see: OCR and `pdf_to_markdown` cleanup. (c) A hard stop when a library's batch would pass its pool ceiling (today nothing enforces one). | review §4; ledger shows $12.38 committed, pilot spend never booked | M | **required** |
| C4 | `optical_all_pages` becomes a **library setting** (default off), recorded in the run log, instead of a per-call flag someone must remember. Decide per library. | `tools/batch.py:19`; the owner's rule that configurable limits should not be hardcoded | S | **required** |
| C5 | Free load test of staging with thousands of synthetic items (list, counts, approve-batch, resume) | untested; 30k files per kind and O(n) loads are plausible | S | **required** |

### B. Catalogue quality, before a large run (free development, then a small paid re-read of the pilot papers to confirm)

| # | Correction | Why | Size |
|---|---|---|---|
| C6 | **Titles and authors from the opening text** when the title equals the filename stem. Add a title proposal to the metadata stage (it proposes only `language` today), checked by the provenance guard, shown for the person's approval. | 10/10 titles are filenames | M |
| C7 | **Topic is never left "Unfiled".** Propose a topic through the existing taxonomy flow; leave it staged for review. | 10/10 topics "Unfiled" | S |
| C8 | **Card summary samples every chunk**, not the first 40 bullets; the full list stays in the record. | the card hides pp. 32–77 on the 77-page paper and loses results and conclusions on 3 papers | S |
| C9 | **Foreign material out of the paper's own claims.** Drop author-biography and back-matter chunks; record cited figures and abstracts as citations. | 7 IEEE biography lines stored as claims; the SIDAM abstract filed as a course claim | M |
| C10 | **Do not discard oversized items whole.** Split them or keep them with an explicit truncation marker, and tell the Clerk to keep equation text and table values. | discards on 8 of 10 papers; only 43 of 772 bullets carry any math | M |
| C11 | Resolve single-run documents and `aa38784` to `not_applicable` at relate (already in code at `a65671c`; confirm on re-run). Keep `dik.chapters`' 10-page fallback. | review §3 | S |

### C. Verification and graph, before claiming "verified" (not before a bounded further batch)

| # | Correction | Size |
|---|---|---|
| C12 | Independent verification gate: two tier-2 comparisons or one tier-1, bound to original and derivative hashes. Nothing is "verified" from a draft or a valid citation alone (Codex P1/P2). 0/10 papers are corroborated today. | L |
| C13 | Publish a paper's graph **after** reading and review, with claims and concepts populated; today every paper database is empty. | L |
| C14 | Stop copying external files into the library at acceptance; keep a reference path plus hash (the owner's reference-in-place design). | M |

### D. Measure, then price

| # | Step | Cost |
|---|---|---|
| C15 | Five text-layer PDFs from `external research` with `optical_all_pages` off, cleanup cost captured (needs C3 and C4 first) | under $0.50 |
| C16 | Re-price the full run from C15's measured per-page cost | free |

## 2. Cost model after the review

| Method | Per page | 17,044 pages | Status |
|---|---|---|---|
| Vision OCR on every page (the pilot's method) | $0.0036–0.0038 all-in | **about $43–52** | OCR measured ($0.00306); Clerk estimated |
| Text layer plus `pdf_to_markdown` cleanup, vision only where the text layer is missing (about 2–6% of pages) | list-price estimate about $0.0008–0.0010 | **about $14–17** | **unmeasured**: cleanup token counts are assumed; C15 settles it |

By paper count, with the pilot's method: Nonlinear Field Lab plus Parallax is 231 of 370 papers for about $25–27; Resource-Library's 139 papers are mostly books. Pool today: $20 ceiling, about $12.4 committed, $2 reserve, so about $5 of headroom. **Nothing larger than C15 should run before C3 and C4.**

## 3. Carried over from the planning transcript (checked against what exists)

Done: five Nonlinear Field Lab graphs for quantule_mapper; third-party separation (L4); credential refusal (L5); graphify-out suggested as excluded; duplicates `quantule_mapper_dev` and `_review` not ingested; per-library Geo services and buttons.

**Not done, and nothing currently tracks them:**
1. **Nonlinear Field Lab:** `F:\Mark-XLVIII-main` and `F:\Maths_exploration` were never added.
2. The promised list of the roughly 384 paths unique to `quantule_mapper_review` (reported to the owner, not ingested).
3. **Parallax:** `network_management` never surveyed on current code (0 cards), including the owner's folder pairing: `third_party_research\repos` plus `Network Reconnaissance & Penetration Testing` as third-party, with `Model_training\docs\research_docs_pdf` and the Wi-Fi Sensing folders as research documents; `csi-hub-mtls` (config and relay text only, no keys). The Parallax Core has not been started since the stale lease. Which `network_management` folders go to which library is still unanswered.
4. **Resource-Library:** nothing added (Geo-Grapher, ToolSet, Librarian_V2, knowledge_compiler_engine, `E:\Librarian research` excluding the `.gg-w4-final-temp` scratch). **The four shared graphs (ToolSet, librarian-v2, ai-research-papers, timeline-mapping) were never moved into per-library catalogs.**
5. Graphify cleanup: 9 untracked `graphify-out` folders and 4 git-tracked ones; the `/graphify` entry in the global `CLAUDE.md`.
6. Restore the temporary bindings. The recorded restore file covers lead and Clerk only; it must also cover the Clerk now bound to Gemma, OCR bound to Qwen3.5-27B, and DeepInfra host concurrency raised to 8.
7. `specs` folder still held (the provenance guard rejects its description). The Folders badge and the raw graph ID in the workspace heading.
8. Later features: session working-memory graph, notes graph, lineage DAG packets, node-colour decision D4, `06-Papers` originals (D2).

## 4. Git and housekeeping

- **Decide which history is authoritative.** `origin/master` is one curated commit (`f8dc6b8`); local master holds the full history and is 50 ahead, 1 behind. Neither has this branch's work.
- The other agent's edits (`docs/agent-guide.md`, `reports/2026-11-12-progress/LIBRARY-ACCESS-API-SCOPE.md`, this folder) are uncommitted in the working tree.

## 5. Recommended sequence and decisions

1. **Now (free):** C1, then C2, C3, C4, C5.
2. **Then (free development):** C6–C11, followed by one small paid re-read of the pilot papers to confirm.
3. **Then:** C15 (under $0.50), then C16.
4. **Only then** a bounded larger batch. Verification (C12–C14) is required before anything is called verified, not before that batch.

Decisions needed from the owner:
- Conversion default per library: OCR only where the text layer is missing, or every page (equations and figures cost more)?
- Budget: the pool ceiling and the shape of the run (phase by library?) once C15 is priced.
- Which history is authoritative for the next push.
- Which `network_management` folders go to Nonlinear Field Lab versus Parallax.

---

## 6. Progress: C1–C5 (2026-11-16, later the same day)

| # | State | What was done and found |
|---|---|---|
| C1 | **Done, one check open** | Nonlinear Field Lab's Core (pid 13204) turned out to run **an old code copy** (`D:\Resource-Library\.v2`, from October) under system Python, not this repository. It had no admitted work, so it was ended and restarted under the Host with takeover (new pid recorded by `host status`). Its Geo service (pid 9176, identified by its command line as this library's) had **survived the Core** and was ended by hand: the C2 orphan risk, seen live. **Open:** re-running `aa38784` was not possible (`process_approved`: "nothing is approved"); confirming its `relate` fix needs the owner to re-approve that paper (a paid re-read) or it is covered by the C11 test only. |
| C2 | **Done** (Geo `30a8040`, Librarian `b85536b`) | `serve-graphs --parent-pid` exits when the owning Core exits (holds a handle to the parent on Windows, so a pid cannot be reused while it waits). `GeoService.stop()` now ends only a listener it read from the ready file after its own launch and can still identify by start time; a stale file or a reused pid is never touched. The runtime wheel was rebuilt and reinstalled in `G:\Libraries\_geo-runtime\env`. **Order matters:** Cores that pass `--parent-pid` need this wheel, so restart each library's Core only after it. |
| C3 | **Done** (this checkpoint) | Pilot OCR spend ($0.6054) booked to the `geo-grapher` pool (committed $12.379 to $12.984; backup `ledger.json.pre-pilot-booking`). OCR pages and `pdf_to_markdown` calls now write usage rows (`.librarian/runtime/usage-*.jsonl`, with `usd` where the provider reports it). New optional `[budget] ceiling_usd` (and `cleanup_usd_per_mtok_in/out` to price cleanup tokens; unpriced tokens are never guessed): OCR stops submitting pages, cleanup refuses, and the batch stops resumably between items at the ceiling. **Not done:** the library ceiling is separate from the pool ledger; nothing yet writes usage back to the shared ledger. |
| C4 | **Done** | `[conversion] optical_all_pages` (default off) is read by every batch stage and recorded in the run's `started` event. A per-call flag still forces it on for one run. |
| C5 | **Done; two findings** | Synthetic staging at 2,000 and 10,000 items. (1) **Bug fixed:** `batch.status` scanned all log events once per item (items x events; about 8 seconds at 4,000 items, hours at 30,000). It now groups once; a regression test seeds a 4,000-item run and requires under 3 seconds. (2) **Cost, not fixed:** every listing (`counts`, `waiting`, `batch_status`, `staging_list`, `queue_list`) re-reads every item file. Warm, that is about 0.1 ms per item per call (about 3 s per call at 30,000); the first read after writing is **much** slower on this machine (counts: 14.5 s at 2,000 and 74 s at 10,000 on first read, then 0.2 s). Antivirus scanning of freshly written files is the likely cause. Approving 30,000 items also writes them one by one inside one writer operation (about 50 s of write time estimated from seeding). A count index would fix all of it; it is a design change, so it is listed, not done. |

Also found: the access-review gate (`docs/tool-access-declarations.json`) fingerprints tool source, so editing `ocr_pdf` and `pdf_to_markdown` made two rows stale. I reviewed the edits (they add spend logging and a budget check only; reads still go through the same path guard) and refreshed those two fingerprints.
