# Core concurrency: bounded Windows validation

Status: INDEX-05 partial delivery, 2026-10-25. Implementation: `f11e98d`.
The unified implementation plan remains the delivery/status authority.

## Findings and fixes

Deterministic lifecycle tests failed **6 cases** on the previous implementation:
Desk pin/unpin/touch/read operations left connections unclosed, a failed Desk
transaction also left its connection open, and lens migration failure escaped
before cleanup. Three control cases passed. Desk now commits/rolls back and
closes explicitly; lens setup closes on failure. Both have explicit five-second
SQLite busy timeouts, and per-path schema/migration initialization exclusion.
Their schemas, journal formats, acceptance semantics and hash-chain format are
unchanged. These accepted-data stores remain distinct from the disposable index.

A separate native Windows fixture reproduced `get_note` holding an open
Markdown handle while a prepared `edit_note` tried atomic replacement:
`PermissionError: WinError 5`. The shared per-file exclusion now covers
`get_note`, pane/script display reads, `notes.load`, and the stat/text snapshot
inside `Index.upsert`, in addition to fingerprints and atomic replacement.
Four controlled interleavings check the getter, pane, loader and index upsert.
The final tests probe actual lock ownership at the prepared-write boundary;
they do not rely on sleeps to guess which side won. Parsing and SQLite work
occur after the file-read handle closes. No whole-vault lock or mutation retry
was added. This new reproduction does not establish the cause of earlier,
unreproduced mixed-staging failures.

Chat's automatic desk-touch path also now uses the Core writer, like registered
desk tools. The UI, picker, service selections and permission controls were not
redesigned. Browser build and complete smoke passed, including desk behavior,
model selection, staged review and interrupted-work controls.

## Repeated loopback experiment

Each fixture uses one coordinated Core and seven concurrent workers: browser
tool requests, constrained MCP RPC, direct agent-registry work, read/search/
desk/lens queries, refresh/WAL checkpoint maintenance, person-accepted staged
lenses, and Obsidian-style dirty-document heartbeats plus direct human saves.
Each worker performs six category iterations. This tests client protocols and
Core behavior, not running Obsidian/Cowork GUI binaries or a live language model.

Three fresh pytest invocations each ran the three fixture repetitions:

| Measurement | Observed |
| --- | --- |
| Independent fixture executions | 9 |
| Concurrent workers per fixture | 7 |
| Completed category iterations | 378 |
| Successful loopback HTTP requests, including setup/release | 531 |
| Core WAL checkpoint calls | 54 |
| Index connections / SQL worker threads per fixture | 1 / 1 |
| Completed operation IDs / unfinished IDs | 405 / 0 |
| Closed index / desk / lens connections, aggregate | 9 / 117 / 126 |
| Per-fixture HTTP p50 range | 32–47 ms |
| Per-fixture HTTP p95 range | 235–281 ms |
| Slowest individual HTTP request | 359 ms |
| Per-fixture measured duration, including cleanup | 2.91–3.19 s |
| Model requests / provider spend | 0 / $0 |

Every fixture checks SQLite integrity, exact note presence in Markdown and
the index, retained human text, session hash-chain integrity and folded plan
fields, desk touch counts, lens count and acceptance-log integrity, all opened
connection closures, writer start/finish pairs, and a surviving watcher. No
SQLite busy/cross-thread exception, lost asserted result or unfinished operation
was observed in these runs. PASSIVE checkpoint completion is exercised; this
does not measure checkpoint backlog against unsupported external SQLite readers.

These are instrumented micro-fixtures on small starter vaults. Timings include
test connection tracking and other local verification running concurrently.
The timer is `time.monotonic`; the Windows/Python timer resolution limits
precision. The p95 range is a range of nine per-fixture percentiles, not a
pooled percentile or a latency SLA. It is not a throughput, local-model,
provider-quality or production-capacity benchmark.

Raw local measurements: `tmp/core-concurrency-repeat-2026-10-25-01.log`.
Metrics print only counts/timings; no keys, prompts or source text are emitted.

## Human editing and explicit recovery

A separate fixture keeps a note focused/dirty through three direct human saves
and MCP reads while unrelated notes are written. Typing/reading alone creates
no checkpoints. One attempted same-note write creates exactly one conflict
checkpoint. Releasing the lease, waiting for the actual watcher/quiet window,
and resolving `retry_after_review` does not perform a write. Only a subsequent
explicit MCP call with a fresh revision commits, preserving the person's text.

## Verification and limits

**301 focused tests passed in 147.92s**, including **18 new checks** (nine
auxiliary-store cases and nine Core concurrency cases). Repeated contention
executions above are additional to that focused run. Browser TypeScript/build
and complete smoke passed; the generated UI bundle did not change. Exact
commands and final frozen-source full verification are recorded in
`docs/regression-manifest.md`. Against `f11e98d`, the full run passed **1,302
tests, 2 skipped, 1 deselected in 449.18s**, with thread-exception warnings
treated as errors and no warnings reported. Local output:
`tmp/core-concurrency-full-2026-10-25-01.log`. Source/tests stayed frozen during
that run. A subsequent module-docstring clarification describes the additional
schema-initialization use of the path mutex; runtime behavior is unchanged.

INDEX-05 and G1 remain open for broader acceptance. Outstanding scope includes
large vaults and attachments, sustained rather than six-round activity,
concurrent rename/delete and note/index-metadata snapshot consistency,
process-crash/forced shutdown during mixed traffic, simultaneous real adapters,
unsupported external readers/editors, the supported Python-version matrix,
and clean packaged installs. General raw-read inventory and store/recovery
transactions are not certified by these selected read paths. Existing blocked
read/hash behavior can still wait on same-file IO; no fixed upper hash-latency
bound or cancellation guarantee was added. The SQLite busy timeout does not
bound path-mutex waits or schema-rebuild duration. Staging quarantine/encoder waits,
strict extract revision pinning, adapters, adoption/dedupe, and the Session
harness remain separate plan work.
