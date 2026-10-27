# INDEX-05 snapshot and reviewed-file continuation

Date: 2026-10-26  
Implementation: `74c6081`  
Status: partial; this packet does not close INDEX-05 or G1

## Delivered boundary

- Index reads now capture bytes and file metadata from one active handle, reject
  content that changes during the read, and persist nanosecond timestamps plus a
  native file identity. Same-size atomic replacement with a restored timestamp
  is therefore no longer treated as unchanged.
- Refresh and rebuild reconcile rename/delete races for at most three passes,
  remove stale note and component rows, and report when a changing tree did not
  converge. The index schema is version 3; the version-2 migration retains old
  rows until the required rebuild restores Markdown truth.
- Extract plans obtain their revision only from reviewed survey evidence. An
  absent or ambiguous survey revision fails closed. A deterministic plan token
  binds the revision, selected files, limits and evidence; materialization
  recomputes and verifies that token before network access.
- Fresh staging rejection prepares a collision-safe quarantine target before
  approval and fingerprints both complete and partial source attachments. A
  changed attachment refuses the operation, older quarantine records are not
  overwritten, and source attachments remain in place for recovery.

The work was split across three implementation lanes and independently
cross-reviewed. Review found and the implementation corrected: same-size
replacement detection, stale component rows after rebuild, hidden rebuild
non-convergence, ambiguous extract survey revisions, extract plans not binding
all reviewed inputs, the model-expectation rejection path ignoring its prepared
target, and partial staging items omitting attachment checks.

## Verification

The dedicated snapshot, extract-pinning and staging groups passed **69 tests**.
The combined index, watcher, extract, staging, revision and recovery group
passed **310 tests**. Frozen-source full verification passed:

```text
1435 passed, 2 skipped, 1 deselected in 502.77s
```

Dedicated command:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests/test_index_snapshot_consistency.py tests/test_extract_pinning.py tests/test_model_expectation_authoring.py tests/test_staging.py tests/test_staging_safety.py -p no:cacheprovider -o faulthandler_timeout=60
```

Combined command:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests/test_index_snapshot_consistency.py tests/test_index.py tests/test_file_access.py tests/test_core_index_service.py tests/test_core_concurrency.py tests/test_watcher_recovery.py tests/test_index_ownership_runtime.py tests/test_sqlite_ownership.py tests/test_embed.py tests/test_extract_pinning.py tests/test_upkeep.py tests/test_core_upkeep.py tests/test_model_expectation_authoring.py tests/test_staging.py tests/test_staging_safety.py tests/test_intake.py tests/test_core_source_promotion.py tests/test_core_source_batch.py tests/test_core_mixed_acceptance.py tests/test_revisions.py tests/test_operation_recovery.py -p no:cacheprovider -o faulthandler_timeout=60
```

Full-suite command:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -o faulthandler_timeout=60
```

The first combined run reported **309 passed and one failure** in
`test_an_external_edit_between_read_and_write_becomes_a_conflict_checkpoint`:
the immediate second write was still inside the watcher's quiet window. The
related watcher/index group then passed 26 tests, the single test passed five
successive invocations, the complete combined group passed all 310 tests, and
the full suite above passed. It was not reproduced again during this packet and
no product or test relaxation was made. It later recurred under full-suite load;
`f3b0508` isolated the revision/CAS fixture from the independently tested
watcher quiet window, as recorded in the [process-interruption report](2026-10-27-index05-process-interruption.md).

The Codex app sandbox redirected temporary files into a Windows app-container
that denied atomic replacement and also stalled a socket-pair fixture. Final
verification therefore ran, with approval, in the normal repository host
environment. This is execution-environment disclosure, not a product pass
obtained by changing the tests.

## Remaining boundary

INDEX-05/G1 remains open. Evidence is still required for sustained and
large-vault traffic, authenticated Host force-stop under mixed traffic, actual
simultaneous adapters, unsupported external-handle interference, the supported
Python matrix, and a clean packaged installation. Encoder IO in source
promotion also still occupies the enclosing writer call; moving that slow work
outside SQLite ownership is a separate orchestration change. The three-pass
index reconciliation is deliberately bounded and asks a later refresh to
finish a tree that continues changing. No atomic whole-vault snapshot or
exactly-once crash guarantee is claimed.
