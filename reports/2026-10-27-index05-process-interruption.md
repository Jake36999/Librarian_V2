# INDEX-05 process-interruption continuation

Date: 2026-10-27  
Implementation: `2e9df4a`; fixture stabilization: `f3b0508`  
Status: partial; abrupt process-death slice implemented, INDEX-05/G1 open

## Delivered boundary

A real coordinated Windows child Core runs the normal loopback server with an
isolated configuration. Child-side admission markers prove that a person write
and search, an MCP write, and checkpoint creation each entered their own Core
admission boundary. An Obsidian heartbeat and external edit exercise the
ephemeral editor state and later index reconciliation.

The fixture pauses after `Notes/CrashTarget.md` has been atomically written but
before the writer can append its terminal operation record. At the same time,
IndexService holds an uncommitted WAL transaction. The exact child then exits
with `os._exit(97)`; all waiting clients terminate within a bound and the exact
PID/start identity is dead.

A normal successor refuses the stale sidecar. Explicit takeover:

- creates exactly one recovery checkpoint for the start-only operation;
- exposes targets and current fingerprints without private note contents;
- performs no replay or automatic repair;
- preserves the already-applied note and does not create the queued note;
- verifies the Session hash chain and loses the prior in-memory editor lease;
- confirms the uncommitted WAL probe rolled back and `PRAGMA integrity_check`
  is `ok`;
- refreshes the index to the post-crash Markdown bytes, nanosecond metadata and
  native file identity;
- leaves no orphan chunk, facet, link or component rows; and
- creates no duplicate recovery on a second clean restart.

The fixture also reproduced a Windows lock probe that raised `PermissionError`
before `msvcrt.locking` could report contention. `VaultCoordinator.acquire()`
now translates that error only when the diagnostic sidecar names an exact live
foreign PID plus `process_start`. Missing, stale, ownerless and legacy-unpinned
sidecars do not mask ordinary filesystem permission failures.

Independent review found two overclaims before final verification: checkpoint
admission had been inferred from a generic mutation count, and permission
mapping was initially unconditional. Exact per-route admission markers and the
exact-identity condition corrected both. A second review required
`process_start` even for a live PID, closing the recycled/legacy PID ambiguity.

## Verification

The corrected abrupt-crash scenario passed five consecutive independent
invocations. The final focused lifecycle/index command passed **66 tests in
31.92s**:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests/test_core_process_interruption.py tests/test_operation_recovery.py tests/test_shutdown.py tests/test_host_lifecycle.py tests/test_process_identity.py tests/test_core_concurrency.py tests/test_index_snapshot_consistency.py -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=60
```

Frozen-source full verification:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=60
```

Result: **1,438 passed, 2 skipped, 1 deselected in 468.12s (7m48s)**.

The first full run reached **1,437 passed, 2 skipped and 1 deselected**, with
one failure in the pre-existing revision-conflict fixture. Under suite load,
the watcher could observe the deliberate external edit before the fixture's
second write, correctly applying its separate quiet-window refusal. The test
now stops the watcher so it deterministically exercises only the documented
no-plugin revision/CAS path; watcher behavior remains covered in its own suite.
The corrected test passed five consecutive runs and the related
revision/watcher/file-access/snapshot group passed **44 tests** before the final
full rerun. No product safety check was relaxed.

The normal repository host was used with approval because the Codex app sandbox
redirected temporary files into an app-container that denied child atomic lease
replacement. No paid provider, external service or route qualification was
used.

## Remaining boundary

This packet validates abrupt process death and durable ambiguity; it does not
claim exactly-once mutation semantics. Applied bytes intentionally remain for
human review, while queued work is not replayed.

The authenticated `HostManager.stop(force=True)` path under active mixed
traffic is separate and remains open. INDEX-05/G1 also still requires sustained
and large-vault evidence, simultaneous real adapters, unsupported
external-handle interference, encoder writer-release work, the supported
Python matrix and a clean packaged installation.
