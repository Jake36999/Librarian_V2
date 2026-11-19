# Folder changes during a live run: what broke and a hardening plan

2026-11-17, agent Claude. Trigger: the owner asked to move Parallax's 7 vendor datasheets out of
`docs` into a subfolder. The move itself took one second. Getting the library to recognise it took
three hours. Along the way it killed two ingestion runners, cleared six held folders' review flags,
and silently lowered one. Nonlinear Field Lab's move of 70 PDFs on 2026-11-16 hit the same problems.

Evidence tags: **measured** (seen in logs, timings or code), **inferred** (reasoned, not yet proven).
Code references are to the Core source at `ea6bda2`.

## What happened

| Time | Event | Tag |
|---|---|---|
| 09:03 | 7 PDFs moved to `docs/vendor_datasheets` (same-drive rename) | measured |
| 09:03–09:11 | Re-survey of `F:\network_management`: 466 s, 15,543 folder cards | measured |
| | The root (`.`) and `docs` lost their accepted decisions | measured |
| | The 7 held repositories lost their `review_required` flags | measured |
| 09:12 | Clerk check of `.` and `docs` failed with `FOLDER_DRAFT_FAILED` (no reason, no usage record) | measured |
| 09:12–09:20 | Accepting the 7-file subfolder re-walked the whole 180,000-file root | measured |
| 09:29 | Parallax runner died: `batch_status` timed out after 600 s | measured |
| ~10:30 | Second Clerk check also timed out after 600 s | measured |
| 10:56 | Checks finally ran, after the Core's batch finished | measured |
| 10:56 | `openclaw-ruview-presence-main` came back `normal`; it was `review_required` before | measured |
| 10:56 | Policy acceptance returned HTTP 400 (body not captured by my script) | measured |
| 11:4x | Resource-Library runner died the same way: `staging_list` timed out | measured |
| 11:4x | A restart was then refused: "8 person calls" still in flight | measured |
| 11:50 | Parallax Core: one thread at 0.78 CPU, 14,500 CPU s since 06:11; `batch_status` took 168 s | measured |

## Causes

1. **Every folder operation re-walks the whole source root.**
   - `FolderReview.accept` calls `deploy_survey.survey(card['source_root'])` (folder_review.py:369), then filters to the one folder. This happens even when that folder holds 7 files.
   - The survey and policy routes walk the root too.
   - Cost: 466 s for Parallax and 802 s for Nonlinear Field Lab, per call. **measured**

2. **That walk starves the Core.**
   - The Core is a `ThreadingHTTPServer`, but the walk is CPU-bound Python. It holds the interpreter lock for minutes, so other requests barely run: `batch_status`, `staging_list`, Clerk checks, the batch worker. **measured** (thread CPU, 168 s status read)
   - Clients time out, but the Core keeps doing the abandoned work. Retries pile up behind it: 8 person calls in Resource-Library. **measured** (count). **inferred** (that these were abandoned calls)
   - Resource-Library's slow `staging_list` (440 items, over 120 s) is not fully explained: its Core was not walking a root then. A stack sample is needed (see decisions).

3. **A folder's fingerprint covers everything beneath it** (`Subtrees.rows`, `digest(selected)`).
   - Moving 7 files inside `docs` therefore staled both `docs` and the root `.`. Any edit anywhere in a live project stales the root's decision.
   - Each stale decision needs a paid Clerk check and a policy pass. Until then the root is unaccepted. **measured**

4. **A re-survey throws away Clerk results for undecided folders, even unchanged ones.**
   - The old card is kept only if it is accepted or has a decision (folder_review.py:260). Otherwise a fresh card starts at "not examined".
   - The 7 held repositories were undecided by design, because they wait for you, so they lost their flags. **measured**

5. **The Clerk's sensitivity verdict is not stable, and a lower verdict lifts a hold.**
   - On re-check, `openclaw-ruview-presence-main` went from `review_required` to `normal`. A policy pass would now accept it without you. **measured**
   - Together with cause 4, a routine agent re-run can remove a person-level hold. **This is the safety issue.**

6. **A move is seen as a delete plus a new file.**
   - Identity is the absolute path: the `folder-sources.json` ledger keys and the staging item `file`.
   - Nonlinear Field Lab: 70 staged items pointed at vanished paths and had to be rejected by a hand-written script. That rejection failed until `b0387fa`. Their old ledger entries still dangle. **measured**
   - Parallax was spared only because none of the 7 PDFs had been queued.

7. **Failures are opaque.**
   - `FOLDER_DRAFT_FAILED` drops the Clerk result's status and problems (folder_review.py:337). The failed call wrote no usage record.
   - An in-process repeat of the same check succeeded, which points to a timeout under load. **inferred**

8. **My own tooling made it worse.** **measured**
   - The runners had no tolerance for a busy Core.
   - I ran folder operations while the runners were mid-round.
   - The budget supervisor walks every root each minute (about 1 min per pass, about 22,000 CPU s overnight) and rewrites each `config.toml` whenever a ceiling moves.

## Status (2026-11-17, evening)

- **Landed in `5f5fb1e`:** items 1, 4 and 5, with yellow flags for moves.
  - A re-survey tells a move or removal (decision kept, yellow `change` record) from new or edited content (re-review).
  - Decided subfolders no longer re-ask their parent.
  - Clerk results survive unchanged re-surveys, and a hold is lifted only by a person.
  - Staged sources and the ledger follow moved files.
  - **Open:** whole-folder renames, Geo-Grapher re-application for moved files, and deferred ingest entries.
- **Landed in `4e470c1`:** item 8 (held and undecided folders stay out of indexing), item 10 (index log capped and truncated), and cheap staging counts (optimisation item 2).
- **Open:** items 2–3 (subtree-only fingerprint checks; long folder work as background jobs), 6, 7, 9 and 11.

## Hardening plan (in order)

Each item lands with its tests, a §19 plan entry, and a full suite in the clean clone.

1. **Make holds sticky (safety; first).**
   - Keep a card's Clerk results (sensitivity, description, evidence) across re-surveys while its fingerprint is unchanged, decided or not.
   - Once a folder is flagged `review_required`, only a person can lower it. A later `normal` verdict on the same fingerprint is recorded but does not lift the hold.
   - *Done means:* tests show a re-survey keeps `review_required`, and a `normal` re-check leaves the folder held and unaccepted by policy.

2. **Check only the folder being decided.**
   - `accept` and `accept-policy` verify fingerprints by walking the card's own subtree (`source_root/path`), not the whole root.
   - *Done means:* a test with a large synthetic root shows that accepting a 7-file folder walks 7 entries.

3. **Take long folder work off the request path.**
   - Survey and policy run as background jobs, like `process_approved`, and return a job id. A second one for the same root gets `409 FOLDER_BUSY` with that id instead of queuing.
   - Status and list reads never wait on these jobs.
   - *Done means:* `batch_status` answers in under 1 s while a slowed survey runs (test with an injected slow walk).

4. **Narrow fingerprints to what a decision governs.**
   - A folder's fingerprint excludes subtrees that have their own decided cards. Moving files into a decided child, or editing inside one, no longer stales the parent or the root.
   - A new, undecided child shows up as its own card without resetting the parent.
   - *Done means:* the vendor-datasheet move, replayed in a test, leaves the root (`.`) accepted and stales only `docs`.

5. **Recognise moves.**
   - On survey, match vanished paths to new ones under the same root by size and sha256.
   - Carry over the ledger entry, the staging item's `file` and stages, and the source note, and record a `moved` event. Nothing is read again.
   - A vanished file with no match becomes a visible "source missing" item in review, not a silent dangling item.
   - Also add a person-route `/api/folders/move` that moves files and updates all of this in one serialized step, so no agent hand-rolls it.
   - *Done means:* a test moves 3 queued files and shows no new intake, updated paths and zero model spend.

6. **Say why things fail.**
   - `FOLDER_DRAFT_FAILED` carries the Clerk status and problems.
   - Every Clerk call writes an outcome record, failures included.
   - Policy errors carry their code.

7. **Write down the vault layout rule.** Add the owner's convention to `docs/product-contract.md`:
   - Visible folders hold only what a person uses (source summaries, their documents).
   - Granular analysis, graph data, metadata, memories and agent material live in dot-folders, which Obsidian hides.
   - Add a doctor check that flags agent material in visible folders.

## Operating rules until the plan lands (agents)

- Before moving files in an attached root: let that library's runner reach a batch boundary and stop it. Then move, survey once, check once, apply policy once, and resume.
- Never call folder routes while a runner is mid-round on the same Core.
- After any re-survey, compare every held folder's sensitivity with its pre-survey value. Treat a lifted hold as still held, and ask the person.
- Runners tolerate a busy Core and adopt sources an interrupted round staged. Done for Parallax and Resource-Library on 2026-11-17.
- The budget supervisor caches each root's document count and re-walks a root only when it changed, at most every 15 minutes. **Not yet done.**

## Disk: what the 20–30 GB per library is (measured 2026-11-17 12:20)

G: is 95% full (13 GB free). Each library's visible folders are tiny; everything sits in `.librarian`.
No original project files were copied into the libraries: `Sources/` holds 4 KB–1.4 MB.

| Library | Total | Geo-Grapher graphs | Search index | Index write-ahead log | Extracted text |
|---|---|---|---|---|---|
| Nonlinear Field Lab | 30 GB | 28 GB (largest 18 GB) | 1.0 GB | 0.8 GB | small |
| Resource-Library | 24 GB | 22 GB (largest 13 GB) | 0.8 GB | 0.8 GB | small |
| Parallax | 22 GB | 8.2 GB | 6.8 GB | 6.8 GB | 0.5 GB |

1. **The search index does hold project text.**
   - `derived/index.sqlite` keeps the chunked full text of every file it indexes, because "other own content is indexed whole" (§19). Parallax: 54,225 files, 1.7 GB of text, 1.5 M chunks. Nonlinear Field Lab: 4,459 files. Resource-Library: 2,598 files.
   - This is the copy the owner did not expect. The design intent is to read connected projects through client access.
2. **It indexed a repository held for review.**
   - 51,507 of Parallax's 54,225 indexed files are `linux-80211n-csitool-master` (`.c`/`.h`), indexed 07:22–07:50 today. Further held repositories are in there too: `mitmproxy-main` 986 files, `bettercap-master` 423.
   - Cause **(inferred)**: a held, undecided child has no root of its own, so the parent root's own-current decision ("index whole") covers it.
3. **The write-ahead logs were never folded back.**
   - Parallax's log is as large as its index (6.8 GB). The other two are about 0.8 GB each.
   - A checkpoint (SQLite folds the log into the index; nothing is lost) would free about 8.4 GB.
4. **Geo-Grapher graphs store structure, not file contents.**
   - The tables are entities, relationships, evidence and analysis results; there is no body column.
   - The 18 GB graph keeps 4 full generations (snapshot sets) of a roughly 150,000-entity graph, plus wide indexes on long string ids. Rows take about 4.6 GB; indexes take the rest.
   - Geo-Grapher has no snapshot-retention command. Its `prune` route derives a graph without some paths; it does not drop old generations.

Added plan items:

8. **Never index an undecided or held folder.** Folders held for review, or not yet decided, are left out of their parent's whole-content indexing until a person decides.
9. **Don't store connected projects' text.** Index connected project content by reference (path, offsets, hashes, an external-content full-text table) and read the text from the project on demand, through client access, instead of storing chunk text.
10. **Keep the write-ahead logs small.** Checkpoint the index's log after each indexing pass, and on a clean Core stop.
11. **Geo-Grapher snapshot retention (in the Geo-Grapher repo).** Keep the current generation and the one before it; delete older ones, then compact.

## Decisions for the owner

- **`openclaw-ruview-presence-main`:** keep it held for your review (recommended, per plan item 1), or take the new `normal` verdict.
- **Resource-Library's visible `model_tests/` folder:** agent test results and a test script from 2026-09-29. Move it under `.librarian/` to match the convention?
- **Stack sampling:** installing `py-spy` (from PyPI) into a scratch environment would let me sample a starved Core's threads and settle cause 2's open question.
- **Go-ahead to implement plan items 1–7** in `Librarian_V2`.
