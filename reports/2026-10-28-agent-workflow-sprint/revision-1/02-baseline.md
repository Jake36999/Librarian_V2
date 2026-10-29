# Baseline from the existing evidence (deliverable 2)

Date: 2026-10-28. Window for limit analysis: 2026-10-24T09:00Z to 2026-10-28T16:00Z (103 hours). Population: 118 commits on master (104 in the window); development side only. All values come from `data/baseline_metrics.json` and the CSVs beside it. Tags: **[M]** measured, **[R]** reported, **[U]** outside claim. The sprint's own Claude sessions are excluded; they are reported as self-metrics in `00-summary.md`.

## Headline

| Metric | Baseline | n | Interval or spread | Tag |
|---|---|---|---|---|
| M1 Claude, tokens per accepted change | fresh 27.9k, output 13.2k, cache-read 9.6M; 18.5 requests | 24 | weighted index median 603k (IQR 297k to 1.15M) | M |
| M1 Codex, tokens per accepted change | fresh 244k, output 43.3k, cache-read 12.4M; 69 requests | 37 | weighted index median 942k (IQR 517k to 1.40M, p90 2.88M) | M (weights from Claude prices) |
| M2 Claude shadow dollars per change | median $3.00, mean $4.45, total $106.8 | 24 | IQR $1.48 to $5.73 | M (client-computed list price) |
| M2 DeepInfra spend, development side | $0.155 (shared ledger, 10 real calls) + $0.546 (Claude, one aggregated row) = about $0.70 | 5 days | rate-card estimates, not invoices | M |
| M3 line survival at HEAD | median 0.98 | 74 | IQR 0.94 to 0.99 | M |
| M3 changes with at least 30% of lines rewritten in 24 h | 2.7% | 73 | 2 commits | M |
| M3 reverts | 0 | 74 | | M |
| M4 review findings upheld, commit-recorded | 6 of 12 = 50% | 12 | Wilson 25% to 75% | R, fixes visible in diffs |
| M5 both agents limit-blocked | up to 59 h of 103 h (57%) | window | upper bound | M |
| M5 Codex bursts ending in a limit | median 28.5 min | 23 | IQR 20.9 to 35.2, mean 36.8 | M |
| M5 Codex idle after a limit | median 4.62 h | 38 | IQR 3.67 to 8.40 | M (upper bound) |
| M6 Claude resume after a limit | 502k fresh tokens, 2 requests | 3 | IQR 467k to 631k | M |
| M6 Codex main-thread resume after a limit | 135k fresh tokens, 4 requests | 21 | IQR 62k to 171k | M |
| M7 orchestrator follow-up per delegate result | Claude 14.9k, Codex 33.4k fresh+output tokens | 31 / 62 | p90 48k / 246k | M |
| M10 Codex parallelism | 1.66 mean, peak 6 threads | 148 workers with token counts (149 worker rollouts) | orchestration 12.6% of tokens | M |
| M11 compactions per 100k output tokens | Claude 0.14, Codex 1.96 | | | M |
| M12 delegate calls truncated at the output cap | 4 of 9 completed = 44% | 9 | Wilson 19% to 73% | M |

## Findings

**1. The binding constraint is quota, not dollars.** DeepInfra spend on development was about $0.70 in five days, while Claude was locked out for 62 hours (weekly limit hit 2026-10-26T01:00Z, reset 2026-10-28T15:00Z) after two 5-hour limits (2.6 h and 1.0 h). Codex hit 59 unique usage-limit turns in nine days (11, 5, 0, 3, 8, 9, 5, 14, 4 per day from Oct 20; plan type `plus`). In the 103-hour window Claude was blocked for 65.6 h (63.7%), Codex idle after limit events for up to 73.7 h (71.5%), and both for up to 59.0 h (57.3%). That last figure is an upper bound because Codex idle time includes hours when you were away.

**2. Codex works in short bursts.** Bursts that end in a limit have a median of 28.5 minutes (mean 36.8) and are followed by a median 4.6-hour wait. The earlier statement "a limit every 30 to 40 minutes, about five-hour waits" matches the measurement (see conflicts below).

**3. Cache reads dominate tokens, and resuming means rebuilding them.** Cache reads are 99.1% of Claude's input tokens and 97.1% of Codex's. After a limit stall the first Claude request rebuilds the cache: median 502k fresh tokens (about $4 at the fitted cache-write price). After a compaction it is 104k (n=1). Codex's main thread pays 135k after a limit and 58k after a compaction. The unified plan a fresh session would read grew from 13.2k to 31.1k tokens over 42 versions; §19 alone is 17.6k.

**4. Parallelism is real but costs quota.** Codex's spawned workers ran at 1.66 mean parallelism (peak 6) and used 46% of all fresh+output tokens (main 44%, guardian review threads 9.5%). Orchestration calls alone are 12.6% of tokens. Only 4 of 325 rollouts are top-level threads: 149 are workers and 172 are guardian reviews (148 workers and 53 guardian threads recorded token counts of their own). Compaction is 14 times more frequent per output token in Codex than in Claude.

**5. Delegation did not measurably cut orchestrator tokens.** Claude changes that involved a delegate (n=14) have a median weighted index of 603k, those that did not (n=10) 701k, with overlapping spread; output tokens were higher with delegation (15.8k against 8.4k). After a delegate result arrives, Claude spends a median 14.9k fresh+output tokens (8 requests, 4.6 min) and Codex 33.4k (17 requests) before moving on, against a median delegate output of 4,000 tokens in the 9 Codex receipts (several sit at their cap) and 2,425 tokens in the one Claude example whose size was recorded: about 8.3 times (Codex) and about 6 times (Claude, a single example) the size of the output being checked. T_direct cannot be observed, so this is not a proof of loss, only an absence of visible saving.

**6. Delegate drafts and delegate reviews behave differently by task type.** Claude landed 9 delegate-drafted commits (ADAPT-04 to 08, the runner, the liveness check, the IndexService desk-lookup change) with 0 to 2 recorded fixes each; the adapter drafts were checked by golden fixtures captured before the change. Codex's two mapper, builder, critic chains produced no accepted builder output: the Qwen patch was rejected locally (initialisation order, legacy semantics, test patch) and the second builder call timed out at 181 seconds. Critic and mapper calls were useful (the GLM critic correctly rejected the Qwen draft). The final correction came from local measurement.

**7. Review hold-up is about half in the pooled commit record, but the split is large.** Counts transcribed from commit text: Claude-side reviews 6 upheld, 2 recorded rejected (6 of 8 = 75%, Wilson 41% to 93%, an upper bound because three events record only the fixes); Codex-side encoder review 0 upheld, 4 rejected (0 of 4, Wilson 0% to 49%). Pooled 6 of 12. Model-labelled dispositions in the two development transcripts (un-adjudicated, mixed reviewers) give 26 upheld, 13 partial, 9 rejected of 48: 54% strictly upheld, 81% upheld or partial.

**8. The delegation instrumentation is itself unreliable.** Of 10 real calls: one call finished but stayed `started` in the ledger (its reserve is still charged); a retry began 55 seconds after the first, before it completed, and was itself truncated; 4 of 9 completed calls hit `finish_reason = length`; one call failed and is charged at its reserve, not metered usage; the runner's input estimate (characters ÷ 3.5) is 27% high; the 9 completed calls took 22 to 98 seconds and one call timed out at 181 seconds (p90 over all 10 calls: 106 seconds). Three of eight rate cards are stale against DeepInfra's live listing: GLM-5.3 is half the live price, and DeepSeek-V4.1-Flash is 1.4 to 2 times too low [verified 2026-10-28T17:05Z at `https://api.deepinfra.com/v1/openai/models`]. Per-call receipts for 2026-10-24 to 27 are missing; they survive only as 31 delegate invocations in Claude's log and as one aggregated ledger row.

**9. Hosted compute (prior art in `G:\vast`).** Seven rentals, 31 jobs collected, $13.62 spent ($0.44 per job) over 15 hours; the cap was raised from $13.50 to $14.00 mid-run. Boxes A and B produced nothing and were rented about 14 hours each (an estimated $4.46, a third of spend): a step error was logged at 05:24 but the boxes were destroyed at 19:29. Thirteen of 16 pre-registered predictions passed automatically. Provisioning (rent to runner up) took 4.6, 5.6 and 5.5 minutes on the three boxes where the log shows it.

## Measured against reported

| Statement | Source | Measurement | Verdict |
|---|---|---|---|
| Delegated review findings held up about half the time | Claude's end-of-session summary, 2026-10-28T16:10Z [R] | 6 of 12 in commit text (Wilson 25 to 75%) | Supported as a pooled figure; hides 75% (Claude side) against 0% (Codex encoder review); n too small |
| Codex hit its usage limit every 30 to 40 minutes, with about five-hour waits | same [R] | bursts median 28.5 min (mean 36.8), idle median 4.6 h | Supported |
| The orchestrator's tokens went on checking | brief [R] | about 8.3 times the delegate's output (Codex, 9 receipts) and about 6 times (Claude, one recorded example) | Supported as a ratio; whether net negative is unmeasured |
| Both agents hit usage limits often | brief [R] | Claude 3 hits including a 62-hour lockout; Codex 59 turns | Supported; Claude's lockout was not mentioned anywhere in the brief |
| The `33fb3b5` review had "four findings" | commit text [R] | the only matching receipt lists a SHIP verdict and five residual risks | Unreconciled (a missing receipt or loose paraphrase) |
| Gemini: a 943,000-token compaction | Gemini review [R] | research session compaction 2026-10-21: 969,271 to 26,310 tokens (942,961 dropped) | Verified |
| Gemini: the whole history is re-processed every turn (50k to 100k+ tokens) | Gemini [R] | cache reads are 99.1% of Claude input; client-inferred cache-read price is about 4% of fresh input; peak context 966k | Mechanism true, cost overstated |
| Gemini: $0.59 to $1.03 per batch, 37 notes for $1.03 | Gemini [R] | "$1.03" appears once in research tool output ("14 DeepInfra $1.03"); $0.59 and the per-batch framing not found | Partly |
| Gemini: tools 133 to 11, 15,813 to 1,241 tokens, -92.2% | Gemini [R] | `reports/2026-10-26-adapt11-tool-surface.md` | Verified |
| Gemini: DeepSeek-R1, Qwen-2.5-Coder-32B, Llama-3.3-70B are the cheap workers | Gemini [U] | R1 (R1-0528) and Llama-3.3-70B-Instruct-Turbo listed; Qwen-2.5-Coder-32B not listed (2026-10-28) | Partly |
| Gemini: new FanOutDispatcher, LeaseWatchdog, DeferredQuestionQueue, EngagementPlanner, telemetry bus | Gemini [R] | equivalents exist in some form, see `06-design-proposals.md` | Largely duplicates of existing parts; `pace.py` is not pacing (it is `set_effort`) |
| Claude spent too little on DeepInfra and hoarded 90% of the labor | Gemini [R] | not measurable from the provided data | Not tested |

## Caveats

- Codex "observed idle" includes time you were away. The weekly quota fit mixes Claude-derived weights with Codex tokens and is an exchange rate, not a price.
- The 16 unjoined commits are 13 from 2026-09-29 to 10-04 (before the available logs for this repository), one on 10-23 and two PR merges.
- Model-labelled transcript events are tier R. Their anchors are verified; their labels were not individually adjudicated.
- `claude-ledger.json` reports $0.5457 of earlier spend as one row with no per-call detail.
