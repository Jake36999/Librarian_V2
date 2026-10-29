# Baseline from the existing evidence (deliverable 2, revision 2)

Date: 2026-10-28 (revised the same evening after a second-pass review; the first-pass file is kept in `revision-1/`). Window for limit analysis: 2026-10-24T09:00Z to 2026-10-28T16:00Z (103 hours). Population: 118 commits on master (104 in the window); development side only. All values come from `data/baseline_metrics.json` and the CSVs beside it. Tags: **[M]** measured by a re-runnable script, **[R]** reported in prose, **[U]** outside claim. The sprint's own Claude sessions are excluded; they are reported as self-metrics in `00-summary.md`.

**What changed in revision 2.** The delegation-cost metric of the first pass counted commands that merely mentioned a runner (reading, searching, editing, testing it) as delegate results, and started every follow-up window when a shell call returned, which for a backgrounded or yielding launch is before the answer exists. Delegation calls are now rebuilt from the runners' own records and joined to the launching command, the call's real end and the first re-read of its output (`scripts/delegate_events.py`). Cache creation is priced separately from ordinary input. The review-finding split was misattributed and is withdrawn. Rework figures separate mature from still-maturing commits. Section "Changes from the first pass" lists every number that moved.

## Headline

| Metric | Baseline | n | Interval or spread | Tag |
|---|---|---|---|---|
| M1 Claude, tokens per accepted change | fresh 27.9k (all but about 50 tokens of it is cache creation), output 13.2k, cache-read 9.6M; 18.5 requests | 24 | weighted index median 620k (IQR 309k to 1.30M) | M |
| M1 Codex, tokens per accepted change | fresh 244k, output 43.3k, cache-read 12.4M; 69 requests | 37 | weighted index median 942k (IQR 517k to 1.40M, p90 2.88M) | M (weights taken from Claude prices; an exchange rate for comparison only) |
| M2 Claude shadow dollars per change | median $3.09, mean $4.88, total $117.1 | 24 | IQR $1.54 to $6.48 | modelled from client-computed list prices (not billing; the plan bills by quota) |
| M2 agents' DeepInfra spend, 24 to 28 Oct | about $1.15 across 57 recorded calls: Codex runner $0.155 (ledger; one failed call charged at reserve), Claude `delegate.py` $0.546 (25 calls), Claude `second_reader.py` about $0.447 (20 calls, in no ledger) | 57 calls | rate-table estimates, not invoices | M |
| M3 line survival at HEAD | median 0.98 | 74 | IQR 0.94 to 0.99 | M (a proxy, not correctness) |
| M3 changes with at least 30% of lines rewritten in 24 h | 3.0% (2 of 67 with 10 or more inserted lines and 24 h of follow-up) | 67 | 6 of 74 commits are too recent to judge | M |
| M3 changes with any line rewritten in 72 h | 82% (42 of 51 with 72 h of follow-up) | 51 | 23 of 74 commits too recent; ordinary later edits count, so this is weak | M |
| M3 reverts | 0 | 74 | | M |
| M4 review findings upheld, as recorded in commit text | 6 of 12 = 50% | 12 | Wilson 25% to 75%; three of the five events record only the upheld findings, so 50% is an upper bound | R, fixes visible in diffs |
| M5 both agents limit-blocked | up to 59.0 h of 103 h (57.3%) | window | upper bound (Codex idle includes your absences) | M |
| M5 Codex bursts ending in a limit | median 28.5 min | 23 | IQR 20.9 to 35.2, mean 36.8 | M |
| M5 Codex idle after a limit | median 4.62 h | 42 | IQR 3.67 to 7.86 | M (upper bound) |
| M6 Claude, tokens in the first requests after a limit | 502.5k fresh, 2 requests; the whole of it is cache creation (about $4.0 at the fitted $7.98 per million) | 3 | IQR 467k to 631k | M (contains the cache rebuild and the first productive request; not isolated re-reading) |
| M6 Codex main thread, tokens in the first requests after a limit | 136k fresh, 5 requests | 21 | IQR 62k to 178k | M (same caveat) |
| M7 work-packet delegation, post-result interval | Claude: median 8.4 min, 8 requests, 11.6k fresh + 5.6k output tokens; Codex: 7.6 min, 19.5 requests, 19.8k fresh + 5.4k output | 19 / 6 batches (25 / 9 calls) | the interval ended at a commit in 18 of 19 Claude batches but in only 1 of 6 Codex batches | M (descriptive; **not** verification cost) |
| M10 Codex overlap | 1.66 mean active threads, peak 6 | 148 workers with token counts | orchestration calls are 12.6% of tokens | M (a proxy for overlap, not speedup) |
| M11 compactions per 100k output tokens | Claude 0.14, Codex 2.0 | | | M |
| M12 delegate calls truncated at the output cap | 4 of 9 completed Codex-runner calls = 44% | 9 | Wilson 19% to 73% | M |

## Findings

**1. The binding constraint is quota, not dollars.** Agents' recorded DeepInfra spend over the five days was about $1.15, against a 62-hour Claude lockout (weekly limit hit 2026-10-26T01:00Z, reset 2026-10-28T15:00Z) after two 5-hour limits (2.6 h and 1.0 h). Codex hit 59 unique usage-limit turns in nine days (11, 5, 0, 3, 8, 9, 5, 14, 4 per day from Oct 20; plan type `plus`). In the 103-hour window Claude was blocked for 65.6 h (63.7%), Codex idle after limit events for up to 73.7 h (71.5%), and both for up to 59.0 h (57.3%). The last two are upper bounds because Codex idle time includes hours when you were away, and calendar idle is not recoverable productive time.

**2. Codex works in short bursts.** Bursts that end in a limit have a median of 28.5 minutes (mean 36.8) and are followed by a median 4.6-hour wait. The earlier statement "a limit every 30 to 40 minutes, about five-hour waits" matches the measurement (see below).

**3. Cache reads dominate tokens; the first requests after a limit are mostly cache creation.** Cache reads are 99.1% of Claude's input tokens and 97.1% of Codex's. After a limit stall the first Claude requests re-create the prompt cache: a median 502.5k tokens, all cache creation (n=3), about $4.0 modelled at the fitted cache-creation price. After a compaction it is 104k (n=1); Codex's main thread uses 136k after a limit and 62k after a compaction. These figures are the tokens before the first edit, commit, delegation or test under a rule-based action classifier. They include the full prompt rebuild and the first productive request, so they are **not** an estimate of waste from a bad handoff, and a compact note inside the same restored conversation would not remove the history it sits in. The unified plan a fresh session would read grew from 13.2k to 31.1k tokens over 42 versions; §19 alone is 17.6k.

**4. Parallelism overlaps, and costs quota.** Codex's spawned workers show a mean overlap of 1.66 threads (peak 6) and used 46% of all fresh+output tokens (main 44%, guardian review threads 9.5%). Orchestration calls alone are 12.6% of tokens. Of the threads that recorded token counts, 2 are top-level, 148 are workers and 53 are guardian reviews. The 1.66 figure is built from request timestamps (gaps over 10 minutes split activity, plus a one-minute tail); it estimates overlap, not speedup, throughput or the share of agent time used. Permission errors in tool output (43 git permission-denied, 8 `index.lock`) show friction, not merge conflicts, and a low rewrite rate does not show that shared writable lanes are safe.

**5. Whether delegation saved orchestrator tokens cannot be estimated from this data.** The repaired measure is the *post-result interval*: from the first re-read of a delegate's output to the next commit by that agent, the next launch, or 3 hours. For work packets (code drafts and reviews) it is short in Claude's sessions (19 batches from 25 calls: median 8.4 minutes, 8 requests, 17.2k fresh+output tokens, ended by a commit in 18 of 19) and shorter-lived but busier in Codex's (6 batches from 9 calls: 7.6 minutes, 19.5 requests, 25.2k tokens, ended by the next launch in 4 of 6). That interval contains integration, tests and unrelated work as well as checking, so it is an upper bound on result-related work and not a verification cost; the first pass's "6 to 8 times the delegate's output" came from a population that was mostly inspection commands and from windows that began before the answers existed, and is withdrawn. Claude changes whose commit text records a delegate draft or review (n=14) have a median weighted index of 620k against 713k for those without (n=10), with overlapping spread; the two groups differ in task type, and T_direct, the cost of doing the same work directly, cannot be observed. This is a description, not evidence for or against delegation.

**6. Delegate drafts and delegate reviews behave differently by task type.** Claude landed 9 delegate-drafted commits (ADAPT-04 to 08, the runner, the liveness check, the IndexService desk-lookup change); their commit messages record 0 to 2 review fixes each, and the adapter drafts were checked by golden fixtures captured before the change. (That is a provenance summary, not measured draft retention.) Codex's two mapper, builder, critic chains produced no accepted builder output: the Qwen patch was rejected locally (initialisation order, legacy semantics, test patch) and the second builder call timed out at 181 seconds. Critic and mapper calls were useful (the GLM critic correctly rejected the Qwen draft). The final correction came from local measurement.

**7. Review hold-up is about half in the pooled commit record; the earlier Claude-against-Codex split was a misattribution.** The four findings of commit `33fb3b5` were produced by a review that Claude commissioned (`encoder-review`, DeepSeek-V4-Pro, 15:38:38Z to 15:39:18Z, run through Claude's scratchpad runner) of an implementation by ChatGPT that had been left uncommitted at its usage limit; Claude checked the findings and committed. The Codex receipt `index05_encoder_diff_critic` (DeepSeek-V4.1-Flash, 14:50Z, ended at its output cap) is a different review. The reviewer's output was recovered from the scratchpad (`out/encoder_review.md`): five numbered items, four defect claims and a fifth that the reviewer itself retracted; the commit text records all four defect claims as checked and not holding. Recorded dispositions (commissioning orchestrator, implementer, reviewer and committer are separate fields in `data/finding_dispositions.csv`):

| Event | Implemented by | Reviewer | Upheld | Rejected |
|---|---|---|---|---|
| E01 `344a49c` | Claude | DeepSeek-V4-Pro, GLM-5.3 | 3 | 2 |
| E02 `8a34cc7` | Claude | GLM-5.3 | 1 | not recorded |
| E03 `f014b2f` | Claude | Qwen3.5-397B | 1 | not recorded |
| E04 `119ded6` | Claude | DeepSeek-V4-Pro | 1 | not recorded |
| E06 `33fb3b5` | ChatGPT | DeepSeek-V4-Pro | 0 | 4 |

All six commit-recorded reviews were commissioned by Claude (the sixth, `77315cc`, found no defects and is not listed). Pooled, 6 of 12 recorded findings held (Wilson 25% to 75%), an upper bound because E02 to E04 record only the upheld findings. Reviews of Claude's own changes held 6 of 8 and the review of the ChatGPT change 0 of 4, but the reviewers, diffs and packets all differ, so this is not a comparison of implementers or orchestrators. The five report-text reviews in the Codex session (`E07a` to `E07e`) have incomplete counts and are kept in the CSV only. Model-labelled dispositions in the two development transcripts (un-adjudicated, mixed reviewers) give 26 upheld, 13 partial, 9 rejected of 48: 54% strictly upheld, 81% upheld or partial.

**8. The delegation instrumentation is itself unreliable.** Of the Codex runner's 10 real calls: one finished but stayed `started` in the ledger (its reserve is still charged); a retry began 55 seconds after the first, before it completed, and was itself truncated; 4 of 9 completed calls hit `finish_reason = length`; one call failed and is charged at its reserve, not metered usage; the runner's input estimate (characters ÷ 3.5) is 27% high; the 9 completed calls took 22 to 98 seconds and one timed out at 181 seconds (p90 over all 10 calls: 106 seconds). Three of eight rate cards are stale against DeepInfra's live listing: GLM-5.3 is half the live price, and DeepSeek-V4.1-Flash is 1.4 to 2 times too low [verified 2026-10-28T17:05Z at `https://api.deepinfra.com/v1/openai/models`]. **The first pass said per-call records for 24 to 27 October were missing. They exist outside the repository**, in the Claude session's scratchpad: 25 rows of the scratchpad `delegate.py` ledger (the same $0.5457 as the aggregated import row) and 20 logs of the earlier `second_reader.py`, whose roughly $0.45 is in no ledger at all. Delegation records for development work therefore live in three places, and 36 of the 57 recorded calls were launched by a shell call that returned before the API call had finished.

**9. Hosted compute (prior art in `G:\vast`).** Seven rentals, 31 jobs collected, $13.62 spent ($0.44 per job) over 15 hours; the cap was raised from $13.50 to $14.00 mid-run. Boxes A and B produced nothing and were rented about 14 hours each (an estimated $4.46, a third of spend): a step error was logged at 05:24 but the boxes were destroyed at 19:29. Thirteen of 16 pre-registered predictions passed automatically. Provisioning (rent to runner up) took 4.6, 5.6 and 5.5 minutes on the three boxes where the log shows it; that does not isolate image pull from weight load.

**10. Token counters reconcile exactly once branches are accounted for.** In all 207 Codex rollout files the per-request sum equals the counter's own advance (final value minus its value before the file's first request). Two logical threads span two files each, and the second file in each case resumes from an earlier point than the first file reached; the first file's usage after the branch point (2,081,984 and 954,735 tokens) really happened but is absent from the later counter. These are neither duplicates nor overbilling evidence. Duplicate token events inside a file (308) are removed by the parser.

## Measured against reported

| Statement | Source | Measurement | Verdict |
|---|---|---|---|
| Delegated review findings held up about half the time | Claude's end-of-session summary, 2026-10-28T16:10Z [R] | 6 of 12 recorded findings (Wilson 25 to 75%); three of five events record only the upheld findings | Supported as a pooled tally of recorded dispositions; not an estimate of reviewer precision; the Claude-against-Codex split in the first pass is withdrawn |
| Codex hit its usage limit every 30 to 40 minutes, with about five-hour waits | same [R] | bursts median 28.5 min (mean 36.8), idle median 4.6 h | Supported |
| The orchestrator's tokens went on checking | brief [R] | post-result intervals of 8 minutes and 17k tokens (Claude), 8 minutes and 25k (Codex) per batch, containing more than checking | Not measurable: the first pass's ratio is withdrawn |
| Both agents hit usage limits often | brief [R] | Claude 3 hits including a 62-hour lockout; Codex 59 turns | Supported; Claude's lockout was not mentioned anywhere in the brief |
| The `33fb3b5` review had "four findings" | commit text [R] | the review is Claude's `encoder-review` call; its output was recovered and lists four defect claims | Reconciled; the first pass matched the wrong receipt |
| Gemini: a 943,000-token compaction | Gemini review [R] | research session compaction 2026-10-21: 969,271 to 26,310 tokens (942,961 dropped) | Verified |
| Gemini: the whole history is re-processed every turn (50k to 100k+ tokens) | Gemini [R] | cache reads are 99.1% of Claude input; client-inferred cache-read price is about 4% of fresh input; peak context 966k | Mechanism true, cost overstated |
| Gemini: $0.59 to $1.03 per batch, 37 notes for $1.03 | Gemini [R] | "$1.03" appears once in research tool output ("14 DeepInfra $1.03"); $0.59 and the per-batch framing not found | Partly |
| Gemini: tools 133 to 11, 15,813 to 1,241 tokens, -92.2% | Gemini [R] | `reports/2026-10-26-adapt11-tool-surface.md` | Verified |
| Gemini: DeepSeek-R1, Qwen-2.5-Coder-32B, Llama-3.3-70B are the cheap workers | Gemini [U] | R1 (R1-0528) and Llama-3.3-70B-Instruct-Turbo listed; Qwen-2.5-Coder-32B not listed (2026-10-28) | Partly |
| Gemini: new FanOutDispatcher, LeaseWatchdog, DeferredQuestionQueue, EngagementPlanner, telemetry bus | Gemini [R] | equivalents exist in some form, see `06-design-proposals.md` | Largely duplicates of existing parts; `pace.py` is not pacing (it is `set_effort`) |
| Claude spent too little on DeepInfra and hoarded 90% of the labor | Gemini [R] | not measurable from the provided data | Not tested |

## Changes from the first pass

| Quantity | First pass | Revision 2 | Cause |
|---|---|---|---|
| Delegation "results" analysed | Claude 31, Codex 62 | Claude 19 batches (25 calls) plus 5 reading batches (20 calls); Codex 6 batches (9 calls) | classifier counted inspection commands; windows began at shell return |
| Orchestrator follow-up per result | Claude 14.9k, Codex 33.4k (p90 246k); "6 to 8 times" delegate output | Claude 17.2k, Codex 25.2k per batch, no ratio | repaired population and start times; descriptive only |
| Claude weighted index per change | 603k | 620k | cache creation priced at $7.98 per million, not $4.98 |
| Claude shadow dollars per change | median $3.00, total $106.8 | median $3.09, total $117.1 | same |
| Rework in 24 h | 2 of 73 (2.7%) | 2 of 67 mature (3.0%); 6 commits censored | censoring |
| Any rewrite in 72 h | 69% of 74 | 82% of 51 mature; 23 censored | censoring |
| Review hold-up split | Claude 6 of 8 against Codex 0 of 4 | withdrawn: all six commit-recorded reviews were Claude-commissioned | misattribution of `33fb3b5` |
| Agents' DeepInfra spend | about $0.70 | about $1.15 | scratchpad `second_reader.py` calls found; `delegate.py` ledger recovered |
| Per-call records for 24 to 27 Oct | "missing" | 25 ledger rows and 20 logs in the Claude scratchpad | not looked for outside the repository |
| Token reconciliation | "203 of 205 threads within 1%" | 207 of 207 files exact; two branch overlaps explained to the token | counter offsets and branch points modelled |

## Caveats

- Codex "observed idle" includes time you were away. The weekly quota fit mixes Claude-derived weights with Codex tokens and is an exchange rate, not a price. Quota percentages are account-wide and cannot be read as the price of one task.
- The 16 unjoined commits are 13 from 2026-09-29 to 10-04 (before the available logs for this repository), one on 10-23 and two PR merges.
- Model-labelled transcript events are tier R. Their anchors are verified; their labels were not individually adjudicated.
- Shadow dollars use fitted list prices from the client's own cost records (30 records, R² 1.0000) and are modelled, not billing.
- Line survival and rewrite counts are proxies: legitimate refactors delete good code, untouched bugs survive, repairs made before the commit are invisible, and deletion-only fixes insert no lines.
