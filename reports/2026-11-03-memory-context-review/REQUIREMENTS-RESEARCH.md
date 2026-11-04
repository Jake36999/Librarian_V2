# Research pass: candidate memory and context requirements

3 November 2026. Research and proposed specification language only. No runtime implementation, benchmark execution, provider spending, canonical specification edits, or acceptance-gate changes.

## Result

The strongest addition is a **memory-use contract**: before a remembered item influences a new decision, establish its scope, origin, applicability, revision and supporting evidence. Memory quality should be judged by subsequent task outcomes and correction handling, as well as retrieval accuracy.

The [candidate design addendum](/D:/Librarian_V2/docs/proposals/memory-context-design-addendum.md) supplies 16 individually testable clauses. Eleven apply to existing context/retrieval/delegation boundaries; five apply only if reusable cross-session memory or richer graph features are adopted. They are proposals, not new mandatory work or evidence that a feature is implemented.

## Method and limits

This pass compared the current [harness specification](/D:/Librarian_V2/docs/long-horizon-harness-design.md) with the previous [implementation comparison](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/REVIEW.md), the product compatibility contract, selected local research passages, and ten external primary sources. Web discovery was followed by reading relevant original-paper sections; secondary summaries and forum claims were not used as evidence. Sources were selected for relevance and contrary findings, not to compile a comprehensive literature census or product leaderboard.

The research folder remains empty. Local evidence comes from the preserved extracts, with the PDF/extraction limitations already recorded in the first review. I reread LLM-S2KG's representation distinction, STAGE's original-text fallback and CoACL's uncertain-link treatment. I did not repeat the earlier corpus inventory, full code review or tests; the earlier 84 passing tests are historical evidence from the first review, not results of this research pass.

Below, source findings and Librarian requirements are deliberately separate. The papers motivate failure cases; they do not prove that the proposed requirements or any particular algorithm will improve Librarian. Version-pinned links document what was read. A preprint, benchmark result, vendor engineering article, and local system constraint have different evidential roles.

## Evidence and transfer

| ID / primary source | Passage examined and relevant finding | Limitation and resulting design direction |
|---|---|---|
| S1 — [LongMemEval, v2](https://arxiv.org/html/2410.10813v2), §§4–5 | Separates memory values, retrieval keys, queries and reading. Summary/fact-only values lose information in most tested settings; temporal retrieval and structured reading address different problems. | A conversational benchmark, not a task-execution guarantee. Keep resolvable original episodes; test indexing and answer use separately. |
| S2 — [MemoryAgentBench, v3](https://arxiv.org/html/2507.05257v3), §3 and Appendix K | Evaluates incremental acquisition, retrieval, learning, long-range understanding and selective forgetting. Its update task supplies an explicit chronological overwrite rule, which remains challenging. | Later-wins is a benchmark policy, not a universal truth rule. Make update authority explicit and test multi-hop effects of corrections. |
| S3 — [Memora, v1](https://arxiv.org/html/2604.20006v1), §§4.2,6 | Evaluates remembering, recommendations and reasoning with evolving memories. The error analysis distinguishes incomplete retrieval from continued use of invalid memories. | Constructed personalized conversations and model-based scoring limit transfer. Measure both missing current information and inclusion of obsolete information. |
| S4 — [MemoryArena, v1](https://arxiv.org/html/2602.16313v1), §§3–4 | Tests interdependent multi-session actions rather than recall alone. Performance decays with dependency depth; some precise-reuse tasks favor retrieval over heavier abstraction. | Benchmark environments and selected task/model combinations. Add chained real-work fixtures and preserve exact intermediate evidence where needed. |
| S5 — [MemDev-Bench, v1](https://arxiv.org/html/2610.27524v1), §§4.3–6 | Finds historical guidance can produce compatibility mismatches, misapplied transfer, scope expansion and persistence despite counter-evidence. Raw trajectories expose useful process details that compressed records can omit. | Recent preprint; experiments use one agent/model configuration and a SWE-bench Verified subset. Treat applicability and process preservation as hypotheses to test outside coding. |
| S6 — [Why Do Multi-Agent LLM Systems Fail? / MAST, v3](https://arxiv.org/html/2503.13657v3), §4 and Appendix A | Separates history loss, missing communication, ignored agent input, incorrect assumptions and verification failures. Similar visible failures can have different causes. | Observational taxonomy and partly automated annotation; not proof that typed messages eliminate failures. Require inspectable handoffs and independent merge checks. |
| S7 — [MINJA, v1](https://arxiv.org/html/2503.03704v1), §§1,3–4 | Demonstrates malicious memory records induced through ordinary query interaction in its evaluated agents. A model-authored stored response can carry attacker influence into later work. | Threat model and evaluated agents differ from Librarian; published attack rates are not product-risk estimates. Preserve input lineage through summaries and reuse; storage alone must not increase trust. |
| S8 — [RULER, v3 abstract](https://arxiv.org/abs/2404.06654v3) | Adds multi-needle, tracing and aggregation tasks beyond a single needle, demonstrating that advertised context length and useful context are distinct in tested models. | Abstract-level screening in this pass; synthetic tasks and older models. Require route-specific context evaluation, not any historical model's context threshold. |
| S9 — [Anthropic: Effective context engineering](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents), 29 September 2025, compaction/note-taking/subagent sections | Describes compaction, durable notes, isolated exploration and condensed handoffs; warns that aggressive compression can omit subtle details. | Vendor engineering guidance, not an independent controlled comparison. Test selection fidelity and retain rehydration paths; do not import a fixed summary size or file count. |
| S10 — [Zep, v1](https://arxiv.org/html/2501.13956v1), §§2.1–2.2.3 | Describes source episodes, semantic records and separate system-time/validity-time semantics. Some provenance connections are described but not directly evaluated in the paper. | Vendor-authored architecture; contradiction resolution uses an LLM. Borrow explicit temporal meanings without copying autonomous invalidation or requiring its service. |

Local corroboration: [LLM-S2KG extract](/D:/Librarian_V2/reports/2026-10-29-long-horizon-harness-research/data/paper_text/remaining_02.txt), pp.10–12,24–25; [CoACL extract](/D:/Librarian_V2/reports/2026-10-29-long-horizon-harness-research/data/paper_text/remaining_04.txt), p.19 Appendix A.3; [STAGE extract](/D:/Librarian_V2/reports/2026-10-29-long-horizon-harness-research/data/paper_text/remaining_13.txt), p.6. They support provenance-bearing graph retrieval, explicit unresolved links and retaining original text. They do not establish graph-derived truth, reliable causal inference, or a universal graph-token selector.

## What changes relative to the existing design

The current specification already requires bounded assembled input (§6), provenance and stale checks (§4), safe reduction (§5), untrusted worker/document data (§7), cost accounting (§6) and multi-dimensional evaluation (§9). Those are existing commitments. Calling them new would overstate this research's contribution.

| Existing boundary | Missing precision | Proposed clauses |
|---|---|---|
| §6 bounded input | Applies to final dispatched input and protocol continuation, not just the projection object | MC-01, MC-02 |
| §4 resolvable evidence | Explicitly survives worker exit/restart where continuity is promised; changed/unavailable versions remain visible | MC-03 |
| §4 correction/freshness | Reusable procedure applicability and different meanings of time | MC-04, MC-05, conditional |
| §§3,7 authority/trust | Retrieved memory, transformed summaries and child-private context obey current scope and preserve origins | MC-06, MC-07 |
| §§3,5 delegation/reduction | Minimum decision-relevant handoff, input snapshot and idempotent parent merge | MC-08, MC-09 |
| §6 cost accounting | Atomic reservations across concurrent workers and uncertain completion | MC-10 |
| §§7,9 coverage and evaluation | Partial lookup is distinguishable from absence; memory is tested in subsequent decisions, including regressions | MC-11, MC-12 |
| §§4,8 records/privacy | Consolidation semantics and withdrawal across derivatives if reusable memory is adopted | MC-13, MC-14, conditional |
| §11 graph-memory change control | Graph-edge meaning, snapshot scope and safe fallback if graph retrieval expands | MC-15, conditional |
| §§6,8 operating bounds | Memory storage/retrieval work itself has caps and explicit exhaustion outcomes | MC-16 |

“Conditional” means that adopting a feature activates its contract. It does not authorize implementing that feature or make it a HARNESS-01–07 acceptance obligation retroactively.

## Prioritized recommendation

First specify MC-01/02/03 and MC-08/09: the request boundary, evidence continuity and worker merge semantics. These directly address the current implementation gaps in the earlier review. Pair them with MC-10/12 so benefits and total costs can be evaluated.

For reusable cross-session memory, settle MC-04/05/06/07/13/14 **before** indexing arbitrary history for automatic reuse. Existing immutable Session history can remain intact while derived current-state retrieval suppresses superseded material. Safe memory use does not require a new authoritative memory store.

Make MC-11/16 part of all retrieval work. Evaluate MC-15 only when graph retrieval is proposed; fine-grained dependency invalidation remains HARNESS-09. No source establishes that a graph service, extra agent role, always-on reflection or trained memory policy should be a default requirement.

## Evaluation additions justified by this pass

1. **Applicability reversal:** a remembered workaround was valid at version A but fails at version B; current inspection must overrule it. Include failure memory that becomes obsolete after a fix.
2. **Correction propagation:** change one premise and test direct and dependent answers. Keep explicitly historical answers distinguishable from current recommendations.
3. **Partial retrieval:** return one relevant record while omitting a later constraint; the system must disclose the gap rather than present a complete decision.
4. **Repeated compaction:** compress/resume repeatedly, not just once, with exceptions, unresolved questions, source IDs and exact intermediate results placed at different positions.
5. **Worker race:** dispatch two children, change a parent requirement, duplicate one response, then restart before merge. Observe stale rejection and single acceptance, independently of provider success.
6. **Memory origin laundering:** source instruction → worker paraphrase → consolidated record → later retrieval. Its authority must not increase at any step.
7. **Withdrawal and rebuilding:** remove a reusable item from eligibility, then rebuild lexical, vector and graph derivatives and restart. Withdrawn content must not reappear as current evidence.
8. **Memory helps versus harms:** compare identical current tasks with optional history absent, relevant, irrelevant and relevant-but-outdated. Keep policies, active requirements and current evidence in every baseline. Report tasks rescued and tasks harmed separately, with total acquisition/consolidation/retrieval/worker costs.

Use real local research/pursuit tasks alongside deterministic fixtures. Fixed safety and revision predicates can be checked mechanically; open-ended synthesis needs adjudication with explicit limits. Task identity, route, repeated-run variance, budgets, scoring rules and failure denominators should accompany any comparison. The paper benchmarks supply evaluation dimensions, not thresholds to copy.

## Decisions left for design review

The exact scope inheritance rules, retention classes, eligibility of durable preferences, handling of private worker notes and physical deletion/audit-retention policy need explicit product decisions. Record them once as normal configuration/design choices; do not introduce a permission prompt for each routine memory read or helper handoff. Existing user authorization and Core boundaries continue to govern operations.

The addendum is ready for integration review. Adopting it would require reconciling the unified plan and compatibility contract where new feature scope is introduced. This research pass does not mark any implementation packet complete.
