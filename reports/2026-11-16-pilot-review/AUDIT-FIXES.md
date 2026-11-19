# Gemini audit: what was fixed, what is left (2026-11-17)

The owner had Gemini audit the three pilot libraries and both codebases. A review session checked
its claims against the code. This session then paused ingestion and made the fixes. Each item
below was checked in the code or reproduced first. Commits are on `feat/geo-per-library-service`
(Librarian) and `feat/per-library-service` (Geo-Grapher); none is pushed.

## Fixed

| Audit item | Fix | Commit |
|---|---|---|
| R3.1 Held or undecided folders leak into graph builds | The Librarian sends `withheld` paths; Geo-Grapher excludes them and each card's partition excludes | Librarian `f181d6f`, Geo `71c9b85` |
| R3.2–3 Leaks into the index, folder sources and reads | Inherited held cards count; in-vault notes are filtered; manifest excludes are honoured | `f181d6f` (plus `4e470c1`) |
| R4.1 Re-checks lower holds | A later "normal" check is recorded beside a hold, never in its place (re-survey stickiness was `5f5fb1e`) | `f181d6f` |
| R1 Long folder work inside the single writer | Acceptance and policy run beside the writer, under one folder lock; each write goes through the writer; survey walks happen before the writer is asked; draft and queue take the lock; atomic ledger | `f181d6f` |
| R2 Partial commits | A failed policy build restores `content-roots.json` | `f181d6f` |
| R2 Catalogue without WAL or busy timeout | `journal_mode=WAL`, `busy_timeout=5000` | Geo `71c9b85` |
| R4.3 Secret-file rules differ | Geo-Grapher takes the Librarian's `SECRET_*` rules | Geo `71c9b85` |
| M3 Markdown read as "p. 1", one chapter, no relate | Unpaged texts get "part N" and part-based chapters | `6125370` |
| 2.2 "Not confident" reported as "waiting for the Clerk" | Separate statuses | `6125370` |
| M5 Project READMEs refused as duplicates | Generic names become "<folder> - <stem>" | `6125370` |
| M4 The 40-bullet cap hides later parts | The cap draws evenly from every part | `6125370` |
| G4 Paper graphs without concepts or authors; unread PDFs published | Terms become section concepts; metadata comes from `fields`; publication waits for a full reading | `6125370` |
| R5 External attached files can't be accepted | Reproduced; the note now names the original in place and nothing is copied | `693448d` |
| G1/G2 Common-word mentions, one entity per comment line, notebook comment lines, the slow owner scan | Mention filter (code-marked words still link); comment blocks; unparsed cells skipped; per-file lookup; extractor version bumped | Geo `71c9b85` |
| Parallax's C/Rust/Go repositories planned as docs | `CODE_SUFFIXES` widened | Geo `71c9b85` |

**Tests:** Librarian full suite 2,657 passed; Geo-Grapher full suite 884 passed.

**Deployed:**
- Geo-Grapher wheel rebuilt and installed in `G:\Libraries\_geo-runtime\env`. The previous wheel is in `dist\previous\geo_grapher-0.2.0-before-71c9b85.whl`.
- All three Cores restarted on frozen `693448d`.

**Ingestion:** all three runners are paused.

## Left

1. **Relabel stored Markdown records. Done 2026-11-17 19:23, with no model calls.**
   - `run-scripts/relabel_md.py` ran through `run-scripts/migrate_one.py`, one library at a time, Core stopped and lease held.
   - Relabelled: 292 records in Resource-Library, 691 in Nonlinear Field Lab and 30 in Parallax (1,013).
   - 421 of them now have several chapters instead of one.
   - 7 records were left for a real reading, because a part is unread or its text changed.
   - Every changed file was first copied to `.librarian/migrations/relabel-unpaged-2026-11-17/`.
   - Tested first on a copy of Resource-Library: readings unchanged apart from locators, no other field changed, a second run finds nothing to do. Records that repeat a passage word for word keep each part's own reading.
   - Still open:
     - the relate step can now run on those 421 records, but only when they are processed again (a small Clerk cost);
     - staged lens quotes still carry their old "p. 1" locators;
     - the test copy `G:\relabel-test` is still on disk. The safety check would not let me delete it, so that is left to the owner.
2. **Rebuild the graphs, then prune.**
   - The new extractor applies only when a graph is rebuilt.
   - Parallax's 16 code repositories also need their decisions moved from `Parallax-third-party-docs` to the code graph `Parallax-third-party`. That is a re-accept, owner-instructed.
   - A rebuild adds a version to every graph. Version retention (keep current and previous) is not built yet, so pruning comes after the rebuild, as planned.
   - Hours of CPU; G: has the room (97 GB free).
3. **Not checked or not fixed:**
   - `[[...]]` links extracted from code files, and wiki-link resolution for workspace notes;
   - helper-tree contraction;
   - titles and topics: fixable later on stored records for a few cents;
   - links between code, doc and paper graphs: a feature, not a fix.
4. **Resume ingestion.** All three runners resume where they stopped, with the new reading rules.
