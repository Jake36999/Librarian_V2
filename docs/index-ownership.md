# Core index ownership and offline compatibility

Status: INDEX-04 gateway/pack boundary implemented and locally verified
(2026-10-25). INDEX-05 stress and broader G1 acceptance remain open.

## Serving callers

Browser, Obsidian, Cowork/MCP and CLI clients use Core APIs. App-created
Contexts and the CLI's short-lived leased Core set `index_access: core` and
supply their own vault's `IndexService`. Helpers inherit these extras.
Attaching a chat session now uses the same person-call path, not a bare
Context without the Core extras.

`tools.library.index_service_for` validates the mode, concrete service and
vault identity before any direct fallback/cache lookup. A missing service
in a Core/MCP/writer-backed Context, a foreign service, an invalid mode, or
an attempted serving/offline combination raises `CORE_REQUIRED`. A closed
service retains its normal closed-service failure; it never opens a new
connection to recover silently. The mode is trusted runtime metadata, not
a tool argument or something a model can change.

`engine_for` and an unowned `_build_engine` are offline-only, including when
a legacy engine is already cached. `with_engine`, `with_index` and
`IndexGateway` use the validated service for bounded callbacks. Interleaved
work returns copied plain data through the gateway; no worker-owned Engine,
SQLite row/connection/cursor may cross that boundary.

The static construction guard has **zero serving-debt entries**. Its narrow
infrastructure exceptions are construction inside IndexService, low-level
offline helpers and the guarded legacy engine builder. It also rejects new
`open_index`/`run_index` calls outside reviewed boundaries, preventing a new
tool from merely renaming direct construction as an offline-helper call.
Desk and lens databases remain separately listed stores, not proof of vault
index ownership; their concurrency work remains INDEX-05.

## Explicit offline entry points

New direct graph/extract pack calls require either `index_service=...` or
`offline=True`. An absent service alone is not an offline decision:

```python
communities.rebuild(vault, index_service=core.index_service)
extract.plan(vault, "catalogued-repository", index_service=core.index_service)

# Developer/library use only, with no active Core for this vault:
communities.rebuild(vault, offline=True)
extract.plan(vault, "catalogued-repository", offline=True)
```

`run_index` centralizes this choice and checks a supplied service's vault.
Registered pack tools first validate their Context; their public schemas do
not expose an `offline` switch. Bare standalone Contexts remain a legacy
2.x compatibility alias for offline access. New standalone code should state
`index_access: offline`; adapters must never use that compatibility alias.
The supported CLI still discovers/proxies an active Core or acquires the
vault lease before constructing a short-lived IndexService.

This is an architectural boundary for Librarian's supported entry points,
not a sandbox against arbitrary Python scripts or external programs that
can open the SQLite file directly. Low-level offline library callers must
not run beside a Core. No new interprocess service/lease mechanism was added.

## Extract callback and remaining pack work

Extract materialization copies source metadata on the SQLite worker, then
does evidence/cache/network IO outside it via the existing source-file
callback. A fetch can query IndexService while pending without deadlocking
the worker. The extracted result/cache format and person-only execution
permissions are unchanged.

This does not prove full extract parity. In particular, the existing planner
can inherit a timestamp-like component revision, while source-file retrieval
can fall back to the current default branch if survey evidence has no tree
SHA. Mixed source metadata/revisions between files also need a pinned-plan
review. Those pre-existing pack-contract gaps require explicit revision tests
and closure before release; this ownership migration does not certify them.
Schema/model-service cancellation, large embedding IO on the worker and
adopted-root indexing remain separate tasks.

## Windows fingerprint/replacement exclusion

A native regression reproduces an ordinary open reader preventing atomic
replacement of a Windows destination. A proposed FILE_SHARE_DELETE opener
was tested and discarded: it was insufficient for the `os.replace` path on
this host. No experimental Win32 shim remains in the product. See the
[CPython Windows replacement issue](https://bugs.python.org/issue46003) and
[Microsoft file-sharing contract](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew).

`file_access` now provides short, reentrant, process-local, per-canonical-path
locks around fingerprint reads and the final text/binary replacement syscall.
A reader closes before another Core thread replaces that path. Independent
notes remain writable; the registry is weakly held rather than retaining
every path forever. No entire tool, approval wait, provider request or vault
is locked. No mutation retry, rollback, external-editor exclusion or new
cross-process guarantee is implied. Uncoordinated external readers can still
cause an explicit Windows access failure. Large-file hashing can occupy the
same-file lock; no bounded hash latency or throughput improvement is claimed.

The earlier authoring development failure is recorded as a denied atomic
replacement. The native fixture proves a relevant reader/replacement failure
mode; it does not establish which handle caused that particular failure or
explain the two earlier non-reproduced mixed-acceptance failures.

Exact focused/full verification and the frozen-source evidence are recorded
in [regression-manifest.md](regression-manifest.md).
Implementation: `ded98c0`, `e40a4a6`; coordinated revision fixture: `d31cda5`.
Final frozen-source run: **1,284 passed, 2 skipped, 1 deselected in 434.41s**,
with thread-exception warnings treated as errors and no warnings reported.
UI build/complete smoke passed. These checks used CPython 3.11.3 on this
Windows host, not the whole supported-version/packaged-release matrix.
