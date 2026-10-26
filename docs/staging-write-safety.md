# Staging write boundaries

Status: partial implementation, 2026-10-25. This records the delivered slice of
CORE-05 and INDEX-03/04; the unified implementation plan remains authoritative.

## Review and acceptance

`staging_show` returns an opaque `staged_revision` for the exact staged JSON
bytes shown. For an accepted-source revision it also returns `revision` for
the current destination note. Tokens use the existing Core signing mechanism:
they are bound to vault, path, caller kind, session and Core lifetime. A staged
record token cannot authorize a Markdown edit. Reopen the item after a restart.

The existing browser/Obsidian shared Staging view forwards these tokens from
the review to Accept. Changed note or staged bytes cause `DOCUMENT_ACTIVE`
and a write-conflict checkpoint, not an automatic retry. The form stays intact
until the person explicitly chooses **Reload item (discards form edits)**.
Reloading is review, not permission to accept automatically.

An agent/MCP revision acceptance must supply its own destination-note token.
It cannot borrow the person's token. Accept revisions individually; a token
never authorizes several notes. Explicit legacy person calls without tokens
remain compatible through 2.x: they get dispatch-to-write checks, **not** a
claim that the Core knows which earlier version the person reviewed. New
clients should always forward both tokens. On acceptance the staged token is
optional for legacy callers, but any supplied token is validated, including
person calls. Approve/reject/defer retain their existing semantics; review-token
guards for those lifecycle decisions are not claimed by this slice.
The registry's existing 100-item limit still clamps public list arguments with
`adjusted_arguments`. Expanded taxonomy plans additionally check the existing
200-target/dependency recovery bound; a topic's stored members are not bounded
by the caller's item-ID list. Oversized plans refuse before mutation: accept
the topic without filing its sources, then refile them in smaller batches.

Before approval or queueing, the tool snapshots staged JSON and selected
destination bytes. The writer checks them after preceding operations commit.
If a staged item is retargeted during a permission wait, the operation refuses
before it writes. A concept/import destination initially missing must remain
missing. An active human lease blocks only the affected note. Internal state
dependencies are fingerprinted separately and do not become human-note locks.
Public file APIs still cannot access `.librarian` or other hidden directories.

Revision acceptance now also enforces the normal sensitivity gate: allowing
agent promotion does not allow an agent to merge a sensitive source revision.
Only a person can do that. Revision destinations must be visible, inside the
vault, and typed source notes. Staged IDs must be plain filenames, and embedded
ID/kind must match the loaded file.

## Mutation and ownership inventory

| Operation | Visible effects | Current protection | Index access |
| --- | --- | --- | --- |
| Source revision | Existing source sections; previous section text retained on staged item | Destination revision, staged dependency, target lease, sensitivity policy | Core callback |
| Concept | One new `Concepts/<name>.md` | Staged dependency; destination snapshot/missing guard; target lease | Core callback |
| V1 import | One new explicit target note | Staged dependency; destination snapshot/missing guard; target lease | Core callback |
| Lens | Separate lens store, plus staged lifecycle record | Staged dependency; serialized acceptance | Separate SQLite store; INDEX-05 review remains |
| Single new source | Source note, managed attachment copies, concept backlinks, topic/master indexes, optional vectors, staged record | Reviewed staged bytes; complete target/dependency plan; per-write CAS/leases; explicit interrupted-acceptance progress | Core callback |
| Source-only new-source batches | Source notes, managed attachment copies, shared concept backlinks and topic/master views, staged records | Complete bounded pre-approval plan; one shared own-write guard; reserved copy destinations; per-item progress/results | Core callback |
| New sources in mixed-kind batches | Source note, managed attachment copies, views/concept backlinks, staged records | Bounded pre-approved footprint; ordered replanning; own-write hashes; unknown scope refuses | Core callback |
| Single topic acceptance | `About/Topics.md`, optional source refiling, topic/master indexes, staged record | Staged review token; prepared target/dependency CAS; per-write guards; retained partial progress | Core callback |
| Topic acceptance in mixed/multi-item batches | Topic rows, source refiling, topic/master views, staged records | Same bounded footprint; fresh derived text preserves earlier rows/prose; partial-primary targets blocked | Core callback |
| `refile_source` | Changed source frontmatter and old/new topic/master indexes | Prepared note bytes and target/dependency CAS; per-write guards | Core callback |
| `views_refresh` | Planned generated topic/master indexes | Prepared output inventory/CAS; changed topic inventory requires replanning | Core callback |

Deep-read schema/note lookups and acceptance previews now use Core index
callbacks. Clerk/deep-read processing runs after the callback returns. Covered
Markdown writes stay on VaultWriter; index updates stay on IndexService. An
unavailable service refuses before covered acceptance mutates content. Offline
domain callers keep their explicit Engine compatibility path.

## Taxonomy planning and recovery

`refile_source`, `views_refresh`, and single-item topic acceptance retain their
public tool signatures and ordinary permission flow. First-party preparation
resolves file targets before approval. It reads and hashes the same source
bytes used for planned frontmatter updates, and includes `About/Topics.md` as
a policy dependency. It never passes an Engine or SQLite connection to the
caller. A `WriteIntent` carries invocation-local preparation; the registry
copies it into that invocation only, never into tool arguments or durable
logs. This is not another event store or an additional permission grant.

Topic/master renderers produce text on IndexService, then Markdown is written
on VaultWriter and individually upserted back through Core. Before each file
write, guards recheck the taxonomy dependency, destination fingerprint and
active document lease. An edit starting mid-operation stops the next write;
unrelated active documents remain usable. Refusals report `completed_paths`,
which are also retained as declared-path evidence in the conflict checkpoint,
not just its short title. Completed writes are not silently rolled back.

These metadata/refiling plans use dispatch-time snapshots, not a new promise
that the Core knows what prose version a caller reviewed earlier. Existing
opaque caller-read revisions remain required for the previously covered
replace-existing prose tools. No role authority or model selection changes.

Settings receives a `staged_revision` with each topic proposal and forwards it
to Accept. A stale proposal cannot silently change the set of sources filed.
Reload is explicit and retires old form handlers while fetching replacements.
Rewrite indexes checks structured refusals before showing success. Alias text
is normalised to one table cell; colliding Windows-safe topic filenames refuse
before mutation rather than overwriting another topic's generated view.

Single-topic acceptance interrupted after the taxonomy row commits stores
versioned `acceptance_progress` on the existing staged item: approved request,
exact row, completed paths and timestamps. The item remains staged. After
review/reload, **Finish acceptance** prepares the remaining work from current
notes; it neither appends the row again nor overwrites notes already filed.
Caught IO failures retain the same progress when it can be saved. This survives
Core restart and permits unrelated taxonomy additions, but changed approved
wording/row or request requires reconciliation rather than silent reuse.
Re-proposal cannot replace a partially applied person's candidate.

Reject/defer does not undo earlier committed taxonomy/source changes; the
Staging view warns about that. There is no automatic resume, auto-promotion,
cross-file transaction or automatic rollback. An abrupt crash between a file
commit and progress persistence still needs the existing operation-recovery
checkpoint and human inspection; this is not exactly-once execution.

## Approved-batch continuation

`process_approved` is a first-party, person-tier orchestrator, not one long
writer operation. Its approved-set reservation is serialized before stages
start. Batch-owned staging changes, run-log appends, derived DIK saves,
captured PDFs and local extraction phases use the existing Core writer in
both synchronous and background mode. The existing run log and stage replay
remain authoritative; no second job store or reducer was introduced.

Validation/readiness use callback-only IndexGateway access with the existing
no-refresh semantics. A closed Core index or writer refuses rather than
opening another index or falling back to direct filesystem writes. Metadata
proposals read the latest staged fields under the actor and fill missing
values only, preserving person edits and unrelated proposals. Slow data and
chapter-relation results check their staged-input/derived-output fingerprints
before commit. Chapter-relation Clerk queue writes and consumed-answer cleanup
use an optional synchronous state-write callback; model requests remain outside
that commit. This is not a claim that every Clerk caller has been migrated.

The writer can audit explicitly named owned `.librarian` targets without
treating them as editable Obsidian documents. Its internal resolver rejects
escapes and unrelated hidden directories. Public file routes and document
heartbeats still reject hidden paths. Generated extraction-cache target
inventory and the wider index/cache ownership contract remain follow-up work.

Host active-work status includes the background batch. Explicit stop signals
its cancellation and waits within the existing grace period before closing
the writer. Batch-owned commits arriving after that writer closes refuse;
the run remains interrupted and explicitly resumable. Stopping after the last
stage records cancellation rather than incorrectly finishing the item, and
resume reuses committed stage results. A changed person decision is not replaced
by an enriched/failed batch status. An ambiguous final start-audit failure clears
the in-memory reservation, leaving the existing durable recovery mechanism to
surface the interrupted operation. Browser failure state is visible alongside
explicit resume; the model picker and normal approval controls are unchanged.

These are stage-boundary cancellation guarantees, not in-flight transport
cancellation. Nested registered deep-read/review/OCR/cleanup tools can still
hold their own writer operation during provider work. Their transport shutdown
and late-result boundaries remain ADAPT-04/06 work; this packet does not close
the complete Host-stop or single-owner release gate.

Implementation: `ce88b04`. Verification: **113 focused tests**, **1,103 passed,
2 skipped, 1 deselected** in the full suite, plus browser build and expanded
smoke. See `regression-manifest.md` for commands and the local full-run log.

## Catalogue promotion continuation

The registered `model_catalog_adopt` path now uses Core-only SQL callbacks and
bounded per-entry writer operations. It is an explicitly reviewed person-tier
orchestrator, alongside the approved batch and audited macros; external tools
still cannot opt out of writer ownership. The whole catalogue is not treated
as one oversized 200+ source transaction. No second job store was added.

Shared promotion preparation snapshots the new Source target, topic/master
indexes, linked Concept notes, content-model/taxonomy dependencies and local
configuration. Evidence validation/content-address calculation is read-only
before the entry commits. The entry then declares its immutable evidence path
as well. Per-step guards stop on new edits/leases, preserve completed work and
return its paths. A concept's generated backlink section is rebuilt over the
exact prepared note snapshot, preserving the person's definition and prose.
Evidence collisions are refused, not repaired or overwritten. Internal writer
path resolution now recognizes the owned `.evidence` root as well as
`.librarian`; public file routes/heartbeats still reject both and unrelated
hidden roots remain forbidden.

The initial Source write carries an incomplete-promotion `needs_attention`
marker, cleared only after final checks. A mid-round conflict, IO failure or
restart cannot make that partial note appear complete merely because it was
indexed. Catalogue status/Settings surface affected names; failure messages
include completed paths and document conflicts create a normal checkpoint.
Re-adoption skips existing names and never attempts an automatic repair or
replacement. This corrects old documentation claiming URL dedupe or automatic
bundle updates: existing behavior was name-based skip. Model source cards do
not grant route qualification.

Catalogue SQL planning uses `IndexGateway(include_vectors=False)`, avoiding
encoder initialization on every callback. Lexical title/Bottom Line/concept
and backlink checks are deterministic; hybrid retrieval itself is unchanged.
Source-only embedding sync separately copies chunks, runs the encoder outside
SQLite, validates count/dimensions/finite values, rechecks configuration and
representation, and commits each vector batch transactionally. It does not
silently rebuild unrelated sources. A hosted representation without an explicit
first embedding pass is deferred to Settings, matching the documented opt-in
spend rule; a changed representation still requires an explicit rebuild.
Embedding failures remain visible as `needs_attention` rather than losing an
already-written Source or claiming complete findability.

This catalogue packet initially applied the new shared boundary to **catalogue
adoption only**. The single-source and source-only batch continuations below
also use it; the mixed-kind/multi-topic continuation below closes staging's
last direct-engine path. Catalogue encoder IO releases SQLite, but
still runs within that entry's writer operation; transport cancellation and
writer-release restructuring remain separate work. File/index/evidence writes
are not one cross-resource transaction, and partial work requires explicit
inspection using the normal notes/index tools, not automatic replay.

Implementation: `508959a`. **113 focused tests passed**, plus UI build and
expanded browser smoke, including catalogue partial-failure visibility.
Frozen-source full suite: **1,125 passed, 2 skipped, 1 deselected in 373.99s**.
Commands/log location are recorded in the unified plan and regression manifest.
No paid provider call or model qualification was run.

## Single-source acceptance and retained attachments

The registered single-item `staging_decide(decision="accept")` path now uses
the shared promotion planner and Core-owned index callbacks. It prepares the
approved prose/fields, source kind, coverage, D/I/K sections, destination and
concept context before an approval wait. The plan records source/view/concept
targets, staged JSON, schema/topics/configuration, D/I/K bytes and attachment
input/destination fingerprints. The existing writer audit and 200-dependency
bound apply; no parallel job log or new permissions mechanism was introduced.
Preview uses the same preparation and predicts copy destinations without
changing user files or staged JSON (derived index refresh is still possible).

Accepting a single source **copies**, rather than moves, its raw and cleaned
attachments into `Sources/<kind>/files/`. Original project/Inbox/staging files
remain in place. Existing destination files are never reused for a first
acceptance, even if identical; a numbered destination is selected instead.
This is source-preservation behavior, not the future deployment/dedupe system.
It deliberately differed from the initial mixed-kind legacy path, now migrated
below. Offline domain relocation remains legacy. No background cleanup of
retained originals is performed.

Copies stream through a same-directory temporary file, check the input digest
and all preconditions before publication, and atomically replace the prepared
missing destination. Content fingerprints also stream, so large PDF dependencies
do not require loading an entire attachment into memory. Hidden inputs are
limited to the owned `.librarian/staging/files/` subtree; hidden configuration,
Git files, traversal and redirected staging-input escapes are refused. Managed
destinations cannot redirect through links. These checks are not an OS lock
against a malicious process changing filesystem links concurrently.

An active target document lease or changed dependency blocks before the first
copy. A lease/edit that begins during promotion stops its next guarded write,
leaving completed work intact. Different notes remain writable. SQL/rendering
runs on IndexService, file effects on VaultWriter. Encoder IO releases SQLite
but can still occupy this writer operation; transport cancellation and finer
writer-release work remain open.

If a caught interruption follows committed copies/notes, the staged record
retains `promotion_progress`: completed paths, owned-copy identities, exact
last Core source fingerprint, approved-content hash and original session.
This save occurs only if the staged JSON itself is unchanged. An external
staged edit is not overwritten to record progress. If progress cannot be
persisted, the existing operation audit/recovery workflow remains the manual
inspection path; there is no promise that every failure is resumable.

After a restart, open the item again. The shared UI shows completed paths,
retained originals and **Finish acceptance** instead of re-ingestion/redrafting.
It still requires a deliberate person action. Finishing reuses only the
recorded byte-identical managed copies and exact unchanged source, with fresh
review tokens and guards. It preserves the approved author's metadata and
provenance. Changed source bytes, approved prose/fields or inputs require
inspection and the normal source-revision workflow, not replacement by a
replayed draft. Agents cannot finish partial promotion even in agent promotion
mode. Partial items cannot be accepted through the legacy batch shortcut.

Rejecting or deferring a partial item does **not** undo copies, repair a source,
or move original inputs. The UI says this explicitly. Reject still quarantines
the staging record. A new Source retains its incomplete marker until promotion
checks finish; normal accepted-but-unfindable reporting remains unchanged.
Source, view, index and staged-record updates are not one transaction. A hard
crash or failed final state save can still leave ambiguous completed work;
there is no automatic replay, promotion or exactly-once guarantee.

Verification: **182 focused tests passed**, including 41 new source-promotion,
streaming and restart checks. Implementation: `870f2e5`.
Full Python suite: **1,166 passed, 2 skipped,
1 deselected in 391.56s**. UI build and expanded browser smoke cover the retained
originals/partial-work warning, explicit finish action and approved-text label,
as well as existing selection/staging flows. See `regression-manifest.md` for
the exact command, final UI-only verification ordering and local full-run log.

## Remaining limits

- Mixed-kind plans now have bounded footprints and guarded effects, but are
  not simulations of all future outcomes. Newly discovered dependencies need
  another review. Offline domain attachment relocation remains legacy.
- Rejecting a fresh, non-partial source still uses the legacy quarantine/move
  path. The originals-retained guarantee above applies to registered source acceptance
  and subsequent partial-work decisions, not every ingestion/rejection path.
- Per-item batch results remain, but a dispatch-level fingerprint conflict
  refuses the whole call before mutation. This is safer than accepting an
  unseen partial batch; no automatic resolution or merge is performed.
- CAS, per-write checks and editor heartbeats are not an OS lock on Obsidian.
  A narrow check-to-replacement race remains possible with external writers.
- Filesystem/index updates are not a multi-resource transaction. Interrupted
  operations use existing recovery checkpoints, not automatic replay or a
  promise of exactly-once acceptance.
- Staging review/deep-read provider waits are not claimed to be eliminated by
  this slice. Runtime enforcement, lens-store ownership and the Windows WAL stress
  gate remain open.

Verification: `tests/test_staging_safety.py` exercises a coordinated Core,
concurrent accepts, approval-wait retargeting, active editing, sensitivity,
stale review tokens, hidden dependencies and file/index thread boundaries.
The browser smoke walk also exercises stale review, preserved form edits,
explicit reload and successful revision acceptance without live providers.
Implementation: `90b1945`. The combined staging/upkeep packet passed **1,060
tests, 2 skipped, 1 deselected**, plus UI build and browser smoke. The focused
commands and generated full-log location are in `regression-manifest.md`.
Taxonomy continuation adds `tests/test_core_taxonomy.py` for write/index thread
ownership, approval races, mid-round edits, concurrent plans, topic-row progress,
restart, alias/filename safety and unchanged person/agent gates. The expanded
browser walk verifies stale topic review and structured refresh failure UX.
Taxonomy implementation: `fc58af2`; **145 focused tests**, **1,084 passed,
2 skipped, 1 deselected** in the full suite, plus UI build/browser smoke. The
static direct-index construction debt falls **8 → 6**; the single-owner release
gate is not yet closed.

## Source-only acceptance batches

The registered `staging_decide` now uses Core callbacks for batches consisting
only of new-source items (invalid IDs still get individual errors). All valid
source plans are resolved before approval. Raw and cleaned copy destinations
are reserved across the batch without writing files; previews use the same
reservation logic. Duplicate note names are refused across source kinds, not
just within a folder. A batch cannot share one item's edited prose/fields;
review those individually, as before. Interrupted promotions also still
require individual person review rather than a bulk finish shortcut.

The combined inventory includes each staged snapshot and all source, view,
concept, attachment and policy dependencies. Inconsistent shared snapshots
refuse during preparation; the existing **200-file** recovery bound applies
to the whole operation, not independently to each item. Smaller groups are
required when the combined inventory exceeds it. This is a bounded serialized
operation, not a new queue or a cross-item transaction.

One shared guard checks this inventory throughout execution. Its expected
fingerprints advance only to known bytes written by this operation. It does
not refresh arbitrary fingerprints to make the next item's plan pass. This
lets later source writes render current backlinks/views without losing earlier
sources or human concept prose. Final staged-state writes advance that same
guard, so prior successful decisions do not appear to be external conflicts.

An initial lease or stale approval blocks before any copy. A later external
edit stops remaining work and returns `completed_paths`, `completed_results`
and a normal conflict checkpoint. A conflict can precede the final session
handoff pass: review those handoffs as well before retrying remaining items.
Caught per-item IO errors retain only that item's partial progress; unchanged
other items can finish. A stopped service aborts later items without copying
their inputs and retains earlier decisions. Nothing is automatically retried,
rolled back, promoted, rerouted or marked as research kept.

Every source keeps its own origin session, rather than inheriting a shared
batch origin. A missing origin session no longer creates a log lacking an
opening event or hides accepted results. The source's provenance remains
unchanged; a structured `handoff_warning` asks for session inspection, and the
shared UI distinguishes that warning from the durable library decision.

The static construction debt remains **3**: mixed-kind/multi-topic staging
acceptance (one serving site) and graph/extract's explicit offline branches
(two). Full runtime ownership enforcement, Windows concurrency stress and
encoder/transport writer waits remain open. Commit `74c6081` later added
collision-safe fresh-rejection targets plus complete/partial attachment
fingerprints while retaining originals. The source-only path preserves
originals; this is not deployment-wide
deduplication or an all-path source-preservation guarantee.

The conservative shared guard currently rehashes the combined dependency set
at each write. Large-PDF batches can therefore be I/O-heavy even below the
200-file bound; use smaller groups. No batch throughput improvement is claimed.
Optimizing this requires measured per-item write receipts/preconditions, not
replacing content hashes with unchecked stat-based rebasing.

Verification: **204 focused tests passed**, including **22 new batch checks**;
UI build and expanded browser smoke passed, preserving the picker and normal
staging flows and checking explicit finish plus the missing-session warning.
Implementation: `c48e6a0`. Frozen-source full suite: **1,188 passed, 2 skipped,
1 deselected in 439.18s**. Exact command and local final log are recorded in
`regression-manifest.md`. No live/paid provider evaluation was performed.

## Mixed-kind and multi-topic acceptance

Registered staging acceptance no longer calls `engine_for`, including mixed
source/import/revision/lens batches and multiple topics. Each call resolves a
bounded file footprint before approval. It includes staged records, source and
copy destinations, topic/master views, concept backlinks, configuration and
schema dependencies, plus known future source/import member paths that a later
topic may refile. The complete footprint must fit the existing 200-file bound.

Execution preserves caller order. Before each mixed item it checks the shared
hash ledger, then replans derived text against earlier verified Core writes.
Source prose/request hashes and topic wording/rows remain the approved ones.
A fresh plan's writes and dependencies must remain within the footprint, with
fingerprints equal to known current ledger values. It cannot adopt arbitrary
outside edits as its baseline or discover a new file and silently authorize it.
Undeclared scope returns a normal write-conflict checkpoint with completed
paths/results and asks for another review.

This prevents later topic plans replacing an earlier table row or overwriting
earlier revised prose while refiling. A topic later in the list can file a
source or typed source import accepted earlier in that call. A topic earlier
in the list does not defer/retry missing members automatically; its result
still reports them as unavailable at that step. Concept imports remain
explicitly reviewed imports; ordinary concept acceptance still needs its own
person-authored definition. Agents do not gain taxonomy authority or multi-note
revision-token privileges by composing a batch.

Staged state commits advance the same ledger. Caught source/topic failures
retain item-local progress when the staged record remains unchanged. Progress
recording has a narrow staging-record-only CAS; it cannot write policy files
or bypass a stale staged edit. Later items cannot modify a primary note left
partially written by an earlier failed item: finish/reconcile it individually
first, preserving its recovery fingerprint. A failed final progress save or a
hard crash can still require manual operation-log reconciliation; resumability
is not guaranteed for every failure. Imported files/revisions and the separate
lens store do not acquire a new cross-resource transaction or automatic repair.

Distinct topic names with the same Windows-safe index filename are refused
before the later topic row is written. A later legitimate topic cannot erase
an earlier index just because their normalized filenames coincide.

Mixed dry-run responses retain source coverage/sections/copy information and
revision `would: merge` wording, and declare `ordered_replanning: true`.
They are a read-only footprint/initial-feasibility preview, not an exact
simulation of later SQL outcomes after preceding items. No approval or file
mutation is performed by preview; normal derived-index refresh can occur.
The shared UI, picker, existing single-item APIs and explicit review controls
are unchanged. No new event store, permission path or implicit promotion exists.

The static direct-index debt falls **3 → 2**: graph/extract's explicit offline
branches remain. This does not close INDEX-04 runtime fallback enforcement,
INDEX-05 Windows/desk/lens concurrency stress, or G1. Fresh-item quarantine
relocation, whole-footprint rehashing cost and writer occupancy during encoder
IO remain documented limits. Adoption/dedupe, adapters, Session harness and
integrated release acceptance remain separate work.

Verification of mixed acceptance: implementation `87e2460` passed **185
focused tests** (27 new), UI build/browser smoke, nine extra targeted ordering
and refiling executions, and a frozen-source full run of **1,215 passed,
2 skipped, 1 deselected in 458.38s**. Final local log:
`tmp/mixed-acceptance-full-2026-10-25-02.log`. Two development acceptance
failures did not reproduce; their cause remains unestablished. The earlier
development full run also exposed a distinct watcher PermissionError/thread
crash warning. The final mixed run had no warning, but absence of a warning
does not fix that separate failure path; see the watcher continuation below.

## Watcher read-failure recovery

The polling watcher retries failed filesystem observations without consuming
the pending event. A locked/unreadable note blocks only that document until a
successful rescan; passing the one-second quiet window or expiring an editor
heartbeat cannot clear an unresolved read failure. Exact known Core bytes do
not create a false human-edit conflict on recovery. Unknown/mismatching bytes
use normal debounce, including a human save immediately after a Core save.

Read failures during an editor heartbeat preserve the active editor lease.
A post-commit fingerprint read failure does not retroactively turn a durable
write into a failed mutation: it pauses that note for a conservative rescan
instead. Partial directory walks retain known entries rather than interpreting
unobserved files as deletions. Unexpected programming errors are not swallowed.

`/api/meta.non_secret_health.watcher` reports ready/degraded/failed/stopped
states, a pending-read count, and bounded relative-path/error-class diagnostics.
It does not expose raw exception messages or provider/source text. This is
operational health evidence, not a new UI alert or automatic overwrite/replay.
The poller still scans visible Markdown in its current vault scope; adopted
root scoping/large-tree budgeting remains DEPLOY work. This packet is not
proof that the earlier two development acceptance failures shared this cause.

Focused verification passed **210 tests**, including **17 new watcher
regressions**, with `PytestUnhandledThreadExceptionWarning` promoted to an
error. UI TypeScript/build and the complete browser smoke passed, including
the existing model-selection and interrupted-staging UX. Implementation:
`89e609d`. Frozen-source full verification passed **1,232 tests, 2 skipped,
1 deselected in 422.29s**, with thread warnings treated as errors and no
warnings reported. Exact command/log: `regression-manifest.md`.

## Runtime ownership continuation

`ded98c0` now refuses direct/cached engine fallback in serving Contexts,
validates service/vault identity, and makes graph/extract offline use explicit.
The static serving-debt list is empty (**2 → 0**); low-level infrastructure
and separately reviewed desk/lens stores are not counted as serving debt.
This does not close G1 or replace INDEX-05 concurrency verification.

`e40a4a6` coordinates only a Core fingerprint handle and final atomic
replacement of that same canonical path. A native Windows fixture shows why
an open reader can deny replacement. The fix closes the Core handle first;
it does not retry/replay a mutation, lock the whole vault or hide outside
reader/ACL errors. The native mechanism does not establish the cause of the
earlier intermittent acceptance failures. See [index-ownership.md](index-ownership.md)
for offline compatibility, explicit limitations and the remaining extract
revision-pinning contract gap. The expanded focused group passed **381 tests**;
the revised coordinated MCP/revision follow-up passed **149 tests**. UI build
and complete smoke passed. Final frozen-source full verification passed
**1,284 tests, 2 skipped, 1 deselected in 434.41s**, with thread warnings as
errors and no warnings reported. Test snapshot: `d31cda5`; exact commands,
earlier failures and final local log are in `regression-manifest.md`.
