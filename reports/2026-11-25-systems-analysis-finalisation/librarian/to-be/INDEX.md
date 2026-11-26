# Librarian — to-be pack

The preferred Librarian: every use case runs under a parent process that owns it end to end, is granted its authority once, is judged by an Oracle separate from its workers, and repairs its failures through tickets and a Doctor. handles.yaml answers each as-is weakness, and the as-is index counts what is left. Nothing here is accepted or built (PROPOSED_UNACCEPTED).

[Use case diagram](use-case-diagram.md) · [Composition](composition.md) · [States](states.md) · [Authority (permissions, reserved decisions and risk)](authority.md) · [Data contract (Medallion and DIK)](data-contract.md) · [Who starts each use case (the person, tier 0, a schedule)](initiators.md) · [Performance (baselines, metrics and targets)](performance.md) · [Ingest sequence by source kind (a repository and a document)](source-kinds.md) · [Stage contracts and CI/CD pathways](stages.md) · [Ticket routing (who owns each ticket class)](ticket-routing.md) · [Geo-Grapher woven into the Librarian](weave.md) · [Canvas](index.canvas)

## Use cases

| Id | Use case | Status | Nodes | Steps | Paths | Tier-0 turns (main / worst) | Weaknesses | Handles | Errors | Warnings |
|---|---|---|---|---|---|---|---|---|---|---|
| UC1.3 | [acceptance](views/acceptance.views.md) | `PROPOSED_UNACCEPTED` | 9 | 2 | 4 | — | 0 | 0 | 0 | 0 |
| UC0 | [activation-external-project](views/activation-external-project.views.md) | `PROPOSED_UNACCEPTED` | 34 | 8 | 12 | 2 / 2 | 0 | 4 | 0 | 0 |
| UC0 | [activation-overseer](views/activation-overseer.views.md) | `PROPOSED_UNACCEPTED` | 39 | 9 | 16 | 2 / 2 | 0 | 2 | 0 | 0 |
| UC0 | [activation-web-ui](views/activation-web-ui.views.md) | `PROPOSED_UNACCEPTED` | 39 | 12 | 22 | — | 0 | 3 | 0 | 0 |
| UC9 | [agenda](views/agenda.views.md) | `PROPOSED_UNACCEPTED` | 20 | 6 | 8 | 0 / 1 | 0 | 0 | 0 | 0 |
| UC1b | [batch-enrichment](views/batch-enrichment.views.md) | `PROPOSED_UNACCEPTED` | 37 | 10 | 21 | — | 0 | 1 | 0 | 0 |
| UC8.2 | [catalogue](views/catalogue.views.md) | `PROPOSED_UNACCEPTED` | 34 | 12 | 12 | — | 0 | 0 | 0 | 0 |
| UC4 | [cite-graph](views/cite-graph.views.md) | `PROPOSED_UNACCEPTED` | 12 | 5 | 6 | — | 0 | 2 | 0 | 0 |
| UC8 | [compose](views/compose.views.md) | `PROPOSED_UNACCEPTED` | 35 | 10 | 26 | 1 / 1 | 0 | 3 | 0 | 0 |
| UC0.4 | [delegate](views/delegate.views.md) | `PROPOSED_UNACCEPTED` | 19 | 7 | 9 | 2 / 2 | 0 | 0 | 0 | 0 |
| UC-D | [doctor](views/doctor.views.md) | `PROPOSED_UNACCEPTED` | 26 | 6 | 13 | — | 0 | 5 | 0 | 0 |
| UC1.1 | [folder-review](views/folder-review.views.md) | `PROPOSED_UNACCEPTED` | 23 | 6 | 20 | — | 0 | 3 | 0 | 0 |
| UC1 | [ingestion](views/ingestion.views.md) | `PROPOSED_UNACCEPTED` | 40 | 13 | 31 | — | 0 | 8 | 0 | 0 |
| UC-L | [learn](views/learn.views.md) | `PROPOSED_UNACCEPTED` | 10 | 5 | 3 | — | 0 | 0 | 0 | 0 |
| UC-O | [oracle](views/oracle.views.md) | `PROPOSED_UNACCEPTED` | 16 | 5 | 7 | — | 0 | 1 | 0 | 0 |
| UC1c.3 | [paper-publication](views/paper-publication.views.md) | `PROPOSED_UNACCEPTED` | 8 | 2 | 6 | — | 0 | 1 | 0 | 0 |
| UC2 | [research](views/research.views.md) | `PROPOSED_UNACCEPTED` | 34 | 15 | 18 | — | 0 | 6 | 0 | 0 |
| UC1c | [source-enrichment](views/source-enrichment.views.md) | `PROPOSED_UNACCEPTED` | 26 | 7 | 16 | — | 0 | 2 | 0 | 0 |
| UC1.2 | [source-intake](views/source-intake.views.md) | `PROPOSED_UNACCEPTED` | 9 | 4 | 3 | — | 0 | 2 | 0 | 0 |
| UC1c.1 | [source-parse](views/source-parse.views.md) | `PROPOSED_UNACCEPTED` | 17 | 3 | 6 | — | 0 | 1 | 0 | 0 |
| UC1c.2 | [source-reading](views/source-reading.views.md) | `PROPOSED_UNACCEPTED` | 20 | 12 | 5 | — | 0 | 2 | 0 | 0 |
| UC3 | [verify-claims](views/verify-claims.views.md) | `PROPOSED_UNACCEPTED` | 20 | 6 | 6 | — | 0 | 2 | 0 | 0 |

Not drawn yet: UC8.1 Run a saved workflow from the Web UI (deferred: no separate to-be spec: its steps are wgrant, uinotify and uiagenda in activation-web-ui, under compose (as-is W-WFR-01 to 03 are handled there)); UC5 Trust a relation (deferred: USE-CASES.md UC5; not yet drawn); UC6 Reorganise a folder into groups (deferred: PLAN.md 2.2); UC7 See the data in another model (deferred: PLAN.md 2.2); UC10 Search and read the library (deferred: the Web UI's Search and note view, and the search and get_note tools; it only reads); UC11 Add a project and map what the library holds for it (deferred: the add_project session purpose; its sources go through UC1); UC12 Suggest work for the vault (deferred: the suggest session purpose); UC13 Start a pursuit (a course, a role or a project) (deferred: the start_pursuit session purpose); UC14 Study a topic with the library (deferred: the learn session purpose (tutoring); not UC-L, which learns a remedy); UC15 Add a capability (an MCP server) (deferred: the add_capability session purpose; the person decides the install); UC16 Run a scheduled pipeline (deferred: weekly-review and clear-enrichment-backlog; not overseen, so a high-risk decision holds for the Owner).

## Checks

Errors (0):

Warnings (0):
