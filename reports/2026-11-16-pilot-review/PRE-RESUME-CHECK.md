# Second pass before ingestion resumes (2026-11-17, evening)

The owner asked for a second pass before any more paid ingestion: look for mistakes like the
"p. 1" one, and for tasks dropped along the way. Everything here was measured on the three
libraries (read-only unless stated) with the Cores on `693448d`.

## Similar mistakes found, and fixed (no model calls)

| Found | Fixed |
|---|---|
| 503 staged lens quotes drawn from texts without pages still cited "p. 1" | 438 lenses relabelled by part: each quote was found in its source's current parts. The 8 left are from PDFs, where "p. 1" is a real page. Backups are in `.librarian/migrations/maintenance-2026-11-17/` |
| The 20 files quarantined for a generic name (README) were still in the folder-sources ledger, so the runners would never offer them again | Their ledger entries were removed, so the next round queues them under "<folder> - README" |
| Parallax's index stayed 7.3 GB after its held repositories' 53,000 notes were removed | Compacted to 4.9 GB (see "for the owner" below for the rest) |
| Compaction left the Parallax Core unable to start in the Host's 20-second window: at startup `folder_overrides` read all 15,543 folder cards (233 MB), about 7 s warm and longer cold | `folder_overrides` now reads the manifest, which acceptance already writes: 6.8 s down to under 0.01 s with the same result. Committed and pushed as `7cd530a` (full suite 2,657 passed). All three Cores now run it and restart in about 3 s |
| `openclaw-ruview-presence-main` was accepted by policy after a re-check lowered its earlier hold, and the Parallax runner would have read it | The Parallax runner skips it until the owner decides. Its folder decision is unchanged |

## Checked and clean

- **No live staged item points at a missing file**, and no file is held by two live items.
- **No enriched item has unread parts.** Every review stage still marked "waiting on model" (52 / 30 / 1) is on a partial item, so the runners' final retry of partial items covers them.
- **Every attached root has an accepted card.** The only folders held for review are Parallax's 6 repositories.
- **The new withheld rule leaves out only 3 Resource-Library documents**, all already queued before. All 1,639 of its withheld cards are suggested exclusions in `Librarian_V2\tmp`.
- **Index logs are empty**, and the 64 MB cap holds.
- **Validators** (`validate_library.py`, read-only) pass almost everything:
  - Resource-Library: 10 of 12 checks;
  - Nonlinear Field Lab: 12 of 14;
  - Parallax: 8 of 9.
- **The validator failures are explained:**
  - **Graph entities "in the wrong graph":** 19 in Resource-Library, 2 in Parallax. Each shares a name such as `README.md` or `POLICY.txt` with a file in another root, which is likely a false positive. The graphs are due a rebuild anyway.
  - **3 Resource-Library records** no longer match their file's bytes. Those files were edited after reading.
  - **One Nonlinear Field Lab PDF has part locators.** It is read from an unanchored conversion, which by design is labelled by part.
  - **2 third-party points don't match their source text.** They are model paraphrases, not a pattern.
- **Spend:** $7.68 of the shared $30 (Nonlinear Field Lab $5.20, Resource-Library $2.19, Parallax $0.29). The budget supervisor is running.

## What resuming will spend on (expected, inside the $30)

- **Partial items get retried.** The biggest group is Resource-Library's 43 items with unread parts, mostly the `E:\Librarian research` PDFs read before a Clerk route was working.
- **Their paper graphs get republished.** 12 of those PDFs were published with no claims. Once read, they are published again, but every publication still copies the whole paper database (audit R6, not fixed).
- **The 20 README files** are read for the first time.
- **The 421 records that now have several chapters** can have their chapters related when they are next processed (small Clerk cost).

## Dropped or open tasks

**Owner decisions:**
1. `openclaw-ruview-presence-main`: keep it accepted, or set it back to held.
2. The 6 Parallax repositories held for review.
3. Resource-Library's visible `model_tests/` folder: move it under `.librarian/`?
4. Parallax's Clerk is still Gemma. The restore record for `gpt-oss-120b` is `G:\Libraries\Parallax\.librarian\runtime\clerk-binding-2026-11-17.json`.
5. Own project data and logs are indexed whole. Parallax's index is still 4.9 GB, because one YAML file (92,002 chunks), a presence log (44,382) and several CSVs (about 36,500 each) are stored as text. Keep them out, cap them, or index by reference (optimisation item 7).
6. Edited own-docs are not re-read: the ledger offers a file once. Resource-Library has 3 such records now. Re-read changed files, or not?

**Work not done yet:**
7. Graph rebuild with the new extractor, with Parallax's 16 code repositories moved to the code graph, then version retention and pruning (Geo-Grapher).
8. `INGESTION-RUN.md` is due an update with today's results. It was planned for the end of the run.
9. Re-checking `D:\Librarian_V2` in Resource-Library: the repository changed a lot today. New files are queued anyway; its folder decisions are only re-asked on a re-survey.
10. **From the audit, not done:**
    - `[[...]]` links taken from code files;
    - wiki-link resolution for workspace notes;
    - helper-tree contraction;
    - titles and topics (C6–C9), fixable later on stored records for a few cents;
    - each paper publication copying the whole paper database.
11. **Hardening items still open:**
    - acceptance checks the whole project rather than the folder's own subtree (it now runs beside the writer);
    - whole-folder renames;
    - deferred ingest entries are not re-pointed after a move.
12. The test copy `G:\relabel-test` is still on disk. The safety check would not let me delete it.
