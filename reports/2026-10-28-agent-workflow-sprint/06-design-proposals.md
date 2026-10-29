# Design proposals (deliverable 5, revision 2)

Date: 2026-10-28 (revised the same evening after a second-pass review; the first-pass file is in `revision-1/`). Proposals rest on measured evidence ([M]) and verified facts only; each cites `02-baseline.md` or a data file. Where a literature source informs a proposal it is marked Hypothesis and cited in `04-extraction-table.md` (papers evaluate their own settings; none validates these designs for the Librarian). Nothing here changes product code; each proposal is a plan row you can adopt or drop.

**Naming.** `DEPLOY-xx` in the plan means vault-directory deployment (create, adopt, attach), so agent run patterns use a new prefix: **DELEG-xx** for development-delegation tooling (extends plan §3 and §11) and **HARNESS-10 and up** for runtime items. Sizes follow plan §3.1.

**Status words.** *Implemented* = code exists. *Planned* = a specification or plan row exists. *Missing in development tooling* = no code or plan row for the agents that build the Librarian.

## Design constraints

1. **No second authorization or qualification system.** Which model may take which role is already decided by exact-route qualification and expectation records (`model_invocation.py`, role bindings in `role_routes.py`, `docs/model-expectations-registry.md`). The quote-match percentages in this report are priors for choosing readers, not qualification evidence, and a report-side ledger must not become a parallel source of authority.
2. **Runtime vault writes keep the single Core writer with compare-and-swap.** File ownership and worktrees isolate development lanes only.
3. **Receipts are the record, reports are evidence.** Anything a report derives must be re-creatable from receipts, logs and git.
4. **Different model IDs are a procedural independence rule, not proof of independent errors.** Readers agreed on labels at Cohen's kappa 0.45 on 30 judgements, which says nothing about whether their mistakes are correlated.

## Requirements the evidence supports

| ID | Requirement | Evidence |
|---|---|---|
| R1 | Delegated output is cheap to check mechanically (typed, anchored, or test-gated), and a passing check means what it says | 3 of 11 triage batches were malformed JSON; 17 of 85 first-pass calls and 4 of 9 runner calls truncated; a verified quote does not prove its label (two "present" labels described static caps); quote-location fidelity is automated, interpretation precision is not (see M8) |
| R2 | Delegation records join to plan tasks, commits and findings, and live in one place | development records are in three places: repository receipts, a scratchpad ledger (25 calls) and scratchpad logs (20 calls, about $0.45 in no ledger); one orphan ledger entry, one duplicate call; the "four findings" of `33fb3b5` matched the wrong receipt until the reviewer's output was recovered |
| R3 | A fresh session resumes from a small amount of durable state, and the benefit is measured | the first requests after a limit cost 502.5k tokens for Claude (all cache creation) and 136k for Codex; this is the cost around a resume, not isolated waste; the plan is 31k tokens (§19: 17.6k); a 62-hour lockout |
| R4 | Dispatch can see each orchestrator's quota | both agents blocked up to 57% of 103 h (an upper bound); Codex bursts of 28 min then 4.6 h waits; calendar idle is not recoverable work |
| R5 | Concurrent writers are isolated, budgeted and accounted | overlap proxy 1.66 at 46% of tokens in workers; orchestration 12.6%; guardian reviews 9.5%; 43 git permission-denied and 8 `index.lock` events (friction, not merge conflicts) |
| R6 | The instrumentation is correct by construction | 3 of 8 stale rate cards (GLM-5.3 at half price), input estimate 27% high, failed calls charged at reserve, 36 of 57 launches returned before the call finished |
| R7 | Routing by task type rests on measured outcomes through the existing qualification seams | plan §3.2 calls its lanes "hypotheses"; Qwen3-Coder builder 0 of 2 accepted; DeepSeek-V4-Pro and GLM-5.3 drafts landed 9 times; the evidence is too thin to rank models |
| R8 | Hosted compute has deadlines, progress checks, collection and teardown | `G:\vast`: two boxes rented about 14 h with no output (an estimated $4.46 of $13.62), cap raised mid-run |

## Gemini's proposals against what already exists

Statuses come from two independent readers per component with anchor-verified quotes (`data/capability_matrix.csv`; Cohen's kappa 0.45) and from my direct reading of `tools/delegate.py`, `effort.py`, `tools/pace.py` and the harness specification `docs/audited-engagement-harness.md`. The architecture readers saw code packets, not that specification, so their "absent" labels for the capsule and exact-quote closure were too broad and are corrected here.

| Gemini proposal | Existing equivalent | Status | Gap |
|---|---|---|---|
| `ingest_and_verify_corpus` (two-stage stamping) | `deep_read.py` (paragraph-safe chunks that keep pages, quotes checked with `clerk.quoted`), `intake.py`, `pdf_markdown.py` | implemented (runtime) | no budgeted batch driver or independent second reader for development; this sprint's `sprint_dispatch.py` and `verify_anchors.py` are a prototype |
| `delegate_sandbox_script` (write-run-fix loop) | `sandbox.py` and `tools/sandbox.py` (a landing pad where "nothing on the pad is ever executed") | implemented, deliberately non-executing | an executable gate for development patches is missing (DELEG-06) |
| `pre_flight_audit` | `doctor.py` and the BASE tasks | partly implemented | |
| `telemetry.jsonl` bus | `trace.py`, session events (`model_request`, `model_response`, ADAPT-03) | implemented (runtime) | development receipts lack join keys (DELEG-01) |
| compute router and cost quantifier | `effort.py` (static caps), `role_routes.py`, `service_routes.py`, `hosts.py` limiter, runner `reserve_cost` | caps implemented | no cost model and no hosted-compute route; **`pace.py` is `set_effort`, not pacing** |
| FanOutDispatcher | `tools/delegate.py` (parallel read-only helpers, caps from the effort slider, profile guard), `batch.py` | implemented (runtime) | typed, anchored helper results are planned inside HARNESS-04/06 |
| LeaseWatchdog | `coordination.py` (`DocumentLeases`, vault lease, Obsidian heartbeat, `VaultWatcher`) | implemented for documents | missing for long-running agent tasks |
| DeferredQuestionQueue | `broker.py` (an unanswered request expires and parks the session), `8a34cc7` | implemented | HARNESS-03 plans question blocking |
| EngagementPlanner | HARNESS-04 manifest ("remaining budget"), `effort.profile` budgets | planned and partly implemented | |
| context capsule | `docs/audited-engagement-harness.md` §7.5 `ContextCapsule`: bounded, redacted, with a hard token budget, assembled for one fresh executor or auditor call | specified; HARNESS-03/04 are plan rows | a capsule for **development agents** resuming after a limit is missing (DELEG-04) |
| closure by exact quote presence | HARNESS-06 ("the quote is present in evidence `<id>` at offset N, never the claim is true"), HARNESS-07 (protected-target diff) | planned | a development-side analogue is DELEG-02/03 |

In development tooling, quota awareness, an executable gate, lane isolation and a drafter-not-reviewer check are **missing as code**. The runtime harness already specifies a capsule and exact-quote closures, so the development proposals below reuse that vocabulary instead of inventing another.

## Proposals, in priority order

### 1. DELEG-01 Runner hygiene and receipt v2 (adopt first)
- **Requirement.** R2, R6.
- **Evidence.** orphan `started` entry whose output exists; duplicate call 55 s after the first, itself truncated; 4 of 9 completed calls truncated; stale cards; failed-call cost is the reserve; development records scattered over three places; launches that return before the call finishes.
- **Change** (extends `scripts/delegate_deepinfra.py`; `a328e7c` already fixed the ledger race): persist the complete **redacted request and contract**, manifest, schema and route identity with the receipt; separate **transport state** (launched, running, returned, failed) from **acceptance state** (not reviewed, accepted, rejected, partly); link launch, process, completion and result consumption by `run_id`; refuse a second identical packet hash while a receipt for it is `started`, with the check **atomic with the reservation** and an expiry derived from the call's own timeout (a fixed ten-minute exclusion is shorter than the 900-second timeouts used here); exit non-zero on `finish_reason=length` unless `--allow-truncated`; record `--task-id`, `--role`, `--parent-run`, `--agent`, `cost_basis` (metered or reserve) and later the commit hash; compare rate cards with the live listing at start (`deepinfra_check.py` is a working version); write all agents' calls to the same ledger (the scratchpad runners did not).
- **Cost.** low. **Risk.** low; stricter exits may need a flag for callers.
- **Plan row.** `DELEG-01 | Small | depends: none | owner review | Acceptance: regression tests for atomic duplicate refusal with timeout-derived expiry, truncation exit, price check, state separation and receipt fields; the measured defects each have a failing-then-passing test.`

### 2. DELEG-02 Typed, anchored delegate output with a local verifier
- **Requirement.** R1, R2.
- **Evidence.** 1,963 first-pass items and the revision-2 full-text readings were checked mechanically (see `04-extraction-table.md` and `data/lit2_summary.json`); repair of a missing brace rescued 3 of 11 batches and salvage rescued truncated outputs; review findings are not stored as data, so M4 had to be rebuilt from prose.
- **Change.** promote `verify_anchors.py` to `scripts/verify_delegate_output.py` with a schema argument. Critic packets require `findings[]` with the **exact source hash and offset, the claim, the evidence quote, a falsifier and a separate disposition** (upheld, rejected, partial, with a commit hash and the adjudicating agent). A quote that is present does **not** make the claim supported: record quote-validity and claim-support as two fields. Keep the raw malformed or truncated output, the repair applied and a missing-item status; a salvaged array never proves completeness.
- **Cost.** low to medium. **Risk.** over-trusting anchors; a label such as "present" needs its gap text reviewed.
- **Plan row.** `DELEG-02 | Small-Medium | depends: DELEG-01 | Acceptance: the verifier reproduces this sprint's quote-location rates on the saved lane outputs; fixtures cover brace repair, truncation salvage, an adjacent-page quote and a quote-valid but unsupported claim; a disposition file feeds the hold-up metric without hand counting.`

### 3. DELEG-03 Packet lint and diff-scope guard
- **Requirement.** R1, R7. **Evidence.** plan §3.3 fields are unenforced; builder output was rejected for initialisation order and legacy semantics (a "preserve existing behaviour" field would target exactly that); no code path checks that drafter and reviewer differ.
- **Change.** a lint that fails a packet missing a §3.3 field or naming one model ID as drafter and reviewer (a procedural rule, see constraint 4); a **pre-landing** `check_diff_scope` on the candidate patch that fails on forbidden files, **deletes, renames and tests that weaken an acceptance check**, and keeps an owner-approved test or oracle outside the delegate's reach.
- **Cost.** low. **Risk.** low.
- **Plan row.** `DELEG-03 | Small | depends: DELEG-01 | Acceptance: lint and scope check have positive and negative fixtures including a deleted test and a renamed file; M9 becomes measurable.`

### 4. DELEG-04 Resume capsule for development agents (prototype and test)
- **Requirement.** R3. **Evidence.** the cost around post-limit resumes (502.5k and 136k tokens, containing the cache rebuild and the first productive request); the plan is 31k tokens to read cold; two commit messages record work "left uncommitted at its usage limit"; the harness specification already defines a bounded `ContextCapsule` (§7.5) for runtime sessions.
- **Change.** `scripts/write_resume.py` writes `resume.json` before a stop or on request, reusing the specification's vocabulary: git state hash, branch or worktree, last green commit, **diff and receipt hashes**, uncommitted files with diffstat, open receipts, **constraints, unresolved judgments and artifact references**, pending verifications, next action, other agents' reset times. A capsule must be revalidated against the actual branch, worktree and vault state and refreshed when stale. Hypothesis: a fresh context plus capsule reaches a verified first action for less than a restored conversation. **That saving is not asserted until E3 shows it**, and E3 compares correctness to completion and total role costs, not the first edit only.
- **Cost.** medium. **Risk.** a stale capsule misleads; refuse on a state-hash mismatch; copying one long summary into every prompt preserves errors as efficiently as facts.
- **Plan row.** `DELEG-04 | Medium | depends: DELEG-01 | Acceptance: experiment E3 on three recorded handoff points reports correctness, cache writes and reads, total role costs and time to a verified action for both conditions; adopt only if the capsule is no worse on correctness and cheaper.`

### 5. DELEG-05 Auto-recorded delegation lines and closure check (adopt narrowly)
- **Requirement.** R2, R3. **Evidence.** 41 of 118 commits are bookkeeping-only (0.55 per code commit); §19 grew to 17.6k tokens; the "four findings" record could not be matched to a receipt.
- **Change.** generate the §19 delegation line (task, model, tokens, cost, disposition) from receipts, reusing the Session event vocabulary and existing plan status values; `check_task_closure` fails a "done" row without a commit hash and test names, and requires a documentation diff **or an explicit "no documentation change required"** (not every legitimate fix changes a document). Do not make the 31k-token plan the canonical event database.
- **Cost.** low. **Risk.** low. **Plan row.** `DELEG-05 | Small | depends: DELEG-01, DELEG-02 | Acceptance: the generated line replaces hand-written ones for new packets; the closure check passes on the last 10 §19 entries or lists their gaps.`

### 6. DELEG-06 Executable acceptance gate (small local pilot, moved earlier)
- **Requirement.** R1. **Evidence.** drafts checked by golden fixtures (ADAPT-04, 05) landed with at most two fixes; concurrency-sensitive changes cost more to settle; the single-shot runner cannot run tests by design. Literature distinguishes an artifact that executes from one that is semantically right (`04-extraction-table.md`, E-rows).
- **Change.** apply a proposed patch in an existing worktree-isolated scratch tree with explicit execution limits, run the packet's declared test command against **task-specific positive and negative fixtures**, and return pass or fail plus at most 40 lines. Tasks touching `host.py`, `coordination.py`, `connection.py`, `cli.py`, `mcp_server.py` or the writer keep the established Windows owner-host full-suite gate (plan §3.2). Passing tests the delegate wrote itself is not sufficient.
- **Cost.** medium. **Risk.** sandbox safety and false confidence on weak tests. Run experiment E2 on a small pilot first.
- **Plan row.** `DELEG-06 | Experimental medium | depends: DELEG-03 | kill criterion: no reduction in post-result work or rework on 10 paired packets | Acceptance: written go or no-go with measured post-result intervals, rework and the fixtures' known-bad detection rate.`

### 7. DELEG-07 Limit-aware scheduling (defer automation)
- **Requirement.** R4. **Evidence.** up to 57% of the window with both agents blocked; Claude weekly lockout 62 h; Codex bursts 28 min. Codex logs expose `used_percent` and reset times; Claude exposes a limit only when it hits.
- **Change.** begin with an **observational** status script (latest Codex quota, last Claude limit and reset) and a replay (E6); automate routing only if the replay shows coverable work. Available backlog, task dependencies and actual demand decide whether idle time could have been used.
- **Cost.** medium. **Risk.** Claude's quota is only partly observable; a wrong estimate wastes a window; runtime `effort.py` is static and is not the place for this.
- **Plan row.** `DELEG-07 | Experimental medium | depends: DELEG-04 | kill criterion: replay shows under 10% of blocked hours were coverable | Acceptance: replay report on 2026-10-24 to 28 data.`

### 8. HARNESS-10 Typed helper results at runtime (fold into HARNESS-04/06 where possible)
- **Requirement.** R1. **Evidence.** `tools/delegate.py` fans out read-only helpers but returns free text cut at 4,000 characters per helper. HARNESS-04 (bounded projection) and HARNESS-06 (exact quote-presence closure) already plan the verification side.
- **Change.** helper replies carry `sources[]` (note name, offset, verbatim quote) checked by the loop before the lead sees them; keep a **raw-result handle** before the 4,000-character cut; reuse invocation usage and route fingerprints and Core-owned verification; read-only helpers keep their existing authority.
- **Plan row.** `HARNESS-10 | Small-Medium | depends: HARNESS-04 | Acceptance: helper results with an unverifiable quote are marked, a raw handle is kept, with a test; close this row if HARNESS-04/06 already deliver it.`

### 9. DELEG-08 Lane isolation (prerequisite for concurrent writers)
Evidence of conflict is weak (3.0% of mature changes had 30% or more of their lines rewritten within 24 hours), but that is not evidence that shared writable lanes are safe, and Codex tool output shows 43 git permission-denied and 8 `index.lock` events. Do not defer this until a scheduler exists: any concurrent writers need a worktree per lane, a file-ownership map and a pre-merge scope check first. `DELEG-08 | Small-Medium | depends: DELEG-03 | prerequisite for concurrent development writers; runtime vault writes keep the single Core writer and compare-and-swap.`

### 10. DELEG-09 Hosted-compute rules (conditional on E5)
Before any new rental: a per-box deadline, a progress watchdog, checkpoint and result collection, teardown after a **terminal** failure, bounded retries for recoverable faults, and a recorded decision to raise any cap. ("Destroy on the first error" is too broad: it can lose useful work.) `DELEG-09 | Experimental medium | depends: E5 | Acceptance: rules enforced in the controller; replay of the 2026-10-25 run would have stopped boxes A and B within 10 minutes without discarding collectable output.`

### 11. DELEG-10 Hygiene
`tmp/` is untracked but not ignored; classify its contents first. Ignore disposable and sensitive scratch data (transcripts, packets, raw model output) but preserve the redacted evidence, contracts and artifacts needed to reproduce published results. The Vast controller log contains a plaintext instance API key in its first error line; rotate it and keep error text out of logs (no credentials were inspected or rotated in the second-pass review either). Add a rate-card freshness test to the runner suite.

## Deliberately not proposed
New FanOutDispatcher, LeaseWatchdog, DeferredQuestionQueue, EngagementPlanner or a telemetry bus: equivalents exist (table above). A hosted-compute router before E5: the only evidence is one run. Changing the §3.2 model lanes or ranking models from quote-match percentages: current n per lane is 1 to 8, and route qualification belongs to the existing expectation records.
