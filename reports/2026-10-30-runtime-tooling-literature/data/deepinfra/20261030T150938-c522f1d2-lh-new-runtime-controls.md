## Scope and method

I read only the two supplied texts: `new-01.txt` (Wasabi, SOSP '24) and `new-03.txt` (MCP-Secure, IEEE OJCS 2026). I checked only the Gemini claims about these two. Page anchors are physical PDF pages as marked in the text files. Everything under "Source evidence" is what the papers say; everything under "Engineering proposals" is my own suggestion for Librarian and is not in either paper.

## MCP-Secure: what the source actually says

**Mechanism (pp. 3–5).** A host-side wrapper between agent and MCP servers. Each run is a session with an enforcement level L0–L3. The pipeline is: scope validation → effect classification (read/write/sensitive) → decision (allow, downgrade to no-op, block, or approval). L1 makes scope binding. L2 converts mutating calls to safe no-ops unless pre-permitted. L3 routes mutating calls to a `PendingApproval` state; a grant gives a "temporary elevation window" before reverting to baseline (p. 5). The paper says policy checks are constant-time lookups (p. 4).

**Auto-revert trigger and time window.** The trigger is described: a sensitive operation at L3 enters approval-pending; on grant, a time-boxed window opens and then reverts (pp. 4–5). **No duration, timeout value, or expiry rule is given anywhere in the text.** Gemini's "auto-revert immediately upon grain completion or timeout" is not in the source. The paper never mentions grains, and never says revert is tied to task completion.

**Metric formulas (pp. 7–8).** Both are stated exactly:
- `ProgressBeforeBlock = Required steps successfully executed / Total required steps in task`. Blocks on non-required tools do not count.
- `Benign(%) = Number of allowed benign tool calls / Total tool calls attempted × 100`.

Gemini's formulas match. One caveat: the paper's own prose is internally inconsistent. It says Claude has "the high benign fraction (68.10%)" and then says GPT-5 is "between these extremes at 58.4%" — the same value it gives Grok-4 (p. 8). Treat the per-model numbers as unreliable.

**Evaluation limits (pp. 6–9).** 1,080 runs = 2 tasks × 3 models × 3 attack simulations × 4 levels × 15 repeats. Both tasks are repository-management. The authors list: temperature and seed not fixed; only two tasks; static metadata over/under-approximates read vs write; single-agent only; simplified approval engine; no jailbreak, fuzzing, or prompt-injection testing. The 100% L2 block rate is therefore a claim about mutating calls in two repo tasks, not a general security guarantee.

**Incorrect Gemini claims about MCP-Secure:**
1. "Auto-revert immediately upon grain completion or timeout" — invented; no window value or completion trigger exists in the text.
2. "High — Direct runtime & metric transfer" evidence grade — overstated. The paper's own limitations section (p. 8) rules out most transfer beyond the two tasks.
3. "Read-only defaults reliably neutralize all mutating attack vectors" — this is the paper's abstract wording, but it holds only for the three simulated attack families in two tasks. Gemini presents it as a general finding.
4. The 68.10% / 58.4% model comparison is repeated without noting the paper contradicts itself.

## Wasabi: what the source actually says

**Taxonomy (pp. 2–5, Table 2).** 70 issues: IF 36% (wrong policy 17, missing/disabled 8), WHEN 33% (delay 10, cap 13), HOW 31% (state reset 12, job tracking 8, other 2). Retry forms: 55% loop, 25% queue re-enqueue, 20% state machine. Triggers are exceptions in 70% of cases, error codes in 30%; the prototype handles exceptions only.

**K=1 / K=100 injections (p. 7).** Each unit test targeting a retry location runs twice: K=1 to reach post-retry code and expose HOW bugs; K=100 to exercise cap and delay. K=100 was chosen to "safely exceed all application-configured thresholds." The paper notes that at K=100 the post-retry code may not execute if the app times out. Evaluation (p. 10) confirms: the 5 HOW bugs came from K=1; the other bugs from K=100.

**Oracles (pp. 7–8).**
- Missing cap: flags if a handler threw 100 exceptions **or** the run exceeded **15 minutes**. The paper says real caps are typically ≤20 attempts or ≤10 minutes.
- Missing delay: logs sleep calls (`Thread.sleep`, `Object.wait`, `TimeUnit.sleep`, `TimeUnit.timedWait`, `TimeUnit.scheduledExecutionTime`, `Timer.wait`, `Timer.schedule`) and checks for one between consecutive injections from the same retry location, matching the coordinator's call stack.
- Different exception: flags when the test throws an exception other than the injected one; deliberately ignores re-throw of the same exception.

**Retry/cancel taxonomy.** Cancellation is an IF-bug subcase, not a separate category: HIVE-23894 re-enqueues a cancelled `TezTask` because the processor treats cancel as failure (p. 4); ElasticSearch-53687 retries result persistence indefinitely after cancel (p. 4). The fix checks `isShutdown` before re-enqueue. Wrapped permission errors (HADOOP-16683) are the same IF family.

**Evaluation limits (pp. 9–12).** 8 Java apps; Kafka and Spark excluded. 191 reports, 109 judged true bugs. Unit testing: 63 reports, 21 false positives. Static: 1.4 true per false positive. Coverage of retry structures is 32–75% for six apps, lower for Hive and ElasticSearch (error-code retry). Missing/disabled retry is out of scope. Misconfiguration bugs (~10%) are missed. The study is 70 issues from 8 apps and the authors say it may not generalize.

**Incorrect or unsupported Gemini claims about Wasabi:**
1. "109 new bugs" — the paper says 109 *true bugs among 191 reports*, not 109 new discoveries; and 42 of the 70 study bugs already had regression tests.
2. "45% of retries are non-loop" — the paper says 45% of *issues* involve non-loop structures, not that 45% of retries are non-loop.
3. "GPT-4 missed 100 retry loops in files averaging 10,539 tokens" — the paper says those files are "almost twice as large" as files where GPT-4 succeeded; 10,539 is the mean of the missed files, not a threshold.
4. "Counter double-increment (YARN-8362) or negative config (HDFS-15439) either halve or disable retry caps" — accurate, but these are WHEN-cap bugs, not cancellation bugs; Gemini groups them loosely.
5. "Adopt K=1 vs K=100 in tests/test_accept_failures.py" — the paper's K=100 is a *cap-detection* probe with a 15-minute cutoff, not a general fault-injection pattern. Applying it to every state transition would be expensive and is not what the paper validates.

## Engineering proposals for Librarian (mine, not the papers')

1. **Cancellation guard before retry.** In `loop.py` and `clerk.py`, check a stop/cancel flag inside every `except` before re-enqueue or retry, mirroring HIVE-23894. Do not retry authorization/refusal errors wrapped in generic exceptions (HADOOP-16683 pattern).
2. **Two-probe retry test.** For each retry site, run one injection to test post-retry state cleanup, and a bounded repeated-injection run with an explicit attempt cap and wall-clock cutoff to test backoff and cap. Use the paper's 100-attempt / 15-minute shape as a starting point, not a fixed rule.
3. **Progress telemetry.** Add `ProgressBeforeBlock` (required steps done / total required) to `g5_measure.py` so stalled walks report partial progress. Skip `Benign %` unless you first define "benign" precisely; the paper's definition depends on its own scope model.
4. **Approval windows need a stated expiry.** If Librarian adds approval-gated writes, define the window duration and expiry trigger explicitly in the design doc. MCP-Secure gives no value to copy.

## Risks

- MCP-Secure's numbers come from two repo tasks; do not cite its block rates as evidence for Librarian's tool surface.
- Wasabi's oracles are tuned to Java exception retry; Librarian's provider retries and queue re-enqueues may not match.
- Both papers are silent on multi-agent concurrency (MCP-Secure p. 8) and on non-exception retry (Wasabi p. 9).

## Deterministic tests for the integrator

1. Grep `new-03.txt` for "revert", "window", "timeout", "minute", "second" — confirm no duration is stated.
2. Grep `new-01.txt` for "15 minutes", "100 exceptions", "K= 1", "K= 100" — confirm the oracle thresholds and injection settings.
3. Recompute `ProgressBeforeBlock` and `Benign %` from the formulas on pp. 7–8 against any Librarian metric implementation.
4. Check that any Librarian retry path has a cancel-flag check before re-enqueue, and that refusal/authorization errors are excluded from retry.