# Regression manifest

**Status:** Living verification manifest. The [unified implementation plan](unified-implementation-plan.md)
owns task ordering and delivery status; this file makes the evidence command
and expected boundary explicit.

## Rules

- Run Python tests through the repository virtual environment:
  `& .\.venv\Scripts\python.exe -m pytest -q ...`.
- `tests/conftest.py` verifies that imports come from this checkout. A bare
  system `pytest` result is not release evidence.
- A merged code packet needs its focused command and a full-suite run. The
  full command is `& .\.venv\Scripts\python.exe -m pytest -q`.
- A `Windows host` row requires the owner's real Windows launch path; a
  `provider budget` row is opt-in and records its cost separately.
- Future rows are planned verification contracts, not assertions that those
  checks currently pass.
- A `tmp/...` path is an untracked local log from the originating worktree,
  not a committed or release artifact. It supports the summarized local run
  only. For portable evidence, retain the command, source revision,
  environment identity, and result in a tracked record, and archive raw output
  outside `tmp/` when a reviewer or release decision needs it.

| Task | Delivery status | Focused command / fixture class | Expected boundary | Extra requirement | Evidence |
| --- | --- | --- | --- | --- | --- |
| BASE-01 | implemented | `git status --short`; manifest review | Existing work is attributed without reset or loss. | Maintainer approval before committing pre-existing work. | `ad02715`, `f213fc6`, `1fd49c3` |
| BASE-02 | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_source_identity.py` | Repo venv is accepted; stale sibling checkout is refused. | None. | `a467710` |
| BASE-03/04/05 | implemented | Documentation link/status review; `& .\.venv\Scripts\python.exe -m pytest -q tests/test_source_identity.py` | Status vocabulary, terminology, and test provenance remain explicit. | None. | This document and terminology.md. |
| CORE-01 | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_process_identity.py tests/test_host_lifecycle.py` | A live Core is identified by exact process identity, not PID alone. | Windows host. | `f014b2f`, `8a34cc7` |
| CORE-02A/B | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_shutdown.py tests/test_host_lifecycle.py tests/test_person_waits.py` | Stop refuses new work, parks interrupted sessions, and exits using the real child PID. | Windows host. | `1a8adf6`, `3015bc2`, `8a34cc7` |
| CORE-03 | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_session_events.py` | Session mutations use Core writer ordering or a safe offline path. | Multi-process fixture when changed. | `4873894`, `8a34cc7` |
| CORE-04A | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_mcp.py` | MCP never opens vault state; it proxies as a capped MCP caller. | Coordinated Core fixture. | `d177d55`, `8a34cc7` |
| CORE-05A/B | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_revisions.py tests/test_authoring.py tests/test_mcp.py` | Replace-existing writes require a bound revision and stale writes conflict. | Add a fixture before expanding coverage to a new write kind. | `119ded6` |
| CORE-05 staging / INDEX-03 staging | partial | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_staging_safety.py tests/test_deep_read.py tests/test_dik.py tests/test_staging.py tests/test_revisions.py tests/test_v2_remediation.py tests/test_sqlite_ownership.py tests/test_operation_recovery.py`; UI build/browser smoke | Source revision CAS/leases, staged-record review/dispatch guards, concept/import creation guards, sensitivity gate, Core SQL vs writer file access. | New-source/topic multi-target promotion and lens-store ownership remain open. | `90b1945`; expanded combined group: 122 passed; browser smoke passed; staging direct-index debt 17 → 14. Full suite: 1,060 passed, 2 skipped, 1 deselected. |
| INDEX-03/04 upkeep | partial | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_core_upkeep.py tests/test_upkeep.py tests/test_dik.py tests/test_model_catalog.py tests/test_core_index_service.py tests/test_sqlite_ownership.py` | Query results leave worker as ordinary data; network/provenance/D/I/K processing runs outside it; derived mutations use writer. | Remaining promotion/taxonomy/batch and offline compatibility paths need migration/enforcement. | `90b1945`; expanded combined group: 122 passed; direct-index debt 14 → 8. Full suite: 1,060 passed, 2 skipped, 1 deselected. |
| CORE-05 / INDEX-03/04 taxonomy | partial | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_core_taxonomy.py tests/test_taxonomy.py tests/test_staging.py tests/test_staging_safety.py tests/test_revisions.py tests/test_registry.py tests/test_core_index_service.py tests/test_sqlite_ownership.py`; UI build/browser smoke | Pre-approval targets/bytes remain invocation-local; SQL/rendering stays on Core; each file write checks revisions/leases; caught partial topic acceptance survives review/restart; Settings does not misreport refusals. | Mixed/batch topic and new-source promotion, six direct construction sites and Windows stress remain. | `fc58af2`; expanded focused: 145 passed; browser build/smoke passed; full: 1,084 passed, 2 skipped, 1 deselected. |
| CORE-06 | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_operation_recovery.py` | Start-only operation produces one idempotent recovery checkpoint before mutation admission. | Core restart fixture. | `c264b9a` |
| CORE-07 | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_event_resync.py tests/test_app.py tests/test_shutdown.py tests/test_host_lifecycle.py` | SSE gaps/restarts emit one epoch-aware resync instruction without replaying actions. | Restart fixture. | `5708c39` |
| INDEX-01/02 | partial | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_sqlite_ownership.py tests/test_core_index_service.py tests/test_desk.py tests/test_taxonomy.py` | Static debt only shrinks; migrated calls remain on IndexService worker. | Real Core context per migrated family. | `557126c`, `8ccce9b` |
| INDEX-03 | partial | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_core_index_service.py tests/test_sqlite_ownership.py tests/test_authoring.py tests/test_sessions.py tests/test_review_gate.py tests/test_offering_view.py tests/test_learn.py tests/test_start_pursuit.py tests/test_weekly_review.py tests/test_pursuits.py` | Interleaved work receives copied data only from Core-owned SQLite; Markdown/session mutations remain on writer; Clerk/Scribe IO releases index worker; changed schemas refresh before validation. | Serving-path debt 33 → 17; further promotion batches and Windows stress remain. | `2e95158`, `86941d3`; final combined suite 1,039 passed, 2 skipped, 1 deselected. |
| Macro writer-wait follow-up | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_macro_permissions.py tests/test_person_waits.py tests/test_registry.py`; full browser smoke | Ask-mode waits never own the writer; explicit Deny/Plan still hold; partial work stays durable; external tools cannot opt out of writer serialization. | Automatic macro resume is not claimed. | `5b3be1f`; expanded focused group: 116 passed; final combined suite: 1,039 passed, 2 skipped, 1 deselected; browser smoke passed. |
| INDEX-04 serving gateway/pack boundary | implemented | `tests/test_index_ownership_runtime.py`, `tests/test_sqlite_ownership.py`, coordinated Core fixtures | A missing/closed/foreign service cannot open a direct fallback; graph/extract offline use is explicit; serving debt is zero. | Low-level offline compatibility remains; not an arbitrary-Python sandbox. | `ded98c0`, `d31cda5`; combined focused: 381 passed, 45 new ownership checks; UI build/smoke passed; full: 1,284 passed, 2 skipped, 1 deselected. |
| INDEX-05 | partial | `tests/test_core_concurrency.py`, `tests/test_auxiliary_store_lifecycle.py`, coordinated read/write/WAL/editor/store fixtures | Bounded native Core API stress preserves state, one index owner and closed auxiliary handles; same-path readers do not deny prepared writes. | Sustained/large-vault, rename/delete/snapshot consistency, crash/stop, real adapter and packaged matrix remain. | `f11e98d`; 301 focused passed, 18 new cases; nine extra contention fixtures passed; UI build/smoke passed; full: 1,302 passed, 2 skipped, 1 deselected. |
| Core fingerprint/replacement exclusion | implemented | `tests/test_file_access.py` plus watcher/authoring/staging fixtures | A Core fingerprint closes before same-path atomic replacement; unrelated notes stay writable; external access errors remain visible. | Native Windows baseline; no mutation retry, global/editor lock, or bounded large-file hash claim. | `e40a4a6`; 7 new checks; combined focused: 381 passed; full: 1,284 passed, 2 skipped, 1 deselected. |
| CORE-05 / INDEX-03/04 mixed acceptance | partial | `tests/test_core_mixed_acceptance.py` plus source/staging/taxonomy/revisions/ownership/recovery fixtures; UI build/smoke | Approved footprint bounds ordered replanning; earlier rows/prose survive; interrupted primaries cannot be modified; no direct staging engine. | Runtime enforcement, Windows/desk/lens stress, quarantine and rehash costs remain open. | `87e2460`; 185 focused passed, 27 new checks; UI build/smoke passed; full: 1,215 passed, 2 skipped, 1 deselected; static debt 3 → 2. |
| Watcher read-failure recovery | implemented | `tests/test_watcher_recovery.py` plus coordinated staging/index/lease/shutdown/Host fixtures, with thread warnings treated as errors | Failed observations retry without unlocking unreadable notes or stopping the watcher; diagnostics are bounded and non-secret. | Adopted-root scoping and full Windows multi-client stress remain separate. | `89e609d`; 210 focused passed, 17 new checks; UI build/smoke passed; full: 1,232 passed, 2 skipped, 1 deselected. |
| CORE-05 / INDEX-03/04 source-only batches | partial | `tests/test_core_source_batch.py` plus single-source/staging/catalogue/taxonomy/ingestion/revision/index fixtures; UI build/browser smoke | Copy destinations and all dependencies precede approval; own-write hashes preserve shared views; partial results/provenance survive faults without replay. | Mixed-kind/multi-topic staging, rehash IO costs, cancellation and full ownership enforcement/stress remain open. | `c48e6a0`; 204 focused passed; 22 new checks; browser build/smoke passed; full: 1,188 passed, 2 skipped, 1 deselected. |
| CORE-05 / INDEX-03/04 single-source acceptance | partial | `tests/test_core_source_promotion.py` plus staging, catalogue/taxonomy, revisions, ingestion/intake, upkeep and index-ownership fixtures; UI build/browser smoke | Complete single-source plan precedes approval; copies preserve inputs; Core owns SQL; partial outcomes survive explicit review/restart without overwriting changed work. | Multi-item promotion, fresh-item quarantine relocation, provider cancellation, runtime enforcement and Windows stress remain open. | `870f2e5`; 182 focused passed; browser build/smoke passed; full: 1,166 passed, 2 skipped, 1 deselected. |
| INDEX-03/04 catalogue promotion | partial | `tests/test_core_catalog.py` plus model catalogue/staging/embed/ownership/recovery fixtures; UI build/browser smoke | Catalogue SQL stays on Core; per-entry effects are declared/guarded; partial notes remain visible; vector IO releases SQLite and stale/invalid batches refuse or roll back. | Three construction sites, staging attachments/new-source promotion, full cancellation and Windows stress remain. | `508959a`; 113 focused passed; UI build/smoke passed; full: 1,125 passed, 2 skipped, 1 deselected. |
| INDEX-03/04 approved batch / lifecycle | partial | `tests/test_core_batch.py` plus ingestion/DIK/Clerk, writer/recovery/shutdown and registry/macro fixtures; UI build/browser smoke | Batch SQL stays on Core; batch-owned commits serialize; metadata and decisions survive; cancelled stages resume once; closed-writer late results refuse; failed work remains visible. | Four construction sites, full source promotion, nested provider cancellation and Windows stress remain open. | `ce88b04`; 113 focused tests passed; browser build/smoke passed; full: 1,103 passed, 2 skipped, 1 deselected. |
| ROUTE-01/02 | implemented / partial | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_app.py` | Lead patch preserves other positions; display preserves `unknown`. | API alias coverage belongs to ROUTE-03. | `77315cc`, `7a48f0c` |
| ROUTE-03 (chat) / ROUTE-05 (chat) | partial | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_role_route_store.py tests/test_role_route_bindings.py tests/test_qualification_jobs.py tests/test_app.py tests/test_agent_runtime_profiles.py tests/test_clerk_routes.py` | Chat/background/helper use canonical bindings; task role owns qualification; invalid endpoints refuse without fallback. | Restart projection repair, offline lease, explicit helper preservation, and profile-slot fixtures. | `b6ef33b`, `14837a2`; full suite 1,016 passed, 2 skipped, 1 deselected on 2026-10-25. |
| BASE-02 (browser smoke) | implemented | `npm.cmd run build`; `npm.cmd run smoke` in `ui/` | Browser smoke uses this checkout, scripted providers, isolated credentials, and only its own process tree. | Installed Chromium-family browser. | `c6d189e`; complete smoke pass. |
| ROUTE-03 (services) / ROUTE-04/05 (routing) | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_service_routes.py tests/test_app.py tests/test_stt.py tests/test_role_route_bindings.py`; service-adapter group; `npm.cmd run build`; `npm.cmd run smoke` in `ui/` | Canonical assignments execute exact hosts; Clerk evidence never qualifies Lead; custom OCR/embedding routes and native speech remain explicit; stale/late service calls refuse. | Full suite during development: 1,028 passed, 2 skipped, 1 deselected; expanded focused group 84 passed, final service group 38 passed; browser smoke passed. Transport extraction/cancellation remains ADAPT-06. | 2026-10-25 service/readiness continuation; final combined full run follows next ownership batch. |
| ADAPT-01 | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_provider_failures.py tests/test_loop.py tests/test_model_invocation.py` | Metadata/continuation preserves legacy provider ABI, redacts secrets, and replays reasoning only for tool continuation. | Live L1 only when opted in. | `48b61a8` |
| ADAPT-02–05 | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_provider_failures.py tests/test_loop.py tests/test_model_invocation.py tests/test_openai_chat_adapter.py tests/test_anthropic_messages_adapter.py` | Identity, redacted evidence, continuation, and trusted rendering preserve the legacy provider ABI. | Live L1 only when opted in. | `344a49c`, `d2f7f81`, `b242d8b` |
| ADAPT-06/07 | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_approved_transports.py tests/test_host_local_yield.py tests/test_qualification_jobs.py` | Shared host policy and two-turn tool continuation are enforced. | Provider budget for the recorded L1 route probes. | `999fe1a`, `e8b5d15`; [probe report](../reports/2026-10-26-adapt07-continuation-probe.md). |
| ADAPT-08 | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_model_dialect.py` | Declarative dialect packs fail closed and cannot carry executable fields. | Exact reviewed route evidence before behavior changes. | `b70af09`; 49 focused passed, full suite 1,376 passed, 2 skipped, 1 deselected. |
| ADAPT-09 | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_prompt_layout.py tests/test_openai_chat_adapter.py tests/test_anthropic_messages_adapter.py tests/test_loop.py tests/test_arguments.py tests/test_assumptions.py tests/test_d_items.py tests/test_lens_use.py` | Vault-derived text remains outside system instructions; delimiters cannot be escaped; prior history and the stable prefix retain their order. | Provider-specific cache billing only when opted in; no route-specific layout is enabled. | `c06d1b6`; [measurement](../reports/2026-10-26-adapt09-prompt-layout.md); 93 focused passed, full suite 1,383 passed, 2 skipped, 1 deselected. |
| ADAPT-10–11 | planned | Expectation authoring, prompt-boundary, and tool-bundle/handle fixtures | Rejected records change no routing; context and oversized results remain bounded. | Provider measurement only when opted in. | — |
| DEPLOY-01–05 | planned | Adoption survey/apply/dedupe fixtures | Existing document trees remain byte-preserved and searchable without hidden user docs. | Windows/Obsidian fixture as applicable. | — |
| HARNESS-01–09 | planned | Session replay, verifier, and closure fixtures | Audited work reuses Session, never auto-promotes, and remains evidence bounded. | Tier-B evaluation budget only after its gate. | — |
| ACCEPT-01 | planned | End-to-end research, staging/promotion, V1 import, profile/bundle/macro/checkpoint, client lifecycle, service, Workbench, and ranking fixtures | Each workflow has success, refusal, recovery, and no-mutation-on-failure coverage. | G1 through G4. | — |
| ACCEPT-02 | planned | Fresh Windows repository-artifact acceptance, including lifecycle, dirty documents, two-client coordination, adoption, Docker/fallback, and rollback rehearsal | Results retain OS/Obsidian/Docker versions and a successful rollback rehearsal. | ACCEPT-01, CORE-02, DEPLOY-04. | — |
| ACCEPT-03 | planned | Capability-matrix and V1/V2-parity reconciliation from passing acceptance evidence | Documentation distinguishes delivered behavior, exclusions, and deferred V3 work. | ACCEPT-01. | — |
| RELEASE-01 | planned | Release-queue refresh with source-identity and lifecycle gates | R0 no longer assumes V2 implementation is complete. | BASE-03, ACCEPT-03. | — |
| RELEASE-02–03 | blocked externally | Frozen artifact, UI/adapter, Windows, rollback, and qualification matrix | Stable-release claims have real environment/provider evidence. | RELEASE-01/G5 or RELEASE-02/ACCEPT-02, plus release-owner authority, credentials, and signing material. | — |

Final combined verification on 2026-10-25 used
`& .\.venv\Scripts\python.exe -m pytest -q -o faulthandler_timeout=60`:
**1,039 passed, 2 skipped, 1 deselected in 338.19s**. This includes the final
canonical service, role-readiness, authoring/Session ownership and macro-wait
changes. Output: `tmp/ownership-macros-full-2026-10-25-01.log` (local generated
log, not a release artifact). UI build and expanded `npm.cmd run smoke` passed.
No paid-provider validation or stable-release qualification is implied.

Staging/upkeep continuation `90b1945` was verified with the same full command:
**1,060 passed, 2 skipped, 1 deselected in 349.00s**. Output:
`tmp/staging-upkeep-full-2026-10-25-02.log`. UI build and expanded browser smoke
passed. The exact **122-test** combined focused command was:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -x tests/test_core_upkeep.py tests/test_staging_safety.py tests/test_deep_read.py tests/test_upkeep.py tests/test_dik.py tests/test_model_catalog.py tests/test_sqlite_ownership.py tests/test_core_index_service.py tests/test_revisions.py tests/test_staging.py tests/test_v2_remediation.py tests/test_operation_recovery.py
```

No paid-provider call, L1–L3 requalification, or release-gate closure is implied.

Taxonomy continuation `fc58af2` passed the full repository-venv command with
`-o faulthandler_timeout=60`: **1,084 passed, 2 skipped, 1 deselected in 345.72s**.
Output: `tmp/taxonomy-ownership-full-2026-10-25-01.log`. UI build and the expanded
browser smoke walk passed, including structured refresh refusal and explicit
stale-topic reload. The exact **145-test** focused command was:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -x tests/test_core_taxonomy.py tests/test_taxonomy.py tests/test_staging.py tests/test_staging_safety.py tests/test_revisions.py tests/test_sqlite_ownership.py tests/test_core_index_service.py tests/test_registry.py tests/test_operation_recovery.py tests/test_macro_permissions.py tests/test_mcp.py
```

These remain deterministic/scripted checks, not paid model qualification or
Windows multi-client stress/release acceptance.

Approved-batch continuation on 2026-10-25 passed the **113-test** focused group:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -x tests/test_core_batch.py tests/test_ingest_service.py tests/test_dik.py tests/test_sqlite_ownership.py tests/test_shutdown.py tests/test_revisions.py tests/test_operation_recovery.py tests/test_clerk.py tests/test_registry.py tests/test_macro_permissions.py
```

`npm.cmd run build` and the expanded `npm.cmd run smoke` in `ui/` passed,
including the failed-batch banner and explicit resume control. Full verification
uses the repository-venv command with `-o faulthandler_timeout=60`; output is
retained at `tmp/batch-ownership-full-2026-10-25-01.log` (local generated
output, not a release artifact). Implementation `ce88b04` passed **1,103 tests,
2 skipped, 1 deselected in 343.67s** against the frozen source. No paid provider
call, in-flight cancellation guarantee, or stable-release gate closure is implied.

Catalogue-promotion continuation on 2026-10-25 passed the **113-test** focused group:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -x tests/test_core_catalog.py tests/test_model_catalog.py tests/test_staging.py tests/test_embed.py tests/test_sqlite_ownership.py tests/test_macro_permissions.py tests/test_core_batch.py tests/test_operation_recovery.py tests/test_staging_safety.py tests/test_core_index_service.py
```

UI `npm.cmd run build` and expanded `npm.cmd run smoke` passed, including
catalogue incomplete-note and partial-write failure messages, existing model
selection and staging acceptance. Frozen-source full verification uses the
repository venv with `-o faulthandler_timeout=60`; output is retained locally
at `tmp/catalog-ownership-full-2026-10-25-01.log`. Implementation `508959a`
passed **1,125 tests, 2 skipped, 1 deselected in 373.99s** against frozen source.
These are scripted/local checks, not paid model qualification or Windows
multi-client release acceptance.

Single-source acceptance continuation on 2026-10-25 passed the **182-test**
focused group, including **41 new checks**:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_core_source_promotion.py tests/test_staging.py tests/test_staging_safety.py tests/test_core_catalog.py tests/test_core_taxonomy.py tests/test_revisions.py tests/test_sqlite_ownership.py tests/test_core_index_service.py tests/test_ingest_service.py tests/test_intake.py tests/test_upkeep.py -q -x -o faulthandler_timeout=60
```

UI `npm.cmd run build` and expanded `npm.cmd run smoke` passed, including
interrupted-promotion warnings, completed paths, retained originals and an
explicit finish action, plus the existing picker and ordinary staging flows.
An old Inbox-PDF test now asserts byte-identical retained input and managed
copy rather than expecting input deletion. The first full pass also caught
and prompted restoration of the preview's `promotion.mode` diagnostic. That
development run is retained at `tmp/source-promotion-full-2026-10-25-01.log`
(2 failed, 1,163 passed); it is not final verification evidence.

The full repository-venv run with `-o faulthandler_timeout=60` passed **1,166
tests, 2 skipped, 1 deselected in 391.56s**. Output:
`tmp/source-promotion-full-2026-10-25-02.log` (local generated output).
Python/Core and test source were frozen during this run. A subsequent UI-only
approved-text author-label correction was verified separately by TypeScript
check/build and the expanded browser smoke, including its new assertion. No
Python/Core behavior changed after the full run. Implementation: `870f2e5`.
No paid provider call, model
qualification, Windows multi-client stress or release-gate closure is implied.

Source-only acceptance batches on 2026-10-25 passed the **204-test** focused
group, including **22 new checks**:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_core_source_batch.py tests/test_core_source_promotion.py tests/test_staging.py tests/test_staging_safety.py tests/test_core_catalog.py tests/test_core_taxonomy.py tests/test_revisions.py tests/test_sqlite_ownership.py tests/test_core_index_service.py tests/test_ingest_service.py tests/test_intake.py tests/test_upkeep.py -q -x -o faulthandler_timeout=60
```

UI `npm.cmd run build` and `npm.cmd run smoke` passed. Smoke confirms that
opening partial work never accepts it, only the deliberate finish sends one
acceptance, and the saved library decision is distinguished from an unrecorded
origin-session handoff. Existing model selection and staging walks still pass.

Implementation: `c48e6a0`. Final frozen-source full verification used the
repository venv with `-o faulthandler_timeout=60`: **1,188 passed, 2 skipped,
1 deselected in 439.18s**. Local generated output:
`tmp/source-batch-full-2026-10-25-02.log`. No product or test source changed
during this final run. The earlier `01` development run began before the
cross-kind duplicate-name correction/new regression and is not the final
verification record. No paid model calls, new qualification, throughput
benchmark, Windows multi-client stress or stable-release gate closure is implied.

Mixed-kind/multi-topic acceptance on 2026-10-25 passed **185 focused tests**,
including **27 new checks**:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_core_mixed_acceptance.py tests/test_staging.py tests/test_core_source_promotion.py tests/test_core_source_batch.py tests/test_core_taxonomy.py tests/test_sqlite_ownership.py tests/test_staging_safety.py tests/test_revisions.py tests/test_core_index_service.py tests/test_operation_recovery.py -q -x -o faulthandler_timeout=60
```

UI `npm.cmd run build` and `npm.cmd run smoke` passed against this checkout.
The source/topic ordering and revision/refiling checks passed three repeated
three-case runs (nine executions) after two non-reproduced development acceptance
failures. Their cause was not established. Structured mixed failure messages retain the cause class without
raw exception text. No blanket retry was introduced; a successful repeat is not
evidence that transient Windows IO or the full concurrency release gate is solved.

Implementation: `87e2460`. Frozen-source full command:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -o faulthandler_timeout=60
```

Final result: **1,215 passed, 2 skipped, 1 deselected in 458.38s**, no warnings.
Output: `tmp/mixed-acceptance-full-2026-10-25-02.log`. The earlier development
`01` run began before the final preview compatibility fix and contained a
watcher-thread PermissionError warning. It is not the final mixed verification
snapshot. A separate deterministic watcher regression now exercises that
read-failure path; it does not establish the cause of the two other failures.

Watcher read-failure recovery uses thread-exception warnings as failures:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_watcher_recovery.py tests/test_v2_remediation.py tests/test_core_index_service.py tests/test_core_source_promotion.py tests/test_core_mixed_acceptance.py tests/test_core_source_batch.py tests/test_shutdown.py tests/test_app.py tests/test_host_lifecycle.py tests/test_revisions.py -q -x -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=60
```

New fixtures cover exact-Core/hash-mismatch recovery, unchanged-stat retries,
new/deleted observations, per-note blocking, locked heartbeats, post-commit
read failure, partial directory/stat failures, real polling-thread recovery,
visible programming errors, alias refusals, bounded diagnostics and `/api/meta`.

Focused result: **210 passed in 144.85s**, including **17 new watcher checks**.
UI `npm.cmd run build` and full `npm.cmd run smoke` passed. Frozen-source full
verification command (no product/test source edits during the run):

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=60
```

Output: `tmp/watcher-recovery-full-2026-10-25-01.log` (local generated log).
Implementation: `89e609d`. Final result: **1,232 passed, 2 skipped, 1 deselected
in 422.29s**, no warnings. No product/test source changed during this run.
No paid qualification or broader release-gate closure is claimed by this
read-failure recovery packet.

INDEX-04 gateway/pack continuation and Core file-access exclusion:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_index_ownership_runtime.py tests/test_file_access.py tests/test_sqlite_ownership.py tests/test_core_index_service.py tests/test_core_mixed_acceptance.py tests/test_core_source_batch.py tests/test_core_source_promotion.py tests/test_core_catalog.py tests/test_core_taxonomy.py tests/test_core_batch.py tests/test_core_upkeep.py tests/test_v2_remediation.py tests/test_watcher_recovery.py tests/test_app.py tests/test_sessions.py tests/test_registry.py tests/test_person_waits.py tests/test_mcp.py tests/test_upkeep.py tests/test_cli.py -q -x -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=60
```

**381 passed in 204.42s**, including **45 new ownership checks and 7 new
file-access checks**. The smaller combined native/gateway/watcher group also
passed **86 tests**. Browser `npm.cmd run build` and complete
`npm.cmd run smoke` passed, including session attach and existing picker,
service and interrupted-staging interactions.

The earlier development run stopped at **1 failed, 57 passed** after an
authoring `task_route` atomic replacement returned WinError 5. That test
passed in isolation. A deterministic native test separately reproduces an
open-reader replacement failure, and controlled Core read/write interleaving
now passes. This establishes a mechanism and its local fix, not which handle
caused that particular failure or the two prior mixed-acceptance failures.
A FILE_SHARE_DELETE opener was experimentally insufficient and was removed;
no Win32 shim or broad retry is included. Mechanism/source references and
limits: [index-ownership.md](index-ownership.md).

Implementation: `e40a4a6` (file exclusion), `ded98c0` (ownership). Frozen-source
full command:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=60
```

The first frozen-source run found **1 failed, 1,283 passed, 2 skipped,
1 deselected in 434.56s**. An old token-binding fixture constructed MCP calls
without any Core service; it now correctly hit `CORE_REQUIRED` instead of
receiving a revision. The fixture was moved to a coordinated Core while
retaining its session/caller/forgery/restart assertions. The production gate
was not relaxed. Development evidence: `tmp/index-runtime-full-2026-10-25-01.log`.

Final verification against corrected snapshot `d31cda5`: **1,284 passed,
2 skipped, 1 deselected in 434.41s**, no warnings. Product/test source stayed
frozen throughout the run. Output: `tmp/index-runtime-full-2026-10-25-02.log`.
The corrected revision fixture plus runtime ownership, file-access, static
guard, coordinated index, MCP and App group passed **149 tests in 103.63s**:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_revisions.py tests/test_index_ownership_runtime.py tests/test_file_access.py tests/test_sqlite_ownership.py tests/test_core_index_service.py tests/test_mcp.py tests/test_app.py -q -x -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=60
```

Verification environment: repository `.venv`, CPython **3.11.3 x64**,
Windows build **10.0.26200**, imports from `D:\Librarian_V2\src`. This is not
a fresh Python 3.12/3.13 matrix result or a clean packaged-install test.
No G1/INDEX-05 release stress, extract pinned-plan correctness or paid provider
qualification is implied by this packet.

INDEX-05 native Core-API contention continuation (`f11e98d`):

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_core_concurrency.py tests/test_auxiliary_store_lifecycle.py tests/test_core_index_service.py tests/test_index_ownership_runtime.py tests/test_file_access.py tests/test_watcher_recovery.py tests/test_desk.py tests/test_lens_use.py tests/test_lens_concentration.py tests/test_lens_quality.py tests/test_lens_gold.py tests/test_session_events.py tests/test_revisions.py tests/test_sqlite_ownership.py tests/test_shutdown.py tests/test_person_waits.py tests/test_app.py tests/test_mcp.py tests/test_core_mixed_acceptance.py -q -x -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=60
```

**301 passed in 147.92s**, including **18 new tests**. Native resource-lifetime
reproductions initially gave six failures/three controls passing, then passed
after explicit cleanup. The prepared-writer/getter fixture separately failed
with WinError 5 before the added coordinated reads. Initial test-harness errors
(a helper parameter collision and the lens chain's empty-string convention)
were corrected, not counted as product defects. Final interleavings probe the
actual shared lock instead of guessing scheduling with sleeps.

Three independent invocations of this command each ran the three parameterized
contention fixtures (nine fixture executions in all):

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_core_concurrency.py -k concurrent_loopback_clients -q -s -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=60
```

Local raw metrics: `tmp/core-concurrency-repeat-2026-10-25-01.log`: **531 HTTP
requests, 378 activity iterations, 54 checkpoints**, no unfinished operations,
all handles closed. Per-fixture HTTP p95 **235–281 ms**, maximum individual
request **359 ms**. These are instrumented local micro-fixtures, not a pooled
percentile, live model validation or performance SLA. Methodology and precise
limits: [validation report](../reports/2026-10-25-core-concurrency-validation.md).

UI `npm.cmd run build` and full `npm.cmd run smoke` passed, including the
existing picker, service slots, desk, note pane and staging/recovery UX; bundle
unchanged. Frozen-source full command:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=60
```

Final result against `f11e98d`: **1,302 passed, 2 skipped, 1 deselected in
449.18s**, no warnings. Local log: `tmp/core-concurrency-full-2026-10-25-01.log`.
No product/test source changed during the final run. A later module-docstring
clarification describes schema-lock usage without changing behavior. No paid calls, stable
release qualification or INDEX-05/G1 gate closure is claimed.
