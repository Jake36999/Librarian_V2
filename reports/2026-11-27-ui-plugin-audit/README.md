# Obsidian Plugin & Web UI Before/After Audit (27 November 2026)

**Branch & commit audited:** `feat/geo-per-library-service` at `383a3d15154b70556bfe550f5265ec4cbed79bea` (`383a3d1`).
**Baseline references compared:** `c4eb76f` (`167` commits prior) and `04acfe4` (baseline of the current finalisation series).
**Result:** **0 shipping regressions found** across `obsidian/src/`, `obsidian/dist/`, `ui/src/`, `src/resource_librarian/ui/`, and Core `/api/` routes (`app.py`). No production files required restoration. Two historical smoke scripts (`ui/smoke.mjs` via stale `tests/ui_demo_core.py:280` wrapper, and hardcoded `ui/live-permissions-staging-check.mjs`) are documented as smoke-harness coverage gaps with exact causes.

---

## 1. Source Diff & Deletion-Hunk Review (`c4eb76f..383a3d1` & `04acfe4..383a3d1`)

- **`04acfe4..383a3d1` (`10` UI/Obsidian files changed):**
  - `obsidian/src/` had **0** changes since `04acfe4`; `obsidian/dist/{main.js, styles.css}` were rebuilt from updated `ui/src/`.
  - `ui/src/` changed only in `folders.ts`, `main.ts`, `style.css`, and `views.ts` (M1a additions: `Reload item, keeping your edits`, `processing` = *Being ingested* mutual-exclusion filter, `Selected for the description batch; not decided yet` / `Decided and applied by a person` folder badges, and finished run chip `Details` dialog).
- **`c4eb76f..383a3d1` (`16` source/bundle files changed, `136` deleted source lines across `ui/src/`):**
  - Every deletion hunk across `ui/src/` (`api.ts`: 1, `attach.ts`: 35, `chat.ts`: 7, `commands.ts`: 1, `main.ts`: 30, `pane.ts`: 13, `panels.ts`: 24, `settings.ts`: 2, `style.css`: 1, `views.ts`: 22) was inspected and verified **`intended`**:
    - `attach.ts`: replaced duplicated inline `/api/files` folder browser with `AttachHooks.pickFile()` (single navigation surface in `DocPane`) + `openRegistry()` + `workflows()`.
    - `panels.ts`, `views.ts`, `main.ts`: extracted `workflows.ts`, `folders.ts`, `catalogue.ts`, `model_order.ts`; replaced hardcoded model ordering and silent reload discard with explicit preservation helpers.

---

## 2. Clean Lockfile Rebuilds vs. Committed Artifacts

Both packages were copied to isolated scratch (`G:\Librarian-work\tmp\build-check\repo\`), installed cleanly from lockfiles with `npm ci`, and built (`npm run check && node build.mjs` — `tsc --noEmit` + `esbuild`):

| Artifact | Clean `tsc --noEmit` | Clean `esbuild` Output vs. Committed File | Notes |
|---|---|---|---|
| `src/resource_librarian/ui/app.js` | **PASS** | **`0` diff lines** (`9163` lines normalized) | Byte difference (`426,858` vs `436,021`) is CRLF vs LF line endings only |
| `src/resource_librarian/ui/app.css` | **PASS** | **SHA-256 identical** (`28669af97abf6746`, `50,907` B) | Exact byte match |
| `src/resource_librarian/ui/index.html` | **PASS** | **SHA-256 identical** (`105a96cb8d4b9792`, `773` B) | Exact byte match |
| `obsidian/dist/main.js` | **PASS** | **`0` diff lines** (`9704` lines normalized) | Byte difference (`429,102` vs `438,806`) is CRLF vs LF line endings only |
| `obsidian/dist/styles.css` | **PASS** | **SHA-256 identical** (`28669af97abf6746`, `50,907` B) | Exact byte match |
| `obsidian/dist/manifest.json` | **PASS** | **SHA-256 identical** (`a1a3035715705e01`, `293` B) | Exact byte match |

---

## 3. Core API Parity (`ui/src/` & `obsidian/src/` vs. `app.py`)

Scanned all `/api/...` request patterns across `ui/src/*.ts` and `obsidian/src/*.ts` against `/api/...` route literals in `src/resource_librarian/app.py` (`98` route literals):
- **Result:** **`82 / 82`** UI/Obsidian `/api/` endpoint patterns match live Core routes in `app.py` (**`0` missing routes**).

---

## 4. Browser & Adapter Smoke Verification (Synthetic Scratch Fixtures Only)

All runnable smoke checks ran against the **freshly rebuilt** scratch bundles (`G:\Librarian-work\tmp\build-check\repo\`), Chrome (`C:/Program Files/Google/Chrome/Application/chrome.exe`), zero live vaults, zero paid model calls:

| Smoke Check | Fixture Used | Result | Notes / Root Cause if Not Run or Stale |
|---|---|---|---|
| `ui/obsidian-view-smoke.mjs` | Synthetic host stub + rebuilt `obsidian/dist/main.js` | **PASS** | Verified retry, explicit stale-lease takeover, protocol recovery, disposal |
| `ui/m1a-smoke.mjs` | `tests/folder_review_demo.py` + Geo-Grapher wheel Python | **PASS** | All 4 M1a checks passed (run `Details`, stale keep-edits, `processing`/`accepted` mutual exclusion, folder batch-selected/person-decided labels) |
| `ui/folders-smoke.mjs` | `tests/folder_review_demo.py` + Geo-Grapher wheel Python | **PASS** | Draft, metadata, suggested group, person accept, persistence, stale refusal, re-survey |
| `ui/phase8-catalogue-smoke.mjs` | `esbuild` bundle of `src/catalogue.ts` in Chromium | **PASS** | `7 catalogue browser checks passed; zero model calls` |
| `ui/phase8-folder-intake-smoke.mjs` | `esbuild` bundle of `src/folders.ts` in Chromium | **PASS** | `4 folder intake browser checks passed; zero models` |
| `ui/phase8-model-card-smoke.mjs` | `esbuild` bundle of `src/panels.ts` in Chromium | **PASS** | `4 model-card picker checks passed; zero model calls` |
| `ui/phase8-workspace-smoke.mjs` | `esbuild` bundle of `src/pane.ts` in Chromium | **PASS** | `4 read-only workspace browser checks passed; zero model calls` |
| `ui/phase8-authorship-smoke.mjs` | Disposable `G:\Libraries\_qa\b3-tmp-auth` output dir | **PASS** | Verified purpose derivation, no data default, explicit authorship; temp dir cleaned up |
| `ui/permissions-staging-smoke.mjs` | `esbuild` bundle of `src/settings.ts` in Chromium | **PASS** | `PASS: Permissions page saves only the selected tool` |
| `ui/staging-race-check.mjs` | Scratch-pathed copy of `src/views.ts` in Chromium | **PASS** | `PASS delayed folder response cannot overwrite Sources` |
| `ui/run-smoke.mjs` (`ui/smoke.mjs` + `tests/ui_demo_core.py`) | `tests/ui_demo_core.py` | **Coverage gap (stale smoke harness)** | Unmodified `tests/ui_demo_core.py:280` defines `def person_call(name, arguments, session="")` without `actor=None`, causing `TypeError: person_call() got an unexpected keyword argument 'actor'` from `app.py:4877` on Desk/Lenses calls (`smoke.mjs:189`). Production `App.person_call` (`app.py:3059`) accepts `actor=None` cleanly. When `actor=None` is forwarded in a scratch copy of `ui_demo_core.py`, steps 1–35 pass until `smoke.mjs:599`, where `locator('.lib-staging').locator('text=Accepted')` matches the hidden M1a `<option value="accepted">Accepted into the library</option>` first (stale selector vs M1a UI). |
| `ui/live-permissions-staging-check.mjs` | None (`http://127.0.0.1:57707/`) | **Coverage gap (one-off live script)** | Hardcoded Nov 15 local server port `57707` and `G:/Libraries/_qa/*.png`; superseded by `permissions-staging-smoke.mjs` and `m1a-smoke.mjs`. |
| `ui/packaged-smoke.mjs` & `ui/phase8-woven-smoke.mjs` | Installed wheel & woven fixtures | **Coverage gap (wheel/release harness)** | Designed for `scripts/smoke-installed-wheel.ps1` / standalone woven fixture generator; contract coverage verified by `tests/test_installed_wheel_smoke.py` and `tests/test_packaged_adapter_smoke.py` in the clean-clone pytest run. |

---

## 5. Verification Before Commit

- `src/resource_librarian/`, `ui/`, and `obsidian/` required **0** code edits (`0` production regressions).
- Clean-clone `scripts/regression_audit.py compare`: `0 difference(s) to account for; 0 tool(s) added` (`201 tools, 172 modules, 98 routes, 86 rules`).
- Clean-clone `pytest tests/test_*.py`: `2933 passed, 2 skipped, 5 deselected in 779.98s (0:12:59)` (all `test_installed_wheel_smoke.py` and `test_packaged_adapter_smoke.py` cases included).
