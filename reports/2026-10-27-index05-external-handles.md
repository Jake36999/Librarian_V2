# INDEX-05 unsupported external handles

Date: 2026-10-27
Implementation: `ef143be`
Status: partial; foreign-handle fail-safe/recovery accepted, INDEX-05/G1 open

## Delivered boundary

This packet characterizes two hostile Windows states outside Librarian's
coordination boundary. It does not turn arbitrary third-party file or SQLite
handles into supported clients.

The file fixture uses native `CreateFileW` to keep a Markdown destination open
for reading without delete sharing. A same-note replacement through the real
Core therefore cannot complete its atomic `os.replace`. The call must return
within a bounded join with an explicit failed/`PermissionError` result. The
fixture proves that the original bytes and revision remain current, the index
still describes those bytes, no temporary file is left, the writer remains
alive and an unrelated note remains writable. Once the foreign handle closes,
an explicit retry with the still-current revision succeeds and the operation
trail contains the failed attempt followed by the completed retry.

The SQLite fixture opens the derived index directly through a foreign,
query-only connection and holds a read transaction. Six Core-owned refreshes,
ordinary reads and integrity checks continue while that transaction pins WAL
frames. `IndexService.checkpoint()` now returns `busy`, `log_frames`,
`checkpointed_frames` and `complete`; existing callers may continue to ignore
the result. A passive checkpoint returns promptly and reports incomplete work.
After the foreign reader closes, a deliberate next checkpoint completes, with
one owned index connection and a stopped worker after teardown.

## Verification

Focused normal-host regression:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests\test_index_external_file_handle.py tests\test_index_external_sqlite_handle.py tests\test_revisions.py tests\test_file_access.py tests\test_core_concurrency.py tests\test_index_sustained_traffic.py -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

Result: **29 passed, 1 deselected in 23.16s**. The deselected case is the
existing explicit slow characterization, not a failure.

Frozen-source full default-suite verification against `ef143be`:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

Result: **1,466 passed, 2 skipped, 3 deselected in 485.52s (8m05s)**.

## Limits and remaining boundary

These tests prove bounded failure, continued unrelated Core progress and
explicit recovery. They do not coordinate external processes, guarantee that
a third party releases its handle or impose a deadline on that third party.
No automatic retry or Windows sharing shim was added.

INDEX-05/G1 therefore remains open for large attachments and scan
amplification, encoder writer occupancy, hosted Python matrix and signing
evidence, and execution in the external real host applications.
