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
The registry's existing 100-item list limit bounds these note/staged-record
dependencies to its 200-fingerprint durable recovery limit. As before, larger
lists are clamped with `adjusted_arguments`; callers must submit the remainder
separately. This slice adds no new batch truncation behavior.

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

| Acceptance kind | Visible effects | Current protection | Index access |
| --- | --- | --- | --- |
| Source revision | Existing source sections; previous section text retained on staged item | Destination revision, staged dependency, target lease, sensitivity policy | Core callback |
| Concept | One new `Concepts/<name>.md` | Staged dependency; destination snapshot/missing guard; target lease | Core callback |
| V1 import | One new explicit target note | Staged dependency; destination snapshot/missing guard; target lease | Core callback |
| Lens | Separate lens store, plus staged lifecycle record | Staged dependency; serialized acceptance | Separate SQLite store; INDEX-05 review remains |
| New source | Source note, optional attachment move, concept backlinks, topic/master indexes, optional vectors, staged record | Staged dependency only; **multi-target protection unfinished** | Legacy engine path |
| Topic | `About/Topics.md`, optional source refiling, topic/master indexes, staged record | Staged dependency only; **multi-target protection unfinished** | Legacy engine path |

Deep-read schema/note lookups and acceptance previews now use Core index
callbacks. Clerk/deep-read processing runs after the callback returns. Covered
Markdown writes stay on VaultWriter; index updates stay on IndexService. An
unavailable service refuses before covered acceptance mutates content. Offline
domain callers keep their explicit Engine compatibility path.

## Remaining limits

- Full new-source/topic promotion needs a resolved, versioned mutation plan
  including attachment destinations, generated views and linked concept notes.
  Do not wrap the complete promotion in an index callback: it writes files and
  may run vector IO. Attachment movement before all validation is still debt.
- Per-item batch results remain, but a dispatch-level fingerprint conflict
  refuses the whole call before mutation. This is safer than accepting an
  unseen partial batch; no automatic resolution or merge is performed.
- Initial CAS and editor heartbeats are not an OS lock on Obsidian. External
  edits can still occur during a multi-step operation; per-write validation
  and interruption boundaries remain necessary for the full promotion path.
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
