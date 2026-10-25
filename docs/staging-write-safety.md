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
| New source | Source note, optional attachment move, concept backlinks, topic/master indexes, optional vectors, staged record | Staged dependency only; **multi-target protection unfinished** | Legacy engine path |
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

## Remaining limits

- Full new-source and mixed/batch topic promotion need a resolved mutation plan
  including attachment destinations, generated views and linked concept notes.
  Do not wrap the complete promotion in an index callback: it writes files and
  may run vector IO. Attachment movement before all validation is still debt.
- Per-item batch results remain, but a dispatch-level fingerprint conflict
  refuses the whole call before mutation. This is safer than accepting an
  unseen partial batch; no automatic resolution or merge is performed.
- CAS, per-write checks and editor heartbeats are not an OS lock on Obsidian.
  A narrow check-to-replacement race remains possible with external writers.
  New-source promotion still needs these interruption boundaries throughout.
- Filesystem/index updates are not a multi-resource transaction. Interrupted
  operations use existing recovery checkpoints, not automatic replay or a
  promise of exactly-once acceptance.
- Staging review/deep-read provider waits are not claimed to be eliminated by
  this slice. Source promotion, lens-store ownership and the Windows WAL stress
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
