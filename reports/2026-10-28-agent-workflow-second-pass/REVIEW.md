# Second pass of the agent-workflow research sprint

Reviewed 28 October 2026. Original work: `../2026-10-28-agent-workflow-sprint/00-summary.md` through `08-claim-register.md`, their scripts/data, the supplied completion transcript, relevant repository source and plan, and the research PDFs.

**Verdict: retain the evidence collection and most engineering directions; revise the quantitative conclusions and expand the literature synthesis before treating the sprint as a design baseline.** The work is useful, but “finished and verified” overstates its coverage. Several important errors survived its critic pass.

The best part is citation fidelity. I independently extracted all 50 distinct PDFs from `E:\Librarian research`, matched their hashes to the original inventory, and checked all 168 method cards. All **134 cards labelled verified match their exact claimed PDF page**, including all 103 verified primary-reader cards. None required the original verifier's one-page tolerance. This is a substantial positive result. It does not establish the accuracy of every other field on a card, the soundness of a paper, or completeness of extraction.

The most consequential corrections are below. See [LITERATURE.md](LITERATURE.md) for missed methods, limitations and reading priorities, and [CLAIMS.md](CLAIMS.md) for external-claim corrections. `data/` contains independent checks; the original reports, product source and vault notes have been left intact.

## Findings requiring correction

### F1. The delegation follow-up metric counts inspection commands as delegated results

**High priority.** `scripts/common.py:command_category` classifies a command as delegation whenever its text contains `delegate_deepinfra` or `api.deepinfra.com`. Reading, searching, editing and testing the runner can therefore create a “delegate result.” Both log parsers use this classifier.

I located all **62 Codex rows** in `data/codex_delegates.csv` in the source rollouts. **39 contain inspection signatures** such as `Get-Content` or `rg`. Only 17 contain both task and model flags; my conservative launch-signature detector matches 14. These last two counts are diagnostic, not corrected invocation totals: compound commands and failed launches still require adjudication. The original development receipts contain ten non-canary calls, nine completed.

There is a second independent error: a shell tool can return a running-process handle before the API finishes. All **12 task-name-matched shell-result rows** in my receipt comparison precede the associated receipt's terminal timestamp. The mapper is an obvious example: the original metric starts its window before the mapper result existed.

Consequently, withdraw the 33.4k Codex median, its 246k p90, the Claude 14.9k median pending the same repair, and the derived 6–8× “verification” ratios as estimates of delegation cost. Their arithmetic can be reproducible while their population and start times are wrong. Even a repaired post-result interval includes implementation, tests and unrelated work; it is not automatically verification labor.

**Repair:** identify invocations structurally; distinguish launch, process yield, polling, terminal completion and actual result consumption; join to `run_id`/receipt/output hash. Attribute work to task and lane, and prevent overlapping windows from double-charging the same requests. Compare total task cost against matched direct work before claiming savings or losses. Independent evidence: `data/delegate_classification_audit.csv` and `data/delegate_result_timing.csv`.

### F2. The Claude-versus-Codex review-finding split is misattributed

**High priority.** `finding_dispositions.csv` labels the four rejected findings attached to commit `33fb3b5` as Codex-side. But the commit says the implementation was ChatGPT's work, left uncommitted at a limit; **Claude commissioned the later review and committed the result**. The sprint's own `claude_librarian_v2_delegates.csv` records `encoder-review`, DeepSeek-V4-Pro, at **15:38:38Z**, returning at **15:39:18Z**. The commit followed at 15:46:56Z.

The Codex `index05_encoder_diff_critic` receipt is a different review, at **14:50Z**, on **DeepSeek-V4.1-Flash**, not DeepSeek-V4-Pro. Comparing it to the later four-finding review creates the purported mismatch.

Thus “75% Claude versus 0% Codex” does not describe who orchestrated these reviews. The pooled **6/12 remains a tally of recorded dispositions**, with incomplete denominators and report-level evidence. It is not an estimate of overall reviewer precision. Keep implementer, commissioning orchestrator, reviewer and committer as separate fields. Recover the later review artifact if available; otherwise retain a precise “artifact not located” limitation, rather than asserting the two reviews conflict.

### F3. Shadow cost underprices cache creation

**Medium priority.** The fitted rates distinguish ordinary input (4.98) from cache creation (7.98 dollars per million tokens), but `analyze_baseline.py` merges both into `fresh` and prices that whole bucket at 4.98.

Holding the original attribution and rounded fitted rates fixed, restoring the cache-creation component changes Claude's 24-change total from **$106.76 to $117.08**; the median changes from **$3.00 to $3.09**. This is a sensitivity calculation, not verified vendor billing. The same merged bucket also distorts the weighted token index.

Keep four token components through aggregation. Describe shadow dollars as modelled, not `[M]` actual spend. Source/check: `data/shadow_price_sensitivity.csv` and `data/metric_sensitivity.json`.

### F4. Resume/cache measurements do not establish recoverable handoff waste

The 502k and 135k figures describe fresh tokens around selected post-limit resumes under a heuristic action classifier. They include full prompt/cache reconstruction and the first productive request. They do not isolate rereading, lost knowledge or additional work caused by a handoff. A compact resume note inside the same restored conversation will not remove that conversation's history; a genuinely fresh context is a different treatment.

Keep the raw measurements with their definitions. Change “resuming costs the most” and “capsules avoid the cache rebuild” to hypotheses. Test **same task, fresh context plus capsule versus restored history**, including correctness, total role costs, cache writes/reads and time to a useful verified action. Measure task quality after that first action too. A quota percentage is account-wide and cannot be treated as a task price without accounting for other activity.

### F5. Rework and parallelism are proxies with incomplete follow-up

At an explicit review cutoff of **2026-10-28T21:00Z**, only **68/74** code commits have 24 hours of follow-up; **51/74** have 72 hours. The original two-of-73 rewrite statistic includes immature observations. Mark those censored and report mature-cohort rates separately.

Line survival is not correctness. Legitimate refactors delete good code; untouched bugs survive; pre-commit repairs are invisible. Counting inserted lines also poorly represents deletion-only fixes. “0–2 recorded fixes” is a provenance summary, not measured draft retention.

Likewise, 1.66 “parallelism” comes from request timestamps grouped with ten-minute gaps and a one-minute tail. It estimates overlapping activity, not speedup or efficiency. Permission errors do not demonstrate merge conflicts, and low rewrite rates do not establish that shared writable lanes are safe. Measure actual task spans, successful throughput and critical-path elapsed time separately.

### F6. Token-counter reconciliation remains incomplete

The original `determinism_check.json` already records two out-of-tolerance main rollout files, but excuses them with a note about fork inheritance. They are continuation files sharing main-thread IDs.

After grouping those files by logical thread, saved request sums exceed the largest cumulative counter by **2,081,984** and **954,735 total tokens**. The other **201 logical threads with token-bearing rows reconcile exactly**. Counter rollback, continuation semantics or duplicated usage could explain these differences; the current data does not distinguish them. This is not proof that all of that difference is overbilling or duplicate model work.

Document initial counter offsets and counter epochs, and reconcile requests within each logical thread before further cost comparisons. Source: `data/codex_counter_reconciliation.csv`. Re-running the same parser and getting the same CSV does not settle its interpretation.

### F7. Extraction completeness was constrained by the prompts, then largely unmeasured

The triage model screened first/last pages and headings. The method prompt allowed **at most six cards per paper**. The primary reader produced 108 cards for 18 papers, exactly six each. This is a useful bounded extraction, not evidence that useful content has been exhausted.

The final extraction table uses roughly thirteen papers, leaving even the highly ranked Embodied Tree of Thoughts without a row. It also excludes several directly useful adjacent sources; see the supplement. A high quote-match rate says nothing about methods not selected, truncated tails or entire unparseable calls. Report **call completion, parse success, quote fidelity, semantic support and coverage** separately, by lane; current per-model rates confound model, task and packet difficulty.

The claim that precision is automated should read “quote-location fidelity is automated.” Interpretation precision remains unmeasured. The 71% capture–recapture estimate is exploratory: independence, equal detectability and the definition of an event are not established. Cohen's kappa 0.45 measures label agreement, not error correlation; it cannot populate a verification-failure model.

### F8. The literature synthesis omits material costs, negative results and formal limitations

Examples requiring addition:

- ReflectiChain explicitly reports **68% extra tokens**, conservatism/throughput costs, heuristic drift estimates and unfaithful-rationale risk. Its own small CodeSim test reports **40% constraint compliance versus ReAct's 95%** (Table9, p18), a particularly relevant negative transfer result. Its printed SFI equation has unresolved scale/range issues; its contraction argument does not establish a ready-to-use safety guarantee.
- TMS's published PDF retains a code-repository placeholder and repeats one arXiv identifier for different cited works. Its reported results need a reproducibility caution, not just a “simulation” label.
- Embodied Tree of Thoughts measures verification as the dominant model overhead, and parallel rollout reduces one task's simulation time from 55 to 26 seconds.
- The policy-compiler paper finds that a matched fixed rule explains most stationary gains. Under structural change, its comparison also changes target re-resolution, so an adaptive deterministic baseline remains necessary.
- The knowledge-pack paper's useful result is **non-monotonic context utility**, not simply “more cache reuse is better.”

These affect the recommended defaults. The supplement gives sources and bounded applications.

### F9. Several external-claim verdicts need replacement

The OpenAI announcement is retrievable in this review. It confirms the 17-hour Lean phase via GPT-6 Astra, despite CL-014's “no source states” wording. It distinguishes run-specific counts from totals across all attempted problems, and distinguishes discovery from formalisation. An unnamed discovery model does not contradict a named formalisation model.

The claim register's regex rules operate on fragments rather than complete scoped propositions. Listing a model on an API is not verification that a proposed autonomous debugging workflow works. Finding a Vast controller is not proof its image includes JAX, CuPy and vLLM. Detailed corrections and individual dispositions for all 58 rows currently classified as outside claims are in [CLAIMS.md](CLAIMS.md) and `data/claim_review.csv`.

### F10. The architecture recommendations need clearer boundaries and acceptance tests

Most directions are sensible engineering choices even after weakening the baseline. Keep extending the existing runner, invocation model and Session/Core seams. But distinguish **implemented**, **planned** and **missing in development tooling**. The existing harness specification already defines a context capsule, and HARNESS-04/06 already cover bounded projections and exact quote-presence closure. “Absent everywhere” is too broad.

Make these concrete changes before adopting the rows:

| Proposal | Assessment | Required revision |
|---|---|---|
| DELEG-01 receipts/hygiene | Adopt first | Persist complete redacted request/contract plus manifest, schema and route identity; separate transport and acceptance states; link launch/process/result consumption. Idempotency must be atomic with reservation and use a renewable lease or timeout-derived expiry: a fixed ten-minute exclusion is shorter than the sprint's 900-second timeout. |
| DELEG-02 typed findings | Adopt with stronger semantics | Store exact source hash/offset, claim, evidence, falsifier and disposition separately. Quote-valid must not imply claim-supported. Preserve raw malformed/truncated output, repair provenance and missing-item status; salvage never proves completeness. |
| DELEG-03 scope/lint | Adopt | Check the candidate patch **before landing**, including deletes, renames and tests that could weaken acceptance; preserve an owner-approved test/oracle. Different model IDs are a procedural independence rule, not proof of independent errors. |
| DELEG-04 capsule | Prototype and test | Version/git/diff/receipt hashes, constraints, unresolved judgments and artifact references; fresh-context trial against restored history. Remove the asserted causal saving until E3 demonstrates it. |
| DELEG-05 closure/progress | Adopt narrowly | Reuse Session/event vocabulary and existing plan status. Permit explicit “no documentation change required”; a doc diff is not required for every legitimate fix. Do not make a 31k-token plan the canonical event database. |
| DELEG-06 executable gate | Move a small local pilot earlier | Use task-specific positive/negative fixtures, existing worktree isolation and explicit execution limits; keep the established Windows owner-host suite gate for sensitive paths. Passing self-authored tests is insufficient. |
| DELEG-07 quota scheduling | Defer automation | Start with observational status and replay. Available backlog, task dependencies and actual user demand matter; calendar idle is not recoverable productive time. |
| HARNESS-10 helper results | Fold into HARNESS-04/06 where possible | Reuse invocation usage/route fingerprints and Core-owned verification; keep raw-result handles before the current 4,000-character helper-answer cut. Read-only helpers keep their existing authority. |
| DELEG-08 isolation | Prerequisite for concurrent writers | Do not defer this until a scheduler exists. File ownership and worktrees help source changes; runtime vault writes still use the single Core writer/CAS. |
| DELEG-09 hosted compute | Conditional | Deadline, progress watchdog, checkpoint/collection and teardown after terminal failure; bounded retries for recoverable faults. “Destroy on first error” is too broad and can lose useful work. |
| DELEG-10 hygiene | Sensible after classifying artifacts | Ignore disposable/sensitive scratch data, but preserve the redacted evidence, contracts and artifacts needed to reproduce published results. No credentials were inspected or rotated in this review. |

Do not promote model-role routes from these quote-match percentages alone. Existing exact-route qualification and expectation records in `model_invocation.py` and role bindings are the appropriate enforcement seams; a new report ledger must not become a second runtime authorization or qualification system.

## Experiments should answer the intended question

Revise E1–E4 before running them. Precision alone favors reviewers that report almost nothing; include known defects, verified clean changes, false-positive burden, defect recall and severity. Historical reviews and repeated seeded variants need task-level paired comparisons, with uncertainty clustered by task.

“Ten paired packets, half gated” is ambiguous: a pair needs both treatments on the same baseline task, with order randomized and prior outputs hidden. Count packet preparation, delegate work, checking, repair and failed outcomes. For parallelism, repeat each concurrency level with matched work and report actual speedup/throughput, rather than fitting a scalability curve to four unreplicated points. For capsule tests, use the same handoff state in both conditions; compare correctness through completion, not only the first edit.

Add **E11 coverage and support audit**: create a manually adjudicated checklist of methods/limitations for a small stratified paper set; compare six-card extraction with section-guided extraction. Score missed methods, omitted limitations, claim support and correct abstention. Add the fixed-rule versus model-assisted dispatch comparison suggested by the policy-compiler paper. Those experiments directly address gaps left by the sprint.

## What remains trustworthy, and the scope of this review

The original inventory, saved quote matches, receipt anomalies and source pointers remain useful. Structured limit hits show a real continuity problem; idle intervals remain upper bounds. The strong directions are durable provenance, exact predicates, smaller reusable state, deterministic gates and bounded independent work. The current evidence does not establish a causal delegation advantage or disadvantage, a universal best model, or a validated drift alarm.

I screened the 50 distinct PDF sources, checked all saved method-card quotes, and read targeted method, result and limitation sections for the papers driving the findings. I inspected four rendered pages for formula/table fidelity. This is a relevance and interpretation review, not a replication of all experiments or a complete line-by-line peer review of 50 papers. The per-paper coverage ledger states the depth and decisions. I also inspected the original vault-note selection and the generated notes' pipeline; memory-written notes remain secondary unless their primary source was retrieved here.

No paid model calls, product changes, vault-note edits, commits or key access were needed. The checks write only to this new review folder. Run the independent scripts with the system Python that has PyMuPDF; they explicitly import the repository's `src` for quote normalization. No product release-test claim is made. Original deterministic scripts were inspected rather than rerun in place, since their hard-coded outputs would overwrite the evidence being reviewed.
