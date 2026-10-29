# Design review and dispositions

The proposed [harness design](../../docs/long-horizon-harness-design.md) received two bounded DeepInfra critiques. Findings were evaluated against the current unified plan and the local source extracts; model labels such as “defect” were not accepted automatically.

## Contract and scope review

DeepSeek V4.1 Flash, task `lh-design-contract-review`, returned a complete response. It received the design and the unified plan's exact Wave 4 excerpt. The preserved receipt/output is in `data/remaining_deepinfra/`.

| Finding | Disposition |
|---|---|
| Claimed contradiction between prohibited read→write composition and allowed scoped staging | **Rejected as a contradiction.** The design distinguishes permitted staged effects from authority escalation and out-of-scope effects. The plan does not prohibit every write after an untrusted read. No blanket read→write ban was added. |
| Baseline versus deferred trust enforcement unclear | **Clarified.** HARNESS-05 must demonstrate contract, per-call and prohibited-composition guards before audited mutation acceptance. Comprehensive multi-hop trust propagation remains deferred. The design makes no claim that all of this is already implemented. |
| Requirement/contract changes need freshness semantics, not only `external_edit` | **Accepted.** Requirement revisions and contract revisions now explicitly participate in epoch invalidation, with acceptance coverage assigned to HARNESS-02. |
| Latest verifier result could hide another failing predicate | **Accepted.** A requirement must expose current results for every closure obligation, either through separate grains or per-predicate results. A mixed pass/fail fixture is included. |
| Replace HARNESS-06's real-session measurement with synthetic-fixture instrumentation | **Rejected.** That would weaken an explicit plan requirement. The design retains measurement on actual local research sessions, with denominators; synthetic fixture results are separate. A hosted production deployment is not necessary to observe local real sessions. |
| Interface verification indistinguishable from a clean diff | **Accepted.** Staging record/artifact revision and declared lookup checks are now distinct from protected-target diffs, when required by the contract. |
| Replay integrity failure cases missing | **Accepted with qualification.** A recoverable incomplete trailing append is distinguished from an invalid committed prefix or unsupported schema. An unresolved effect cannot silently disappear during recovery. |
| Material-change list should match plan deferrals | **Recorded.** The unified plan remains the scope authority; the design's speculative additions are not required features. No plan task status or dependency was changed. |

## Evidence-transfer and user-control review

Qwen3.5-397B-A17B, task `lh-design-evidence-review`, received the updated design, corpus synthesis and locally extracted passage anchors. The response **truncated at its output limit**; it is a partial review, not a completed independent audit. Four findings and the start of a fifth were visible.

| Finding | Disposition |
|---|---|
| Repair of malformed contracts needs explicit safety conditions | **Clarified.** Every repaired proposal must repeat full preflight; no execution occurs during repair. This is a product design decision, not an empirical claim that R06 demonstrated product repair safety. |
| Integrity-checked state versus unauthenticated environment creates a contradiction | **Rejected.** Event integrity, source freshness and semantic truth are explicitly separate. The design does not infer environmental authenticity or truth from a hash. |
| Parking uncertain effects could harm continuity | **Useful recovery clarification, not a contradiction.** The user can inspect evidence, supply a receipt for verification, select independent work, or end with the effect unresolved. Required policy and verification cannot be bypassed to force progress. |
| R14's manually instantiated proof parameters require user-editable monitoring thresholds | **Rejected.** Formal invariant parameters are not the same as product monitoring thresholds. Users receive explanations and scope controls; they do not automatically acquire authority to change mandatory safety policy. Numerical tuning remains open. |
| Beginning of a finding that a hard context bound freezes a small detail | **No actionable complete finding.** A bound is explicitly required by HARNESS-04; its numeric allocation and assembly strategy remain open. |

## Local checks and limits

- All 51 source files and extraction paths were checked; every SHA-256 matched the complete manifest. Fifty hashes are distinct.
- All 20 new normalized passage anchors were checked against the specified physical PDF page. These checks establish quotation presence, not semantic support or experimental validity.
- The four final corpus reader outputs were complete; several earlier responses elsewhere in the sprint were truncated. Preserve each receipt's actual status rather than treating all model output as fully reviewed.
- Relative Markdown links in the delivered design/review documents were checked after artifact creation. Results are saved in `data/delivery-validation.json`.
- The final budget is recorded in `data/budget-summary.json`, including the unresolved historical reservation. Charges are metered estimates rather than a provider invoice.
- No implementation tests or product benchmark was run for this documentation-only delivery. The specification identifies required implementation acceptance cases; it does not claim those cases have passed.

The original audited-engagement proposal and unified implementation plan remain unchanged. The new design is a proposal for their HARNESS-01 reconciliation and the subsequent implementation session.
