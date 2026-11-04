# Unified requirements and specifications

[01 Report](</D:/Librarian_V2/reports/2026-11-04-master-finalization/01-MASTER-SYSTEM-REPORT.md>) · [02 Specification](</D:/Librarian_V2/reports/2026-11-04-master-finalization/02-UNIFIED-REQUIREMENTS-AND-SPECIFICATIONS.md>) · [03 Plan](</D:/Librarian_V2/reports/2026-11-04-master-finalization/03-MASTER-FINALIZATION-PLAN.md>) · [04 Integration](</D:/Librarian_V2/reports/2026-11-04-master-finalization/04-PLAN-INTEGRATION-SUMMARY.md>)

Prepared 4 November 2026 against `40ec923f5d7cb5612939b9fc456963b88e0af4a3` on `master`. **Proposed synthesis for approval; not runtime implementation or release certification.** The current user request governs; transcript instructions are historical evidence.

## 1. Scope, authority and requirement naming

This is a proposed canonical addendum, consolidating MC-01..16, the native designs, UI D1..D6 and Settings/Staging/Search corrections. “Must” defines the proposed acceptance contract, not current implementation. Existing Core security/closure policy remains controlling. All new runtime work is planned unless document 01 explicitly says delivered.

**Architecture invariant A-01.** Python single-owner Core; SQLite through IndexService; durable vault mutations through VaultWriter; existing Session/run JSONL and recovery records; Markdown as note truth, immutable EvidenceStore for captured inputs and `.librarian/` sidecars for manifests/derived views; vanilla TypeScript/CSS for both hosts. No Temporal, XTDB, LangGraph, CWL runner, GraphRAG, Anki, Inspect AI, React, Vue or Tailwind. No new independent scheduler, belief database, task ledger or browser authority. Acceptance: ownership/transport guards pass and no active-Core fallback constructs private vault state.

**A-02.** Preserve Broker/person permissions, current access checks, staging review, exact revision-CAS tokens and existing verifier authority. Data, including retained transcript instructions and worker paraphrases, cannot elevate permissions or become person requirements through repetition. Acceptance: revoked-access and source-instruction fixtures fail closed at retrieval, handoff and merge; LLM consensus never closes an authoritative predicate.

IDs **MC-01..16 are requirement clauses**, whereas **MEM-01..12 are the review's implementation packets**. The user's shorthand “MC-02 durable handles / MC-03 handoffs” maps operationally to MF-012/MF-021, but canonical clauses remain MC-03 for durable evidence and MC-08/09 for handoff/merge. MF-* is the unique execution namespace.

## 2. Complete memory/context contract

| Requirement | Normative contract | Acceptance | Execution owner |
|---|---|---|---|
| MC-01 | Final route input, protocol/schema overhead and reserved output fit the effective supported allowance. Count after trusted rendering; identify tokenizer/estimate and uncertainty. Essential overflow splits or parks before dispatch. | 50/200 rounds, Unicode/code/schemas and continuation blocks: every dispatch within bound or explicit refusal; no orphan tool result. | MF-011 |
| MC-02 | Derived context preserves typed goal, constraints/exceptions, corrections, unresolved decisions, uncertain effects and required evidence identities. Record source event boundary, revision and omitted categories. | Repeated compaction/restart retains exact constraints; summaries cannot replace authority; distinguish presence from successful model use. | MF-011/041 |
| MC-03 | Promised durable evidence resolves beyond originating Loop with version, locator and representation; current access checked; ephemeral lifetime explicit. | Parent after child exit/Core restart opens exact version or gets changed/missing/expired/forbidden outcome, never silent new bytes. | MF-012/030 |
| MC-04 (conditional) | Procedure reuse carries assumptions/scope/version, outcomes, limitations and applicability checks; old failure is conditional. | Environment fix permits requalification; obsolete workaround rejected; unknown fit remains tentative. | MF-023/036/041 |
| MC-05 (conditional) | Recording and validity times distinct; authorized correction/supersession explicit; independent conflicts unresolved unless adjudicated. | Current/as-of answers differ correctly; corrections affect dependent use; unknown dates not backfilled. | MF-036/037 |
| MC-06 | Library/project/session/role scope checked at read, rehydrate and merge. Private worker context is not automatically shared. | Similar forbidden project leaks no excerpt, count or neighbor; revocation between read/merge prevents dependent use. | MF-012/021/030 |
| MC-07 | Origin and lineage survive retrieval, paraphrase, consolidation and graph projection; duplicate source derivations are not corroboration. | Hostile source instructions remain data; lost lineage stays advisory; duplicated summaries count as one source. | MF-012/021/036 |
| MC-08 | Worker packet includes parent work/revisions, question, snapshot, constraints, scope, allowance and result obligations; result includes evidence/caveats/conflicts/stops/usage. | Late caveat past preview retained structurally or explicit overflow with durable reference; missing prerequisite may be reported without answer. | MF-021 |
| MC-09 | Core merge checks current requirements/contract/evidence/access against stable child identity; receipt and acceptance distinct, deduplicated durably. | Concurrent stale results cannot close revised work; replay accepts once; crash before merge leaves pending, not presumed accepted. | MF-021/030 |
| MC-10 | Shared controlling allowance reserved atomically before parallel/inner/retry/repair/review calls; attribution avoids double count; unknown charges retain reserves. | N workers cannot each spend remaining cap; two vault TTS requests serialize personal cap; totals reconcile exactly. | MF-019/021/024/028 |
| MC-11 | No eligible match, incomplete search, forbidden/access failure, stale, partial and contradictory evidence distinct; bounded follow-up may abstain. | Two of three required sources yields explicit coverage gap, not complete answer; top-k miss never proves absence. | MF-027/028/038 |
| MC-12 | Evaluate later decisions with optional memory absent/relevant/noisy/outdated; measure benefit and harm, supported decisions, recovery and all costs. | Held-out chained and preservation slices, denominators and stream-level uncertainty; no recall-only pass. | MF-041 |
| MC-13 (conditional) | Consolidation is reversible versioned proposal/view with evidence/status; promotion required for durable accepted knowledge; originals remain usable. | Faulty lesson withdrawal/rebuild loses no original episodes; inferred preference never becomes global instruction; enrichment failure falls back. | MF-036 |
| MC-14 (conditional) | Withdrawal propagates to search/vectors/summaries/caches/worker acceptance/graph views; retrieval suppression distinct from audit retention/byte deletion. | Withdraw, restart, rebuild: no current retrieval; in-flight dependent result refused; retained audit reference accurately disclosed. | MF-012/036 |
| MC-15 (conditional) | Edges distinguish structure/source claims/inference and retain direction/negation/qualifiers/version/scope; graph paths/community are advisory. | Inhibits never becomes promotes; two-hop similarity not causal verification; stale community visible; original lexical evidence fallback. | MF-037/038/039/040 |
| MC-16 | Retrieval/fan-out/rehydration/consolidation/index maintenance have resource ceilings and observable exhaustion; caches cannot evict canonical constraints. | Fan-out, irrelevant recall loop and cache exhaustion stop boundedly; source-loss vs cache-unavailable explicit; no unbounded paid maintenance. | MF-011/012/015/021/041 |

Source clauses and rationale: [memory-context-design-addendum.md:9](</D:/Librarian_V2/docs/proposals/memory-context-design-addendum.md:9>); [REQUIREMENTS-RESEARCH.md:19](</D:/Librarian_V2/reports/2026-11-03-memory-context-review/REQUIREMENTS-RESEARCH.md:19>).

### 2.1 Context assembly and durable handle shapes

Compute `input_allowance = route_context_limit - output_reserve - protocol_safety_margin`. The route manifest identifies whether the limit is total-context or input-only; use its actual semantics. Count the complete rendered request with the route tokenizer when available; an estimated method needs a qualified conservative upper bound, not the current characters/4 assumption. If no safe allowance can be established, refuse the context-sensitive profile with an explicit configuration outcome. Provider-reported usage calibrates later calls; it cannot retroactively make an oversized dispatch safe.

Include current essential Session projection on each audited dispatch, then bounded dialogue and evidence selected within remaining allowance. Preserve tool-call/result groups and provider continuation as indivisible units. Keep required corrections/uncertain outcomes outside optional summary eviction. Never persist hidden reasoning blocks in diagnostics or durable handles; existing ephemeral provider continuation semantics remain intact. Log redacted component counts/digests, method and margin, not prompts.

Proposed v1 reference envelope (ordinary values, never a SQLite connection or capability to arbitrary paths):

```json
{"v":1,"ref_id":"ref-17","lifetime":"durable","library_id":"lib-A","source":{"kind":"evidence","id":"existing-evidence-id","revision_sha256":"<64 hex>","locator":{"kind":"text_span","start":420,"end":690,"unit":"unicode_codepoint"},"representation":"utf8-text-v1"},"scope_ref":"session-event-ref","manifest_ref":".librarian/results/ref-17.json","state":"available"}
```

The Core validates ref IDs and resolves its own allowlisted sidecar; `manifest_ref` is descriptive, not caller-supplied file authority. Persist exact large-result payloads as immutable private sidecar blobs or unframed evidence only when the content fits EvidenceStore's data contract. Search-result sets containing project context must **not** be forced into EvidenceStore, whose structural framing prohibition remains. Sidecar identifies payload digest/length, origin, source versions, access requirements and withdrawal state. Quota/retention policy is explicit per library. Required resumable references are pinned by Session usage; TTL eviction applies only to expendable previews/caches. A missing durable payload returns unavailable, never a recreated newer payload under the same identity.

Existing Loop handles remain private ephemeral previews. Promotion to a parent-readable durable reference is explicit through the Core and current access checks; it does not expose child-private context. Locator interpretation is tied to the stored representation; byte offsets and codepoint offsets never mix. Outcomes: `available`, `changed`, `missing`, `expired`, `forbidden`, `withdrawn`, `integrity_failed`; filtered callers receive only permitted diagnostics.

Default scope/retention policy for this addendum: a durable reference inherits the originating library and intersection of source access with admitted parent work; cross-project sharing is opt-in through existing authorized promotion/configuration, never inferred by similarity. Worker-private results remain child-only until an explicit allowed result packet shares them. Active Session-required references are pinned until the Session's explicit archival/withdrawal policy releases them; derived caches may be evicted without deleting snapshots or canonical constraints. No automatic age-based deletion of evidence/history is introduced. Withdrawal appends an eligibility change through existing Session/manifest ownership and disables current retrieval/merge across derivatives; it is not physical erasure. Physical deletion remains a distinct explicit source operation, leaving only permitted audit metadata and an unavailable outcome for deleted bytes. Historical retrieval rechecks access and never promises to reopen bytes deliberately removed. Numeric storage ceilings must be configured and tested before durable-reference admission; exhausting a ceiling refuses new durable retention rather than evicting active required evidence.

### 2.2 Worker and service envelopes

```json
{"type":"worker_requested","v":1,"operation_id":"op-1","child_id":"w-1","parent_session":"s-1","library_id":"lib-A","input_snapshot":{"epoch":4,"contract_revision":2,"requirements":{"R1":3},"evidence_refs":["ref-17"]},"question":"bounded question","constraint_refs":["s-1:event-12"],"scope":{"project_id":"P","role":"research_helper","roots":["Sources"]},"allowance":{"reservation_id":"res-1","max_calls":3,"max_tokens":8000},"result_contract":"worker-result-v1"}
{"type":"worker_result_received","v":1,"operation_id":"op-1","child_id":"w-1","input_snapshot_digest":"<64 hex>","result_ref":"ref-18","findings":[{"text":"advisory finding","evidence_refs":["ref-17"],"origin":"inferred"}],"caveats":["limited span"],"conflicts":[],"unresolved":[],"stop":"completed","coverage":"partial","overflow_ref":null,"usage":{"receipt_refs":["receipt-1"],"state":"known"}}
{"type":"worker_merge_decided","v":1,"operation_id":"op-1","child_id":"w-1","result_digest":"<64 hex>","decision":"stale","checked_parent_epoch":5,"reason":"requirement changed"}
```

These payloads extend existing Session JSONL, not an additional worker log. Stable merge key is `(library_id,parent_session,child_id,operation_id,result_digest)`; same child/operation with a different digest is a conflict to resolve, not a fresh accepted effect. Core serializes current-state check and durable decision append through existing writer authority. A received result is a proposal; merge acceptance does not itself run a verifier, publish a note, or close a predicate. Replayed receipt settlement is idempotent independently of editorial acceptance.

Common service metadata is carried outside Clerk/Scribe neutral prompts: `operation_id`, `attempt_id`, `parent_session`, `child_id`, `library_id`, `input_sha256`, route/adapter/configuration digests, reservation/receipt IDs, deadline, cancellation generation, output evidence IDs and coverage. Error taxonomy: configuration, authentication, quota, transient_transport, invalid_output, cancelled, stale_assignment, outcome_unknown, with safe original codes retained. Capture, OCR, cleanup, search, TTS and STT charge actual usage if known, conservative reserve otherwise; cache hits link original receipts without billing twice. TTS's personal cap uses a short process-safe file lock plus durable reservation records beside its current user-level ledger, across vault Cores. Expiry is not automatic refund.

If a provider reports actual cost above the reserved bound, record the full actual liability and halt further discretionary dispatch; never hide the overrun to preserve a cap claim. Qualification must establish defensible upper-bound reservations and output limits. Where a true upper bound is unavailable, label estimated monetary enforcement explicitly and do not claim a hard financial guarantee.

## 3. Native ingestion, workflow and migration contracts

| Requirement | Contract | Acceptance | Owner |
|---|---|---|---|
| N-01 / NAT-01 | Deep-read reuse key = source full-byte revision + chunker/version + ordered chunk digest + extraction route/recipe identity. Reuse unchanged chunks by digest; legacy count-only records become stale. | Same-count edit and reorder cannot inherit extracted claims; unchanged chunks demonstrably reuse. | MF-013 |
| N-02 / NAT-02 | Within one IndexService transaction, remove vanished non-document rows, reconcile stable document IDs, transfer document chunks only for unambiguous matching attachment manifests, then purge settled orphans. Live-note joins exclude unresolved orphan chunks. | Move keeps chunk IDs/text/FTS/vector identity; ambiguous copy and changed attachment never cross-attach; injected crash rolls back whole movement. | MF-014 |
| N-03 / NAT-03 | Preserve publish → release owners → compute → derived CAS commit → writer CAS settlement. Pending marker/staged record remains recovery authority; bind operation/source/representation/chunk manifest. No vector-job database. | Blocked encoder leaves unrelated work live; source/route change rejects settlement; inserted/skipped counters reflect actual rows; active Core never enters offline fallback. | MF-022 |
| N-06 / NAT-06 | Snapshot recursive workflow closure and route targets at start into existing evidence; resume only pinned definitions or explicit drift refusal. | Nested child edit cannot execute unseen; unknown action/code/cycle refused; unchanged closure resumes. | MF-017 |
| N-07 / NAT-07 | Validated replay enum never/read_only/reconcile; mutation default never. Shared RunStore helper for intent/result and existing operation recovery; macro expanded plan approval retained. | Death before dispatch, after effect, before result produces provable reuse/retry or outcome_unknown; no blind external send/push retry. | MF-018 |
| N-08 / NAT-08 | Recipe binds exact commit/tree/image/input/environment/argv/dependency/verifier digests, allowed effects, outputs and replay mode. Latest is a new-version run. | Mismatch refuses; missing input/tool could-not-run; stored replay has no side effects; changed environment gets new run derived_from old. | MF-023 |
| N-09 / NAT-09 | All inner Clerk/Scribe/Scout work has operation/parent/reservation/deadline identity without project framing in source-description prompts. Effort log failure is observable before claiming persisted change. | Browser/MCP/batch/worker receipts agree; repairs charged; cancelled task starts no new inner calls; concurrent limits isolated. | MF-024 |
| N-12 / NAT-12 | PDF/OCR/search use common envelopes, raw/derived manifests and page/span coverage; stop between pages/chunks and retain already-dispatched liabilities. | Partial coverage survives; cleanup not mislabeled original; cancelled chunks not sent; backend/route changes invalidate incompatible cache. | MF-028 |
| N-13 / NAT-13 | Read V1 note once, parse those bytes, retain full digest. Batch reuse key `(library_id,item_id,input_revision,stage,stage_version,route_or_recipe_digest)`; earliest affected dependent stage reruns. | Concurrent source change yields one consistent snapshot or refusal; old completion cannot cover new content; post-wait stale output cannot commit. | MF-020 |
| N-14 / NAT-14 | Import manifest accumulates stable source_root_id/source revision/target mapping, attachment hashes and every edge disposition across batches. Histories are inert evidence. | Alias/rename/missing endpoint/attachment fixture accounts for every item; no guessed edge; repeated batches retain mappings; V1 bytes unchanged. | MF-029 |
| N-17 / NAT-17 | Docs/Cowork prompts describe only actual tool contracts and recovery semantics. Do not equate replay with exactly-once, capture bounds with disk quota, or extraction with truth. | Current source/tool-name and test-target checks plus per-packet result links; historical records explicitly superseded. | MF-042 |

Native detailed derivation: [DESIGNS.md:5](</D:/Librarian_V2/reports/2026-11-04-native-subsystem-review/DESIGNS.md:5>); [PACKETS.md:7](</D:/Librarian_V2/reports/2026-11-04-native-subsystem-review/PACKETS.md:7>).

### 3.1 Run JSONL and recovery

```json
{"type":"run.started","v":2,"run_id":"run-1","recipe_manifest":"evidence-ref","input_manifest":"<64 hex>","scope_ref":"session-event-ref","environment_manifest":"sidecar-ref","parent_session":"s-1","replay_mode":"execute"}
{"type":"step_intent","v":1,"step_key":"run-1/step-2","attempt_id":"a-1","operation_id":"op-2","input_digest":"<64 hex>","definition_digest":"<64 hex>","expected_revisions":{"Sources/A.md":"opaque-revision-token"},"replay":"reconcile"}
{"type":"step_result","v":1,"step_key":"run-1/step-2","attempt_id":"a-1","operation_id":"op-2","result_handle":"ref-19","result_digest":"<64 hex>","receipt_refs":["receipt-2"],"verifier_result":{"state":"pass","verifier":"declared-version"}}
```

Extend current RunStore envelope, preserving old replay readers through explicit version handling. Intent precedes effect; the gap between effect and result is reconciled against existing durable target/operation receipts. A cursor cannot prove an external effect occurred exactly once. `resume` continues interrupted work, `replay` reads retained evidence without execution, `rerun` creates a new linked run on newly declared inputs. A changed goal/lens invalidates dependent reuse, not unrelated history.

## 4. Windows/WSL2 Docker resource and teardown contract

**N-04 (MF-015).** Artifact outputs are disk-backed, never charged to RAM-backed tmpfs. No custom in-container supervisor daemon. Preflight records Docker Desktop/engine/WSL/storage-driver identity, digest-pinned image, available backing storage, intended byte/inode ceiling, setup/log/export amplification, global concurrent reservations and quota enforcement capability. A Docker flag accepted syntactically is not qualification. A global WSL VHD cap alone does not prove per-run quota or protect unrelated data. Named volumes or overlay writable layers are not assumed to have usable per-run quotas on Windows.

Qualify a supported native disk-backed quota configuration with rapid-write and tiny-file floods. If the active backend cannot enforce the required byte/inode bound, the contained execution profile is unavailable with a precise preflight reason. A best-effort I/O monitor is additional protection, not a substitute for the hard bound. This is an explicit remaining implementation/host qualification gate. Do not promise a universally working Docker Desktop storage-opt recipe without evidence.

**N-05 (MF-016).** Create/start containers **without `--rm`**. Sources/inputs are read-only and network/CPU/memory/process limits remain existing policy. Native host-side capture owns shared counters for total stdout/stderr and I/O monitoring; overflow/deadline/cancel requests one idempotent stop. Count produced bytes separately from retained tail bytes. Document sampling/buffer overshoot and keep it within predeclared tolerances; never label polling exact containment.

State machine:

```text
preflight -> reserved -> created -> running -> stop_requested
 -> stopped_verified -> export_quarantine -> validated -> disposed
                           |                    |
                           +-> rejected --------+
stop/inspect uncertainty -> cleanup_unknown (no success/promotion)
```

Call docker stop, escalate docker kill as required, wait and inspect that the entire producer container is stopped before export. The stopped filesystem is inert; do not restart it to retrieve artifacts. Use bounded `docker cp <container>:<output> -` tar stream into a private host quarantine. Reject absolute/drive/UNC paths, traversal, alternate streams/reparse hazards, symlinks/hardlinks, devices/FIFOs, duplicate or case-colliding destinations, excessive depth/name length/member count and truncated/sparse-overflow payloads. Count directories and metadata as well as regular files. Check remaining byte/count budget before allocating each destination/write; hash while streaming. No accepted/indexed/executable artifact until the entire manifest passes policy. `docker rm` follows export disposition; failed disposal is reported explicitly, not hidden behind success. Quarantine retention is bounded and visible in the existing run record, not a new job database.

```json
{"execution_v":2,"state":"quarantined","stop_reason":"output_quota","container_id":"nonsecret-id","limits":{"artifact_bytes":52428800,"artifact_entries":200,"stdout_bytes":1048576,"stderr_bytes":1048576},"quota":{"backend":"qualified-disk-backend-id","verified":true,"evidence_ref":"quota-check-ref"},"observed":{"artifact_bytes":8192,"artifact_entries":2,"stdout_bytes":1048577},"cleanup":"verified","export":{"complete":false,"manifest_ref":null},"environment":{"image_digest":"sha256:...","source_commit":"...","source_tree":"...","runtime_version":"...","platform":"windows-wsl2","input_manifest":"sha256:...","argv_digest":"sha256:...","dependency_manifest":"sha256:...","network":"none"}}
```

Numbers above are provisional test-policy examples, not measured optimal defaults. Teardown verification, export completeness, validation and disposal are separate facts. A stopped container can have an incomplete export; `cleanup_unknown` prohibits a safe-completion label. Claim Run stays Docker-only. Person-confirmed `non_isolated_host_exec` remains a distinct Workbench choice with no network-isolation promise, never automatic fallback.

Acceptance: real declared backend tests byte/tiny-file floods, stdout/stderr floods, cancellation, failed kill/inspect, child processes, malformed tar, setup/export concurrency and benign exact hashes. Fake-runner tests supplement but cannot close NAT-04/05.

## 5. Evolving knowledge integrated with DIK and closure

### 5.1 Module responsibilities and authority

| Existing module | Extension / invariant | Acceptance |
|---|---|---|
| [facts.py:697](</D:/Librarian_V2/src/resource_librarian/facts.py:697>) | Keep deterministic catalogue derivation; bind observed facts to source snapshot/version. Do not turn it into a free-form conversational belief writer. | Same snapshot yields same facts; application scope never alters neutral source description. |
| [dik.py:65](</D:/Librarian_V2/src/resource_librarian/dik.py:65>) | Reuse stable datum/edge IDs, origins and typed relationships. Derived DIK JSON gains links to temporal/support manifests; accepted Markdown and evidence remain reconstruction inputs. | Observed/static/source-stated/inferred stay distinct after rebuild; relations retain direction/negation/qualifiers. |
| [evidence.py:77](</D:/Librarian_V2/src/resource_librarian/evidence.py:77>) | Immutable unframed captures; add narrowly validated note_snapshot evidence kind if needed. Store bytes/digests/locators here, scope/approval in Session/sidecars. | Snapshot intact after overwrite; FRAMING_KEYS guard unchanged; project/session metadata cannot enter raw evidence. |
| [closure.py:156](</D:/Librarian_V2/src/resource_librarian/closure.py:156>) | Current applicability/coverage can block reuse; only existing person-named exact/bounded verifier and contract may establish authoritative closure. | Accepted claim, lesson or support graph cannot close a predicate by itself; stale checks refused. |
| [closure_audit.py:150](</D:/Librarian_V2/src/resource_librarian/closure_audit.py:150>) | Recheck current retained evidence and verifier receipts; reference temporal/support state for explanatory invalidation. | Independent check and rerun explicitly distinguished; no hidden relaxation of closure strength. |
| [agenda.py:76](</D:/Librarian_V2/src/resource_librarian/agenda.py:76>) | Derive recheck/review work through existing Markdown task/session mechanisms; no second scheduler or authority to auto-edit goals. | Source change yields bounded review proposal; completion of a reminder does not imply verification. |

### 5.2 Frontmatter, sidecars and immutable history

Content-model change is explicitly reviewed through `About/Note Content Model.md`; `schema.py` validates it and leaves legacy notes valid. Prefer an optional nested `knowledge` block to avoid colliding with existing top-level lifecycle status:

```yaml
knowledge:
  claim_id: claim-42
  status: accepted
  valid_from: 2026-10-01T00:00:00Z
  valid_until: null
  supersedes: [claim-42-r1]
```

`accepted` means editorial acceptance, not general truth. `valid_from: null` means unspecified start, not a known infinite past; absent metadata means temporally unspecified. `valid_until: null` means no stated end, not proof of permanent validity. Multi-claim notes use `knowledge.claims` entries with unique claim_id and stable section anchor, validated as a separate schema variant. Human authors never maintain long premise/evidence/locator SHA-256 lists in YAML.

The immutable proposed `.librarian/knowledge/revisions/<revision_id>.json` manifest binds full note bytes and DIK lineage. This is Core-written metadata for existing note/evidence authority, not a separately editable belief store:

```json
{"v":1,"library_id":"lib-A","claim_id":"claim-42","revision_id":"claim-42-r2","operation_id":"op-42","library_revision_seq":12,"note_path":"Notes/Claim.md","section_anchor":null,"note_sha256":"<64 hex>","snapshot_id":"unframed-note-snapshot-id","scope":{"project_id":"P","goal_epoch":3,"lens_digest":"<64 hex>"},"origin":"inferred","epistemic_status":"source-stated","lifecycle":"reusable","applicability":"unknown","dependency_coverage":"complete_declared","recorded_event":{"session_id":"s-1","position":18,"hash":"existing-chain-hash"},"support_sets":[{"id":"S1","coverage":"complete_declared","premises":[{"id":"datum:source-9:page4","revision":"rev-9","evidence_id":"ev-9","evidence_sha256":"<64 hex>","locator":{"kind":"page","page":4},"locator_sha256":"<64 hex>"}]}],"conflicts_with":[],"lesson":{"episode_refs":["s-1:10-17"],"assumptions":["tool T available"],"failure_conditions":["missing T"],"qualification_refs":[],"counterexamples":[]}}
```

Full SHA-256 fields supplement existing shortened EvidenceStore IDs and Session chain hashes; they do not reinterpret those existing IDs as full hashes. Raw note snapshot payload contains only path/content/encoding/digest, not project or reasons. Framed scope/lesson/approval belongs in the manifest and owning Session.

Proposed Session payload (store adds the existing `t` and `h`; do not change hash algorithm):

```json
{"type":"knowledge_revision","v":1,"operation_id":"op-42","claim_id":"claim-42","revision_id":"claim-42-r2","prior_revision":"claim-42-r1","manifest_ref":".librarian/knowledge/revisions/claim-42-r2.json","manifest_sha256":"<64 hex>","decision":"accept","reason":"authorized correction","library_revision_seq":12}
```

The existing envelope is flat JSONL with Core timestamp `t` and chained `h`, not a fabricated new `payload/seq/prev_hash` wrapper. Event position is the Session line order. For cross-session temporal ordering, Core reserves a monotonically increasing **library revision sequence** through its existing writer operation-intent/recovery seam and persists that sequence in immutable manifests/events; reconstruct the next value from retained committed records, never solely from SQLite. A crashed reservation may leave a gap, never reuse a committed number. A revision becomes eligible only when the existing operation disposition confirms all required note/snapshot/manifest/event writes; incomplete operations yield recovery checkpoints and unknown state, not speculative acceptance. This does not claim a filesystem/JSONL atomic transaction.

Event validation: `knowledge_revision.decision` is `accept`, `dispute`, `withdraw` or `correct`; `observed_external_revision` never implies any of those authorizations. Each carries operation/revision/manifest identity, recorded sequence and safe reason; withdrawal identifies the affected revision/scope and invalidates current derived eligibility. `worker_requested`, `worker_result_received` and `worker_merge_decided` retain their separate phases; merge decision is `accepted`, `stale`, `duplicate`, `conflict`, `forbidden` or `partial`. Unknown new envelope versions cannot execute effects. New public tool callers cannot supply trusted Core recording time, chain hash or sequence; importer-observed historical timestamps stay data fields. Snapshot/manifest integrity and replay compatibility tests cover every event kind.

Retain old full bytes before approved overwrite. Manual external edits generate `observed_external_revision` at observation time with current snapshot and unknown approval; never backdate when Core knew it or resurrect an accepted state from arbitrary YAML. New accepted revision must match the reviewed source fingerprint/CAS; later edits immediately make that projection stale. Historical access remains subject to current permissions.

### 5.3 Exact proposed SQLite migration

These are **new derived tables**, owned by the current IndexService connection and schema migration machinery. Reserve the next schema version at implementation time (baseline is schema 5); do not mutate this checkout. Foreign keys refer only to locally projected revision identities; evidence/premise resolution is validated by Core, with missing references explicit. UTC timestamps are canonical fixed-format strings validated before insertion; SQL checks are a second guard, not a timestamp parser.

```sql
CREATE TABLE claim_revision (
  library_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  revision_id TEXT NOT NULL,
  scope_key TEXT NOT NULL,
  note_path TEXT NOT NULL,
  section_anchor TEXT,
  snapshot_id TEXT NOT NULL,
  note_sha256 TEXT NOT NULL CHECK(length(note_sha256)=64),
  manifest_sha256 TEXT NOT NULL CHECK(length(manifest_sha256)=64),
  valid_from TEXT,
  valid_until TEXT,
  validity_known INTEGER NOT NULL CHECK(validity_known IN (0,1)),
  recorded_at TEXT NOT NULL,
  recorded_event TEXT NOT NULL,
  recorded_position INTEGER NOT NULL CHECK(recorded_position>=1),
  library_revision_seq INTEGER NOT NULL CHECK(library_revision_seq>=1),
  operation_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('accepted','disputed','withdrawn','unknown')),
  origin TEXT NOT NULL CHECK(origin IN ('person','observed','source-stated','derived','model-produced','inferred')),
  epistemic_status TEXT NOT NULL,
  lifecycle TEXT NOT NULL CHECK(lifecycle IN ('working','reusable','archived','withdrawn')),
  dependency_coverage TEXT NOT NULL CHECK(dependency_coverage IN ('complete_declared','partial','unknown')),
  PRIMARY KEY(library_id,revision_id),
  UNIQUE(library_id,operation_id,claim_id),
  UNIQUE(library_id,library_revision_seq,claim_id),
  CHECK(valid_from IS NULL OR valid_until IS NULL OR valid_from<valid_until)
);
CREATE INDEX claim_revision_lookup ON claim_revision(library_id,scope_key,claim_id,library_revision_seq);
CREATE TABLE claim_supersedes (
  library_id TEXT NOT NULL, newer_revision TEXT NOT NULL, older_revision TEXT NOT NULL,
  PRIMARY KEY(library_id,newer_revision,older_revision),
  CHECK(newer_revision<>older_revision),
  FOREIGN KEY(library_id,newer_revision) REFERENCES claim_revision(library_id,revision_id)
);
CREATE TABLE claim_support_set (
  library_id TEXT NOT NULL, conclusion_revision TEXT NOT NULL, support_set TEXT NOT NULL,
  coverage TEXT NOT NULL CHECK(coverage IN ('complete_declared','partial','unknown')),
  PRIMARY KEY(library_id,conclusion_revision,support_set),
  FOREIGN KEY(library_id,conclusion_revision) REFERENCES claim_revision(library_id,revision_id)
);
CREATE TABLE claim_support (
  library_id TEXT NOT NULL, conclusion_revision TEXT NOT NULL, support_set TEXT NOT NULL,
  premise_id TEXT NOT NULL, premise_revision TEXT NOT NULL,
  evidence_id TEXT NOT NULL, evidence_sha256 TEXT NOT NULL CHECK(length(evidence_sha256)=64),
  locator_json TEXT NOT NULL, locator_sha256 TEXT NOT NULL CHECK(length(locator_sha256)=64),
  relation TEXT NOT NULL CHECK(relation IN ('supports','requires')),
  PRIMARY KEY(library_id,conclusion_revision,support_set,premise_id,premise_revision,evidence_id,locator_sha256),
  FOREIGN KEY(library_id,conclusion_revision,support_set)
    REFERENCES claim_support_set(library_id,conclusion_revision,support_set)
);
CREATE INDEX claim_support_reverse ON claim_support(library_id,premise_id,premise_revision);
CREATE TABLE claim_conflict (
  library_id TEXT NOT NULL, revision_id TEXT NOT NULL, other_revision TEXT NOT NULL,
  basis_manifest TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('proposed','unresolved','resolved')),
  PRIMARY KEY(library_id,revision_id,other_revision),
  FOREIGN KEY(library_id,revision_id) REFERENCES claim_revision(library_id,revision_id)
);
CREATE TABLE knowledge_episode (
  library_id TEXT NOT NULL, episode_id TEXT NOT NULL, scope_key TEXT NOT NULL,
  session_id TEXT NOT NULL, first_position INTEGER NOT NULL, last_position INTEGER NOT NULL,
  boundary_hash TEXT NOT NULL, source_revision TEXT NOT NULL, kind TEXT NOT NULL,
  lifecycle TEXT NOT NULL CHECK(lifecycle IN ('working','reusable','archived','withdrawn')),
  summary_ref TEXT, PRIMARY KEY(library_id,episode_id),
  CHECK(first_position>=1 AND last_position>=first_position)
);
CREATE INDEX knowledge_episode_scope ON knowledge_episode(library_id,scope_key,kind,lifecycle);
```

A missing superseded revision is retained as an unresolved reference, which is why `older_revision` has no foreign key. Do not infer permission or validity from a successful SQL join. Scope keys are canonical versioned JSON encodings of library/project/session/goal/lens dimensions, not fuzzy text. All retrieval lanes authorize before exposing rows/counts/derived summaries. `knowledge_episode` is an approved-scope event-range lookup; it neither copies full transcripts into privileged prompts nor constitutes a new authority. Model summaries remain optional derived references.

Migration acceptance: empty and populated legacy indexes upgrade; invalid manifests are quarantined/skipped with explicit diagnostics; SQLite deletion/rebuild from Markdown/evidence/committed manifests/events reproduces identical eligible answers; orphan/missing references yield unknown; migration failure leaves original notes unchanged; rollback rebuilds the previous projection or declares unsupported reader rather than corrupting truth. All SQL runs in short IndexService transactions, never across network/encoder work.

### 5.4 Temporal and support semantics

Query modes are current, historical `(valid_at, known_at)`, compare and hypothetical. `known_at` may be a Core recorded-time cutoff or an exact library revision sequence. Select only committed observations known by that cutoff; evaluate half-open `[valid_from,valid_until)` when known. Unknown applicability time remains unknown. Supersession is scoped and interval-aware: a correction covering October does not globally hide an otherwise applicable September assertion. Newer timestamps alone do not settle disagreement between independent sources. Same known-time ordering must be deterministic across Sessions using the persisted library sequence, not comparison of unrelated Session positions.

Within a complete nonempty support set premises are AND; alternative complete sets are OR. Each premise must resolve to the required version, authorized scope and declared verification/applicability. Multiple summaries of one source remain one underlying support origin. Invalidate/re-evaluate reverse dependents to a bounded fixed point. A surviving independently sufficient set preserves supported eligibility. A cycle with no grounded external support contributes no support; partial/unknown coverage, cap overflow or unavailable evidence is unknown. Maintain conservative Session epoch invalidation for closure until the explicitly gated HARNESS-09 comparison proves a scoped optimization safe and worthwhile.

Conflicts are staged with reasons; person approval or the existing authorized workflow adopts revisions. Do not claim complete AGM postulates or a natural-language contradiction oracle. Goal/lens changes alter scoped applicability and query perspective, never hard permissions or neutral source facts. Preserve `{goal_epoch,content_model_hash,profile_digest,selected_lenses:[id,digest]}` in existing Session/run evidence. Hypothetical branches do not adopt goals.

A direct refutation or unresolved conflict is a separate epistemic state: surviving positive support does not erase it. The support evaluator reports support and conflict independently and cannot silently promote a disputed conclusion to verified closure.

Acceptance N-15/N-16: retroactive correction/current-vs-historical fixtures; partial interval supersession; unknown times; duplicate operation replay; independent vs conjunctive support; ungrounded cycles; incomplete dependencies; bounded overflow; scope isolation; manual note edits; withdrawn records surviving restart/rebuild; unchanged closure strength. Lessons retain episode/assumptions/outcome/failure/counterexample/check references and are qualified on unseen variants. Agent probe pass cannot satisfy a person's own-words understanding record or an execution predicate.

## 6. Backend payload bridges for honest UI

**U-B1 — durable stall/block reason (MF-010).** Add `reason` and `source` to `audit_projection._EVENT_KEYS`; fold latest blocked/stall disposition per requirement from existing durable events into `session_status`. Proposed additive `audit.blocked_reasons[rid] = {reason,source,event_ref,requirement_revision,epoch}`; validate actual event fields, preserve missing/legacy as unknown. UI correlates selected session/revision and shows real reason after restart. Counters are actual projected counters, never a hardcoded eight. Acceptance: stall, restart, reopen and explicit revision clear/update reason consistently; bounded event projection does not drop current blocked requirement explanation.

**U-B2 — bound reply review (MF-027, NAT-10).** Add `reply_id`, `turn_id`, exact canonical `note_path`, `source_revision`, evidence reference and `coverage:{checked_spans,unit,total_length,complete,truncated}` to review event/result shape. Reuse existing reply IDs if present; otherwise allocate stable IDs when transcript reply is appended. Root-relative paths, not basename guesses, identify citations; ambiguous link remains unchecked. Targeted spans beyond old 5,000-character prefix may be checked under budget; unexamined spans cannot be labeled contradicted. Count and token caps include missing-link challenges. Persist association through existing transcript/Session evidence, not a UI-owned challenge store. Late async results update only the original matching reply/revision; stale ones remain historical or are discarded with explicit status. Advice is not a veto or verification. Acceptance: duplicate filenames, late evidence, rapid new turn, source edits, challenge floods, resume and unknown legacy events.

**U-B3 — composed staging preview (MF-027).** Extend `staging_show` with `preview:{kind,current_markdown,composed_markdown,sections,source_revision,staged_revision,dependency_digest,preview_digest}` generated by the same server composition/preparation logic used for source promotion, with **no writes**. Obtain current bytes/tokens from one reviewed snapshot. Keep existing opaque review/revision-CAS tokens authoritative; preview_digest is not authorization. Any edited proposal field or changed source/dependency invalidates local preview and requires a refreshed preview/token check. Acceptance refuses stale tokens exactly as today. Before/after UI displays these composed bytes, not a browser approximation. If composition cannot be determined, return typed conflict/needs-input with no actionable accept, rather than a permanent missing-payload banner. Taxonomy membership review stays semantic unless its exact multi-file prepared writes are also exposed under a separately bounded extension.

Bridge code anchors: [audit_projection.py:36](</D:/Librarian_V2/src/resource_librarian/audit_projection.py:36>); [session.py:1143](</D:/Librarian_V2/src/resource_librarian/session.py:1143>); [reply_review.py:38](</D:/Librarian_V2/src/resource_librarian/reply_review.py:38>); [staging.py:1](</D:/Librarian_V2/src/resource_librarian/tools/staging.py:1>).

## 7. UI contracts: D1..D6 reconciled

### 7.1 Projection, actions and oversight

D1 stays a view over existing authenticated Api/Core operations plus U-B1..3. Transient pending flags prevent duplicate clicks; they do not create authoritative workflow state. Health uses `Promise.allSettled`, individual unavailable results, bounded nonoverlapping refresh while visible, disposal cancellation and manual refresh. SSE connectivity is separate from lease/writer/index/watcher/shutdown health. Index counts are snapshots, never invented percentages or ETA. Accepted notes and derived embedding failure remain separately visible. General embedding-job/quarantine-history APIs are not created by implication; immediate NAT receipts are rendered when available. Offline G5 ledger is not live runtime task spend.

D2 requires truthful action transitions: draft/attachments retained through admission; success clears only submitted snapshot; ambiguous transport causes inspection, not automatic resend. Busy Enter preserves next draft; explicit Stop shows pending until canonical stop. Failed mode/effort/model/service/Forget mutation restores last confirmed state and visible error. “Mark reviewed; retry manually” only records its checkpoint choice. Approved execution checkpoint still requires a separate person start with matching ID. Library force-switch describes leaving work running with possible failure/wait, not guaranteed completion. Remove-reference never deletes uploaded Inbox bytes.

D3 renders legacy/invalid banner before empty inspector return, uses actual nonempty legacy/invalid values, blocks history mutations and offers a new audited session. File edits and stale requirements are listed separately until real dependency evidence supports a causal link. Requirement text edits preserve full predicates/verifier parameter objects and closure. Existing set_requirement has no revision-CAS parameter: reread detects known changes but is not atomic CAS; do not claim otherwise. U-B1 supplies resumed stop reasons. Refusal details, predicate detail and skeleton are progressive disclosures, retaining focus/open state by stable identity. Skeleton is proposed, not admitted; fits=false cannot lead to admission.

D4 uses server-composed staging preview, bound advisory reply review and visible Docker preflight. Keep accepted/captured/full-depth/source-stated/quote-located/arithmetic/replicated/person-accepted meanings separate. Claim Run never falls back to host execution. Workbench host mode explicitly says network isolation is not enforced and requires current person/checkpoint confirmations. Failed teardown or incomplete export cannot show safely quarantined/replicated success.

| Requirement / aliases | Acceptance contract | Owner |
|---|---|---|
| U-01 / UI-01 | 409, network loss, duplicate Enter, later edits and attached references survive correctly; explicit cancel distinct. | MF-005 |
| U-02 / UI-02 | Every rejected mutation visibly rolls back confirmed state; checkpoint action makes zero effect replay; normal mount retry never takes over. | MF-006 |
| U-07 / UI-07 | Empty legacy and invalid histories visibly read-only; new session separate; stale evidence not green. | MF-009 |
| U-08 / UI-08 | Restart preserves reason/source; revision request retains predicate/verifier objects; skeleton/refusal detail available without flooding chat. | MF-010 |
| U-09 / UI-09 | Connected stream with failed writer still warns in all tabs; dirty paths visible; stale health labeled last reported; no polling after dispose. | MF-026 |
| U-10 / UI-10 | Bound late reviews never attach to latest reply by arrival; exact source spans open; composed preview matches preparation; stale CAS refuses; unavailable Docker sends no execution request. | MF-027 |

### 7.2 D5: DOM/CSS containment and root-width layout

Canonical DOM skeleton:

```html
<div class="librarian-root" data-lib-instance="unique">
  <div class="lib-app">
    <header class="lib-header"><!-- Settings and Choose models remain reachable --></header>
    <section class="lib-operations" aria-label="Operations"></section>
    <div class="lib-body"><main class="lib-main"></main><aside class="lib-pane"></aside></div>
  </div>
  <dialog class="lib-dialog lib-settings" aria-labelledby="unique-settings-title"></dialog>
</div>
```

```css
.librarian-root {
  container-type: inline-size;
  container-name: librarian;
  min-inline-size: 0;
}
.librarian-root .lib-app { min-inline-size: 0; }
.librarian-root dialog.lib-dialog {
  box-sizing: border-box;
  max-inline-size: min(1120px, var(--lib-dialog-max-width));
  max-block-size: min(820px, var(--lib-dialog-max-height));
}
.librarian-root dialog.lib-dialog::backdrop { background: rgb(0 0 0 / 25%); }
.librarian-root dialog.lib-dialog .lib-page { min-inline-size: 0; }
@container librarian (max-width: 999px) {
  .librarian-root .lib-body { display: block; }
}
@container librarian (max-width: 839px) {
  .librarian-root .lib-settings-rail { display: none; }
  .librarian-root .lib-settings-category { display: block; }
}
@container librarian (max-width: 599px) {
  .librarian-root .lib-search-controls { grid-template-columns: minmax(0, 1fr); }
}
```

CSS queries descendants of the named root, not the container itself. Queries are the primary responsive mechanism; ResizeObserver measures available root width/height and clamps persisted split widths, top-layer dialog dimensions/position and popovers. Top-layer dialog geometry must be tested in both hosts because viewport-centred native placement is not root containment: compute root bounds on open/resize, set owned coordinates and available max dimensions, and keep the dialog's DOM ancestry rooted. No body-portal framework. Use viewport intersection to cap root geometry, preserving 12px each side (24px total) where space permits. Dispose observer/listeners/timers and reject delayed results from previous mount/library/session generations.

Wide roots >=1000px use main >=360px and pane >=300px if those minima fit. Compact roots 600–999px use explicit document overlay with return action. Narrow roots stack queue/detail/evidence, preserve draft and selected note, and offer Back to items/chat. Separate saved desktop split preference from transient narrow overlay state. Settings uses 1120×820 maximum rather than the superseded generic 680px cap; ordinary small dialogs may stay narrower. Sidebar becomes labelled selector/drawer below ~840px. Breakpoints are proposed design constants to validate, not research-derived universal thresholds.

Every outgoing dialog selector, including comma branches and backdrop/descendants, starts `.librarian-root dialog.lib-dialog`. Namespace high-collision generic owned tokens (`row`, `row2`, `item`, `list`, `title`, `body`, `header`, `badge`, `tabs`, `page`, `slot`, `primary`, `ghost`, `opt`, `active`, `error`, etc.) in every emitter, CSS, event selector and test. Preserve host-owned integration classes only at adapter boundaries. Local custom properties use `--lib-*`. No global dialog/button/input/select/textarea/*/:root reset. Use surgical owned control baselines (height:auto, min-height:0, wrapping, line-height, margin, box-sizing); no broad all:initial. Retain the proven model-card/popover/grid fix. Namespacing does not promise immunity to arbitrary hostile !important rules targeting new names.

Acceptance U-03/U-04: inventory all 309 CSS rule headers and 113 main/panels declarations from source appendices plus other emitters; foreign dialog computed styles unchanged; hostile old generic selectors do not collapse owned controls; 320/420/760/1100 root widths within 1440 window and short-height leaf; 420px Search input >=280px; saved oversize split clamped; dialog/popover stays within visible root; generated assets match source builds.

### 7.3 D6: focus, touch and navigation

U-05: focus first usable popover control after async content arrives; nonmodal Tab may leave and closes predictably; native dialog owns modal focus trap. Escape closes innermost owned surface and consumes only handled events originating there; outside leaves keep their keys. Restore focus only when appropriate. IDs/radio groups are mount-unique; disposal removes all listeners. Real Obsidian capture hotkeys require real-host evidence beyond synthetic bubble tests.

U-06: tabs use roving tabindex, Arrow/Home/End and panel relations; splitter supports bounded keyboard adjustments and aria min/max/current; touch long-press cancels on movement/touchcancel and suppresses following click; visible actions supplement hover. Reduced-motion disables action fades. Acceptance includes two mounts, dispose/remount, async focus, keyboard-only complete journeys, touch cancellation and screen-reader-oriented labels. No formal accessibility compliance claim is inferred.

U-11: role-first selection for Lead, Notes and Small tasks; preserve existing ordered-tier/backend binding semantics, qualification and explicit override. Clearing a middle slot cannot silently shift later roles; if current API only supports a prefix, disclose its consequence or use honest clear-all. Service clear remains a service mutation. State/readiness/tested/qualified are distinct.

## 8. Settings, staging and search workspace

### 8.1 Left-sidebar Settings contract (U-12A)

Persistent header controls **Settings** and **Choose models** are available in Chat, Staging and Search. Settings is a native root-contained dialog, max 1120×820, 224px stable left rail, flexible content with 28–32px padding and approximately 760px readable form width. One main content scroller; header/Close/navigation available while scrolling. Long rail may scroll when necessary, but cards do not become independent scroll traps. Narrow root uses labelled category selector/drawer and clear Close/Back.

| Group | Page | Presentation | Existing contract |
|---|---|---|---|
| Environment | Providers & keys | Provider/host/key summary; selected-provider detail; Edit connection advanced URL/timeouts/concurrency; Save connection separate from Save key; last connection test separate from qualification. | /api/keys, /api/hosts, /api/usage |
| Environment | Tools & integrations | Installed-for-user and enabled-for-library states; server summary then per-tool Allow/Ask/Deny; filter; advanced installation actions explicitly scoped. No new Allow all. | Existing /api/mcp family; /api/tool-setting |
| Current library | Models & services | Named chat roles; separate OCR/read-aloud/STT/embedding cards; model catalogue/qualification details secondary; embedding coverage distinct from retrieval quality. | /api/state, /api/tiers, /api/services |
| Current library | Chat behaviour | Context for chat replies; Short/Long/Custom with conditional custom input; Answer/Coach and learn-session override explanation. | /api/context |
| Current library | Review & promotion | Publish authority distinct from advisory checks; direct reviewer-role link; distribution posture. | /api/library |
| Current library | Project access | Master access, folder read/edit state, explicit write approvals; explain metadata creation before adding folder. | Existing /api/projects operations |
| Current library | Methods & lenses | Domain initialization profile, available packs, inspected/accepted methods; pack acceptance distinct from session lens adoption. | library_profile, lens_packs, lens_pack_accept |
| Current library | Topics & organisation | Topics/unfiled/proposals/refile; links back to staging; separate maintenance commands from preferences. | topics_list, topic_propose, staging_decide, views_refresh |
| Advanced | Agent profiles | Permission ceilings, tool bundles, route restrictions, explicit profile editing/history. | /api/profiles, /api/agent-profile and existing history |
| Advanced | Health & diagnostics | Actionable warning summary, installation capabilities, integrity and route/qualification detail; safe support metadata and key-migration actions. | /api/library doctor payload; /api/meta |

Control-level scope labels govern, not category headings alone. Host/key definitions are computer/account scoped; Obsidian-managed credentials lead to SecretStorage. Services, context, review policy, roots, accepted packs and profile definitions are library scoped. **Chat tiers, lead overrides and effort also update shared defaults used by libraries without their own choices.** Explain this next to affected controls; do not claim every existing library changes immediately or infer inheritance from equal values. Session lens adoption remains thread scoped.

Forms retain explicit Save/Cancel; immediate toggles show Saving/Saved/error and revert on failure. No global Save all. Preserve category, scroll and unsaved edits; closing offers Save/Discard/Stay for applicable forms; switching libraries must never submit old-library data into the new one. Navigation warns before discarding edits, not silently saves them. Commands such as Test, Measure, Propose and Rewrite have separate pending/result feedback. No paid probe on page load. Actionable warnings stay visible and deep-link to the relevant category; technical records stay expandable. Retain warm neutral palette, white edit fields, stronger selected navigation and readable evidence; numerical typography/colour effects require actual validation.

Acceptance: all ten categories reachable by keyboard at desktop/420px/short root; provider setup does not require opening Agent profiles; changing Notes preserves Lead; SecretStorage ownership preserved; shared-default side effect visible; failed Save stays dirty with error; close/reopen and cross-workflow return retains state; stale library callback discarded.

### 8.2 Right pane and Staging (U-12B)

Visible view switching **Note / Browse / Plan / This week** is separate from current-note **⋮** actions and **🔊 Read aloud** with explicit playback state. Narrow pane may use labelled View selector. Keep Desk/pins and recent notes reachable without confusing them with settings. Empty Plan does not consume half the review surface; explicit user-opened content remains recoverable after resize.

Staging hierarchy is queue → selected state/next action → form and evidence → decision. Compact queue has obvious selection; scoped counts explain current filter versus library totals. Evidence is a readable proportional-text surface, with monospace only for code/raw extraction. Wide layout gives draft and evidence useful width; narrow layout stacks with Back to items and retained edits. Selecting evidence must not silently overwrite an unrelated open document.

Distinguish **Approve for processing** (read/prepare for later review) from **Keep captured version** (publish limited available capture under existing rules), **Accept reviewed draft**, **Defer** and **Reject**. Hide secondary reason fields until applicable without bypassing required person judgments or coverage checks. Bulk actions in scope are **defer** and **approve-for-processing only**. Snapshot selected IDs, library and current revision tokens; apply bounded existing per-item person decisions; report each success/refusal/stale item, retain unresolved selection, stop on library change/cancel. No bulk publish, fabricated evidence review or implicit payment authority. Retrying uncertain outcome requires current-state inspection.

Acceptance: six-item mixed-state bulk fixture changes only eligible selected items, preserves rejected/stale items and reports partial results; never calls publication acceptance; queued work uses existing budgets/permissions. Settings roundtrip and source preview refresh preserve edits or explicitly request discard. Evidence/claim/revision can be located and explained.

### 8.3 Search (U-12C)

First row: labelled full-width query with usable Submit. Second row: readable scope/intent/date/source filters wrapping or disclosed at narrow widths. Never shrink selected values into fragments. Preserve query/filter selection across results and pane changes. Search depth/score/coverage/advisories are not truth ratings. Empty states offer a few real actions (find source, review captured item, resume session), not decorative pseudo-features.

Acceptance: 390px viewport and 420px leaf within wide window keep readable active filters and query; text zoom and short height retain actions; open result then return keeps query/context. Actual human usefulness and findability measured separately from automated selectors.

### 8.4 Four implementation steps and evaluation criteria

Reconcile the four-step summary with the detailed source's five numbered entries by keeping verification as an exit condition of every step: (1) larger shell/header/left navigation MF-032; (2) redistribute controls and preserve pending forms MF-032; (3) simplify providers/models/tools MF-031/033; (4) connect related workflows, pane/Staging/Search and return state MF-034. MF-035 verifies the integrated result. This does not create a duplicate fifth implementation program.

| QA criterion | Acceptance observation / owner |
|---|---|
| L01 | New user locates Settings/provider setup without hints; MF-032/035. |
| L02 | Readable query/scope at tested widths; MF-008/034. |
| L03 | Resize/open/close pane preserves task and draft; MF-008/025/034. |
| L04 | Replace Notes only and explain result; MF-031. |
| L05 | User distinguishes selected/connection-tested/qualified; MF-031/033. |
| L06 | Locate cited evidence and explain limitation before review; MF-027/034. |
| L07 | Explain captured/queued/processed/accepted and bulk consequences; MF-034. |
| L08 | Recover interrupted/stale review without lost edits or duplicated effect; MF-006/027/035. |
| L09 | Explain write scope before approval and retain Ask/Deny; MF-006/033. |
| L10 | Complete a first meaningful task from empty screen; MF-034/035. |
| L11 | Find ordinary provider/service setup without unrelated advanced controls; MF-032/033. |
| L12 | Record success/errors/human interaction time separately from provider wait and ease/usefulness judgments; MF-035/044. Independent evaluator/user validation remains open. |

Evaluation uses consented minimal task/context observations, not source text, credentials, inferred demographics or silent telemetry. Automated Playwright proves scripted behavior, not novice comprehension or standards conformance. Human study outcomes remain unverified until collected; no paper's demographic or visual effect becomes an app design constant.

## 9. Benchmark and knowledge acceptance

EK-01..08 are refinements of the contracts above: distinct status dimensions; conditioned lessons; localized reversible updates; exploration vs adoption; independent support preservation; version-qualified recipes; separate human/agent/training identities; chronological held-out transfer and harm measurement. Training pipelines are out of scope.

| Scenario | Required assertion | Primary owners |
|---|---|---|
| EKP-01 — Goal pivot preserves historical evidence | A_inapplicable_to_current_goal; old_rationale_resolvable; old_measurement_not_refuted_by_goal_change | MF-036; MF-041 |
| EKP-02 — Selective source revision | C1_needs_recheck; C2_preserved; revision_reason_recorded | MF-037; MF-041 |
| EKP-03 — Alternative complete justifications | C1_remains_supported_by_E3_v1; incomplete_E1_E2_set_not_claimed_current | MF-037; MF-041 |
| EKP-04 — Exploration is not adoption | offline_constraint_preserved_before_adoption; scope_changes_only_at_revision_2; comparison_history_retained | MF-036/037; MF-041 |
| EKP-05 — Conditional failure becomes obsolete | R_eligible_only_with_current_qualification; old_failure_preserved_with_conditions; no_universal_success_claim | MF-023/036; MF-041 |
| EKP-06 — Scoped retrieval fallback | no_P2_content_or_summary_leak; no_unrestricted_fallback; lookup_gap_visible | MF-012/030/038; MF-041 |
| EKP-07 — Replication qualification is versioned | old_receipt_retained; current_qualification_requires_affected_checks; unrelated_checks_not_erased; execution_requires_existing_policy | MF-023; MF-041 |
| EKP-08 — Versioned probes and actor separation | Q1_retired_or_revised; no_human_understanding_from_agent_answer; rubric_hidden; probe_pass_not_execution_closure | MF-037/041; MF-041 |
| EKP-09 — Concurrent stale results and duplicate merge | no_stale_closure; no_duplicate_accepted_effect; cost_reconciled_without_double_counting; useful_old_material_requires_reassessment | MF-021/030; MF-041 |
| EKP-10 — Archive return with unavailable evidence | historical_rationale_retained; missing_required_evidence_disclosed; no_unqualified_current_reuse; archive_not_equated_with_falsehood | MF-012/036; MF-041 |

Implement a deterministic adapter to real Session/evidence/workflow interfaces; seeds are not API calls. Include late caveat, source-instruction laundering, recipe cycle, false paraphrase conflict and forbidden-similar-source variants. Fixed input manifests and hidden rubrics remain inaccessible to the evaluated agent. Freeze source/tool/route versions, clone initial state per arm, use chronological/disjoint project splits, and repeat streams independently.

Start A no optional prior experience, B scoped original episodes, C B plus lifecycle tiers, D B plus qualified versioned lessons. Every arm retains operative requirements/current evidence/access. E recipes and F event-driven probes follow only after A–D are sound. Compare equal total budget and separately matched-quality cost. Report task predicates, partials, transfer, tasks helped/harmed, preserved valid knowledge, stale-use rate, correct/over-invalidation, adaptation lag, historical rationale, applicability errors, replication failures/unavailable, retrieval coverage, latency/human corrections, storage and all roles' tokens/known/unknown cost. Zero accepted outcomes retain total cost with no finite cost-per-success.

Deterministic integrity gates require zero dropped mandatory constraints, stale authoritative merges, duplicate accepted effects and scope leaks in authored fixtures. Behavioral improvement thresholds/pilot size must be preregistered against actual available budget; do not claim statistical benefit from ten seeds or pool correlated questions as independent samples. Layer 0 completion does not establish Layer 1–3 learning. This pass specifies the suite; execution belongs MF-041.

## 10. Verification ownership and scope limits

Every requirement above has a done-only-when check and one MF owner; document 03 supplies exact existing test paths plus explicitly planned new targets. No new target is represented as already passing. Before each implementation merge, use repo-venv source identity, focused tests and the required full regression; UI slices also check/build both distributions and run Playwright. Real Windows/Obsidian/Docker/provider evidence remains distinct. Optional features may be rejected after measurement without blocking release when explicitly excluded from shipped scope. No universal correctness, exact-once external execution, scientific replication or human-learning claim follows from finite fixtures.

