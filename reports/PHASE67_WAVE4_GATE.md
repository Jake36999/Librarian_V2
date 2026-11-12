# Phase 6–7 Wave 4 gate — 2026-11-12

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
