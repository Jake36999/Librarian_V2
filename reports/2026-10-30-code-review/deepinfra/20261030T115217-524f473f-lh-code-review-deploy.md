## Findings (correctness lens, max 4)

**1. `iter_documents` follows Windows junctions (and the watcher's `_markdown` does too)**
- Anchor: `content_roots.iter_documents` (dirnames filter uses `(here / d).is_symlink()`), and `coordination.VaultWatcher._markdown` (`entry.is_symlink()`).
- Trigger: a directory junction (or mount point) inside a read-write root, e.g. `docs/linked -> D:\elsewhere`. `Path.is_symlink()` is false for junctions; `os.walk`/`scandir` descend into them. `deploy_survey._is_link` correctly treats reparse points as links, so the survey reports them as links and never follows them — but the indexer and watcher do follow them.
- Effect: documents outside the approved roots get indexed (and watched), contradicting the module docstring ("without entering … links") and the survey's "reported and never followed". A junction to a parent can also produce cycles/duplicate paths.
- Fix direction: reuse `deploy_survey._is_link` (reparse-point check) in both `iter_documents` and `_markdown`.

**2. `apply_adopt` writes state before the "documents unchanged" check, and the check is not atomic**
- Anchor: `content_roots.apply_adopt` — `before = survey(root).entries` is taken, then `.librarian/` is created/written, then `after` is compared.
- Trigger: a document is edited/added/deleted between `before` and `after` (or between `plan_adopt`'s fingerprint and `before`). The refusal `ADOPTION_PLAN_STALE` is raised *after* `config.toml`, the manifest, and work folders are already on disk. The caller sees a refusal but the folder is now half-adopted (a `.librarian` exists, so a retry hits `_librarian` → `librarian_vault` and `adopt` becomes impossible).
- Also: `before`/`after` compare `(path, size, mtime_ns)` only; a same-size edit within the mtime granularity is invisible. The fingerprint has the same weakness, so the compare-and-apply guarantee is weaker than the docstring claims.
- Fix direction: re-survey and compare *before* creating `.librarian/`, or roll back on mismatch; include a content hash for the small set of changed files.

**3. `reconcile` can carry an id onto the wrong document when a path is reused**
- Anchor: `document_identity.reconcile`, layer loop over `("file identity", "byte_hash")`.
- Trigger: file A at `x.md` is deleted and a *different* file is created at `x.md` in the same refresh, while a new path `y.md` appears. `remember` for `x.md` updates the existing row in place (same `path`), so `x.md` is not "fresh"; the old row's `file_key`/`byte_hash` are overwritten. If `y.md` matches the *old* A by byte hash, `orphans` no longer contains A (its row was mutated), so the move is missed — or, worse, if the new `x.md` content equals an orphan elsewhere, `x.md` is treated as the move target and inherits that orphan's `doc_id` even though `x.md` is a genuinely new document at a reused path.
- Effect: `doc_id` (and `first_seen`/`moved_from`) can attach to the wrong document; `duplicates` then reports misleading groups.
- Fix direction: on `remember`, if the path exists but `file_key`/`byte_hash` changed, treat the old row as an orphan (insert a new provisional row) rather than mutating in place.

**4. Watcher scope is captured once at construction; manifest changes are ignored until restart**
- Anchor: `coordination.VaultWatcher.__init__` (`self._roots, self._excludes = watch_scope(vault.root)`), used by `_markdown`/`_snapshot`.
- Trigger: `apply_attach` (or a future root/exclude edit) rewrites `content-roots.json` while the Core is running. `Index._model_hash` includes `manifest_bytes`, so the *index* rebuilds on the next refresh, but the watcher keeps the old roots/excludes until the process restarts.
- Effect: newly attached read-write roots (or newly excluded folders) are not watched / still watched — stale scope, exactly the class of bug the manifest was meant to fix. Attached read-only roots are intentionally unwatched (documented exclusion), but read-write root and exclude changes are not.
- Fix direction: re-read `watch_scope` when the manifest's mtime/bytes change (cheap check per scan), or have `apply_attach`/manifest writers signal the watcher.

## Assumptions / risks
- Assumed `Path.is_symlink()` semantics on the target Windows version (junctions are not symlinks) — verify with a real junction in a test.
- Assumed `apply_adopt` is reachable from a UI that surfaces the refusal without cleanup; if a caller rolls back `.librarian/`, finding 2's severity drops.
- Finding 3 depends on `remember` being called for a reused path before `reconcile` in the same refresh — true in `Index.refresh`/`upsert`.

## Deterministic tests for the integrator
1. Create `root/docs/real.md` and a junction `root/docs/j -> root/other` containing `hidden.md`; assert `iter_documents(root)` excludes `hidden.md` and `VaultWatcher._snapshot()` does not list it.
2. Monkeypatch `survey` to return a changed `entries` on the second call; assert `apply_adopt` raises and `.librarian/` is absent (or restored).
3. Seed `document` with `x.md` (file_key K1, byte_hash H1), then `remember` `x.md` with K2/H2 and `y.md` with H1; run `reconcile`; assert `y.md` does not inherit `x.md`'s `doc_id` and `x.md`'s row is a new provisional id.
4. Start `VaultWatcher`, rewrite `content-roots.json` to add a read-write root with a new `.md`, call `scan_once()`; assert the new file is observed (or document that restart is required).