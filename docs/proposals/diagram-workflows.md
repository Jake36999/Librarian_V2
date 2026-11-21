# Diagram workflows: analyse a target through a lens and draw it as a reviewable model

**Status:** proposal (rank 5 in `docs/policy/README.md`). Owner direction, 20 November 2026. It extends workstream W2 (canvas service) of [the plan forward](plan-forward-2026-11.md), and runs beside it rather than through the main workflow. It becomes plan work only once the owner accepts a phase.

**Inputs:**
- the owner's systems-analysis course material (CO1605):
  - *Introduction to Systems Analysis* (week 1): problem versus symptom, stakeholders, scope, the 7-step process;
  - *UML: Use Case Diagrams* (week 2), with *include*, *extend* and granularity;
  - *Describing Use Cases with Activity Diagrams* (week 3);
  - *Writing Use Case Descriptions* (week 4);
  - *Testing Your App*;
- the owner's hand-drawn timeline map (Excalidraw, Timeline-mapping vault);
- [USE-CASES.md](../../reports/2026-11-20-workflow-map/USE-CASES.md) and the generated [WORKFLOW-MAP.md](../../reports/2026-11-20-workflow-map/WORKFLOW-MAP.md);
- the Librarian's lens packs (`standard/lens_packs/`).

## 1. The idea in one paragraph

The course gives four ways to review a system:
- a **use case diagram** shows who and what;
- an **activity diagram** shows how;
- a **written use case** shows exactly what happens, including when things go wrong;
- **test cases** show how we would know.

They are four projections of **one** model: actors, goals, steps, decisions with their guards, and outcomes. Read as **tree logic**, every path from the start to an end is a scenario. Every scenario except the happy path is an extension, and every scenario is a test.

So the proposal is:
- One **diagram spec**: a small, typed schema that an agent fills in about a target.
- Deterministic **validators** per diagram kind, which refuse a malformed spec instead of repairing it.
- **Renderers** to an Obsidian canvas, to Mermaid (for draw.io) and to tables.
- A **lens** per diagram kind that sets the analysis's perspective and tone.

The same machinery then draws the other "flat surface" models we need: timelines laid out left to right (like the owner's Chartists and Marx map), lineage, and relationship maps.

## 2. Before drawing: the analysis frame

The course's week 1 puts analysis before modelling, and the workflow keeps that order. Its 7-step process maps onto what the diagram workflow does:

| Course step | In the workflow |
|---|---|
| 1. Understand the situation | Name the target and its context (workflow step 1) |
| 2. Identify the stakeholders | List the actors, and each one's perspective (section 4) |
| 3. Investigate the current processes | Gather what can be derived: code, logs, notes (workflow step 3) |
| 4. Identify the problem and needs | Separate symptom from root cause, below |
| 5. Model the system | Draft and validate the spec (workflow steps 4–6) |
| 6. Define the requirements | Each open question and each `??` extension becomes a requirement or a decision |
| 7. Evaluate the possible change | Compare the diagram before and after, on the same lens |

**Problem, symptom, proposed solution.** Analysts work backwards ("why?") from what is visible to its cause, and do not start from a proposed fix. The 19–20 November run shows why:
- "The Judge phase has nothing to keep" was a **symptom**.
- "Let a graph citation count as evidence" was a **proposed solution**.
- "The papers were read but never accepted, and nothing said so" was the **root problem** (UC1 `11a`).

An analysis that skips this step draws the symptom. So every diagram run records a short *problem statement* first: the symptom observed, the "why?" chain, and the root cause where it is known. That statement is the diagram's caption.

**Scope.** The system boundary in a use case diagram is a decision, made early and recorded. What is inside is the Librarian's to change. What is outside (the model host, Geo-Grapher's internals, the Owner's own judgement) is drawn as an actor, never as an activity.

## 3. The four views, and how they check each other

| View | Question | Built from the spec | Its own validation (deterministic) |
|---|---|---|---|
| **Use case diagram** | Who interacts with the system, and what goals they pursue | actors, use cases, system boundary, `include`/`extend` | Actors sit outside the boundary. Each use case is named verb-first after the actor that starts it. Each `include` names an existing use case. Every primary actor starts at least one use case. |
| **Activity diagram** | How the process flows | start, activities, decisions with guards, merges, forks and joins, end; one swimlane per actor | Exactly one start, and at least one end. Every decision has at least two outgoing flows, each with a guard, and the guards together cover every case (an `else` counts). Every fork has its join. No node is unreachable. |
| **Written use case** | What exactly happens, step by step | the main success scenario is the guard-true path; each other path is an extension, numbered by the step it leaves (`4a1`, `4a2`); open questions | Each step names its actor ("who has the ball"). Each extension ends with "rejoin at N" or "the use case ends". An unfinished branch is marked `??` and listed as an open question. |
| **Test cases** | How we would know it works | one test per root-to-leaf path, plus boundary values for every guard on a number (at, just inside and just outside each limit; empty; the wrong type) | Every path has a test with an expected result. A test that cannot fail is flagged: "a successful test is one which fails". |

**Tree logic** joins them. Unfold the activity diagram from its start, and each decision becomes a branch:
- each leaf is an outcome (success, or "the use case ends");
- the number of leaves is the number of scenarios;
- each root-to-leaf path is one row in the test table and one extension in the written use case.

Any of the four can then be checked against the others with no model:
- every extension in the written use case has a path in the activity diagram;
- every decision has an extension for each of its non-success guards;
- every path has a test;
- every use case in the diagram has a written description.

A mismatch is reported as a flag, not fixed silently.

## 4. Actors

The course rule is that an actor is a role, not a person or a product, and need not be human. For the Librarian:

| Actor | Kind | Typically |
|---|---|---|
| Owner | human | primary |
| Outside agent (tier 0, through MCP) | model | primary |
| Lead (tier 1) | model | primary or secondary |
| Scribe and helper (tier 2) | model | secondary |
| Clerk (tier 3) | model | secondary |
| Core | the system | the system boundary itself |
| Geo-Grapher | system | secondary |
| Model host (DeepInfra, in our case) | external system | secondary. Its timeouts, refusals and unavailability are extensions in their own right, as in the 19–20 November runs. |

A model is **assigned** to a role (`docs/policy/`), so a diagram names the role, never the model; the model appears only in provenance.

**Stakeholders are wider than actors.** The course defines a stakeholder as anyone who affects, is affected by, or has an interest in the system, and stakeholders rarely agree. For the Librarian:

| Stakeholder | Perspective |
|---|---|
| The Owner as researcher | Wants findings that hold up |
| The Owner as budget holder | Wants cost bounded |
| The Lead | Needs the next step offered in its phase |
| The Clerk | Needs small, unambiguous tasks |
| A future reader of an offering | Needs provenance and labelled authorship |
| Third-party authors | Their work cited, never passed off as ours |

A diagram can be drawn from one stakeholder's perspective, and the spec records which, in `perspective`.

## 5. Graph kinds beyond UML

| Kind | Layout | Nodes | Edges | Example |
|---|---|---|---|---|
| `use_case` | actors left (primary) and right (secondary), boundary box in the middle | actor, use case, boundary | association, include, extend | The Librarian's UC1–UC8 |
| `activity` | top to bottom, one swimlane column per actor | start, activity, decision, merge, fork, join, end, note | control flow (with an optional guard) | UC2's research session |
| `decision_tree` | top to bottom, or left to right | root, decision, outcome | branch (with a guard) | UC3's claim review, unfolded |
| `timeline` | left to right by date, one lane per place or thread | event (date or span), period, place lane | influence, cause (each needs evidence), same-time marker | The owner's Chartists and Marx map |
| `lineage` | left to right, layered | item (original, conversion, reading, claim, note, offering) | derived from | One offering's claims back to their PDFs |
| `relationship` | stable clustered grid | entity | typed relation (UC5's vocabulary) | Papers and the code each one bears on |
| `er` | entities placed in clusters; relationships between them | entity, attribute (marked key, composite or multivalued), relationship | relationship with its cardinality (1:1, 1:N, M:N); generalisation | The views UC7 and W4 publish (semester 2: ER modelling, normalisation, integrity) |
| `stakeholder` | the system in the centre, stakeholders around it | stakeholder, interest | affects, is affected by, conflicts with | Who wants what from a library, and where they disagree |

The left-to-right kinds (`timeline`, `lineage`, and `activity` with swimlanes) are the "flat surface" models the owner asked for. Their meaning is in position: time, derivation or actor. So their layout is part of the kind, not a later choice.

## 6. The diagram spec

One schema for every kind; each kind constrains which node and edge kinds it allows. Written as YAML (or JSON) and stored beside what it describes.

```yaml
diagram: uc3-verify-claims          # stable id
kind: activity                       # use_case | activity | decision_tree | timeline | lineage | relationship
title: Verify a report's claims
target: {kind: use_case, ref: "reports/2026-11-20-workflow-map/USE-CASES.md#uc3"}
lens: [the-root-cause-lens, the-guard-completeness-lens]  # the lenses this analysis ran under
perspective: Owner                   # whose view the diagram takes (section 4)
problem:                             # the analysis frame (section 2); the diagram's caption
  symptom: "three reviews came back unchecked, with no reason"
  why: ["the Clerk's reply did not complete", "cause not yet known"]
  root: "??"                         # unknown until found; also listed as an open question (OP9)
lanes: [Lead, Core, Clerk]           # swimlanes (activity) or place/thread lanes (timeline)
nodes:
  - {id: s,  kind: start}
  - {id: a1, kind: activity, lane: Lead,  label: "submits a draft with its claims"}
  - {id: a2, kind: activity, lane: Core,  label: "validates each quote verbatim in its source"}
  - {id: d1, kind: decision, lane: Core,  label: "quote found?"}
  - {id: a3, kind: activity, lane: Clerk, label: "judges whether the passage supports the claim"}
  - {id: d2, kind: decision, lane: Clerk, label: "verdict"}
  - {id: a4, kind: activity, lane: Core,  label: "stages the report"}
  - {id: e1, kind: end, label: "report staged"}
  - {id: e2, kind: end, label: "draft refused; Lead resubmits"}
edges:
  - {from: s,  to: a1}
  - {from: a1, to: a2}
  - {from: a2, to: d1}
  - {from: d1, to: a3, guard: "found"}
  - {from: d1, to: e2, guard: "not found", ext: "2a"}
  - {from: a3, to: d2}
  - {from: d2, to: a4, guard: "holds"}
  - {from: d2, to: a1, guard: "fails or unreadable", ext: "4a/4b"}
  - {from: d2, to: a4, guard: "did not complete (recorded as unchecked)", ext: "4c"}
  - {from: a4, to: e1}
evidence:                            # optional, per node or edge: what supports it
  a2: ["src/resource_librarian/tools/sessions.py:_quote_found"]
provenance: {drafted_by: "role:clerk", lens_pack: modelling@<digest>, from: [USE-CASES.md], at: 2026-11-20}
```

Its fields:
- **`kind` and the per-kind vocabulary.** These make the validators possible. An unknown node kind is refused, never guessed.
- **`guard` on an edge leaving a decision.** This is what makes tree logic and test generation mechanical.
- **`ext`** links a path to its numbered extension in the written use case, so the cross-view checks have something to match.
- **`evidence`** lets a diagram drawn from research be checked like any other claim. It takes a note name, a `cite_as`, a code entity, or a file and line, and it ties into UC3 and W5.
- **`lane`, and for timelines `when`.** `when` is a date, a span, or `undated` with a reason. Position carries meaning here, so it is data, not drawing.

## 7. The lens for each kind: tone and perspective

The Librarian's lens shape already says how to look at something:
- `perspective`;
- `attends_to` and `deprioritizes`;
- `probes`;
- `catches`, the failure it prevents;
- `applies_when` and `not_when`;
- a `prompt_fragment`.

Packs are keyed by `materials` (what is analysed) and `tasks` (what is done with it). So a diagram kind is a **task**, the target's type is a **material**, and `lens_suggest` picks the lenses. A new standard pack, **`modelling`**, would hold one lens per kind plus a few shared ones. Drafts:

| Lens | Task (diagram kind) | Perspective and tone | It catches |
|---|---|---|---|
| The Root-Cause Lens | every kind, first | Work backwards from what is visible, asking "why?" until the cause is reached. Name the symptom, the cause and any proposed fix as three different things. Patient, not eager to fix. | Drawing the symptom; starting from a proposed solution; one "why" too few |
| The Conflicting-Perspectives Lens | `stakeholder`, `use_case` | There is rarely one version of what a system needs. Draw each stakeholder's goal, and where two goals pull apart. | One stakeholder's view presented as the requirement |
| The Granularity Lens | `use_case` | An oval is an actor's end goal. Steps belong in the activity diagram or the written use case. | A use case per form or button; a diagram too detailed to give the overview |
| The Boundary Lens | `use_case` | Who is outside the system, and what goal each actor came for. Goals, never steps. Name each use case after the actor who starts it. | A use case per screen or step; the system drawn as an actor; "Sell stock" where the actor is buying |
| The Who-Has-the-Ball Lens | written use case | Every step is one actor doing one thing toward the goal. Intent, not interface. Validate, don't check. | `if`/`else` inside the happy path; steps with no actor; UI talk |
| The Guard-Completeness Lens | `activity`, `decision_tree` | At every decision: what are all the ways this can go, and is each one drawn? Sceptical: assume the unusual case happens. | A decision with one way out; a missing `else`; a failure path that just stops |
| The Real-Concurrency Lens | `activity` | What actually runs at the same time: Clerk tasks in a pool, or a Core and its Geo-Grapher. What must wait for what? | Drawing as parallel what is serial, or the reverse; a fork with no join |
| The Every-Path-Is-a-Test Lens | tests | Adversarial: a test that cannot fail proves nothing. One test per path. Boundary values at every limit, plus empty input and the wrong type. | Only testing the happy path; tests without an expected result |
| The Time-Axis Lens | `timeline` | Place events on the axis by their dates and keep the lanes apart. Two things side by side are not cause and effect without evidence. Neutral historian's tone: no hindsight in the labels. | Undated events placed by guesswork; adjacency read as causation; a term from one period used for another |
| The Lineage Lens | `lineage` | Follow each item back to where it came from, and record who authored each hop (owner's, generated, third-party). | A claim with no path to an original; generated text labelled as the source |
| The Typed-Relation Lens | `relationship` | Each link says what kind of relation it is, and its evidence. Similarity may suggest a link but never asserts one. | Links made by shared words; untyped "related" everywhere |

Accepting a pack is a person's decision (`lens_pack_accept`), as now. The lens a diagram ran under is recorded in its `provenance`, so two diagrams of the same target under different lenses can be compared, not confused.

## 8. The workflow

This is a YAML pipeline over registered actions (`workflows.py`): no code between steps, and every step passes the registry's gates. After W1 it is an ordinary workflow like any other.

1. **The Owner (or an agent) names a target and a diagram kind.** A target is a use case, a workflow or pipeline, a session's log, a note or project, a graph, or a folder.
2. **The Core suggests lenses** for that kind and material (`lens_suggest`), and the chosen ones are adopted for the run.
3. **The Core gathers what can be derived without a model.**
   - Phases and gates come from the code (`workflow_map`'s walker).
   - Steps come from a YAML workflow.
   - Calls and refusals come from a session's log.
   - Entities and relations come from a graph query.
   - Dates come from notes' frontmatter.
4. **The Clerk or Lead drafts the spec** for what cannot be derived, under the lens's prompt fragment. A small, bounded task per lane or per decision, not one large free-form drawing.
5. **The Core validates the spec** with the kind's rules (section 3).
   - A failure goes back with the exact problems.
   - Repair is bounded to two attempts; after that the spec waits for a person.
   - Nothing is repaired silently. MARK XLVIII measured multi-branch model decomposition succeeding about 2 times in 6, which is why its validators refuse rather than repair.
6. **The Core checks the spec against the other views** of the same target that exist (section 3). Each mismatch becomes a flag.
7. **The Core renders the spec:**
   - an Obsidian canvas with the kind's layout profile (W2's canvas service);
   - Mermaid, for Obsidian and draw.io;
   - for activity diagrams, the decision tree and the test table.
8. **The Core stages a preview** with its content hash.
9. **The Owner approves**, and the Core writes the canvas through the safe, hash-checked commit (W2). Afterwards a person's moves on the canvas are kept: a node a person moved stays pinned.

When the target is our own code or workflows, steps 3 and 5 alone can produce the activity diagram and its tree with no model. `scripts/workflow_map.py` already does the gathering. The model is needed for the parts only judgement can fill: the extensions not yet observed, and the meaning of a timeline's links.

## 9. Phases

| Phase | What | Needs | Done when |
|---|---|---|---|
| **P0** | The spec schema; validators for `use_case`, `activity` and `decision_tree`; a Mermaid renderer; tree logic producing the test table | Nothing new: no model, no canvas service | UC1–UC4 in USE-CASES.md each have a hand-checked activity spec that passes its validator. The generated test table has one row per extension. A planted gap (a missing `else`) is caught. |
| **P1** | Canvas renderer with swimlane, tree and timeline layouts | W2's canvas layer, `src/resource_librarian/canvas/` (being built in the W2 session, 20 November 2026): the document, the layouts, the safe preview-and-commit write, and workflow ⇄ canvas. P1 targets it; nothing is copied from MARK a second time. | The UC2 activity canvas opens in Obsidian with lanes for Owner, Lead, Clerk, Core, Geo-Grapher and Model host, and a re-render keeps a node the Owner moved |
| **P2** | The `modelling` lens pack and the drafting workflow (steps 1–9) | W1 (workflows as data) is helpful but not required | A Clerk drafts an activity spec for a workflow that has no hand-written one. It validates within two repairs, and the Owner judges it correct. |
| **P3** | Cross-view consistency checks and generated test cases | P0 | Each mismatch between USE-CASES.md and its activity specs is listed as a flag, and each fixed mismatch clears its flag |
| **P4** | `timeline`, `lineage` and `relationship` kinds | P1; W5's relation vocabulary for `relationship` | The owner's Chartists and Marx map is redrawn from notes, each placed event carrying a date and evidence. An offering's lineage canvas runs from each claim to its PDF. |
| **P5** | Read a hand-drawn canvas back into a spec (round trip) | P1; MARK's canvas-compiler design (plan forward, Appendix A) | A hand-drawn activity canvas becomes a spec that validates. Unknown node kinds are refused, not guessed. |

P0 can start now: it touches no existing workflow and needs no model. P1 waits for W2's canvas layer. Until then, the prototype `render_spec.py` in `reports/2026-11-20-workflow-map/examples/ingestion/` writes canvases directly. It is an example, and P1 replaces its canvas output with calls to the canvas layer. P2–P5 can follow in any order after P1.

**The canvas layer's contract for P1**, as the W2 session described it on 20 November 2026:
- **Writes.** `service.preview(path, generated, profile=...)` then `service.commit(path, previewed)`, or `service.write()` for both at once. A refusal is `CANVAS_CONFLICT` from the tools, or `service.CanvasConflict` in Python.
- **Node ids.** Generated ids must start with `librarian-`; every other node is treated as the owner's and kept. The prototype's ids (`a1`, `d3`, `r1`) do not, so P1 prefixes them.
- **Existing canvases.** A canvas holding no `librarian-` node is never merged into without `adopt=True`.
- **Geometry.** `profile=None` keeps the renderer's own geometry, so a lane stays a column, and a node already on the canvas keeps its position. The named profiles (`plan`, `tasks`, `dependency`, `evidence`, `relationship`) come from MARK's layouts. In `dependency`, a node's `branch` field makes columns.
- **What survives.** Node metadata lives under `node["librarian"]`. Colours "1"–"6" and unknown fields survive.
- **YAML guard.** The layer's workflow compiler reads text not starting with `{` or `[` as a plain string, so a lane like "Doctor (Lead, tier 1)" stays whole. A mapping or list that parses with a bare null, or does not parse, is refused with "quote that value".

## 10. The oracle and the doctor: review kept apart from the work

Owner direction, 20 November 2026. The worked example's to-be ingestion ([INGESTION-TOBE.md](../../reports/2026-11-20-workflow-map/examples/ingestion/INGESTION-TOBE.md)) adds a **doctor**, UC-D: a tier-1 role that resolves failures arriving at mapped extension points, from a remedy catalogue. This section adds its counterpart, the **oracle**, and the rules that keep the two apart.

### 10.1 Three roles, three languages

| Role | What it does | What it never does | Its language |
|---|---|---|---|
| **Worker** (Lead, helper, Clerk) | Does the task | Judges whether its own work is done | "Do": *open, read, draft, queue* |
| **Oracle** | Judges a run's output against its specification | Executes or repairs anything; it is read-only | "Judge": *the spec says…, the evidence shows…, verdict…* |
| **Doctor** | Repairs a failure the oracle tagged, by a catalogued remedy within its blast radius | Judges completion; it hands back to the oracle to judge again | "Diagnose and remedy": *symptom, remedy, radius, rejoin* |

**The separation is semantic as much as technical.** A worker's prompt and an oracle's prompt use different words for different acts, so a review cannot drift into redoing the task.

The oracle and the doctor each treat themselves as **outside the system and outside each other**:
- they share no conversation with the worker or with each other;
- each sees only what its role is given: for the oracle, the specification, the artifact and the evidence;
- each has its own model assignment.

The Librarian already follows this for claim review: the reviewer sees one claim and its passage, never the draft (UC3).

**Why it matters, from experience.** A meta-reasoning loop run under the same task premise ("look at your work and correct it") has produced "corrections" that were themselves wrong. The reviewer shared the worker's framing, so it repeated the worker's assumptions. Two rules break that loop: separate context and separate assignment. The rule in 10.2 then keeps a review from becoming an order.

### 10.2 A verdict is a claim, not a fact

The oracle's output is a **claim, with its evidence**: "the success guarantee is not met: 3 of 96 notes are not findable (evidence: …)". It is never a command to the worker. Like every claim in the Librarian:
- it can be **rebutted**: the worker answers with evidence, and a person decides, as with a challenged claim in UC3;
- it is **checked itself**: `closure_audit.py` already re-checks each closure by an independent route, and counts a failed re-check as a *false closure*. The oracle's false-verdict rate is measured the same way.

Where a verdict goes depends on its severity:

| Verdict | Goes to | Because |
|---|---|---|
| Pass | The run's owner, as one notification; tier 0 is told only if it set the spec | Nothing to act on |
| Failure at a mapped extension point | **The doctor**, keyed by use case and extension | The extension says what this failure is and where it rejoins |
| Failure with no matching extension | **The tier-1 Lead** that owns the run, with the oracle's report and suggestion | A new shape: the Lead synthesises, and may draft a new remedy for UC-L |
| Critical: security, data loss, a boundary crossed, a person's decision | **Tier 0 and the Owner**, at once | Too consequential to route through a repair loop |

### 10.3 Who sets the oracle's specification

Every oracle has **exactly one specification owner**. Either:
- **tier 0 sets it for a tier-1 run**: the Owner, or a tier-0 agent acting for them, hands a Lead a task with its success guarantee; or
- **a tier-1 Lead sets it for a sub-run it delegates**, to a helper or the Clerk.

Never both for the same run.
- The spec records `set_by`.
- A tier-1 spec may only **narrow** a tier-0 parent's spec, never widen it. This is the same rule as tiers capping each other in the registry.

**The specification is the use case.** Its success guarantee is what the oracle checks, and its extensions are how a failure is labelled. A verdict of "failed at 14b" is exactly the key the doctor's catalogue is indexed by. So the use cases written for review (UC1–UC8) become both the oracle's specification and the doctor's index. Nothing new needs to be authored.

**This is what lets tier 0 step back.** Tier 0 sets the spec and the terminal fallback (escalate, keep what passed, or abort), then waits for one notification: a pass, a counted escalation, or the fallback taken. Between those, the oracle and the doctor run at tiers 1 and 2. Today tier 0 polls, as it did through every turn of the 19–20 November runs.

### 10.4 What exists already

Most of the oracle is the **audited** session purpose (`tools/audited.py`, `closure.py`, `closure_audit.py`), generalised from a session purpose into a role any workflow run can have:

| Oracle element | Already built |
|---|---|
| A spec the worker cannot set | `set_requirement`: a person's tool; a model proposes, never sets |
| Gate between stages | preflight admits a contract; execute only stages; reduce computes statuses from verifier results alone |
| Deterministic checks first | 12 verifiers: `schema.valid`, `quote.located`, `citation.resolves`, `index.findable`, `target.diff_clean`, `claim_run.passed`, `arithmetic.reproduces`, `evidence.integrity`, `coverage.status`, `boundary.staged`, `packet.citation_resolves`, `review.llm` |
| A model judge, with its context kept apart | `review.llm`; the claim review sees the claim and its passage, never the draft |
| The oracle checking itself | `closure_audit.py`: independent re-checks; false closures counted |
| Bounded loops | `AUDITED_STALL_LIMIT` (8) and `AUDITED_MAX_ROUNDS` (50); phase budgets; the spend ceiling |
| Human oracle | `accept_artifact`; person-only promotion |

**Missing:**
- attaching an oracle to any workflow or pipeline run (W1);
- reading the success guarantee and the extensions from the use case's spec;
- the one-shot hand-back to whoever set the spec;
- the `set_by` rule.

### 10.5 The slot for security and correctness checks

The chain from a change to its review is where security and correctness workflows belong. Each link uses something planned or built:

1. **A change lands**: code, a document, a library record.
2. **The Core computes its blast radius** (W3): dependants through the code graph, documentation mentions, lineage and bridges.
3. **The Core runs only the tests and checks inside that radius.**
   - Deterministic first: tests, AST checks, schema validators.
   - Security checks:
     - secrets in the diff, using the existing credential-path rules;
     - changes to a tool's tier, effect or permission (the access declarations already fingerprint these);
     - new outbound calls;
     - paths that escape their containment;
     - text that reads as instructions to a model, using the existing injection markers.
4. **A failure goes to the oracle**, which writes a report and a suggestion: a claim, with evidence (10.2).
5. **Tier-2 helpers scout the blast zone**, read-only: what else reaches the failing point, and what changed nearby.
6. **The tier-1 Lead synthesises the findings** and presents a solution.
7. **The doctor applies it** if the solution is a catalogued remedy within its scope. If not, the Owner decides, and a critical finding goes straight to tier 0 and the Owner (10.2).

As an activity diagram this is the same shape as the to-be ingestion: one main path, and every failure point a reference (to UC-O, the oracle, or UC-D, the doctor) with its outcomes checked by the renderer.

### 10.6 A short, fixed list of models for each role

To keep the oracle and the doctor predictable, **each role gets a short, fixed list of models it may be assigned**, one or two each, qualified for that role and measured in it. Never "any capable model".

**Rule.** For any single run, the oracle's model is a different assignment from the worker's, and from the doctor's. The Core refuses a run whose oracle would grade its own worker. Assignments stay revisable, and a model is never bound to a role.

**Starting point.** The library's existing review route (`route_review`, GLM-5.3 in Resource-Library) is a natural first oracle candidate, distinct from the Lead and the Clerk. Inside the Core it is not yet honoured (OP8), so fixing that comes first.

### 10.7 How both grow

Both roles keep provenance:
- **The oracle's verdicts** record the spec's digest, the verifiers run, and the evidence.
- **The doctor's cases** record the symptom, the remedy and the result.

That history is what each learns from.
- The oracle's checks are recalibrated against its measured false-verdict rate.
- The doctor's catalogue grows through UC-L, one entry the Owner accepted at a time.
- The blast radius bounds what either may touch, so their influence grows only as far as their record and declared scope allow.

### 10.8 Phases

| Phase | What | Needs | Done when |
|---|---|---|---|
| **P6** | UC-O as a spec, beside UC-D and UC-L. The to-be ingestion's final verification (step 19) becomes an oracle call, with its outcomes checked by the renderer. | P0 | All specs render with 0 problems and 0 flags. The ingestion's lane load shows no tier-0 node outside the hand-over and the hand-back. |
| **P7** | The oracle as a role on any workflow run: the spec comes from the use case, `set_by` and narrowing are enforced, a separate assignment is required, and the result comes back as one notification | W1; the audited harness's verifiers | A tier-1 ingestion run with a tier-0-set spec reports exactly once to tier 0, and a planted failure reaches the doctor keyed by its extension |
| **P8** | The change → blast radius → tests → oracle → scouting → solution chain, with the security checks in 10.5 | W3; P7 | A planted secret and a planted tier change are each caught, reported as a claim, and routed as critical |

## 11. Upward composition: actions, workflows, pipelines, sprints

Owner direction, 21 November 2026, after a discussion with Gemini. That discussion's summary is weighed below: claims checked against the code or the files are marked as such, and the rest is proposal.

### 11.1 Processes and parent processes

Every unit of work is a **process**, and there are four kinds, in this order:

**action → workflow → pipeline → sprint**

A process is built from processes that come earlier in the order, and the process built is their **parent process**: an action's parent process is a workflow, a workflow's is a pipeline, and a pipeline's is a sprint. Any process may also be a component *of* a component: an action may sit directly in a pipeline or a sprint, not only inside a workflow. Nothing is ever built from a process later in the order, so a pipeline is never a component of an action. That is what keeps composition free of loops.

| Process | What it is | Its components | Examples |
|---|---|---|---|
| **Action** (L0) | The smallest defined step an agent follows to complete a task. It is carried out by one registered tool, which may be one bounded model call. | None | open a file; read its functions; describe what a function does; write a summary (owner's examples, deliberately granular). In the Librarian: `staging_list`, `deep_read`, `decide`. |
| **Workflow** (L1) | A named sequence of actions, invoked as one step | Actions, and workflows without a cycle | `review`, `scout`; shipped: `deep-read-staged`, `review-item`, `flag-sensitive`; the doctor's remedies R1–R6 |
| **Pipeline** (L2) | A sequence of workflows, with routing, concurrency and spend gates, that may add actions of its own or skip steps of its workflows | Workflows and actions | the ingestion; shipped: `clear-enrichment-backlog`, `weekly-review` |
| **Sprint** (L3) | Pipelines sequenced toward one Owner objective | Pipelines, workflows and actions | Nothing yet; see below |

**Granularity is a choice made by which process is invoked.** To review a file, an agent can:
- invoke the `review` workflow as one step;
- or, where more granularity is wanted, as in ingestion, run its actions one by one (open, read the functions, describe each, summarise);
- or use a workflow composed for that purpose.

The workflow is the same either way; only the level it is invoked at changes.

**New processes are built from existing ones.**
- A pipeline is made from existing workflows, adding new actions or skipping steps as that pipeline defines.
- When a new action is defined, or a new use of existing actions is found, it becomes a new workflow. Those workflows, in different orders and mixed with single actions for the niche features of an expected result, become new pipelines.

The blocks are built like Lego, with a vertical axis that glues them together: what a block is made of defines what it is.

**What the structure lets anyone infer without reading further:**
- a pipeline contains at least one workflow;
- a workflow contains one or more actions, usually several;
- so a sprint's actions can be found from its pipelines' manifests (11.7) without opening a single action.

**No rush for sprints.** The design benefit is definition: room above pipelines for planning how agents are orchestrated, without forcing work into pipelines too narrow to hold it. Sprints are named now so they can be planned with; they need not be built yet.

**Most of this exists already** (verified): `workflows.py` defines actions, workflows and pipelines in YAML.
- It ships 19 workflows and 2 pipelines (as of 21 November 2026), including the agent macros, which were folded into YAML workflows in `f61e30c`, so one step-sequencing mechanism remains.
- It validates each process before it is saved.
- `closure()` finds every process a run can reach and refuses a cycle.
- A run is pinned to the exact text of each of those processes.
- Every step goes through the registry, so every gate applies.

New:
- sprints;
- the order made an explicit, enforced rule;
- the **repertoire**, the one place accepted processes are kept and promoted;
- **manifests** (11.7);
- expressing the coded flows (session phases, intake, batch stages) as pipelines (OP16).

The owner's design was the origin of the orchestration the Librarian already runs, but it has not been carried through everywhere as the system was built. OP16 is where it stopped.

### 11.2 Composing and promoting a process (UC-C), as an activity diagram

The order and promotion are drawn as an activity diagram in [compose.spec.yaml](../../reports/2026-11-20-workflow-map/examples/ingestion/compose.spec.yaml), with [its generated views](../../reports/2026-11-20-workflow-map/examples/ingestion/compose.views.md) and [canvas](../../reports/2026-11-20-workflow-map/examples/ingestion/compose.canvas). It renders with 0 problems and 0 flags.

**Main success scenario** (generated):
1. The Lead needs a capability its task calls for.
2. The Core searches the repertoire for an accepted process that covers it, lowest layer first.
3. The Lead drafts a process at the layer the task needs, from accepted processes as its components.
4. The Core validates the draft: schema, references, arguments and outputs.
5. The Core validates the layer rule: components from earlier layers, or its own layer without a cycle.
6. The Core compiles the draft's manifest: its actions in order, their declared effects, and the blast radius.
7. The Oracle dry-runs the draft against its specification: Tier A checks first, then a Tier B review.
8. The Core runs the process for the task, pinned to its text.
9. The Lead proposes promoting the process into the repertoire.
10. The Core checks the proposal against the repertoire and puts it on the Owner's agenda.
11. The Owner accepts the process into the repertoire.
12. The Core pins the process's digest and records its manifest and provenance.

**Extensions:**
- **2a.** An accepted process already covers it. It is used, and the use case ends *reused*: composition starts from what exists.
- **4a.** The draft is invalid. The Lead revises it from the named problems, at most twice; after that the case escalates.
- **5a.** The draft uses a later layer, or makes a cycle. The Lead recomposes it from processes of earlier layers.
- **6a.** The manifest is outside the parent process's mandate. Tier 0 puts the decision to the Owner, who approves it or pauses the composition.
- **7a.** The oracle's specification is not met. The Lead revises from the oracle's report, within the same two-revision bound.
- **10a.** The draft duplicates an accepted process. The existing one is used (*reused*).
- **11a.** The Owner declines it. It ran for this task and is not kept (*used once*).

**Tier-0 turns: 0** on the main success scenario. Tier 0 appears only to relay a decision to the Owner (6a) or to take over an escalation.

**The same promotion serves every process.** A doctor's remedy (a workflow) and a learned remedy from UC-L are promoted exactly this way: same validators, same order, same Owner acceptance and digest pinning. Recovery uses the same grammar as normal work, so it needs no separate execution engine.

### 11.3 What the order makes possible

- **A blast radius computed, not estimated.** If every action declared the state it can change, a process's blast radius would be the union of its actions' declared effects. UC-D's step 3 and UC-C's step 6 would then need no model.
  - Today an action declares its effect (read or write), whether it reaches outside the library, whether it is idempotent, and its access fingerprint.
  - Replace-and-multi-target writes also declare their targets before they run (`WriteIntent`, CORE-05A).
  - Missing: a declared list of the *state classes* each action may change. That is a prerequisite for W3.
- **Roles defined by what they are given, not by persuasion.** A role is its mandate plus the subset of the repertoire **mounted** for it. This is what the phase bundles already do: a phase offers only its tools, and the registry refuses the rest. It replaces prose "forbidden" lists (11.5).
  - Gemini's summary says roles "do not require separate prompt architectures". That holds for *what* a role can do. A role still needs its own language (10.1): what it may *do* is set by its mount, how it *speaks* by its mandate.
- **Dynamic composition, promoted back.** An orchestrating agent composes a process for a new task at whatever layer it needs (UC-C), and a process that proves itself is promoted, so the repertoire grows with use.

### 11.4 The fault register: a Boolean signature for the doctor and the oracle

Gemini proposed recording each failure as a fixed set of Boolean faults, not a weighted score. Adopted here for **system-level invariants only**, as four bits in strict order of priority:

| Bit | Name | Set when | Example |
|---|---|---|---|
| b3 | `F_ESC` | A failure is escalated to tier 0 unresolved | Any escalated path in the to-be diagrams |
| b2 | `F_ATTEST` | An attestation or policy invariant is breached | An agent's acceptance recorded as `attested_by: person` (finding F2) |
| b1 | `F_BLAST` | A remedy exceeds its declared blast radius | Re-surveying one stale root rebuilds every group (OP2) |
| b0 | `F_SYMPTOM` | The extension point's check still fails after a remedy | UC-D steps 5–6 failing |

The doctor evaluates each remedy attempt with three checks on the register before (`before`) and after (`after`):
- **Regression:** `after & ~before != 0`, meaning the remedy set a new fault. Roll it back at once by its compensation step (UC-D `x4`).
- **Progress:** no new fault, and at least one fault cleared (`before & ~after != 0`).
- **Circuit breaker:** `mask & 0b1110 != 0`. An escalation, attestation or blast-radius fault stops automation and goes to tier 0 and the Owner, as section 10.2 routes a critical verdict.

The case record in UC-D step 7 stores `(use case, extension, before, remedy, after)`. The difference `before ^ after` is what a remedy measurably fixed, which is the evidence its trust tier (bronze, silver, gold) is earned from.

**A remedy may be searched for only safely.** Trying several candidate remedies needs either an isolated dry run, or a verified compensation step behind the scope check (UC-D `d2`), so a failed attempt leaves nothing behind.

**Symptom-masking is the risk this does not remove.** A fix can clear a fault without reaching its cause. Two things guard against it:
- the Root-Cause lens, at the analysis frame;
- the Owner's acceptance in UC-L, before a remedy joins the catalogue.

The 20 November run has an example. `1064cf0`, graph citations as evidence, was a sound proposed solution, but it treated the research-side symptom. The root, an unowned hand-off in staging (OP1), is still open.

### 11.5 Audit: the target standard against the legacy harness

Gemini compared the target against an earlier harness, `E:\Aletheia_project\AI_onboarding\40_pipelines\`. Spot-checked: the five pipeline files it names exist, `mock_runner_master_pipeline.yaml` does give the rule "SSE > 0.02" to an `llm_reasoning` step, and `mock_runner_governance.yaml` does rely on a prose `forbidden:` list. The rest of the table was not checked file by file.

| Criterion | Avoid (the legacy pattern) | Enforce (the target) |
|---|---|---|
| What YAML holds | Prose instructions, and English test rules, written as YAML | Declarative processes: typed `inputs`, named components, explicit `from:` bindings (as in `clear-enrichment-backlog.yaml`) |
| What a model decides | Open-ended reasoning steps doing checks code can do (a numeric threshold) | A closed choice between named options; every check code can make runs as code first |
| How roles are limited | Persuasive "forbidden" lists | The role's mount: a role sees, and composes from, only its subset of the repertoire |
| Structure | Flat scripts mixing scraping, linting, running and reasoning | The order (11.1), with typed `outputs` at every parent-process boundary |
| References | Silent drift to undefined names or empty files | Validation before any run: every reference, outcome edge, refusal code and target exists |
| The repertoire's upkeep | Duplicate and divergent copies | Promotion only through UC-C: validated, accepted by the Owner, digest-pinned, its trust measured |

### 11.6 Two open decisions

1. **How many fault bits?** Proposal: keep the register **universal and small**, the four system-level bits above.
   - Faults specific to one use case are already named exactly by its **extension ids** (`13b`, `18a`), so they need no bits of their own.
   - Generating bits per spec from its decision nodes would make registers incomparable across use cases.
2. **Behaviour spec and execution YAML: one schema or two?** Proposal: keep them **separate and linked** for now.
   - The `.spec.yaml` describes behaviour, including people and model hosts, which no process file can.
   - The process YAML (`workflows.py`) holds only registered actions and the processes built from them.
   - Each process declares `implements: <spec id>`. A parity check then confirms that every automated step in the spec has its step in the process, and that every refusal the spec names exists.
   - Compiling both from one schema can be decided once both exist side by side.

### 11.7 Process manifests: check a component without opening it

**The problem.** To decide whether a process may become a component of a parent process, a model today has to open the process, then each of its components, then each action, to see what it does. Most of that is reading it should not need to do.

**The proposal.** Each process gets a compiled **manifest**. It is generated from the process's YAML and the registry, never written by hand, and it lists:
- the **component tree**: which processes it is made of, each with its kind and layer;
- **every action it can take, in order**, with its place (the step path, and the route branch it sits on) and each action's declared properties: registry tier, effect, whether it reaches outside the library, idempotence, whether it returns content, and its access fingerprint;
- a **roll-up**: the number of action steps, the distinct actions, the highest tier, the set of effects, whether any action reaches outside the library, which steps are routed by a model, and any action that is not registered;
- the process's **digest**, the same one a run pins, so a manifest always describes exactly one text.

A parent process states its **mandate**: the highest tier, the effects and outside access it allows, a deny list, and its own layer. The suitability check compares the mandate with the component's manifest alone, and names each action that does not fit, with its step path. Only the processes that pass are integrated, so a model never reads an action file to find out it was unsuitable.

**Format.** The process stays **YAML**: people and agents write it. The manifest is **JSON**: it is compiled, it is validated against a JSON Schema, and it is read by code and models but never edited. Keeping them apart means a manifest cannot drift from its process: it is rebuilt whenever the process's digest changes.

**Prototype, run on 21 November 2026** ([examples/manifests/](../../reports/2026-11-20-workflow-map/examples/manifests/)). `build_manifest.py` compiled the shipped pipeline `clear-enrichment-backlog`:
- **Structure:** L2, 3 action steps, 3 distinct actions, one model-routed step.
- **Properties:** highest tier `contribute`, effect `write`, and it reaches outside the library.
- **Read-only parent** (no writes, no outside access): refused from the manifest alone, with 5 named problems. `intake_run` and `staging_review` write and reach outside the library, and `staging_flag` writes.
- **Ingestion sprint** (writes and outside access allowed): suitable.

**What exists and what is missing.** `closure()` already computes the component tree, and refuses cycles. `granted_actions()` already computes the set of actions a run can call, for what a person authorises by starting it. Missing:
- the actions **in order**, with their branches;
- the **roll-up** of declared properties;
- a **saved, schema-checked manifest** per process;
- the **mandate check** at integration time;
- declared state classes per action (11.3), so the manifest's blast radius is complete.

The manifest is also what makes sprints cheap to design. A sprint's actions are the union of its pipelines' manifests, so planning a sprint means reading a few manifests, not every file beneath them.

## 12. Terminology

At this scale a word must mean one thing. This section is binding for this proposal, its specs and its diagrams. [docs/terminology.md](../terminology.md) is the authority above it: where a term is defined there, its definition is used and noted here, and the terms below that are new should be added there once the owner accepts them.

### 12.1 Composition

| Term | Means | Is not |
|---|---|---|
| **Process** | Any one action, workflow, pipeline or sprint | A run, which executes a pinned copy of a process, or a session |
| **Action** | The smallest defined step an agent follows to complete a task, carried out by one registered tool (possibly one bounded model call) | A step, which is one use of an action inside a process |
| **Workflow** | A named sequence of actions (and workflows, without a cycle), invoked as one step | A session, or a pipeline |
| **Pipeline** | A sequence of workflows and actions, with routing, concurrency and spend gates | A sprint, or a batch run |
| **Sprint** | A sequence of pipelines toward one Owner objective, with its own success guarantee and budget | A session's phase, or a calendar period |
| **Order** | action → workflow → pipeline → sprint. A process is built only from processes earlier in the order (or of its own kind, without a cycle), and never from a later one. | An agent tier, registry tier or trust tier |
| **Layer** | A process's position in the order: L0 action, L1 workflow, L2 pipeline, L3 sprint | An agent tier, registry tier, trust tier, or Tier A/B audit |
| **Component** | A process used inside another process | A step, which is one use of a component at one place |
| **Parent process** | The process made when processes are combined: an action's parent process is a workflow, a workflow's a pipeline, a pipeline's a sprint. Used whether the parent exists yet or is being designed. | The process that called it at run time (a run has a caller; a process has parents) |
| **Definition** | The YAML text of a process | The process itself |
| **Manifest** | A process's compiled description (JSON): component tree, actions in order with their declared properties, roll-up, digest. Generated, never edited. | The process's YAML, or its spec |
| **Mandate** | What a parent process allows its components: highest tier, effects, outside access, deny list | A role's permissions (registry tier) |
| **Repertoire** | The set of accepted processes, shipped and promoted, that new work is composed from. Not called a "library", since a library is a vault, nor a "catalogue", since that is the doctor's list of remedies. | The library, or the remedy catalogue |
| **Mount** | The subset of the repertoire a role may use | A role's permissions, or its prompt |
| **Promote** (a process) | Add it to the repertoire through UC-C: validated, accepted by the Owner, digest-pinned | Promoting an *offering* into the vault (a separate act) |

### 12.2 Use cases and diagrams

| Term | Means | Is not |
|---|---|---|
| **Use case** | An actor's goal and everything that can happen pursuing it, written in the nine-field template | A diagram, or a process |
| **Spec** (diagram spec) | The `.spec.yaml` describing one use case's behaviour: lanes, typed nodes, guarded edges, outcomes | A process's definition (11.6) |
| **Main success scenario** | The numbered happy path: one actor per step, "Actor + verb + object" | A test, or a run |
| **Extension** | A path leaving the main success scenario at a numbered step (`13b`): its condition is line 1, its steps follow, and it ends with "rejoin at N" or "the use case ends" | An error code. An extension id is the *place*; a refusal code is the *shape*. |
| **Outcome** | How a use case ends: `success`, `resolved`, `learned`; neutral `reused` and `used once`; or `paused`, `declined`, `escalated` | An execution outcome (docs/terminology.md: completed, refused, failed…), which describes one attempt |
| **Reference** (`ref`) | A node that calls another use case (UML's call-behaviour action), handling each of its outcomes | A link, or a wikilink |
| **Lane** | A column of an activity diagram holding one actor's steps | A role slot, or a model |
| **Turn** (tier-0 turn) | One return of control to tier 0. Consecutive tier-0 steps are one turn. Grades: 2 ideal, 3 expected, 4 rusty, 5–10 bad, more "might as well have done it themselves" | A model call, or a chat turn |

### 12.3 Actors and roles

| Term | Means | Is not |
|---|---|---|
| **Owner** | The person who runs the library; the only actor whose decisions are reserved | Tier 0 |
| **Agent tier** (from docs/terminology.md) | 0 = an outside agent (Claude Code, Codex…); 1 = Lead; 2 = Scribe and research helper; 3 = Clerk | Registry tier (consult, contribute, curate), trust tier (gold, silver, bronze), layer (L0–L3), or Tier A/B audit |
| **Oracle** | The actor that judges a run's output against its specification and never executes or repairs. Its verdict is a claim, with evidence. | The worker, the doctor, or a Tier B audit on its own (an oracle runs Tier A before Tier B) |
| **Doctor** | The actor that repairs a failure at a mapped extension point, by a catalogued remedy within its blast radius, then hands back to the oracle | The oracle, or tier 0 |
| **Tier A / Tier B audit** (from docs/terminology.md) | Tier A: deterministic, target-scoped checks. Tier B: a read-only model assessment. An oracle runs Tier A first and Tier B only after it passes. Gemini's "hard oracle" and "soft oracle" are these. | Agent tiers |
| **Assign** (from docs/terminology.md) | Choose the route a role uses; always revisable. Never "bind". The oracle's and doctor's assignments must differ from the worker's on the same run. | Bind |

### 12.4 Failure handling

| Term | Means | Is not |
|---|---|---|
| **Symptom** | What is observed at an extension point: refusal code, shape, evidence | The root cause |
| **Root cause** | The answer at the end of the "why?" chain (section 2) | A proposed solution |
| **Remedy** | A workflow in the doctor's catalogue, keyed by use case, extension and symptom, with declared scope and rejoin | A fix written for one case, or a code change (that escalates) |
| **Catalogue** (remedy catalogue) | The doctor's accepted remedies and their case history | The repertoire, which holds every process, or the model catalogue |
| **Blast radius** | What a change or a remedy can touch: computed as the union of its actions' declared effects, and followed through dependants, lineage and bridges | A guess |
| **Escalation** | A failure handed back to tier 0 unresolved. It is a counted failure of the use case (`F_ESC`). | A pause for the Owner's decision |
| **Fault register** | The four Boolean system faults (11.4) recorded before and after a remedy | A score, or a confidence |
| **Verdict** | The oracle's judgement: a claim with its evidence, which can be rebutted and is itself re-checked | A fact, or an instruction to the worker |

## 13. Risks and limits

- **Model reliability.** Drafting a whole diagram in one call is unreliable. The design keeps model tasks small (per lane, per decision) and leans on deterministic gathering and validators.
- **Drift from the code.** A spec of our own system can go stale. Wherever a spec can be derived from code, it is regenerated, not edited (as with WORKFLOW-MAP).
- **Layout clutter.** Hubs with dozens of links become unreadable. The `relationship` kind needs W8's link node (the "knot on the string") before it scales.
- **Causation in timelines.** Placing two events side by side invites a reading the evidence may not support. Influence and cause edges require evidence, and the Time-Axis Lens names the trap.
- **Scope.** This draws and checks models; it does not run them. Executing a drawn workflow is W2's canvas → workflow compiler.

## 14. Decisions for the owner

1. Accept P0 to start now, beside the main work.
2. The `modelling` lens pack. Draft it from section 7, then accept it as a person's decision.
3. Where diagram specs live. Proposal:
   - specs of the Librarian itself under `reports/<date>-workflow-map/specs/`, regenerated from code where possible;
   - specs a library makes about its own material in that library's vault, as notes with their canvases beside them.
4. The oracle and the doctor (section 10):
   - accept P6 (specs only, no code) to follow P0;
   - choose the fixed list of models for the oracle and doctor roles. The first oracle candidate, the library's review route, needs OP8 fixed first.
5. Upward composition (section 11):
   - the order as written: action → workflow → pipeline → sprint, each process built from earlier ones (or its own kind without a cycle), never later ones;
   - **repertoire** as the name for the set of accepted processes;
   - the two open decisions in 11.6: a universal four-bit fault register, and separate but linked spec and process files;
   - manifests (11.7): YAML for the process, compiled JSON for its manifest, and the mandate check before any process becomes a component of a parent process.
6. The terms in section 12 that are new (process through promote, outcome, reference, turn, oracle, doctor, remedy, fault register, verdict) to be added to `docs/terminology.md` once accepted.
