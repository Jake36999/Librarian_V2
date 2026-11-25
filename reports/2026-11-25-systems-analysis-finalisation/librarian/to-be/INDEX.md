#  — to-be pack



[Use case diagram](use-case-diagram.md) · [Composition](composition.md) · [Canvas](index.canvas)

## Use cases

| Id | Use case | Status | Nodes | Steps | Paths | Tier-0 turns (main / worst) | Weaknesses | Handles | Errors | Warnings |
|---|---|---|---|---|---|---|---|---|---|---|
| UC1.3 | [acceptance](views/acceptance.views.md) | `PROPOSED_UNACCEPTED` | 9 | 2 | 4 | — | 0 | 0 | 0 | 1 |
| UC0 | [activation-external-project](views/activation-external-project.views.md) | `PROPOSED_UNACCEPTED` | 34 | 8 | 12 | 2 / 2 | 0 | 0 | 0 | 2 |
| UC0 | [activation-overseer](views/activation-overseer.views.md) | `PROPOSED_UNACCEPTED` | 40 | 9 | 16 | 2 / 2 | 0 | 0 | 0 | 3 |
| UC0 | [activation-web-ui](views/activation-web-ui.views.md) | `PROPOSED_UNACCEPTED` | 37 | 12 | 23 | — | 0 | 0 | 0 | 2 |
| UC1b | [batch-enrichment](views/batch-enrichment.views.md) | `PROPOSED_UNACCEPTED` | 37 | 10 | 21 | — | 0 | 0 | 0 | 1 |
| UC8 | [compose](views/compose.views.md) | `PROPOSED_UNACCEPTED` | 34 | 9 | 22 | 1 / 1 | 0 | 0 | 0 | 3 |
| UC-D | [doctor](views/doctor.views.md) | `PROPOSED_UNACCEPTED` | 26 | 6 | 13 | — | 0 | 0 | 0 | 2 |
| UC1.1 | [folder-review](views/folder-review.views.md) | `PROPOSED_UNACCEPTED` | 22 | 5 | 16 | — | 0 | 0 | 0 | 2 |
| UC1 | [ingestion](views/ingestion.views.md) | `PROPOSED_UNACCEPTED` | 36 | 13 | 30 | — | 0 | 0 | 0 | 1 |
| UC-L | [learn](views/learn.views.md) | `PROPOSED_UNACCEPTED` | 10 | 5 | 3 | 1 / 1 | 0 | 0 | 0 | 1 |
| UC1c.3 | [paper-publication](views/paper-publication.views.md) | `PROPOSED_UNACCEPTED` | 8 | 2 | 4 | — | 0 | 0 | 0 | 1 |
| UC1c | [source-enrichment](views/source-enrichment.views.md) | `PROPOSED_UNACCEPTED` | 26 | 7 | 16 | — | 0 | 0 | 0 | 1 |
| UC1.2 | [source-intake](views/source-intake.views.md) | `PROPOSED_UNACCEPTED` | 8 | 3 | 3 | — | 0 | 0 | 0 | 1 |
| UC1c.1 | [source-parse](views/source-parse.views.md) | `PROPOSED_UNACCEPTED` | 17 | 3 | 6 | — | 0 | 0 | 0 | 1 |
| UC1c.2 | [source-reading](views/source-reading.views.md) | `PROPOSED_UNACCEPTED` | 20 | 12 | 4 | — | 0 | 0 | 0 | 2 |

## Checks

Errors (0):

Warnings (24):
- acceptance: written use case lacks: Use case name, Brief description, Primary actor, Supporting actors, Preconditions, Trigger, Success guarantee, Minimal guarantee, Open questions
- activation-external-project: written use case lacks: Use case name, Brief description, Primary actor, Supporting actors, Preconditions, Trigger, Success guarantee, Minimal guarantee, Open questions
- activation-external-project: decision dmissing ('catalogued Sources satisfy external need?') tests a quantity but declares no boundary values
- activation-overseer: written use case lacks: Use case name, Brief description, Primary actor, Supporting actors, Preconditions, Trigger, Success guarantee, Minimal guarantee, Open questions
- activation-overseer: decision dpperm ('partials acceptable for sprint?') tests a quantity but declares no boundary values
- activation-overseer: decision dverdict ('L3 sprint obligations satisfied?') tests a quantity but declares no boundary values
- activation-web-ui: written use case lacks: Use case name, Brief description, Primary actor, Supporting actors, Preconditions, Trigger, Success guarantee, Minimal guarantee, Open questions
- activation-web-ui: decision dgate1choice ('Gate 1 Source choice on Staging page?') tests a quantity but declares no boundary values
- batch-enrichment: written use case lacks: Use case name, Brief description, Primary actor, Supporting actors, Preconditions, Trigger, Success guarantee, Minimal guarantee, Open questions
- compose: written use case lacks: Use case name, Brief description, Primary actor, Supporting actors, Preconditions, Trigger, Success guarantee, Minimal guarantee, Open questions
- compose: decision dnarrow ('sub-run manifest fits parent mandate (Rules 9, 10, 16)?') tests a quantity but declares no boundary values
- compose: decision dscope ('within spec & parent mandate?') tests a quantity but declares no boundary values
- doctor: written use case lacks: Use case name, Brief description, Primary actor, Supporting actors, Preconditions, Trigger, Success guarantee, Minimal guarantee, Open questions
- doctor: decision dgrant ('within parent mandate and DOC-GEO-03 bounds?') tests a quantity but declares no boundary values
- folder-review: written use case lacks: Use case name, Brief description, Primary actor, Supporting actors, Preconditions, Trigger, Success guarantee, Minimal guarantee, Open questions
- folder-review: decision oraclecov ('degraded parse within caller tolerance?') tests a quantity but declares no boundary values
- ingestion: written use case lacks: Use case name, Brief description, Primary actor, Supporting actors, Preconditions, Trigger, Success guarantee, Minimal guarantee, Open questions
- learn: written use case lacks: Use case name, Brief description, Primary actor, Supporting actors, Preconditions, Trigger, Success guarantee, Minimal guarantee, Open questions
- paper-publication: written use case lacks: Use case name, Brief description, Primary actor, Supporting actors, Preconditions, Trigger, Success guarantee, Minimal guarantee, Open questions
- source-enrichment: written use case lacks: Use case name, Brief description, Primary actor, Supporting actors, Preconditions, Trigger, Success guarantee, Minimal guarantee, Open questions
- source-intake: written use case lacks: Use case name, Brief description, Primary actor, Supporting actors, Preconditions, Trigger, Success guarantee, Minimal guarantee, Open questions
- source-parse: written use case lacks: Use case name, Brief description, Primary actor, Supporting actors, Preconditions, Trigger, Success guarantee, Minimal guarantee, Open questions
- source-reading: written use case lacks: Use case name, Brief description, Primary actor, Supporting actors, Preconditions, Trigger, Success guarantee, Minimal guarantee, Open questions
- source-reading: decision drelate ('multi-chapter document needing semantic relations?') tests a quantity but declares no boundary values
