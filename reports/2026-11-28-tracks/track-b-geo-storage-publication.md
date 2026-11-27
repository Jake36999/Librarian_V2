# Track B: Geo-Grapher storage and publication (G4 integration, G5, W-PUB-02)

**Why:**
- **Storage.** Each paper publish copies the whole paper database. Resource-Library's DataManagement graph keeps 96 generations: 915 MB for a 16.7 MB active database (55x). Growth is quadratic, about 86 GB at 1,000 papers in one graph (`reports/2026-11-27-geo-g5-measurement/README.md`). The Owner decided on 27 November: fix the growth first, and delete nothing meanwhile.
- **Publication.** A PDF added without folder review never publishes (W-PUB-02).

**Repositories:**
- Geo-Grapher: `F:\uv-data\Geo_Grapher`, working in `G:\Librarian-work\geo-grapher-g4`.
- The Librarian, for the call sites.

**Environment:** run the Geo-Grapher suite with `uv run --extra test` and `UV_CACHE_DIR=G:/Libraries/_geo-runtime/uv-cache`; it needs a built `frontend/dist`. Three tests fail without the optional `tree_sitter` parser, on any commit, and hosted CI excludes them.

## Sprint B1: G4 integration (on the Owner's word to push it)

G4 (`feat/g4-incremental-groups`, `b39897f`) is reviewed:
- all 11 incremental-safety rows are tested;
- no function or parameter was removed;
- 987 pass, with only the 3 environmental failures.

The Owner accepted snapshot-scoped rename aliases. Pushing and merging still need the Owner's word. Then:
- push it, and read Geo-Grapher's hosted CI result;
- merge it into `feat/per-library-service`;
- build the wheel;
- in the Librarian, send `target_groups` from `folder_review.accept` and `accept_by_policy` (the `_apply` request), so one decision applies one group;
- re-run `tests/test_m5_planted.py` and the folder suites against the new wheel.

**Done when:**
- a test shows one group touched per accept;
- both suites, and both hosted CIs, are green;
- the M5 acceptance script (`G:\Librarian-work\m5-acceptance\run.py`, in a fresh library) still ingests the fixed folder end to end. That run needs the Owner's approval of about $0.15 of DeepInfra.

## Sprint B2: G5, one active paper database

- **The change:** a publish inserts into the one active paper database, transactionally. Rollback and pinned history are kept by snapshot records, not full copies.
- **Keep unchanged:** the v1.2 receipt contract (`document_id`, `cite_as`, status, content coverage), which the Librarian stores and links by.
- **The plan's gates come first:** crash recovery, rollback, the WAL checkpoint, the disk reserve sized to the paper, and the compare-and-swap retry.
- **Existing generations:** never pruned. Retention numbers are still the Owner's.

**Done when:**
- the gates pass;
- a 100-paper synthetic graph grows linearly, with the growth measured and reported;
- every existing generation still opens;
- the Librarian's M5 tests pass against the new wheel.

## Sprint B3: W-PUB-02, the library's own papers group

**Today:** `paper_graph.publish_artifact` returns `awaiting_accepted_folder` when no accepted folder card covers the PDF. Geo-Grapher's `import-library-paper` accepts only an existing reviewed folder group whose stratum's authorship matches the paper's.

- **Geo-Grapher:** a library-level papers graph, per authorship stratum, that a library may create and publish into, with the same scope checks: the original lies under the library, and is not a credential or generated path.
- **The Librarian:** when no folder card covers the PDF, publish there with the staged item's authorship. When the authorship is unknown, do not publish, and say why.
- **The spec audit's D2:** it recommends publishing. The Owner chose to fix W-PUB-02 on 27 November.

**Done when:**
- an Inbox PDF read in full is published with a v1.2 receipt and a stored `graph_paper` link;
- one of unknown authorship is not published, with a named reason;
- both suites pass.
