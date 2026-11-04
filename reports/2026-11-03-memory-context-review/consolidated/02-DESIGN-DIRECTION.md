# 2. Consolidated design direction and requirements

3 November 2026. Candidate design direction. No canonical specification, implementation status or release gate is changed.

## Preserve history; revise eligibility for current use

Keep evidence and decision history under explicit retention rules. Maintain a separate current-use view that can exclude outdated guidance without erasing why an earlier decision was reasonable. A goal shift can make a recommendation unsuitable while leaving its original measurements valid.

Represent distinct dimensions:

| Dimension | Question answered |
|---|---|
| Epistemic status | Is this observed, source-stated, inferred, disputed or refuted? |
| Freshness | Has the supporting source/version been checked for this use? |
| Applicability | Under which task, environment and assumptions does it hold? |
| Relevance | Does it matter to the operative goal? |
| Lifecycle | Is it working material, reusable, archived or withdrawn? |
| Authority and scope | What may it influence, and where may it be accessed? |

An overdue review is a recheck trigger, not proof of falsity. Retrieval frequency is a utility signal, not validation. A hypothetical perspective must remain separate from adopted requirements. Current, historical, comparison and exploratory queries need different eligibility semantics.

## Proposed architecture

Retain existing Session/evidence/Markdown records as the durable basis and use derived indexes for lookup. Start with the existing SQLite infrastructure and bounded dependency structures. Whether an external graph or memory service is justified remains an experimental question.

The proposed learning cycle is:

1. Record an application episode and its observable outcome.
2. Propose a localized lesson containing conditions, evidence, limitations and failure cases.
3. Qualify it against current checks and previously unseen task variants.
4. Publish the accepted version through existing staging/Writer ownership.
5. Retrieve it only in eligible scopes and verify its applicability to the current task.
6. Record helpful and harmful uses; revise or withdraw the relevant version when conditions change.

Localized updates are motivated by [ACE](https://arxiv.org/html/2510.04618v1); success/failure lessons by [ReasoningBank](https://arxiv.org/html/2509.25140v1). Their results motivate experiments rather than establish that an LLM-generated lesson is correct. Preserve original episodes and avoid granting remembered text privileged instruction authority.

Candidate interfaces include `propose_lesson`, `explain_basis`, `knowledge_status`, recipe qualification and `assessment_probe`. These are design names, not existing registered tools or authorization to implement them.

## Three different graph purposes

| View | Meaning | Required distinction |
|---|---|---|
| Evidence lineage | Which sources and assumptions support a claim or recommendation? | Declared/observed dependencies versus inferred, possibly incomplete links |
| Replication recipe | Which bounded steps produce named artifacts and checks? | Executable dependency ordering versus evidence that a result is correct |
| Learning prerequisites | Which concepts or abilities a practice task depends on | Human learning versus agent evaluation |

A general knowledge graph need not be acyclic. Execution plans and versioned derivations need defined cycle handling. Preserve independently sufficient justifications: required premises are conjunctive, alternative complete support sets are disjunctive. If dependency coverage is unknown, use conservative invalidation rather than assume no dependency. Formal support semantics and provenance vocabulary offer useful patterns, not an automatic truth oracle. [Reiter and de Kleer](https://cdn.aaai.org/AAAI/1987/AAAI87-033.pdf); [W3C PROV-DM](https://www.w3.org/TR/prov-dm/).

A replication recipe should identify input versions, environment, parameters, allowed operations, pre/postconditions, artifacts, verifiers, limits and retry/reconciliation behavior. Build on existing workflows and claim checks; a generated recipe must not acquire arbitrary execution privileges.

## Flashcards and probes

Maintain separate identities for human understanding, agent assessment and possible future training data. Human cards can support recall and application. Agent probes should measure closed-context recall, retrieval-assisted answers and actual task execution separately, with versioned evidence and hidden scoring criteria. Passing a card does not establish procedural competence; repeatedly presenting cards does not update a frozen model's weights. Human retrieval-practice evidence supports a separate human learning feature, not an agent forgetting schedule. [Primary human study](https://pubmed.ncbi.nlm.nih.gov/21252317/).

## Multiagent and context contracts

Bound the final dispatched request, including system content, schemas, essential state, dialogue, retrieved material and continuation overhead. Preserve essential typed constraints; split or park when they cannot fit. Compaction must keep evidence references and disclose omissions.

Worker handoffs should carry task identity, input/requirement revision, permitted scope, outcome, evidence versions, unresolved questions, truncation/coverage status and cost receipts. Recheck scope and applicability at parent merge. Duplicate results must not be accepted twice; stale results must not close revised requirements. Budgets need shared reservations rather than independent worker estimates. Worker-private context should not become globally shared merely because it might help retrieval.

## Consolidated requirement crosswalk

The detailed [MC draft](/D:/Librarian_V2/docs/proposals/memory-context-design-addendum.md) and [EK proposals](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/EVOLVING-KNOWLEDGE-REVIEW.md) retain their original identifiers. This grouping avoids creating a competing numbered specification.

| Priority | Requirements | Acceptance focus |
|---|---|---|
| Foundation | MC-01/02/03 | Final request bounds, repeated compaction and evidence reopening after restart |
| Shared work | MC-06/07/08/09/10 | Scope/trust preservation, sufficient handoffs, stale/duplicate merges and total budgets |
| Measurable operation | MC-11/12/16 | Retrieval gaps, later-task benefit/harm and bounded memory costs |
| Qualified evolving knowledge | MC-04/05/13/14; EK-01/02/03/04 | Applicability, temporal corrections, reversible updates, withdrawal and hypothetical branches |
| Procedures and assessment | EK-06/07/08 | Version-qualified recipes, distinct human/agent outcomes and held-out transfer |
| Selective graph revalidation | MC-15; EK-05 | Typed edges, alternative support, dependency coverage and conservative fallback |

MC-04/05/13/14/15 are conditional feature contracts. Fine-grained graph invalidation remains within the deferred HARNESS-09 boundary. The existing harness already calls for provenance, bounded inputs, untrusted worker/document handling and evaluation; proposed precision should not be misreported as wholly new functionality.

## Suggested sequence and open decisions

First resolve context, evidence and worker continuity contracts and establish baseline measurements. Then pilot episode retrieval against qualified lesson reuse. Add versioned recipes and separate agent probes only when the simpler comparison works. Evaluate selective dependency tracking after measuring unnecessary rechecks and stale-use failures.

Design review still needs to settle retention/deletion rules, project-to-project sharing, lesson qualification strength, acceptable unknown applicability, probe scheduling, and quality/cost thresholds. These are product and experiment decisions, not reasons to request approval for each routine retrieval. No automatic reflection after every action, new graph service, learned retention policy or model training is a default requirement.
