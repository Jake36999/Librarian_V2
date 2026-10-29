# Metrics for agent and orchestration performance (deliverable 1, revision 2)

Date: 2026-10-28 (revised the same evening after a second-pass review; the first-pass file is in `revision-1/`). Every metric names its source files, its script and its known bias. Evidence tags: **[M]** measured by a re-runnable script on machine-written data; **[R]** reported in prose by an agent or person; **[U]** claim about an outside tool or company (verified / plausible / unverified, see `08-claim-register.md`). Scripts live in `scripts/`, outputs in `data/`; run them with `python -I` (the repository venv for `verify_anchors.py`).

## Measurement pipeline

| Source | Script | Output | What it gives |
|---|---|---|---|
| Git history, 118 commits on master | `git_metrics.py` | `commits.csv`, `rework_edges.csv` | commit class (code / bookkeeping / plan-only), provenance lines, line survival at HEAD, line-level rework graph via `git blame` on each commit's parent |
| DeepInfra receipts and two ledgers | `receipt_metrics.py` | `delegations.csv`, `ledger_reconciliation.json` | per-call model, tokens, cost basis, latency, finish reason, orphan and overlap flags |
| Delegation calls and their launches | `delegate_events.py` | `delegate_events.csv`, `delegate_launch_audit.csv`, `delegate_inventory.json` | every call the runners recorded (receipts, the Claude scratchpad ledger and logs), linked to the shell launch, the call's real end and the first re-read of its output |
| Claude Code session logs | `claude_log_metrics.py` | `claude_*_messages/events/prompts/commits/delegates.csv` | per-message usage (input, cache creation, cache read, output), `quotaLimits` limit events with `resetsAt`, compactions |
| Codex rollouts | `codex_log_metrics.py` | `codex_threads/requests/events/commits/delegates.csv` | per-request usage, 5-hour and weekly `used_percent`, `usage_limit_exceeded` turns, spawned workers and guardian threads, counter offsets per file |
| Plan and handoff files | `plan_log_metrics.py` | `plan_growth.csv`, `handoff_artifacts.csv` | tokens of a cold-start read at each plan version |
| Hosted-compute prior art | `vast_queue_metrics.py` | `vast_*.csv/json` | boxes, jobs, spend, failures |
| Reliability benchmark (2026-09-29) | `benchmark_digest.py` | `benchmark_models.csv` | per-model probe outcomes (priors only) |
| Transcripts (22 chunks) | DeepInfra lane T, then `verify_anchors.py`, `aggregate_events.py` | `transcript_events.csv` | 802 anchor-verified workflow events (labels are tier R) |
| Papers (50 distinct PDFs) | `build_lit2.py`, `sprint_dispatch.py`, `verify_anchors.py` (lane L2) | `data/lit2_*` | full-text reading records with page-anchored quotes (see M8) |
| All of the above | `analyze_baseline.py` | `baseline_metrics.json` | the values in `02-baseline.md` |

**Commit join.** A commit is attributed to the agent whose session ran it: the commit hash appears in the tool result of the commit command (Claude `git commit -q` prints no hash, so any real commit hash in the result that was created up to 15 minutes earlier counts). Result: 102 of 118 master commits joined (Claude 39, Codex 63); every non-merge commit from 2026-10-24 on.
**Privacy.** The session-log scripts emit only numbers, timestamps, enums and IDs, never message text, and nothing from the logs is sent to a model. Commands are read locally only to classify them and to extract task, model and file names.
**Population.** Development work in Librarian_V2 and research use of the library are different populations and are never pooled.

## Definitions

### Accepted change
A commit on master that touches `src/`, `tests/`, `scripts/`, `plugin/`, `obsidian/`, `ui/` or other non-document files, has one parent, and is not documentation-only. Sensitivity variants: **A0** as stated; **A1** = A0 minus reverts and minus commits with at least 10 inserted lines of which 30% or more were rewritten within 24 hours; **A2** = A1 minus commits whose lines have a survival ratio under 0.5 at HEAD. In this data A1 removes 2 Claude changes and A2 removes none more.

### M1 Orchestrator tokens per accepted change
- **Definition.** For each agent family (Claude, Codex), tokens of every request between the previous accepted commit of that family and this one, reported as five components and never merged: **ordinary input** (Claude: input tokens; Codex: input minus cached input), **cache creation** (Claude only), **cache read**, **output** (including thinking or reasoning), and **requests**. The tables also show "fresh" = ordinary input plus cache creation, which is how the first pass reported it. Bookkeeping commits do not close a window, so the cost of recording and verifying a change stays inside it; they are counted per window.
- **Weighted index** = ordinary input + w_cc × cache creation + w_read × cache read + w_out × output, with weights inferred from the client's own cost records for Claude Opus 5.5 (30 `cost-state` records, R² 1.0000): about $4.98, $7.98, $0.20 and $19.66 per million tokens for ordinary input, cache creation, cache read and output, so **w_cc 1.60, w_read 0.04, w_out 3.94** [M: client-computed list price; vendor page not fetched]. The first pass priced cache creation as ordinary input and so under-weighted it. The same weights are applied to Codex only for comparison.
- **Quota currency.** Codex records `used_percent` for a 5-hour and a weekly window; weighted tokens per 1% of the weekly window are fitted per window (about 165k to 215k weighted tokens per percent). Claude exposes no quota percentage, only limit hits. Quota percentages are account-wide, so they are an exchange rate and not the price of one task.
- **Bias.** Parallel Codex workers' tokens are charged to the next accepted commit of the family, not of the thread. Window edges leave a small unattributed remainder after the last commit (reported). Continuation files that branch from an earlier point add real usage that the later counter omits (see M12).

### M2 Dollars per accepted change
Delegate dollars (receipts or ledgers, rate-card estimate; failed calls at reserve) plus orchestrator **shadow dollars** (all four components × the fitted Claude prices). Subscription plans bill by quota, so shadow dollars are a **modelled** comparison, not spend, and are not tagged [M] as actual cost. Report median and IQR. Delegate dollars are recomputed at live prices where cards are stale (`deepinfra_live_check.json`).

### M3 Rework rate
Share of accepted commits (a) reverted, or (b) with at least 30% of their inserted lines rewritten within 24 hours (`rework_edges.csv`, `git blame` on the parent of each later commit). Also the **line survival ratio** at HEAD and the share with any line rewritten within 72 hours. **Right-censoring:** a commit made within 24 (or 72) hours of the end of the data cannot yet show a rewrite; mature cohorts (at least 24 or 72 hours of follow-up at an explicit cutoff, 2026-10-28T21:00Z) are reported with the number of censored commits. These are proxies: line survival is not correctness (refactors delete good code, untouched bugs survive, repairs before the commit are invisible, deletion-only fixes insert nothing). **Delegate-draft retention** is measured only as a provenance summary from commit messages ("Drafted by", fixes recorded in review); the draft text is not stored, so true retention is unmeasured.

### M4 Review-finding hold-up
Each finding gets one disposition: upheld (a fix landed), partial, rejected (checked and false), unverifiable, duplicate. Roles are separate fields: **implementer**, **commissioning orchestrator**, **reviewer model**, **committer**. **Precision** = (upheld + partial) / dispositioned, with a Wilson 95% interval, stated as an upper bound when rejections are not recorded. It is a tally of recorded dispositions, not an estimate of a reviewer's precision, and it says nothing about recall: a reviewer that reports almost nothing scores well on precision alone. Source: commit text and reports (tier R; each fix is visible in a diff) and, as an un-adjudicated cross-check, model-labelled transcript events. **Gap:** findings are not stored as data. Experiments E1 and E4 add known defects and verified-clean changes so that false-positive burden, recall and severity can be reported.

### M5 Time lost to usage limits
- **Claude.** Each assistant record with `isApiErrorMessage` and `quotaLimits` is a limit hit; blocked interval = hit time to `resetsAt`. A user message that says the limit reset is corroboration only.
- **Codex.** Each `task_complete` with `codex_error_info = usage_limit_exceeded` (de-duplicated by turn id, history replayed by forks excluded) is a hit. The predicted reset is the exhausted window's `resets_at`; the **observed idle** is the time to the next request of any Codex thread (an upper bound, since it includes time you were away).
- **Joint availability.** Over a stated window, hours when Claude was blocked, Codex was idle, both, and their shares of wall-clock time. **Burst** = continuous Codex activity (gaps under 30 minutes) that ends within 5 minutes of a limit hit. Calendar idle is not recoverable productive time: it depends on the backlog and on whether you wanted work done then.
- Pasted transcripts contain the phrase "usage limit"; only structured fields are used.

### M6 Handoff and resume cost
For every resume boundary (gap over 60 minutes, or a compaction) in an agent family's request stream: **tokens before the first productive request** = ordinary input, cache creation and output summed until the first request that edits, commits, delegates (a structural launch) or runs tests, plus the request count. Boundaries are classed limit, compaction or idle. **Session-start** cold start is measured the same way. **Resume payload** = tokens of the plan and handoff files a fresh session would read. **Handoff loss** (defects traced to missing or wrong state, for example work "left uncommitted at its usage limit") is counted from commit text. Claude's post-limit boundary re-creates the whole prompt cache, so its tokens are all cache creation. **What this does and does not measure:** it is the cost around a resume under a heuristic action classifier, containing the cache rebuild and the first productive request. It does not isolate rereading, lost knowledge or extra work caused by a handoff, and a compact note placed inside the same restored conversation removes none of that conversation's history. A capsule's benefit is a hypothesis for experiment E3 (same task, fresh context plus capsule against restored history, judged on correctness to completion, total role costs and time to a verified action).

### M7 Post-result interval (revised; formerly "delegation follow-up")
A **call** is a record a runner wrote (a receipt, a scratchpad ledger row, a scratchpad log). A **launch** is a shell command that executes a runner (an interpreter running the runner script); reading, searching, editing, diffing or testing a runner is inspection and does not count. Each call is linked to its launch, to its real end time (receipt completion, or output-file time for the scratchpad runners) and to the first later tool call that reads its output file. Results consumed within 90 seconds of each other form a **batch**. The **post-result interval** runs from the batch's first re-read to the next commit by that agent family, the next launch, or 3 hours; each request is charged to the latest open batch, so windows never double-count. Reported: ordinary input, cache creation, output and requests in the interval, and its minutes. It contains integration, tests and unrelated work as well as checking, so it is an **upper bound on result-related work and not a verification cost**; a ratio to the delegate's output is not reported. **Break-even** (delegate if T_direct > T_packet + T_follow-up + p_reject × T_redo) needs T_direct, which cannot be observed; changes with and without delegate involvement are compared observationally and flagged as confounded by task type. Compare total task cost against matched direct work before claiming savings or losses.

### M8 Extraction quality (revised; five separate measures per lane and model)
The first pass reported one "anchor pass rate". A high quote-match rate says nothing about items not selected, truncated tails or unparseable calls, so the measures are kept apart:
- **M8a call completion**: share of calls that returned without error and without `finish_reason = length`.
- **M8b parse success**: share whose output parsed as is, after brace repair, after salvage of complete array items, or not at all. Salvage never proves completeness.
- **M8c quote-location fidelity**: share of items whose verbatim quote is found on the **cited page** (exact page, `clerk.quoted` normalising typographic quotes, Markdown emphasis and PDF line-break hyphens, minimum 8 characters); items found on an adjacent page, elsewhere in the paper, or nowhere are counted separately. It proves the evidence exists, **not** that it supports the label and not that the interpretation is right.
- **M8d semantic support**: share of a sampled set of items whose claim is supported by the quote and its page context, judged by a second model and then adjudicated by me on a subsample. Interpretation precision is otherwise unmeasured.
- **M8e coverage**: share of a checklist of methods, costs and limitations (written independently of the readers) that a reader found, per paper. Capture-recapture between two readers is exploratory because independence, equal detectability and the definition of an item are not established. Cohen's kappa on labels measures label agreement, not error correlation, and cannot populate a verification-failure model.

### M9 Packet-contract conformance
Share of the plan §3.3 fields present in a delegation packet. Receipts do not store the packet text and the briefs were deleted, so this is **not measurable for past calls**; proposal DELEG-01 records it from now on.

### M10 Overlap and parallel activity (revised wording)
Mean number of Codex threads active when at least one is (sum of thread active time ÷ time with at least one active; activity segments are request timestamps with gaps under 10 minutes and a one-minute tail), peak concurrent threads, orchestration-call share of tokens (`spawn_agent`, `wait_agent`, `send_message`, `followup_task`, `list_agents`), and the shares of tokens spent by workers and by guardian (approval-review) threads. This is an **overlap proxy**: it is not speedup, throughput or the share of agent time used, and permission errors are not merge conflicts. Speedup needs matched work at several concurrency levels (experiment E4).

### M11 Context tax
Cache-read share of input; peak context; compactions per 100k output tokens (de-duplicated; sessions replay earlier compactions; the sprint's own sessions excluded).

### M12 Instrumentation integrity
|Σ receipts − ledger|; orphan `started` entries whose receipt completed; duplicate or overlapping calls; failed calls' cost basis (reserve, not metered); share of calls with `finish_reason = length`; input-token estimate ratio; stale rate cards against DeepInfra's live listing; **where the records live** (receipts in the repository, a scratchpad ledger and logs outside it, spend in no ledger); **launch return before real completion** (a backgrounded or yielding launch); and **token-counter reconciliation**: within every Codex rollout file the sum of per-request usage must equal the counter's advance (final value minus its value before the file's first request), and a continuation file that branches from an earlier point is reported with the usage the earlier file spent after the branch point.

### M13 Protocol conformance
Share of the prescribed research-agent phases (scout the catalogue, delegate fetching, dispose of rejects, close and report; `Opening Prompt - Dedicated Research Agent`) observed as anchored events in the research-use transcript. Early baseline only.

## Guardrails
Report M1 beside M3 (cheap but reworked is not cheap) and beside the hold-up rate (M4). Never optimise tokens per change alone. Separate research-side and development-side populations. Report component tokens, not only the index. Report precision beside recall and false-positive burden, never alone.

## Re-running
`python -I scripts/git_metrics.py`, `receipt_metrics.py`, `claude_log_metrics.py D--Librarian-V2 librarian_v2`, `codex_log_metrics.py`, `delegate_events.py`, `plan_log_metrics.py`, `analyze_baseline.py`, `check_determinism.py`. Inputs are listed with hashes in `data/inputs.manifest.json`; live logs are recorded by size and modification time only. `delegate_events.py` reads the Claude session scratchpad folder, which lives outside the repository and may be cleaned up.
