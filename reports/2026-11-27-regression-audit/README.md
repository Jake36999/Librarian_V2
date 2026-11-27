# Regression audit of M0–M5 (27 November)

**Why:** the Owner asked twice that the hardening pass lose nothing the Librarian already did. No one had checked: not after the milestones, and not after the M5 acceptance run.

**What was compared:** `04acfe4`, the last commit before the implementation plan, with `3ac06bb`, the head after the M5 acceptance run. The range is 21 commits. It includes the delegated work of 26 November and one commit of another session (15b5c12).

**What was checked:**
- workflows;
- adapter layers;
- analysis granularity (reading, lenses, D/I/K, model tasks);
- process granularity (stages, recipes, dependencies, tools);
- the tool surface, refusals, routes, roles and profiles;
- tests and docs.

**Result:** two regressions were found and are fixed here.
- **The near-duplicate warning at capture was lost** for PDFs with a metadata title. It came from M5.3.
- **A policy safeguard and a role duty were dropped** in the tier-order correction of 26 November.

Nothing else was lost. Every other difference is listed below with its reason.

## How

`scripts/regression_audit.py`, added here, is the method. It is now a gate at every milestone (implementation plan §2):
- **`inventory`** imports each checkout's own source and records:
  - every registered tool (tier, effect, flags, phases, parameters, defaults, returns);
  - the refusal rules and the standard workflows, pipelines and macros;
  - every module's public functions, classes, methods with their parameters, and module-level constants;
  - API routes and model task names;
  - the batch's stages, recipes, dependencies, model stages and tools, and the roles and default profiles, by value.
- **`compare`** lists what was removed or changed between two inventories.
- **`deletions`** lists, from git, deleted tests, changed assertions, added skips, and every line removed from the docs.

Each difference was then read against its intent. Three further checks went beyond the inventories:
- **Saved definitions:** the saved workflows and pipelines in every library were validated against the new composition rules. These were Resource-Library, Parallax and Nonlinear Field Lab on G:, and ACCEPT-02 on E:. None of them has any saved workflows or pipelines.
- **Live budget ceilings:** each live library's ceiling was compared with its spend, for the per-call guard. None is near its ceiling.
- **New refusals:** every refusal my commits added to an existing module was traced to whether it can refuse a call that succeeded before.

## What is unchanged

| Area | Finding |
|---|---|
| Tools | 187 before, 201 after. None removed. No parameter removed, no new required parameter, no default changed, no return dropped |
| Refusal rules, API routes, model task names | none removed; routes identical (98) |
| Standard workflows, pipelines, macros | none removed or changed. 5 files added: `actions.yaml`, `stages.yaml`, `tickets.yaml`, `manifest.schema.json`, `pipelines/ingest-folder.yaml` |
| Batch stages | the same 9 stages in the same order. Model stages, stage tools and recipes are equal by value. Dependencies are equal by value; they were hard-coded in `batch._run` and are now read from `stages.yaml`. The folder stages' recipes now appear, with the same default `"1"`, so no completion key changes and nothing re-runs |
| Default profiles | none removed or changed; `oracle` and `repair` added |
| Adapter layers | no change at all: `adapters/` (OpenAI chat, Anthropic messages), `providers.py`, `service_adapters.py`, `service_routes.py`, `model_invocation.py`, `mcp_client.py`, `mcp_server.py`, `geo_service.py`, `websearch.py` |
| Analysis granularity | no change at all: `deep_read.py`, `lenses.py`, `lens_packs.py`, `lens_gold.py`, `dik.py`, `clerk.py`, `effort.py`, `profiles.py`, `ocr.py`, `pdf_markdown.py`, `conversions.py`, `research_grains.py`, `index.py`, `search.py`, `catalogue_navigation.py`, `model_catalog.py` |
| The vault config template | `init.py` unchanged |
| Tests | no test file or test function removed. Two assertions changed, each to the new value of an intended change (below). One skip guard added, on the new pack test, for when the packs are absent |

## The two regressions, fixed here

1. **The near-duplicate warning at capture** (`intake.ingest`, from M5.3 readable titles).
   - **What was lost:** the check compares the captured title with staged items' titles and library note names. Before M5.3 a file's title was its file name. Now a PDF's title can be its metadata title, which is not its note's name. So a second, different copy of a held file, such as `Welcome Week (1).pdf`, was no longer marked `possible_duplicate_of`.
   - **My earlier claim was wrong:** the M5.3 commit said the name-based duplicate checks were unchanged. That was true of the exact-name and same-content checks, not of this one.
   - **The fix:** it matches on the file's working title, as before, as well as on the readable title and the name.
   - **Test:** `test_ingest_service.py::test_a_similar_name_is_flagged_when_the_pdf_has_its_own_title`. It fails on `3ac06bb`.
2. **The tier-order correction dropped text** (`docs/policy/agent-roles-and-authority.md`, terminology, diagram workflows; 26 November).
   - **What was dropped:** the swap of Scribe 2 and Clerk 3 also removed a safeguard: "These are semantic roles, not instructions to swap legacy numeric configuration fields. Existing role slots, profiles, qualification records and tool gates keep their current behaviour until an explicit implementation change reconciles them." It also removed proofreading, which was a tier-2 duty, from the roles.
   - **The fix:** both are restored; proofreading is now listed with the Scribe, which is tier 2.

## Intended changes to existing behaviour

None of these removes a capability. Each is named so it can be reviewed.

| Change | Where | Effect |
|---|---|---|
| `run_workflow`, `run_pipeline` and `run_resume` are orchestrators | M5 acceptance | They run beside the writer, not inside one writer operation. Each step is still its own checked write. Before, an orchestrating step inside a workflow was refused (`ORCHESTRATION_CONTEXT`); no internal caller runs them inside a writer operation |
| Composition rules 1 and 2 | M1b, `workflows.validate` | Relaxed only: an action may sit directly in a pipeline; a workflow may hold a workflow, and a pipeline a pipeline. Cycles and a workflow holding a pipeline are refused. No saved definition in any library is affected |
| Folder routes call the `folder_*` tools | M1a, `app.py` | `App._folder_review_beside_writer` moved into `FolderService._beside_writer` unchanged: the walk outside the writer, the writes one at a time, the folder lock, the counted mutation and the no-writer path. Errors keep their codes and their 400/409 statuses |
| The Clerk/Scribe ceiling before each call | M5.3, `_background_profile_guard` | The library's own ceiling now also stops Clerk and Scribe calls outside the batch. It uses the batch's spend measure. One nuance: the incremental count keeps the cleanup price in force when each line was read, so the two counts differ only if the cleanup price is changed mid-run. No live library is near its ceiling (Resource-Library $4.74 of $19.47; Parallax $0.32 of $2.28; Nonlinear Field Lab $5.20 of $8.25; ACCEPT-02 $0.66 of $10) |
| `record_application`'s two refusals named | M2 | The same two conditions as before. The result is now `refused: APPLICATION_SOURCE_UNKNOWN` or `APPLICATION_SOURCES_REQUIRED` with the remedy, where it was `error: invalid_arguments`. A client matching on `invalid_arguments` would see the new code |
| Readable titles | M5.3 | A captured file's `title` can be its PDF's metadata title. Its name, and so the exact-name and same-content duplicate checks, are unchanged |
| The graph citation pattern allows inner spaces | M5 acceptance | It accepts what it refused before; nothing it accepted is refused |
| Report-mode checks | M1b, M4 | The stage tool guard, the acceptance entry receipt and the provenance comparison record and never refuse, unless `enforce: refuse` is set; it is not set |
| The checkpoint store's lock | M3 | A re-entrant per-file lock around read-modify-write; the rows and API are unchanged |
| Additions | M0–M5 | The `agenda` returns 4 more sections. There are 25 more rule codes, 3 more checkpoint types and the `oracle` and `repair` role slots, which are unassigned and change nothing. FOLDER_DRAFT_FAILED and GEOGRAPHER_CALL_FAILED messages now say why. The UI's folder wording is clearer, the queue button is shown for own-docs too (which the queue already accepted), and a stale-revision reload keeps the person's edits |

## The metadata specification, against the to-be step

Semantic metadata (W-REA-02) was specified on 30 September:
- **Research Pipeline §3.4:** metadata is derived from the Data and Information layers, "not invented independently by a summary writer". Facts go in typed fields with evidence and locators, and distinct concepts are kept separate.
- **Novel values:** a novel axis or category value is staged as a taxonomy candidate, and a person accepts it in Settings → Library. The per-vault Note Content Model stays authoritative.
- **§4.3 step 5** ("Derive metadata and taxonomy candidates"), and **Addendum R16** (explicit stages for metadata and category proposals).

The existing stage, `batch._metadata`, does the deterministic part:
- the literal Data facts;
- the required fields still unknown, from `readiness` against the content model;
- `metadata_proposals`, confirmed at acceptance.

The pack's `metapropose` step ("a Scribe proposes semantic content-model metadata fields from evidence; retains Unknown where insufficient") agrees with this but is less precise. It is now recorded in the implementation plan as an extension of `_metadata`, built within the 30 September constraints:
- values from the D/I records, with their ids and locators;
- the library's own content model;
- novel values staged as taxonomy candidates;
- the deterministic part kept when no model answers;
- no project-need context.

It is not an Owner decision; I was wrong to call it one.

## Not covered

- Behaviour inside functions whose signatures did not change was covered by reading every hunk with deletions, plus the added hunks in `registry`, `staging`, `tools/staging` and the runners. It is not proven exhaustively.
- **The Obsidian plugin:** its source (`obsidian/src`) is unchanged in this range. Its built `obsidian/dist`, rebuilt by the delegated work, was not compared with a fresh build.
- **The Web UI:** its source (`ui/src`: 62 lines added, 15 removed) was read through its built `app.js`, whose 15 removed lines are listed above. Its views were not driven before and after.
- Geo-Grapher's own repository is outside this audit.
- The branch's history before `04acfe4`, against `master`, is not audited here. That is a delegable task.
