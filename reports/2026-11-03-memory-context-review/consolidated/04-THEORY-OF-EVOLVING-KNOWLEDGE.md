# A theory of evolving knowledge for Librarian

**Purpose:** explain the reasoning behind the proposed memory, context and learning architecture.

3 November 2026. This document synthesises the completed research. It is a conceptual explanation, not an adopted specification or a claim that the proposed features are implemented. Sources support particular mechanisms; the combined architecture is a design inference for Librarian.

## 1. The central problem: remembering what remains useful

A long-running project needs more than accurate recall. It needs to retain earlier evidence, understand why decisions were made, and recognise when that reasoning no longer applies. The project may change even when none of its earlier observations was wrong.

Consider a research project choosing a document-processing service. Early trials show that a hosted service is accurate and inexpensive, so the team recommends it. Later, the user introduces an offline-only requirement. The original measurements remain legitimate historical evidence, but the recommendation is no longer suitable. Deleting the earlier records loses useful knowledge; continuing to apply the recommendation violates the new requirement.

The proposed architecture therefore separates three questions:

1. What happened, and what evidence was available?
2. What is currently supported under the relevant assumptions?
3. What information should influence this particular decision?

These questions require related but distinct representations. A record of an experiment, a reusable lesson and a current recommendation are different objects. Treating them as interchangeable “memories” hides the transitions where mistakes occur.

## 2. Memory as history, knowledge and working context

The proposed design has three conceptual layers. They need not be separate databases.

| Layer | Purpose | Example |
|---|---|---|
| Evidence and history | Preserve observations, actions, sources and decisions under the applicable retention policy | The hosted-service trial, its input documents and measured results |
| Qualified knowledge | Express claims and methods with their supporting evidence and conditions | The service worked on these document types under this configuration |
| Working context | Select information needed for the current task | Offline-only requirement, eligible local methods and unresolved accuracy questions |

The first layer explains the past. The second makes explicit what can be reused. The third limits what occupies the agent's immediate attention.

This explains the value and limits of tiered memory. Working, reusable and archived tiers control placement and default exposure. They do not determine whether a claim is true. An archived result can still be correct; a frequently retrieved lesson can still be wrong. Moving an item into long-term memory changes its lifecycle, not its evidential strength.

For Librarian, these layers can build on existing Session history, evidence, application records, notes and derived indexes. The architectural requirement is a clear distinction between durable records and the views computed from them. A failed or outdated index should be rebuildable without losing the underlying evidence.

## 3. Time has two meanings

Bitemporal modelling distinguishes **when information applies** from **when the system learned it**. These are often different. The distinction is implemented explicitly in temporal database systems such as XTDB. [XTDB time model](https://docs.xtdb.com/about/time-in-xtdb.html).

Suppose a source changes on 10 October, but Librarian discovers that change on 15 October. A question about the source on 12 October has two possible meanings: its state according to today's information, or the state Librarian believed it had on that date. Keeping both times allows both questions to be answered.

Our proposed use adds another distinction: applicability to a project goal. The offline-only requirement might take effect today without changing any source fact. A recommendation can become inapplicable because the decision criteria changed, while its supporting experiment remains historically accurate.

The important operation is therefore a versioned change with a reason: correction, changed environment, new requirement, withdrawal or newly discovered evidence. Each has different consequences. A generic age-based decay score cannot represent all of them faithfully.

Historical access must still respect current access permissions and retention rules. Preserving history does not imply unlimited retention or permission to reveal it.

## 4. Knowledge is supported under assumptions

Assumption-based truth maintenance studies how conclusions depend on assumptions. Provenance algebra provides formal ways to express how evidence combines in defined query systems. These are foundations for tracking support, rather than tools that decide whether arbitrary natural-language statements are true. [Reiter and de Kleer](https://cdn.aaai.org/AAAI/1987/AAAI87-033.pdf); [Green, Karvounarakis and Tannen](https://web.cs.ucdavis.edu/~green/papers/pods07.pdf).

The proposed Librarian adaptation is to record sufficient support groups. For example:

`support for conclusion = (evidence A AND assumption B) OR evidence C`

A and B are jointly necessary for one justification. C represents a separate sufficient justification. If A becomes invalid, C may still support the conclusion. A simple graph traversal that invalidates everything connected to A would lose this distinction.

This is why typed relationships matter. “Mentions,” “derived from,” “requires,” “contradicts” and “independently supports” are different relations. A graph containing many links is not necessarily a useful model of justification.

Unknown support also needs its own meaning. If the source is unavailable, the system may be unable to confirm the conclusion without having evidence that it is false. A useful state is “requires recheck,” rather than an automatic true/false decision. Conflicting evidence should remain visible rather than be resolved by retrieval rank.

The formal benefit depends on accurately declared support. If an inferred edge is wrong or a dependency is missing, mathematically correct propagation can still produce a wrong practical result. The design must expose incomplete coverage and retain conservative fallback behaviour.

## 5. Staleness resembles incremental computation

Build systems offer a useful analogy: an output depends on inputs, and a relevant input change may require recomputation. Research on build systems separates the order of computation from the decision about whether recomputation is necessary. [Build Systems à la Carte](https://www.microsoft.com/en-us/research/publication/build-systems-la-carte/).

For Librarian, a synthesis, recommendation, recipe or assessment can be treated as a derived artifact with recorded dependencies. A changed source marks affected artifacts for re-evaluation. Unrelated results remain usable. This is selective revalidation.

The analogy has limits. A compiler can often reproduce an output from fixed inputs. A model-generated interpretation may vary between runs, and its dependencies may be partly implicit. Revalidation therefore needs a declared criterion: exact artifact equality, a numerical tolerance, satisfaction of a requirement, or a reviewed argument. Identical wording is not always the right test.

The proposal is to begin with dependencies that can be observed or declared reliably. Broader inferred dependency tracking should earn its complexity by reducing stale use or unnecessary rework. When dependency coverage is uncertain, a broader revision check remains appropriate.

## 6. Learning is a cycle of adaptation and testing

Case-based reasoning provides an established account of learning from experience: retrieve a relevant case, reuse or adapt it, evaluate and revise the solution, then retain useful experience. Evaluation is part of the cycle, not an optional step after storage. [Aamodt and Plaza, §3.3](https://www.iiia.csic.es/~enric/papers/Aamodt_1994_Case.pdf).

Librarian's application logs already provide the beginnings of cases. They can describe the problem, sources, action and outcome. The proposed addition is a distinction between the recorded case and a generalised lesson.

For example, “this configuration failed on these scanned documents” is an observation. “This tool cannot process scanned documents” is a much broader claim. The second does not follow automatically from the first. A qualified lesson should preserve the conditions, failure signature and limits of the observation, then be tested on unseen variants before broader reuse.

Modern work on incremental playbooks and reasoning memory offers evidence that external lessons can help particular agent tasks. It also identifies failure modes: poor reflection can produce harmful context, and model-generated success labels can be noisy. [ACE](https://arxiv.org/html/2510.04618v1); [ReasoningBank](https://arxiv.org/html/2509.25140v1).

This motivates localized, versioned changes. A correction should revise the relevant lesson while preserving unrelated knowledge and the original episode. It should be possible to explain what changed and restore an earlier view. Rewriting an entire project memory after every experience makes that accountability harder.

Here, “learning” means improving future behaviour through external records and procedures. It does not imply that the language model's weights have changed.

## 7. Context is a limited decision resource

An arbitrarily long project history cannot be compressed into a fixed-size representation without losing some distinctions. This follows from a simple counting argument: there are more possible unbounded histories than possible bounded representations.

The practical question is which distinctions must survive for the current task. Operative requirements, explicit exceptions, unresolved decisions and evidence identities should be represented deliberately. Optional background can be retrieved when needed. Omitted detail should remain recoverable where continuity is promised.

This gives two separate quality criteria:

- **Capacity correctness:** the complete request fits the route's available context, including instructions, tool schemas, history, evidence and output reserve.
- **Decision effectiveness:** the agent finds and uses the right information within that request.

The first can be enforced by accounting and dispatch rules, provided counting assumptions are valid. The second needs behavioural evaluation. Merely including an important constraint does not prove the model will follow it.

Retrieval ranking also serves a limited purpose. Lexical, vector and graph methods help locate candidate material. Their scores should not decide truth, permission or applicability. Those checks belong around retrieval and use. Graph-based summaries may help broad synthesis, while precise lookup may favour direct source retrieval; published GraphRAG results concern particular question types rather than universal superiority. [GraphRAG](https://arxiv.org/html/2404.16130v2).

## 8. Multiagent memory is a concurrency problem

Multiple agents can inspect different snapshots of a changing project. One worker might evaluate the hosted service while another explores local tools. If the user introduces offline-only operation before the first worker returns, its report can remain useful evidence without being eligible to close the current task.

The proposed handoff therefore includes the worker's input revision, evidence versions, scope, outcome and unresolved issues. Parent acceptance compares that result with current state. Arrival order does not establish authority.

Acceptance must also be atomic: checking a revision and then recording acceptance in an unrelated later step leaves room for a change between the two. A stable receipt identity prevents duplicate deliveries from becoming duplicate accepted work. Durable workflow documentation illustrates why completion reports can be lost and activities retried even after an external action succeeded. [Temporal activity semantics](https://docs.temporal.io/activity-definition).

Shared budgets have the same structure. Two workers can each observe enough remaining budget and collectively overspend unless reservation is coordinated. A useful invariant is:

`spent + outstanding reservations <= total allowance`

This holds only under explicit assumptions about atomic admission and bounded consumption. An uncertain completion should retain its reservation until reconciled. An estimate of provider cost is not an exact monetary guarantee.

These are suitable targets for state-machine specification and model checking. Such methods analyse transition rules; they do not establish the truth of a worker's research conclusions. [AWS experience with formal methods](https://lamport.azurewebsites.net/tla/formal-methods-amazon.pdf).

## 9. Replication recipes make procedural knowledge inspectable

A lesson explains what might work. A recipe specifies how to attempt it. A run receipt records what actually happened. Keeping these separate prevents a successful description from being mistaken for demonstrated execution.

A useful recipe identifies inputs, parameters, relevant environment versions, permitted operations, expected artifacts and verification criteria. Its qualification belongs to that version and those conditions. An environment change may require requalification even when the general method remains sensible.

Workflow standards such as CWL define dependency and input/output semantics; provenance packaging such as Workflow Run RO-Crate records execution context and products. These offer useful contracts without requiring Librarian to replace its workflow runtime. [CWL v1.2.1](https://www.commonwl.org/v1.2/Workflow.html); [Workflow Run RO-Crate](https://www.researchobject.org/workflow-run-crate/).

A replication DAG is consequently an execution view, not the whole knowledge base. Evidence relationships and learning prerequisites have other meanings and can contain cycles. A task graph's acyclic ordering does not establish scientific validity or permission to execute its nodes.

## 10. Flashcards test a different kind of knowledge

Human review, agent recall and procedural competence require different assessments. A person may benefit from spaced retrieval practice. An agent answering a question from retrieved notes may demonstrate retrieval and synthesis. Successfully executing a procedure demonstrates something else again.

The proposed agent probes should therefore identify the tested condition: closed-context recall, retrieval-assisted reasoning or action with verifiable results. Their source version and scoring criteria should be recorded, and held-out answers should remain outside ordinary memory.

For an agent using fixed model weights, elapsed calendar time alone does not establish biological-style forgetting. Failures may instead arise from source changes, model updates, retrieval selection, context interference or altered tools. Relevant-change triggers and periodic regression checks are therefore hypotheses worth testing. Human spaced-repetition schedules should not be assumed to solve agent-memory management.

## 11. What would demonstrate that the design works?

There are two independent obligations: maintaining correct system state and improving useful behaviour.

State invariants include rejecting stale closure, preserving scope, accepting each result once and retaining essential records during cache eviction. Formal models and implementation tests can examine these properties under stated assumptions. Passing a finite model is evidence about that model, not an unbounded proof of production software.

Behavioural improvement requires a controlled comparison. Give matched task streams the same current requirements and source access, then vary optional past experience: no prior-task memory, original episodes, tiered episodes or qualified lessons. Test later unseen tasks, introduce a goal or source change, and return to earlier work. Report both tasks helped and tasks harmed.

Measure current correctness, historical recall, adaptation delay, preservation of unaffected knowledge and total acquisition/retrieval/curation/checking cost. Chronological splits and hidden scoring prevent future answers from becoming part of the memory being evaluated. Replay research already shows that benefit depends on the model and amount of experience supplied. [LifelongAgentBench](https://arxiv.org/html/2505.11942v1).

The combined theory predicts that useful knowledge evolution requires preservation, conditional reuse and correction together. Storage without qualification accumulates unreliable guidance. Qualification without history loses explanation and recovery. History without selective context becomes expensive and difficult to use. Evaluation determines whether the chosen balance actually improves Librarian.

## Connection to the development proposals

| Theoretical principle | Proposed consequence |
|---|---|
| History and current use answer different questions | Versioned evidence plus a derived eligibility view |
| Applicability changes independently of truth | Separate goal revisions, freshness, scope and epistemic status |
| Conclusions can have alternative justifications | Typed support groups and selective revalidation |
| Experience needs adaptation and evaluation | Qualified lessons linked to application episodes |
| Context capacity is finite | Essential-state projection, bounded requests and evidence reopening |
| Workers operate on different snapshots | Revision-aware handoffs, atomic acceptance and shared reservations |
| Procedures need observable outcomes | Version-qualified recipes and run receipts |
| Recall and execution are different abilities | Separate human review, agent probes and action verification |
| Formal consistency does not imply useful reasoning | State verification alongside held-out behavioural evaluation |

The [research findings](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/formal-solutions/RESEARCH-FINDINGS.md) provide the evidence assessment, the [formal contracts](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/formal-solutions/FORMAL-CONTRACTS.md) state proposed predicates and assumptions, and the [tool register](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/formal-solutions/TOOL-DECISIONS.md) assesses implementation options. This document explains their common rationale; it introduces no new implementation mandate.
