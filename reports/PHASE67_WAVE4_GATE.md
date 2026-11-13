# Phase 6–7 Wave 4 gate — 2026-11-12

Owner-directed acceptance revision completed 2026-11-13; current verdict is in §12. Earlier measurements remain historical rows.

**Verdict: NOT READY for wave acceptance.** The implementation is reviewable on feature branches. Local engineering checks pass, but the model-assisted code benchmark and the qualified-helper pilot do not close the acceptance criteria. Neither branch has been merged or pushed.

## 1. Scope and source ownership

Geo Grapher: `phase67-wave4`, from main `0f12dfa`; primary implementation `a5c0ce3`. Librarian: `geo-grapher-wave4`, from committed master `c4eb76f`, in `F:/uv-data/Geo_Grapher/output/phase67-gates/lib-wave4`. The original Librarian checkout's mixed-owner changes remain untouched and uncommitted. Its survey branch remains unmerged. No bridge-firewall amendment was made.

The takeover assessment is `reports/PHASE67_WAVES1_3_TAKEOVER_ASSESSMENT.md`. Its fresh baseline was 626 backend tests and 17 browser tests, plus frontend checks.

Implemented:

- Tier ceilings, exact-budget snapshot task packets, revalidated structured upstream ports and the six-tool `lead` preset.
- Route-aware external bounds, atomic structured withholding, and access/client/library rechecks before and after MCP calls.
- An unframed Clerk contract task; bounded citation membership checks; packet/answer hash binding in receipts and the executable research-grain verifier.
- Validated task DAG dispatch through actual Clerk/delegate production paths, per-wave effort caps, verified-port forwarding, failure propagation and final snapshot rechecks.
- Directed bridge impact, trust/pin costs, reviewed-bridge conformance, per-graph citations, scoped packing and cursors.

The MCP endpoint adds explicit impact starts and theory/code roles because the plan's original signature had no way to supply them. Explicit-profile federation accepts budgets below the old 2048 floor so the 1200/1800 profiles are usable; no-profile behavior is preserved. Rulings and per-task receipts are in `.superpowers/sdd/2026-11-11-phase6-7-04-wave4-librarian/progress.md`.

MF-011 fitting remains intact. MF-030 contributes the relevant revocation/library/client slice; MF-024 contributes correlated Core-only receipts. This does not claim completion of either broader release epic.

## 2. Deterministic engineering evidence

| Check | Result |
|---|---|
| Fresh pre-wave `scripts/verify.ps1` | 626 backend / 17 browser; frontend typecheck, build, unit passed |
| Wave 4 verification before schema presentation follow-up | 642 backend / 17 browser; frontend checks passed |
| Librarian full suite before reference follow-up | 2174 passed, 2 skipped, 5 deselected (659.88 s); two subsequent additive dispatcher tests passed separately |
| Scoped real-wheel MCP smoke | Exactly 6 `lead` tools, declared 1M-window limit 125829 characters |
| No-model search → packet through installed wheel and Librarian | 5 search hits; `effort.py.of` packet 1142 tokens / 2785 characters, 1 anchor, 5 handles; expected graph and snapshot |
| Impact fixture | Code function cost 0.20; caller 1.20; pinned-transcript alternative 0.40; stale bridge excluded |
| Determinism | Impact/conformance byte-identical in two fresh processes |
| DAG/Clerk focused checks | Invalid DAGs make zero external calls; per-wave caps, cancellation, alternate server, missing anchor, stale scope, real helper allowlist, real Clerk payload and Broker/read-only expansion covered |

**Final verification:** `scripts/verify.ps1` exited 0 after concrete-schema presentation: 642 backend tests, 17 browser tests and frontend typecheck/build/unit checks passed (`output/w4-verify-inline-final.log`). The final Librarian suite exited 0: **2181 passed, 2 skipped, 5 deselected in 662.04 s**, from neutral `F:/uv-data` (`output/w4-librarian-ref-fix-full.log`).

## 3. Through-Librarian benchmarks

Each run uses a fresh temporary Librarian vault/configuration, actual `Loop`, `McpManager`, scoped stdio MCP, and an exact locally built wheel launched through `uvx`. Gate SQLite stores were backed up from read-only handles into `output/phase67-gates/wave4/`; originals were not opened for writing. Wheel refresh avoids a stale same-version cached package.

Model: `Qwen/Qwen3-Coder-480B-A35B-Instruct-Turbo`. These are declared route-window overrides testing delivery and behavior, **not proof that the model has a native 1M context window**, and not qualification for a production runtime role. The older benchmark used a different model; its 7/7 marker result is a criterion, not an equivalent repeated trial.

| Run | Questions | Fact markers | Calls | Calls/question | Wrong-graph calls | Withheld | Answered |
|---|---:|---:|---:|---:|---:|---:|---:|
| Default window, papers | 5 | 7/7 | 27 | 5.4 | 0 | 0 | 5 |
| Declared 1048576 window, papers | 5 | 6/7 | 26 | 5.2 | 0 | 0 | 5 |
| Declared 1048576 window, lead/code, first complete run | 5 | 0/5 | 57 | 11.4 | 0 | 0 | 2 |
| Lead/code after coercion repair | 5 | 0/5 | 60 | 12.0 | 0 | 0 | 0 |

The code questions have their own five-marker denominator and cannot be scored against the paper questions' seven markers. The initial code run had three `max_steps` stops. The first two paper runs took 201.7 and 184.8 seconds summed over questions; the first code run 172.8 seconds.

The missing 1M paper marker was doc:108 in the knowledge-graphs question: that document was retrieved, but the answer cited other papers. Preserve the first score; do not silently substitute a better repeat.

The code benchmark found a genuine pre-existing integration defect: Librarian coerced an external request with a local JSON Schema `$ref` into text even when the caller supplied an object. A RED oracle reproduced it. Local references now resolve before coercion; missing, external and cyclic references fail explicitly. The installed-wheel smoke confirms valid object requests work end to end. Geo Grapher also exposes concrete request schema fields to function-call clients and documents canonical packet-anchor lookup. All wire constraints are retained.

The cheap agent still constructs invalid requests, including a 4096-token request under the 1800-token forager ceiling. Do not describe the benchmark as successful merely because a deterministic client works. A separately retained final schema-presentation run is appended below.

**Final code schema run:** 0/5 markers, 0/5 final answers, 60 calls (12/question), all five stopped at `max_steps`, zero wrong-graph calls and zero withheld results. The agent now emits nested request objects, but still violates required fields and profile ceilings. All three code runs are retained separately; this is not a best-of score or a successful repair score.

## 4. Library-scoped leakage probes

29/29 completed with the declared 1M window, six paper tools per server, fresh temporary library scopes and the same exact wheel. There were 129 tool calls (4.4/probe), zero withheld results, zero wrong-graph calls, zero bundle refusals, and one mistyped graph identifier.

| Scorer category | Result |
|---|---:|
| Cross-graph leakage | 0/29 |
| Prior-knowledge leakage | 1/29 |
| Citation error / recall miss / no answer | 0/29 each |

The negative AI-paper question about Paul Warburg elicited unsupported prior knowledge despite acknowledging the corpus's absence. Scope enforcement held; the model's answer discipline did not. Do not call this zero overall leakage or pool it with older trials to advertise a new statistical bound.

## 5. Qualified six-task pilot — blocked

The owner selected Resource-Library. Its configured canonical `research_helper` route is `google/gemma-4-26B-A4B-it`; Clerk is `Qwen/Qwen3.5-397B-A17B`. Offline inspection found no qualification runs for either role, and the recorded Core was not alive. The guide requires role-specific screened evidence. The owner was asked to qualify the routes or defer the live pilot; no approval to bypass qualification was inferred from the guide.

Therefore the real four-Clerk / one-tier-2 / one-tier-1 pilot has **not run**. Waves, real Clerk verification rate, stale count, live wall time and live cost are unmeasured. Fixture providers and development workers are not substitutes. Production paths and qualification guards are retained and tested.

## 6. First attempts, fixes and budget

Retained artifacts under `output/phase67-gates/wave4/` include the benchmark/probe JSON, failed/first complete code runs, exact wheel builds and packet smoke. Logs under `output/w4-*` preserve first failures.

- The first code harness attempt failed because result accounting knew only paper labels. Fixed; its log was retained. Incorrect graph-label accounting was separately corrected with the original metrics retained; graph labels accepted by the router are not cross-graph calls.
- A complete Librarian run found the missing executable grain registration. Fixed with packet/answer digest binding and a substitution regression.
- The nested-worktree CLI failures came from parent-vault discovery and its stale lease. Neutral-directory runs passed without weakening lease checks.
- Initial benchmark accounting retained four byte-bound retry reserves per logical chat and reached the $10 ceiling. Completed receipts were reconciled using metered prompt counts while still retaining both possible full retry outputs; original charges remain recorded. Interrupted code/probe runs resumed completed cases without replacing their first results. New runs reserve and settle **each HTTP attempt** via the delegation script's ledger functions. No pool increase or out-of-pool spend.
- Model drafts were proposals. Packet, DAG and impact drafts needed substantial lead replacement; the citation module was partially retained and hardened. Qwen reviews mostly misread the specification; GLM's review exhausted its output without a parseable verdict. Findings were adjudicated rather than applied. The final reference-fix review reported no concrete finding.

Budget figures are stored planning-rate estimates, not invoice amounts. Final totals and commit references are appended below.

## 7. Acceptance still open

The strict paper threshold (7/7 in the larger window) was missed; the cheap code-agent benchmark is unsuccessful; native 1M route capability is not established; the qualified real-helper pilot is blocked. The bridge-firewall owner decision and earlier latency/survey items remain carried forward. Feature branches stay unmerged and unpushed until acceptance is resolved.

## 8. Final reviewable state

| Repository | Implementation commits |
|---|---|
| Geo Grapher `phase67-wave4` | `a5c0ce3` packet/analysis implementation; `1b9f3c0` concrete MCP request schemas |
| Librarian `geo-grapher-wave4` | `6c1d9df` route bounds; `e0855c3` Clerk/checks; `5eb6ca0` DAG dispatch; `0c559f8` reference coercion |

Final wheel SHA256: `448b4c80322e3f360be6a78d5e00bb0479c2bc0b35db9cecf5ada0bf82a4bf18`. Before-inline wheel retained separately. `reports/PHASE67_WAVE4_GATE.json` contains compact measurements and the exact packet-smoke snapshot identity.

The approved pool opened at $0.491624 and finishes at approximately **$3.81 committed of $10**. Benchmark runs account for $3.160513 of conservative ledger charges, including retained retry allowances; their observed API usage at stored planning rates estimates **$0.953234**, including interrupted and repeated runs. These figures are distinct and are not invoice claims. Remaining model-worker/reviewer costs are in the delegation receipts. No pool cap was increased.

Final schema follow-up review: three proposed defects were rejected after source checks (correct pointer decoding; a quoted deleted line; allOf retaining sibling constraints). An escaped-pointer smoke passed and all eight generated concrete request schemas pass JSON Schema validation with no remaining references. No concrete review finding remains unadjudicated.

All local implementation and evidence work is committed on the feature branches. The next acceptance work is a capable lead-route/code-tool pilot, disposition of the 6/7 paper result and prior-knowledge failure, and the six-task pilot after actual Resource-Library role qualification. None is represented as already passed.

## 9. Owner-directed acceptance revision — 2026-11-12

The earlier rows and verdicts above are historical first results. The owner identified the code-tool interface as a product defect: agents were required to construct the internal wire protocol. The new MCP front door accepts flat calls, fills protocol fields server-side, clamps agent budgets and reports actionable errors. Strict `{graph_id,request}` remains a separate, strictly validated form. No branch may be merged without the owner's approval, even when automated gates pass.

### Code re-run: criterion registered BEFORE the run (§3.3)

Freeze the same five CODE_BENCH questions and markers, model `Qwen/Qwen3-Coder-480B-A35B-Instruct-Turbo`, declared route window 1048576, library-scoped `lead` preset and 12-step limit. This run must have **at least 4/5 markers, zero withheld results, zero wrong-graph calls, and at most 8 tool calls/question on average**. Every condition is required. Each call records tool name, arguments (600 characters), error code/message (300 characters), success and per-question top errors. No first file is overwritten and no best-of score is taken.

First output: `output/phase67-gates/wave4/code-frontdoor-run1.json`. If it fails, permit only **one** further engineering iteration, decided from its per-call errors, and **one** additional run saved as `code-frontdoor-run2.json`. A second failure is escalated to the owner. These rules are written before either run.

### Paper protocol and leakage decisions (§3.4, §3.6)

The owner selected option (a): evaluate the retained 1M paper run once as **retrieval 7/7 and answer at least 6/7**, with separate scores. Use exact document IDs from `retrieved['ai-research-papers']` for retrieval and retain the original answer-marker score. Record the resulting protocol row below; do not replace the original 6/7 row or run a best-of study.

The leakage gate **PASSES its stated criterion: zero cross-graph leaks (0/29)**. The separate prior-knowledge result remains 1/29. The Warburg abstention/answer-contract remedy belongs to wave 5, not this acceptance criterion.

### Registered front-door run 1 and the single allowed iteration

Run 1: **3/5 markers, 0 withheld, 0 wrong-graph calls, 23 tool calls / 5 questions = 4.6 average, 0 tool errors**. All questions received answers. This is **FAIL** solely on markers, retained in `code-frontdoor-run1.json`.

Its per-call logs show the missed helper-tool and MCP-bound questions fetched unrelated code, without errors. The agent adapter had selected symbol-only lexical search for natural-language questions, excluding original documentary evidence. The one permitted iteration switches the default to the existing `hybrid` retrieval mode and returns up to eight ranked hits (still bounded), without corpus-specific query rewrites or marker hints. A RED oracle using a docstring-only query demonstrates the gap. Run 2 keeps the frozen model, questions, markers and pass mark above. No third re-run is authorized.

| Registered code run | Markers | Calls/question | Withheld | Wrong-graph calls | Verdict |
|---|---:|---:|---:|---:|---|
| Original first complete code run | 0/5 | 11.4 | 0 | 0 | FAIL; original file retained |
| After reference coercion repair | 0/5 | 12.0 | 0 | 0 | FAIL; original file retained |
| After concrete schema presentation | 0/5 | 12.0 | 0 | 0 | FAIL; original file retained |
| Flat front door, run 1 | 3/5 | 4.6 | 0 | 0 | FAIL (markers) |
| Hybrid default, run 2 | 2/5 | 7.2 | 0 | 1 | FAIL; escalated to owner, no third attempt |

The first run had zero tool errors and all five answers, proving the protocol barrier was removed. Remaining retrieval/answer quality still fails the frozen product gate; the second run also made a rejected wrong-graph request. First files remain separate and all new results have per-call diagnostics.

Run 2 has seven rejected calls: four unscoped aliases, two entity IDs absent from the graph, and one mistyped/unknown graph ID. These are preserved in its per-call records and top-error summaries. The next code-product investigation should inspect discovery/ranking and the coexistence of wire aliases with the front door's canonical handles; no third model attempt was made.

### Paper option (a), applied once

`scripts/score_paper_protocol.py` evaluated the retained 1M run: **retrieval 7/7, answer 6/7 — PASS** under the owner's chosen criterion. The original answer-only 6/7 row remains above. Evidence: `papers-option-a-verified.json`. The `85` marker is the token-reduction quantity supported by ChatP&ID (`doc:115`), and `234` is the workflow count supported by ESW (`doc:2`); neither is a document ID. Their source abstracts and the support map are retained in the score file. An initial incorrect all-markers-as-document-IDs calculation is archived separately as rejected accounting, not a model run.

## 10. Resource-Library qualification — exact owner steps (§3.5)

**STOP at the live pilot.** These instructions are prepared, not executed by Codex. Continue only when the owner has qualified the exact roles/routes and asked for the six-task pilot. Application QA below is independent and continues. Do not substitute a different Clerk if Qwen times out.

Run these PowerShell commands as the owner:

```powershell
$libPy = 'D:/Librarian_V2/.venv/Scripts/python.exe'
$env:PYTHONPATH = 'D:/Librarian_V2/src'
& $libPy -m resource_librarian host status
& $libPy -m resource_librarian host start --vault 'D:/Resource-Library/.librarian-app' --open
```

The Host should return `status: running` and open the library. If startup instead reports a **stopped/stale** vault lease, first verify the reported PID is not alive with `Get-Process -Id <reported-PID> -ErrorAction SilentlyContinue`; do not take over a live process. Only after confirming the old Core is stopped, the explicit recovery command is:

```powershell
& $libPy -m resource_librarian --vault 'D:/Resource-Library/.librarian-app' app --takeover --port 0 --open
```

In Models → qualification, confirm host `preset-deepinfra` and the role-specific canonical bindings: `research_helper` → `google/gemma-4-26B-A4B-it`; `clerk` → `Qwen/Qwen3.5-397B-A17B`. Lead qualification does not cover either role. The equivalent exact commands below call the running Core, keeping its private token inside the helper process:

```powershell
$qualify = 'F:/uv-data/Geo_Grapher/scripts/qualify_resource_library.py'
# Read-only plans: inspect the estimate before approving any paid probe.
& $libPy $qualify --role research_helper --level L1
& $libPy $qualify --role clerk --level L1
# Free deterministic checks, then the owner's explicit paid approvals.
& $libPy $qualify --role research_helper --level L0 --run
& $libPy $qualify --role clerk --level L0 --run
& $libPy $qualify --role research_helper --level L1 --run --confirm-spend
& $libPy $qualify --role clerk --level L1 --run --confirm-spend
& $libPy $qualify --role research_helper --status
& $libPy $qualify --role clerk --status
```

Each L1 performs a real tool proposal **and continuation**, and must produce a role-specific `pass`, a matching observed model, and `qualification.status: screened` with `fresh: true`. Expected evidence is in `C:/Users/jakem/.config/resource-librarian/model-evaluations.json` (`runs` and `qualifications` for both roles), the vault's `.librarian/checkpoints.json` (approved evaluation-spend decisions), and the private Core discovery record under `C:/Users/jakem/.config/resource-librarian/cores/`. Save public command output if desired; never share the Core token or API keys.

Planning estimate from the maintained guide: about **$0.005 per role, approximately $0.01 total** for the small L1 probes; L0 is free. The live plan's estimate is authoritative and should be checked before the owner confirms. A timeout may retain an uncertain charge. Qwen3.5-397B timed out in wave 2: if it times out here, retain that failure and report it; **do not change models** without owner approval. Leave the Core running and tell Codex both role statuses to resume the four-Clerk / tier-2 / tier-1 ToolSet pilot.

## 11. Application testing (§4)

Automated installed-package preset, real-store browser, and latency results follow below. All use disposable copies, not the live project catalogs.

The first-result rows below are historical and deliberately retained. Review-2 fixes and subsequent results are in §§13–14; the owner workspace command below has been updated to the new UI wheel and catalog.

### Owner's 20-minute exploratory checklist

- [ ] 0–2 min: start the workspace on the disposable QA catalog using the command recorded with the application results; open its loopback URL.
- [ ] 2–6 min: switch ToolSet/Librarian graphs, inspect grouping choices, open a block and inspect labels and role badges. Check whether directed QI is actually available in the spatial UI; do not count an API-only certificate as rendered groups.
- [ ] 6–10 min: Add folder → browse a scratch project → preview → untick one partition → ingest → observe the completed job and new graph.
- [ ] 10–13 min: box-select a small source region → prune into a new graph → verify the source graph's snapshot is unchanged.
- [ ] 13–16 min: review two bridge candidates; accept a justified one with a rationale, reject an unrelated one; check bridge state through `list_bridges`.
- [ ] 16–20 min: after role/lead readiness is established, ask one code question in Resource-Library with the production lead and six-tool `lead` preset. Inspect the cited `graph-label/entity:` handles and open their source in the UI. Record actual success/failure; do not substitute the development benchmark route.

The prior-knowledge abstention remedy (Warburg negative probe) is a wave 5 backlog item: when the corpus lacks the subject, abstain rather than append prior knowledge; cover this in a Librarian answer-contract test.

### Front-door defaults and review

The agent adapter uses schema 1.1, the catalog's current snapshot, a deterministic digest request ID, the connection profile ceiling, canonical identities and null cursor. Search defaults to hybrid mode, eight results and no kind/repository restriction. Context defaults to atomic grouping, radius one, no pins and QI disabled; enabled QI defaults to tree-balls with diameter two. Content defaults to the entity's original source range (documentation for fragments), radius zero. Dependants default to incoming depth one; architecture checking returns `not_configured` when no rule model exists. Flat and strict forms may not be mixed. Over-ceiling flat budgets report their clamp; strict requests retain strict rejection. Error examples are minimal argument templates; replace the bracketed IDs with IDs from discovery/search.

The DeepInfra review (`w4-frontdoor-direction-review`, Qwen3-Coder) cost $0.0021204 at stored rates. Its proposed minimum-budget defect is incorrect: `<256` already accepts 256. Different per-operation defaults do not violate profile ceilings. A missing repository root requires a malformed code snapshot; ingestion supplies it, and the no-model paper path does not index roots. The 0.85 packing reduction is implementation headroom, not an acceptance defect. No proposed finding warrants another model benchmark. Existing real-store cap failures remain open independently.

Code run 1 cost $0.0881403 across 28 metered HTTP attempts; run 2 cost $0.1760749 across 39. These are API-usage estimates at stored planning rates, not invoices. After both runs and review, the delegation ledger records **$4.07390895 committed of the approved $10 pool**. No further paid benchmark or route qualification was run.

### Installed-wheel preset smoke

`scripts/qa_mcp_presets.py` exercises the exact advertised six-tool sets through `uvx`, without a model, with a 7,500-character response ceiling. The script removes `PYTHONPATH` from the child environment, checks exact tool names, calls every tool, and makes one deliberate bad call per preset. Code schemas are also checked against 1,200 characters in the front-door oracle tests.

| Preset | Calls passing success/error and character checks | Result |
|---|---:|---|
| papers | 7/7 | PASS |
| code | 5/7 | FAIL |
| lead | 6/7 | FAIL |
| cross | 6/7 | FAIL |

First evidence: `output/phase67-gates/wave4/preset-smoke-first.json`. Final-wheel confirmation on a separate catalog: `preset-smoke-isolated.json`. Both expose the same four failures: minimal `find_dependants` and two preset instances of `get_architecture_context` return `BUDGET_TOO_SMALL` while trying to fit the full response into 7,500 characters; `federated_search` succeeds but returns **20,098 characters**, breaching that ceiling. All four deliberate bad calls return actionable examples. Minimal architecture and dependant calls pass on the small oracle fixture; the real-store failures are additional product gaps, not a claim that application QA passed.

The intermediate `preset-smoke-final-wheel.json` overlapped the browser on the same disposable catalog and is retained as contaminated. The final confirmation uses `application-smoke-isolated/catalog.sqlite`; the browser uses a different copy. No original catalog or source tree was modified.

Reproduce the final no-model smoke from the repository root:

```powershell
output/wheel-env/Scripts/python.exe scripts/qa_mcp_presets.py `
  --catalog output/phase67-gates/wave4/application-smoke-isolated/catalog.sqlite `
  --wheel output/phase67-gates/wave4/frontdoor-final-dist/geo_grapher-0.1.1-py3-none-any.whl `
  --out output/phase67-gates/wave4/preset-smoke-owner-new.json
```

Result paths must be new: the scripts refuse to overwrite first evidence. Final wheel SHA256: `dba2434547f393e1cbc133e19ae0b645ee45512fd60f6d726f8617b516ca8cc9`.

### Owner workspace command

The 20-minute checklist above starts with this installed-wheel command on the disposable real-store catalog, after automated QA has stopped:

```powershell
uvx --refresh-package geo-grapher --from F:/uv-data/Geo_Grapher/output/phase67-gates/wave4/continuation-dist2/geo_grapher-0.1.1-py3-none-any.whl geographer serve-graphs `
  --catalog D:/Librarian_V2/tmp/geo-grapher-wave4-continuation-stores/catalog.sqlite `
  --browse-root D:/Librarian_V2/tmp/geo-grapher-wave4-continuation-stores/browse `
  --transport http --port 8790
```

Open `http://127.0.0.1:8790/`. The scratch folder is `browse/project`. For a bridge decision with actual overlapping code, check only librarian-v2 and librarian-survey-worktree; ToolSet/librarian-v2 returned no pending candidates in the recorded probe. The review-2 wheel now exposes Off / Helper balls / Directed in the atomic spatial view; the owner should exercise Directed, expand a block, and return to Off. Keep the Core qualification commands in §10 separate from this workspace command. The manual checklist is prepared for the owner; Codex has not claimed a completed hands-on owner pass.

### Real-store browser evidence — resumed 2026-11-13

The final browser harness launches the installed wheel through `uvx`, strips source `PYTHONPATH`, and uses disposable gate-store copies with reconstructed snapshot source bytes. It asserts empty page-error/console-error lists and deletes created graphs and new proposal rows in `afterAll`.

| Browser attempt | Passed / failed | Interpretation |
|---|---|---|
| `results-first.json` | 0 / 5 | Retained harness defects: cleanup request format, ambiguous locator and hidden menu controls; also exposed missing QI control |
| `results-harness-corrected.json` | 2 / 3 | Retained contaminated run: concurrent smoke shared its writable disposable stores and caused SQLite locks |
| `results-isolated.json` | 2 / 3 | Separate stores; 20-second waits expired for prune/candidates; add-folder and path refusals passed |
| `results-wheel.json` | 3 / 2 | Installed wheel: prune (21.5 s), folder ingestion and path refusals passed; QI control missing; first code-pair review did not complete |
| `results-bridge-diagnostic.json` | 0 / 1 | Explicit pair/readiness/response checks: ToolSet/librarian-v2 returned no pending candidates; no artificial candidate inserted |
| `results-bridge-real-pair.json` | 1 / 0 | Related real librarian-v2/librarian-survey-worktree copies: candidate reviewed and rejected with rationale (11.6 s) |

All result JSON files are under `output/qa-real/`, with matching traces/screenshots in their `test-results-*` directories. No best-of full-suite score is claimed. The completed workflow evidence is: prune creates a derived graph and preserves ToolSet's source snapshot; add-folder previews two partitions, deselects one and creates exactly one graph; `..`, UNC, a real junction and an existing outside absolute directory all return 403; bridge review decides an actual related-code candidate. The required **directed-QI spatial workflow FAILS** because the workspace exposes no directed-QI algorithm control or rendered QI groups. An API certificate does not satisfy that UI requirement.

Offline audit `output/phase67-gates/wave4/application-cleanup-audit.json` confirms every application copy retains all baseline snapshot IDs, has no extra graph rows and has zero proposal rows. The original stores were only used through read-only backup handles. No browser console/page error was reported in the successful final workflow tests.

For a fresh browser run, first prepare a new output directory with `scripts/qa_real_store_prepare.py --catalog output/phase67-gates/wave4/catalog.sqlite --out <new-copy>`, then set `QA_REAL_ROOT` to that directory, `QA_REAL_PORT` to a free loopback port, `QA_REAL_OUTPUT` and `QA_REAL_REPORT` to new evidence paths, and run `npx playwright test --config playwright.real.config.cjs`. The QI test intentionally remains a failing acceptance assertion until the UI exists.

### Cold latency (C14)

`scripts/qa_wave4_latency.py` uses a new installed-wheel Python process per sample, the first function by canonical ID, atomic grouping, radius two, QI diameter two and an 8,192-token strict request. Timing covers `GraphRouter.query`, including cold service/snapshot hydration; interpreter startup and read-only focus selection are excluded. Existing on-disk analysis artifacts are retained. No sample is discarded. The first run overlapped other QA; the second ran after the suites and browsers stopped, on its own store copy.

| Run / graph | Tree-balls seconds (three cold processes) | Directed seconds (three cold processes) | Criterion |
|---|---|---|---|
| First / ToolSet | 3.726, 3.412, 3.395 | 2.755, 2.962, 2.804 | FAIL tree-balls <3.0 s |
| First / librarian-v2 | 11.194, 10.888, 10.953 | 6.923, 6.927, 6.607 | Recorded, not gated |
| Quiet / ToolSet | 5.646, 3.149, 3.130 | 2.897, 2.504, 2.514 | FAIL tree-balls <3.0 s |
| Quiet / librarian-v2 | 13.981, 9.097, 9.133 | 7.409, 6.107, 6.091 | Recorded, not gated |

All queries succeeded. C14 requires both algorithms below 3 seconds on ToolSet, so it **FAILS** even though directed QI passes. Raw evidence: `latency-application-first.json` and `latency-application-quiet.json` under `output/phase67-gates/wave4/`. These measurements do not replace earlier wave latency rows.

Reproduce with the installed wheel's Python and a new result path:

```powershell
uvx --refresh-package geo-grapher --from output/phase67-gates/wave4/frontdoor-final-dist/geo_grapher-0.1.1-py3-none-any.whl python scripts/qa_wave4_latency.py `
  --catalog output/phase67-gates/wave4/application-smoke-isolated/catalog.sqlite `
  --out output/phase67-gates/wave4/latency-owner-new.json
```

## 12. Current verdict — 2026-11-13

**NOT READY after local continuation.** The new candidate passes C14, installed-wheel presets, real-store browser and full Geo/Librarian verification (§15). Local search fixes address inflection, missing comment-block support and rank displacement during packing. The failed registered code cycle remains **5/15**; no new model cycle has validated this changed product. Core remains stopped, so role qualification and the six-task pilot remain pending. Neither branch is merged or pushed. §16 records a concrete proposed cycle awaiting fresh owner authorisation.

### Review-2 verdict — retained

**NOT READY after review 2. Neither branch is merged or pushed.** The registered three-run code cycle fails: **1/5, 1/5, 3/5 = 5/15**, against each ≥3/5 and aggregate ≥12/15. All 78 tool calls succeeded; wrong-graph and withheld counts are zero; average 5.2 calls/question. No fourth run was made. The remaining code-discovery and answer failures are escalated with per-call evidence in §13.

The cap, caching, constant extraction and identifier fixes are implemented. Installed-wheel preset checks now pass 28/28. Directed-QI controls, certificates, rendered groups and expansion are implemented; the final real-store browser run passes all five scenarios. Full Geo and Librarian verification pass. **Current-store C14 still FAILS**, despite the export-scan cache improvement and earlier old-store pass; all final cold samples are retained in §14. Paper option (a) and cross-graph leakage still pass under their original criteria.

The six-task pilot remains blocked on the owner's exact Resource-Library helper and Clerk qualification and a running Core; §10 gives the commands. The production-lead question is non-gating and also waits for route readiness. The owner's 20-minute checklist and W3-5 bridge-firewall decision remain outstanding. No merge approval is requested while acceptance remains open.

### Historical assessment before review 2 — retained

**NOT READY. Neither branch is merged or pushed.** The owner-directed work and application assessment are complete to the requested stop point; acceptance is not complete.

- Code front door and diagnosable harness are implemented; all five code runs remain separate. The two allowed re-runs fail the preregistered product gate. Escalated; no third run.
- Paper option (a) **PASS**: retrieval 7/7, answer 6/7. Leakage criterion **PASS**: cross-graph 0/29. Prior-knowledge 1/29 remains a wave 5 item.
- Installed-wheel preset QA **FAIL** on real-store response fitting/federation caps. Directed-QI spatial UI **FAIL**. ToolSet C14 **FAIL** for tree-balls. Prune, selected-partition ingestion, picker refusals and a related-code bridge decision have successful real-store browser evidence.
- Resource-Library qualification commands, evidence locations and cost are in §10. The six-task pilot is **BLOCKED on owner qualification and a running Core**, and has not been executed or replaced with other routes.
- Final `scripts/verify.ps1` exited 0: full backend suite, frontend typecheck/build/unit and 17 browser tests (`output/w4-direction-verify-final.log`). Four front-door oracle tests and the related catalog/cross-graph suite passed 45 tests (`output/w4-direction-focused-final.log`). Full Librarian suite: **2,181 passed, 2 skipped, 5 deselected in 714.18 s** (`output/w4-direction-librarian-full.log`). Only QA harness/report files changed after that final product verification.

Remaining acceptance work is concrete: improve code discovery/handle usability under the frozen gate; fit minimal real-store results and enforce federation character caps; expose directed QI in the spatial workspace; restore the tree-balls cold-latency target; and run the six-task pilot after the owner's exact Resource-Library roles are qualified. The owner must approve any eventual merge of either branch. The 20-minute manual checklist is prepared above and remains for the owner to perform.

Reviewable implementation/QA commit: Geo Grapher `4498b08` on `phase67-wave4`. This revision's report and machine evidence summary are also mirrored onto Librarian's `geo-grapher-wave4` worktree; no new Librarian production code was changed in this revision. Original result files remain in the workspace paths referenced above.

## 13. Second owner-directed cycle — registered 2026-11-13 BEFORE execution

The owner explicitly authorises a new cycle under `PHASE67_WAVE4_REVIEW_2.md` §3, after cap fixes, latency caching, constants and canonical-identifier changes. The previous iteration limit and all prior scores remain historical; none is overwritten.

Freeze the same five CODE_BENCH questions and five markers, model `Qwen/Qwen3-Coder-480B-A35B-Instruct-Turbo`, declared 1,048,576-token window, library-scoped `lead` preset, and 12-step limit. Run **exactly three independent runs**, each with fresh temporary library state, using one unchanged wheel and the same re-ingested source snapshot for all three. No tuning between runs and no best-of selection.

Acceptance requires **each run at least 3/5 markers AND aggregate at least 12/15**, **zero withheld results**, **zero wrong-graph calls**, and **at most eight tool calls/question on average across all 15 questions**. Every condition is required. Per-call names, bounded arguments, errors, success and per-question top errors remain enabled.

New result paths are `output/phase67-gates/wave4/code-review2-cycle-run1.json`, `code-review2-cycle-run2.json` and `code-review2-cycle-run3.json`. Preserve every first attempt and report all three rows, then evaluate the cycle once. If it fails, stop model re-runs and escalate with the per-call diagnosis. Estimated cycle cost is approximately $0.50, charged to the existing $10 `geo-grapher` pool; retries remain charged to that pool. Record actual metered costs after each run. No extra benchmark cycle is implied by this authorisation.

One production-lead question is explicitly **non-gating** and waits for that exact Resource-Library route to be qualified. Role qualification and the six-task pilot still wait for the owner; no silent route substitution or branch merge is authorised.

### Engineering completed before the cycle

Implementation commit `16a0c59` fixes the cap, export-cache, constant and identifier issues. Two RED cap oracles now pass, including whole-envelope federation accounting and explicit flat degradation down to a focus-only answer. Strict wire queries retain their contract; every MCP response has a final character-cap guard. The installed-wheel preset smoke passed 28/28 on the real-store copies (`preset-smoke-review2-caps-first.json`, then `preset-smoke-review2-canonical.json`); a final check of the frozen wheel is retained separately.

The DeepInfra export-cache draft (`20261113T010241-e0e2b475`, DeepSeek-V4-Pro, $0.0160628) was partially accepted and hardened: retain source encoding, preserve augmented assignments and continue scanning after dynamic declarations. Stage 3 persists the source-only export analysis; older snapshots compute it once in their service context. It is filter-independent; applying protected paths to the selected vertices still respects each filter. CProfile artifacts are `review2-latency-before.pstats` and `review2-latency-after.pstats`; `contract_helpers` cumulative time fell from 0.904 to 0.149 s (instrumented whole-query times 5.395 and 6.448 s, both retained). The separate quiet, unprofiled C14 run passes: ToolSet tree-balls **2.908, 2.859, 2.870 s**, directed **2.650, 2.655, 2.641 s** (`latency-review2-cache-first.json`). No warm sample is substituted for a cold one.

Constants now have exact assignment spans, file parents, documentary incidences, source-value AST fingerprints and conservative static reads. The `constant` enum member already existed in both declaration files; the v1.1 producer now emits it, its generated schema digest was refreshed, and v1.0 presents it as `fragment` without modifying the frozen 1.0 files. Exact short constant names receive the existing exact-symbol priority. Non-callable class slots continue to mask inherited methods; verification caught and fixed that regression before any paid cycle run.

The original librarian-v2 copy has 27,953 entities; the new copy has 28,809 (+3.06%), including 968 constants. One baseline ingest took 54.872 s and the first constant-enabled ingest took 63.189 s (+15.16%, indicative single passes; the latter overlapped verification). The subsequent non-callable-mask correction was re-ingested separately and retained in `review2-ingest-callmask-fixed.json`. Known JavaScript optional-parser coverage is unchanged and recorded in those reports. `qa_constant_inventory.py` confirms the three reviewed constants rank first and return their original source; constants remain outside helper blocks. A first diagnostic mistakenly required a cluster ID even for entities outside the selected static graph; that rejected accounting check is retained in its log, then corrected to test non-contraction.

The wave-2 six-edit fixture was reconstructed from pinned commit `45d37319d0b221839aa76819f8deca45467e2d15` with preserved CRLF, since the old temporary source copies are not present. Baseline-wheel and new-wheel re-ingests both produce **MISSING 11 and UNKNOWN 7,885**, and all six named target tiers agree. The new extractor adds 108 IDENTICAL constant records. These reconstructed results are separate from the original wave-2 rows (`review2-drift-baseline/result.json`, `review2-drift-constants/result.json`). The constant-value oracle separately confirms BODY_REFACTOR; the existing CONTROL_GUARD outcome matrix and complete drift suite pass.

Flat MCP code responses expose canonical entity IDs and citation handles, with no view-local aliases; federation uses the same projection. Labels are shown first in discovery and recommended in the schemas/instructions. Legacy alias recovery is a deterministic bounded LRU scoped by MCP connection, graph and snapshot; ambiguity returns real canonical choices and a valid example. Strict calls keep their aliases.

Pre-cycle verification: full Geo verify **PASS: 657 backend, 17 browser, frontend typecheck/build/unit**, `output/w4-review2-verify-prebench5.log`; Librarian **2,181 passed, 2 skipped, 5 deselected in 718.88 s**, `output/w4-review2-librarian-prebench.log`. Earlier failed/superseded verification logs are retained: stale generated digest, expanded identifier checks, and the non-callable-slot regression were resolved before this cycle. Qwen's separate review (`20261113T011802-c35eb15d`, $0.0035787) proposed four findings, all rejected after checks: it quoted a deleted line, missed recursive canonical conversion, missed the explicit lowest-utility selection, and requested literal folding beyond the specified extraction contract.

**Frozen benchmark wheel:** `review2-prebench-dist5/geo_grapher-0.1.1-py3-none-any.whl`, SHA256 `70db1c61b785625268c629c5f5e3dec672a3a8ee4c49d4d8be7e93baa523e396`. **Frozen librarian-v2 snapshot:** `snapshot:33ba9c619765ea532d2e91be5089f6348631cb1fb0d6c9b25fd9a83562d1c98a`, graph label `librarian-v2`. These are recorded before any of the three paid runs. The production-lead readiness check found model `ByteDance/Seed-2.0-mini`, host `preset-deepinfra`, **Core not running**; the non-gating question and real pilot remain unexecuted.

Registered review-2 run 1: **1/5**, 4.6 calls/question, 0 wrong-graph, 0 withheld, 0 tool errors; metered planning-rate cost **$0.0997139** across 28 HTTP attempts. First file: `code-review2-cycle-run1.json`.

Registered review-2 run 2: **1/5**, 5.8 calls/question, 0 wrong-graph, 0 withheld, 0 tool errors; metered planning-rate cost **$0.1509306** across 33 HTTP attempts. First file: `code-review2-cycle-run2.json`.

Registered review-2 run 3: **3/5**, 5.2 calls/question, 0 wrong-graph, 0 withheld, 0 tool errors; metered planning-rate cost **$0.1308777** across 31 HTTP attempts. First file: `code-review2-cycle-run3.json`.

Three-run cycle verdict: **FAIL — escalate; no extra model run**, 5/15 markers; 5.20 calls/question across all 15 questions. All three rows above are retained.

### Cycle diagnosis and escalation

The cycle cost **$0.3815222** at stored planning rates, including metered retries; each run has a separate `-cost.json` receipt. No criteria, questions, markers, model, wheel or snapshot changed between runs. Preregistration commit `4522115` preceded the three calls. This is a failed product gate despite protocol success, not evidence that the model is weak.

`code-review2-cycle-diagnosis.json` retains each question's search arguments and selected canonical source spans. The HELPER_TOOLS question misses all three times: natural-language search selects `Broker.set_tool`, rather than the indexed constant. The DEFAULT_CONTEXT_TOKENS question also misses all three: searches select loop-context helpers and other context constants. MAX_EXTERNAL_RESULT succeeds in all three runs. Exact-name lookup of all three constants passes the separate no-model oracle; natural-language discovery remains a product gap. `lead_agents` and `run_one` each appear in only one run's final answer. Some selected entity spans contain those markers, but span membership alone does not establish that the relevant lines were delivered in the bounded content page. Pagination, content selection and answer citation need further investigation under a separately authorised plan. Code scores keep their frozen final-answer marker criterion; paper option (a) is not retroactively applied to them.

## 14. Review-2 application completion and owner stop point

### Directed QI and real-store browser

The atomic spatial toolbar now offers Off, Helper balls and Directed. Other grouping or relationship modes disable it with an explanation. The additive v1.1 frame request carries QI options; its response carries the existing certificate. Directed mode shows the block count and **reachability preserved (existential)**. QI nodes render as enclosures with expandable membership. Expansion uses separate transient pins; switching Off restores the original atomic partition. Multi-graph frame requests carry the same selection. Frozen v1.0 declarations remain unchanged.

Real-store QA exposed a filtered-partition affinity bug: the geometry path projected excluded test/vendor endpoints into a QI partition that did not contain them. The QI geometry now uses the certificate's filter. A regression fixture includes excluded test code and sphere-affinity layout; the two new viewport-QI tests and related 15-test viewport/affinity selection pass.

All following rows are retained separately under `output/qa-real/`:

| Review-2 browser attempt | Passed / failed | Interpretation |
|---|---:|---|
| `results-review2-first.json` | 3 / 2 | Exposed QI affinity product defect and prune harness selection/wait defect |
| second attempt, partial traces | aborted | F: filled; server/trace output stopped; no valid completed result JSON |
| `results-review2-after-recovery.json` | 4 / 1 | QI passed; bridge harness still selected the graph created by prune |
| `results-review2-final.json` | **5 / 0** | All scenarios pass on the same cleaned disposable real-store copy |

The final installed-wheel pass used `review2-ui-dist2/geo_grapher-0.1.1-py3-none-any.whl` and `review2-browser-first/catalog.sqlite`, prepared from the new constant-enabled snapshots. Directed QI rendered more than one block, expanded a real group, restored the atomic partition on Off, and exercised Helper balls (46.8 s, within the unchanged 120-second scenario timeout). Prune preserved the source snapshot and created a derived graph (19.9 s); bridge review rejected an actual related-code candidate with a rationale (6.5 s); add-folder deselected one of two preview partitions and created one graph (2.1 s); parent traversal, UNC, junction and outside absolute paths were refused. Successful scenarios asserted no browser page or console errors. Screenshot: `output/qa-real/review2-directed-final.png`. The owner's hands-on checklist remains unperformed.

### Evidence preservation and storage recovery

The second browser attempt exhausted F: space. Redundant databases from three older disposable QA copies (`application-r1`, `application-browser-isolated`, `application-bridge-real-pair`) were moved to `E:/Librarian research/Geo_Grapher-wave4-QA-archive/`, with SHA256 before/after checks and manifests. Their old catalog database locators were updated to the archive, so historical copies remain usable. `output/phase67-gates/wave4/qa-archive-locations.json` records the mapping. Raw results, traces, source copies, original gate stores, the frozen benchmark catalog and wheels were retained. About 5.2 GB was recovered. Geo's final temporary directory used E:. Librarian's initial E: run was stopped at 36% because of hard-disk temporary-file latency; an attempted D: root directory was denied and that short fallback run was stopped too. Both partial logs remain. The unchanged full Librarian suite was restarted using a writable task directory under `D:/Librarian_V2/tmp/` on the SSD; no Librarian production source was modified.

### Final verification

Final Geo `scripts/verify.ps1` **PASS**, exit 0: **659 backend tests**, frontend typecheck/build, **16 frontend unit tests**, and **17 browser tests**. Evidence: `output/w4-review2-verify-final.log`. The backend took 1,587.43 s using E: temporary storage; this is verification runtime, not an application latency measurement. Product/UI commit: `2c042f0`.

The final UI wheel's no-model preset smoke **PASS: 28/28**, all within 7,500 characters (`preset-smoke-review2-ui.json`); the frozen benchmark wheel's separate 28/28 result is retained. Cleanup audit `review2-final-audit.json` confirms all five baseline graph/snapshot pairs remain exactly unchanged, no extra graphs and zero bridge proposals. It also verifies the frozen benchmark wheel hash is unchanged. The UI wheel SHA256 is `af44c34b6ad70e67da939d82a37346c49acd3da8c6cd35968f18f11df3d690aa`.

Final full Librarian suite **PASS**, exit 0: **2,181 passed, 2 skipped, 5 deselected in 595.40 s**, `output/w4-review2-librarian-final-ssd2.log`. It ran against the isolated `geo-grapher-wave4` worktree; the owner's dirty original Librarian checkout was not changed.

The final quiet latency check ran only after both suites and browser servers stopped, through the installed UI wheel on `review2-stores/catalog.sqlite`. Every query succeeded, but the process exits 1 because the ToolSet ceiling is breached. All 12 first samples are retained in `latency-review2-final.json`; no warm replacement, discarded spike or repeat was used.

| Final current-store graph | Tree-balls seconds (three cold processes) | Directed seconds (three cold processes) | Verdict |
|---|---|---|---|
| ToolSet | **3.746, 3.020, 3.051** | **3.713, 2.796, 2.920** | **C14 FAIL** (<3.0 s required for every ToolSet sample) |
| librarian-v2 | 11.495, 9.278, 9.169 | 9.789, 6.732, 6.559 | Recorded, not gated |

The earlier cache-first old-store pass in §13 remains valid for that artifact, but does not supersede the final current-store failure. The isolated export scan became faster; end-to-end current-store cold latency still needs investigation. This is escalated with the failed code cycle, without additional product tuning or paid attempts.

No additional paid benchmark run is authorised or planned. Pool commitment after engineering delegation and all three runs is **$4.47507265 of $10**, leaving approximately **$5.5249**; this is a planning-rate ledger, not an invoice. Machine summary `reports/PHASE67_WAVE4_GATE.json` adds a review-2 section and preserves every historical result key.

### Required owner action

Follow §10 exactly for Resource-Library: start Host/Core; qualify both configured research_helper and Clerk roles with free L0 and paid L1 only after reviewing its plan; inspect `--status` for **screened** and **fresh: true** for both; leave Core running and report the statuses. If the configured Qwen3.5-397B Clerk times out, retain/report that failure and decide a replacement separately. Do not silently swap it. Only after the owner reports qualification can the six-task pilot resume. The production-lead question has not run: the recorded readiness check found Core not running. Both branches remain unmerged pending owner approval, and acceptance remains open because the registered code cycle failed.

## 15. Local continuation — 2026-11-13

Reviewable implementation and QA scripts: **`fe75697`** on `phase67-wave4`.

The owner's “please continue” resumes local engineering and independent application checks. It does **not** authorise another paid code benchmark cycle, changing the failed cycle's criteria, route substitution or merging. The configured helper and Clerk read-only status commands both found Core stopped; no qualification call or pilot task was sent. All earlier rows and frozen benchmark wheel/snapshots remain intact.

### Source-independent fixes and diagnostics

Three RED oracles exposed concrete issues before their fixes:

- Headless graph opening imported `geographer.server` solely for `persisted_secret`, loading MCP/HTTP transport modules inside a cold local query. The identical key-file behavior now lives in a small `cursor_secret` module; the server re-exports it for compatibility. A fresh-process test forbids server/MCP/Starlette imports while actually importing a project and opening its service.
- Unstemmed FTS failed ordinary plural/singular queries and admitted common function words as competing matches. Both FTS indexes now use SQLite's Porter/Unicode tokenizer. A conservative prose stopword list falls back to all original terms when it would remove everything, preserving function-word symbols. Exact canonical/qualified/constant-name matches retain priority, original term-count and candidate bounds remain, and matched-fields metadata comes from actual FTS matches. Retrieval semantic fingerprints include `lexical-fusion-v2-porter`.
- Only the final line of a constant's preceding comment block was associated with it. A sparse mapper now links every contiguous full-line comment at the assignment's literal indentation, plus comments inside its span. It stops at blanks, other statements and indentation changes. Original fragment text, spans and owner remain; only documentary incidences change, including removal of erroneous associations to a preceding statement's inline comment. `python-ast-symtable-v5-constant-comments` requires a new snapshot; prior facts are not edited.

DeepInfra Qwen drafted the mapper (`20261113T045321-97d80d8a`, $0.0007801), then the lead made it sparse, stabilised line iteration and wired extraction. Adjudication: **partial**. A separate Qwen review (`20261113T045718-b4649bd7`, $0.0039364) is **rejected**: its all-stopword finding contradicts the specified fallback; two findings supply no triggering input and are covered by actual headless/boundary tests; its fingerprint finding misses the dynamic retrieval-version inclusion. No reviewer output was accepted without code inspection.

Initial source-independent tests and full verify passed (668 backend, 17 browser, frontend), and `continuation-dist1` passed 28/28 preset calls. Its no-model diagnostics then exposed a fourth defect: utility-per-byte packing could drop the highest-ranked natural-language hit because its documentary nodes cost more than weaker matches. A new `UPLOAD_BUFFER` fixture reproduced that failure. Search units now use rank-ordered tiers, so a higher-ranked hit that fits is admitted before cheaper lower-ranked hits. The shared packer and other operations are unchanged. The `search-rank-tiers-v1` semantic fingerprint prevents reuse of old selections. Focused actor/retrieval/cap tests pass 29/29; the full suite was rerun after this change.

The same two observed diagnostic queries now return HELPER_TOOLS and DEFAULT_CONTEXT_TOKENS as their first delivered entities. The broader `external result cap` query still favours other cap-related code; it is **not** a three-question discovery pass. `continuation-search-first.json` and `continuation-search-ranked.json` retain complete flat responses. These are local, no-model diagnostics, not new benchmark answers or held-out quality evidence. The registered code cycle remains **FAIL 5/15**, with no additional paid benchmark calls.

All three source-copy re-ingests retain their entity and relationship counts; ToolSet has 17,597 entities and librarian-v2 28,809. Added documentary support is in `continuation-ingest-first.json`. The optional JavaScript parser still publishes no complete facts for the known `ui/app.js` failure; this environment reports Tree-sitter syntax failure rather than the wheel's missing-optional-parser message. The new immutable librarian-v2 snapshot is `snapshot:1703964f018a8f5981c139069836a87178098924bd94383d5788c083bb89c9bf`. New stores are under `D:/Librarian_V2/tmp/geo-grapher-wave4-continuation-stores/`; original project stores are untouched.

### Final candidate and local check registration

Final candidate: `continuation-dist2/geo_grapher-0.1.1-py3-none-any.whl`, SHA256 **07870422dcc7c758079929379ceb78015d6f8599a5016e13f093d8b1a25b3864**. Full Geo verify **PASS: 669 backend tests, 16 frontend unit tests, frontend typecheck/build, 17 browser tests**, exit 0 (`output/w4-continuation-verify-final.log`); first full verification remains separate. Librarian **PASS: 2,181 passed, 2 skipped, 5 deselected in 667.17 s** (`output/w4-continuation-librarian-full.log`). Final-wheel preset smoke **PASS 28/28**, `preset-smoke-continuation-ranked.json`; the first wheel's 28/28 row is also retained. Diagnostic and first-smoke processes briefly overlapped on the disposable catalog without lock/error; the final-wheel smoke ran after diagnostics completed, and before the browser.

Before the new local cold measurement: keep the unchanged C14 criterion, every ToolSet sample for both algorithms **<3.0 s**, three fresh processes each, all queries successful; Librarian timing remains non-gating. Use the final wheel and `continuation-latency-stores/catalog.sqlite`. Its ToolSet database is an isolated backup on **F:**, the same SSD as the previous gated run, with snapshot `snapshot:f5029b6bf601fcb2896a3c494e30dc306ced8624436d9334a9f9000931e1abee`. Nongating Librarian stores are on D:, so those timings are not a direct disk-controlled comparison. Run only after suites and browser stop; keep all first samples and no warm replacements. The earlier C14 failure remains a separate row, whatever this candidate measures. Capture one post-change cProfile separately; profiler timing is diagnostic, not the gate.

Final real-store browser **PASS 5/5** on the installed final candidate (`output/qa-real/results-continuation-first.json`): directed QI/expansion/Off restoration 51.2 s, prune 21.5 s, actual related-code bridge review 6.2 s, selected-partition ingestion 2.9 s, and four picker refusals. No page or console errors. Screenshot: `output/qa-real/continuation-directed-first.png`.

The first quiet local measurement **PASSES C14**, process exit 0, all 12 queries successful:

| Candidate / graph | Tree-balls seconds (three cold processes) | Directed seconds (three cold processes) | Verdict |
|---|---|---|---|
| continuation-dist2 / ToolSet (F:) | **2.474, 2.449, 2.429** | **2.975, 2.331, 2.296** | **PASS**, all <3.0 s |
| continuation-dist2 / librarian-v2 (D:) | 11.350, 8.215, 8.235 | 10.445, 6.461, 6.194 | Recorded, not gated |

Evidence: `latency-continuation-first.json`. The slowest directed sample has only about 25 ms headroom; this is a pass on the measured host, not a broad performance guarantee. No sample was dropped or repeated. Separate profile artifacts retain whole instrumented query times **4.780 s before and 4.818 s after**, and graph-service opening `_open` **0.734 → 0.167 s**. Profiling overhead and snapshot changes prevent claiming a whole-profile speedup. The cold-query gate is the unprofiled measurement above. Moving the key loader removes transport import from headless local opening; an already running HTTP/MCP server may already have paid that import cost.

The three reviewed constants still rank first for exact-name lookup, return their original lines, and stay outside helper blocks (`continuation-constant-inventory.json`). `continuation-semantic-audit.json` compares all three old/new graph pairs: original entities, dependency fields and multiplicities, every stored fingerprint, and QI group memberships are unchanged. Only version-bound relationship/occurrence IDs and snapshot-bound cluster IDs are normalised. Documentary incidence changes are ToolSet **+91/−15**, librarian-v2 and survey as recorded in that audit. Two initial accounting checks wrongly compared snapshot-bound QI IDs and then version-bound occurrence keys; both rejected assumptions and diagnostics are retained in `continuation-audit-rejected-accounting.json` and `continuation-audit-first-differences.json`. They are not product failures.

`continuation-final-audit.json` confirms every baseline graph/snapshot survived browser QA, no extra graphs or bridge proposals, installed wheel source/assets match the verified source/build, and the frozen benchmark wheel is unchanged. The all-stopword fixture was strengthened to use the actual stopword symbol `where`; all four language/rank tests passed afterwards, with no production changes after full verification.

No new paid code benchmark was run. Pool commitment is **$4.47978915 of $10** after this worker and review; remaining approximately $5.5202. Acceptance remains open: changed-product code quality is unmeasured, the earlier cycle failed, Core/role readiness blocks the live pilot, and owner hands-on/firewall decisions remain. Both branches remain unmerged pending owner approval.

## 16. Proposed changed-product code cycle — awaiting owner authorisation

This is a reviewable proposal, **not permission to execute**. Review 2 §3 required stopping and escalating after the failed cycle. The local continuation changes retrieval, documentary support and packing; testing this changed product needs a separately authorised cycle, rather than a fourth attempt on the old cycle.

Freeze the final candidate wheel/hash and librarian-v2 snapshot from §15, the same five CODE_BENCH questions/markers, Qwen3-Coder-480B, declared 1,048,576-token window, library-scoped lead preset and 12-step limit. Run exactly three independent fresh-library attempts without intervening changes. Preserve all rows in new `code-continuation-cycle-run1.json` through `run3.json`, with per-call logs and separate cost receipts. Pass only if each ≥3/5, total ≥12/15, zero withheld, zero wrong-graph calls and ≤8 average calls/question across all 15 questions. No best-of, changed scoring or fourth attempt. On failure, stop and escalate again.

Planning cost approximately **$0.50**, charged to the existing $10 pool (about $5.52 currently remains). The owner must explicitly approve this proposed cycle before it runs. The six-task pilot independently waits for the Resource-Library roles in §10; approving a benchmark does not qualify or replace those routes and does not approve a merge.
