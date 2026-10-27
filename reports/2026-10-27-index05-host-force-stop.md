# INDEX-05 authenticated Host force-stop continuation

Date: 2026-10-27
Implementation: `84b90a8`
Status: partial; authenticated Host force-stop slice implemented, INDEX-05/G1 open

## Delivered boundary

A real coordinated Windows child Core now exercises the authenticated
`HostManager.stop(force=True)` path while person, MCP and checkpoint requests,
an Obsidian heartbeat, an external edit, a durable Markdown mutation and an
uncommitted IndexService WAL transaction overlap.

An ordinary stop first receives `409` with the active work counts and the
`forced_engagement_close` UI hint; this hint is not represented as a durable
checkpoint. The child stays alive. The explicit force request then closes
admission and makes one bounded shutdown attempt. When admitted work and its
writer cannot drain, the Core records only:

- `admission_closed`;
- `work_cancelled`;
- `writer_drained` with `drained: false`; and
- `shutdown_pending` with `reason: writer_still_running`.

It does not invent `index_closed` or `lease_released`. Host-managed process
teardown then exits the exact child normally and removes only its PID/token
scoped connection record. The stale vault lease is deliberately retained as
crash evidence. A normal successor refuses it; explicit takeover creates one
non-replaying recovery checkpoint, rolls back the uncommitted WAL row, retains
the already-applied Markdown, omits the queued write, restores index/Markdown
convergence and leaves no orphan child rows.

Pending and completed phase telemetry is per-user diagnostic state rather
than ownership authority. `App.close_runtime()` now persists a truthful
pending record on each fail-closed return and replaces it with the complete
record after a successful retry. The Host exit wait is 25 seconds: beyond the
Core's five-second admitted-work grace and ten-second writer drain, with
margin for watcher, MCP and server teardown. There is still no kill fallback.

## Verification

The dedicated force-stop scenario passed three independent invocations during
implementation review. The final focused lifecycle/recovery command passed
**49 tests in 32.78s**:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests/test_core_process_interruption.py tests/test_host_lifecycle.py tests/test_shutdown.py tests/test_operation_recovery.py tests/test_process_identity.py -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=60
```

Frozen-source full verification against `84b90a8`:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=60
```

Result: **1,439 passed, 2 skipped, 1 deselected in 506.43s (8m26s)**.

`compileall` and `git diff --check` also passed. The normal repository host was
used for pytest because the Codex app sandbox redirected temporary files into
an app-container that denied atomic lease replacement. No paid provider,
external service or route qualification was used.

## Remaining boundary

This packet proves authenticated force-stop recovery; it does not claim that
force makes active work finish or provides exactly-once mutation semantics.
The `shutdown_pending` record and stale lease are evidence of that deliberate
fail-closed boundary.

INDEX-05/G1 remains open for sustained and large-vault evidence, simultaneous
real adapters, unsupported external-handle interference, encoder
writer-release work, the supported-Python matrix and a clean packaged install.
