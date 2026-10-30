# Consolidated review and remediation plan

**Final synthesis — 2026-10-30.** Combines the original [code/gate review](REVIEW.md), [secondary-review fact check](SECONDARY-REVIEW-FACTCHECK.md), and the newly supplied [additional-review fact check](ADDITIONAL-REVIEW-FACTCHECK.md). Historical observations remain attributed to their tested revisions.

Source baselines: historical `fd715f1`, fix commit `a9be71b`, and current inspected HEAD `818f1a2` (G5 rerun documentation). Findings below distinguish reproduced historical failures, implementation changes and remaining qualification. No gate status or product code was changed to prepare this report.

## Overall assessment

The remaining local roadmap tasks have implementation work recorded. That does not establish feature completeness or measured code coverage. At `fd715f1`, six executable counterexamples exposed four high-priority closure/read-boundary defects and two medium-priority visibility/budget defects despite a passing suite. `a9be71b` subsequently adds fixes and regression tests; the old findings must not be presented as proof that the same failures persist at current HEAD.

Release freeze should wait for current-revision qualification and the newly reproduced validation/search issues. The wrong-source regression fixture is unstable: an independent 184-test selection failed it, while a later 20-test selection passed it. It has not been repaired. The corrected G5 run now exists and its 25/74 count reproduces; do not repeat it merely because earlier fact checks predated it. Workbench lifecycle containment and provider accounting/recovery still need qualification. Existing owner gate decisions remain recorded; flag affected assurance and record gate changes in the authoritative plan.

## Evidence by revision

| Evidence | Revision/scope | Established result and limits |
|---|---|---|
| Full non-slow suite | `fd715f1`, checkout source | 1,848 passed, 1 skipped, 5 deselected. Does not qualify later code. |
| Original defect reproductions | `fd715f1`, disposable vaults | Wrong-source closure, changed-draft verification, contract read bypass, junction traversal, file visibility and simulated budget overrun. No paid overrun or host write escape demonstrated. |
| G5 saved data | Original 16-session run | 32/74 current Tier A passes, 15/15 recorded restart-hash matches, $2.3665 metered full-run spend, 115 MiMo t5 questions. No fresh crash/recovery run during these reviews. |
| Fix implementation and tests | `a9be71b` | Subject bindings, contract-specific results/reductions, artifact replacement invalidation, read checks, common traversal visibility and pre-call budget control added. Presence of a fix is distinct from completed qualification. |
| Independent affected-suite run | `a9be71b`, eight modules | 183 passed, 1 failed, 1 deselected in 66.67 seconds; the failing wrong-source test also failed alone. |
| Explicit binding check | `a9be71b`, disposable vault | Source A explicitly bound; source B rejected by runtime. Supports the guard while identifying the test fixture as faulty. |
| New existing-test selection | `818f1a2`, workspace/search plus wrong-source fixture | 20 passed in 2.89 seconds. The fixture passing on this run does not cure its demonstrated order dependence. |
| Corrected live G5 saved results | Execution under `a9be71b`, reported at `818f1a2` | 25/74 Tier A passes, 16 valid folded histories, 16 saved restart matches, 25 saved audit checks with zero failures, $1.78283 rerun spend. Independently recomputed saved records, not new live recovery tests. |
| G5 ledger | Snapshot at `818f1a2` review | $4.69723 of $8, including earlier runs and an estimated pilot; separate from the research/delegation pool. |
| Current final full suite | Pending | A final full green run on the assembled candidate was not established by these checks. |

## Consolidated finding register

| ID | Historical issue | Current evidence | Remaining action |
|---|---|---|---|
| F1, P1 | Verifier inputs could establish a different subject from the requirement | Person-bound subjects and rejection added; direct explicit-binding check succeeds | Fix unstable fixture; qualify typed subject, expected value and verifier scope. A quote on the right source still does not establish arbitrary semantic/numeric meaning. |
| F2, P1 | New contracts reused results and could replace verified drafts without staleness | Contract-specific results/reductions and artifact-replacement epoch bump added | Qualify same/new contract changes, acceptance invalidation, restart and other mutation routes. Preserve unchanged-evidence reuse only under explicit validity rules. |
| F3, P1 | get_note escaped declared contract read scope | Resolved note/evidence checks added; affected tests included in current run | Qualify tools' actual resolved resources and recorded dependencies; avoid argument-name heuristics as the general contract. |
| F4, P1 | Adopted scanner followed Windows junctions outside scope | Shared reparse-aware visibility added | Verify indexing and watcher use the same boundary on supported Windows hosts; exercise junctions, symlinks, cycles and access-time changes. |
| F5, P2 | Explicit file exclusions and hidden Markdown entered indexing | Shared file/directory visibility added | Qualify nested/file exclusions and consistency between survey, index and watcher. |
| F6, P2 | Paid-run budget checked only after multiple calls | Pre-call estimate guard and locked shared run ledger added | Qualify input/output accounting, retries, unknown usage, termination, durable reservations and cross-run recovery. |
| F7, reporting | t6 partial requirement incorrectly described as never addressed | Dated correction exists | Carry corrected narrative into new results; retain original evidence. |
| T1, current test defect | Wrong-source test chooses evidence by storage order | `requirements(lead)` uses `stored[0]`; records sort by hash-derived filename | Bind intended fixture identity explicitly. Then rerun affected suite. |
| U1, usability | Rephrased questions bypass reuse guard | Original run recorded 115 questions; current normalized-text guard remains | Introduce bounded clarification/no-progress handling without inventing user answers. |
| U2, usability | High admission refusal rate | 254 admission/event refusals in original run | Improve stable predicate references and structured contract construction; preserve full preflight. |
| V1, P2 | Adopted validation misclassifies foreign-frontmatter docs and drops plain-document links | Reproduced duplicate frontmattered READMEs and a false orphan despite a workspace link | Shared classification and full visible link accounting; distinguish foreign docs from managed notes without relying solely on folder/frontmatter presence. |
| S1, P2 | Aggregate search reports source-only metadata over mixed results | Reproduced workspace hit with top-level uncovered/zero considered | Per-group filters and metadata plus an honest aggregate contract; update workspace guidance. |
| W1, high priority | Workbench imports outputs before enforcing size limits; helpers have weaker explicit restrictions | Source inspection confirms; prior review already carried these concerns forward | Bound writes/import before host materialization and qualify all execution phases. No container escape or disk-exhaustion exploit was run. |
| C1, policy/compatibility | Plain file in Sources becomes workspace document; legacy audited logs replay invalid | Both behaviors confirmed and previously documented | Define managed identity/classification and legacy evidence policy. Neither can be fixed safely by guessing from paths or trusting old closures. |

## Remediation sequence

### R1 — Repair deterministic evidence and adopted-document correctness

Change the test helper to receive the intended evidence ID explicitly instead of selecting the first stored record. Cover both record creation orders and both permitted/refused subjects. Share classification between index, validation and status: current `shape_of` does not return workspace_document, so the proposed one-line replacement is ineffective. Drive managed identity from explicit provenance or a user-declared policy; define how an existing managed note remains identifiable if metadata is lost. Collect visible names/links before any schema exemption; avoid duplicate-name rules for ordinary documentation and use an exclusion-aware inventory that still supports non-Markdown attachments.

Fix aggregate search's response contract: expose per-group considered/matched/verdict/filter applicability, update guidance, and avoid reporting source-only uncovered metadata as the complete answer. Source-license/age filters do not automatically make sense for every other shape. Reject or explain unsupported parameter combinations rather than silently treating a source selector as universal scope.

Add regression cases from the new disposable-vault reproduction. Rerun affected suites, then the full non-slow suite once final fixes are assembled. Record revision, import identity, command, skips and failures. Exit: stable source identity selection, correct mixed-document link/schema behavior, coherent grouped search and a repeatable green candidate suite.

### R2 — Qualify closure meaning, lifecycle and compatibility

Check source/note/run bindings, scope completeness and expected values. Keep semantic interpretation and uncheckable numeric claims partial or human-judgment. Verify that changes invalidate affected verification and acceptance through Core and external paths, across restart and contract boundaries. The conservative epoch model is sufficient for this remediation; a full dependency/taint graph is optional follow-on work.

Old histories lacking contract IDs on verified reductions now replay invalid. Preserve them with their original revision and declared read/review path. Do not silently mutate original logs or present a replay failure caused by the format change as newly discovered historical corruption. Exit: explicit compatibility decision and tests for valid new histories, invalid histories, interruption and stale results.

### R3 — Qualify filesystem and execution accounting boundaries

Exercise the shared traversal rule at every depth for indexing and watching. Check resolved resource access rather than only requested strings; explicitly define discovery searches' authority. Before release qualification, bound Workbench output growth/import and snippet-sandbox landing growth while work runs, not only in cleanup. Validate exported paths/types before host materialization. Apply a documented isolation policy to provisioning, extraction, execution and export helpers. Setup may need a narrow privileged operation; copying execution flags without checking provisioning needs is insufficient. Test process descendants, quotas, cancellation and cleanup on supported Windows/Docker/WSL configurations. No new live attack was run by these fact checks.

The current G5 guard is a pre-dispatch estimate, and its ledger has no durable per-call reservation. For provider accounting, show that each billable dispatch, including retries, has an adequate reservation; unknown usage prevents further spend and crash recovery retains unresolved charges. The current token estimate needs a demonstrated relation to actual serialized provider requests. Use durable per-call reservation/settlement for the G5 runner or reuse the existing ledger service; do not add a third incompatible accounting policy.

The delegation runner already rejects NUL-containing input before dispatch, classifies failures, marks truncation and supports reconciliation. Keep these safeguards. If PDF cleanup is useful, make it an explicit normalized artifact with original/normalized hashes and transformation metadata. Never refund uncertain billable requests automatically. Retry or continuation requires a new bounded admission; it is not an automatic correctness repair.

Exit: benign tasks remain usable and injected boundary/accounting failures stop safely, with evidence tied to the tested host and route. The current Workbench import/lifecycle gaps should block claims that those resource boundaries are fully enforced until corrected or explicitly excluded from the qualified offering.

### R4 — Bound unproductive interaction and simplify admission

Track clarification/no-progress across answered as well as unanswered questions: the fixed-answer protocol immediately answered the original loop. On exhaustion, preserve constraints and park dependent work or continue only independent authorized work. Do not adopt the secondary review's unevaluated quota of two or similarity threshold of 0.65 as universal defaults. Similarity may flag repetition but cannot substitute for a consequential user decision.

Expose stable predicate references, eligible verifier/input schemas, bound targets and structured refusal details. Generate mechanical contract fields where possible. In the corrected run, the report counts 616 admission refusals, including repeated MiMo proposals omitting verifiers; this warrants interface work rather than weakening the checks. Fill omitted deterministic values only from an existing person's binding, never overwrite a conflicting proposal. Only normalize semantics-preserving differences and rerun full admission after repair. Exit: scripted loop/refusal cases terminate predictably, and a bounded pilot shows lower wasted effort without weaker admission.

### R5 — Re-measure and reconcile gates

Preserve the original 32/74 measurement and completed corrected 25/74 measurement as distinct evidence. Saved records support the latter's four recorded conditions: valid histories, zero detected false closures, restart-hash matches and reported share/interval. The rule has no minimum share and does not require all requirements to close. No end-to-end success was demonstrated; human synthesis acceptance was absent and some authoritative requirements also remained unresolved or failed. Reuse this narrow evidence for unchanged tested behavior, without promoting it to semantic correctness, crash-safe accounting or general capability qualification. After fixes that affect admission, closure or accounting, predeclare and run only the affected slices first; broaden evaluation when those results or changed scope justify it. Follow existing approved budget limits and scope for any provider expenditure.

Report legitimate task progress, per-predicate correctness, integrity, refusals, question counts, cost, failed/idle stops and restart results. Distinguish reruns from independent checks; describe correlated-grain intervals as nominal. Reconcile G3/G5 assurance and release readiness against the exact revision and evidence. Source identity, lifecycle, real-host acceptance and later signing/publication gates retain their established requirements.

## Review/workflow corrections

The evidence does not establish that particular open-weight models drafted these modules or caused the bugs. Earlier delegation elsewhere in the project is insufficient attribution. Future workflow assessments should cite task receipts, source/output identities and integration decisions before assigning authorship or causal responsibility.

Existing tests included meaningful negative cases; describe the specific omitted adversarial bindings and lifecycle transitions rather than calling the whole suite happy-path-only. Have a reviewer derive counterexamples from requirements independently of implementation. Track release claims by revision and evidence type, so an old passing count cannot be reused for changed code.

The hardened [development-agent profile](../../docs/development-agent-harness.md) remains proposed scope. Completion or requalification of HARNESS-01–07 does not establish the persistent edit/build/test workspace, development authorization or publication controls described there. Scope that work explicitly before advertising hardened coding-agent capability. Attached-root indexing is also a documented exclusion: add it as explicit work if full retrieval from attached roots is required. ACCEPT-02 still requires the real Browser/Obsidian/Cowork environment and rollback walk; no UI rendering failure was proved merely by noting the lack of a prior audit.

## Release recommendation

Do not equate either a passing count or the G5 decision rule with whole-product release readiness. Prioritize R1's reproducible correctness fixes and W1's enforced execution boundaries, then complete lifecycle/accounting qualification and the final candidate suite. Record the exact accepted revision and qualified capability scope before the existing R0 source-identity/lifecycle checks. Gate reopening/reclosure remains an explicit owner decision, with this evidence attached; neither supplied review automatically changes the authoritative plan.

Evidence artifacts added in the latest check: [additional reproduction](reproduce_additional_review.py), [rerun recomputation](rerun-recomputed.json) and [detailed claim dispositions](ADDITIONAL-REVIEW-FACTCHECK.md). All reproduced examples used disposable data; no new paid evaluation was launched.

## Independent synthesis critique

### Follow-on: Librarian's own tools and newly added papers

The subsequent [runtime-tooling claim review](../2026-10-30-runtime-tooling-literature/TOOLING-CLAIM-REVIEW.md) checks the full transcript's last two Gemini responses against Librarian's own Registry, profiles, bundles, macros and workflows. It also reviews all eight PDFs added after the original 51-file corpus. It confirms that cancellation already exists, audit projection has not replaced compacted transcript history, registered capabilities are not automatically offered in audited phases, and contracts can cover multiple grains. Its recommendations refine R2–R4: deterministic contract construction, progress-aware stall handling, reachability/retry/failure tests, and a user-facing predicate inspector. Semantic auditing, screening and active example selection remain bounded experiments; no automatic permission bypass, taint-graph requirement or fixed paper-derived threshold is adopted.

DeepInfra supplied a bounded critique (`20261030T145345-14daffdd`), preserved under `deepinfra/`. Accepted clarifications: make classification authority explicit, state the missing durable G5 per-call reservation directly, and limit reuse of the corrected G5 evidence. Other suggestions largely repeated existing cautions. Rejected factual descriptions: the G5 rule is not a minimum-share threshold; `source` is not forwarded by `_everything` at all; session epochs are not implemented in search.py. Model suggestions were checked against source and did not become evidence by themselves. This call cost an estimated $0.0066882; research-pool commitments are $0.36983755 of $8 including the earlier unresolved reserve, separate from the G5 ledger. No provider evaluation was launched by this review.
