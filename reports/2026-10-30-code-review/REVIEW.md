# Code and gate review at fd715f1

Review date: 2026-10-30. Scope: the 32 commits between the locally recorded `origin/master` and `fd715f1`, with deeper inspection of audited Sessions, closure enforcement, adoption/indexing, runtime budgets and G5 evidence. This is a risk-focused code review, not an exhaustive security certification. No product code, gate status or release revision was changed.

**Recommendation: fix the high-priority findings and requalify G5 and the affected G3 boundaries before freezing a release.** The measured run is reproducible, but its closure audit cannot detect an important class of false requirement closures. Passing fixture tests do not cover the counterexamples below.

## Findings, ordered by priority

### 1. P1 — A correct verifier can close the wrong requirement instance

Location: [verify_grain](../../src/resource_librarian/tools/audited.py), lines 166–184; [check_plan](../../src/resource_librarian/closure.py); [closure audit](../../src/resource_librarian/closure_audit.py), `_quote`.

Admission binds the predicate to a verifier ID, but does not bind its subject, evidence identity, note, expected value or scope. `verify_grain` accepts model-supplied `params` unchanged. For a person-defined predicate requiring a quotation from source A, supplying a real quote from source B produces a pass and an authoritative `verified` reduction. The independent audit also reports `holds`: it rechecks B against the same model-selected parameters, not against the person's source-A requirement.

**Reproduced through actual registry calls**, including person-set verifier identity. This is not a claim that the measured G5 quotes all used wrong sources; it demonstrates that the audit's zero-false-closure result is insufficient to establish the promised boundary.

Fix direction: admit a typed predicate instance with constrained inputs and expected subject identities. Check submitted parameters against that instance; bind verified outputs to it. If natural-language meaning cannot be operationalized, keep that part partial or human-judgment. An independent audit must verify the binding as well as rerun the local operation. Include wrong-source, wrong-note, wrong-contract and incomplete-multi-source counterexamples.

### 2. P1 — A later contract can overwrite a draft without invalidating its verification

Location: [audit_events.py](../../src/resource_librarian/audit_events.py), `_contract` around line 200, `_artifact`, `_latest_result` at line 273 and `unreduced_requirements` at line 537.

A fresh contract ID does not advance the epoch. Results and reductions are selected by requirement/current epoch rather than by the changed artifact and the applicable contract. Consequently, C1 can stage and verify a draft, then C2 can overwrite that same staging path, perform a clean target audit and enter reduce without running its planned verifier. `reduce_round` sees the old reduction and leaves the requirement `verified`. The old fingerprint now fails the offline closure audit.

**Reproduced through two registry-driven rounds with actual file replacement.** This exceeds a harmless reuse of unchanged evidence. It also affects a person's acceptance if the accepted artifact is later replaced without invalidation.

Fix direction: invalidate dependent verification/acceptance whenever artifact identity changes, including Core-originated writes. Require results/reductions applicable to the current contract and artifact revision. Reuse is permissible only with explicit unchanged-dependency evidence; epoch equality alone is insufficient.

### 3. P1 — Contract read scope does not cover get_note

Location: [closure.py](../../src/resource_librarian/closure.py), `_PATH_ARGS` and `authorize` lines 255–262; [get_note](../../src/resource_librarian/tools/library.py), line 386.

Read authorization scans a fixed list of parameter names (`path`, `note`, `source_path`, `file`, `target`). `get_note` uses `name`, resolved to a note name, so none of those checks run. An executing contract with empty read/write targets and only the `read` operation can retrieve an existing note through the registry. `read_evidence` similarly uses an evidence ID that is not represented in this scope check.

**Reproduced with actual get_note and an empty read scope.** This bypasses the contract boundary within an otherwise accessible vault; it does not demonstrate an escape from the application's broader vault permissions.

Fix direction: declare resolved read-resource intents in tool metadata, including note paths and evidence identities, and authorize those resources. Treat searches explicitly as discovery scopes rather than relying on parameter-name heuristics. Record actual dependencies for freshness tracking.

### 4. P1 — Adopted-root enumeration follows Windows directory junctions

Location: [content_roots.py](../../src/resource_librarian/content_roots.py), lines 190–198; [VaultWatcher._markdown](../../src/resource_librarian/coordination.py), lines 623–640.

The survey uses a reparse-point-aware `_is_link`, but indexing and watching use `is_symlink`. A Windows junction is not a symbolic link under the Python 3.11 API used here. The index walker therefore enters a junction and returns Markdown outside the adopted root under an apparently in-root path. The watcher has the same guard mismatch.

**Reproduced on Windows using a junction between two disposable directories.** The walker returned `linked/outside.md`. No user files were used. This can expose unapproved content to indexing/model retrieval and can produce cycles; it is a concrete read-boundary defect, not a demonstrated write escape.

Fix direction: share reparse-point-aware traversal with the survey, verify containment and file identity at access, and test junctions, mount points, symbolic links and cycles. Keep inspection and runtime traversal consistent.

### 5. P2 — File exclusions and hidden Markdown are ignored in adopted indexing

Location: [content_roots.py](../../src/resource_librarian/content_roots.py), `iter_documents`, lines 193–198.

Exclusions and hidden-name filtering apply only to directory names. An adopted root with `excludes=['private.md']` still enumerates `private.md`; `.secret.md` is also returned. Before adoption, the ordinary `notes.iter_notes` path excludes every hidden path component. Thus adoption can unexpectedly broaden what enters the index. The watcher also ignores file-level exclusions, although it does skip hidden filenames.

**Reproduced using plan_adopt/apply_adopt followed by iter_documents.** Fix direction: one consistent file-and-directory visibility predicate used by survey, indexing and watching, with explicit tests for relative file exclusions and hidden files.

### 6. P2 — G5's advertised hard dollar cap is checked after a whole model turn

Location: [g5_measure.py](../../scripts/g5_measure.py), lines 166–178 and 362–375; [Loop](../../src/resource_librarian/loop.py), model-step loop around line 921.

`loop.send()` completes before the runner examines metered spend or missing usage. One turn can make many provider calls. The requested remaining-dollar budget is not installed as a per-call reservation in the runtime, and this script does not use the delegation ledger despite the measurement plan promising that mechanism. Independent script invocations also do not share the stated sprint cap.

**Reproduced with a scripted provider and synthetic usage; no paid overrun was induced.** With a $0.10 requested cap, the runner accepted three calls reporting $1 each and stopped only after the turn at $3 simulated spend. [The reproduction](reproduce_budget.py) makes no network calls. The recorded real run remained within its stated total. Before future paid evaluation, reserve worst-case cost before each provider dispatch, enforce remaining budget across runs, settle actual usage, and stop before another dispatch when accounting is unavailable. An after-turn stop is a soft limit, not a hard cap.

### 7. P2 — G5 report incorrectly says t6's partial requirement was never addressed

Location: [measurement report](../2026-10-30-g5-measurement.md), “no_suitable_tool was not exercised.”

In `tmp/g5/full-mimo/t6-long-context-models`, contracts `round-1-model-notes` through `round-4-model-notes` address R1, the partial context-length requirement. The first omits a verifier; later contracts choose `quote.located`. Results V6–V11 include quote passes against that numeric predicate. The final R1 status is partial; the final latest check is not one of the 32 counted passes, so this correction does not itself change the headline numerator.

The statement that neither model addressed R1 is contradicted by the saved history. Fix direction: correct the narrative and distinguish “no_suitable_tool at final epoch” from whether an unplanned predicate or unsuitable proposed verifier occurred anywhere in the session. Preserve the original records.

## Gate evidence and known usability findings

- Recomputed from the saved Session histories: **74 grains, 32 current Tier A passes**, 16 sessions, no invalid audit-state folds; the 32 counted passes have clean/not-required contract integrity. The reported refusal totals also match: 254 admission/event refusals, 87 phase-budget refusals and 38 scope refusals (plus two bundle refusals).
- Saved restart receipts report **15/15 equal state hashes**. This review verified those records, not a fresh live crash/restart experiment. Saved metered spend sums to **$2.3665**.
- The measurement protocol also needs reconciliation: the plan describes a preselected random audit/reduce restart boundary, while `run_task` defaults to restarting after turn two without checking phase. This does not negate the recorded replay equality, but it is not the originally described boundary experiment. The Wilson intervals are nominal per-grain summaries; grains within sessions and repeated tasks across routes are dependent, so they should not be presented as generalization guarantees.
- Stops are **nine max-turn, four idle, three settled: failed**. “Settled” does not mean successful completion. This is compatible with the owner's permissive measurement rule but weak evidence for useful end-to-end task completion.
- The independent-versus-rerun distinction is candidly documented. Nonetheless, independent code is not an independent acceptance oracle if it trusts the same model-selected subject (finding 1).
- MiMo t5 records **115 questions**, and all sessions total 140. `ask_user` is exempt from phase budgets; its reuse guard compares normalized wording. Rephrasing therefore escapes it. Add a bounded unresolved-decision/progress policy with a clear pause reason; do not silently recycle answers across semantically different questions. Model confidence or fuzzy similarity alone should not decide that two consequential decisions are equivalent.
- Contract admission requires models to reproduce long predicate strings and infer target/operation scope. Make predicate identities and eligible verifier/parameter schemas explicit in the projection, return structured validation errors, and reuse deterministic contract construction for mechanical fields. Measure refusal reduction and useful completions without loosening admission rules.
- The design still intentionally defers a hardened development-agent workspace. G5 closure is not qualification of the [development-agent profile](../../docs/development-agent-harness.md). Existing Workbench staging/export concerns from the prior review remain outside these changes.
- Attached-root indexing is explicitly excluded in the implementation plan; it was not reported as an undisclosed regression here.
- The release queue correctly retains real-host, source-identity, signing and publication gates. This review recommends pausing freeze readiness pending fixes; it does not rewrite an owner decision.

## Verification and artifacts

- [Reproduction script](reproduce.py) uses temporary fixture vaults and makes no provider calls. Its assertions describe the observed defects, not desired behavior. [Captured output](reproductions.jsonl) records the results. The initial version needed an explicit close of its offline index connection for Windows temporary-directory cleanup; the preserved version exits successfully.
- [Recomputed G5 data](g5-recomputed.json) records per-session counts, stops, integrity and saved restart receipts.
- Targeted existing tests: **170 passed, 1 deselected**, in 35.81 seconds.
- Full non-slow suite: **1,848 passed, 1 skipped, 5 deselected**, in 635.75 seconds. The first bare-Python attempt correctly refused to test a sibling install; subsequent runs set `PYTHONPATH=src` and passed the checkout-source guard. Release-version consistency also passes. This is source-checkout evidence, not frozen-wheel qualification.
- DeepInfra supplied two bounded reviews (closure/replay and deployment). Suggestions were checked locally. Do not accept its speculative identity-reuse finding or its proposed partial-closure policy change without further evidence: ordinary edits may preserve document identity, and advisory partial closure is intentional. Cross-contract and junction findings were independently reproduced. Cumulative research-pool commitment after these calls: **$0.36314935 / $8**, including the earlier unresolved reserve; this review added **$0.0127752**. This is local accounting, not a provider invoice.

The repository reports master **32 commits ahead of the local origin/master reference**, not 47. No fetch or push was performed, so this does not establish the current remote server's state. The pre-existing untracked `Theorising_transcription.md` was left untouched.
