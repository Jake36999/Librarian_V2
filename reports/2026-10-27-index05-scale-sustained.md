# INDEX-05 large-vault and sustained-traffic continuation

Date: 2026-10-27
Implementation: `ae00300`
Status: partial; bounded scale/sustained slice implemented, INDEX-05/G1 open

## Delivered boundary

Two deterministic, explicitly slow Windows characterizations now cover the
previously open Markdown scale and sustained native-Core traffic boundary.
They enforce correctness and ownership, while timings are diagnostics rather
than release SLAs.

`tests/test_index_large_vault.py` creates 5,000 notes containing 24,190,000
bytes. It proves:

- the initial build converges to every Markdown path and exact file metadata;
- an unchanged refresh performs zero note-payload snapshots;
- 50 modifications, 25 renames and 25 deletions cause exactly 75 payload
  snapshots, 75 upserts and 50 removals;
- a second stable refresh again performs zero payload snapshots;
- changed and renamed notes have the exact normalized-content hash;
- SQLite integrity is `ok`, no transaction remains open and note-derived
  child tables contain no orphan paths; and
- callbacks stay on one IndexService worker and one Index instance, with the
  queue drained and the connection closed at teardown.

`tests/test_index_sustained_traffic.py` seeds 750 notes, then runs 30
two-barrier rounds across six persistent workers: Browser/person writes, MCP
writes, external same-size replacement with restored mtime plus rename/delete/
create, Obsidian heartbeat/edit/release, search/index-status reads, and
refresh/passive-checkpoint maintenance. After 180 worker iterations it proves
exact filesystem/index path, hash and metadata convergence; one index
connection and worker thread; 30 checkpoints; clean document leases;
integrity/no-orphan/no-open-transaction state; complete operation records;
closed SQLite handles; and successful post-stop lease reacquisition.

The fixture uses the real loopback Browser, MCP and Obsidian HTTP contracts. It
does not claim separately packaged adapter processes. Transient Windows CRT
sharing failures receive a narrowly bounded two-second retry and are reported
as metrics; the final run needed none. This does not close unsupported
long-lived external-handle interference.

## Verification

Final sequential slow characterization:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests/test_index_large_vault.py tests/test_index_sustained_traffic.py -m slow -rP -s -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=120
```

Result: **2 passed in 110.81s**.

Large-vault measurements from that run:

- initial refresh: 22.550s, 24,226,620 returned snapshot bytes;
- stable refresh: 2.989s, zero payload snapshots;
- incremental refresh: 3.230s, 363,700 returned snapshot bytes across the
  exact 75 changed/destination paths; and
- derived index: 2,953,216 bytes.

Sustained measurements from that run:

- 30 rounds, 180 worker iterations and 180 HTTP requests;
- 30 refreshes with zero non-convergence reasons and 30 checkpoints;
- 820 final notes / 90,480 Markdown bytes and 63 operation IDs;
- request p50 1,047ms, p95 2,344ms and maximum 2,391ms; and
- 70.39s elapsed, one index connection and zero sharing retries.

The focused default-marker companion command passed **18 tests, 2 deselected
in 17.82s**:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests/test_core_concurrency.py tests/test_index_snapshot_consistency.py tests/test_index_large_vault.py tests/test_index_sustained_traffic.py -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

Frozen-source default-suite verification against `ae00300`:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

Result: **1,439 passed, 2 skipped, 3 deselected in 481.36s (8m01s)**. The two
new deselections are the deliberate slow tests above.

Independent review added fail-safe barrier abort/join ordering before Core
teardown, bounded and measured Windows sharing retries, explicit post-close
connection/thread assertions, and corrected a comment that had described a
per-file IO bound too broadly as a process-memory bound. An earlier sustained
attempt overlapped the separate large-vault pytest process and ended in a
Windows access violation without an assertion result; it is not counted. Both
final characterizations ran sequentially in one host process. `compileall` and
`git diff --check` passed. No paid provider, external service or route
qualification was used.

## Limits and remaining boundary

`read_bytes_snapshot()` intentionally reads a changed file twice to detect a
same-size mutation whose metadata is restored. The test bounds returned
payloads per file and proves stable refreshes read no payloads; it does not set
an RSS threshold or claim a single-read implementation. Large attachment and
large individual-note costs are not covered by the 4.8 KiB synthetic notes.

INDEX-05/G1 remains open for simultaneous packaged real adapters, unsupported
external-handle interference, large-attachment and encoder writer-occupancy
work, the supported-Python matrix and a clean packaged install.
