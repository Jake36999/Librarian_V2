# Secondary review claim check

Checked 2026-10-30 against current HEAD `a9be71b` and historical `fd715f1`. No product code or gate status changed in this check.

**Verdict:** the six historical defects and recorded G5 numbers are supported. The secondary review conflates revisions, overstates test coverage and delegation evidence, and presents several unqualified implementation suggestions as established fixes.

## Claim-by-claim assessment

| Claim | Assessment |
|---|---|
| All 14 local tasks have implementation work recorded | Supported by the unified plan and commits. This is a task-status statement, not proof of complete behavior or readiness. |
| “Feature-complete code coverage” | Unsupported terminology. Passing-test counts do not measure statement/branch coverage, requirements completeness or adversarial coverage. No coverage measurement supporting that phrase is cited. |
| Suite grew from 1,574 to 1,848 passing tests | Supported as historical snapshots. They are from different revisions and selection counts also differ. The earlier 1,848/1/5 result applies to `fd715f1`, not automatically to `a9be71b`. |
| 32/74 grains, 15/15 restart matches, approximately $2.37 spend and 115 MiMo t5 questions | Supported by the preserved evidence and original independent recomputation. Restart matches are saved receipts, not a fresh recovery experiment in this check. |
| Four P1 and two P2 implementation defects | Supported for `fd715f1`. The budget reproduction is in `reproduce_budget.py`, not the main reproduction script. The simulated $3 overrun incurred no real spend. |
| The same six defects remain proved at `a9be71b` | Incorrect. That commit adds fixes and regression tests for those six defects. Historical scripts intentionally assert the defective behavior and cannot be treated as current regression expectations. |
| Reopen G3/G5 and block freeze | Reasonable review recommendation while qualification is incomplete, not an observed gate-state change or automatic consequence of six tests passing. Owner decisions and release entry gates still apply. |
| Delegation caused the blind spots, and named models drafted the nine listed modules and tests | Not established by the available receipts, commit messages or plan. Earlier parts of the project do document DeepInfra drafting; that does not establish authorship of these particular modules or causation. The two Oct-30 DeepInfra calls in this review were reviewer calls. No evidence supports the asserted motive of conserving Claude tokens. |
| Existing tests cover only happy paths and obviously unpermitted tools | Incorrect characterization. Tests already covered invalid plans, unsupported verifiers, strength limits, stale evidence, edits after staging, target violations, composition restrictions and other refusal paths. The six counterexamples identify specific missing cases. |
| MiMo never addressed t6's partial requirement | Incorrect historically, as both reviews recognize. Current `a9be71b` already adds a dated correction preserving the original narrative. |
| Fixes and passing regression tests alone make all gates ready for freeze | Too strong. The corrected G5 report recommends a new measurement with fixed code and subject bindings; source identity, lifecycle and other release gates remain required. |

## What changed at a9be71b

The commit adds person-bound verifier subjects, contract-specific results/reductions, epoch invalidation when an existing artifact path is recorded with changed content, resolved note/evidence read checks, shared visibility/reparse-point filtering, a pre-dispatch G5 budget guard and shared run ledger. It also corrects the t6 narrative and reports a retrospective subject check of 29 subject-taking passes. The latter is a retrospective audit claim; it does not make the original execution a run under the new enforcement.

The original suite result cannot be carried forward. This check ran eight affected test modules with checkout imports explicitly selected: **183 passed, 1 failed, 1 deselected**, in 66.67 seconds. The failure is `test_a_quote_from_the_wrong_source_cannot_verify_the_requirement` at `tests/test_research_round.py:454`. It also failed when run alone.

The failure is a test-fixture defect: `requirements(lead)` chooses `stored[0]`, while `EvidenceStore.iter()` sorts records by hash-derived filename. The supposedly wrong source B can therefore become the person-bound source. Its successful check is then allowed by the implemented policy. An independent disposable-vault check explicitly bound source A and supplied source B: **the runtime refused it**. Fix the fixture by passing the intended evidence identity explicitly. Do not interpret that failed assertion as proof that the original wrong-source bypass still exists.

The plan's post-fix entry itself records a full-suite failure followed by a targeted validator pass; that is not evidence of a final full green run. A full suite was not rerun during this claim check.

## Corrections to technical detail

- The historical adopted walker **did check `is_symlink()`**. It missed Windows reparse points/junctions; saying it checked neither is inaccurate.
- It pruned excluded directories at multiple depths, not only top-level directories. The missing checks were for files and hidden filenames.
- The verifier is `target.diff_clean`, not `staging.clean`. The product uses an audited Session, not an `AuditedEngagement` class. The tool is `record_assumptions`, not `record_assumption`.
- `get_note` bypassed the contract boundary inside an otherwise accessible vault. The reproduction did not prove a broader filesystem permission escape.
- The quote audit used separate checking code over saved model-selected parameters. Its defect was lack of independent subject binding; describing all checks as simply rerunning the same verifier loses the independent/rerun distinction.

## Assessment of the proposed fixes

**Subject binding:** correct direction, now partly implemented. Binding a source ID establishes which source was checked; it does not prove that an arbitrary quotation establishes the natural-language claim. Verifier capability, expected value, scope and semantic acceptance still need explicit boundaries. A quotation alone cannot prove numeric agreement across several models.

**Staleness:** correct objective. The current fix conservatively bumps the shared epoch when a recorded artifact is replaced. A targeted dependency/taint graph is an implementation option, not necessary to fix the reproduced case. Same-contract replacement, other mutation routes and accepted artifacts should remain in qualification coverage.

**Read scopes and traversal:** correct objectives. Current code addresses the named cases. Prefer declared resource intents and consistent access-time containment as the tool surface grows; adding one parameter name alone is insufficient.

**Budget:** a pre-call guard is the right direction and now exists. The current character-based worst-case estimate and ledger still need qualification for actual provider serialization/token accounting, retries, missing usage, crash recovery and durable reservations. A per-turn profile limit alone does not establish a cross-session dollar cap. The saved synthetic overrun is evidence about the old runner, not a provider billing guarantee.

**Question loop:** a bounded no-progress/clarification policy is justified. The proposed quota of two and Jaccard threshold of 0.65 have no supporting evaluation here. Unanswered-only quotas would miss the recorded run because questions received fixed answers. Similar wording does not establish equivalent authorization. On exhaustion, preserve unresolved constraints and pause/park or continue only independent authorized work; do not instruct the agent to assume a missing consequential answer and proceed.

**Admission interface:** explicit predicate IDs, eligible verifier schemas and a generated contract skeleton are useful. Current code already accepts an unambiguous bare predicate key and normalizes some inputs. Only apply semantics-preserving repairs; rerun full admission after repair. Never infer or enlarge authority, targets or verifier strength to get a proposal admitted.

**Next evidence:** correct the regression fixture, validate remaining changes, qualify budget failure modes, and run the affected G5 slices under the new code/task bindings. Old audited histories now intentionally replay invalid because their verified reductions lack contract fields; preserve their original evidence and use a declared compatibility/review path rather than silently rewriting them.
