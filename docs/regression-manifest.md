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
| INDEX-05 | partial | `tests/test_core_concurrency.py`, `tests/test_auxiliary_store_lifecycle.py`, `tests/test_index_snapshot_consistency.py`, `tests/test_core_process_interruption.py`, `tests/test_index_large_vault.py`, `tests/test_index_sustained_traffic.py`, coordinated read/write/WAL/editor/store fixtures | Bounded native Core API stress preserves state and ownership; active-handle snapshots catch replacements; crash and authenticated force-stop recover without replay; 5,000-note refresh and 30-round mixed traffic converge exactly with one index owner. | Packaged real adapters, unsupported external handles, large attachments/encoder occupancy and packaged/Python matrix remain. | Through `ae00300`; slow scale group: 2 passed; default focused: 18 passed, 2 deselected; full: 1,439 passed, 2 skipped, 3 deselected; [scale report](../reports/2026-10-27-index05-scale-sustained.md). |
| Extract reviewed-plan pinning | implemented | `tests/test_extract_pinning.py`, extract/upkeep fixtures | Registered-tool materialization requires one reviewed survey tree revision and a deterministic token for the exact recomputed plan before network access. | Direct Python compatibility may omit both explicit pins together but still uses its internally derived pins; network/provider qualification is separate. | `74c6081`; included in 69 dedicated, 310 combined and 1,435 full-suite passes; [report](../reports/2026-10-26-index05-snapshot-continuation.md). |
| Fresh-rejection quarantine safety | implemented | `tests/test_staging.py`, `tests/test_staging_safety.py`, `tests/test_model_expectation_authoring.py` | Rejection WriteIntent/preflight binds a collision-safe quarantine target and complete/partial attachment fingerprints; changed inputs refuse; older records and source attachments are retained. | Hard-crash exactly-once quarantine is not claimed; encoder IO still occupies an enclosing writer call. | `74c6081`; included in 69 dedicated, 310 combined and 1,435 full-suite passes; [report](../reports/2026-10-26-index05-snapshot-continuation.md). |
| Core fingerprint/replacement exclusion | implemented | `tests/test_file_access.py` plus watcher/authoring/staging fixtures | A Core fingerprint closes before same-path atomic replacement; unrelated notes stay writable; external access errors remain visible. | Native Windows baseline; no mutation retry, global/editor lock, or bounded large-file hash claim. | `e40a4a6`; 7 new checks; combined focused: 381 passed; full: 1,284 passed, 2 skipped, 1 deselected. |
| CORE-05 / INDEX-03/04 mixed acceptance | partial | `tests/test_core_mixed_acceptance.py` plus source/staging/taxonomy/revisions/ownership/recovery fixtures; UI build/smoke | Approved footprint bounds ordered replanning; earlier rows/prose survive; interrupted primaries cannot be modified; no direct staging engine. | Runtime enforcement, Windows/desk/lens stress, quarantine and rehash costs remain open. | `87e2460`; 185 focused passed, 27 new checks; UI build/smoke passed; full: 1,215 passed, 2 skipped, 1 deselected; static debt 3 → 2. |
| Watcher read-failure recovery | implemented | `tests/test_watcher_recovery.py` plus coordinated staging/index/lease/shutdown/Host fixtures, with thread warnings treated as errors | Failed observations retry without unlocking unreadable notes or stopping the watcher; diagnostics are bounded and non-secret. | Adopted-root scoping and full Windows multi-client stress remain separate. | `89e609d`; 210 focused passed, 17 new checks; UI build/smoke passed; full: 1,232 passed, 2 skipped, 1 deselected. |
| CORE-05 / INDEX-03/04 source-only batches | partial | `tests/test_core_source_batch.py` plus single-source/staging/catalogue/taxonomy/ingestion/revision/index fixtures; UI build/browser smoke | Copy destinations and all dependencies precede approval; own-write hashes preserve shared views; partial results/provenance survive faults without replay. | Mixed-kind/multi-topic staging, rehash IO costs, cancellation and full ownership enforcement/stress remain open. | `c48e6a0`; 204 focused passed; 22 new checks; browser build/smoke passed; full: 1,188 passed, 2 skipped, 1 deselected. |
| CORE-05 / INDEX-03/04 single-source acceptance | partial | `tests/test_core_source_promotion.py` plus staging, catalogue/taxonomy, revisions, ingestion/intake, upkeep and index-ownership fixtures; UI build/browser smoke | Complete single-source plan precedes approval; copies preserve inputs; Core owns SQL; partial outcomes survive explicit review/restart without overwriting changed work. | Multi-item promotion, provider cancellation, runtime enforcement and Windows stress remain open; rejection target/attachment guards were completed in `74c6081`. | `870f2e5`; 182 focused passed; browser build/smoke passed; full: 1,166 passed, 2 skipped, 1 deselected. |
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
| ADAPT-04B | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_provider_cancellation.py tests/test_model_invocation.py tests/test_model_session_evidence.py tests/test_loop.py tests/test_shutdown.py tests/test_host_local_yield.py -p no:cacheprovider` | First-party transports abort active calls; cancellation is typed through runtime, durable Session evidence, Loop and Core shutdown while legacy provider ABI remains compatible. | Normal calls retain configured timeout semantics; custom synchronous providers can only observe cancellation before/after their call. | `6960d84`; included in 184 focused and 1,417 full-suite passes. |
| ADAPT-10 | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_model_expectation_authoring.py tests/test_model_dialect.py tests/test_model_invocation.py tests/test_staging.py tests/test_arguments.py -p no:cacheprovider` | Only a person-reviewed, revision-matched, exact-route, provenance-linked declarative model-card record can enter the active personal pack; rejected/malformed records change no route. | Signed/sharded global pack distribution remains deferred. | `6960d84`; included in 184 focused and 1,417 full-suite passes. |
| ADAPT-11 | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_result_handles.py tests/test_loop.py tests/test_prompt_size.py tests/test_effort.py tests/test_shared_models.py -p no:cacheprovider` | Bare loops stay within the bundle cap; oversized supported reads return a bounded projection whose exact text is retrievable only through the originating loop. | Provider billing measurement remains opt-in; deterministic schema estimate recorded. | `6960d84`; [measurement](../reports/2026-10-26-adapt11-tool-surface.md); included in 184 focused and 1,417 full-suite passes. |
| DEPLOY-01–05 | planned | Adoption survey/apply/dedupe fixtures | Existing document trees remain byte-preserved and searchable without hidden user docs. | Windows/Obsidian fixture as applicable. | — |
| HARNESS-01–09 | planned | Session replay, verifier, and closure fixtures | Audited work reuses Session, never auto-promotes, and remains evidence bounded. | Tier-B evaluation budget only after its gate. | — |
| ACCEPT-01 | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_acceptance_matrix.py tests/test_accept_failures.py tests/test_accept_ranking.py tests/test_accept_workbench.py` | Each workflow has success, refusal, recovery, and no-mutation-on-failure coverage; the matrix test fails on an empty cell or a cited test that is missing or not in the default run. | G1, G2 and G4 closed; G3 not yet closed. | `tests/test_acceptance_matrix.py` (8 workflows x 4 kinds) |
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

INDEX-05 snapshot and reviewed-file continuation (`74c6081`):

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -o faulthandler_timeout=60
```

Active-handle snapshots, schema-v3 nanosecond/native identity, bounded
rename/delete reconciliation, stale-component cleanup, strict extract revision
and plan-token pinning, and collision-safe fresh-rejection quarantine are
covered by 69 dedicated tests and a 310-test combined group. Frozen-source full
verification passed **1,435 tests, 2 skipped, 1 deselected in 502.77s**.

The first combined run had one watcher quiet-window timing failure after 309
passes. The related 26-test group, five direct repetitions, the complete
310-test rerun and the full suite passed; it was not reproduced again during
that packet. It later recurred under full-suite load, and `f3b0508` isolated
the revision/CAS fixture from the independently tested watcher without
weakening either assertion. The normal host environment was used with approval
because the Codex app sandbox denied atomic replacement in its redirected
temporary directory and stalled a socket-pair fixture. Scope and remaining G1
work are recorded in the [continuation report](../reports/2026-10-26-index05-snapshot-continuation.md).

INDEX-05 process-interruption continuation (`2e9df4a`):

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests/test_core_process_interruption.py tests/test_operation_recovery.py tests/test_shutdown.py tests/test_host_lifecycle.py tests/test_process_identity.py tests/test_core_concurrency.py tests/test_index_snapshot_consistency.py -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=60
```

The final focused group passed **66 tests in 31.92s**. The corrected abrupt-crash
scenario also passed five consecutive independent runs. Frozen-source full
verification:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=60
```

Result: **1,438 passed, 2 skipped, 1 deselected in 468.12s (7m48s)**.

The first full run reported one failure after **1,437 passes**: the existing
revision/CAS test raced its second write against the watcher's independent
quiet window. Commit `f3b0508` isolates that no-plugin revision fixture; five
direct repetitions and the 44-test revision/watcher/file-access/snapshot group
then passed without relaxing product behavior.

The normal host environment was required because the Codex app sandbox's
redirected temporary tree denied child atomic lease replacement. No external
provider or paid call was used. This closes abrupt process-death evidence only:
authenticated Host force-stop, scale, real adapters, external handles and the
supported-Python/packaged matrix remain open.

INDEX-05 authenticated Host force-stop continuation (`84b90a8`):

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests/test_core_process_interruption.py tests/test_host_lifecycle.py tests/test_shutdown.py tests/test_operation_recovery.py tests/test_process_identity.py -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=60
```

The focused lifecycle/recovery group passed **49 tests in 32.78s**. The real
child first refuses a non-force stop with active counts, then accepts an
authenticated force request, records a truthful `shutdown_pending` result and
exits without a kill fallback. Explicit stale-lease takeover creates one
non-replaying recovery and restores WAL/index/Markdown integrity.

The same frozen-source full command passed **1,439 tests, 2 skipped, 1
deselected in 506.43s (8m26s)**. The normal host environment was again
required because the app sandbox denied atomic replacement in its redirected
temporary tree. This closes the Host force-stop slice only; scale, real
adapters, unsupported external handles and the supported-Python/packaged
matrix remain. See the [force-stop report](../reports/2026-10-27-index05-host-force-stop.md).

INDEX-05 large-vault and sustained-traffic continuation (`ae00300`):

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests/test_index_large_vault.py tests/test_index_sustained_traffic.py -m slow -rP -s -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=120
```

The sequential characterization passed **2 tests in 110.81s**. It covers a
5,000-note / 24.19 MB initial, stable and incremental refresh plus 30 sustained
barrier rounds across Browser/person, MCP, external-file, Obsidian, read and
maintenance workers. Correctness assertions cover exact bytes/metadata/path
convergence, no orphans/open transaction, one IndexService connection/thread,
completed operations, clean leases and teardown. Timings are diagnostics, not
SLAs.

The default-marker companion passed **18 tests, 2 deselected in 17.82s**. The
frozen-source default suite passed **1,439 tests, 2 skipped, 3 deselected in
481.36s (8m01s)**; the two additional deselections are the explicit slow
characterizations. Packaged adapters, unsupported long-lived external handles,
large attachments/encoder occupancy and the supported-Python/packaged matrix
remain. See the [scale report](../reports/2026-10-27-index05-scale-sustained.md).

INDEX-05 packaged-adapter prerequisite continuation (`bcf687a`):

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests/test_setup_python.py tests/test_release_versions.py tests/test_obsidian_adapter_contract.py tests/test_host_lifecycle.py tests/test_process_identity.py tests/test_doctor.py -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

The focused group passed **41 tests in 12.41s**. It pins supported-interpreter
selection, exact release-version agreement, authoritative Obsidian discovery
identity and the Host process-start publication used by that check.

```powershell
Push-Location obsidian
npm.cmd run build
npm.cmd run check
Pop-Location
& .\.venv\Scripts\python.exe scripts/check_release_versions.py --root .
& .\scripts\build-release.ps1 -OutDir tmp\release-prereq-check-host-20261027 -SkipTests -SkipUi
```

Both Obsidian commands passed. The metadata check reported Core `2.1.0.dev0`
and adapters `2.1.0-dev`. The fresh Python 3.11 host release candidate passed
the same gate, built the wheel in isolation and included both expectation JSON
resource families. The first sandbox build reached the metadata gate and then
failed only because DNS/PyPI access was blocked; it is not acceptance evidence.
Generated `tmp/` artifacts remain untracked.

Frozen-source default verification:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

Result: **1,453 passed, 2 skipped, 3 deselected in 1,025.42s (17m05s)**.

This packet is not a packaged-runtime or matrix result. It does not cover
simultaneous packaged Browser/Cowork execution, real Obsidian execution,
Python 3.12/3.13, a clean installed-wheel smoke, signed artifacts, external
handles, large attachments or encoder writer occupancy. See the
[prerequisite report](../reports/2026-10-27-index05-package-prerequisites.md).

INDEX-05 clean installed-wheel continuation (`6fb2389`):

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests\test_installed_wheel_smoke.py -p no:cacheprovider
& .\.venv\Scripts\python.exe -m pytest -q tests\test_installed_wheel_smoke.py tests\test_release_versions.py tests\test_host_lifecycle.py tests\test_source_identity.py -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

The contract passed **6 tests in 0.13s**. The focused group passed **19 tests
in 4.59s** on the normal host. Its first sandbox run passed 15 and failed four
Host cases only because redirected Windows temporary storage denied atomic
`os.replace`; the host rerun replaces that environment-only result.

The smoke script parsed as PowerShell, and both changed workflow YAML files
parsed. An independent fresh-venv CPython 3.11 replay installed candidate
version `2.1.0.dev0`, served the packaged UI/API, listed **140 MCP tools**, ran
read-only `vault_status` through the live installed Core and stopped without a
lease or discovery record. CI configures the same wheel smoke for 3.11--3.13,
but hosted matrix execution is not claimed; stable uses its reviewed offline
wheelhouse.

Frozen-source default verification:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

Result against implementation commit `6fb2389`: **1,459 passed, 2 skipped, 3
deselected in 518.59s (8m38s)**.

This packet does not prove Python 3.12/3.13 execution, real Browser UI
automation, the Claude/Cowork host UI, real Obsidian, or a signed bundle.
External handles, large attachments and encoder writer occupancy remain open.
See the [installed-wheel report](../reports/2026-10-27-index05-installed-wheel-smoke.md).

INDEX-05 packaged Browser/Cowork continuation (`788540e`):

```powershell
node --check ui\packaged-smoke.mjs
& .\.venv\Scripts\python.exe -m pytest -q tests\test_packaged_adapter_smoke.py tests\test_installed_wheel_smoke.py -p no:cacheprovider
& .\.venv\Scripts\python.exe -m pytest -q tests\test_packaged_adapter_smoke.py tests\test_installed_wheel_smoke.py tests\test_release_versions.py tests\test_host_lifecycle.py tests\test_mcp.py tests\test_source_identity.py -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

The combined fast contracts passed **11 tests in 0.21s**. The relevant
normal-host group passed **44 tests in 27.06s**. PowerShell AST and both changed
workflow-YAML parses also passed.

```powershell
& .\scripts\smoke-packaged-adapters.ps1 `
  -Python .\.venv\Scripts\python.exe `
  -Wheel tmp\release-prereq-check-host-20261027\core\resource_librarian-2.1.0.dev0-py3-none-any.whl `
  -CoworkZip tmp\release-prereq-check-host-20261027\cowork\librarian-cowork.zip `
  -WorkRoot C:\Users\jakem\AppData\Local\Temp\librarian-packaged-adapters-root-review-02
```

The independent fresh-venv replay passed with a real installed Edge page held
open while the command from the actual Cowork ZIP resolved inside the venv,
listed **140 MCP tools** and called `vault_status` through the shared installed
Core. The same browser rechecked the API afterwards; one Core then stopped
without lease or discovery residue. The token used only environment state and
was deleted before launching the browser child.

Frozen-source default verification:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

Result against implementation commit `788540e`: **1,464 passed, 2 skipped, 3
deselected in 500.98s (8m20s)**.

The configured Python 3.13 adapter and candidate/stable release jobs have not
run in hosted CI. This is packaged protocol/runtime evidence, not execution in
the real Claude/Cowork host UI or Obsidian. Python 3.12/3.13 runtime evidence,
a signed bundle, external handles, large attachments and encoder occupancy
remain open. See the
[packaged-adapter report](../reports/2026-10-27-index05-packaged-adapters.md).

INDEX-05 unsupported external-handle continuation (`ef143be`):

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests\test_index_external_file_handle.py tests\test_index_external_sqlite_handle.py tests\test_revisions.py tests\test_file_access.py tests\test_core_concurrency.py tests\test_index_sustained_traffic.py -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

The focused group passed **29 tests, 1 deselected in 23.16s**. A native
no-delete-share handle makes one Markdown replacement fail explicitly without
partial bytes, stale index state, a temporary-file leak or a dead writer; an
unrelated write and an explicit post-release retry succeed. A foreign
query-only SQLite transaction retains WAL frames while coordinated
refresh/read/integrity work stays live; passive checkpoint metrics expose the
incomplete work and the first checkpoint after release completes.

Frozen-source default verification:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

Result against implementation commit `ef143be`: **1,466 passed, 2 skipped, 3
deselected in 485.52s (8m05s)**.

This is fail-safe and recovery evidence for unsupported foreign handles, not a
promise that arbitrary external file or SQLite handles are coordinated or
time-bounded. Large attachments/scan amplification, encoder writer occupancy,
hosted matrix/signing evidence and external real-host execution remain open.
See the [external-handle report](../reports/2026-10-27-index05-external-handles.md).

INDEX-05 large-attachment characterization (`901ec65`):

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests\test_index_large_attachments.py -m slow -rP -s -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=120
& .\.venv\Scripts\python.exe -m pytest -q tests\test_core_source_promotion.py tests\test_index_large_attachments.py -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

The slow characterization passed **1 test in 7.18s**. It promoted 64 MiB of
raw input and 16 MiB of cleaned input through the real coordinated Core,
retained both originals, published exact copies, left no attachment temporary
file, converged the source/index, passed integrity and drained/closed the
writer and index service. Browser and MCP reads completed in **0.047s** while
the first attachment scan was paused. The default companion passed **41 tests,
1 deselected in 25.86s**; its deselection is the explicit slow case.

The measured work shape was **2,332,033,024 attachment bytes read**, **2,279
read calls**, a **1 MiB** maximum block and **27.8x scan amplification** over
80 MiB of logical input. These are diagnostic local measurements, not latency,
memory or capacity guarantees.

Frozen-source default verification:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

Result against implementation commit `901ec65`: **1,466 passed, 2 skipped, 4
deselected in 497.98s (8m17s)**.

This packet characterizes but does not reduce repeated attachment hashing.
Scan amplification, encoder writer occupancy, hosted matrix/signing evidence
and external real-host execution remain open. See the
[large-attachment report](../reports/2026-10-28-index05-large-attachments.md).
