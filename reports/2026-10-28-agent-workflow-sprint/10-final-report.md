# Final report: how agents use and build the Librarian, and what to do about delegation

Date: 2026-10-29. This is the synthesis you asked for after the second-pass review and the overseer-workflow review. Nothing was committed and no product code changed. `00-summary.md` stays as the revision-2 summary; this file is the entry point and `00` to `09` are the evidence.

**What came in.** You sent two analyses to weigh. The first is the second-pass review of my first pass. I had already answered it point by point (`09-response-to-second-pass.md`), and its three report files have not changed since 21:41Z on 2026-10-28, so the text you pasted again adds nothing new. The second is new: the overseer-workflow review in `../2026-10-28-deepinfra-overseer-workflow/` (the "overseer review" below). It asks how Claude and Codex could hand DeepInfra complete, checked work rather than drafts. I read its report and evidence file in full, checked its facts against my data (section 3), and combined the three analyses into one recommendation.

**Tags.** [M] measured by a re-runnable script from machine-written records. [R] reported by an agent, a transcript or a commit message. For outside claims: *verified* (primary source read, date given), *plausible*, *unverified*. **Hypothesis** marks my inference or proposal; nothing under that word is evidence. Designs rest only on [M] and verified facts.

## 1. The answer on one page

**Where lead effort and quota go.** The scarce resource is the lead's capacity, not API money. Development delegation cost about $1.15 over 57 calls in five days, and the median call cost 1.7 cents [M]. In the same days Claude was locked out for 62 hours by its weekly limit (65.6 hours counting two earlier 5-hour limits) and Codex hit 59 usage-limit turns; both were blocked for up to 59 of 103 hours (57%, an upper bound, because Codex idle time includes your absences) [M]. Modelled at list prices a median accepted change cost the lead $3.09 (n=24, shadow dollars, not billing) [M]. Resuming after a limit costs the lead 502.5k tokens for Claude (all cache creation, n=3) and 136k for Codex before the first productive action [M].

**What delegation has been.** One call that returns a proposal. The lead applies it, runs the tests and repairs it. Nine commits record a delegate draft with 0 to 2 review fixes each (seven by DeepSeek-V4-Pro and two by GLM-5.3, as their commit messages say), the adapter ones protected by golden fixtures; Codex's two builder attempts produced nothing accepted; 4 of the 9 real Codex runner calls stopped at the output cap [M]. ADAPT-09 shows the failure mode in one case: the draft returned in 11.9 s for $0.009, the lead's own splice script edited the source and then failed on the test file, and the weekly limit arrived [M][R].

**What we cannot say.** Whether delegation saved lead effort. No comparable direct-work baseline exists, and the first pass's "checking costs 6 to 8 times the output" came from commands that merely mentioned a runner; it is withdrawn [M]. All three analyses treat 20/80 as a target, not a result.

**What checking is.** Three separate things. That the quote exists is cheap and scriptable: 97.7% of 1,771 reading items sit on the cited page under a lenient comparison (letters and digits only) and 91.8% under the strict one [M]. That the quote supports the claim needs a second look: of 60 sampled items a third-family judge found 45 supported, 12 partly and 3 not; I read its 15 flags and 5 passes, kept 13 of the 15 flags and overturned 2, and agreed with all 5 passes [M]. That the reading covers what matters needs a checklist written before reading: against 25 passages chosen independently, the primary reader's items contained 13 by rule, both readers' items together 16, and 22 after I read the rest [M].

**What the three analyses agree on.** Delegation as practised returns proposals and leaves execution with the lead. The saving is unmeasured. "Done" hides four states (provider response, usable artifact, verified behaviour, integration). Native Codex subagents are not DeepInfra and must be counted apart. Parallel work needs isolation before scale. Gemini's absolute rules ("never read unless two workers disagree", "a ten-line spec is enough") do not hold.

**What the overseer review adds, and I adopt.** The unit of delegation should be a *work package* whose completion means evidence, not an answer: admission, worker ownership, an evidence-bearing completion record, and escalation and resumption. A local controller, not the hosted model, applies the patch, runs the checks and allows bounded repair. Acceptance fixtures are protected. A three-arm comparison (direct lead, today's one-shot delegation, managed work package) is the only way to turn the break-even idea into a measurement, and an accounting identity gives 20/80 a defensible meaning (section 6).

**What I recommend.**
- **Now (small, no new capability):** DELEG-01 receipt v2 and one ledger, importing the Claude scratchpad ledger and the overseer ledger; DELEG-11, a one-page work-package contract that maps onto plan section 3.3; pick the pilot task class and write its protected fixtures.
- **Next (one complete path):** DELEG-03 (packet lint, protected fixtures, diff-scope guard) and a reshaped DELEG-06 (controller-run apply, check and at most two repair rounds) on that one class; an interruption drill (E14); then the three-arm comparison (E2').
- **Later, only on evidence:** capsule (DELEG-04, after E3), limit-aware scheduling (DELEG-07, after E6), lane isolation before any concurrent writers (DELEG-08), hosted compute (DELEG-09, after E5), model routing (after E12).
- **Not proposed:** new dispatcher, watchdog, planner or telemetry components; changes to the plan's model lanes; importing Gemini's 90% or "never read" rules.

**What I need from you** (section 9): the `DELEG-xx` prefix, the pilot class, the meaning and thresholds of 20/80, permission to import the stray ledgers, a standing rule for DeepInfra exports, and three smaller items.

## 2. The three analyses and how far I trust each

| | Sprint (mine, revision 2) | Second-pass review | Overseer review |
|---|---|---|---|
| Question | Where do agents spend lead effort and quota, and what should be built | Is the sprint right | How should delegated work own execution, checking and recovery |
| Evidence | Five transcripts, the Claude Code and Codex session logs, git, receipts, ledgers; 50 papers read in full | The sprint's outputs, 50 PDFs, 168 saved quotations, 58 external-claim entries | The same five transcripts read by 13 DeepInfra calls (100 of 104 episode anchors present, none adjudicated by the model), 12 transcript anchors adjudicated locally, source, test and commit inspection |
| Measured or argued | Measured by scripts, reconciled against independent counters | Re-checked, ten findings | Argued from cases; no new metrics; takes its numbers from a snapshot of my revision 2 |
| DeepInfra spend | 168 calls, $4.48 at live prices (both passes) | none; it states that no paid model calls were needed | 14 calls, $0.3573, in its own ledger |
| Cannot show | That delegation saved lead effort | | That the controller works, or any saving |

The overseer review and the sprint share one evidence population (the five transcripts and my revision-2 snapshot). They are not independent replications of each other.

## 3. What I checked in the overseer review

| Its claim | My check | Result |
|---|---|---|
| About $1.15 over 57 development calls; nine delegate-drafted commits; 4 of 9 completed real Codex-runner calls at the output cap | `delegate_events.csv` and `delegate_inventory.json` are byte-identical to its snapshot. The 56 completed calls with a cost sum to $1.115 (the failed call is charged at its reserve). The Codex runner has 10 completed calls, one of them the 147-token canary; 4 of the other 9 ended at the cap | Confirmed [M] |
| It used a snapshot of revision 2 | `02-baseline.md` differs from the snapshot in 17 lines, all small corrections from my data cutoff (for example both-blocked 59.1 to 59.0 h, overlap 1.65 to 1.66, orchestration 12.5% to 12.6%, thread counts 3 and 54 to 2 and 53, and one wording change on review attribution). The overseer report uses none of these figures | Consistent [M] |
| ADAPT-09: 11.9 s, $0.009, then a crashed integration and the weekly limit | Ledger row: DeepSeek-V4-Pro, 11.9 s, $0.009, finish `stop`. Transcript lines 985 and 1048 to 1085: source written at 1069, `IndexError`, no test file, "no tests ran", weekly limit. The work landed as `c06d1b6` at 03:16Z on 2026-10-26, after the 01:00Z limit, with no "Drafted by" line | Confirmed [M][R]. My count of nine delegate-drafted commits is a floor: commit text cannot say whether `c06d1b6` built on the draft |
| Transcript cases E2 to E8 | 12 line cites checked in the Claude, Codex-2, research and Gemini transcripts (for example Codex-2 lines 2452 native agents, 3186 transport retry, 760 checkout reset, 1666 worker limits; research 1798 to 1807, 3850 to 3869, 430 to 451; Gemini 207 and 216) | All 12 say what the report says [R] |
| Repository anchors | Commits `d2f7f81` and `b242d8b` (DeepSeek-V4-Pro drafts, 1,323 and 1,333 passed in the commit text, not rerun); the two byte-identical request-body tests; `retries=()` at `scripts/delegate_deepinfra.py:480`; plan sections 3.2 and 3.3 at lines 145 and 169; the INDEX-05 report's delegation table | All present as described [M] |
| Prices and arithmetic | MiMo-V2.6-Pro and GLM-5.3-Flash prices equal my live check from the same endpoint on the same day. First call recomputed: 55,768 x $0.43/M + 4,485 x $0.87/M = $0.027882 | Confirmed [M] |
| Spend is reconciled to "the local ledger" | Its 14 calls sit in a separate ledger (budget $5, agent `codex-overseer-research`, receipts under `tmp/overseer-workflow/runs/`). The repository ledger holds 11 calls ($0.1552) and `claude-ledger.json` $4.30 | Records now live in five places (section 7, DELEG-01) [M] |
| Nine paper ranks (#01, #03, #07, #11, #14, #26, #28, #42, #45) and their facts | All nine are among my 14 high-priority papers. Its EToT facts (Judge overhead on page 8, 55 s to 26 s) are in my reader's items. The strict check had marked the Judge quote "unverified" because the PDF breaks "VLM- related" across a line | Facts confirmed; exposed a bias in my instrument (below) |
| Four outside sources | Fetched 2026-10-29 (appendix A) | Verified, with two qualifications |
| Its remote critic | It saw only a newly written abstract contract, so its private facts had no independent remote check, as the report says | Noted |

**Result.** In the parts I checked I found no factual error in the overseer review. Two qualifications: the scaling paper's headline numbers changed between versions (it cites v2, whose numbers are right for v2), and Agentless's reproduction-test rule is "keep a test only if it reports the issue on the original repository", which is a fair reading of "should fail on the original code" but not the paper's words.

**Three weaknesses in my own instruments that the check exposed.**
1. The strict page check misses quotes broken by hyphenation. A lenient comparison (letters and digits only) moves 104 of the 145 misses onto the cited page (98 on it, 6 starting on it and running onto the next, which the strict rule also accepts): 97.7% instead of 91.8% (MiMo 98.1%, GLM-5.3 98.3%, GLM-5.3-Flash 94.4%), and 30 quotes (1.7%) are not found anywhere in the paper [M] (`scripts/hyphen_recheck.py`, `data/hyphen_recheck.json`). The strict rate is a floor. The coverage figure of 22 of 25 is also a floor: the EToT "verifier cost dominates" passage, listed as missed, was extracted and sits on page 8 (rank 7, costs, page 8 in `data/hyphen_recheck.csv`).
2. Commit-text provenance undercounts delegate drafts (`c06d1b6`).
3. Spend records are scattered across five places: the repository ledger, `claude-ledger.json`, the Claude scratchpad ledger, the scratchpad reader logs (no ledger), and the overseer ledger.

## 4. Where the analyses agree, extend each other, or differ

| Topic | What the evidence says | Source |
|---|---|---|
| Cost of checking delegate output | Unknown. The 6 to 8 times ratio is withdrawn; the post-result interval (Claude median 8.4 min and 17.2k tokens, Codex 7.6 min and 25.2k, n=6) is an upper bound that includes integration and unrelated work. Only a direct baseline can settle it | Sprint, second pass, overseer all agree |
| Review precision | 6 of 12 pooled dispositions is a tally, not precision; all six commit-recorded reviews were commissioned by Claude; three of five events record only upheld findings | Sprint, second pass; overseer does not reuse it |
| Native versus external workers | Codex's 148 spawned workers used 46% of its fresh and output tokens [M]; its own transcript says the recent delegation was to built-in subagents, not DeepInfra (Codex-2 line 2452) [R]. Native subagents spend the same quota family in parallel; they are not quota relief | Sprint and overseer agree |
| Who owns execution | The runner makes one call and cannot run tests by design, so apply, run and repair stay with the lead. The overseer review makes this the central gap | Overseer extends the sprint |
| What "verified" means | Quote present, claim supported and coverage adequate are separate for research; applies and runs, satisfies behaviour and integrates are separate for code | Sprint (research), overseer (code) |
| Parallelism | Overlap 1.66 is not speed-up. The scaling paper finds sequential tasks degrade under multi-agent arrangements (v2: worst case about -70%) and Anthropic says most coding tasks have fewer parallelisable parts than research (both verified, appendix A). Isolate lanes first | Sprint and overseer agree; outside sources support |
| Gemini's rules | "Never read unless two workers disagree": agreement can share an omission, two readers agreed on labels at kappa 0.45, and two of the judge's three "not supported" flags were false alarms that only a reading caught. "Hoarded 90%", "6.5 out of 10": not tested | Sprint and overseer agree |
| Hosted compute | One run, 31 jobs for $13.62, two of the six boxes in the box table dead about 14 hours (the controller summary counts seven rentals). Defer | Sprint and overseer agree |
| Gate versus repair loop | The sprint's DELEG-06 returned pass or fail; the overseer review argues the repair loop belongs inside the package, otherwise the lead stays the repairer. **I adopt that** (section 7) | Overseer corrects the sprint |
| Direct baseline | The sprint's break-even was observational; the overseer's three-arm design is the missing measurement. **Adopted** | Overseer corrects the sprint |
| Retrieval for the worker | The overseer review would let the worker fetch more context through the controller; the sprint only has fixed packets. Untested either way; it becomes a factor in E7, not a pilot feature | Open |
| Order of work | The sprint put hygiene first; the overseer review puts the execution boundary first. They do not conflict: DELEG-01 and the contract are small and come first, the pilot follows | Merged |

## 5. The merged recommendation

### 5.1 The unit of delegation is a work package

The sprint and the overseer review find one gap from two sides. The runner makes one audited call and returns an untrusted proposal; apply, run, diagnose and repair remain with the caller, so the lead keeps the expensive steps. The remedy is a work package whose completion means evidence. Four boundaries, from the overseer review:

1. **Admission.** Task, base revision, allowed effects, protected acceptance fixtures with hashes, environment identity, resource ceilings and the acceptance method. A task with no defensible acceptance method may still be delegated for exploration, but is labelled exploratory.
2. **Worker ownership.** The worker proposes; the local controller, not the hosted model, applies the patch in an isolated worktree, runs the declared checks in a pinned environment and allows at most two bounded repair rounds.
3. **Evidence-bearing completion.** Artifact reference, base revision, exact changes, the checks that were run with results by reference, unresolved findings, cost and a proposed disposition, all recorded by the controller. The worker's prose is not the record.
4. **Escalation and resumption.** Ambiguity, scope change, exhausted ceilings and repeated failure return to the lead. A partial answer, a truncated answer, an unknown network outcome and a verified artifact are different states. Resume from the artifact and the environment, not from a conversation summary.

For code, three predicates are recorded separately: it applies and runs, it satisfies the behaviour, it integrates. For research, four: the source is the right one, the quote is present, the claim is supported, coverage is adequate. None is replaced by a worker saying "verified". This is plan section 3.3, the existing packet contract, made executable. It adds protected fixtures, environment identity, ceilings and the completion record. It creates no second authority over roles or models.

### 5.2 Where to start

Start where an oracle already exists: refactors and extractions that preserve behaviour and can be fixtured before the change, like ADAPT-04 and ADAPT-05 (golden request bodies captured first, tests compare byte-identical requests [M]; 1,323 and 1,333 tests passed per the commit text [R]). Keep concurrency, lifecycle and writer-ownership changes lead-led with mapper and critic helpers: in the INDEX-05 chain the Qwen builder patch was rejected for initialisation order, legacy semantics and a defective test patch, and a later builder timed out [M]. The ADAPT results show accepted contributions, not a labour ratio.

### 5.3 Deployment patterns by task type (revises `05`)

| Task type | First choice | Check | Do not |
|---|---|---|---|
| Counting or joining facts in logs, git, ledgers | Deterministic script | Reconcile against an independent total | Ask a model to count |
| Reading transcripts, papers or code for evidence | Anchored extraction by the primary reader, a second family on a sample | Quote location by script, support audit on a sample, coverage checklist written before reading | Treat a present quote as support, or skip adjudication because two readers agree |
| Behaviour-preserving refactor or extraction with a fixture | Managed work package (the pilot) | Protected fixtures run by the controller | Delegate without an oracle, or let the worker replace the oracle |
| Bug fix with a reproducer | Managed work package after the pilot | Reproducer fails before and passes after, plus regression | Accept "tests pass" when the worker wrote the tests |
| Concurrency, lifecycle, writer ownership | Lead-led, with mapper and critic helpers | Owner-host full suite (plan section 3.2) | Accept an unmeasured builder patch |
| Review of a finished change | Typed findings with a falsifier, scored on known-bad and verified-clean changes | The lead adjudicates each finding against code | Judge a reviewer by precision alone |
| Breadth exploration | Read-only parallel helpers bounded by quota | Each lane's own checks | Parallel writers on one checkout |
| Long sweeps on hosted compute | Oracle, deadline, progress watchdog, collection | Pre-registered predictions | Rent first and write the deadline later |
| Work that must survive a limit | Write the state first (capsule is a hypothesis until E3) | Revalidate against the actual branch and worktree | Rely on an open conversation |

### 5.4 What stays out for now

Model routers and swarms, a hosted-compute migration, a telemetry bus, and a second qualification system. Most of Gemini's components already exist in some form (`06`). More parallel calls before the execution boundary works only enlarge the review queue: MAST finds 14 failure modes in three categories and that successful runs are not failure-free (verified, appendix A), and Anthropic says multi-agent systems fit poorly where agents share context or depend on each other (verified vendor statement, appendix A).

## 6. What 20/80 would take

Take the overseer review's identity (D is the lead effort for a comparable task done directly, d the fraction of D removed by moving execution to workers, h the added briefing, review, integration and expected rescue, as a fraction of D):

**Remaining lead effort / D = (1 - d) + h.**

It is the break-even of `01` (delegate when T_direct exceeds T_packet + T_follow-up + p_reject x T_redo) written as a fraction, with h = (T_packet + T_follow-up + p_reject x T_redo) / D. **Hypothesis (arithmetic on that identity, not data):**

- Leaving the lead 20% needs h to be at most d - 0.8. Even when d = 1 that is h of 0.2 or less; at d = 0.9 it is 0.1 or less.
- If a rejected result means the lead redoes the whole task, p_reject must be at most 0.2 minus all other overhead: about 0.1 if the rest costs 0.1. If a rejection costs only a small repair (say 0.2 D), p_reject can reach about 0.5 on the same budget.
- A fixed per-task handoff cost f (write the brief, read the completion record, merge) sets a minimum task size. The measured upper bound on lead time between re-reading a delegate result and the next commit or launch (capped at 3 hours) is a median 8.4 minutes for Claude and 7.6 for Codex [M], including unrelated work. If f were that large, a 10% overhead budget needs D of roughly 84 minutes (Claude) or 76 minutes (Codex), or more. So 20/80 is unlikely on small tasks whatever the worker's quality, and the pilot class should be chosen for size as well as for an available oracle.

**What to measure.** Primary: R, the remaining lead effort divided by D per accepted task, paired by task, with failed and abandoned tasks in the denominator. Lead effort is read from the logs I already parse: lead requests, lead tokens by component (ordinary input, cache creation, cache read, output), active time (the sum of gaps between lead requests below a threshold to be fixed before the pilot) and, for Codex, the quota percentage. Secondary: the worker-owned share of planned units, fixed at admission and effort-weighted; generated tokens are not a measure. Also manual rescue count, escaped defects against protected fixtures, elapsed time and API cost.

**What n can resolve.** The 95% half-width on a mean of n paired ratios is t x sigma / sqrt(n): 0.64 sigma at n = 12 and 1.05 sigma at n = 6. If sigma is 0.25 (a guess; estimate it from the first six pairs), twelve pairs in one class separate R = 0.2 from R = 0.5 but not 0.2 from 0.3, and six pairs in a class (half-width 0.26) can show a gross failure but not confirm 20/80. So claim 20/80 for a task class with a stated interval, and accept a lower gain if that is what the data show.

## 7. Plan rows (merged; the unchanged rows are in `06`)

Sizes follow plan section 3.1. These are proposals for you to adopt or drop; I did not edit `docs/unified-implementation-plan.md`.

| ID | Size | Depends | Change relative to `06` | Acceptance |
|---|---|---|---|---|
| DELEG-01 Runner hygiene, receipt v2, one ledger (amended) | Small | none | Everything in `06` section 1, plus an uncertain-outcome state (an unknown outcome keeps its reserve and blocks relaunch of the same packet until reconciled; the INDEX-05 mapper's $0.00589 reserve is the precedent), per-task and total reservation ceilings and attempt counts in the receipt, `agent` and `host` fields so Claude and Codex write the same record, and one-time marked imports of the Claude scratchpad ledger (25 calls, $0.5457), the scratchpad reader logs (20 calls, about $0.45, in no ledger) and the overseer ledger (14 calls, $0.3573) | As in `06`, plus a test that an interrupted run neither loses nor repeats a paid call, and an import test that reproduces the totals above |
| DELEG-11 Work-package contract, specification only (new) | Small | none | One page and a JSON schema draft for the four boundaries in section 5.1. Reuses plan section 3.3 field for field and adds only what it lacks | Every section 3.3 field maps to a contract field; ADAPT-05 filled in by hand on one page; a Claude and a Codex session can each complete the form for a new task unaided |
| DELEG-03 Packet lint, protected fixtures, diff-scope guard (amended) | Small | DELEG-01, DELEG-11 | `06` section 3, plus: lint fails a packet that names no acceptance method or whose checks do not cover the stated behaviour (a generic green suite is not admission evidence); protected fixtures are fingerprinted so changing one invalidates completion; worker-written tests add evidence and never replace the owner's | Positive and negative fixtures including a deleted test, a renamed file, a weakened assertion and a fixture edited by the worker; M9 becomes measurable |
| DELEG-06 Controller-run apply, check and bounded repair, pilot (reshaped) | Experimental medium | DELEG-03 | Was a pass or fail gate. Now the controller applies the patch in an isolated worktree, runs the declared checks in a pinned environment (interpreter and dependency identity recorded; a mismatch stops for requalification), feeds failures back for at most two repair rounds and writes the completion record. The hosted model executes nothing. One task class. Windows-host-sensitive files keep the owner-host gate | Kill criterion: no reduction in R against the direct arm in E2'. Written go, narrow or stop decision with measured R, escaped defects and the fixtures' known-bad detection rate |
| DELEG-02 Typed, anchored output and verifier (one addition) | Small to medium | DELEG-01 | As in `06` section 2; the record carries the code and research predicates separately; the page check normalises hyphenated line breaks (104 of 145 misses recovered: 98 on the page, 6 running onto the next) | As in `06`, plus a fixture for a hyphenated break |
| DELEG-05 Completion record and generated plan line (amended) | Small | DELEG-01, DELEG-02 | Generate the plan section 19 delegation line and the lead-facing summary from controller records, not worker prose | As in `06`, plus a summary that fits one screen with evidence linked by reference |

**Unchanged and deferred:** DELEG-04 (after E3), DELEG-07 (after E6), DELEG-08 (a prerequisite for concurrent writers), DELEG-09 (after E5), HARNESS-10, DELEG-10.

**What the pilot costs.** The DeepInfra calls are cheap: a median 1.7 cents, 90th percentile 4 cents, maximum 7.8 cents across 56 completed development calls, and 86 s median duration [M]. Twelve tasks in three arms with three to six calls per managed task come to roughly $1 to $4 (Hypothesis, from those per-call figures). The real costs are building DELEG-06 (medium) and the lead sessions the comparison needs.

## 8. How to find out

| # | Question | Design | Decision rule | Cost |
|---|---|---|---|---|
| E2' (replaces E2) | Does the managed package cut remaining lead effort at equal quality? | Stage A: twelve tasks in the pilot class (oracle-backed refactor or extraction), three arms (direct lead, one-shot delegation as today, managed package), frozen base revision, protected fixtures, blinded independent scoring, a fresh session per arm so cold start is separable. Stage B, only if A passes: six tasks in each of two more classes (reproducible bug fix, evidence extraction), enough to show a gross failure but not to confirm 20/80 for the class. A cheaper variant of A replays historical direct tasks at their parent commit and takes the direct arm from the logs (M1), calibrated by four prospective direct runs; the retrospective baseline includes unrelated chatter and therefore flatters the managed arm. For Codex leads, a fourth arm using built-in subagents under the same contract would show whether an external controller pays | Thresholds are yours to set before running; my proposal, using the mean R and its 95% t-interval (a paired bootstrap if the ratios are skewed; report the median too): stop if mean R is 0.8 or more or escaped defects exceed the direct arm's; narrow to classes where mean R is 0.5 or less; claim 20/80 on a class only if mean R is 0.2 or less and the upper end of its interval is below 0.5 | API $1 to $4; lead sessions dominate |
| E14 | Does an interrupted job resume without repeating paid work? | Kill the controller after the worker call returns and before apply; resume from artifact state; repeat after a simulated limit under each lead | Zero repeated paid calls, the uncertain reserve retained, same completion record | free |
| E1, E3, E5, E6, E9, E11, E13 | as in `07` | | | |
| E7 (extended) | Does a smaller budgeted packet, or worker retrieval through the controller, change hold-up or rework? | Full packet, anchored-excerpt packet under a token budget, and packet plus bounded retrieval, on the same task | Recall of needed facts, wrong assumptions, retries, rework | about $0.5 |

## 9. Decisions that are yours

1. **Prefix.** `DELEG-xx` for development delegation (assumed throughout), or fold these into HARNESS rows. I recommend `DELEG-xx`: it keeps development tooling out of the runtime roadmap, as the overseer review also does.
2. **Pilot class and order.** Confirm DELEG-01 and DELEG-11 now, then DELEG-03 and DELEG-06 on oracle-backed refactors or extractions. Name another class if you prefer.
3. **Meaning of 20/80.** Fix R, the interval rule and the thresholds in section 8 before any run.
4. **Stray records.** May DELEG-01 import the Claude scratchpad ledger, the scratchpad reader logs and the overseer ledger into the repository ledger, marked as imported? The scratchpad lives outside the repository and may be cleaned up.
5. **Approvals.** Two Codex launches in my records came back "Rejected" or "unacceptable risk" [M], which is the automatic review's wording; it also blocked the overseer review's critic export [R]. Do you want a standing, recorded authorization for redacted repository packets to DeepInfra within a stated budget, so lanes do not stall?
6. **Vault notes.** Twelve paper notes sit as drafts in `D:\Resource-Library`. Should they wait for your review of `04-extraction-table.md`?
7. **Rotate the Vast.ai key** on line 4 of `G:\vast\cloud_queue.log`. I did not copy it anywhere.
8. **Further reading.** Retrieve the primary Reflexion and Tree of Thoughts papers, and read Agentless, MAST and the scaling paper beyond the sections I fetched? Low priority.

## 10. Limits

n is small throughout (12 recorded review-finding dispositions, 9 delegate-drafted commits, 3 Claude resumes, 6 Codex post-result batches). The overseer review and the sprint share one evidence population. The recommended controller does not exist; every number about it is a hypothesis. Model-made labels (802 transcript events, 100 overseer episodes) are anchored to the text but not individually adjudicated. Applicability levels and the reading priority are judgements. The quote checks bound location only: the strict rate is a floor, the lenient rate a ceiling, and the support audit is a sample of 60. Outside sources were read through a fetch tool's extract of the primary page, not from the PDFs. About 107 Gemini claims and the research-side batch scripts were not examined. A direct-work baseline cannot be recovered from history, which is why section 8 proposes one. Codex idle time includes your absences.

## Appendix A. Outside claims introduced by the overseer review

All fetched 2026-10-29 through the fetch tool, which summarises the primary page. Tags follow `08-claim-register.md`. None of the designs above depends on a claim that is not *verified*.

| # | Claim as the overseer review uses it | Source and version | Tag | Note |
|---|---|---|---|---|
| 1 | Agentless uses a localisation, repair and validation pipeline without letting the model choose actions or use complex tools; 32.00% (96 fixes) on SWE-bench Lite at $0.70 | arXiv 2407.01489 v2, revised 2024-10-29 (abstract) | verified | Benchmark figures describe 2024 open-source systems; they say nothing about this repository |
| 2 | A reproduction test is kept only if it reproduces the issue on the original repository; regression tests are existing passing tests filtered by the model | Same paper, HTML v2, sections 3.3.1, 3.3.2, 5.1.3 | verified (paraphrase) | "Should fail on the original code" is a fair functional reading, not the paper's words; there is no section 3.4 |
| 3 | 14 failure modes in three categories (system design, inter-agent misalignment, task verification); 1,600+ annotated traces over 7 frameworks; kappa 0.88 | arXiv 2503.13657 v3, revised 2025-10-26 (abstract) | verified | |
| 4 | Failure modes also occur in successful runs ("Successful runs are not failure-free"); verification failures appear often in successful runs | Same paper, appendix J.1 | verified | The overseer review's "apparently successful runs can retain process failures" holds |
| 5 | Interventions gave modest gains (+9.4% from role specification on ChatDev; up to +15.6% from a high-level verification step on ProgramDev) | Same paper, sections 4 and 5.3 | verified | Fetch-tool extract; figures not re-read in the PDF |
| 6 | 180 configurations, four benchmarks, five architectures; best gain +80.8% (centralised, finance), worst loss about -70% (independent, planning) | arXiv 2512.08296 **v2** | verified for v2 | **Version drift:** v3 (revised 2026-04-08) reports 260 configurations, six benchmarks, three model families, a predictive model with cross-validated R2 of 0.373, and no quantified error amplification in the abstract. Cite the version with any number |
| 7 | A subagent brief needs an objective, an output format, guidance on tools and sources, and clear task boundaries; vague briefs caused duplicated work; subagents store outputs externally and pass references; execution resumes from checkpoints | `https://www.anthropic.com/engineering/multi-agent-research-system` | verified | Vendor account; the overseer review links the `/research/` path, which I did not test |
| 8 | Agents use about 4 times and multi-agent systems about 15 times the tokens of chat; the multi-agent system beat single-agent Opus 4 by 90.2% on an internal evaluation; token usage alone explained 80% of the variance on BrowseComp | Same page | verified as the vendor's statement | Internal evaluation on models since superseded; not an independent trial |
| 9 | Multi-agent systems fit poorly where agents share context or have many dependencies; "most coding tasks involve fewer truly parallelizable tasks than research" | Same page | verified | Not cited by the overseer review; bears directly on lane design |
| 10 | DeepInfra prices: MiMo-V2.6-Pro $0.43 and $0.87, GLM-5.3-Flash $0.15 and $0.50 per million input and output tokens | `https://api.deepinfra.com/v1/openai/models`, 2026-10-28 | verified | Same figures in both reviews |
| 11 | An automatic approval review blocked an export of the private draft and evidence excerpts | `data/approval_review.json` in the overseer folder | reported [R] | Not reproducible; consistent with two rejected Codex launches in my records [M] |

## Appendix B. Where things are

| File | What it is |
|---|---|
| `00-summary.md` | Revision-2 summary |
| `01-metrics-definition.md` to `07-open-questions-experiments.md` | The six deliverables: metrics, baseline, reading list and extraction table, deployment patterns, design proposals, experiments |
| `08-claim-register.md` | Gemini's outside claims tagged; appendix A above covers the overseer review's |
| `09-response-to-second-pass.md` | Point-by-point answer to the second-pass review |
| `10-final-report.md` | This file |
| `data/`, `scripts/` | Re-runnable inputs and code (`STATE.md` lists the order). New here: `scripts/hyphen_recheck.py`, `data/hyphen_recheck.*` |
| `../2026-10-28-agent-workflow-second-pass/`, `../2026-10-28-deepinfra-overseer-workflow/` | The two other analyses, read-only |
| `D:\Resource-Library` | Twelve draft paper notes, the application record and index rows, uncommitted |

## Appendix C. How this synthesis was checked

Section 3 lists the checks against the overseer review: 12 transcript anchors, 5 repository line anchors, the INDEX-05 delegation table, 2 commits, prices, ledgers and 9 paper ranks, all against the files. Appendix A comes from pages fetched on 2026-10-29. The quote-location follow-up is `scripts/hyphen_recheck.py`. The critic pass and the number check are recorded below.

**Number check.** `scripts/check_final_numbers.py` looked up every meaningful number in this report (174 checked) in the sprint, second-pass and overseer files. All were found except five that are derived or fetched, which the script lists with reasons (`data/final_number_check.json`).

**Independent critic.** Two models that did not draft the report read it together with the reports and data it relies on (`scripts/build_final_critic.py`). MiMo-V2.6-Pro returned 9 findings and Qwen3.5-397B 4; a third critic, GLM-5.3-Flash, timed out after 900 seconds and was not retried. All 13 findings quote text that exists at the cited lines (`scripts/collect_final_critic.py`, `data/final_critic_findings.csv`; MiMo's output had one misplaced bracket, repaired). I dispositioned each one in `data/final_critic_adjudication.csv` (D = defect, fixed; P = partly valid, wording or traceability fixed; X = not a defect, explained): 5 D, 4 P, 4 X. The defects were a per-class 20/80 rule that twelve tasks over three classes could not support (E2' is now staged), a mean and median mismatch in the decision rule, a recheck data file that divided by the wrong denominator, a post-result interval described as ending at a commit when it also ends at a launch, and loose arithmetic (84 and 76 minutes).

**Spend for this synthesis.** Three DeepInfra calls, about $0.16: the MiMo critic $0.0679, the Qwen critic $0.0746, and the timed-out GLM call, charged at its reserve of $0.0221. `claude-ledger.json` now shows $4.47 committed of $8. The outside-source fetches cost no API money.
