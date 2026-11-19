# Ten-paper ingestion pilot: independent review (2026-11-16)

**Scope.** This review covers three things:
- the Librarian's health after the Geo-Grapher integration;
- the ten-paper pilot in **Nonlinear Field Lab**;
- the claims made about the pilot by the agent that ran it, and by Gemini's blind review (parts 1 and 2).

**Method.** Every figure below was measured from:
- the staged records (`.librarian/staging/source/*.json`);
- the conversions (`.librarian/conversions/`);
- the run logs;
- the code on `feat/geo-per-library-service` at `f4947f3`.

The scripts used are in this session's scratchpad. Nothing was changed, promoted or re-run, and no paid calls were made.

## 1. Verdict

- **The pilot works as a reading pipeline.** All 198 pages were converted. All 116 chunks were read. Every point carries a page locator. The conversions match the PDFs' own text layers closely.
- **Its output is not ready to be the catalogue.** Problems found:
  - every title is a filename;
  - every topic is "Unfiled";
  - card summaries stop about halfway through long papers;
  - equations and table values are mostly absent;
  - nothing is corroborated or verified.
- **The full-run cost estimate rests on a wrong premise.** See section 4.

## 2. Health and the Geo-Grapher integration

| Check | Result |
|---|---|
| Full suite on `f4947f3`, fresh clone | 2,570 passed, 2 skipped, 0 failed (16 min) |
| Live Cores | Nonlinear Field Lab (pid 13204, older code) and Resource-Library both answer `/api/meta` |
| Per-library Geo services | Both running, each parented to its own Core; no orphans |
| Graph separation in Nonlinear Field Lab | 5 graphs: `quantule_mapper`, `-data`, `-docs`, `-logs`, `third-party` |
| Parallax and Resource-Library | Initialised, with 0 graphs (not populated) |
| Paper graphs | Written to `derived/paper-graph/`. **Not published:** every graph's paper database is empty |
| Resume blocker from Codex's audit | Fixed: a stage is reused only when logged `complete` (`batch.py:668`) |

**Two Geo lifecycle risks**, inferred from the code and not reproduced:
1. **Orphaned services.** `serve-graphs` doesn't watch its parent. A Core that crashes or is force-killed leaves its Geo service running. Reopening the library then starts a second service on the same catalog.
2. **Killing the wrong process.** `GeoService.stop()` always calls `_terminate()`. That kills the pid in `geographer-ready.json` even when Geo never started in this session. If the file is stale and Windows has reused the pid, an unrelated process is killed. `process_identity` already provides the needed identity check.

**Git.** The two masters have diverged:
- `origin/master` is one curated commit (`f8dc6b8`) on top of `c4eb76f`;
- local master holds the full history: 50 commits ahead and 1 behind.

The owner should decide which history is authoritative before the next push.

## 3. The claims, checked

Verdicts: **confirmed**, **partly** (right in substance, wrong in detail or degree), **wrong**, or **unverifiable** from current records.

### Gemini

| Claim | Verdict | Measured |
|---|---|---|
| 116/116 chunks read; every point page-anchored | confirmed | 116/116; 772 points and limits, all with locators |
| Vision OCR ran on PDFs whose intake said "usable, next: nothing" | confirmed | 3 PDFs (77 + 34 + 22 = 133 pages), recipe `visual-v3` on every page. The cause is `optical_all_pages`, a batch option (`batch.py:201`). |
| …and that OCR was unnecessary | partly | Mostly, but not wholly. The slide deck's page 74 is an image of a paper's abstract; only the vision pass captured it. |
| Titles are raw filenames on 6/10 (part 2: 7/8) | partly, understated | **10/10** titles and names equal the filename stem. Four happen to be readable. |
| Topic "Unfiled" on 10/10 | confirmed | 10/10 |
| Card `Claims` is the first 40 bullets, hiding later pages | confirmed | Hidden counts match exactly: 59, 40, 19, 12, 12 and 1. The last page cited on the cards is pp. 32–34 of 77, 15–17 of 34, and 14–15 of 22. |
| Equations written as pointers ("given by Eq. (38)") | partly, overstated | 8 of 772 bullets point at an equation or table. The bigger gap is absence: only 43 bullets carry any math at all. Rating quantitative content "4/10" is fair; blaming pointer prose for it is not. |
| Oversized bullets discarded, including mechanisms | confirmed | Discards on 8 of 10 papers. `aa38784` alone lost 11 points and 13 limits. The KLM drawbacks bullet was discarded. |
| LaTeX backslashes break JSON | confirmed | On 4 papers. The text is kept as literal source, not dropped silently. |
| IEEE author biographies extracted as claims (04404842) | confirmed | 7 biography lines at pp. 8–9 |
| Astronomy (SIDAM) abstract presented as a course claim | confirmed, with a correction | It is in the source, as an image on slide 74. It wasn't made up. It is a cited figure filed as the course's own claim. |
| `aa38784` has 4× duplicate discards | partly | 41 discards, 8 exact duplicates (repeats of 3–5×) from its four runs |
| Chunk keys out of order (bell) | confirmed, cosmetic | Key `2` is stored after `5`; the locators are correct |
| Positive claims misfiled as limits | mostly wrong | 3 exact overlaps between points and limits across all ten papers |
| 0/10 corroborated; 0 probes confirmed | confirmed | 0/10. 3 document proposals: 2 staged, 1 rejected by the grounding gate. |
| 6/10 skipped or stalled at relate | confirmed | 5 `not_applicable`, 1 `partial` |
| Cause: `relate` needs `#` headings | wrong | `dik.chapters` falls back to 10-page runs. The 5 papers are single runs (≤10 pages, or no headings), so there is nothing to relate. `aa38784` has two runs. |
| Fix: resolve `aa38784` to `not_applicable` | already in code | Added in `a65671c` (10:38, 2026-11-16), after the last batch (00:32), on the older Core. Re-running it under current code would clear it. |
| Cause of filename titles: metadata only fills empty fields | wrong mechanism, right outcome | The metadata stage never proposes a title; it proposes only `language` (`batch.py:436`) |
| `gpt-oss-120b` "avoids aliasing" error self-healed (part 2) | unverifiable | Not in current records; Gemini was likely given an earlier version |
| Part 2 figures (8 documents, 190 pages, `_2.json` files) | wrong population | The pilot is 10 records and 198 pages. Part 2 saw a different extract. |

### The pilot agent

| Claim | Verdict | Measured |
|---|---|---|
| 9 of 10 complete; `aa38784` honestly partial at relate | confirmed as stored | Its stated cause (page 11 has no claims) is right, and current code already resolves that case |
| OCR spend $0.605, about $0.0025 per page | confirmed, as a floor | 218 retained page receipts sum to $0.6054. Failed and cancelled calls are not counted. Clerk reading is unpriced. |
| "Conversions are faithful" (one paper checked) | confirmed more widely | Median word recall against the text layer is 0.90–1.00 on all ten papers; all 198 page markers are present. Word recall does not test equations. |
| "The pilot's ten papers were all scans, which made OCR look dominant" | **wrong** | None was a scan: 3 had a clean text layer and 7 needed cleanup, and all had text layers. OCR dominated because `optical_all_pages` was on. |
| Full PDF run ≈ $17 | **unsupported for the pilot's method** | Explained in section 4 |
| Usage log added | in code, not live | Pid 13204 runs older code, so no `usage-*.jsonl` exists yet |
| Suite green: 2,571 passed | consistent | 2,570 passed, 2 skipped here; the difference is one environment-dependent skip |

## 4. The cost estimate

**The estimate doesn't match the pilot's own conversion method.**
- The estimate is about $0.00094 per page: $6.4 for Nonlinear Field Lab's 6,834 pages. It assumes most pages get free text extraction, with vision OCR only on image-only pages (2–6%).
- The pilot used vision OCR on **every** page, at a measured $0.0025–0.003 per page.

**At the pilot's settings, OCR alone would cost** (receipts at the pilot's rate; Clerk reading excluded):

| Library | Pages | OCR at the pilot's rate |
|---|---|---|
| Nonlinear Field Lab | 6,834 | $17–21 |
| Resource-Library | 10,006 | $25–30 |
| Parallax | 204 | about $0.6 |
| **Total** | **17,044** | **about $43–51** |

**Turning `optical_all_pages` off doesn't make text pages free.**
- "Cleanup" PDFs go to `pdf_to_markdown`, a separate paid model route. That route is not in the new usage log and was never priced.
- Seven of the ten pilot papers were "cleanup".
- So the cheaper path has neither a measured cost nor a measured quality. The pilot proves neither.

### What a $30 budget covers (asked 2026-11-16)

**Rates:**
- **OCR:** $0.00306 per page, measured ($0.6054 over 198 pages, all-pages vision OCR).
- **Clerk reading:** $0.0005–0.0008 per page. This is the pilot agent's estimate; it was never measured.
- **All in, at the pilot's method:** about $0.0036–0.0038 per page, before failed and retried calls (which are not recorded).

**The pool.** The ingestion draws on the `geo-grapher` pool in `tmp/deepinfra-delegation/ledger.json`. It has a $20 ceiling, $12.38 committed and a $2 reserve. The pilot's own spend (about $0.7) was never booked to it.

| If $30 means… | Spendable on ingestion | Pages covered at the pilot's method | Share of 17,044 pages |
|---|---|---|---|
| the pool ceiling rises to $30 | about $15 | about 3,900–4,200 | **about 23–25%** |
| $30 of new money for the run | $30 | about 7,900–8,400 | **about 46–49%** |

**70–80% coverage at the pilot's method needs about $43–52**, with no margin for failures.

**By paper count the share is higher.** Resource-Library's 139 papers average about 72 pages each, mostly books. Nonlinear Field Lab plus Parallax is 231 of the 370 papers (62%) in 7,038 pages, about $25–27.

**Without all-pages OCR,** the cost depends on the cleanup route, which is unpriced. If the pilot agent's model is right (about $17 in all), $15 covers most of the run and $30 covers all of it. That is unmeasured, and so is the conversion quality on that path. The pilot only measured the vision path.

The agent's proposed second batch of five text-layer PDFs is the right next step. It should be run with `optical_all_pages` off, and with cleanup costs captured.

## 5. Enrichment quality

**Good enough for routing and comprehension.**
- From the records alone, Gemini reconstructed each paper's problem, method, setup, results and limits accurately.
- The page locators let an agent open the 1–2 pages it needs.
- The lens gates (stance, verbatim copy, two-part grounding) rejected bad proposals.

**Not yet a catalogue.** In order of impact:
1. **The card hides the second half of long papers.** The first-40 rule drops results and conclusions on 3 papers.
2. **Identity.** 10/10 titles are filenames and 10/10 topics are "Unfiled". The real titles and authors are in each record's opening text.
3. **Quantitative content.** Only 43 of 772 bullets carry math; tables are named but not extracted. Oversized-item discards remove some of the densest statements.
4. **Foreign material.** Author biographies and a cited figure's abstract are stored as the paper's own claims.
5. **No verification.** 0/10 corroborated and 0 probes confirmed. Paper graphs are unpublished, and their claims and concepts are empty.

## 6. Recommended order (all free unless noted)

1. **Restart Nonlinear Field Lab's Core on current code.** The pilot agent does this itself, as `docs/agent-guide.md` (Managing Cores) describes. Pid 13204 was started outside the Host. The agent checks it has no admitted work, ends it, and starts the library under the Host with a takeover. Then it re-runs `aa38784` to confirm it resolves. (Corrected 2026-11-16: this first said the owner must close the Core. Agents manage Cores.)
2. **Fix the catalogue fields before any large run:**
   - title and authors from the opening text, when the title equals the filename stem;
   - a card summary that samples every chunk, not the first 40 bullets;
   - drop biography and back-matter chunks;
   - mark cited figures as citations.
3. **Settle conversion before costing.** Decide `optical_all_pages` per library. Add the cleanup route to the usage log. Then run the five-paper text-layer batch (paid, small) and price from that.
4. **Close the Geo lifecycle risks** (orphan services and the pid check) before reopening libraries at scale.
5. **Then** the verification gate and paper-graph publication after reading, as Codex's audit already lists.

## 7. The material, for any further review

All under `G:\Libraries\Nonlinear Field Lab\.librarian\` unless stated:

| What | Where |
|---|---|
| Originals | `F:\quantule_mapper\external research\research_pdfs\` |
| Records (reading, card, review draft, discards) | `staging\source\*.json` |
| Conversions | `conversions\<hash>.md` (each record's `clean_file`); receipts and costs in `conversions\index.json` |
| Chapter and Data records | `derived\dik\` |
| Paper graphs (unpublished) | `derived\paper-graph\*.nodes.json` |
| Run logs | `runs\batch-2026-11-1[56]-*.jsonl` |
| Hashes of the originals | `G:\Libraries\_qa\pilot-source-hashes-recovery.json` |
