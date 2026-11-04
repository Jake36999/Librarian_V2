# 3. Research objectives: memory tooling and evolving knowledge systems

3 November 2026. Proposed next research program, not a completed tooling survey. Tool families below are investigation targets; capabilities, versions, maintenance, licensing and integration costs must be verified before selection.

## Aim and common decision rule

Determine which mechanisms improve Librarian's later-task success, adaptation to change and preservation of useful context at acceptable total cost. Require a demonstrated gap in the current system before recommending a new dependency. A negative result that favors the existing implementation is useful.

Every objective should produce a short evidence dossier: primary sources and exact versions; supported capabilities versus assumptions; fit with existing interfaces; a minimal experiment; measured outcomes and failure cases; and an adopt, adapt, defer or reject recommendation. Code inspection and benchmark results must remain distinguishable from product claims.

## R1 — Durable memory and provenance infrastructure

**Question:** Can current storage support exact-version reuse, temporal queries and withdrawal without a separate authoritative memory service?

**Explore:** existing Session/evidence/SQLite projections; event-sourced and temporal stores; provenance schemas; source-addressed artifact systems; temporal graph memory patterns described by [Zep](https://arxiv.org/html/2501.13956v1) and [PROV-DM](https://www.w3.org/TR/prov-dm/). A named paper is a research starting point, not an endorsement of its current implementation.

**Experiment:** compare the local baseline with at most one alternative adapter using the same episode, source revision, restart, revoked access and historical-query fixtures. Include reconstruction after index loss and withdrawal across lexical/vector/graph derivatives.

**Measures/deliverable:** exact-version resolution, current/historical correctness, leakage, rebuild time, storage and integration burden; deliver a storage/interface decision record. Advance an alternative only if it fixes a demonstrated requirement the local baseline cannot meet economically.

## R2 — Complete context assembly and worker continuity

**Question:** Which selection, compaction and handoff mechanisms preserve decision-critical information through long runs and multiagent work?

**Explore:** provider-aware request accounting, structured working-state projections, reference-based expansion, durable result stores, checkpoint/resume systems and typed worker-result envelopes. Examine context engineering guidance alongside failure evidence from [MAST](https://arxiv.org/html/2503.13657v3); distinguish communication defects from reasoning defects.

**Experiment:** repeated compaction over 50/200-round synthetic histories; late caveats; worker exit; parent requirement changes; duplicate results; restart between dispatch and merge. Compare current assembly with bounded selection and structured handoffs, holding current essential state constant.

**Measures/deliverable:** serialized-request bounds, essential constraint preservation and use, evidence reopening, stale closure, duplicate acceptance, aggregate cost and latency; deliver a request/handoff contract and regression fixtures. This precedes claims that richer memory improves long-horizon work.

## R3 — Learning reusable lessons from application episodes

**Question:** Do qualified lessons improve future work more than retrieving original episodes or adding lifecycle tiers?

**Explore:** incremental playbooks, episodic/semantic/procedural memory, bounded curation and failure-conditioned lessons. Starting sources: [ACE](https://arxiv.org/html/2510.04618v1), [ReasoningBank](https://arxiv.org/html/2509.25140v1), [Dynamic Cheatsheet](https://arxiv.org/html/2504.07952v1). Inspect implementation and feedback-label assumptions before selecting a prototype.

**Experiment:** run benchmark arms A/B/C/D: no optional prior experience; episode retrieval; episodes plus tiers; episodes plus qualified versioned lessons. Include a previously useful workaround that becomes wrong and a failed method that becomes viable after a fix.

**Measures/deliverable:** held-out transfer, tasks helped/harmed, applicability false acceptance/rejection, correction uptake and full curation costs; deliver a lesson schema, qualification rubric and promotion/revision policy. Continue only if gains survive unseen variants and account for extra model work.

## R4 — Selective staleness and dependency revalidation

**Question:** Can explicit support tracking reduce unnecessary rework without silently retaining invalid conclusions?

**Explore:** truth-maintenance systems, build-system invalidation, data lineage, temporal graphs and dependency indexes. Compare declared/mechanically observed dependencies with inferred edges; evaluate relational storage before adding a graph service.

**Experiment:** compare conservative epoch invalidation against dependency-based rechecks for a changed premise, two alternative support sets, conjunctive prerequisites, a missing dependency and a goal-only pivot. Include compatible revisions that resemble contradictions.

**Measures/deliverable:** affected items missed, unaffected items blocked, preserved alternative support, explanation correctness and recheck cost; deliver dependency semantics and a conservative fallback policy. Treat this as a HARNESS-09 research spike, not evidence that the deferred feature is approved or complete.

## R5 — Replication recipes and procedural memory

**Question:** What additional contract turns an existing workflow into a reusable, requalifiable procedure?

**Explore:** current workflow and claim-check tools first; artifact manifests, environment capture, reproducible workflow engines and parameterized skill libraries. [Agent Workflow Memory](https://arxiv.org/html/2409.07429v1) motivates procedure abstraction, but its web-task evidence does not establish research reproducibility.

**Experiment:** derive a recipe from completed episodes, test unseen inputs, then change one environment prerequisite. Test interrupted runs, retry reconciliation, dependency cycles and partial artifacts. Compare plain episode guidance, descriptive recipes and eligible executable workflows.

**Measures/deliverable:** verified replication, transfer failures, stale qualification, recovery correctness, setup and execution cost; deliver the recipe/receipt schema and extension-versus-new-engine decision. Do not widen execution scope to accommodate a candidate tool.

## R6 — Agent probes and human review systems

**Question:** Which assessments detect meaningful knowledge decay or applicability change, and which scheduling policy is worthwhile?

**Explore:** existing understanding/review features, versioned question banks, spaced-repetition systems, regression probes and event-triggered assessment. Keep human-learning evidence and agent-performance evidence separate.

**Experiment:** compare fixed checkpoint, relevant-change-triggered and failure-triggered agent probes. Score closed-context recall, retrieval-assisted answers and task execution separately. Revise a probe's source and check retirement of the old answer. A human delayed-learning study would be a separate protocol.

**Measures/deliverable:** consequential failures detected/prevented, false alarms, answer leakage and probe overhead; deliver distinct human/agent schemas and a scheduling decision. Agent card accuracy alone cannot justify deployment or a claim of acquired skill.

## R7 — Evaluation harness and real-project task streams

**Question:** Can a reproducible harness distinguish memory benefit from added compute, leaked answers or easier tasks?

**Explore:** adapters for [MemoryArena](https://arxiv.org/html/2602.16313v1), [MemoryAgentBench](https://arxiv.org/html/2507.05257v3), [LifelongAgentBench](https://arxiv.org/html/2505.11942v1) and [Evo-Memory](https://arxiv.org/html/2511.20857v1), plus versioned local research projects. Assess dataset terms, runnable dependencies, scoring fidelity and tool-policy compatibility before importing anything.

**Experiment:** turn the existing ten abstract seeds into deterministic adapter tests, then separately authored chronological task streams. Include goal changes, exploration without adoption, archived-project return and stale concurrent workers. Begin with A/B/C/D; add recipe and probe arms E/F only after the baseline is sound.

**Measures/deliverable:** a runnable adapter, frozen run manifests, hidden scoring, cloned treatment state, stream-level uncertainty and cost reports. Follow the existing [benchmark design](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/EVOLVING-KNOWLEDGE-BENCHMARK.md). Establish numeric quality/cost thresholds and pilot size before experiments, based on available budget; do not select them after seeing results.

## R8 — Retrieval utility, graph routing and resource policies

**Question:** When do graph navigation, richer ranking or adaptive memory budgets add value over scoped lexical/vector retrieval?

**Explore:** V1 community orientation and dependency digests; current V2 hybrid retrieval; graph-guided source expansion; deterministic versus learned replay/retention policies. [LIMBO](https://arxiv.org/html/2609.14138v1) and [TokenWorth](https://arxiv.org/html/2610.26453v1) are recent research starting points with benchmark-specific assumptions.

**Experiment:** compare lexical, hybrid and bounded graph-assisted retrieval on source discovery, multi-hop synthesis and changed-evidence tasks. Use equal total budgets and separately report matched-quality costs. Test empty scoped results, highly similar forbidden material and unavailable graph artifacts. Study learned scheduling only after collecting reliable utility telemetry.

**Measures/deliverable:** required-evidence coverage, downstream correctness, harmful context inclusion, fallback behavior, latency and total tokens; deliver a routing policy and justified decision on whether any new graph/vector infrastructure is needed.

## Research order and integration gates

| Stage | Objectives | Exit artifact |
|---|---|---|
| Establish baselines | R7 fixture/manifest design, R1 continuity requirements, R2 request/handoff contracts | Reproducible baseline and known failures |
| Test useful learning | R3 and R8 with simple deterministic policies | Episode/tier/lesson comparison and retrieval evidence |
| Test procedures and monitoring | R5, then R6 | Qualified recipes and probe cost/benefit results |
| Optimize change handling | R4; adaptive portion of R8 only if warranted | Selective revalidation or scheduling decision |

At each gate, require current access/scope preservation, no stale requirement closure, inspectable provenance, restart behavior and full cost accounting. These are integration checks, not a claim of universal safety from a finite test suite. Behavioral improvement must be measured separately.

For each external candidate, verify primary documentation and repository at a pinned version, deployment/local-offline requirements, exportability, license, maintenance, scope enforcement, deletion/withdrawal, telemetry and migration burden. Compare against an extension of existing V2 facilities. Prefer an adapter-sized prototype that can be removed if it does not help.

The final research output should be a ranked decision register: problem addressed, baseline, candidate, evidence strength, integration cost, benchmark result, unresolved risks and adopt/adapt/defer/reject rationale. No benchmark execution, service adoption or model training is implied by this research agenda.
