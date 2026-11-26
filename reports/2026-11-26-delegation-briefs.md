# Work another agent can take (26 November 2026)

These are self-contained pieces of [the implementation plan](../docs/proposals/implementation-plan-2026-11.md) that another agent, such as Codex or Antigravity, can do. Claude stays on the Librarian core milestones (M4 onward) and on review.

Each brief names its files, what done looks like, and what to leave alone.

## Rules for every brief

- **Branch and room:** work on your own branch or worktree. Make clean clones under `G:\Librarian-work`, because C: and D: are nearly full. Run tests with `TMP`/`TEMP` and `--basetemp` on G:.
- **Hands off the Librarian core:** do not edit `src/resource_librarian/` unless the brief says so. Claude is changing `broker.py`, `registry.py`, `staging.py`, `batch.py`, `checkpoints.py`, `tickets.py`, `manifests.py`, `stages.py`, the tools, and `docs/tool-access-declarations.json`.
- **The house rules (CLAUDE and AGENTS files, docs/policy):**
  - full suite in a clean clone before a commit;
  - a §19 entry in `docs/unified-implementation-plan.md` for Librarian changes;
  - explicit-path commits;
  - never force-push.
- **No feature losses** (Owner, 26 November): this is a hardening pass over the existing architecture. A new check that could refuse something allowed today ships in report mode first.
- **Tests:** list only `tests/test_*.py` when running pytest. `tests/ui_demo_core.py` serves forever.

## 1. Geo-Grapher: hosted CI, accurate status, the receipt contract (G2, G3, G1)

**Repository:** `F:\uv-data\Geo_Grapher`. This one is separate from the Librarian repository, so nothing conflicts with Claude's work.
- **G2:** add hosted CI. The repository has about a hundred test files and no `.github` folder. Run the suite on each push.
- **G3:** make the status say what was done. Complete, partial, refused and not applicable stay distinct; a parse failure is never "complete"; a genuinely empty input is not miscalled a failure.
- **G1:** define the receipt contract as a JSON schema with fixtures. Fields:
  - for graph building: `snapshot_id`, `parser_version`, coverage with the unparsed files, `changed_entity_ids`, counts;
  - for papers: `document_id`, the source's identity, and claim and concept counts.

  Geo-Grapher emits and tests it. The Librarian side (`geo_service.py` reading it) is Claude's, later.

**Done when:** a Geo-Grapher push runs its suite; a receipt missing a field fails Geo-Grapher's tests; the receipt's coverage matches the parse log.

**Read first:**
- `reports/2026-11-25-systems-analysis-finalisation/geo-grapher/to-be/receipt-contract.md`;
- `incremental-safety.md` in the same folder.

## 2. Geo-Grapher: an inventory for the agent interface, and triage of four defects (G6, read-only)

**Output:** a report only, `reports/2026-11-26-geo-grapher-inventory/README.md` in the Librarian repository.

**The inventory (G6):** compare what Geo-Grapher's Phase 6–7 already ships (integrated locally; v1.1 contracts, token accounting) with the to-be agent interface (GT6) and bridge review (GT5).

**The triage:** one code check each, with file and line evidence, for the four defects deferred in the systems-analysis README:
- dependency relations for Python functions;
- search when repository ids are omitted;
- conversions persisting a source graph;
- attached repositories kept read-only.

**Done when:** each item says "exists", "partly" or "missing", with evidence, and each defect says "confirmed" or "not reproduced".

## 3. The Obsidian plugin's build

**Files:** `obsidian/` only.

`obsidian/dist/main.js` and `styles.css` are well behind `ui/src`. Rebuilding pulls in every UI change since the last plugin build, M1a's included.

**Steps:**
1. Rebuild (`cd obsidian; node build.mjs`).
2. Review the diff.
3. Load the plugin in the test vault (`E:\Librarian ACCEPT-02 Vault`) and check the views open.
4. Commit the build with what was checked.

**Done when:** `tests/test_obsidian_adapter_contract.py` passes and the plugin opens in Obsidian with no console errors.

## 4. A browser check of M1a's Web UI

**Files:** `ui/*.mjs` (smoke scripts) and a short report.

**How:** start the folder demo with its temp folder on G:. Without that, Geo-Grapher refuses with `DISK_RESERVE`.

```powershell
$env:TMP="G:\Librarian-work\tmp"; $env:TEMP=$env:TMP; $env:WAVE_L_WHEEL_PYTHON="G:/Libraries/_geo-runtime/env/Scripts/python.exe"; $env:PYTHONPATH="src"; .venv\Scripts\python.exe tests\folder_review_demo.py
```

**What to check:**
- a finished run's chip has a Details button that opens its record;
- after a stale-revision conflict, "Reload item, keeping your edits" keeps the Bottom Line;
- "Which sources" lists processing and accepted items;
- folder cards say "Selected for the description batch; not decided yet" and "Decided and applied by a person".

Extend `ui/folders-smoke.mjs`, or add a smoke script, so these checks repeat.

**Done when:** the smoke passes against the demo Core and a screenshot of each check is in the report.

## 5. Draw UC10–UC16 in the systems-analysis packs (docs only)

**Files:** `reports/2026-11-25-systems-analysis-finalisation/librarian/` (as-is and to-be specs), rendered with `render_pack.py --all`.

**The use cases:**
- UC10, search and read;
- UC11–UC15, the five session purposes with no flow yet: add_project, suggest, start_pursuit, the tutoring session (`learn`) and add_capability;
- UC16, scheduled pipelines.

The initiators table lists them. Draw the as-is from the code (`standard/phases.yaml`), and the to-be as the current system hardened, following the builds-on table.

**Leave alone:** `stages.table.yaml` and `builds-on.table.yaml`, which Claude updates.

**Done when:** `render_pack.py --check --all` and `tests/test_packs.py` pass.
