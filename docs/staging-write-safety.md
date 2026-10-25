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
| New sources in multi-item batches | Same promotion effects, legacy attachment relocation | Staged dispatch dependency only; **multi-target protection unfinished** | Legacy engine path |
| Single topic acceptance | `About/Topics.md`, optional source refiling, topic/master indexes, staged record | Staged review token; prepared target/dependency CAS; per-write guards; retained partial progress | Core callback |
| Topic acceptance in mixed/multi-item batches | Same taxonomy effects | Staged dispatch dependency; per-write domain guards, but **pre-approval multi-target inventory unfinished** | Legacy engine path |
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
adoption only**. The single-source continuation below also uses it; multi-item
source/topic acceptance still retains a legacy serving path. Catalogue encoder IO releases SQLite, but
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
It deliberately differs from multi-item and offline legacy relocation, which
are still debt. No background cleanup of retained originals is performed.

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

- Multi-item new-source and mixed/batch topic promotion need a resolved mutation plan
  including attachment destinations, generated views and linked concept notes.
  Do not wrap the complete promotion in an index callback: it writes files and
  may run vector IO. Legacy multi-item/offline attachment movement remains debt.
- Rejecting a fresh, non-partial source still uses the legacy quarantine/move
  path. The originals-retained guarantee above applies to single-source accept
  and subsequent partial-work decisions, not every ingestion/rejection path.
- Per-item batch results remain, but a dispatch-level fingerprint conflict
  refuses the whole call before mutation. This is safer than accepting an
  unseen partial batch; no automatic resolution or merge is performed.
- CAS, per-write checks and editor heartbeats are not an OS lock on Obsidian.
  A narrow check-to-replacement race remains possible with external writers.
  Multi-item promotion still needs the single-item interruption boundaries.
- Filesystem/index updates are not a multi-resource transaction. Interrupted
  operations use existing recovery checkpoints, not automatic replay or a
  promise of exactly-once acceptance.
- Staging review/deep-read provider waits are not claimed to be eliminated by
  this slice. Multi-item promotion, lens-store ownership and the Windows WAL stress
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
