# Additional review fact check

Checked 2026-10-30. Review target: `a9be71b`; current HEAD during this check: `818f1a2`, which adds completed G5 rerun results and document changes. Product logic remains the `a9be71b` implementation. This report checks the supplied review; absence of a prior audit is not itself proof of a defect.

## Verdict

The review adds supported validation/link-accounting and aggregate-search findings, and correctly carries forward Workbench containment concerns. Several other claims are already acknowledged design choices, stale run snapshots or unsupported generalizations. Its proposal to refund uncertain API reservations automatically is unsafe. Its proposed workspace classifier does not exist in the current content-model API.

### 1.1 — Adopted document validation: substantially supported, classification caveat

`tools/core.py:check_notes` skips plain adopted documents before collecting names and links, while frontmattered documents remain subject to duplicate-name checks. A disposable adopted-vault reproduction confirms:

- Two ordinary frontmattered `README.md` documents are flagged as duplicate note names.
- A plain workspace document links to a typed Concept, but that link is ignored and the Concept is reported as an orphan.
- A plain file in `Sources/` receives no normal model-check violations, whereas directly invoking the content model on the same file produces violations.

The last observation is a **classification ambiguity**, not enough by itself to prove corrupted Librarian-note state: existing tests deliberately require a plain `Sources/vendor-notes.md` to remain a workspace document. Folder placement alone cannot distinguish an adopted document from a managed note that lost its metadata. Explicit managed identity/provenance or a user-declared policy is needed.

The code's `rglob('*')` file-existence inventory indeed bypasses the exclusion-aware traversal. That broad inventory can create inconsistent link judgments and unnecessary scanning; this review did not demonstrate content exfiltration through it. Preserve intentional support for non-Markdown attachments when replacing this scan.

**Proposed fix correction:** `schema.ContentModel.shape_of()` does not return `workspace_document`; that classification currently lives in the indexer. Reusing `shape_of(...) == 'workspace_document'` would not work. Establish a shared classification policy used by indexing, validation and status, and collect the visible link graph independently from schema enforcement. Ensure foreign YAML metadata does not make adopted documentation disappear from workspace search.

### 1.2 — Aggregate search: supported misleading metadata; filter semantics need qualification

`search._everything` copies verdict, coverage, considered count and other metadata from `orient` while appending results from other groups. The reproduction returned **one workspace match with top-level `verdict='uncovered'`, `considered=0`**, while the direct workspace search reported `thin`. Guidance also omits workspace. These are confirmed response-consistency defects.

It is true that only `orient` receives constraints and the age bound, and that `_everything` does not forward `source`. However, direct `pattern`, `made` and `workspace` searches also do not apply source-axis constraints; age filtering is currently defined for source-shaped results. The `source` argument currently scopes `technique`/`in_text`, neither included in the all-search groups. Much of this predates DEPLOY-03.

Do not blindly apply source license/age axes to Concepts or workspace documents. Specify valid filters by result group, reject or explicitly report inapplicable filters, and expose per-group coverage/counts. Add an honest aggregate verdict rather than averaging incomparable coverage. The lack of validation/clarity on unsupported combinations is a contract issue; the existing source filter cannot be assumed to promise an ACL for every intent.

### 1.3 — Coarse epoch invalidation: true behavior, optional redesign

Artifact replacement bumps a session-wide epoch and can stale unrelated results. This is conservative and intentionally permitted by the accepted harness design; targeted dependency invalidation was deferred. It is a potential efficiency/usability cost, not a new security bypass. Measure unnecessary revalidation before adopting a larger dependency/taint system. Do not require that system to finish the original stale-closure remediation.

### 1.4 — Legacy replay: supported, previously acknowledged

Old verified reductions without a contract field replay invalid under the new rules. The commit/plan acknowledge this compatibility break and identify the existing audited histories as G5 fixtures/runs. The earlier fact check also called for a declared compatibility path. A legacy reader/versioned policy is warranted; it must distinguish unsupported historical format from corruption and avoid granting old results current assurance. “Replay cleanly” must not mean grandfathering unsafe verification as trusted.

### 1.5 — Failing evidence fixture: supported and order dependent

The previous eight-module run recorded 183 passed, 1 failed, 1 deselected; the test also failed alone. It picks `stored[0]` from hash-sorted evidence, which can bind source B. The earlier explicit source-A check rejected source B correctly. During this check, the same test passed in a 20-test run. That varying result supports fixture instability, not proof the product bug returned. Passing today does not repair the fixture. Change the helper to take the intended evidence ID explicitly; do not change the evidence iterator's ordering to conceal the error. No generalized runtime use of `iter()[0]` was established by the review.

### 1.6 — Quote semantics: supported limitation

`quote.located` establishes normalized substring presence in evidence; it does not establish entailment or cross-source numerical agreement. The source key is currently `evidence`, not `source_id`. Subject binding fixes wrong-subject substitution but not an unsuitable acceptance predicate. Admit only operational predicates whose intended assertion matches the verifier, or split mechanical evidence presence from human semantic acceptance. The existing t6 partial status should not be described as a full authoritative semantic closure.

### 1.7 — Read-scope architecture: supported concern, incomplete enumeration

Tool-level resource resolution is more explicit after the fixes but remains incomplete as a general read boundary. The review lists both module and tool names as if they were all modules; the tools directory has 34 Python files including `__init__.py` (33 others), not the enumerated structure implied in the prose. The number does not establish a bypass.

A capability-aware file/index/evidence access service or explicit read intents are reasonable directions. Thread trusted session/contract context through all access paths; merely adding a path check to a context-free storage function is insufficient. First define whether discovery search may read the whole vault, then test it. Do not silently break legitimate global discovery or claim it is scoped without enforcement.

### 1.8 — Budget estimates and durability: supported qualification gaps

The pre-call guard and shared locked G5 ledger are real improvements. Their “worst case” input estimate depends on serialized input and provider accounting. The G5 ledger records spend after a task and lacks a durable unresolved per-call reservation, so crash recovery requires qualification. Provider-internal retries and usage uncertainty need explicit accounting. This is distinct from the separate DeepInfra delegation ledger, which already retains uncertain reservations and has a reconciliation command.

### Other surfaces

| Claim | Checked result |
|---|---|
| Workbench export checks bytes after copying | Supported by `_archive_outputs`; no large copy or escape exploit executed. Treat as a high-priority live resource/import boundary gap. |
| Workbench staging helper lacks main-execution restrictions | Supported. Output initialization has `--network none`; source staging lacks the same explicit restriction and several other flags. Neither the main command nor the helper explicitly selects a seccomp profile; Docker defaults must not be mistaken for demonstrated absence of seccomp. Provisioning may need a narrowly privileged phase rather than blindly copying all flags. |
| These Workbench concerns were never carried into the release review | Incorrect. The original REVIEW.md explicitly carries forward the earlier Workbench staging/export concerns, and development research documents detail them. They were not fixed or exploit-tested by that review. |
| Current Workbench lacks persistent edit/build/test workspace | Supported, explicitly proposed development scope. It does not establish a regression in the original research-session task count. |
| Attached roots are not indexed | Supported and explicitly excluded in the plan/capability record. This limits the product meaning of Attach; it does not alone prove violation of the owner-approved narrowed G3 gate. Include indexing as new work if full attached-root retrieval is required. |
| NULs in extracted PDF text caused export refusal | Supported by recorded cleanup and `checked_text`'s preflight binary guard. No evidence that a provider dispatch with NULs failed. Automatic blanket stripping would weaken the export guard and alter evidence. Use explicit, provenance-bearing text normalization before admission. |
| $0.0136 reservation is permanently orphaned | Unsupported as stated. An unresolved reservation exists in historical accounting; `delegate_ledger.py reconcile` can settle started/uncertain entries from receipts or verified charges. Unknown billability is a reason to retain a reserve, not refund it automatically. |
| All failures lack reservation settlement | Incorrect. The runner catches failures and settles known non-billable failures to zero while retaining reserves for uncertain outcomes. Abrupt process death still needs reconciliation. |
| Truncation without automatic continuation is a reliability bug | Truncation occurred, but it is recorded and returns nonzero by default. Bounded explicit follow-up is available; automatic paid retries/continuation are not inherently required and can corrupt structured output or exceed budgets. |
| UI/Obsidian behavior lacks qualification | Real-host ACCEPT-02 remains outstanding. These reviews did not perform that acceptance walk. Absence of prior audit is not proof of a rendering defect; generic rendering also need not contain literal workspace/audited labels in source. |

## G5 rerun claims updated

The supplied $4.16/partial-MiMo snapshot is stale. At HEAD `818f1a2`, both reruns have eight completed result rows. Independent recomputation from saved Session histories gives **25/74 current Tier A passes**, **16 valid audit-state folds**, and **16 saved restart-hash matches**. Saved closure-audit records check 25 passes and report zero failures. Metered rerun spend sums to **$1.78283**; the G5 ledger is **$4.69723 of $8**, including earlier runs and an estimated pilot. This is local accounting, not a provider invoice. See `rerun-recomputed.json`.

Stops are six idle, five max-turn and five settled as failed. No session completed with all requirements closed. The new run meets the recorded permissive measurement rule; that does not qualify general coding capability, high task-success rate, budgets under crashes or semantic correctness.

Transcripts show paid reruns were launched, and the source still contains the unstable test helper. A final clean independent suite was not established before the run by the reviewed evidence. The exact asserted test/audit chronology is not proved by the quoted summary. Closure audits normally happen after each generated session; saying the run began before its audit is not independently a protocol defect. Distinguish failure to establish a regression baseline from the ordinary sequence of execution then audit.

## Verification in this claim check

- `reproduce_additional_review.py`: validation duplicate/orphan behavior and aggregate-search metadata reproduced in disposable vaults, zero provider calls.
- Existing workspace/search tests plus the unstable wrong-source test: **20 passed in 2.89 seconds**. These pass despite the new counterexamples; no full suite was rerun.
- Saved G5 histories/receipts recomputed as above; no new provider evaluation or live crash experiment launched.
- No product code or gate state changed. The final remediation sequence is in `CONSOLIDATED-REVIEW-AND-REMEDIATION.md`.
