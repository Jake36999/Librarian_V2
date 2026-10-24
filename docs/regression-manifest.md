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
| CORE-06 | planned | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_operation_recovery.py` | Start-only operation produces one idempotent recovery checkpoint before mutation admission. | Core restart fixture. | — |
| CORE-07 | planned | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_event_resync.py` | SSE gaps/restarts emit one epoch-aware resync instruction without replaying actions. | Restart fixture. | — |
| INDEX-01/02 | partial | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_sqlite_ownership.py tests/test_core_index_service.py tests/test_desk.py tests/test_taxonomy.py` | Static debt only shrinks; migrated calls remain on IndexService worker. | Real Core context per migrated family. | `557126c`, `8ccce9b` |
| INDEX-03/04/05 | planned | Focused module batch plus `tests/test_core_index_service.py` and Windows stress fixture | No serving path constructs a direct SQLite engine; WAL reads/writes remain safe. | Windows host. | — |
| ROUTE-01/02 | implemented / partial | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_app.py` | Lead patch preserves other positions; display preserves `unknown`. | API alias coverage belongs to ROUTE-03. | `77315cc`, `7a48f0c` |
| ROUTE-03–05 | planned | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_role_route_bindings.py tests/test_qualification_jobs.py tests/test_app.py` | Role slot resolves one exact route and role-scoped evidence. | Migration fixture. | — |
| ADAPT-01–05 | planned | `& .\.venv\Scripts\python.exe -m pytest -q tests/test_provider_failures.py tests/test_loop.py tests/test_model_invocation.py` | Metadata/continuation/rendering preserve legacy provider ABI and redact secrets. | Live L1 only when opted in. | — |
| ADAPT-06/07 | planned | Service transport unit fixtures; qualification probe tests | Shared host policy and two-turn tool continuation are enforced. | Provider budget for L1. | — |
| ADAPT-08–11 | planned | Pack, prompt-boundary, and tool-bundle/handle fixtures | Declarative packs cannot execute instructions; context/result bounds remain enforced. | Provider measurement only when opted in. | — |
| DEPLOY-01–05 | planned | Adoption survey/apply/dedupe fixtures | Existing document trees remain byte-preserved and searchable without hidden user docs. | Windows/Obsidian fixture as applicable. | — |
| HARNESS-01–09 | planned | Session replay, verifier, and closure fixtures | Audited work reuses Session, never auto-promotes, and remains evidence bounded. | Tier-B evaluation budget only after its gate. | — |
| ACCEPT/RELEASE | blocked externally | Frozen artifact, UI/adapter, Windows, rollback, and qualification matrix | Stable-release claims have real environment/provider evidence. | Release-owner authority, credentials, signing material. | — |
