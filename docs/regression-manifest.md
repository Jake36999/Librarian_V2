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
| CORE-06 | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_operation_recovery.py` | Start-only operation produces one idempotent recovery checkpoint before mutation admission. | Core restart fixture. | `c264b9a` |
| CORE-07 | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_event_resync.py tests/test_app.py tests/test_shutdown.py tests/test_host_lifecycle.py` | SSE gaps/restarts emit one epoch-aware resync instruction without replaying actions. | Restart fixture. | `5708c39` |
| INDEX-01/02 | partial | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_sqlite_ownership.py tests/test_core_index_service.py tests/test_desk.py tests/test_taxonomy.py` | Static debt only shrinks; migrated calls remain on IndexService worker. | Real Core context per migrated family. | `557126c`, `8ccce9b` |
| INDEX-03 | partial | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_core_index_service.py tests/test_sqlite_ownership.py tests/test_authoring.py tests/test_sessions.py tests/test_review_gate.py tests/test_offering_view.py tests/test_learn.py tests/test_start_pursuit.py tests/test_weekly_review.py tests/test_pursuits.py` | Interleaved work receives copied data only from Core-owned SQLite; Markdown/session mutations remain on writer; Clerk/Scribe IO releases index worker; changed schemas refresh before validation. | Serving-path debt 33 → 17; further promotion batches and Windows stress remain. | `2e95158`, `86941d3`; final combined suite 1,039 passed, 2 skipped, 1 deselected. |
| Macro writer-wait follow-up | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_macro_permissions.py tests/test_person_waits.py tests/test_registry.py`; full browser smoke | Ask-mode waits never own the writer; explicit Deny/Plan still hold; partial work stays durable; external tools cannot opt out of writer serialization. | Automatic macro resume is not claimed. | `5b3be1f`; expanded focused group: 116 passed; final combined suite: 1,039 passed, 2 skipped, 1 deselected; browser smoke passed. |
| INDEX-04/05 | planned | Focused module batch plus `tests/test_core_index_service.py` and Windows stress fixture | No serving path constructs a direct SQLite engine; WAL reads/writes remain safe. | Windows host. | — |
| ROUTE-01/02 | implemented / partial | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_app.py` | Lead patch preserves other positions; display preserves `unknown`. | API alias coverage belongs to ROUTE-03. | `77315cc`, `7a48f0c` |
| ROUTE-03 (chat) / ROUTE-05 (chat) | partial | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_role_route_store.py tests/test_role_route_bindings.py tests/test_qualification_jobs.py tests/test_app.py tests/test_agent_runtime_profiles.py tests/test_clerk_routes.py` | Chat/background/helper use canonical bindings; task role owns qualification; invalid endpoints refuse without fallback. | Restart projection repair, offline lease, explicit helper preservation, and profile-slot fixtures. | `b6ef33b`, `14837a2`; full suite 1,016 passed, 2 skipped, 1 deselected on 2026-10-25. |
| BASE-02 (browser smoke) | implemented | `npm.cmd run build`; `npm.cmd run smoke` in `ui/` | Browser smoke uses this checkout, scripted providers, isolated credentials, and only its own process tree. | Installed Chromium-family browser. | `c6d189e`; complete smoke pass. |
| ROUTE-03 (services) / ROUTE-04/05 (routing) | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_service_routes.py tests/test_app.py tests/test_stt.py tests/test_role_route_bindings.py`; service-adapter group; `npm.cmd run build`; `npm.cmd run smoke` in `ui/` | Canonical assignments execute exact hosts; Clerk evidence never qualifies Lead; custom OCR/embedding routes and native speech remain explicit; stale/late service calls refuse. | Full suite during development: 1,028 passed, 2 skipped, 1 deselected; expanded focused group 84 passed, final service group 38 passed; browser smoke passed. Transport extraction/cancellation remains ADAPT-06. | 2026-10-25 service/readiness continuation; final combined full run follows next ownership batch. |
| ADAPT-01 | implemented | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_provider_failures.py tests/test_loop.py tests/test_model_invocation.py` | Metadata/continuation preserves legacy provider ABI, redacts secrets, and replays reasoning only for tool continuation. | Live L1 only when opted in. | `48b61a8` |
| ADAPT-02–05 | planned | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_provider_failures.py tests/test_loop.py tests/test_model_invocation.py` | Metadata/continuation/rendering preserve legacy provider ABI and redact secrets. | Live L1 only when opted in. | — |
| ADAPT-06/07 | planned | Service transport unit fixtures; qualification probe tests | Shared host policy and two-turn tool continuation are enforced. | Provider budget for L1. | — |
| ADAPT-08–11 | planned | Pack, prompt-boundary, and tool-bundle/handle fixtures | Declarative packs cannot execute instructions; context/result bounds remain enforced. | Provider measurement only when opted in. | — |
| DEPLOY-01–05 | planned | Adoption survey/apply/dedupe fixtures | Existing document trees remain byte-preserved and searchable without hidden user docs. | Windows/Obsidian fixture as applicable. | — |
| HARNESS-01–09 | planned | Session replay, verifier, and closure fixtures | Audited work reuses Session, never auto-promotes, and remains evidence bounded. | Tier-B evaluation budget only after its gate. | — |
| ACCEPT/RELEASE | blocked externally | Frozen artifact, UI/adapter, Windows, rollback, and qualification matrix | Stable-release claims have real environment/provider evidence. | Release-owner authority, credentials, signing material. | — |

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
