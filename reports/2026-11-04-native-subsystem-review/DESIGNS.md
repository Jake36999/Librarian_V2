# Concrete native designs

Proposals only, 2026-11-04. All mutations remain Core-brokered; SQLite projections use IndexService and durable vault writes use VaultWriter. Do not add an external database, orchestrator, or second authoritative task ledger. Existing durable evidence/configuration stores remain valid exceptions to Markdown note authority.

## 1. Encoder release: preserve the delivered fix and tighten recovery

Current path: `tools/staging.py:_StagingEmbeddingContinuation.finish` → `embed.sync_source_via` → short IndexGateway callbacks → `promote.embedding_success/failure` through a second VaultWriter submission. Source promotion and catalogue adoption also call `sync_source_via`. The unified plan records this as implemented. Calling `conn.commit()` while retaining the enclosing writer callback would not release either queue; explicitly returning from both owners is essential.

Required sequence:

1. **Publish:** VaultWriter validates staged/destination revisions and leases, writes the accepted note with existing `EMBEDDING_PENDING`, and captures a full-byte fingerprint. IndexService upserts it and commits. Return an immutable continuation containing values, never an Engine/connection/cursor.
2. **Prepare:** a short IndexService callback copies `{chunk_hash, heading, text}` plus document identity, source revision and representation fingerprint. Commit/return before model loading or encoding. The current implementation already follows this separation.
3. **Compute:** encoder loading, network calls, NumPy conversion/normalization and vector construction occur outside both queues. Deadline/cancellation are checked between batches and before commit. Shared host admission remains authoritative.
4. **Commit derived batch:** IndexService rechecks representation/configuration and surviving source/chunk identity. Insert only still-applicable vectors in one short transaction; mismatched results become stale. Never hold a transaction across encoder work. Count actually inserted/skipped rows rather than reporting the number originally planned as completed.
5. **Settle:** VaultWriter CAS-checks the published fingerprint and operation identity before removing pending status or recording failure. A newer note wins. A failed derived update must not roll back accepted Markdown. A stopped Core must not fall back to direct writes.

Proposed staged-record delta (retain current promotion fields):

```json
{"embedding_job":{"v":1,"operation_id":"embed-...","source_path":"Sources/A.md","source_revision":"sha256:...","representation":"sha256:...","chunk_manifest":"sha256:...","state":"pending","attempt":1}}
```

Use the existing pending marker and staged record as recovery authority; no new jobs database. Append `embedding_prepared`, `embedding_batch_committed`, `embedding_settled` references to the owning session when one exists. On restart scan pending records, obtain current authorization/route policy, and replan from current bytes. Old vectors may remain a content-addressed cache, but cannot establish completion for a different operation. A crash between note publish and staged update is detected by the note's pending marker; recovery records uncertainty and does not clear it speculatively.

No SQLite schema change is required for this fix. Keep `embedding(hash, model, dim, vector)` and representation metadata for now. Add coverage counters to the continuation result; avoid a competing durable vector-job state machine. Offline Engine compatibility paths must stay explicitly offline; test that active-Core surfaces never select them.

## 2. External rename: preserve attached chunks before deletion

Current order in `Index.refresh`: upsert destinations → delete vanished paths with `keep_documents=False` → reconcile `document` identities. The identity table survives long enough to match a move; the document chunks do not.

Minimal fix needs **no table migration**:

```diff
- delete vanished rows including document chunks
- commit
- reconcile document identities
+ delete vanished note/facet/link/component and non-document chunks only
+ reconcile document identities against the completed observed tree
+ for each unambiguous move: transfer old document chunks to destination
+ remove remaining orphan document chunks only after reconciliation settles
+ commit all identity/chunk/FTS changes together
```

Within the IndexService transaction, use the returned `{doc_id, from, to}` mapping. Resolve destination `note.name`, then `UPDATE chunk SET path=?, note=? WHERE path=? AND role='document'`. Preserve chunk IDs, ordinal, heading, text and hashes. `chunk_fts` indexes heading/text by rowid, so unchanged moved chunks require no FTS rewrite; content-addressed embeddings remain valid. Do not rewrite inbound Markdown links automatically.

Preconditions: unique file-identity or exact-byte match from `document_identity.reconcile`; no destination document-chunk set conflicting with the old set; and unchanged attachment evidence identity. For a rename accompanied by edits, compare attachment references and extraction manifest hash. If attachment identity cannot be established, quarantine/re-extract rather than attach old PDF text to a new source. Never match only by basename, normalized text or URL. On ambiguous copies retain evidence for recovery but do not expose orphan chunks in retrieval.

Refresh currently commits each reconciliation pass. Change each pass to resolve moves before its commit; on an unsettled filesystem preserve unattached document chunks outside search visibility for the next pass rather than prematurely deleting them. All document-chunk retrieval must join a live note. Rebuild must use the same stable document mapping rather than ambiguous names.

Follow-on rebuildability improvement: add an attachment extraction manifest to the accepted source's existing evidence references, `{attachment_sha256, extraction_version, text_sha256, pages, evidence_id}`. Persist extracted text with the evidence when it cannot be deterministically recovered locally. Derived SQLite can then be deleted and rebuilt without silently depending on the chunks it previously contained. This is distinct from the minimal rename fix.

## 3. Evolving knowledge: authority and exact data shapes

Keep source notes descriptive. Add optional `knowledge` frontmatter to the vault's **About/Note Content Model.md** through an explicit schema-change review; `schema.py` remains the parser/validator, not the authority that invents a domain schema. Existing notes remain valid and are marked temporally unspecified, never backdated automatically.

```yaml
knowledge:
  version: 1
  claim_id: claim-42
  revision_id: claim-42-r2
  scope: {library_id: lib-A, project_id: project-P, goal_epoch: 3}
  perspective: {lens_id: lens-7, lens_digest: "sha256:..."}
  valid_from: "2026-10-01T00:00:00Z"
  valid_until: null
  status: accepted
  supersedes: [claim-42-r1]
  supports:
    - set_id: support-1
      premises:
        - {id: source-9, revision: "sha256:...", evidence_id: ev-9, locator: "page 4"}
  conflicts_with: []
```

This illustrates one claim-note revision; multi-claim notes use a versioned list with unique claim IDs and section anchors. `accepted` is an editorial decision, not verified truth. Store old full note bytes in existing immutable EvidenceStore before an approved overwrite; reference that snapshot in a session event. Do not pretend mutable current frontmatter preserves history by itself.

Proposed session JSONL payload, within the existing event envelope:

```json
{"type":"knowledge_revision","v":1,"operation_id":"op-42","claim_id":"claim-42","revision_id":"claim-42-r2","prior_revision":"claim-42-r1","source_snapshot":"ev-raw-42","note_sha256":"...","scope":{"library_id":"lib-A","project_id":"project-P","goal_epoch":3},"decision":"accept","reason":"new requirement","recorded_at":"2026-11-04T10:00:00Z"}
```

Use session sequence as transaction order, not model-supplied timestamps. `valid_from/until` expresses applicability in the world; recorded time/sequence expresses what Core knew when. A retroactive correction is a new revision/event, never editing an old event. A manually edited note is observed at refresh time with an `observed_external_revision` event; no claim of earlier knowledge. Historical queries return unknown if no retained snapshot exists.

Proposed **derived** additions to `index.py:SCHEMA` (version migration required; names are new):

```sql
CREATE TABLE claim_revision (
  library_id TEXT NOT NULL, claim_id TEXT NOT NULL, revision_id TEXT NOT NULL,
  scope_key TEXT NOT NULL, note_path TEXT NOT NULL, snapshot_id TEXT NOT NULL,
  note_hash TEXT NOT NULL, valid_from TEXT, valid_until TEXT,
  recorded_event TEXT NOT NULL, recorded_seq INTEGER NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('accepted','disputed','withdrawn','unknown')),
  PRIMARY KEY(library_id, revision_id)
);
CREATE TABLE claim_supersedes (
  library_id TEXT NOT NULL, newer_revision TEXT NOT NULL, older_revision TEXT NOT NULL,
  PRIMARY KEY(library_id,newer_revision,older_revision)
);
CREATE TABLE claim_support (
  library_id TEXT NOT NULL, conclusion_revision TEXT NOT NULL,
  support_set TEXT NOT NULL, premise_id TEXT NOT NULL, premise_revision TEXT NOT NULL,
  evidence_id TEXT NOT NULL, locator TEXT NOT NULL,
  PRIMARY KEY(library_id,conclusion_revision,support_set,premise_id,premise_revision)
);
CREATE INDEX claim_support_reverse ON claim_support(library_id,premise_id,premise_revision);
```

Rebuild these from current Markdown, retained snapshots and session revision events; never store sole authoritative belief state in derived SQLite. Validate references and cycles in Core before projection; unresolved references remain explicit unknowns. Reject malformed intervals. Scope keys are canonical encodings, not free-form similarity matches. A withdrawn revision can still be retrieved for historical explanation.

**Bitemporal behavior:** for query `(valid_at, known_at, scope)`, select events known by the recorded cutoff, follow supersession only within applicable scope, and evaluate half-open validity intervals. An old assertion remains the answer to “what did we believe then?” even if corrected today. Supersession can cover only part of an interval; do not globally hide the older revision outside the newer interval.

**ATMS-style dependency invalidation:** premises inside a support set are AND; alternative sets are OR. Traverse reverse dependencies when a premise revision becomes unavailable/inapplicable. Recompute applicability to a fixed point; a conclusion remains supported if any complete support set survives. Cyclic support alone supplies no evidence. Cap work per operation and mark overflow unknown pending recomputation. This is a bounded support-maintenance algorithm, not a claim to implement a complete ATMS. An invalid extraction is different from a disputed real-world claim.

**AGM-inspired revision:** detect conflicts and stage alternatives with evidence, scope and retained reasons. Apply a minimal explicitly approved change, preserving independent support and unrelated claims. Do not claim full AGM postulates for natural-language beliefs: this system lacks logical closure and a complete contradiction oracle. Competing perspectives may coexist; a lens switch changes the query scope and derived assessment, not global source facts. Hard permissions in `rules.py` cannot be revised by belief updates.

`profiles.py` remains library initialization policy. Session events record `{goal_epoch, content_model_hash, profile_digest, selected_lenses:[{id,digest}]}` when perspective changes. Keep `lenses.sqlite` as accepted configuration; snapshot the selected lens definition/digest in run evidence. Ranking results and benchmark labels bind to this scope and corpus/evaluation digests. New goals invalidate applicability, not historical evidence.

## 4. Live execution quotas and quarantine

Polling a writable host directory cannot enforce a hard byte/file ceiling: an adversarial process can exceed it between polls. Do not advertise a polling monitor as disk containment.

For snippet execution replace the writable host landing bind with a bounded container-local filesystem: a verified tmpfs size and inode ceiling on the supported Docker/WSL backend, charged to the container memory limit. Disable Docker log persistence for these jobs or configure bounded logging. Workbench's larger output needs either the same bounded staging model or a tested filesystem quota backend. If a backend cannot enforce bytes and inode count, refuse that contained execution profile rather than silently providing an unbounded volume. Keep source/input mounts read-only.

Tmpfs contents do not survive container stop. For tmpfs output, use a trusted supervisor that terminates and reaps the untrusted process group while retaining the container for bounded export; verify the producer has no remaining processes or writable handles before exporting. If the entire container must be killed, discard tmpfs outputs and record their loss. Alternatively use a tested quota-backed persistent volume, stop the producer container, then export using a read-only helper. Do not rely on `--rm` where it would destroy evidence needed for export. Count directories and files, reject links/devices/path escapes, bound depth/name length, detect short/truncated members, hash while streaming, and write to a private quarantine directory. Each write checks remaining byte/file budget before creating/extending the destination. No indexed, executable or accepted artifact until the manifest is complete and policy allows promotion.

Extend `sandbox.drain` with shared atomic counters and one idempotent stop request on stdout/stderr produced-byte limits, cancellation, deadline, or runner failure. Preserve bounded tails separately. Kill the container/process tree, wait for exit, inspect absence of active descendants, then remove container and temporary resources. A failed kill/inspect produces `cleanup_unknown`; retain quarantine and block success. Host Job Object mode remains explicitly non-isolated with no network-isolation claim; it is ineligible for isolated replication assertions. Docker absence means inspect/retry or a separate person-approved host operation, never automatic fallback.

Add fields to existing sandbox/workbench run records (not another runner database):

```json
{"execution_v":2,"state":"quarantined","stop_reason":"output_quota","limits":{"artifact_bytes":52428800,"artifact_files":200,"stdout_bytes":1048576,"stderr_bytes":1048576},"observed":{"artifact_bytes":0,"artifact_files":0,"stdout_bytes":1048577},"cleanup":"verified","environment":{"source_commit":"...","source_tree":"...","image_digest":"sha256:...","runtime_version":"...","platform":"...","input_manifest":"sha256:...","argv_digest":"sha256:...","dependency_manifest":"sha256:...","network":"none"},"artifacts_manifest":"sha256:..."}
```

Numbers are proposed defaults to test, not measured optimal values. Record missing fingerprints as unknown and downgrade replay eligibility. Disk limits must include setup archives, output, runtime logs and export copies, with a global admission cap for concurrent runs; per-run limits alone can still exhaust the machine.

## 5. Native recipe replay: extend workflows and macro runtime

Keep `workflows.py` as the sequential interpreter. Its earlier-step references already form an acyclic dataflow graph; do not create a new DAG scheduler. Resolve the complete child-workflow/route closure at start and retain exact accepted YAML plus digests in existing evidence. `run.started` gains `recipe_manifest`, source/input hashes, selected scope, environment manifest, parent session and replay mode. Resume uses pinned definitions, or refuses drift; it never loads a changed child silently.

Add optional per-step `replay: never|read_only|reconcile` and declared output verifier metadata to the validated YAML grammar. Default mutating/external actions to `never`. Registry remains the sole action dispatcher. Macros retain expanded-plan checkpoints and per-step Broker gates, but use the same RunStore step-record helper instead of inventing separate resume semantics.

Before dispatch append `step_intent` with `{step_key, attempt_id, input_digest, definition_digest, operation_id, expected_revisions}`. After dispatch append `step_result` with `{operation_id, result_handle, result_digest, receipt_refs, verifier_result}`. Bind mutable Core effects to the same operation ID in their existing recovery record. Crash after effect but before result becomes `outcome_unknown`; a registered reconciler checks the durable target/effect receipt before deciding to reuse or retry. External sends/pushes without idempotency or reconciliation require a person decision. A JSONL completion cursor alone cannot guarantee exactly-once effects across filesystem/provider boundaries.

Distinguish three operations: resume an interrupted run; replay stored evidence without side effects; rerun a recipe against new inputs/environment. Rerun creates a new run linked by `derived_from`, never overwrites the old result. A changed goal/lens/evidence revision invalidates dependent step reuse, not unrelated historical outputs.

Extend `claim_run.run` with an explicit pinned revision and reviewed image digest. Fetch that exact revision and verify commit/tree before running; keep the current “test latest” option clearly labelled as new-version testing. Persist failing input, interpreter/dependency identity, argv, seed/locale where relevant, output hashes and verifier version. Exact reproducibility applies only to deterministic tools under declared controls; recorded model output can be replayed, but a new model call is not promised to be bit-identical.

## 6. Service receipts and migration fidelity

Use an operation envelope across PDF cleanup/OCR/STT/TTS/search: operation/attempt ID, library/session identity, input hash, route and adapter fingerprints, reserved estimate, cancellation generation, output evidence IDs and receipt. Normalize failures to configuration, authentication, quota, transient transport, invalid output, cancelled, stale assignment, and outcome unknown. Preserve original safe diagnostic codes. Reserve before sending, settle actual cost when known, and retain uncertain liability when a request may have been billed. Rejecting a late result is not proof of transport cancellation or zero cost.

TTS's existing personal global cap needs a local process-safe reservation ledger across vault Cores, outside the vault beside its current spend ledger. A short OS file lock plus durable reservation events is sufficient; no server. Expired in-flight reservations are reconciled or remain uncertain, never silently refunded. Store no credentials in receipts. Cache identity includes route/adapter version and output-affecting options; cached responses link to original evidence.

Migration reads each V1 note once using a stable byte snapshot, parses those same bytes, and records full hash. Extend the existing import manifest/history with stable `source_root_id`, per-source revision, target identity, attachment manifest and edge reconciliation rows: `{from_old_id,to_old_id,kind,status,target_from,target_to,reason}`. Status is preserved, unresolved, excluded or intentionally transformed; never silently dropped. Preserve V1 evidence/session history as inert imported evidence, not active instructions or approvals. Copy referenced attachments through existing guarded staging, and verify hashes before acceptance. Resolve name collisions with explicit mappings; missing endpoints stay unresolved, not guessed. Re-running a bounded batch must accumulate mappings across prior batches, even when the latest summary only lists the latest staged IDs.

Batch reuse key becomes `(library_id,item_id,input_revision,stage,stage_version,route_or_recipe_digest)`; stale stages rerun from the earliest affected dependency, and old results remain evidence. Library switching must bind operation callbacks and result handles to the originating library ID. `libraries.py` supplies locations only; it must not imply cross-vault graph merging or global memory.
