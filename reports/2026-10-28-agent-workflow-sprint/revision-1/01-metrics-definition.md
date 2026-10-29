# Metrics for agent and orchestration performance (deliverable 1)

Date: 2026-10-28. Every metric names its source files, its script and its known bias. Evidence tags: **[M]** measured by a re-runnable script on machine-written data; **[R]** reported in prose by an agent or person; **[U]** claim about an outside tool or company (verified / plausible / unverified, see `08-claim-register.md`). Scripts live in `scripts/`, outputs in `data/`; run them with `python -I` (the repository venv for `verify_anchors.py`).

## Measurement pipeline

| Source | Script | Output | What it gives |
|---|---|---|---|
| Git history, 118 commits on master | `git_metrics.py` | `commits.csv`, `rework_edges.csv` | commit class (code / bookkeeping / plan-only), provenance lines, line survival at HEAD, line-level rework graph via `git blame` on each commit's parent |
| DeepInfra receipts and two ledgers | `receipt_metrics.py` | `delegations.csv`, `ledger_reconciliation.json` | per-call model, tokens, cost basis, latency, finish reason, orphan and overlap flags |
| Claude Code session logs | `claude_log_metrics.py` | `claude_*_messages/events/prompts/commits/delegates.csv` | per-message usage (fresh, cache-write, cache-read, output), `quotaLimits` limit events with `resetsAt`, compactions, delegate calls |
| Codex rollouts | `codex_log_metrics.py` | `codex_threads/requests/events/commits/delegates.csv` | per-request usage, 5-hour and weekly `used_percent`, `usage_limit_exceeded` turns, spawned workers and guardian threads |
| Plan and handoff files | `plan_log_metrics.py` | `plan_growth.csv`, `handoff_artifacts.csv` | tokens of a cold-start read at each plan version |
| Hosted-compute prior art | `vast_queue_metrics.py` | `vast_*.csv/json` | boxes, jobs, spend, failures |
| Reliability benchmark (2026-09-29) | `benchmark_digest.py` | `benchmark_models.csv` | per-model probe outcomes (priors only) |
| Transcripts (22 chunks) | DeepInfra lane T, then `verify_anchors.py`, `aggregate_events.py` | `transcript_events.csv` | 802 anchor-verified workflow events (labels are tier R) |
| All of the above | `analyze_baseline.py` | `baseline_metrics.json` | the values in `02-baseline.md` |

**Commit join.** A commit is attributed to the agent whose session ran it: the commit hash appears in the tool result of the commit command (Claude `git commit -q` prints no hash, so any real commit hash in the result that was created up to 15 minutes earlier counts). Result: 102 of 118 master commits joined (Claude 39, Codex 63); every non-merge commit from 2026-10-24 on.
**Privacy.** The session-log scripts emit only numbers, timestamps, enums and IDs, never message text, and nothing from the logs is sent to a model.

## Definitions

### Accepted change
A commit on master that touches `src/`, `tests/`, `scripts/`, `plugin/`, `obsidian/`, `ui/` or other non-document files, has one parent, and is not documentation-only. Sensitivity variants: **A0** as stated; **A1** = A0 minus reverts and minus commits with at least 10 inserted lines of which 30% or more were rewritten within 24 hours; **A2** = A1 minus commits whose lines have a survival ratio under 0.5 at HEAD. In this data A1 removes 2 Claude changes and A2 removes none more.

### M1 Orchestrator tokens per accepted change
- **Definition.** For each agent family (Claude, Codex), tokens of every request between the previous accepted commit of that family and this one, reported as four components and never merged: **fresh input** (Claude: input + cache-creation; Codex: input − cached input), **cache-read**, **output** (including thinking or reasoning), and **requests**. Bookkeeping commits do not close a window, so the cost of recording and verifying a change stays inside it; they are counted per window (`bookkeeping_commits_in_window`).
- **Weighted index** = fresh + w_read × cache-read + w_out × output, with weights inferred from the client's own cost records for Claude Opus 5.5 (30 `cost-state` records, R² 1.0000): w_read 0.04, w_out 3.94 (about $4.98, $19.66, $0.20 and $7.98 per million tokens for input, output, cache-read, cache-write) [M: client-computed list price; vendor page not fetched]. The same weights are applied to Codex only for comparison.
- **Quota currency.** Codex records `used_percent` for a 5-hour and a weekly window; weighted tokens per 1% of the weekly window are fitted per window (`codex_weekly_quota_fit`, about 165k to 215k weighted tokens per percent). Claude exposes no quota percentage, only limit hits.
- **Bias.** Parallel Codex workers' tokens are charged to the next accepted commit of the family, not of the thread. Window edges leave a small unattributed remainder after the last commit (reported).

### M2 Dollars per accepted change
Delegate dollars (receipts, rate-card estimate; failed calls at reserve) plus orchestrator **shadow dollars** (tokens × the fitted Claude price). Subscription plans bill by quota, so shadow dollars are a modelled comparison, not spend. Report median and IQR. Delegate dollars are recomputed at live prices where cards are stale (`deepinfra_live_check.json`).

### M3 Rework rate
Share of accepted commits (a) reverted, or (b) with at least 30% of their inserted lines rewritten within 24 hours (`rework_edges.csv`, `git blame` on the parent of each later commit). Also the **line survival ratio** at HEAD (surviving lines ÷ inserted lines in text files) and the share with any line rewritten within 72 hours. **Delegate-draft retention** is measured at commit level only (the draft text is not stored): commits whose message says "Drafted by" and whether review fixes are recorded.

### M4 Review-finding hold-up
Each finding gets one disposition: upheld (a fix landed), partial, rejected (checked and false), unverifiable, duplicate. **Precision** = (upheld + partial) / dispositioned, with a Wilson 95% interval (Beta(1,1) posterior gives nearly the same). Companion measures: **cost per upheld finding** (delegate dollars + orchestrator follow-up tokens) and **verification asymmetry** V = orchestrator follow-up fresh+output tokens ÷ delegate output tokens (see M7). Source of dispositions: commit text (`finding_disposition` counts in `data/finding_dispositions.csv`, tier R but each fix is visible in a diff) and, as an un-adjudicated cross-check, model-labelled transcript events. **Gap:** findings are not stored as data, so counts come from prose.

### M5 Time lost to usage limits
- **Claude.** Each assistant record with `isApiErrorMessage` and `quotaLimits` is a limit hit; blocked interval = hit time to `resetsAt`. A user message that says the limit reset is corroboration only.
- **Codex.** Each `task_complete` with `codex_error_info = usage_limit_exceeded` (de-duplicated by turn id, history replayed by forks excluded) is a hit. The predicted reset is the exhausted window's `resets_at`; the **observed idle** is the time to the next request of any Codex thread (an upper bound, since it includes time you were away).
- **Joint availability.** Over a stated window, hours when Claude was blocked, Codex was idle, both, and their shares of wall-clock time. **Burst** = continuous Codex activity (gaps under 30 minutes) that ends within 5 minutes of a limit hit.
- Pasted transcripts contain the phrase "usage limit"; only structured fields are used.

### M6 Handoff and resume cost
For every resume boundary (gap over 60 minutes, or a compaction) in an agent family's request stream: **cold-start tokens** = fresh input + output summed until the first request that edits, commits, delegates or runs tests, plus the request count. Boundaries are classed limit, compaction or idle. **Session-start** cold start is measured the same way. **Resume payload** = tokens of the plan and handoff files a fresh session would read (`plan_growth.csv`). **Handoff loss** (defects traced to missing or wrong state, for example work "left uncommitted at its usage limit") is counted from commit text. Claude's post-limit boundary re-creates the whole prompt cache, so its cold-start tokens are mostly cache rebuild, not reading.

### M7 Delegation economics (added)
**Follow-up window** = from the arrival of a delegate result to the next commit or the next delegation (at most 3 hours). Reported: orchestrator fresh+output tokens, requests and minutes in the window. **Break-even:** delegate if T_direct > T_packet + T_follow-up + p_reject × T_redo. T_direct cannot be observed; changes with and without delegate involvement are compared observationally and flagged as such.

### M8 Anchor pass rate (added)
For every model-produced item that cites a place (line or page) and a verbatim quote: share whose quote is found within ±2 lines or ±1 page (`clerk.quoted`: normalises typographic quotes, Markdown emphasis and PDF line-break hyphens, minimum 8 characters). Classes: verified, quote-elsewhere (anchor wrong, evidence real), unverified. Reported per model and lane. It proves the evidence exists, **not** that it supports the label (see C5 in `06-design-proposals.md`).

### M9 Packet-contract conformance (added)
Share of the plan §3.3 fields present in a delegation packet. Receipts do not store the packet text and the briefs were deleted (`briefs/` holds only the canary), so this is **not measurable for past calls**; proposal DELEG-01 records it from now on.

### M10 Parallel efficiency (added)
Mean parallelism when active = Σ thread active time ÷ wall time with at least one thread active (activity segments: gaps under 10 minutes); peak concurrent threads; orchestration-call share of tokens (`spawn_agent`, `wait_agent`, `send_message`, `followup_task`, `list_agents`); share of tokens spent by workers and by guardian (approval-review) threads.

### M11 Context tax (added)
Cache-read share of input; peak context; compactions per 100k output tokens (de-duplicated; sessions replay earlier compactions).

### M12 Instrumentation integrity (added)
|Σ receipts − ledger|; orphan `started` entries whose receipt completed; duplicate or overlapping calls; failed calls' cost basis (reserve, not metered); share of calls with `finish_reason = length`; input-token estimate ratio; stale rate cards against DeepInfra's live listing.

### M13 Protocol conformance (added)
Share of the prescribed research-agent phases (scout the catalogue, delegate fetching, dispose of rejects, close and report; `Opening Prompt - Dedicated Research Agent`) observed as anchored events in the research-use transcript. Early baseline only.

## Guardrails
Report M1 beside M3 (cheap but reworked is not cheap) and beside the hold-up rate (M4). Never optimise tokens per change alone. Separate research-side and development-side populations. Report component tokens, not only the index.

## Re-running
`python -I scripts/git_metrics.py`, `receipt_metrics.py`, `claude_log_metrics.py D--Librarian-V2 librarian_v2`, `codex_log_metrics.py`, `plan_log_metrics.py`, `analyze_baseline.py`. Inputs are listed with hashes in `data/inputs.manifest.json`; live logs are recorded by size and modification time only.
