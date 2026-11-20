# Use cases and open points

20 November 2026. Each use case below is written the plain way: who wants what, what should happen, and what the system actually did when we ran it. The flows themselves are in [WORKFLOW-MAP.md](WORKFLOW-MAP.md), which is generated from the code. Where a flow meets a use case, the gap is an open point.

Evidence is from runs on 20 November 2026 in Resource-Library, unless a row says otherwise.

## UC1. Make a folder of papers into library knowledge

| | |
|---|---|
| **Actor** | Owner |
| **Goal** | The papers in an attached folder become notes that search, research and reports can use |
| **Expected flow** | Attach → survey → folder decisions → queue → intake → approve → read (batch stages) → accept → Source note → paper graph |
| **What happened** | All 96 papers were read and enriched on 19–20 November, then stayed in staging. Nothing said that the last step, accepting them, was still owed. The research session found only catalogue cards, and its Judge phase had nothing to keep. |

**Open points**
- **OP1.** "Enriched but not accepted" has no owner and no alert. A staged backlog should show on the agenda, and the Lead should be told in its library context.
- **OP2.** With 17 graphs, every folder decision rebuilds every reviewed group, so a repository edited all day blocks decisions in an unrelated folder. This belongs to Geo-Grapher.

## UC2. Research a five-question brief across a corpus

| | |
|---|---|
| **Actor** | Owner (the Lead does the work) |
| **Goal** | One evidenced insight report per question |
| **Expected flow** | `explore`: frame → map → need (5 briefs) → search → judge → synthesise (5 reports) → check out |
| **What happened** | The run needed 9 back-end fixes and 4 budget extensions by a person. |

**Open points**
- **OP3.** One session holds one synthesis, but this brief needed five. The five reports share one "Together" and "Unknowns", which went stale after the redraft. A multi-question brief needs a synthesis per brief, or a session per question.
- **OP4.** Judge must decide every candidate. `research_round` brought in 82 candidates, mostly the library's own design notes and folder cards matching the search terms. They were all rejected for the same reason, and they used up the budget before the real papers were in.
- **OP5.** A phase's budget counts every visit to it. Synthesise reopened with one call left.
- **OP6.** In each phase, a refusal named the tool for the next step, but the bundle did not offer it: `resume_session`, then `request_budget`, then `paper_get_outline`. `phase_walk` checks gate tools, but not the tools a refusal names.

## UC3. Trust a report's claims

| | |
|---|---|
| **Actor** | Owner reading a report |
| **Goal** | Each claim is supported by the passage it cites, as written |
| **Expected flow** | Quote verified verbatim → claim reviewed against the passage around it → challenge goes back to the Lead → a person promotes |
| **What happened** | Reviews were off until today. When on, 9 of 12 held and 3 came back "unchecked" with no reason, all three quoting full PDF text. |

**Open points**
- **OP7.** Claim review was opt-in per library, so a garbled claim passed for days.
- **OP8.** Inside the Core, the review runs on the assigned Clerk, so the library's `route_review` is ignored.
- **OP9.** The cause of the "unchecked" reviews is unknown. Since `81914de` a failed review records its reason.

## UC4. Use the knowledge graphs as evidence

| | |
|---|---|
| **Actor** | The Lead |
| **Goal** | Find papers and code in the graphs, cite them, and say where a finding lands in our code |
| **What happened** | The Lead guessed the code graph label `librarian-v2`. `list_graphs` was too large to return. Sections could not be read without the outline. Graph evidence counted for nothing in Judge or in quotes. All four are fixed now (`1064cf0`, `9fd2fe9`). |

**Open points**
- **OP10.** Of the five redrafted reports, two located nothing in the code and one located it weakly. A report's "where it lands" is unchecked prose in the summary, not a claim with a cited entity.

## UC5. Know how far to trust a relation

| | |
|---|---|
| **Actor** | Owner, or an agent reading a graph |
| **Goal** | Each link (doc→code, claim→code, graph→graph) says what kind of relation it is and how sure we are of it |
| **Expected flow** | Enrichment proposes many-to-many candidate relations → distil → check each like a claim → score in a range → map to a trust tier |
| **What happened** | Doc-to-code links are word matches, and common words like "to" and "which" create them. 464 of 690 call edges are unresolved in a Parallax graph. Nothing types a claim-to-code relation. |

**Open points**
- **OP11.** The claim-checking architecture checks a claim's quote and sentence, but never a relation. A relation is not yet a claim the system can check.
- **OP12.** Trust tiers (gold, silver, bronze) exist, but nothing connects them to a relation's score.

## UC6. Reorganise a folder of PDFs into groups

| | |
|---|---|
| **Actor** | Owner |
| **Goal** | Move PDFs into topic groups without breaking what the library already knows about them |
| **What happened** | There is no flow for this. Folder review classifies folders and never moves anything. |

**Open points**
- **OP13.** A lightweight organisation workflow is needed. Steps:
  - propose groups;
  - the person approves the plan;
  - a dry run;
  - moves, each logged with undo;
  - re-survey only the touched folders.

## UC7. See the same data in a different model

| | |
|---|---|
| **Actor** | Owner |
| **Goal** | View what we hold as relational, ER, document, provenance or temporal data (owner's points A–F) without capturing new data |
| **What happened** | `docs/proposals/operators-and-views.md` defines the operators and the views. None of it is built, and it fell out of the order of work. |

**Open points**
- **OP14.** No pre-computed views are published for the query surface to compile against. Views have to come before operators.

## UC8. Compose work from actions

| | |
|---|---|
| **Actor** | Owner, or an orchestrating agent |
| **Goal** | Define a workflow by sequencing named actions with bound arguments, never by writing code |
| **What happened** | This exists: `workflows.py` provides YAML actions, workflows and pipelines that are validated, pinned and resumable. 13 workflows and 2 pipelines ship. |

**Open points**
- **OP15.** Two mechanisms do the same job: the 6 agent macros sequence tools in Python, beside the YAML workflows.
- **OP16.** The biggest flows are hard-coded state machines, not YAML: session phases, intake, batch stages and folder review. Their gates live as `if p == ...` branches in `Session.missing`, which is why a map has to be extracted by forcing phases. If each phase declared its gate and tools as data, the map, the tests and OP6's check would come for free.
