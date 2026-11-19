# Storage and speed: optimisation proposal

2026-11-17, agent Claude, measured on the three pilot libraries (G:\Libraries). Companion to
[FOLDER-CHANGE-HARDENING.md](FOLDER-CHANGE-HARDENING.md), whose disk section has the first
breakdown. Figures are **measured** unless marked **est.** (estimated from row shares).

## Where the space is

| Store | Size now | What fills it |
|---|---|---|
| Geo-Grapher graph stores (15 large graphs) | 69 GB | Every acceptance writes a whole new version of a graph, and old versions are never dropped |
| Librarian search indexes | 9.1 GB + 8.4 GB unmerged logs | Full chunk text of indexed project files, stored twice |
| Folder cards | 233 MB (Parallax), 85 MB (Resource-Library) | Each card stores every file row of its whole subtree |

Graph versions kept (distinct snapshot sets):

| Graph | Size | Versions | Notes |
|---|---|---|---|
| Resource-Library-docs | 13.1 GB | 9 | |
| Nonlinear Field Lab-quantule_mapper | 8.4 GB | 6 | Several versions identical |
| Nonlinear Field Lab-quantule_mapper-docs | 18.5 GB | 4 | Two identical versions of 296,905 entities each |
| Parallax-third-party-docs | 9.3 GB | 2 | Second version being written at 12:40 by a policy pass; it added one repository |

Unchanged repositories are copied into every new version, not referenced: the same `working-tree` revision appears again and again.

## Where the time goes

| Operation | Cost | Why |
|---|---|---|
| `staging_list` (any kind) | 9.4 s Parallax, 2.1 s Resource-Library, uncontended | It calls `counts()`, which parses every staging file of every kind, folder cards included (staging.py:164). Listing the sources alone takes 0.0–0.1 s. Runners call it several times per round. |
| Folder survey / accept / policy | 466–802 s per call | Re-walks the whole source root (see the hardening report) |
| Budget supervisor (my tool) | about 1 min per pass, about 0.5 CPU core around the clock | Walks every root each minute |

## Proposals, in recommended order

| # | Change | Where | Saves | Effort |
|---|---|---|---|---|
| 1 | **Merge index logs back.** Checkpoint after each indexing pass and on clean stop; set `journal_size_limit`. Same for Geo-Grapher's stores (a 3.3 GB log now). | Librarian; Geo-Grapher | about 8.4 GB now plus Geo logs; stops a log from growing to the index's size | Small |
| 2 | **Cheap counts.** `staging_list` with a `kind` counts only that kind. Folder-card counts come from a small summary file kept current on save. | Librarian `staging.py` | 9.4 s → under 0.1 s per list call; removes most Core starvation from runners | Small |
| 3 | **Lean folder cards.** Keep the survey rows once per root (`folder-surveys.json` already holds the survey). Each card keeps only its digest, counts and bytes. | Librarian `folder_intake` / `folder_review` | 233 MB → a few MB (est.); faster card list and survey | Medium |
| 4 | **Keep held, vendor and generated content out of whole indexing.** A held or undecided child, or a folder Geo marks `is_vendor`/`is_generated`, is not indexed under its parent's decision. | Librarian indexer | Parallax: 51,507 of 54,225 indexed files (est. about 6 GB of its 7.3 GB index) | Small–medium |
| 5 | **Store the text once.** Make `chunk_fts` an external-content FTS5 table (`content='chunk'`), so the text is not stored a second time inside FTS. | Librarian index schema (rebuild) | about the raw chunk text again: 1.7 GB Parallax, about 0.2 GB each other (est.) | Medium |
| 6 | **Graph versions by reference.** A new version stores only repositories whose revision changed and references the rest. Keep the current and previous versions; delete older ones and compact. | Geo-Grapher (`F:\uv-data\Geo_Grapher`) | 69 GB → about 31 GB with retention alone (est.), less with reuse; also makes accepts much faster | Larger |
| 7 | **Connected projects by reference.** Index own project content by path, offsets and hashes, and read the text on demand through client access instead of storing it. That is your intended design: connected projects are viewed, not copied. | Librarian index + read tools | Most of what remains of items 4 and 5 | Larger (design) |
| 8 | **Supervisor caches root counts** and re-walks a root only when its folders changed, at most every 15 min. | My tooling | about 0.5 CPU core, constant disk reads | Small |

Items 1, 2, 4 and 8 are quick and safe. Item 1 loses nothing: SQLite folds the log into the main
file. Items 3 and 5 need a test-covered migration. Item 6 belongs to the Geo-Grapher repo. Item 7
needs your design go-ahead: search snippets would come from reading the project at query time, so
results depend on the project drive being attached.

## Note on the running Parallax policy pass

A policy acceptance I sent before you cleared space is still running. It has added one repository
to `Parallax-third-party-docs`, most likely `openclaw-ruview-presence-main`: the Clerk's re-check
called it normal after flagging it earlier. If you want it held, it needs reverting (the hardening
report's decision list).
