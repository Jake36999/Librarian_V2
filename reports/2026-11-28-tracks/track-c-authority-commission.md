# Track C: authority granted once (M2's commission, M3's consolidated question)

**Why:** tier 0 should spend few turns and tokens on the Librarian, by commissioning work that tiers 1 to 3 carry out. Today every high-risk decision goes to the person: approving sources into the batch, starting it, and accepting. `ingestion_begin` holds them for any caller but the person. A commission is what lets an overseen run decide them within what the Owner granted.

M5's last done-when waits on this: a commissioned ingestion in at most 2 tier-0 turns. So does Track D's unattended running.

**Repository:** Librarian.

**Read:**
- the implementation plan, M2 (items 1 to 4, and "Done when") and M3 item 4;
- `reports/2026-11-25-systems-analysis-finalisation/librarian/to-be/authority.md` and `authority.table.yaml` (proposed, not accepted);
- `docs/policy/agent-roles-and-authority.md`, "High risk when no tier 0 oversees".

## Sprint C1: the design, for the Owner

**Write** `reports/<date>-commission-design/README.md`, covering:
- what a commission records: who commissions it, the scope (a pipeline, its inputs, a folder root), the granted decisions, a spend ceiling, the step budget from the manifest, an expiry, and the handover;
- how the person approves it once, building on `Broker.envelope` and `request_envelope`;
- how a run proves it is overseen;
- what stays a reserved decision whatever the commission says: sensitivity reviews, promotion-mode changes, lead overrides;
- how `ingestion_begin`, `staging_decide` and `process_approved` consult it;
- how M3's single consolidated question per overseen run is formed.

**Build on what exists:**
- the permission envelope;
- `CheckpointStore` (the `high_risk_hold` type is declared and unused);
- `TicketStore`;
- the manifests (`manifests.py`, `process_manifest`).

**Done when:** the Owner accepts the design, after Claude has reviewed it. No code in this sprint.

## Sprint C2: the commission record

- Implement the accepted design.
- Every refusal path stays as it is for a run that is not commissioned.
- A new gate starts in report mode where it could refuse something allowed today.

**Done when:**
- the plan's M2 done-when holds: a commissioned ingestion's broker log shows no ask for an enveloped tool and no tool outside the envelope;
- an out-of-envelope call is escalated, and a reserved decision is held;
- an unoverseen run holds its high-risk decision on the agenda while the rest runs;
- the regression audit and the full suite pass.

## Sprint C3: the consolidated question, and the measured run

- M3 item 4: an overseen run's open decisions come back to tier 0 as one question.
- Then the measurement in a throwaway library, with the Owner's approval of the spend: tier 0 commissions `ingest-folder` with `approve_folder_drafts` and `start_batch` on the fixed test folder.

**Done when:** that run reaches accepted notes in at most 2 tier-0 turns, with the turns and tokens reported against the M0 baselines (`reports/2026-11-26-m0-baselines/README.md`).
