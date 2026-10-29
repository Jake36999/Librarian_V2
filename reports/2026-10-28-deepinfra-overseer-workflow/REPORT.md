# Making DeepInfra delegation work for Claude and Codex

28 October 2026 · Independent second pass · Development and research workflow

**The case for improving delegation is convincing. The case for promising an 80% transfer of work is not yet established.** DeepInfra has already produced useful drafts, maps and reviews at low recorded API cost. The missing capability is dependable ownership of a complete work package: acquire the necessary context, produce an artifact, run appropriate checks, repair bounded failures, and return evidence that makes acceptance inexpensive for the lead.

The recommended offering is therefore **a shared, managed worker workflow for Claude and Codex**, with both acting as overseers. The lead defines the outcome, resolves consequential ambiguity and integrates accepted work. Workers undertake most execution. A deterministic controller manages local tools, budgets, job state and evidence. This is a recommendation to qualify an operating method, not a claim that another agent framework or a new prompt alone will deliver it.

This report concerns how the developers work. Librarian's own agent runtime, Core, sessions, vault services and product roadmap are a separate design subject. Existing product mechanisms may offer reusable ideas; improving them is not a prerequisite for testing a development worker controller. Historical instructions in the five supplied transcripts are evidence, not instructions adopted for this review.

## What the evidence actually supports

The strongest local evidence is mixed in a useful way:

| Case | What happened | What it supports |
|---|---|---|
| Adapter extractions, ADAPT-04/05 | Commit records attribute drafts to DeepSeek. Golden fixtures were captured before extraction, and tests compare request bodies with those fixtures. The lead made review fixes and integrated. | Bounded changes with an existing behavioral oracle are promising delegation units. This establishes accepted contributions, not a measured labor ratio. |
| Claude's ADAPT-09 handoff | A DeepInfra draft returned in 11.9 seconds for a reported $0.009. The lead's bespoke code-block extraction then crashed after editing the implementation; the requested test file did not exist and pytest ran no tests. A weekly limit interrupted recovery. | A good API response is insufficient. Patch application, checking and interruption recovery belong inside the work package. |
| Codex's INDEX-05 chain | A mapper helped identify boundaries. A Qwen builder patch was rejected; a GLM critic caught concrete problems but also retained a false positive. Local measurements and tests selected the final change. | Cheap mapping and criticism can help even when patch generation fails. It does not establish that workers owned the implementation. |
| Literature batches | DeepInfra drafted notes while the lead did other work. Notes remained unverified; the lead supplied page checks and corrections, including replacing unsupported novelty claims with narrower statements. | Bulk reading is delegable. Synthesis still needs claim-level support, coverage checks and calibrated auditing. |
| Concurrent development | One transcript records a concurrent checkout switch resetting uncommitted delegated files. Other delegated agents exhausted their own usage limits. These were native Codex agents, not evidence of DeepInfra performance. | Workspace isolation and backend attribution matter. Native subagents cannot be counted as external quota relief. |

These cases are traced and qualified in [EVIDENCE.md](D:/Librarian_V2/reports/2026-10-28-deepinfra-overseer-workflow/EVIDENCE.md). The successful adapter cases also have source tests and commit provenance; the ADAPT-09 failure includes pasted tool output. Retrospective statements about physics errors and time lost are treated as reports, not independent measurements.

The current `scripts/delegate_deepinfra.py` explicitly implements **one bounded model call returning an untrusted proposal**. It exports selected text with hashes and records a receipt; it does not expose a local read–edit–test–repair loop to the remote model. That makes it a useful audited primitive, but leaves execution and recovery with the caller. DeepInfra inference and the local execution environment are different capabilities: the former needs a controller to use the latter.

Claude's sprint baseline is being revised concurrently. This report preserves a snapshot of revision 2 rather than relying on the superseded headline figures. That snapshot records approximately **$1.15 across 57 development calls**, spread across three recording mechanisms. It also records nine delegate-drafted commits, and **four of nine completed real Codex-runner calls ending at the output cap**. These are small, heterogeneous historical populations with rate-table cost estimates. They justify fixing the interface and instrumentation; they do not establish comparative model rankings or savings. The repaired baseline explicitly withdraws the earlier inference that result checking cost six to eight times the delegate's output.

## The bottleneck is the handoff of responsibility

A delegation can appear substantial because the worker emits a large answer while leaving most consequential steps with the lead. In the transcripts the lead repeatedly gathers source material, constructs prompts or batch scripts, applies code from prose, runs tests, explains failures, edits repairs and reconstructs interrupted jobs. Those steps accumulate even when the remote generation is cheap.

This is an inference from the division of work in the cases, not a causal estimate of wasted quota. Some lead work is necessary judgment, and some tasks were poor candidates for immediate handoff. The useful distinction is between **decisions that require the overseer** and **execution the tooling should let a worker finish**.

| Responsibility | Intended owner | Why |
|---|---|---|
| Objective, priority, invariants, risk, final acceptance | Claude/Codex overseer | These establish what the project needs and which tradeoffs are permitted. |
| Search, context acquisition within scope, drafting, implementation, tests, bounded repairs | DeepInfra worker workflow | These account for much repeatable execution and should not require a fresh lead turn for every step. |
| Tool execution, workspace limits, receipts, budgets, retries, durable state | Deterministic controller | These need enforceable rules and observable outcomes. |
| Independent challenge of uncertain claims or patches | A separate critic, with evidence | A recommendation can identify defects; agreement alone cannot authorize acceptance. |
| Merge and changes to acceptance criteria | Overseer | A worker may propose a better criterion but cannot silently redefine success. |

A worker workflow need not be a fully autonomous agent. For predictable tasks, a fixed sequence of localization, patching, test execution and bounded repair can be the stronger baseline. **Agentless** demonstrates that a structured software-repair pipeline can be competitive without a general interactive agent. Its reproduction-test filtering is especially relevant: a purported reproducer should fail on the original code. Its benchmark results do not establish expected performance on this repository. [Agentless, §§3.1–3.3](https://arxiv.org/html/2407.01489v2).

## A better workflow contract

The existing unified implementation plan already requires objectives, permitted files, invariants, test commands, acceptance criteria, ownership and budgets. The improvement is to make those requirements executable and carry them through completion. The contract should describe four boundaries, without committing yet to a particular JSON schema or framework.

**1. Admission.** Identify the task, input revision, allowed effects, protected constraints, environment and resource limits. Define what evidence would establish success before starting, and assess whether the available checks cover that behavior. Preserve relevant failing behavior or reference outputs before editing. A generic green suite is insufficient admission evidence. A task without a defensible acceptance method can still be delegated for exploration or test development, but its result must be labeled exploratory rather than accepted implementation.

**2. Worker ownership.** Give the worker bounded ways to find additional relevant context and to operate on an isolated artifact. It should run the approved checks and attempt limited repairs, rather than returning an untested draft whenever execution becomes necessary. Repository search, source reading and local commands are capabilities supplied by the controller, not inherent powers of a hosted model. Keep optional retrieval within a budget so a small initial packet does not become unlimited exploration.

**3. Evidence-bearing completion.** Return an artifact reference, base revision, exact changes, checks actually executed, results, unresolved findings, cost and an explicit proposed disposition. Logs remain available by reference. The lead receives a concise account of what changed and what still needs judgment. The controller, rather than the worker's prose, records command outcomes and artifact identities.

**4. Escalation and resumption.** Escalate consequential ambiguity, required scope changes, exhausted resources or repeated failures. Preserve enough state to continue without repeating completed paid work. A partial answer, a truncated response, an unknown network outcome and a verified artifact are distinct states. Resume from the actual artifact and environment, not just a conversational summary.

For code, separate three predicates: **the artifact applies and runs; it satisfies the task's behavior; it integrates correctly with the project**. For research, separate source identity, quotation presence, claim support and coverage. None can be replaced by a worker saying “verified.” These are the main formalism gaps exposed by the record.

## Tooling needed, in priority order

**A. Complete execution in a bounded workspace.** Start with one task class whose checks already exist. The worker needs a pinned interpreter and dependencies, repository context, an isolated worktree or equivalent staging area, bounded command execution and a repair loop. Record the actual execution environment, such as interpreter/toolchain versions and dependency identity, and stop for requalification on a material mismatch. The local executor supplies this environment; the remote inference host is not assumed to run repository commands. Enforce permitted file, command and network access in the controller. Protect and fingerprint acceptance fixtures so changes invalidate completion; worker-authored tests can add evidence without replacing the original contract. Proposed acceptance changes require a recorded overseer decision, and frequent requests count against the task class's suitability. The ADAPT-09 integration failure and the rejected INDEX-05 patch are direct reasons to move beyond extracting code blocks from a prose answer.

**B. Make verification discriminate.** Pre-change goldens are a strong local example. Bug fixes need a reproducer plus regression checks; numerical work needs units, reference cases and independently derived constraints; literature needs semantic adjudication and checks for omitted counterevidence. Exercise gates with known-good and deliberately bad artifacts. Record both false acceptance and false rejection. Passing a syntax check, an AST rule or an entire existing suite does not prove every intended property.

**C. Make paid jobs recoverable and attributable.** Record launch, actual provider completion, artifact readiness and acceptance separately. Enforce per-task and total reservation ceilings plus attempt and repair limits before dispatch. Retain reservations for uncertain paid outcomes; reconcile before relaunch. Where no authoritative provider lookup is available, retain the conservative charge and surface the uncertainty rather than assuming a timeout was free. Disable hidden transport retries or explicitly budget and identify every attempt. Idempotency can prevent duplicate local application; it cannot guarantee that an API request with an unknown outcome was never billed. Keep one shared ledger across the supported development entry points and preserve exact backend, model, task and artifact identities. Several of these safeguards already exist in the current runner; extend and test them rather than rebuilding them under new names.

**D. Reduce the lead's information burden.** Provide compact completion and exception records with drill-down references. Batch mechanical checks and source identity checks outside the lead conversation. Use durable progress records so status does not require repeated reasoning turns. Completion notifications are useful where the host supports them; a shared on-disk record must still allow recovery after the host or conversation stops. This report does not assume that either desktop assistant can always be awakened by an external process.

**E. Qualify routing and concurrency.** Route by demonstrated task performance, including repair and verification cost. Split independent work by files or artifacts and serialize coupled changes. Keep the same contract for Claude and Codex, with thin host-specific launch adapters. Read-only counterexample searches can run in parallel without permitting several workers to edit the same checkout. Improve one reliable path before adding swarms, debates or hierarchical model routing.

The order matters. More parallel calls before A–C work can generate a larger review queue and more ambiguous failures. The MAST study identifies system design, inter-agent alignment and verification as distinct failure categories; its outcome analysis also warns that apparently successful runs can retain process failures. It supplies a useful diagnostic vocabulary, not a forecast of local defect rates. [Why Do Multi-Agent LLM Systems Fail?](https://arxiv.org/html/2503.13657v3).

## What to retain and qualify from Gemini

Retain the overseer role, isolated workspaces, dynamic task briefs, bounded background batches, evidence artifacts, operational telemetry, durable handoffs and recorded dead ends. These map well to observed problems. Gemini's later discussion of Librarian's runtime can inspire these development capabilities, but does not make changes to Librarian's product architecture part of this proposal.

Qualify the following claims and prescriptions:

- **“Hoarded 90% of the labor.”** The transcripts do not measure that percentage. They show repeated lead execution; that is enough to motivate a controlled comparison.
- **“Never read PDFs unless two workers disagree.”** Agreement can preserve a shared omission or misreading. Combine independent challenge with sampling of apparently passing results, targeted lead review of consequential claims, and coverage audits. Begin with substantial independent adjudication during qualification; reduce routine lead review only as evidence permits. Consequential claims include those determining a scientific verdict or touching protected behavior, interfaces, authority or data integrity. Sampling effort should respond to observed defects and consequences, not a fixed percentage chosen now; a small passing sample cannot establish the absence of rare serious errors.
- **“A ten-line specification is sufficient.”** Brevity is useful only if the worker can resolve references, obtain missing context and test the result. An underspecified brief shifts cost into failure and rescue.
- **“Never debug or poll in the lead.”** Remove routine execution and polling from the lead's responsibilities, while retaining an explicit escalation path. Exceptional diagnosis may still require the lead.
- **Fixed pulse lengths, model lists, invariant thresholds and culling fractions.** These are proposed defaults, not measured operating optima. Qualify exact routes and task classes with current prices and outcomes.
- **A generic formal or numerical checker settles the research claim.** A checker proves properties of the supplied representation. Incorrect equations, sign conventions, hypotheses or observables can still satisfy it. The transcript's reported research corrections illustrate why semantic correspondence needs a separate check.
- **A rented GPU cluster is necessarily cheaper.** The relevant denominator is accepted work, including idle rental, setup, failures and supervision. Many local execution steps need ordinary CPU resources. Defer compute migration until measured API workloads make a credible comparison possible.

The OpenAI research narrative in Gemini is background inspiration, not evidence for a particular local controller implementation or economic outcome. The earlier [claim review](D:/Librarian_V2/reports/2026-10-28-agent-workflow-second-pass/CLAIMS.md) separates the supported public account from inferred orchestration details. No claimed swarm size or discovery result is needed to justify the bounded workflow recommended here.

## What the papers add to the case

The original fifty-paper collection remains useful, but the second pass found material omissions in costs, negative results, verification and transfer limits. Selected-quote accuracy was stronger than synthesis completeness: all 134 originally verified cards passed exact-page normalized quotation checks, yet important qualifications were missing. That does not mean every claim in every card was semantically correct, or that every useful passage has now been found. The detailed [literature supplement](D:/Librarian_V2/reports/2026-10-28-agent-workflow-second-pass/LITERATURE.md) and its page-level evidence remain part of this review.

| Evidence | Implication for this offering | Transfer limit |
|---|---|---|
| EToT, original rank 7, PDF p8: repeated Judge calls dominate overhead; one parallel simulation case falls from 55 to 26 seconds. | Count verification separately; measure parallel speedup on fixed work. | Robotics planning does not predict software throughput. |
| HDDLGym, rank 11, §§4–5: completion is checked against task effects. | Define acceptance over an artifact's resulting state, not a “done” message. | Its modeled world is more explicit and controlled than a repository or literature corpus. |
| Knowledge-driven mobile reasoning, rank 3, §IV.C: context amount and composition interact; more context is not uniformly better. | Retrieve relevant context and compare packet policies by accepted outcomes. | No universal packet size or prompt-cache saving follows. |
| Policy compiler, rank 14, §§4.6/4.14: matched rules explain much of the stationary gain; refreshing targets confounds adaptation claims. | Compare a fixed controller with adaptive routing before crediting an LLM coordinator. | These are simulated policies, not a trial of developer agents. |
| Rationale faithfulness, rank 42, §§4.2/4.5.4: substring grounding differs from empirical faithfulness. | A quote matcher should validate anchors; a separate check must judge whether the claim follows. | Evidence-removal probes are diagnostic, not a complete proof of causation. |
| ReflectiChain, rank 1, pp18/20/22: additional token cost, heuristic drift estimates and poor CodeSim transfer in a very small test. | Keep drift scores advisory; prefer behavioral constraints and measured verification costs. | Three episodes per benchmark/strategy do not settle general coding performance. |

Three more direct sources sharpen the workflow choice. **Agentless** supports testing a simple pipeline before a general agent. **Towards a Science of Scaling Agent Systems** compares 180 configurations across four benchmarks: task structure and coordination matter, and sequential tasks can deteriorate under multi-agent arrangements. This supports bounded parallelism rather than an assumption that more agents improve all work; its environments and fixed configurations limit transfer. [Scaling study](https://arxiv.org/html/2512.08296v2).

Anthropic's engineering account independently emphasizes clear delegation briefs, artifact references and durable execution. It is a vendor account of its research system, not an independent trial of these DeepInfra routes. Its lessons support the proposed boundaries without establishing our expected savings. [Building a multi-agent research system](https://www.anthropic.com/research/multi-agent-research-system).

Taken together, the evidence favors **explicit task effects, bounded execution, measured checking costs and durable state**. It does not justify importing a paper's trust score, convergence bound or agent count as a production guarantee. [EVIDENCE.md](D:/Librarian_V2/reports/2026-10-28-deepinfra-overseer-workflow/EVIDENCE.md) links the local paper locations and formalism gaps to the proposed capabilities.

## Giving the 20/80 target a defensible meaning

Use 20/80 as an aspiration for suitable work, not a universal task requirement or a ratio of generated tokens. A worker can inflate its token share without reducing the lead's effort. An 80% share of planned work owned by workers and an 80% reduction in lead effort are different claims: the first needs effort-weighted units defined in advance, and the second needs a comparable direct-work baseline. Report both rather than treating one as proof of the other.

For an illustrative accounting model of the second claim, let a comparable task require lead effort **D** when performed directly. Let **d** be the fraction of D removed by transferring execution to workers, and **h** be added briefing, review, integration and expected rescue effort, expressed as a fraction of D. Then:

**Remaining lead effort / D = (1 − d) + h.**

Moving 80% of execution while adding 10% overhead leaves 30% with the lead. At the same transfer with 25% overhead, 45% remains. Moving 90% with 10% overhead reaches 20%. These are accounting examples, not measured predictions or best-case estimates. Overhead can depend on the delegated share, task coupling, worker and controller; the expression assumes neither constant overhead nor independence. It explains why the contract must transfer execution and reduce acceptance cost together. A quota objective should also measure lead token usage by category; attention time, tokens, subscription limits and dollars are different quantities.

The primary outcome should be **accepted work at equal or better quality per unit of scarce lead capacity**. Measure active lead attention, lead requests and fresh/cache/output tokens, accepted worker-owned units defined before execution, manual rescue, total API cost, elapsed completion time, and escaped defects or unsupported claims. Preserve failed and abandoned tasks in the denominator. Historical post-result token windows and line-retention statistics cannot substitute for a comparable direct-work baseline.

## What would justify adopting it

First establish one complete path on a few representative tasks. Then run a modest, balanced comparison across bounded refactors, reproducible bug fixes and evidence extraction: direct lead execution, today's one-shot delegation, and the managed worker workflow. Use comparable tasks or isolated paired runs; freeze input revisions, acceptance criteria and resource limits. Independent scoring should hide which workflow produced an artifact where practical. Do not let an earlier solution leak into the later arm.

A dozen varied tasks can expose basic feasibility and failure modes, but cannot establish a precise universal savings rate. Repeat the comparison if the initial result is promising. Predeclare quality requirements and what counts as manual rescue, including criterion changes and uncertain-charge reconciliation. For research, include known omissions and misleading but correctly quoted claims; for code, include tempting test weakening and environment failures. Test interruption recovery and show that both Claude and Codex can operate the same job contract. Measure differences in briefing, escalation and integration for the two leads rather than assuming their adapters are costless.

Proceed when quality holds, the lead spends materially less effort per accepted task, costs stay bounded and recoveries are observable. Narrow or reject the method where workers repeatedly require the lead to redo the solution. Treat an 80% reduction in lead effort as an outcome to demonstrate on qualified task classes; use a lower, credible gain if that is what the evidence shows.

**Recommendation:** invest first in completing and qualifying the worker execution boundary around the existing audited runner. This has a direct connection to observed failure modes, reuses successful local practices and creates a testable route toward the desired overseer role. Model selection, larger pools and rented compute should follow evidence from that boundary.

## Review method and deliverables

The five complete transcripts were supplied to bounded DeepInfra reading calls using numbered, secret-redacted copies. Worker extractions were mechanically checked against nearby source lines. Selected cases were then independently adjudicated against transcript context, local source, tests and commit records. Quote matches were not treated as proof of the workers' interpretations. A separate DeepInfra critic challenged a newly authored abstract workflow contract; it did not receive or fact-check the private report and evidence. Dispositions and limitations are recorded in [EVIDENCE.md](D:/Librarian_V2/reports/2026-10-28-deepinfra-overseer-workflow/EVIDENCE.md).

This is an evidence review and a workflow recommendation. It does not implement or benchmark the proposed execution controller. The $5 authorization funds this review's model calls; it is not a cost estimate for the proposed pilot. **Fourteen calls completed for an estimated $0.3573**, reconciled to the local ledger; no paid call remains pending or unknown. Actual calls, prices, failures and charges are recorded in [data/delegation_summary.json](D:/Librarian_V2/reports/2026-10-28-deepinfra-overseer-workflow/data/delegation_summary.json) and [data/deepinfra-ledger.json](D:/Librarian_V2/reports/2026-10-28-deepinfra-overseer-workflow/data/deepinfra-ledger.json).
