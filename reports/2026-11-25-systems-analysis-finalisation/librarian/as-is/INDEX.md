# Librarian — as-is pack

How the Librarian works today, drawn from the code at d9435e1 and the runs of 19-21 November. Each use case records its weaknesses and gaps in weaknesses.yaml, and the to-be pack names the element that handles each one. Swim-lane canvases are no longer produced (D1).

[Use case diagram](use-case-diagram.md) · [Composition](composition.md) · [States](states.md) · [Canvas](index.canvas)

## Use cases

| Id | Use case | Status | Nodes | Steps | Paths | Tier-0 turns (main / worst) | Weaknesses | Handles | Errors | Warnings |
|---|---|---|---|---|---|---|---|---|---|---|
| UC1.3 | [acceptance](views/acceptance.views.md) | `IMPLEMENTED_VERIFIED` | 10 | 3 | 5 | — | 4 | 0 | 0 | 0 |
| UC0.2 | [activation-external-project](views/activation-external-project.views.md) | `IMPLEMENTED_VERIFIED` | 14 | 4 | 5 | 2 / 2 | 3 | 0 | 0 | 0 |
| UC0 | [activation](views/activation.views.md) | `IMPLEMENTED_VERIFIED` | 36 | 8 | 36 | 0 / 2 | 5 | 0 | 0 | 0 |
| UC1b | [batch-enrichment](views/batch-enrichment.views.md) | `IMPLEMENTED_VERIFIED` | 29 | 5 | 16 | 1 / 1 | 2 | 0 | 0 | 0 |
| UC4 | [cite-graph](views/cite-graph.views.md) | `IMPLEMENTED_OBSERVED` | 14 | 7 | 3 | — | 2 | 0 | 0 | 0 |
| UC8 | [compose](views/compose.views.md) | `IMPLEMENTED_VERIFIED` | 17 | 6 | 7 | 1 / 1 | 1 | 0 | 0 | 0 |
| UC-D | [doctor](views/doctor.views.md) | `IMPLEMENTED_OBSERVED` | 15 | 6 | 5 | 1 / 2 | 5 | 0 | 0 | 0 |
| UC1.1 | [folder-review](views/folder-review.views.md) | `IMPLEMENTED_VERIFIED` | 20 | 5 | 9 | — | 5 | 0 | 0 | 0 |
| UC1 | [ingestion](views/ingestion.views.md) | `IMPLEMENTED_VERIFIED` | 22 | 10 | 17 | 0 / 1 | 5 | 0 | 0 | 0 |
| UC-O | [oracle](views/oracle.views.md) | `IMPLEMENTED_VERIFIED` | 16 | 8 | 5 | — | 1 | 0 | 0 | 0 |
| UC1c.3 | [paper-publication](views/paper-publication.views.md) | `IMPLEMENTED_VERIFIED` | 9 | 2 | 6 | — | 2 | 0 | 0 | 0 |
| UC2 | [research](views/research.views.md) | `IMPLEMENTED_OBSERVED` | 33 | 15 | 13 | — | 6 | 0 | 0 | 0 |
| UC1c | [source-enrichment](views/source-enrichment.views.md) | `IMPLEMENTED_VERIFIED` | 21 | 7 | 11 | 1 / 1 | 1 | 0 | 0 | 0 |
| UC1.2 | [source-intake](views/source-intake.views.md) | `IMPLEMENTED_VERIFIED` | 9 | 3 | 3 | — | 2 | 0 | 0 | 0 |
| UC1c.1 | [source-parse](views/source-parse.views.md) | `IMPLEMENTED_VERIFIED` | 17 | 3 | 12 | — | 1 | 0 | 0 | 0 |
| UC1c.2 | [source-reading](views/source-reading.views.md) | `IMPLEMENTED_VERIFIED` | 19 | 9 | 8 | — | 2 | 0 | 0 | 0 |
| UC3 | [verify-claims](views/verify-claims.views.md) | `IMPLEMENTED_OBSERVED` | 20 | 6 | 7 | — | 2 | 0 | 0 | 0 |
| UC8.1 | [workflow-run](views/workflow-run.views.md) | `IMPLEMENTED_VERIFIED` | 13 | 3 | 6 | — | 3 | 0 | 0 | 0 |

Not drawn yet: UC5 Trust a relation (deferred: to-be only; there is no as-is (USE-CASES.md UC5)); UC6 Reorganise a folder into groups (deferred: PLAN.md 2.2); UC7 See the data in another model (deferred: PLAN.md 2.2).

## Root causes

| Theme | What goes wrong | Weaknesses | Handled |
|---|---|---|---|
| **T1 No parent process** | Work is a chain of separate surfaces and stages, and the person or tier 0 is the parent that joins them. | W-ACT-04, W-ING-01, W-ING-02, W-ING-04, W-ING-05, W-FOL-04, W-CMP-01 | 7 of 7 |
| **T2 Authority does not fit the work** | Tiers and asks are per call, so delegated work stalls on gates it cannot pass or asks it cannot get answered. | W-ACT-01, W-ACT-02, W-ACT-03, W-ING-03, W-EXT-03 | 5 of 5 |
| **T3 Work is counted, not judged** | A finished call, a full count or the doer's own reading stands in for a check that the result is right. | W-SRC-01, W-REA-01, W-ACC-03, W-VER-01, W-VER-02, W-RES-06, W-ORA-01, W-DOC-04 | 8 of 8 |
| **T4 Failures have no ticket and no repair loop** | A failure is a code in a result; nobody owns it, nothing records it, and repair is tier 0 by hand. | W-DOC-01, W-DOC-02, W-DOC-03, W-INT-02, W-WFR-02, W-BAT-01 | 6 of 6 |
| **T5 Decisions wait with no owner** | Work that needs a decision is left in a state, with no one assigned and nothing drafted to decide from. | W-BAT-02, W-STI-02, W-INT-01, W-FOL-03 | 4 of 4 |
| **T6 Results do not reach the person** | What a run did is dropped, unrecorded or wiped before the person sees it. | W-WFR-01, W-WFR-03, W-ACC-01, W-ACC-02 | 4 of 4 |
| **T7 One decision reaches too far** | A folder decision re-applies, and can be blocked by, every group in the library. | W-FOL-01, W-FOL-02 | 2 of 2 |
| **T8 Links between records are derived or missing** | Paper, note, folder and application records are joined by titles, timing or nothing at all. | W-CIT-01, W-CIT-02, W-RES-05, W-PUB-02, W-EXT-02, W-PAR-01 | 6 of 6 |
| **T9 The research session does not fit a brief** | One session, one synthesis, the whole library as its pool and halving budgets: built for one question about the library. | W-RES-01, W-RES-02, W-RES-03, W-RES-04 | 4 of 4 |
| **T10 Integrity and naming** | Errors where refusals belong, a bypassed gate, states and names that mean two things, and leftovers. | W-EXT-01, W-ACT-05, W-FOL-05, W-ACC-04, W-STI-01, W-DOC-05, W-REA-02, W-PUB-01 | 5 of 8 |

## Weakness register

Every weakness found in the as-is, and the to-be element that handles it.

| Id | Kind | In | Weakness | Handled by |
|---|---|---|---|---|
| W-ACC-01 | fault | `acceptance` | A stale-revision conflict reloads the form and wipes the person's edits (F-09). | `activation-web-ui` |
| W-ACC-02 | gap | `acceptance` | A note written but not findable needs a manual Rewrite indexes; nothing re-checks findability by itself. | `ingestion` |
| W-ACC-03 | unverified | `acceptance` | The only check of an enriched source is a person reading its summary; nothing compares the note with its evidence first. | `ingestion` |
| W-ACC-04 | drift | `acceptance` | The 96 notes an agent accepted on 20 November still record a person as the attester; correcting them is an Owner decision. | open: Owner decision: whether to correct the attester on the 96 notes accepted on 20 November. |
| W-ACT-01 | gap | `activation` | Tier 0 through MCP is capped at contribute: it has no folder tools, and process_approved (curate) is refused, so each folder decision and batch start is handed back to the person. | `activation-overseer` |
| W-ACT-02 | cost | `activation` | A Broker Ask waits 150 s, then fails with PERMISSION_UNANSWERED; an unattended run stalls on each one. | `activation-external-project` |
| W-ACT-03 | cost | `activation` | The in-app Lead asks tool by tool (Ask mode, 600 s wait); there is no permission envelope for a whole run. | `compose` |
| W-ACT-04 | gap | `activation` | Six surfaces enter the Core with different tiers and gates, and none reaches a common parent process for the work it starts. | `compose` |
| W-ACT-05 | risk | `activation` | Add source in the Web UI ingests at curate through person_call and bypasses the Broker; the same act through MCP is gated. | open: Owner decision: may a person's own surface skip the Broker, as it does today? |
| W-BAT-01 | fault | `batch-enrichment` | folder_describe failed in all 12 audited folder-item attempts, and no folder_data success was observed. | `batch-enrichment` |
| W-BAT-02 | gap | `batch-enrichment` | A finished batch is not acceptance, yet nothing assigns the decisions it leaves; W7 now counts them (awaiting_acceptance) but does not route them. | `ingestion` |
| W-CIT-01 | risk | `cite-graph` | A graph paper is linked to its Source note by title, derived each time; a renamed note breaks the link. | `cite-graph` |
| W-CIT-02 | gap | `cite-graph` | A read but unaccepted paper can be kept as a candidate but never quoted. | `cite-graph` |
| W-CMP-01 | gap | `compose` | The batch's stages and the session's phases are not compositions: stages are code, and phases are declared data that no workflow can call (OP16). | `compose` |
| W-DOC-01 | cost | `doctor` | Every repair is tier-0 work: each failure of the 19-20 November run came back to tier 0. | `doctor` |
| W-DOC-02 | gap | `doctor` | A failure is a refusal code in a call's result, not a ticket: there is no register of open failures, their owners or their repairs. | `doctor` |
| W-DOC-03 | risk | `doctor` | Nothing checks a repair's reach before it runs: R1's re-survey re-applied every group in the library. | `doctor` |
| W-DOC-04 | unverified | `doctor` | Whether a repair worked is judged by the agent that made it. | `doctor` |
| W-DOC-05 | drift | `doctor` | `doctor` already names the install capability check (doctor.py, the doctor tool); the repair role needs a distinct code name. | `doctor` |
| W-EXT-01 | fault | `activation-external-project` | Recording an application with no sources used raises a TypeError instead of a refusal. | `activation-external-project` |
| W-EXT-02 | gap | `activation-external-project` | An Applications/ note pins no snapshot hashes, locators or verification, so a later reader cannot tell exactly what was used. | `activation-external-project` |
| W-EXT-03 | cost | `activation-external-project` | A consult-tier delegate is refused, and a session Ask times out at 150 s; either ends the external task's use of the library. | `activation-external-project` |
| W-FOL-01 | risk | `folder-review` | Every accept re-applies every accepted group in the library (OP2): one folder's decision has a whole-library radius. | `folder-review` |
| W-FOL-02 | fault | `folder-review` | A stale card anywhere refuses this decision (FOLDER_STALE across all groups); R1 needed a re-survey of an unrelated root. | `folder-review` |
| W-FOL-03 | gap | `folder-review` | The model's draft of a folder's purpose is off by default (FOLDER_DRAFT_DISABLED); when on, it sees only file counts and bytes. | `folder-review` |
| W-FOL-04 | gap | `folder-review` | Accepting a folder does not start its intake: queueing its documents is a separate click or API call. | `ingestion` |
| W-FOL-05 | risk | `folder-review` | A folder card can be approved (for the batch) or accepted (applied as a group): two states with different powers that the person can confuse. | `state:folder-card` |
| W-ING-01 | gap | `ingestion` | Nothing reconciles a folder's counts (surveyed, queued, staged, enriched, accepted); the person or tier 0 does it by hand. | `ingestion` |
| W-ING-02 | gap | `ingestion` | Queued documents wait until someone runs the queue, and a queue nobody drains says nothing. | `ingestion` |
| W-ING-03 | fault | `ingestion` | Tier 0 cannot approve or start a batch, so an orchestrated ingestion always hands Gate 1 back to the person. | `ingestion` |
| W-ING-04 | gap | `ingestion` | A partial item is re-run only by a fresh approval and start; resuming an unfinished run is a different path. | `ingestion` |
| W-ING-05 | cost | `ingestion` | On 19-20 November control came back to tier 0 eight times on the main path, and ten on the worst (graded bad). | `activation-overseer` |
| W-INT-01 | gap | `source-intake` | Titles fall back to slugs or file names, and the topic to Unfiled; nothing schedules the fix. | `source-intake` |
| W-INT-02 | gap | `source-intake` | A quarantined capture waits for someone to retry it, and nobody is told. | `source-intake` |
| W-ORA-01 | gap | `oracle` | Admitted contracts and Tier A checks exist only in audited sessions; ingestion, research and workflows are judged by whoever ran them. | `oracle` |
| W-PAR-01 | risk | `source-parse` | A provisional paper projection is written before reading; if reading then fails, a catalogue-only projection remains. | `source-parse` |
| W-PUB-01 | cost | `paper-publication` | Old and failed candidate paper databases are never cleaned up. | open: Handled on Geo-Grapher's side (G-BLD-06, G-GEN-01): geo-grapher/to-be paper-import inserts into one active database, and snapshots are pruned by retention. |
| W-PUB-02 | gap | `paper-publication` | Publication needs an accepted current folder, so a source added without folder review is never published. | `paper-publication` |
| W-REA-01 | fault | `source-reading` | Read completion follows the remaining-part counts, not the validity of each part's answer. | `source-reading` |
| W-REA-02 | gap | `source-reading` | The metadata stage copies a few literal Data facts and lists the unknown fields; there is no semantic metadata step. | `source-reading` |
| W-RES-01 | cost | `research` | The candidate pool is the whole library: 82 of its own notes and folder cards had to be decided in the 20 November run (OP4). | `research` |
| W-RES-02 | cost | `research` | A phase's budget is per visit and halves on every return (20, 10, 5, 2, 1, then nothing): the run needed four extensions, and Synthesise reopened with one call left (OP5). | `research` |
| W-RES-03 | gap | `research` | A session holds one synthesis, so every report shares one Together and one Unknowns, which go stale after a redraft (OP3). | `research` |
| W-RES-04 | gap | `research` | Where a finding lands in our code stays prose: it is not a claim, and nothing checks it (OP10). | `research` |
| W-RES-05 | gap | `research` | Read papers that were never accepted are not candidates; the Lead has to find them again by graph citation. | `research` |
| W-RES-06 | fault | `research` | A report quoting only a paper's card broke the project's disqualifier, and nothing caught it. | `research` |
| W-SRC-01 | unverified | `source-enrichment` | A completed model call is counted as a stage done; nothing judges whether the answer is a valid answer to the task. | `source-enrichment` |
| W-STI-01 | risk | `state:staged-item` | A source can be accepted straight from staged ('accept as captured'), entering the library with only what intake fetched read; only its coverage label says so. | `state:staged-item` |
| W-STI-02 | gap | `state:staged-item` | An enriched or partial item has no owner and no deadline: it waits until someone decides it. | `state:staged-item` |
| W-VER-01 | gap | `verify-claims` | Claim review is off by default, so a garbled claim was staged checked only for its quote (OP7). | `verify-claims` |
| W-VER-02 | fault | `verify-claims` | A review that does not complete marks the claim unchecked and stages it anyway; three full-PDF quotes went this way (OP9). | `verify-claims` |
| W-WFR-01 | fault | `workflow-run` | The Web UI discards a run's result (app.js:8472): the person never sees what was read, what failed or why. | `activation-web-ui` |
| W-WFR-02 | gap | `workflow-run` | A paused run shows a static chip, with no route picker, resume or dismiss. | `activation-web-ui` |
| W-WFR-03 | fault | `workflow-run` | deep-read-staged reads each staged source but leaves its status unchanged, so nothing records that it was read. | `source-enrichment` |

54 weaknesses: 51 handled by the to-be, 3 open with a reason, 0 not yet answered.

## Checks

Errors (0):

Warnings (0):
