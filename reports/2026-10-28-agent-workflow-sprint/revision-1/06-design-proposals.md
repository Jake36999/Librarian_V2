# Design proposals (deliverable 5)

Date: 2026-10-28. Proposals rest on measured evidence ([M]) and verified facts only; each cites `02-baseline.md` or a data file. Where a literature source informs a proposal it is marked Hypothesis and cited in `04-extraction-table.md`. Nothing here changes product code; each proposal is a plan row you can adopt or drop.

**Naming.** `DEPLOY-xx` in the plan means vault-directory deployment (create, adopt, attach), so agent run patterns use a new prefix: **DELEG-xx** for development-delegation tooling (extends plan §3 and §11) and **HARNESS-10 and up** for runtime items. Sizes follow plan §3.1.

## Requirements the evidence supports

| ID | Requirement | Evidence |
|---|---|---|
| R1 | Delegated output is cheap to verify mechanically (typed, anchored, or test-gated) | orchestrator follow-up is about 8.3 times the median delegate output (Codex) and about 6 times for the one Claude example with a recorded size; 3 of 11 triage batches were malformed JSON; 17 of 85 sprint calls and 4 of 9 runner calls truncated; a verified quote does not prove the label (C5) |
| R2 | Delegation records join to plan tasks, commits and findings | one orphan ledger entry, one duplicate call, no per-call receipts for 10-24 to 10-27, "four findings" unreconciled |
| R3 | A fresh session resumes from at most about 4k tokens of durable state | resume after a limit costs 502k (Claude) and 135k (Codex) fresh tokens; the plan is 31k tokens (§19: 17.6k); a 62-hour lockout |
| R4 | Dispatch knows each orchestrator's quota and sends mechanical work elsewhere when it is scarce | both agents blocked up to 57% of 103 h; Codex bursts of 28 min then 4.6 h waits |
| R5 | Parallel lanes are isolated, budgeted and accounted | mean parallelism 1.66 at 46% of tokens in workers; orchestration 13%; guardian reviews 9.5%; 43 git permission-denied and 8 `index.lock` events in Codex tool output |
| R6 | The instrumentation is correct by construction | 3 of 8 stale rate cards (GLM-5.3 at half price), input estimate 27% high, failed calls charged at reserve |
| R7 | Routing by task type rests on measured outcomes, not hypotheses | plan §3.2 calls its lanes "hypotheses"; Qwen3-Coder builder 0 of 2 accepted; DeepSeek-V4-Pro and GLM-5.3 drafts landed 9 times |
| R8 | Hosted compute has deadlines, incremental output and early abort | `G:\vast`: two boxes rented about 14 h with no output (an estimated $4.46 of $13.62), cap raised mid-run |

## Gemini's proposals against what already exists

Statuses come from two independent readers per component with anchor-verified quotes (`data/capability_matrix.csv`; Cohen's kappa 0.45 on 30 reader pairs) and from my direct reading of `tools/delegate.py`, `effort.py` and `tools/pace.py`. A reader's label can overstate its own evidence: both "present" labels for quota-aware dispatch described static caps, and one reader's gap note said so.

| Gemini proposal | Existing equivalent | Gap |
|---|---|---|
| `ingest_and_verify_corpus` (two-stage stamping) | `deep_read.py` (paragraph-safe chunks that keep pages, quotes checked with `clerk.quoted`), `intake.py`, `pdf_markdown.py` | no budgeted batch driver and no independent second reader; this sprint's `sprint_dispatch.py` and `verify_anchors.py` are that driver |
| `delegate_sandbox_script` (write-run-fix loop) | `sandbox.py` and `tools/sandbox.py` (a landing pad where "nothing on the pad is ever executed") | running model-written code is deliberately excluded at runtime; a gate for development patches would be new (DELEG-06) |
| `pre_flight_audit` | `doctor.py` and the BASE tasks | partial |
| `telemetry.jsonl` bus | `trace.py` and session events (`model_request`, `model_response`, ADAPT-03) | present at runtime; development receipts lack join keys (DELEG-01) |
| compute router and cost quantifier (DeepInfra against Vast) | `effort.py` (static caps), `role_routes.py`, `service_routes.py`, `hosts.py` limiter, runner `reserve_cost` | no cost model and no hosted-compute route; **`pace.py` is `set_effort`, not pacing** |
| FanOutDispatcher | `tools/delegate.py` (parallel read-only helper agents, caps from the effort slider, profile guard), `batch.py` | no typed results or anchors, no cross-call budget ledger |
| LeaseWatchdog | `coordination.py` (`DocumentLeases`, vault lease, Obsidian heartbeat, `VaultWatcher`) | exists for documents, not for long-running agent tasks |
| DeferredQuestionQueue | `broker.py` (an unanswered request expires and parks the session), `8a34cc7` (question recorded inside the operation) | waiting blocks the call rather than continuing speculatively; HARNESS-03 already plans question blocking |
| EngagementPlanner | HARNESS-04 manifest ("remaining budget"), `effort.profile` budgets | partial |

Quota awareness, an executable gate, a resume capsule, lane isolation for development agents and a drafter-not-reviewer check (C12) are **absent everywhere**.

## Proposals, in priority order

### 1. DELEG-01 Runner hygiene and receipt v2
- **Requirement.** R2, R6.
- **Evidence.** orphan `started` entry whose output exists; duplicate call 55 s after the first, itself truncated; 4 of 9 completed calls truncated; stale cards; failed-call cost is the reserve; the 10-24 to 10-27 spend is one aggregated row.
- **Change** (extends `scripts/delegate_deepinfra.py`; `a328e7c` already fixed the ledger race): refuse a second identical packet hash while a receipt for it is `started` and under 10 minutes old; exit non-zero on `finish_reason=length` unless `--allow-truncated`; record `--task-id`, `--role`, `--parent-run`, `--agent`, `cost_basis` (metered or reserve) and later the commit hash; compare rate cards with the live listing at start (`deepinfra_check.py` is a working version).
- **Cost.** low. **Risk.** low; stricter exits may need a flag for callers.
- **Plan row.** `DELEG-01 | Small | depends: none | owner review | Acceptance: regression tests for duplicate refusal, truncation exit, price check and receipt fields; the 5 measured defects each have a failing-then-passing test.`

### 2. DELEG-02 Typed, anchored delegate output with a local verifier
- **Requirement.** R1, R2.
- **Evidence.** 1,963 anchored items checked mechanically: 99.2% pass for MiMo-V2.6-Pro (n=1,441), 98.6% GLM-5.3, 97.4% GLM-5.3-Flash, 91.5% DeepSeek-V4.1-Flash and 64.5% DeepSeek-V4-Pro (n=141); repair of a missing brace rescued 3 of 11 batches; salvage rescued 17 truncated outputs. Review findings are not stored as data, so M4 had to be rebuilt from prose.
- **Change.** promote `verify_anchors.py` to `scripts/verify_delegate_output.py` with a schema argument; critic packets require `findings[]` with file, lines, verbatim quote and a falsifier; the orchestrator appends `disposition` (upheld, rejected, partial) with a commit hash.
- **Cost.** low to medium. **Risk.** over-trusting anchors: add a rule that a label such as "present" needs its gap text reviewed (C5).
- **Plan row.** `DELEG-02 | Small-Medium | depends: DELEG-01 | Acceptance: the verifier reproduces this sprint's pass rates on the saved lane outputs; fixtures cover brace repair, truncation salvage and a wrong-label case; a disposition file feeds the hold-up metric without hand counting.`

### 3. DELEG-03 Packet lint and diff-scope guard
- **Requirement.** R1, R7. **Evidence.** plan §3.3 fields are unenforced; builder output was rejected for initialisation order and legacy semantics (a "preserve existing behaviour" field would target exactly that); no code path checks that drafter and reviewer differ (C12 absent).
- **Change.** a lint that fails a packet missing a §3.3 field or naming one model as drafter and reviewer; a post-hoc `check_diff_scope` that fails when a landed diff touches a forbidden file.
- **Cost.** low. **Risk.** low.
- **Plan row.** `DELEG-03 | Small | depends: DELEG-01 | Acceptance: lint and scope check have positive and negative fixtures; M9 becomes measurable.`

### 4. DELEG-04 Resume capsule for development agents
- **Requirement.** R3. **Evidence.** resume tax 502k and 135k fresh tokens; cold-start read of the plan 31k tokens; two commit messages record work "left uncommitted at its usage limit"; 44 model-labelled handoff events in the three development transcripts (31, 10 and 3).
- **Change.** `scripts/write_resume.py` writes `resume.json` of at most 4,000 tokens before a stop or on request: lane and branch or worktree, last green commit, uncommitted files with diffstat, open receipts, pending verifications, next action, and the other agents' limit reset times. A fresh session reads that, not the transcript. Hypothesis: capsule-based resume avoids the cache rebuild; the literature on thought management and drift (see `04-extraction-table.md`) supports keeping a compact goal state.
- **Cost.** medium. **Risk.** a stale capsule misleads; include the git state hash and refuse on mismatch.
- **Plan row.** `DELEG-04 | Medium | depends: DELEG-01 | Acceptance: experiment E3 shows a fresh session reaches its first correct action with at most 40k fresh tokens on three recorded handoff points, against the measured 135k to 502k.`

### 5. DELEG-05 Auto-recorded delegation lines and closure check
- **Requirement.** R2, R3. **Evidence.** 41 of 118 commits are bookkeeping-only (0.55 per code commit); §19 grew to 17.6k tokens; the "four findings" record cannot be matched to a receipt.
- **Change.** generate the §19 delegation line (task, model, tokens, cost, disposition) from receipts; `check_task_closure` fails a "done" row without commit hash, test names and documentation diff (reuses the HARNESS-07 verifier idea).
- **Cost.** low. **Risk.** low. **Plan row.** `DELEG-05 | Small | depends: DELEG-01, DELEG-02 | Acceptance: the generated line replaces hand-written ones for new packets; closure check passes on the last 10 §19 entries or lists their gaps.`

### 6. DELEG-06 Executable acceptance gate (experimental)
- **Requirement.** R1. **Evidence.** drafts checked by golden fixtures (ADAPT-04, 05) landed with at most two fixes; concurrency-sensitive changes cost far more to verify (Codex follow-up p90 246k tokens). The single-shot runner cannot run tests by design.
- **Change.** apply a proposed patch in a scratch worktree, run the packet's declared test command, return pass or fail plus at most 40 lines of diagnostics; tasks touching `host.py`, `coordination.py`, `connection.py`, `cli.py`, `mcp_server.py` or the writer stay human-gated (plan §3.2).
- **Cost.** medium. **Risk.** sandbox safety and false confidence on weak tests. Run experiment E2 first.
- **Plan row.** `DELEG-06 | Experimental medium | depends: DELEG-03 | kill criterion: no reduction in follow-up tokens or rework on 10 paired packets | Acceptance: written go or no-go with measured follow-up tokens.`

### 7. DELEG-07 Limit-aware scheduling (experimental)
- **Requirement.** R4. **Evidence.** up to 57% of the window with both agents blocked; Claude weekly lockout 62 h; Codex bursts 28 min. Codex logs expose `used_percent` and reset times; Claude exposes a limit only when it hits.
- **Change.** a read-only status script (latest Codex quota, last Claude limit and reset) and a routing table: when an orchestrator is near a limit, queue mechanical lanes for DeepInfra or local scripts and park decisions that need the lead. Replay first (E6): how many blocked hours could mechanical lanes have covered?
- **Cost.** medium. **Risk.** Claude's quota is only partly observable; a wrong estimate wastes a window. Runtime `effort.py` is static and is not the place for this.
- **Plan row.** `DELEG-07 | Experimental medium | depends: DELEG-04 | kill criterion: replay shows under 10% of blocked hours were coverable | Acceptance: replay report on 2026-10-24 to 28 data.`

### 8. HARNESS-10 Typed helper results at runtime
- **Requirement.** R1. **Evidence.** `tools/delegate.py` already fans out read-only helpers but returns free text truncated to 4,000 characters per helper; the same anchored-extraction pattern worked at 99% here.
- **Change.** helper replies carry `sources[]` with note name and verbatim quote, checked by the loop before the lead sees them; add budget and quota fields to the HARNESS-04 manifest. **Check HARNESS-04 first**: it may already plan this.
- **Plan row.** `HARNESS-10 | Small-Medium | depends: HARNESS-04 | Acceptance: helper results with an unverifiable quote are marked, with a test.`

### 9. DELEG-08 Lane isolation (lower priority)
Evidence of conflict is weak: only 2.7% of changes had 30% or more of their lines rewritten within 24 hours. Worth doing only with DELEG-07, and for the real friction found: Codex tool output shows 43 git permission-denied and 8 `index.lock` events. `DELEG-08 | Small-Medium | depends: DELEG-03 | worktree per lane, file-ownership map, pre-merge scope check.`

### 10. DELEG-09 Hosted-compute rules (conditional on E5)
Requires, before any new rental: per-box deadline, heartbeat, incremental output, destroy-on-first-error, and a recorded decision to raise any cap. `DELEG-09 | Experimental medium | depends: E5 | Acceptance: rules enforced in the controller; replay of the 2026-10-25 run would have stopped boxes A and B within 10 minutes.`

### 11. DELEG-10 Hygiene (trivial)
`tmp/` is untracked but not ignored; add it to `.gitignore`. The Vast controller log contains a plaintext instance API key in its first error line; rotate it and keep error text out of logs. Add a rate-card freshness test to the runner suite.

## Deliberately not proposed
New FanOutDispatcher, LeaseWatchdog, DeferredQuestionQueue, EngagementPlanner or a telemetry bus: equivalents exist (table above). A hosted-compute router before E5: the only evidence is one run. Changing the §3.2 model lanes before there is enough data (S10): current n per lane is 1 to 8.
