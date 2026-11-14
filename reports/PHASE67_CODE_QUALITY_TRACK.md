# Post-wave-4 code-research quality track

This is the separately authorised quality track from `PHASE67_CODE_AGENT_PERFECT_SCORE_PLAN.md`, not a new wave-4 release gate. Wave 4 remains closed and passed at **12/15**. No merge or push is authorised. All previous gate rows and raw attempts remain intact.

**Final outcome:** the single registered 90-episode cycle is complete and closed. Original five: **15/15**. Held-out: **49/75** (14/25, 18/25, 17/25), below both registered held-out thresholds. **FAIL; no repeat.** P1/P2/P4 remain, P3 was reverted, P5 was not applied. Read the measurement-validity audit at the end: the automatic held-out author produced some ambiguous question/key pairs, the development A/B was invalid due to harness setup, and the raw withheld detector counted source literals. No score, question, key or first row was changed to compensate.

## 1. Blind held-out set: sealed before product changes

Commit `0655729` seals 25 questions and keys, with seed **20261113**, against the two immutable snapshots listed in `PHASE67_CODE_QUALITY_HELDOUT_SEAL.json`. The baseline product commit is `d670d20`. Quotas are 10 constants with comments, 10 documented functions, and 5 behaviours involving an entry and 1–2 exact documented callees; 13 librarian-v2 and 12 ToolSet questions. Eligibility excludes tests/generated/vendor/external entities, duplicate or trivial identifiers, the five development markers, and documentation containing those markers. Sampling did not inspect benchmark answers. The implementing lead has not read the selected identifiers, questions or key.

The independent writer received only associated documentation, with defining and supporting identifiers redacted. The answer key was produced mechanically from the sampled canonical entities, not by the author. Raw private artifacts are retained under `output/phase67-gates/code-quality-track/`; their hashes, author model and receipt are committed in the seal. These files must remain unavailable to product workers and fixtures until the final cycle. Automated format/identifier checks do not establish semantic question quality; no human semantic review is claimed.

| Set-building attempt | Outcome | Cost / receipt |
|---|---|---|
| Initial wrapper invocation | Rejected safe-ID task argument before provider dispatch; sample retained unchanged | No provider call |
| GLM-5.3-Flash | Output budget exhausted without question text; raw response and receipt retained | $0.00303790 reserved charge; `20261113T133424-c13531e4` |
| MiMo-V2.6-Flash, same sample and redacted packet | 25 question fields; two mechanical JSON-key repairs and one automatic identifier anonymization, preserving question meaning; sealed | $0.00059836; `20261113T133512-0c9c4d6e` |

Pool commitment after set building: **$5.47175031 / $10**, approximately **$4.52825** remaining. The existing cap applies to all development and final calls, including retries. No budget increase is implied.

## 2. P1/P2 evidence

`code-quality-p1p2-red.log`: four new source-grounded integration tests failed on the baseline. Fixtures cover value/comment/match/reader cards, CRLF-preserving source hashes, cross-file usage, explicitly requested ranges, short-function constants, untrusted comment content and a tight envelope cap. Existing single-line constant assertions now request that exact line explicitly.

First replay, `development-scent-oracles.json`: **2/8**. Retained, not replaced. It revealed cap retries changing the search candidate pool and a replay assumption that the first entity was the requested definition. Neither is treated as a model failure.

| Local check | Retained outcome |
|---|---|
| Four new initial oracles | 4 RED before implementation |
| Initial full verify (`verify1`) | 694 backend, frontend and 17 browser checks passed; later replay still exposed missing real-graph behaviour |
| Replay 2 | 5/8; exposed candidate read omission and cap loss of fifth-ranked hits |
| Replay 3 / 4 / final | 8/8 each; hashes checked against snapshot bytes |
| Compact projection full verify (`verify-final`) | 1 failed / 695 passed: node citation handle compatibility regression |
| Citation correction full verify (`verify-final2`) | 697 backend, frontend 16 unit/typecheck/build, 17 browser passed |
| Long reader-name oracle | RED, then GREEN; bounds preserve the function-name suffix |
| Final full verify (`verify-final3`) | **698 backend, frontend 16 unit/typecheck/build, 17 browser passed** |
| Exact installed wheel, every preset | **28/28**, no model; full envelope <=7,500 characters |
| Exact installed wheel, real-store browser | **5/5**: ToolSet directed QI, prune preserving source, real-code bridge review, add-folder/partition, path refusals |

The P1/P2 wheel is `output/phase67-gates/code-quality-track/quality-dist/geo_grapher-0.1.1-py3-none-any.whl`, SHA256 **`159877aea26a3f1c678652bb804fea4edb0a3339f75ee0fa40a6c21004b000e6`**. Preset evidence is `preset-smoke.json`; browser evidence is `output/qa-real/results-quality-p1p2.json`. QA retention cleanup ran before testing. The disposable copy is complete, its five original graphs preserved and extra graphs removed; only its verified test-owned junction entry was removed after the server stopped, with its target preserved.

Cards use snapshot assignments/comments/docs, matched text and bounded reader names. Constants open with leading comments plus up to three static read sites, <=40 source lines; short functions expose bounded constants/value descriptors. Exact explicit ranges retain their old meaning. Source and comment content is marked untrusted. Candidate reads remain explicitly **candidate**, including the existing fallback-window read edge. No static candidate is promoted to an exact dependency. Every contextual range has an exact UTF-8 hash and source location. Optional context is dropped with omission metadata when necessary.

Search now fits a compact projection of one materialized candidate pool, retaining a prefix of its original ranking. No P5 ranking change was made. The internal 32k materialization cap does not expand the output profile: a tier-3 regression verifies the complete recounted result remains <=1,200 tokens even when a caller requests the lead budget. An independent DeepInfra review (`20261113T135353-c0cf32eb`, $0.00202690) raised four unsubstantiated findings about internal budgeting, cached results and truncation. They were rejected against the output-profile regression, whole-envelope recount and explicit truncation metadata; its raw review remains retained.

## 3. Development self-check A/B protocol (before dispatch)

One run of the original five with P1/P2/P4 and self-check disabled, then one run with the same product and self-check enabled. Same approved Qwen3-Coder-480B route, production temperature **0.2**, 1,048,576-token declared window, library-scoped lead preset and ordinary 12-step budget. This is diagnostic, not the final cycle. Keep P3 only if it increases the number of correct development markers, with no withheld or wrong-graph calls, no newly invented citations, and mean tool calls <=8. A tie does not justify retaining an extra call. Retain both rows and all HTTP receipts. No repeated A/B.

## 4. Final-cycle protocol (registration pending tested candidate)

Exactly one final quality-track cycle: original five and sealed held-out 25, each run three times independently, **90 episodes** total. The exact tested wheel, Librarian source, harness, frozen snapshot IDs, question/key hashes and production route policy will be registered before dispatch. No product changes between runs. The implementing lead must not inspect held-out episodes or keys until all three held-out runs finish. Scoring follows collection, not feedback during implementation.

Development requires **15/15**. Held-out requires **at least 68/75**, with **at least 22/25 in each run** (integer equivalents of >=90% aggregate and >=85% per run). Both require zero withheld, zero wrong-graph calls and mean tool calls <=8. Defining-identifier markers are the registered answer criterion; source/citation delivery remains separate evidence. Misses will be classified from coverage as `not_retrieved`, `retrieved_not_opened`, or `delivered_not_used`, with unknown/clipped evidence explicitly disclosed.

Stop after this cycle whatever the outcome. No extra run, question replacement, ranking tuning, merge or push follows without a new user request. The passed wave-4 release result remains unchanged.

Diagnostic P3 A/B OFF: `{"calls": 14, "correct": 0, "cost_usd": 0.028890999999999993, "enabled": false, "self_check_rejected": 0, "tool_errors": 14, "total": 5, "withheld": 0, "wrong_graph": 0}`.

Diagnostic P3 A/B ON: `{"calls": 10, "correct": 0, "cost_usd": 0.026502999999999992, "enabled": true, "self_check_rejected": 0, "tool_errors": 10, "total": 5, "withheld": 0, "wrong_graph": 0}`.

Diagnostic A/B decision: **do not retain P3** under the predeclared criterion. No repeat A/B.

### Diagnostic validity and corrective action

The two rows above are **invalid for comparing P3 effectiveness**, not product/model answer-quality measurements. All **24 tool calls were refused**: the harness selected `agent_profile=code-research` without supplying its `ProfileStore`, so Registry correctly reduced the caller to consult. The implementing lead introduced this setup error. No graph evidence reached either arm. The costs, raw attempts and numerical rows remain unchanged; neither 0/5 is presented as a valid model score.

There is no repeat A/B under the one-run-per-arm instruction. P3 therefore has **no valid demonstrated benefit** and was reverted in Librarian commit `7b47c68`; P4 remains in `d98cbbe`. This is an inconclusive diagnostic, not evidence that self-checking is ineffective.

The harness now supplies the same vault-backed `ProfileStore` as the application. `profile-access-smoke.json` proves actual installed-wheel list/search/content calls through `Harness.run` and Registry: **3/3 successful**, four scripted provider calls all at **0.2**, **zero paid calls**, with actual source coverage. The first smoke invocation's isolated-import error and corrected smoke log are both retained. An independent **25-question synthetic offline batch** also passes graph switching, fresh workspaces, unscored collection and refusal to overwrite the first output, without opening any held-out artifact. Seven coverage/one-shot tests pass. Supplemental constant-card IDs are logged separately from source delivery to avoid claiming they were absent merely because their source was not opened.

Pool commitment after set building, review and the invalid A/B: **$5.52917121 / $10**, **$4.47082879** remaining. The uncertain first GLM author call retains its conservative reserved charge; it is not recorded as a successful accepted output. The repaired MiMo author output is marked partial, and the unsupported independent review findings are rejected in the delegation ledger.

### Final candidate validation before registration

The P4-only Librarian runtime passes its **full suite: 2,196 passed, 2 skipped, 5 deselected**, in 605.98 seconds (`output/code-quality-librarian-full.log`). No product source changed during that suite. P3 is absent from the resulting source. The existing guarded step-limit synthesis remains; no extra self-check call is enabled.

Geo Grapher retains the exact P1/P2 wheel and its complete 698-test/frontend/browser verification above. Later evaluation-harness changes have **9/9 focused tests** for bounded source provenance, supplemental cards, exact range hashes, one-shot execution, delayed key reads and partial-run closure. The synthetic blind batch passes 25/25 without a model. A delivery-verifier smoke independently reconstructs the already captured development constant's two returned ranges from immutable SQLite source bytes: **2 verified, 0 invalid**, including its definition line. The actual HTTP A/B receipts all recorded temperature 0.2; the final runner will reject any batch with a different observed temperature.

Final scope is **P1 + P2 + P4**, no P3 and no P5. The final cycle is the one authorised cycle, not a retry of wave 4 or of the invalid diagnostic. Its six raw batches remain separate; scored held-out files are additional artifacts, never replacements. Coverage-based miss classifications describe canonical-entity/card retrieval and hash-verified returned source separately, and explicitly mark clipped/invalid evidence as unknown.

## Registered single final quality-track cycle

Registration: `reports/PHASE67_CODE_QUALITY_FINAL_REGISTRATION.json`, SHA256 `23981aadedb4757f63be580b9b2117768e46817c41b912daafdf494e6d79af6a`. This is the only authorised quality-track cycle: dev 15/15; held-out >=68/75 and >=22/25 per run; zero wrong-graph/withheld; mean calls <=8. 90 episodes, three runs each, at the registered production profile. No product changes, replacement questions or extra cycle; stop whatever the result.

Final quality cycle dev run 1: `{"calls": 24, "correct": 5, "cost_usd": 0.10955960000000002, "group": "dev", "run": 1, "self_check_rejected": 0, "tool_errors": 0, "total": 5, "withheld": 1, "wrong_graph": 0}`.

Final quality cycle heldout run 1: `{"calls": 127, "correct": 14, "cost_usd": 0.6464649, "group": "heldout", "run": 1, "self_check_rejected": 0, "tool_errors": 0, "total": 25, "withheld": 0, "wrong_graph": 0}`.

Final quality cycle dev run 2: `{"calls": 27, "correct": 5, "cost_usd": 0.1372894, "group": "dev", "run": 2, "self_check_rejected": 0, "tool_errors": 0, "total": 5, "withheld": 1, "wrong_graph": 0}`.

Final quality cycle heldout run 2: `{"calls": 122, "correct": 18, "cost_usd": 0.5874692999999999, "group": "heldout", "run": 2, "self_check_rejected": 0, "tool_errors": 0, "total": 25, "withheld": 0, "wrong_graph": 0}`.

Final quality cycle dev run 3: `{"calls": 30, "correct": 5, "cost_usd": 0.1568277, "group": "dev", "run": 3, "self_check_rejected": 0, "tool_errors": 0, "total": 5, "withheld": 1, "wrong_graph": 0}`.

Final quality cycle heldout run 3: `{"calls": 121, "correct": 17, "cost_usd": 0.5806140000000002, "group": "heldout", "run": 3, "self_check_rejected": 0, "tool_errors": 0, "total": 25, "withheld": 0, "wrong_graph": 0}`.

Final quality-track verdict: **FAIL**. `{"calls_per_question": 5.011111111111111, "cost_usd": 2.2182249, "development_correct": 15, "development_total": 15, "evaluation_closed": true, "heldout_correct": 49, "heldout_total": 75, "no_repeat": true, "passed": false, "runs": [{"calls": 24, "correct": 5, "cost_usd": 0.10955960000000002, "group": "dev", "run": 1, "self_check_rejected": 0, "tool_errors": 0, "total": 5, "withheld": 1, "wrong_graph": 0}, {"calls": 127, "correct": 14, "cost_usd": 0.6464649, "group": "heldout", "run": 1, "self_check_rejected": 0, "tool_errors": 0, "total": 25, "withheld": 0, "wrong_graph": 0}, {"calls": 27, "correct": 5, "cost_usd": 0.1372894, "group": "dev", "run": 2, "self_check_rejected": 0, "tool_errors": 0, "total": 5, "withheld": 1, "wrong_graph": 0}, {"calls": 122, "correct": 18, "cost_usd": 0.5874692999999999, "group": "heldout", "run": 2, "self_check_rejected": 0, "tool_errors": 0, "total": 25, "withheld": 0, "wrong_graph": 0}, {"calls": 30, "correct": 5, "cost_usd": 0.1568277, "group": "dev", "run": 3, "self_check_rejected": 0, "tool_errors": 0, "total": 5, "withheld": 1, "wrong_graph": 0}, {"calls": 121, "correct": 17, "cost_usd": 0.5806140000000002, "group": "heldout", "run": 3, "self_check_rejected": 0, "tool_errors": 0, "total": 25, "withheld": 0, "wrong_graph": 0}]}`. Evaluation is closed; no further model dispatch. Wave-4 release gate remains closed at 12/15.

## Closed-cycle results and delivery evidence

| Set | Run | Correct / total | Tool calls/question | Errors | Wrong graph | Withheld | Cost |
|---|---:|---:|---:|---:|---:|---:|---:|
| dev | 1 | 5/5 | 4.80 | 0 | 0 | 1 | $0.1095596 |
| heldout | 1 | 14/25 | 5.08 | 0 | 0 | 0 | $0.6464649 |
| dev | 2 | 5/5 | 5.40 | 0 | 0 | 1 | $0.1372894 |
| heldout | 2 | 18/25 | 4.88 | 0 | 0 | 0 | $0.5874693 |
| dev | 3 | 5/5 | 6.00 | 0 | 0 | 1 | $0.1568277 |
| heldout | 3 | 17/25 | 4.84 | 0 | 0 | 0 | $0.5806140 |

Registered verdict: **FAIL**. Development **15/15**; held-out **49/75**. Mean tool calls **5.01**. Cycle cost **$2.2182249**. No replacement run or product tuning follows.

| Held-out stratum | Correct / total |
|---|---:|
| constants | 18/30 |
| functions | 21/30 |
| behaviors | 10/15 |
| librarian-v2 | 23/39 |
| ToolSet | 26/36 |

Coverage classes for held-out misses: `{"delivered_not_used": 1, "not_retrieved": 25}`. Independently verified target source ranges: **68**; invalid hashes/provenance: **0**. The defining source line was returned in **46/75** episodes. Metadata/card retrieval is not counted as source-body delivery.

Coverage scope: the frozen recorder captures search/content coverage and supplemental constant-card IDs. Architecture, packet and cross-graph payloads do not supply equivalent range records; 0/75 episodes used those operations. An absence classification in such an episode is provisional, not proof the agent never saw the definition in another payload. Positive hash-verified delivery remains positive evidence. These limits do not rescore answers.

Supplementary citation check: 28/75 episodes contain entity citation handles; 28/75 have at least one identity present in delivered scoped metadata; 0/75 contain at least one identity not verified by the bounded records. This check normalizes the `entity:` prefix and is not proof of literal handle copying or substantive claim support. It does not alter the registered marker scores.

### Held-out misses (all original rows retained)

| Question | Expected defining identifier / source | Missed runs and coverage class |
|---|---|---|
| heldout-02: Which implementation compacts the history of older tool results sent to the model, clipping them to a character limit while keeping the full log intact? | `KEEP_RESULTS`; `src/resource_librarian/loop.py:128` | run 1: not_retrieved (definition line not verified returned); run 2: not_retrieved (definition line not verified returned); run 3: not_retrieved (definition line not verified returned) |
| heldout-03: Which implementation reads non-model-provider API keys (such as web search backends and GitHub repository intake) from the environment? | `SEARCH_KEYS`; `src/resource_librarian/keys.py:46` | run 1: not_retrieved (definition line not verified returned) |
| heldout-04: Which implementation defines the whole the documented implementation that reads its job from /job/spec.json, imports one module, calls one function, and prints a marked JSON line? | `RUNNER`; `src/resource_librarian/claim_run.py:64` | run 1: not_retrieved (definition line not verified returned); run 3: not_retrieved (definition line not verified returned) |
| heldout-07: Which implementation deliberately omits a repository count from its output, and what reasoning is documented for that choice? | `SERVER_INSTRUCTIONS`; `aletheia_toolchain/code_intelligence/mcp_server.py:46` | run 1: not_retrieved (definition line not verified returned); run 2: not_retrieved (definition line not verified returned); run 3: not_retrieved (definition line not verified returned) |
| heldout-10: Which implementation defines the rule identifiers referenced elsewhere in the documentation? | `R001`; `aletheia_toolchain/tool_command_linter.py:32` | run 1: not_retrieved (definition line not verified returned); run 2: not_retrieved (definition line not verified returned); run 3: not_retrieved (definition line not verified returned) |
| heldout-11: Which function returns everything readable rather than guessed, filtered to the vault's permitted values, leaving a missing axis missing? | `derive_axes`; `src/resource_librarian/facts.py:697` | run 1: not_retrieved (definition line not verified returned); run 2: not_retrieved (definition line not verified returned); run 3: not_retrieved (definition line not verified returned) |
| heldout-12: Which function enforces that Core-backed extraction stays on its single SQLite owner, and what must a standalone script explicitly choose? | `_with_index`; `src/resource_librarian/extract.py:31` | run 2: not_retrieved (definition line not verified returned) |
| heldout-13: Which function looks up a note by name and prefers a particular shape when two notes share a name? | `note_row`; `src/resource_librarian/index.py:789` | run 1: not_retrieved (definition line not verified returned) |
| heldout-16: Which rule identifier flags an automated slicer invocation missing --deterministic as a WARN rather than a BLOCK, and what is the documented justification? | `rule_r005`; `aletheia_toolchain/tool_command_linter.py:486` | run 1: not_retrieved (definition line not verified returned); run 2: not_retrieved (definition line not verified returned); run 3: delivered_not_used (definition line returned) |
| heldout-18: Which function runs partition_experiments in n fresh processes with distinct PYTHONHASHSEED values and reports the spread, and why is that spread meaningful? | `run_replicates`; `aletheia_toolchain/code_intelligence/audit_graphify_graph.py:755` | run 1: not_retrieved (definition line not verified returned) |
| heldout-21: Which implementation defines the three short call kinds (lens_document, lens_support, probe_answers) for staging document-level stances across a book's parts? | `_document_pass`; `src/resource_librarian/deep_read.py:764` | run 1: not_retrieved (definition line not verified returned); run 2: not_retrieved (definition line not verified returned); run 3: not_retrieved (definition line not verified returned) |
| heldout-23: Which implementation applies a person's answer about an outcome-unknown step to a run as its log recorded it, and when is it refused? | `resolve_macro`; `src/resource_librarian/agent_runtime.py:848` | run 1: not_retrieved (definition line not verified returned); run 3: not_retrieved (definition line not verified returned) |

The private seal was created before product changes; its key was first opened after all six raw batches completed. All raw, scored, first failed and cost files remain separate. The invalid development A/B remains disclosed and P3 remains removed. Wave 4 remains closed/passed at **12/15**. No merge or push was performed.

## Post-closure measurement-validity audit

This section is reporting only. No product change, new model call, question replacement, score adjustment or additional cycle follows the result.

### Withheld counter: three source-literal false positives

The raw development rows retain one withheld count per run. `final-withheld-audit.json` shows each is the external-MCP question's successful content response containing the literal `EXTERNAL_RESULT_TOO_LARGE` in frozen `mcp_client.py:490–492`, SHA256 `4b89b153bfc1b70b2cc4f4e10cd1e71debb7da00c16586cca89a027a685415c8`. The inherited harness uses substring detection. All these tool calls succeeded, with source coverage; **no structured withheld error occurred**. Across the cycle there were zero per-call tool errors and zero wrong-graph calls. The raw counters and registered FAIL remain untouched; the held-out threshold independently fails.

### Held-out question/key validity is limited

The set was genuinely sealed before product changes and remained blind, but its semantic quality was not independently reviewed before sealing. Post-closure inspection establishes concrete construction defects:

| Item | Evidence | Consequence |
|---|---|---|
| heldout-02 | The question asks which implementation compacts/clips old tool results. Its key is retention-count constant `KEEP_RESULTS`; all three answers identify `_compact_result`. | The question does not uniquely ask for the sampled constant. A missing constant marker is not sufficient evidence of a wrong implementation answer. |
| heldout-10 | The entire sampled comment is decorative separators around “Rule identifiers”. It passed the >=100-character filter because punctuation counted as content. The key arbitrarily expects `R001`. | The documentation does not distinguish this identifier from other rule implementations; this is a set-construction defect. |
| heldout-16 | The question explicitly asks for a **rule identifier**; the documentation begins “R005”, but the frozen key expects function identifier `rule_r005`. All three answers name R005; run 3 also returns the documented justification with the defining source citation. | At least the run-3 marker miss reflects question/key mismatch, not failure to use the delivered evidence. |

These examples invalidate a claim that **49/75 is a precise general-answer accuracy estimate**, or that all 26 marker misses are product retrieval/answer failures. The coverage classes above are literal delivery diagnostics against the frozen entity key; they do not validate that key's semantic appropriateness. Other misses may still reflect retrieval or answer problems, but this audit does not adjudicate or numerically rescore them. No items are excluded, no alternative score is offered, and no threshold is relaxed. A reliable unseen-quality claim remains unestablished. The required stop is honoured instead of repairing the set after seeing the results.

### Final integrity and cost

`final-audit.json` confirms the tested wheel, all registered harness/runtime inputs, both snapshot IDs and all three sealed-set hashes stayed unchanged. All **541 HTTP attempts completed at temperature 0.2**. The exact quality-cycle cost is **$2.21822490** at the recorded planning rates. Pool commitment is **$7.74739611 / $10**, with **$2.25260389** remaining. The old wave-4 closure marker is unchanged and closed; this quality cycle is separately closed with `no_repeat: true`. Both feature branches remain unmerged and unpushed. Only reporting/documentation is committed after closure.
