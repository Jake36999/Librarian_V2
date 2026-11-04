# Established solutions for Librarian's memory research objectives

3 November 2026. Primary-source research, tooling screening and small abstract model checks. This report answers R1–R8 from the [research agenda](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/consolidated/03-RESEARCH-OBJECTIVES.md). It does not adopt requirements or change runtime code.

## Main conclusion

There are established solutions for **history, dependency tracking, transactional acceptance, durable workflows and reproducible evaluation**. There is no demonstrated universal solution in the reviewed evidence for automatically producing true, transferable lessons from arbitrary agent experience.

The strongest design is a deterministic memory-control layer around an empirically evaluated learning layer:

- Store versioned evidence and explicit applicability intervals.
- Enforce current scope, revisions, support and budgets before use or acceptance.
- Treat learned lessons as conditional cases with observed outcomes.
- Revalidate dependencies and test transfer on later tasks.

This can largely extend the existing Session/evidence/SQLite/workflow architecture. The most immediately useful additional tools are verification and evaluation tools, rather than a replacement memory service.

## What “formal or proven” means here

| Evidence class | What it establishes | What it does not establish |
|---|---|---|
| Formal result | A property follows from a stated mathematical model and assumptions | That natural-language extraction is correct or implementation refines that model |
| Standard/specification | Defined interoperable semantics and conformance obligations | That a particular deployment conforms or its output is scientifically correct |
| Established implementation | Documented mechanisms, inspectable source and operational experience | A universal guarantee or fitness for Librarian without integration tests |
| Empirical research | Improvement or failure on the reported tasks, models and conditions | General improvement on Librarian's projects |
| Local reference check | All reachable states in a specified small abstract model satisfy a predicate | Verification of production code, unbounded executions, real crashes or agent reasoning |

The [formal contracts and check results](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/formal-solutions/FORMAL-CONTRACTS.md) and [tool decision register](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/formal-solutions/TOOL-DECISIONS.md) make these boundaries explicit.

## R1 — Durable memory: bitemporal records and transactional projections

**Established solution:** distinguish system time (when a record entered the system) from valid time (when it is asserted to apply). This supports both “what do we now believe applied last month?” and “what did we believe last month?” XTDB implements these as separate timelines; its documentation also warns that database validity must be mapped carefully to domain semantics. [XTDB time model](https://docs.xtdb.com/about/time-in-xtdb.html); [SQL semantics](https://docs.xtdb.com/quickstart/sql-overview.html).

**Proposed Librarian application:** retain existing durable events, add explicit valid intervals and versioned current-use projections, and distinguish unknown validity from a known interval. Treat source availability and current access as additional predicates. Backdated corrections produce a new recorded version rather than destroy the earlier state. A goal revision changes a recommendation's applicability, not the historical observation it used.

SQLite provides serializable transactions by serializing writers, and snapshot reads in WAL mode. These are useful for atomic local acceptance, but do not automatically coordinate a Markdown write, database update and remote side effect. [SQLite isolation](https://www.sqlite.org/isolation.html). Use the existing Writer/event authority with a durable operation identity and recoverable projection watermark; do not introduce a second independent source of truth.

Use PROV's entity/activity/derivation/revision distinctions for evidence identity and interchange. Provenance describes where a statement came from, not whether it is true. [W3C PROV-DM, 2013 Recommendation](https://www.w3.org/TR/2013/REC-prov-dm-20130430/).

**Decision:** adapt temporal semantics locally; defer XTDB deployment unless temporal query scale or maintenance cost demonstrates a need. Acceptance must cover late corrections, exact-version reopening, index rebuild, withdrawal and current-versus-historical queries.

## R2 — Long-horizon context and workers: explicit state machines

**Established solution:** model dispatch, completion, revision, acceptance, retry and reservation as state transitions, with machine-checkable invariants. AWS reports using TLA+ and model checking to find subtle distributed-system design bugs. This is strong evidence for the engineering method, not proof of Librarian's implementation. [Newcombe et al., 2014](https://lamport.azurewebsites.net/tla/formal-methods-amazon.pdf).

**Proposed application:** each worker result carries its parent requirement revision, source-version references and stable operation identity. The parent checks eligibility and records acceptance atomically against current state. A duplicate receipt is not a second accepted contribution. Uncertain external completion retains an explicit unresolved state. Resource reservations must be shared and committed before dispatch.

Temporal documents why activities can repeat when work succeeds but the completion report is lost; application/service idempotency remains necessary. LangGraph distinguishes per-thread checkpoints from cross-thread stores; checkpointing alone does not define correct lesson reuse. [Temporal activity semantics](https://docs.temporal.io/activity-definition); [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence).

For context, use deterministic essential-state projection plus selectively loaded evidence, and check the complete serialized request at dispatch. A size cap is enforceable; reliable use of every included constraint is behavioral and must be tested. No bounded summary can losslessly encode every possible arbitrarily long history. Preserve rehydration and declare which information may be omitted.

**Decision:** use TLA+/TLC for a focused state model and Hypothesis for implementation-level transition testing. Keep the current runtime unless a separate orchestration comparison justifies replacement. Local finite checks already distinguish guarded transitions from deliberately broken variants; they are described in the companion report.

## R3 — Reusable lessons: case-based reasoning with qualified updates

**Established solution:** case-based reasoning explicitly separates retrieval, reuse, revision through evaluation, and retention. Its foundational account treats adaptation and testing as essential, rather than assuming that similarity makes an earlier solution correct. It also identifies domain dependence. [Aamodt and Plaza, 1994, §§3.3–3.5](https://www.iiia.csic.es/~enric/papers/Aamodt_1994_Case.pdf).

**Modern empirical support:** ACE uses localized updates instead of wholesale context rewriting; its authors warn that a weak reflector can produce harmful context. ReasoningBank extracts strategies from successes and failures but acknowledges noisy LLM-judge labels. These are useful prototypes, not truth guarantees. [ACE v1, §3 and Appendix B](https://arxiv.org/html/2510.04618v1); [ReasoningBank v1, Appendix E](https://arxiv.org/html/2509.25140v1).

**Proposed application:** application logs become cases containing the task, relevant conditions, method, outcome and source/check receipts. A generalized lesson is a separate, versioned hypothesis. Record its tested applicability region and known counterexamples. Keep mechanical test results separate from model judgments and personal confidence. A failed attempt under an old environment must not become a permanent prohibition.

**Decision:** adapt the case-based process and incremental curation; pilot rather than declare automatic learning proven. Compare A/B/C/D from the existing benchmark design. Promote a procedure only within the scope supported by its checks; a single success cannot establish unrestricted transfer.

## R4 — Staleness: support-set maintenance and incremental recomputation

**Formal foundation:** assumption-based truth maintenance associates conclusions with supporting assumptions. Provenance semirings formalize how alternatives and joint dependencies combine for positive relational queries; the factorization theorem explains how annotations can be evaluated under different semirings. These results concern formal inputs and operators, not arbitrary prose claims. [Reiter and de Kleer, 1987](https://cdn.aaai.org/AAAI/1987/AAAI87-033.pdf); [Green et al., PODS 2007, §§3–4](https://web.cs.ucdavis.edu/~green/papers/pods07.pdf).

**Concrete application:** record `support(claim) = (source_A AND assumption_B) OR source_C` when either complete justification suffices. If A fails but C remains qualified, the conclusion still has support. Do not flatten this into “all ancestors must remain unchanged.” Represent unknown checks explicitly; absence of a discovered dependency is not proof of independence.

Build-system research separates scheduling from rebuild decisions and defines consistency with declared computations. Its correctness conditions depend on assumptions including acyclic tasks; nondeterministic tasks require a modified account. [Build Systems à la Carte, author draft, §3.6 and §6.3](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/build-systems-5ab0f42d0f937.pdf). The inspected PDF is marked under review; the [publisher listing](https://www.microsoft.com/en-us/research/publication/build-systems-la-carte/) identifies the subsequent ICFP 2018 publication.

**Decision:** adapt explicit support groups and recorded dependency fingerprints under HARNESS-09. Begin with declared/mechanically observed dependencies. Keep coarse invalidation when coverage is incomplete. LLM output requires task-level verifier equivalence, not an assumption of byte-identical recomputation. Measure missed invalidations and unnecessary invalidations separately.

## R5 — Replication DAGs: workflow standards plus run provenance

**Established solution:** CWL v1.2.1 defines workflow inputs/outputs, data dependencies and execution ordering, with conformance tests. It supplies a concrete exchange contract for computational workflows. It does not establish that the method being executed is correct. [CWL Workflow specification v1.2.1](https://www.commonwl.org/v1.2/Workflow.html).

Workflow Run RO-Crate packages execution provenance and associated inputs, outputs and code at different levels of detail; its Process profile can be used without adopting a workflow engine. [Workflow Run RO-Crate](https://www.researchobject.org/workflow-run-crate/); [RO-Crate 1.1 metadata specification](https://www.researchobject.org/ro-crate/specification/1.1/).

**Proposed application:** extend existing workflow definitions with input/environment fingerprints, explicit check obligations and version-bound qualification receipts. Export a bounded run package when useful. Separate a descriptive method, an authorized executable recipe and evidence that a particular run met its claims. Specify whether success means exact artifact equality, numerical tolerance or a task predicate.

**Decision:** adopt the contract concepts; investigate CWL/RO-Crate interoperability at the boundary. Defer a new runner. The inspected cwltool instructions route Windows users through WSL2/Docker, so it is not a frictionless native-Windows replacement. Environment changes, retry uncertainty and missing inputs must remain visible outcomes.

## R6 — Flashcards and probes: separate scheduling from competence

**Established tooling:** Anki's FSRS schedules human reviews using review history and a retention/workload trade-off. This is relevant to the existing personal review workflow, not a demonstrated decay model for hosted language models. [Anki FSRS documentation](https://docs.ankiweb.net/manual/deck-options#fsrs).

**Proposed agent solution:** versioned regression probes triggered by relevant source, requirement, tool, recipe or model changes, with periodic sentinel tasks for changes not captured by dependencies. Use separate recall, evidence-backed answer and execution scores. Keep held-out rubrics outside reusable memory. A card whose source changes needs revision; a correct old answer may still be appropriate for an explicitly historical question.

**Decision:** preserve existing human-learning support; consider Anki/FSRS integration only for that use. Adapt ordinary regression-testing discipline for agent probes, then measure detection benefit versus overhead. There is no reviewed evidence justifying human forgetting curves as automatic agent-memory expiry.

## R7 — Evaluation: stateful tests plus independent task-stream scoring

**Established tooling:** Hypothesis stateful testing generates sequences of actions and checks invariants against a reference model. It finds and minimizes counterexamples but is not exhaustive verification. [Hypothesis stateful documentation](https://hypothesis.readthedocs.io/en/latest/stateful.html).

Inspect provides composable agent evaluations and an agent bridge. Its bridge redirects model calls, so integration must verify route fidelity rather than silently evaluate a different calling path. [Inspect](https://inspect.aisi.org.uk/); [agent bridge](https://inspect.aisi.org.uk/agent-bridge.html).

**Empirical caution:** LifelongAgentBench reports model- and replay-size-dependent effects, including degradation. More historical experience is therefore a treatment to test, not an assumed improvement. [LifelongAgentBench v1, §§6.2–6.3](https://arxiv.org/html/2505.11942v1).

**Decision:** add a development-only stateful test layer and prototype an isolated Inspect adapter. Preserve current requirements in every baseline. Use chronological acquisition/test splits, cloned initial memory, equal feedback, unseen project families and paired stream-level uncertainty. Report success, harm, stale use, preserved knowledge, adaptation lag and total costs. Public benchmark scores do not set Librarian's acceptance thresholds.

## R8 — Retrieval: retain hybrid fusion; target graph use

**Established empirical method:** reciprocal rank fusion combines ranked lists without requiring a learned fusion model, with positive TREC/LETOR results in the original study. It does not guarantee relevant or correct results for every query. V2 already has this general mechanism. [Cormack et al., SIGIR 2009](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf).

GraphRAG's evidence is strongest for corpus-wide sensemaking; its reported comparisons favor global methods for comprehensiveness/diversity, while vector retrieval is more direct. That does not establish a general advantage for exact lookup, temporal corrections or access control. [GraphRAG v2, §5](https://arxiv.org/html/2404.16130v2).

The inspected Microsoft GraphRAG README now describes the project as largely in maintenance mode. This materially weakens the case for making it a new central dependency, despite recent repository activity. [Pinned README](https://github.com/microsoft/graphrag/blob/34b2b67ae4601ad0b47bcd179fbe3f2a23aa0857/README.md).

**Decision:** retain scoped lexical/vector fusion. Pilot bounded graph/community expansion only for a task class that needs it. Evaluate coverage before top-k truncation and enforce scope at expansion, fallback and rehydration boundaries. Defer adaptive memory-policy training until simple policies and reliable utility telemetry exist.

## Ranked development recommendations

| Order | Recommendation | Evidence and remaining work |
|---|---|---|
| 1 | Formalize worker acceptance, shared reservations and evidence continuity | Strong systems foundations; implementation/refinement tests still needed |
| 2 | Add bitemporal meanings and versioned current-use views | Established temporal model; local schema/migration decisions remain |
| 3 | Build stateful regression tests and a task-stream evaluation adapter | Existing tools; adapter and behavioral benchmark remain unimplemented |
| 4 | Pilot conditional cases and localized lessons using application logs | Established process plus bounded empirical evidence; transfer must be demonstrated |
| 5 | Add version-qualified recipe receipts and optional provenance export | Published standards; external execution and reproducibility require validation |
| 6 | Prototype support groups and selective revalidation | Formal foundations; dependency completeness and scaling remain hard |
| 7 | Add separate human review integration and agent regression probes | Tooling exists; scheduling benefit needs measurement |
| 8 | Add graph routing or replacement infrastructure only on measured need | Task-specific evidence; avoid unnecessary platform migration |

## Work completed and limits

This pass read selected primary papers, official standards/documentation and pinned repository files. Nine repository snapshots and license indicators were recorded. Current V2 HEAD still matches the prior review; its Python/runtime dependency manifest was checked for integration fit. This was not another full repository audit.

A standalone finite reference explorer was executed: guarded worker acceptance explored 97 states, atomic reservations five states, and support logic eight Boolean valuations plus two unknown-state cases. Deliberately broken alternatives produced counterexamples. These are abstract research checks, not production tests or a TLA+ proof.

No dependencies were installed, services launched, paid model calls made, runtime code edited, or canonical requirements adopted. Public learning benchmarks and candidate systems were not reproduced. The practical result is a sourced architecture choice and a bounded verification plan, with the unresolved empirical questions made explicit.
