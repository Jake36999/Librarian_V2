# Librarian — to-be pack

The preferred Librarian: every use case runs under a parent process that owns it end to end, is granted its authority once, is judged by an Oracle separate from its workers, and repairs its failures through tickets and a Doctor. handles.yaml answers each as-is weakness, and the as-is index counts what is left. Nothing here is accepted or built (PROPOSED_UNACCEPTED).

[Use case diagram](use-case-diagram.md) · [Composition](composition.md) · [States](states.md) · [Canvas](index.canvas)

## Use cases

| Id | Use case | Status | Nodes | Steps | Paths | Tier-0 turns (main / worst) | Weaknesses | Handles | Errors | Warnings |
|---|---|---|---|---|---|---|---|---|---|---|
| UC1.3 | [acceptance](views/acceptance.views.md) | `PROPOSED_UNACCEPTED` | 9 | 2 | 4 | — | 0 | 0 | 0 | 0 |
| UC0 | [activation-external-project](views/activation-external-project.views.md) | `PROPOSED_UNACCEPTED` | 34 | 8 | 12 | 2 / 2 | 0 | 4 | 0 | 1 |
| UC0 | [activation-overseer](views/activation-overseer.views.md) | `PROPOSED_UNACCEPTED` | 40 | 9 | 16 | 2 / 2 | 0 | 2 | 0 | 2 |
| UC0 | [activation-web-ui](views/activation-web-ui.views.md) | `PROPOSED_UNACCEPTED` | 37 | 12 | 23 | — | 0 | 2 | 0 | 1 |
| UC1b | [batch-enrichment](views/batch-enrichment.views.md) | `PROPOSED_UNACCEPTED` | 37 | 10 | 21 | — | 0 | 1 | 0 | 0 |
| UC4 | [cite-graph](views/cite-graph.views.md) | `PROPOSED_UNACCEPTED` | 13 | 6 | 4 | — | 0 | 2 | 0 | 0 |
| UC8 | [compose](views/compose.views.md) | `PROPOSED_UNACCEPTED` | 34 | 9 | 22 | 1 / 1 | 0 | 3 | 0 | 2 |
| UC-D | [doctor](views/doctor.views.md) | `PROPOSED_UNACCEPTED` | 26 | 6 | 13 | — | 0 | 5 | 0 | 1 |
| UC1.1 | [folder-review](views/folder-review.views.md) | `PROPOSED_UNACCEPTED` | 22 | 5 | 16 | — | 0 | 3 | 0 | 1 |
| UC1 | [ingestion](views/ingestion.views.md) | `PROPOSED_UNACCEPTED` | 36 | 13 | 30 | — | 0 | 8 | 0 | 0 |
| UC-L | [learn](views/learn.views.md) | `PROPOSED_UNACCEPTED` | 10 | 5 | 3 | 1 / 1 | 0 | 0 | 0 | 0 |
| UC-O | [oracle](views/oracle.views.md) | `PROPOSED_UNACCEPTED` | 16 | 5 | 7 | — | 0 | 1 | 0 | 0 |
| UC1c.3 | [paper-publication](views/paper-publication.views.md) | `PROPOSED_UNACCEPTED` | 8 | 2 | 4 | — | 0 | 0 | 0 | 0 |
| UC2 | [research](views/research.views.md) | `PROPOSED_UNACCEPTED` | 27 | 15 | 12 | — | 0 | 6 | 0 | 0 |
| UC1c | [source-enrichment](views/source-enrichment.views.md) | `PROPOSED_UNACCEPTED` | 26 | 7 | 16 | — | 0 | 2 | 0 | 0 |
| UC1.2 | [source-intake](views/source-intake.views.md) | `PROPOSED_UNACCEPTED` | 8 | 3 | 3 | — | 0 | 1 | 0 | 0 |
| UC1c.1 | [source-parse](views/source-parse.views.md) | `PROPOSED_UNACCEPTED` | 17 | 3 | 6 | — | 0 | 1 | 0 | 0 |
| UC1c.2 | [source-reading](views/source-reading.views.md) | `PROPOSED_UNACCEPTED` | 20 | 12 | 4 | — | 0 | 2 | 0 | 1 |
| UC3 | [verify-claims](views/verify-claims.views.md) | `PROPOSED_UNACCEPTED` | 20 | 6 | 6 | — | 0 | 2 | 0 | 0 |

Not drawn yet: UC5 Trust a relation (deferred: USE-CASES.md UC5; not yet drawn); UC6 Reorganise a folder into groups (deferred: PLAN.md 2.2); UC7 See the data in another model (deferred: PLAN.md 2.2).

## Checks

Errors (0):

Warnings (9):
- activation-external-project: decision dmissing ('catalogued Sources satisfy external need?') tests a quantity but declares no boundary values
- activation-overseer: decision dpperm ('partials acceptable for sprint?') tests a quantity but declares no boundary values
- activation-overseer: decision dverdict ('L3 sprint obligations satisfied?') tests a quantity but declares no boundary values
- activation-web-ui: decision dgate1choice ('Gate 1 Source choice on Staging page?') tests a quantity but declares no boundary values
- compose: decision dnarrow ('sub-run manifest fits parent mandate (Rules 9, 10, 16)?') tests a quantity but declares no boundary values
- compose: decision dscope ('within spec & parent mandate?') tests a quantity but declares no boundary values
- doctor: decision dgrant ('within parent mandate and DOC-GEO-03 bounds?') tests a quantity but declares no boundary values
- folder-review: decision oraclecov ('degraded parse within caller tolerance?') tests a quantity but declares no boundary values
- source-reading: decision drelate ('multi-chapter document needing semantic relations?') tests a quantity but declares no boundary values
