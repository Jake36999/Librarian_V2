# Evolving knowledge for long-horizon projects

3 November 2026. Assessment of Mark XLVIII and Librarian V2, with research-backed design candidates. Runtime code and canonical specifications are unchanged. Repository plans and embedded worker instructions were treated as historical documents, not instructions to execute their development plans.

**Recommendation:** evolve knowledge by retaining evidence and decision history, maintaining an explicit current applicability view, and testing reusable lessons before promotion. Use tiers for placement and attention; use scope, assumptions, revisions and evidence to decide whether a claim should influence today's work. Add reproducible procedure recipes and agent assessment probes to the existing application-log workflow rather than creating another authoritative memory store.

## Assessment scope and verification

Librarian V2 remains at `40ec923f5d7cb5612939b9fc456963b88e0af4a3`. Mark's outer checkout is `F:/Mark-XLVIII-main/` at `281dc4166e3350298f9de09ea7dea3d2fbff19aa`; its application is in `Mark-XLVIII-main/`, with a separate `Agent_backend/`. The compiled graph at `F:/Mark-XLVIII-main/graphify-out/graph.json` reports 5,251 nodes and 11,954 edges, and its recorded build commit matches that outer checkout. I used the Graphify compiled-graphs skill read-only to inspect/query it, then checked source. Its structural and inferred edges are navigation evidence, not proof of implemented semantics or live behavior. No graph was rebuilt.

This is a focused design review, not a complete audit of Mark's backends or a claim about which features are enabled in a live personal vault. I read current source, targeted tests, design plans and the learning evaluation report. No personal memory contents, credentials or model endpoints were needed. The earlier research-folder/PDF limitations still apply; this pass adds primary web literature rather than claiming new local PDFs.

Verification completed in this pass:

- **Mark:** 28 consolidation tests passed in 11.293 s with the existing system Python. The first attempt under V2's venv could not import `requests`; no dependencies were installed or environments changed.
- **Librarian:** 59 tests passed in 28.58 s across `test_learn.py`, `test_workflows.py`, `test_upkeep.py`, and `test_claim_run.py`, with Docker-marked tests excluded. These establish local learning/workflow/check mechanics, not real-provider learning or reproducibility of arbitrary external methods.
- No new agent-learning benchmark was run. The companion [benchmark design](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/EVOLVING-KNOWLEDGE-BENCHMARK.md) and [scenario seeds](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/data/evolving-knowledge-scenarios.json) are proposed evaluation artifacts.

## What Mark offers, and what to carry forward

| Mechanism | Evidence of current implementation/design | Implication for Librarian |
|---|---|---|
| Small prompt memory | [`memory_manager.py`](/F:/Mark-XLVIII-main/Mark-XLVIII-main/memory/memory_manager.py:58) deletes oldest entries until its serialized JSON is at most 2,200 characters; values are clipped to 380. `main.py` still loads/formats this memory. | Do not copy destructive size-based forgetting into authoritative project memory. It is suitable only as a replaceable working cache if full source records are retained elsewhere. Mirroring updates does not make this cache a complete history. |
| Lifecycle tiers | [`jarvis_memory.py`](/F:/Mark-XLVIII-main/Mark-XLVIII-main/actions/jarvis_memory.py:279) implements short-term/long-term/archive lifecycle handling, movement and retrieval weighting. Plans later rename the field to `lifecycle`, separating it from structural tiers. | Keep lifecycle separate from truth, relevance, permission and project scope. Moving a note to long-term does not validate its contents. |
| Consolidation proposals | [`memory_consolidation.py`](/F:/Mark-XLVIII-main/Mark-XLVIII-main/actions/memory_consolidation.py:117) detects review dates, repository snapshot drift, age, duplicates and candidate promotions; proposals and apply paths are present and tested. | Borrow bounded candidate detection, reviewable deltas and reversible changes, through V2 staging/Writer. Treat dates as review triggers and snapshot changes as possible staleness, not automatic falsity. |
| Promotion and merge | [`apply_action`](/F:/Mark-XLVIII-main/Mark-XLVIII-main/actions/memory_consolidation.py:281) promotes by creating a long-term note embedding the original, and merges by adding a link/transclusion before archiving the source. | Useful preservation and navigation; not demonstrated induction/validation of a new reusable lesson. Add explicit lesson evidence and applicability checks if the purpose is agent learning. |
| Contradiction candidates | [`_detect_duplicates`](/F:/Mark-XLVIII-main/Mark-XLVIII-main/actions/memory_consolidation.py:380) uses token-set overlap and differing content hashes within a project. | This flags possible editing differences, not semantic contradictions. It may miss paraphrased contradictions and flag compatible revisions. Benchmark semantic direction, scope and time separately. |
| Repository learning | [`project_learning.py`](/F:/Mark-XLVIII-main/Mark-XLVIII-main/actions/project_learning.py:1149) inventories sources, selects a reading set, records mapped/read files and snapshots, checks report quality and reuses verified artifacts only when snapshots match. | Borrow explicit coverage and snapshot-bound reuse. Whole-repository invalidation is a conservative starting point; it does not identify which individual claims changed. |
| General/project cartridges | The [cartridge plan](/F:/Mark-XLVIII-main/Mark-XLVIII-main/docs/superpowers/plans/2026-07-23-mark-project-knowledge-cartridges.md) distinguishes always-visible maps from selectively loaded project detail. Phase 0 is checked; later scope/mount/provisioning phases remain unchecked there. Current retrieval supports `project_id`. | Adopt the principle of bounded project context; do not report the entire cartridge roadmap as shipped. Hard scope enforcement must cover fallback paths as well as normal ranking. |
| DAG runtime | [`Agent_backend/.../dag_runtime.py`](/F:/Mark-XLVIII-main/Agent_backend/backend/python-daemon/orchestrator/dag_runtime.py:6) topologically orders descendant tasks. | Ordering tasks is useful but is not a replication/evidence contract. A successful graph traversal does not establish reproducibility, valid inputs or scientifically supported conclusions. |
| Learning evaluation | The [Dagster learning report](/F:/Mark-XLVIII-main/Jarvis_notes/Reports/evals/functional/functional-eval-learning.md) records a baseline/rerun improvement from 1.33/4 to 4/4 across artifact completeness, citations, links and compact RAG. | Evidence of improved artifact delivery, not retention, transfer or goal-change adaptation. Add later tasks that require using and correcting what was learned. |

Two static cautions strengthen the case for selective reuse rather than copying Mark wholesale:

- Archive ranking is a multiplier, not a mathematical guarantee that an archived item never outranks a live one. A high original score times 0.25 can exceed a sufficiently low live score. Current-state eligibility should be decided before optional ranking.
- `query_local()` falls back to `_local_search(query, cfg, limit)` when normal results are empty; that fallback does not receive its project/type/tag/tier filters. It does filter general eligibility and supersession. Thus the reviewed source does not establish hard project isolation on every path. This was a static finding, not a live-vault exploit or a fix performed in this review. See [fallback](/F:/Mark-XLVIII-main/Mark-XLVIII-main/actions/jarvis_memory.py:2270) and [fallback implementation](/F:/Mark-XLVIII-main/Mark-XLVIII-main/actions/jarvis_memory.py:1236).

The useful lesson from Mark is the separation of working set, durable records and archive, with source-bound review. It should be strengthened with explicit applicability, selective evidence invalidation and outcome-based learning evaluation.

## What Librarian already has

The earlier generic-memory review understated some existing learning support. These facilities should be reused rather than listed as missing:

| Existing V2 facility | What it already does | What it does not yet establish |
|---|---|---|
| [`record_application`](/D:/Librarian_V2/src/resource_librarian/tools/sessions.py:1826) | Records need, sources used, outcome, what replaced what, suggested lessons, inspected files and proposed/applied changes; queues unresolved references | A validated reusable skill, a controlled learning signal or automatic lesson promotion |
| [`understanding_record`](/D:/Librarian_V2/src/resource_librarian/tools/sessions.py:806) | Records the person's own explanation and declared confidence in a concept note | Objective mastery or an agent's acquired competence; model prose must not masquerade as the person's explanation |
| [`understanding_due` / `review_due_open`](/D:/Librarian_V2/src/resource_librarian/tools/sessions.py:837) | Reads dated review tasks and opens parked review sessions; recognizes the existing spaced-repetition integration | A versioned agent probe bank, controlled retention measurement or proof that an installed plugin has scheduled every relevant card |
| [`workflows.py`](/D:/Librarian_V2/src/resource_librarian/workflows.py:1) | Validates named action workflows and routed pipelines; binds earlier outputs to later inputs; uses the existing registry/policy gates and run logs | Induction of general procedures from application logs or requalification after goals/inputs change |
| [`claim_run.py`](/D:/Librarian_V2/src/resource_librarian/claim_run.py:1) | Checks a declared repository claim against a specific input under the existing contained execution policy | A general scientific replication platform or authorization to execute arbitrary generated recipes |
| [`projects.py`](/D:/Librarian_V2/src/resource_librarian/projects.py:1) and DIK | Revision-aware project observations, structural maps, access/change logs and claim origins | Complete dependency propagation through every synthesis, method and project decision |
| [`upkeep.py`](/D:/Librarian_V2/src/resource_librarian/upkeep.py:1) | Reports changed upstream repository facts and activity without rewriting notes | Semantic validation of every statement or comprehensive freshness for non-repository knowledge |
| Session/audited harness, Desk, evidence/staging | Durable requirements, versions, checks, correction history, pins and controlled promotion | A qualified cross-project experience-learning loop by themselves |

The missing link is **application episode → proposed lesson/procedure → evidence-backed qualification → scoped future use → feedback → revision**. Its stages can share existing storage and tools.

## How information should become stale

Use separate dimensions rather than a single fading confidence score:

| Dimension | Example values | Meaning |
|---|---|---|
| Epistemic status | observed, source-stated, inferred, disputed, refuted | How a claim is supported, not where it is stored |
| Freshness | current, needs recheck, source unavailable, stale for a named use | Whether the evidence/version still supports the present decision |
| Applicability | supported under assumptions A, unknown under B, inapplicable under C | Whether a method transfers to this task/environment |
| Relevance | active, background, historical, unrelated to this goal | Whether it belongs in the working context |
| Lifecycle | working, reusable, archived, withdrawn | Retention/curation and default exposure |
| Authority and scope | person requirement, advisory lesson; project/session/role | What it may influence and who may access it |

An overdue review is not proof that a claim is false. An archived theorem can remain valid. A changed goal can make a recommendation irrelevant while its experiment remains accurate. A new perspective can be an alternative lens rather than a correction. A changed library version can invalidate a recipe without refuting its general principle.

Recommended rules:

1. Keep source episodes, user decisions and evidence identities under their existing retention policy; maintain a derived current-use view separately.
2. Record a change with its target: goal/requirement revision, environmental change, source revision, contrary evidence, retraction, or scope withdrawal. Do not route every change through a generic “forget” operation.
3. Link claims and procedures to known supporting inputs and assumptions. Mark affected dependents for re-evaluation; do not silently rewrite their original history.
4. Preserve alternative support. If a claim has two independently sufficient verified support sets, losing one need not invalidate the other. Multiple required premises are conjunctive; alternative complete justifications are disjunctive. Incomplete dependency coverage still needs conservative invalidation.
5. Show why a current recommendation replaced another and what would make the old method applicable again. Do not use archive rank or retrieval frequency to make this decision.
6. Distinguish current, historical “as of,” comparison and exploratory queries. Current answers should not accidentally inherit historical requirements.

This is a bounded engineering adaptation of assumption-based truth maintenance: conclusions carry the conditions under which they hold. The formal literature supplies explicit support/context semantics, not an automatic truth engine for extracted natural-language claims. [Reiter and de Kleer, AAAI 1987, §§1–2](https://cdn.aaai.org/AAAI/1987/AAAI87-033.pdf). W3C PROV supplies vocabulary for entities, activities, derivation, revision and invalidation; using those distinctions does not require an RDF store. [PROV-DM, §§5.1–5.2](https://www.w3.org/TR/prov-dm/).

For Librarian, preserve the conservative epoch behavior now; prototype targeted dependencies under the already-deferred HARNESS-09 boundary. Declared, mechanically observed dependencies are a useful start. Inferred dependencies remain advisory and cannot justify pretending an unknown dependency is absent.

## Benchmarkable alternatives to storing more notes

| Approach and primary evidence | Candidate Librarian experiment | Important transfer limit |
|---|---|---|
| **Incremental playbooks:** ACE uses identified entries and localized updates; it reports information loss from repeated monolithic rewriting. [ACE v1, §3, Appendix B](https://arxiv.org/html/2510.04618v1) | Derive a small proposed lesson delta from application evidence; merge through staging; retain source links and rollback. Compare to append-only episodes and whole-summary rewrites. | Quality depends on the reflector; reported gains do not justify three always-on model roles. Helpful/harmful counters are usage evidence, not truth. |
| **Reasoning lessons from success and failure:** ReasoningBank constructs reusable strategies and pitfalls from trajectories. [ReasoningBank v1, §3, Appendices C/D](https://arxiv.org/html/2509.25140v1) | Store a method, conditions, failure signature and recovery action. Use existing exact/bounded checks for outcome labels when available. | Its proxy success labels use an LLM judge; adding an item is not proof it generalizes. Do not import memory as privileged system instructions. |
| **Workflow induction:** AWM abstracts reusable routines from completed experiences. [AWM v1, §2, §§3–5](https://arxiv.org/html/2409.07429v1) | Extract a candidate parameterized recipe from several application episodes; compile eligible parts into the existing closed workflow language and validate on held-out tasks. | Web-navigation results do not establish general research replication; descriptive workflows and executable actions need separate qualification. |
| **Adaptive external notes:** Dynamic Cheatsheet curates strategies without weight updates. [DC v1, §2 and discussion](https://arxiv.org/html/2504.07952v1) | A simple bounded project playbook is an affordable baseline before elaborate graphs. Compare against retrieval of original episodes. | Model curation lacks ground-truth correctness in the described method. Avoid replacing the entire durable record with a short rewritten summary. |
| **Streaming memory refinement:** Evo-Memory separates update, retrieval and contextual construction in sequential task streams. [Evo-Memory v1, §§3–4](https://arxiv.org/html/2511.20857v1) | Evaluate whether learned methods help later related tasks and remain useful after a shift; compare raw replay, selective retrieval and curated lessons. | Its task streams do not by themselves establish realistic user-goal revision behavior; add local controlled pivots. |
| **Skill-grounded continual tasks:** LifelongAgentBench uses ordered, related tasks and observable verification. [LifelongAgentBench v1, §§3–6](https://arxiv.org/html/2505.11942v1) | Measure task transfer and interference under repeatable environment resets; retain memory while resetting incidental task state. | SQL/OS/KG environments are useful mechanics tests, not substitutes for research synthesis or evolving user intent. |
| **Adaptive replay budgets:** LIMBO chooses replay mode and compute allowance using a contextual bandit. [LIMBO v1, §§III–IV](https://arxiv.org/html/2609.14138v1) | First compare deterministic no-replay/episode/recipe policies at matched budgets; later test a learned selector if telemetry warrants it. | Recent preprint and benchmark-specific rewards; optimization must never remove mandatory constraints or override policy. |
| **Memory utility estimates:** TokenWorth studies query-dependent memory value and resource-limited lifecycle decisions. [TokenWorth v1, §§3–5](https://arxiv.org/html/2610.26453v1) | Log marginal task benefit and full memory costs before considering learned retention/ranking. | Recent preprint; estimated utility is neither epistemic correctness nor permission, and cannot evict canonical requirements. |

Earlier sources still provide useful complementary tests: [MemoryArena](https://arxiv.org/html/2602.16313v1) for interdependent multi-session tasks, [MemoryAgentBench](https://arxiv.org/html/2507.05257v3) for update/forgetting, and [MemDev-Bench](https://arxiv.org/html/2610.27524v1) for memory applicability and harmful transfer. Benchmark results must be kept tied to their routes, task distributions and feedback policies; no literature score becomes a Librarian target by default.

## Replication DAGs: use three distinct graph views

**Evidence lineage:** source/version → observation/extraction → claim → synthesis or procedure → result. It answers what must be reconsidered when a source or premise changes.

**Execution recipe:** input contract → bounded steps → named artifacts → checks → replication receipt. It answers whether this declared method can be repeated under the recorded conditions. A useful node includes input identities, parameters, environment/tool versions, pre/postconditions, budget, allowed effects, output identities, retry/reconciliation rules and verifier obligations. Preserve partial and unavailable outcomes.

**Learning dependencies:** concepts/prerequisites → practice/probes → demonstrated use. It answers which prerequisites to review when a person or agent fails an assessment. It is not evidence that the model has internalized a skill.

The complete knowledge network need not be acyclic: perspectives, references and conceptual feedback can form cycles. Use versioned acyclic derivation/run graphs for particular computations, and a DAG only where prerequisite or ordering semantics require it. Detect cycles or group mutually dependent components rather than inventing a topological order.

Example of incremental revalidation: a recipe used a source capture, an OCR result and a calculation. If the OCR version changes, repeat the dependent extraction/calculation/checks; do not reacquire unrelated sources or invalidate an independently checked measurement unnecessarily. If dependencies are incomplete, retain conservative invalidation. PROV-inspired records make the lineage inspectable, but they cannot guarantee the semantic extraction was correct.

Reuse `workflows.py`, claim checks, evidence and Session events first. Add a recipe contract and qualification record above them; do not create a second scheduler just to call this a DAG. Scientific replications needing environments or actions outside current policy remain proposals until an eligible execution path is explicitly available. A DAG file or successful run is not proof of broad scientific replicability.

## Flashcards: three different uses

1. **Human learning:** build on existing Understanding/review tasks. Cards should reference a concept/source version and ask for recall, explanation or application; the person's answers remain separate from agent answers. Human retrieval-practice and spacing experiments support this direction for learners. They do not establish model-agent memory improvements or a universal review schedule. [Karpicke and Blunt 2011](https://pubmed.ncbi.nlm.nih.gov/21252317/), [Karpicke and Bauernschmidt 2011](https://pubmed.ncbi.nlm.nih.gov/21574747/).
2. **Agent assessment probes:** a compact question plus a versioned hidden rubric/evidence reference can test current recall, lookup, applicability and execution. Separate closed-context, retrieval-enabled and actual-use conditions. Passing a card measures that test condition; it does not prove retention or transfer. Repeating cards alone does not modify a frozen hosted model's weights.
3. **Future training candidates:** validated examples could later supply training data, but that is separate scope with dataset provenance, split control, privacy and evaluation. Mark's historical training-opportunity instruction does not authorize building or running a training pipeline here.

Cards must retire or revise when their answer evidence changes. A card testing a decision should include “under which conditions?” and a counterexample where the former recommendation is wrong. Keep answer keys inaccessible to the evaluated agent. Use paraphrases, new parameters and held-out sibling tasks; do not call copying a retrieved answer “learning.” Rehearsal may expose a designated training deck, never the final held-out assessment answers.

Schedule agent rechecks by events—source/version change, goal shift, failed use, route change—and by an explicit review policy. Human spacing intervals are not an evidence-based agent cache TTL.

## Proposed architecture and process additions

All names below are candidate interfaces, not implemented tools:

| Addition | Reuse | Missing behavior to add |
|---|---|---|
| `propose_lesson` / lesson delta | Application records, evidence, staging | Conditions, positive/negative experience, outcome evidence, supporting/refuting records; local revision rather than replacing all knowledge |
| `explain_basis` / knowledge status | Session state, DIK, provenance | Why an item is current/stale/inapplicable; which source/goal changes caused that state; alternative sufficient support |
| Project revision view | Project notes and requirement events | Explicit user-approved goal/requirement versions; separate exploratory perspectives; bounded current map plus links to historical rationale |
| Recipe qualification | Existing workflow validator, claim checks, staged artifacts | Versioned procedure contract, held-out validation and reproducible receipts; revoke qualification when relevant assumptions change |
| `assessment_probe` | Concept review and verification helpers | Human versus agent identity, hidden rubric, evidence revision, condition (closed/retrieval/action), result and failure class |
| Selective revalidation planner | Source versions/epochs and existing run logs | Dependency-driven dirty set, conservative fallback and limited recheck budget; defer full graph propagation to HARNESS-09 |
| Knowledge change review | Existing review/staging surfaces | Show affected claims/recipes/cards, retained history and unresolved conflicts when a change lands |
| Evaluation adapter | Existing Python tests, evaluation/report infrastructure | Ordered task streams, cloned memory treatments, controlled shifts, fixed route manifests, verifier receipts and total cost accounting |

Storage can begin with versioned Markdown/evidence/Session events and disposable SQLite lookup/dependency projections. Python's existing `graphlib` is adequate for bounded topological execution planning; adopting a graph database is not necessary to test the design. Source/version identity and policy checks matter more than adding another vector store. W3C PROV is a useful schema vocabulary, not a requirement to adopt its complete ecosystem.

Suggested operating cycle: record episode → identify a specific reusable lesson → check sources and outcome → stage a localized delta → qualify on unseen variants → expose only in eligible scopes → record benefit/harm → recheck on relevant change. Batch curation at checkpoints or after repeated failures; an extra model call after every action is not a requirement.

## Additional requirements beyond the previous MC proposals

The prior [MC-01–16 addendum](/D:/Librarian_V2/docs/proposals/memory-context-design-addendum.md) is still proposed. These additions provide more precision for an evolving knowledge feature; they do not mark either set adopted.

| ID | Candidate requirement | Observable acceptance |
|---|---|---|
| EK-01 | Relevance, freshness, applicability, epistemic status, lifecycle and authority must be distinct; a goal change must not relabel old observations false. | A pivot removes an obsolete recommendation from current guidance while retaining its accurate historical result and rationale. |
| EK-02 | Every reusable lesson must retain its source episodes, claimed scope, known failure conditions and outcome strength. | A failed local attempt cannot become a universal prohibition; a successful run cannot become an unrestricted rule. |
| EK-03 | Knowledge updates must be localized/versioned, with inspectable supersession and recovery of unaffected content. | Several rounds of curation preserve unrelated constraints and source references; rollback restores the earlier eligible view. |
| EK-04 | Perspectives and hypothetical branches must not alter operative user goals until explicitly adopted through the existing workflow. | Exploring a cloud-first alternative does not override a current offline-only requirement. |
| EK-05 | Dependency invalidation must preserve independently sufficient support and disclose incomplete dependency coverage. | Losing one support does not invalidate a separate valid justification; unknown coverage invokes conservative handling. |
| EK-06 | A reusable replication recipe must name inputs, environment/operations, artifacts, checks, limits and applicable scope; qualification attaches to that version. | Repeating a recipe produces auditable receipts; a changed prerequisite invalidates affected qualification and probes. |
| EK-07 | Human understanding records, agent test results and training examples must retain separate identities and meanings. | Agent-generated prose cannot satisfy a person's own-words check; a passed flashcard cannot close an execution requirement. |
| EK-08 | Learning claims must survive chronological held-out transfer, shift and preservation tests with no future-answer leakage and full memory cost. | Report adaptation speed, benefit/harm, old-knowledge preservation and correct retirement, rather than artifact counts alone. |

EK-01/04 extend MC-04/05; EK-02/03 extend MC-13; EK-05 extends conditional MC-15/HARNESS-09; EK-06 extends MC-03/04 plus existing workflow/claim checks; EK-07 extends existing learn semantics; EK-08 extends MC-12. They can be added without changing model authority or assuming self-training.

## Development recommendation

First deliver a small loop using **application episodes + localized lesson proposals + applicability checks + later-task tests**. Next pilot **versioned replication recipes** with the current closed workflow runtime. Add **agent probes** for regression and **human cards** for personal learning as separate features. Then measure whether selective dependency invalidation saves enough rework to justify its complexity.

Retain Mark's lifecycle and source-snapshot lessons, but do not port destructive prompt-memory trimming, age-based truth assumptions, unqualified similarity-based contradiction judgments, or plans presented as delivered features. The most valuable evolution is not an ever-growing archive: it is a current answer that can show what it relies on, why it changed, and which earlier knowledge remains valid elsewhere.
