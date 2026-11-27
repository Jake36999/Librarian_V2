# Branch vs. `master` Audit (27 November 2026)

**Branch audited:** `feat/geo-per-library-service` at pinned commit `383a3d15154b70556bfe550f5265ec4cbed79bea` (`383a3d1`, *M5, fourth part: semantic metadata from the read*).
**Reference master tips & merge base:**
- **Merge base:** `c4eb76ff1c2b78346fd7743dadda5d6b170427b5` (`c4eb76f`, 12 November — *Agent guide: DeepInfra as a code worker (DELEG-01 to DELEG-06)*).
- **Local `master`:** `5abe859ffa8f7605d9ab6a11c00a077baba41e98` (`5abe859`, *Fix the two final S6 suite failures*) — an **ancestor** of `383a3d1` (`0` commits ahead of `383a3d1`, `117` behind).
- **`origin/master` & `public/master-curated`:** `f8dc6b855b9d9eddbe29cf63cac2d4713f1e8425` (`f8dc6b8`, 15 November — *Librarian: Phase 6–8 code, architecture and guides*). Merge base with `383a3d1` is `c4eb76f` (`167` commits on `feat/geo-per-library-service`, `1` curated squash commit on `origin/master`).

**Verdict:**
- **Part A (`c4eb76f..383a3d1`):** **0 unrecorded losses (`0 lost`, `0 unclear`).** All `53` surface/constant/standard differences reported by `scripts/regression_audit.py compare`, all test/doc deletions reported by `deletions`, and all code deletion hunks across the 53 modified Python/YAML modules are accounted for by explicit commits and §19 entries (with the two M0–M5 regressions previously fixed in `6276d70`). All four live libraries' `.librarian/` state loaded cleanly in isolated scratch copies on `G:`.
- **Part B (`c4eb76f..f8dc6b8` vs `c4eb76f..383a3d1`):** `f8dc6b8` introduces **0** code/doc files absent from `383a3d1`; every addition (`71`) and modification (`79`) in `f8dc6b8` already exists on `feat/geo-per-library-service` (`87` files byte-identical at tip; `64` code/doc files strictly newer on `383a3d1`, plus `.gitignore` where `f8dc6b8` swapped dev ignores for public-curation ignores). `f8dc6b8` deletes `576` internal reports, experiments, and handoff docs kept on `feat/geo-per-library-service`. **Do not merge** either direction without resolving the Owner decision list below.

---

## 1. Part A — Branch Since Merge Base (`c4eb76f..383a3d1`, 167 commits)

### 1.1 Automated Inventory Method & Coverage

`scripts/regression_audit.py inventory` was run against `383a3d1` (`201` tools, `172` modules, `98` API routes, `86` rules) and against a detached worktree of `c4eb76f` (`179` tools, `132` modules, `85` routes, `56` rules) using a schema-compatible wrapper (`getattr` fallbacks for `batch.MODEL_STAGES`/`STAGE_TOOLS`/`STAGE_RECIPES`/`CONTRACT`, `role_routes.CHAT_ROLES`, and `agent_runtime.DEFAULT_PROFILES`, because `c4eb76f` predates `STAGE_TOOLS` and `CONTRACT`), then compared with `scripts/regression_audit.py compare` and `scripts/regression_audit.py deletions`.

**Inventory coverage & blind spots:**
- **Covered:** registered tools (tier, effect, flags, phases, parameter names/defaults, returns), `Rule(...)` constants in `rules.py`, `standard/` YAML/JSON/MD files, AST top-level functions/classes/methods/uppercase constants across `src/resource_librarian/**/*.py`, `/api/` route literals in `app.py`, `task=` literals, `MODEL_STAGES`/`STAGE_TOOLS`/`STAGE_RECIPES`/`STAGES`/`ROLES`/`CHAT_ROLES`/`DEFAULT_PROFILES`/`DEPENDENCIES`, deleted test files, removed/changed test assertions & added skips, and deleted doc lines.
- **Not covered by inventory alone (covered manually below or in Brief 3):** logic changes inside unchanged function signatures, TypeScript UI/Obsidian bundles (`ui/src/`, `obsidian/src/`), and live vault `.librarian/` runtime compatibility.

### 1.2 Summary of Unchanged / Strictly Additive Surface

| Area | `c4eb76f` | `383a3d1` | Removals | Notes |
|---|---:|---:|---:|---|
| Registered tools | 179 | 201 | **0** | +22 tools added (`folder_*`, `source_verification_plan`, `request_raw_source_access`, `canvas_*`, etc.) |
| Rules (`rules.py`) | 56 | 86 | **0** | +30 rules added |
| Modules (`src/resource_librarian/*.py`) | 132 | 172 | **0** | +40 modules added |
| API routes (`app.py`) | 85 | 98 | **0** | +13 routes added (`/api/folders*`, `/api/geographer*`, `/api/routes/role`, `/api/skills`, `/api/actions/*/resume`, `/api/actions/*/dismiss`, `/api/source-original`) |
| `task=` names | — | — | **0** | None removed |
| Default profiles (`DEFAULT_PROFILES`) | 4 | 7 | **0** | Preserved `lead`, `scribe`, `clerk`, `research_helper`; added `code-research`, `oracle`, `repair` |
| Deleted test files | — | — | **0** | None deleted |

### 1.3 Accounting for Every Difference from `scripts/regression_audit.py compare` (53 items)

All **53** items reported by `compare` are classified **`intended`**:

| Category | Item(s) | Change (`c4eb76f` → `383a3d1`) | Commit & Rationale (§19) | Verdict |
|---|---|---|---|---|
| Tool flags | `batch_cancel`, `ocr_pdf`, `run_pipeline`, `run_resume`, `run_workflow` (`orchestrates`: `False -> True`) | Enforced orchestrator admission boundary so multi-step/pool callers run beside the writer rather than inside a single writer transaction (`ORCHESTRATION_CONTEXT` fix) | `b5ba9dc` / M5 acceptance (§19) | **intended** |
| Tool tier | `request_budget` (`contribute -> consult`) | Session-scoped budget request opened to consult-tier callers | `bfbf74d` / `48acb1b` | **intended** |
| Tool params | `decide` (`reason`: `'' -> <required>`); `source` accepts `list[str] \| str` | MiMo-V2.6-Flash omitted optional `reason` repeatedly during Judge batching; keeping `source` scalar-compatible preserves existing callers (`2026-11-20` research run) | `ea6a30c` | **intended** |
| Internal helper rename | `tools/work_search.py`: removed `_hit`, added `_matched`, `_ranked`, `_reading` | Internal private helper replaced by rarity-weighted / reading-aware search ranking | `5c5aa3a` / `f6a85d6` | **intended** |
| `session.py` constants moved to data | `ASKS`, `ASSUMPTION_PHASES`, `DEFAULT_BUDGETS`, `MODE`, `PURPOSES` removed from module scope; `HARNESS` grew (`+request_raw_source_access`) | Moved declaratively into `src/resource_librarian/standard/phases.yaml` + `phases.py` (`W1`) | `f6a85d6`, `48acb1b` | **intended** |
| `loop.py` `UPKEEP_TOOLS` | Removed `capability_candidates` from `UPKEEP_TOOLS`; `BASE` prompt gained `"You finish the work you are asked to do..."` | `capability_candidates` belongs to `add_capability`'s `candidate` phase bundle rather than upkeep; prompt updated per `docs/policy/` | `3d50b2f`, `9c0592d` | **intended** |
| `agent_runtime.py` | `MAX_BUNDLE_TOOLS: 12 -> 22`, `BUNDLES`, `MACROS`, `DEFAULT_PROFILES`, `PROJECT_BOOTSTRAP_PURPOSES` | Moved phase bundles/macros to declarative `phases.yaml` + workflow YAMLs; expanded cap so tail gate tools are never clipped | `f6a85d6`, `3d50b2f`, `d68f8bc` | **intended** |
| `staging.py` | `KINDS` (`+folder`); `DECIDABLE['approve']` (`+enriched`) | Supports staged folder review cards and approving already-enriched items | `54f17b5`, `d1d6fd9` | **intended** |
| `checkpoints.py` | `CHECKPOINT_TYPES`: added `publication_taint`, `raw_source_access`, `high_risk_hold`, `folder_sensitivity`, `ticket_escalation` | New governance gates (taint, raw reads, escalations); existing 11 types preserved | `188abac`, `48acb1b`, `dbb08b7` | **intended** |
| `closure.py` / `research_grains.py` | `SUBJECTS`, `VERIFIERS`, `CHECKS`: added `packet.citation_resolves` | Code-research packet citation check; all 8/10 prior entries preserved | `59593d2` | **intended** |
| `role_routes.py` | `CHAT_ROLES` and `ROLES` added `oracle`, `repair` | Added M6 role slots without altering existing `lead`/`scribe`/`clerk`/`research_helper`/`ocr`/`tts`/`stt`/`embeddings` | `6276d70`, §19 (`M0–M5`) | **intended** |
| `batch.py` / `stages.yaml` runtime | `STAGES` (`+publish`), `MODEL_STAGES` (`+folder_describe, +metadata`), `STAGE_TOOLS` (`4` tools), `STAGE_RECIPES` (`metadata: '1' -> '2'`, `+folder_*`, `+publish`), `DEPENDENCIES` loaded from `stages.yaml` | Declarative stage DAG (`stages.yaml`), paper publish stage, folder batch, and W-REA-02 semantic metadata (`383a3d1`); existing 8 stages and deps preserved | `b5ba9dc`, `383a3d1`, §19 | **intended** |
| `standard/` YAML/JSON updates | `deepinfra.json` (Live DeepInfra pricing for 17 models, `fb11f50`; `recommendation_rank` `29296a8`); `core.json` (Gemma/Qwen/GPT-OSS headroom `90f0ca1`, `d1d6fd9`); `weekly-review.yaml`, `deep-read-staged.yaml`, `draft-reflection.yaml`, `ingest-cited.yaml`, `review-staged.yaml` (`+reason`/`+failed`/`+errors`; `item.drafted` vs `item.reviewed`) | Pricing accuracy, reasoning headroom expectations, surfacing skipped/failed items in workflow outputs | `fb11f50`, `29296a8`, `90f0ca1`, `d1d6fd9` | **intended** |
| Remaining constant extensions | `app.py::PROFILE_FIELDS`, `clerk.py::KINDS` (`terms` `max_tokens: 900 -> 1800`, `+folder_describe`), `index.py::SCHEMA_VERSION` (`5 -> 6`), `mcp_client.py::MAX_EXTERNAL_RESULT` (`8000 -> 24000`), `ocr.py::PROMPT`, `pdf_markdown.py::CLEANUP_SYSTEM`, `result_handles.py::ENVELOPE_KEYS` (`+read_allocation`), `search.py::_DEFAULTS` (`+coverage_weighting: rarity`), `text.py::SUPPORTED` (`+code/config suffixes`), `tools/delegate.py` (`HELPER_BRIEF`, `HELPER_TOOLS`), `vault.py::DEFAULT_CONFIG` (`+[reasoning] ocr='none'`, `+coverage_weighting='rarity'`) | Strictly additive / hardened defaults; backwards-compatible fallbacks kept | `5c5aa3a`, `48acb1b`, `f97e77c`, `bfbf74d`, `54f17b5`, `d1d6fd9` | **intended** |

### 1.4 Manual Deletion-Hunk Review Across Changed `src/resource_librarian/` Modules

Every module with deletion lines in `c4eb76f..383a3d1` (`52` pre-`04acfe4` Python/YAML/JSON modules, `21` M0–M5 commits already audited in [2026-11-27-regression-audit/README.md](../2026-11-27-regression-audit/README.md), and `3` post-`3ac06bb` modules excluding UI bundles covered in Brief 3) was inspected at the hunk level. Key deletion hunks verified **`intended`**:

- **`agent_runtime.py` & `session.py` (`f6a85d6`, `3d50b2f`):** Replaced inline `BUNDLES`, `PURPOSES`, `MODE`, `ASKS`, `DEFAULT_BUDGETS`, and `ASSUMPTION_PHASES` dicts with `standard/phases.yaml` loader (`phases.py`). Verified no phase or tool was dropped (tail clipping fixed via `MAX_BUNDLE_TOOLS: 12 -> 22`).
- **`app.py`:** Removed unconditional direct `self.invocation_runtime = InvocationRuntime()` in favor of `UsageLog` trace sink wiring (`trace_sink=self.usage_log.record`); changed `_role_tools` scope narrowing so `Clerk`/`Scribe`/`helper` qualification hashes don't invalidate on unrelated Lead tools; moved `_run_action` thread launch into reusable helper supporting `resume_action` (`WF-D4`); added `_keep_stale_lease` automatic stale takeover for Host-managed Cores (`2026-11-19`, ACCEPT-02); wording `"bind"` -> `"assign"` (`9c0592d`).
- **`broker.py` & `checkpoints.py`:** Re-entrant per-file checkpoint locks and workflow-grant handling (`test_a_workflow_a_person_starts_runs_without_asking_in_ask_mode` while keeping explicit `"deny"` rules enforced).
- **`clerk.py`, `deep_read.py`, `dik.py`, `ocr.py`, `pdf_markdown.py`, `tools/pdf.py`:** Switched hardcoded `inbox.md` siblings for generated conversions to content-addressed `.librarian/conversions/` (`f97e77c`); moved hardcoded DeepInfra cleanup model to configurable `[services] cleanup` slot (`route(vault)`); fixed `ThreadPoolExecutor` progress deadlock (`pdf_markdown.clean_document`); switched non-paged Markdown/text chunks to `unit="part"` (`dik.document`); spread summary bullets across all parts rather than truncating after bullet 40 (`deep_read.spread`).
- **`evidence.py`, `content_roots.py`, `projects.py`, `index.py`, `search.py`, `tools/library.py`, `tools/staging.py`:** Preserved pre-existing hash/legacy behavior when new optional fields (`authorship`, `workflow_grant`, `project-sidecars` when folder review is disabled) are absent; added WAL truncation (`PRAGMA journal_size_limit=64MiB` + `truncate_wal`), per-note lexical pool cap (`PER_NOTE_POOL=3`), `rarity` coverage weighting (`coverage_weighting="count"` retains V1 behavior), and `[search] refresh_seconds` opt-in skip (default `0`).
- **`mcp_client.py` & `tools/workflows.py`:** Reserved `geo-grapher` for library-owned Streamable HTTP service (`set_builtin`) while keeping `mcp.json` stdio/HTTP compatibility for external servers; raised external structured result ceiling from `8,000` to `24,000` (up to `160,000` scaled by route window).

### 1.5 Accounting for `scripts/regression_audit.py deletions` (Docs & Tests)

- **Deleted test files:** None (`0`).
- **Removed/modified test assertions (`tests/`):** Every changed assertion corresponds to an intentional behavior evolution verified by new tests: `test_app_reopen.py` (Host auto-takeover keeping stale lease record, `2026-11-19`), `test_pdf_markdown.py` (hidden `.librarian/conversions/` + `[page N]` anchors + configurable `[services] cleanup`, `f97e77c`), `test_app.py` (workflow-level permission grant with explicit `deny` respected; library-owned `geo-grapher` in `/api/mcp`), `test_agenda.py` / `test_authoring.py` (central `access.sources` provenance + `Manifest` ownership on `Inbox`), `test_handoff.py` (named refusal rules `APPLICATION_SOURCE_UNKNOWN` / `APPLICATION_SOURCES_REQUIRED`), `test_core_concurrency.py` (`wal_checkpoint(TRUNCATE)` on refresh), `test_mcp.py` (clearer Clerk routing message), `test_ocr.py` (`recipe: "visual-v3"`), `test_structure.py` (`KAFKA_BROKERS` refused by credential template guard), `test_workflows.py` (un-ingested external link counting / pipeline checks), `test_sbom.py` (reuse single built wheel variable), `test_result_handles.py` (raw source grant required on fresh instance).
- **Removed doc lines (`docs/`):** All removed lines in `docs/agent-guide.md`, `docs/model-invocation-architecture.md`, and `docs/terminology.md` come from `9c0592d` (*Policy pages, assign-not-bind, Managing Cores*), `4e0be2b`, and `ea6a30c` — replacing manual `host start` / `stale_vault_lease` instructions with full Core-lifecycle guidance and `"assign"` terminology. **Zero lost guidance.**

### 1.6 Isolated Saved-State Compatibility Checks (`G:\Libraries\*` & `E:\Librarian ACCEPT-02 Vault`)

**Directory inventory across `G:\Libraries\*` and `E:`:**
- **Checked Librarian vaults (`4`):** `G:\Libraries\Resource-Library`, `G:\Libraries\Parallax`, `G:\Libraries\Nonlinear Field Lab`, `E:\Librarian ACCEPT-02 Vault` (all contain `.librarian/`).
- **Excluded non-vault directories under `G:\Libraries\*` (`6`):** `_archive`, `_core-runtime`, `_geo-hub`, `_geo-runtime`, `_qa`, `_tmp` (none is a Librarian vault / none contains `.librarian/`).

**Isolation & pre-load live-path scan:** Only minimal `.librarian/` state files (`app.json`, `checkpoints.json`, `config.toml`, `content-roots.json`, `folder-sources.json`, `folder-surveys.json`, `geographer.json`, `profile.json`, `projects.json`, `mcp_enabled.json`, `lens_packs_accepted.json`, `agents/`, `sessions/`, `lenses.sqlite`, `desk.sqlite`, `About/`) were copied into `G:\Librarian-work\tmp\state-check\<vault>` (skipping locked `runtime/*.lock` files). Pre-load scanning detected live absolute paths in:
- `geographer.json` (`G:/Libraries/_geo-runtime/env/Scripts/python.exe` in all 4 libraries),
- `projects.json` (`F:\quantule_mapper` in Nonlinear Field Lab),
- `folder-surveys.json` (`F:\quantule_mapper`, `F:\network_management`, `D:\Resource-Library`, etc.),
- `content-roots.json` & `folder-sources.json` (attached codebase paths on `D:`, `E:`, `F:`), and historical `sessions/*.jsonl`.

All external/live drive paths in the scratch copies were rewritten to `<scratch_vault>/scratch_ext/...` via JSON-level string traversal, and re-scanned to confirm **0** non-scratch filesystem paths remained.

**Load results under `383a3d1` (`G:\Librarian-work\librarian-2026-11-27\src`):**

| Library | Vault Name | `Settings` (`effort`, `mode`, `profile`) | `RoleRouteStore` Bindings Loaded | Checkpoints Loaded | Sessions Loaded | Saved Workflows / Standard Validation | SQLite Copy Integrity | Result |
|---|---|---:|---:|---:|---:|---|---|---|
| `Resource-Library` | Resource-Library | `effort=2`, `mode=ask`, `lead` | All 8 roles (`clerk`, `lead`, `ocr`, `scribe`, `tts`, etc.) | 17 | 14 / 14 (0 err) | 0 user workflows; 22 standard valid | `lenses.sqlite`: ok; `desk.sqlite`: ok | **PASS** |
| `Parallax` | Parallax | `effort=2`, `mode=ask`, `lead` | All 8 roles | 9 | 6 / 6 (0 err) | 0 user workflows; 22 standard valid | `lenses.sqlite`: ok | **PASS** |
| `Nonlinear Field Lab` | Nonlinear Field Lab | `effort=2`, `mode=ask`, `lead` | All 8 roles | 18 | 7 / 7 (0 err) | 0 user workflows; 22 standard valid | `lenses.sqlite`: ok | **PASS** |
| `Librarian ACCEPT-02 Vault` | ACCEPT-02 Testing Library | `effort=8`, `mode=ask`, `lead` | All 8 roles | 18 | 5 / 5 (0 err) | 0 user workflows; 22 standard valid | `lenses.sqlite`: ok; `desk.sqlite`: ok | **PASS** |

*(Staging load verification on sanitized copies: copied up to 50 JSONs per kind from each large vault plus all `246` staging entries / `43` `folder` cards from `Librarian ACCEPT-02 Vault` to `G:\Librarian-work\tmp\state-check\`, scrubbed all live drive paths to `0` non-scratch drive paths, and loaded via `StagingStore.summaries(kind)`: `Resource-Library` `{source: 50, lens: 50, folder: 50}`, `Parallax` `{source: 50, lens: 50, folder: 50}`, `Nonlinear Field Lab` `{source: 50, lens: 50, folder: 50}`, `Librarian ACCEPT-02 Vault` `{source: 96, lens: 104, folder: 43}` — all **PASS** with `0` errors. Live counts in `.librarian/staging/folder/*.json`: `12,861` / `15,543` / `1,584` / `43`.)*

---

## 2. Part B — `origin/master` (`f8dc6b8`) vs. Branch (`383a3d1`) from Base `c4eb76f`

Comparing **both sides** from the common merge base `c4eb76f` prevents mistaking public-curation differences or post-Nov-15 branch work for `f8dc6b8`-unique features:

| Bucket (`c4eb76f..f8dc6b8` vs `c4eb76f..383a3d1`) | Count | Examples & Findings | Would merging `branch -> origin/master` lose it? | Would merging `origin/master -> branch` lose it? |
|---|---:|---|---|---|
| **Files added in `f8dc6b8` NOT in `383a3d1`** | **0** | None. Every file added in `f8dc6b8` (`71` files) also exists on `383a3d1`. | No | No |
| **Files modified in `f8dc6b8` NOT touched in `383a3d1`** | **0** | None. Every file modified in `f8dc6b8` (`79` files) was also touched on `383a3d1`. | No | No |
| **Overlap identical at tip (`383a3d1 == f8dc6b8`)** | **87** | Includes `docs/access-model.md`, `docs/WAVE_L_FOLDER_REVIEW.md`, `docs/library-notes/Content authorship.md`, `docs/phase8/FOLDER_INTAKE.md`, `docs/phase8/MODEL_CARD_REVIEW.md`, `access_classes.py`, `catalogue_navigation.py`, `conversions.py`, `folder_intake.py`, `model_cards.py`, `source_scope.py`, `source_verification.py`. | **No** (identical content) | **No** (identical content) |
| **Overlap differing at tip (`383a3d1 != f8dc6b8`, excl. `.gitignore`)** | **64** | Hunk comparison (`383a3d1..f8dc6b8`) shows `383a3d1` is a **strict superset** containing post-Nov-15 fixes (`SECRET_SUFFIXES` in `credentials.py`, `workflow_grant` & PDF guard in `read_access.py`, `undecided_folders` optimization in `workspace_documents.py`, `MAX_EXTERNAL_RESULT=24000`, `gpt_oss_120b` headroom test, M0–M5, W1–W7). Zero `f8dc6b8`-unique code or doc features are missing on `383a3d1`. | Taking `branch` preserves everything; forcing `f8dc6b8` would **lose** Nov 16–27 fixes | Taking `f8dc6b8` over `branch` would **lose** Nov 16–27 fixes & trigger 64 conflicts |
| **`.gitignore` (divergent policies)** | **1** | `c4eb76f..383a3d1` keeps dev ignores (`__pycache__/`, `node_modules/`, `dist/`, `*.sqlite`, `.env`, `/tmp/`) + adds `*.canvas.*.bak`. `c4eb76f..f8dc6b8` replaces dev ignores with public-curation exclusions (`reports/**`, `docs/experiments/**`, `!docs/experiments/g5-tasks.json`, `docs/proposals/**`, `docs/Development transcripts/**`, `docs/handoff-*.md`, `docs/regression-manifest.md`, `docs/release-implementation-queue.md`, etc.). | Taking `branch` `.gitignore` exposes internal `reports/` & `docs/proposals/` if pushed to public `origin/master` | Taking `f8dc6b8` `.gitignore` removes `*.sqlite`, `.env`, `.venv/`, `node_modules/` ignores from active dev branch |
| **Files deleted in `f8dc6b8`, kept on `383a3d1`** | **576** | Curated removal of internal dev history for public `master`: `reports/**` (`554` files incl. `reports/2026-11-12-progress/LIBRARY-ACCESS-API-SCOPE.md`), `docs/experiments/*` (`5`), `docs/handoff-2026-10-31-codex.md`, `docs/model-adapter-cohort-2026-10-23.md`, `docs/proposals/memory-context-design-addendum.md`, `docs/regression-manifest.md`, `docs/release-implementation-queue.md`, plus `docs/phase8/resource-library-expectations.{draft,review}.json` ignored/absent in `f8dc6b8`. | Merging raw `branch` into public `origin/master` would **publish** all 576 internal files | Merging `f8dc6b8` into `branch` would **delete** 576 internal reports/docs/experiments (unless regenerated/restored) |

### 1.7 Owner Decision List for Part B Reconciliation (Do Not Merge Yet)

1. **Internal dev history vs. public curation (`576` deleted files + `.gitignore`):**
   - **Question:** Keep `feat/geo-per-library-service` (and private development remote) holding all `reports/**`, `docs/experiments/**`, `docs/proposals/**`, and dev handoffs, while continuing curated export commits onto `origin/master` / `public/master-curated`? OR adopt `origin/master`'s `.gitignore` exclusions on an export script/orphan branch only?
   - **Recommended answer:** **Do NOT merge `f8dc6b8` (`origin/master`) into `feat/geo-per-library-service` or vice versa via Git merge.** Treat `public/master-curated` (`origin/master`) as the curated export target updated by a dedicated export step (like commit `f8dc6b8`), keeping BOTH the dev `.gitignore` entries (`*.sqlite`, `.env`, `.venv/`, etc.) and internal `reports/`/`docs/` history intact on the working development branch (or unioning `.gitignore` only if you want `reports/` local-only in git too).
2. **Local `master` (`5abe859`) fast-forward:**
   - **Question:** Fast-forward local `master` (`5abe859`, strictly behind `383a3d1`) when ready, distinct from curated public `origin/master` (`f8dc6b8`)?
   - **Recommended answer:** Keep local `master` distinct from `public/master-curated` (`origin/master`) until you are ready to promote `feat/geo-per-library-service` + M5–M7 as the new full internal `master` tip, and keep `public/master-curated` produced via a curation filter script.
3. **Code/doc files in the `64` overlapping files (`383a3d1 != f8dc6b8`):**
   - **Question:** Any `f8dc6b8` hunk worth cherry-picking back to `383a3d1`?
   - **Recommended answer:** **None needed.** `383a3d1` already contains all Phase 6–8 features from `f8dc6b8` plus verified Nov 16–27 fixes (`0` missing functional hunks).

---

## 2. Verification of Clean Clone Under `audit/branch-vs-master`

- Source & tests audited at `383a3d1` with **0** source code regressions found (`0` edits required to `src/resource_librarian/`).
- `scripts/regression_audit.py inventory` + `compare` after Brief 1 report edits: `201 tools, 172 modules, 98 routes, 86 rules` — `0 difference(s) to account for; 0 tool(s) added`.
- Full clean-clone pytest run (`tests/test_*.py`, `PYTHONPATH=G:\Librarian-work\librarian-2026-11-27\src`, `--basetemp G:\Librarian-work\tmp\pytest-b1`): **`2933 passed, 2 skipped, 5 deselected in 739.63s` (`0` failed)**.
