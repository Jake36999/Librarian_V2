# To-be: ingestion run by the tiers, overseen by tier 0, with an oracle and a doctor

20 November 2026. The second half of the [worked example](INGESTION-EXAMPLE.md). The as-is spec drew the ingestion as it ran. This one draws it as it should run when a tier-0 agent oversees it on the Owner's behalf, under five owner directions:
1. **The Owner and tier-0 lanes are the quietest.** Tier-0 models cost the most tokens, so every step a tier-1 model can do moves down.
2. **Tier 0 does three things at most:**
   - it initiates: hands the run to a Lead, and sets the oracle's specification;
   - it reviews the result once;
   - it reports to the Owner.

   If the review is not satisfied, tier 0 tasks the oracle with tidying up, waits for the oracle's response, makes one more pass, then reports. **The last step is always reporting to the Owner.**
3. **Owner steps in between are decisions only the Owner can make**, relayed by tier 0. Without a tier-0 overseer, these would be tier-1 permission requests, made directly when the permission mode is not Auto.
4. **The oracle and the doctor are actors of their own**, outside the system and outside each other:
   - the oracle judges and never acts;
   - the doctor repairs failures at mapped extension points (UC-D);
   - a shortfall that no extension maps is a tier-1 *misalignment*, which the Lead re-aligns from the oracle's report;
   - an escalation back to tier 0 is a **failure end**, counted.
5. **Lanes in the owner's order:** Owner, tier 0, Oracle, tier 1, Doctor, tier 2, tier 3, then the system actors (Core, Model host, Geo-Grapher). The doctor sits next to tiers 2 and 3, the agents whose failures it will mostly repair. The oracle sits next to tier 1, where a shortfall is most often a misalignment.

Everything below is generated from four specs by [render_spec.py](render_spec.py), with no model call:

| Spec | Use case | Views | Canvas | Paths | Problems / flags |
|---|---|---|---|---|---|
| [ingestion.spec.yaml](ingestion.spec.yaml) | As-is ingestion | [views](ingestion.views.md) | [canvas](ingestion.canvas) | 11 | 0 / 0 |
| [ingestion-tobe.spec.yaml](ingestion-tobe.spec.yaml) | To-be ingestion | [views](ingestion-tobe.views.md) | [canvas](ingestion-tobe.canvas) | 26 | 0 / 0 |
| [doctor.spec.yaml](doctor.spec.yaml) | UC-D: diagnose and resolve | [views](doctor.views.md) | [canvas](doctor.canvas) | 8 | 0 / 0 |
| [learn.spec.yaml](learn.spec.yaml) | UC-L: learn a remedy | [views](learn.views.md) | [canvas](learn.canvas) | 3 | 0 / 0 |

The doctor's remedies are in [remedy-catalogue.yaml](remedy-catalogue.yaml).

## 1. The to-be happy path

From [ingestion-tobe.views.md](ingestion-tobe.views.md), generated:
1. The **Owner** directs the ingestion of a folder into a library, naming the subfolders to exclude.
2. The **Tier 0 agent** hands the ingestion to a Lead, and sets the oracle's specification: UC1's success guarantee.
3. The **Lead** opens an ingest-folder run for the folder.
4. The **Core** surveys the folder and proposes a decision per subfolder.
5. The **Lead** applies the Owner's exclusions and the decisions policy allows.
6. The **Clerk** assesses each remaining subfolder's sensitivity.
7. The **Core** accepts the remaining subfolders by policy, attested as the policy.
8. The **Core** queues the in-scope documents for each accepted root.
9. The **Helper** validates the queued count against the survey.
10. The **Core** captures and stages each document.
11. The **Core** approves the staged documents by policy, attested as the policy.
12. The **Core** parses and converts each document.
13. The **Clerk** reads each document part by part.
14. The **Core** enforces the library's spend ceiling (concurrently with 12–13).
15. **Geo-Grapher** imports each fully converted paper into the paper graph.
16. The **Core** accepts the enriched documents by policy, attested as the policy.
17. The **Core** writes each Source note and validates it is findable.
18. The **Oracle** judges the run against the specification: deterministic checks first, then a model review.
19. The **Lead** hands the result and the oracle's verdict to tier 0.
20. The **Tier 0 agent** reviews the result once against the specification.
21. The **Tier 0 agent** reports the result to the Owner.

The Owner's subfolder exclusions now come with the direction at step 1, so the happy path has no Owner step between the start and the report.

### Tier-0 turns: the measure

A **turn** is one return of control to tier 0. Consecutive tier-0 steps on a path count as one turn, since the agent is invoked once and does them together. The renderer counts turns on every path, to its end, and grades them on the owner's scale:

| Turns | Grade |
|---|---|
| 2 | ideal |
| 3 | expected |
| 4 | rusty |
| 5–10 | bad |
| 10–15 | might as well have done it themselves |

| | As-is run | To-be |
|---|---|---|
| Main success scenario | **6 (bad)** | **2 (ideal)**: initiate (2); review and report (20–21) |
| Worst graded path | 7 (bad) | **3 (expected)** |
| Paths at 3 turns | — | 6b: a sensitive subfolder, which tier 0 relays to the Owner. 20a: the review sends the result back to the oracle; tier 0 waits, makes a second pass, then reports. |
| Escalations | — (every failure was resolved by tier 0 by hand) | 6, each drawn as a failure end and not graded |

Every other path is 2 turns (ideal), including each pause for an Owner decision. The pause reaches the Owner through tier 0, in the same turn as its report.

### Lane load

Counted by the renderer (`## Lane load` in each views file), as actions and decisions per lane, not tokens. Tier 0's 4 nodes on the main scenario are its initiation, its review, the review's decision and its report: 2 turns.

| Lane | As-is, main scenario | To-be, main scenario | To-be, anywhere |
|---|---|---|---|
| Owner | 2 | **1** | 3 |
| **Tier 0 agent** | **8** (6 turns) | **4** (2 turns) | 10 |
| Oracle | — | 2 | 4 |
| Lead (tier 1) | — | 3 | 7 |
| Doctor | — | 0 | 6 |
| Helper (tier 2) | — | 2 | 3 |
| Clerk (tier 3) | 3 | 3 | 3 |
| Core | 9 | 13 | 16 |
| Model host | 2 | 2 | 2 |
| Geo-Grapher | 1 | 1 | 1 |

### How it can end

There are 26 paths:
- 1 **success**;
- 7 **paused**, for an Owner decision: the budget ceiling, or a remedy the Owner declined;
- 6 **escalated**, one per doctor call;
- 12 that rejoin the main flow: a failure the doctor resolved, a decision the Owner made, the concurrent spend check, a partial page picked up later, a misalignment the Lead re-aligned, or the oracle's tidy-up.

**An escalated path is a failure of this use case, by design.** The doctor could not resolve the case, so tier 0 had to take it over (one tier-0 step, "takes over the escalated case"). The measure to drive down is escalations per run.

## 2. Extensions as references

Every repairable failure point in the to-be ingestion is a **reference** to another use case (UML's call-behaviour action, drawn `[[…]]` in Mermaid and as an orange card in the Doctor's lane on the canvas), not an improvised fix:

| Extension | Symptom | Handled by | Remedy | As-is |
|---|---|---|---|---|
| 4a | a stale root elsewhere | Doctor (UC-D) | R1 re-survey the root | 3a, resolved by hand |
| 6a | Clerk qualification lost | Doctor (UC-D) | R2 re-qualify the role | 5a, resolved by hand (`cab623a`) |
| 6b | subfolder sensitive | Lead → tier 0 → Owner decides | — | anticipated |
| 9a | queued count mismatch | Doctor (UC-D) | R3 queue per root | 8a, resolved by hand |
| 13a | model unavailable or partial page | (rejoins at the join; 13b picks it up) | — | 12a |
| 13b | some documents partial | Doctor (UC-D) | R4 re-read the partials | 12b, resolved by hand |
| 14a | spend ceiling reached | Lead → tier 0 → Owner (the use case pauses) | — | anticipated |
| 16a | the library's promotion mode is person | Core raises an agenda item; Owner accepts | — | **15a: the hand-off nobody owned** |
| 17a | note not findable | Doctor (UC-D) | R5 re-index the note | anticipated |
| 18a | oracle: shortfall at a mapped extension | Doctor (UC-D) | R6 reconcile and route | — |
| 18b | oracle: shortfall no extension maps (misalignment) | Helper scouts the blast radius; Lead re-aligns; oracle judges again | — | — |
| 20a | tier 0's review: needs tidying | Tier 0 tasks the oracle; oracle oversees the Lead and doctor; oracle judges again and responds; tier 0 makes a second pass | — | — |

**The renderer checks every reference against the spec it calls.** UC-D can end *resolved*, *declined* or *escalated*, so each of the six calls must handle all three, and nothing else. This was tested: deleting one call's *declined* branch made the renderer report `r1 calls UC-D but does not handle its outcome 'declined'`.

This is what lets a tier-0 agent working outside a use case stay inside the map. If it meets a stale root while doing something else, the stale root is not new: it is UC1's extension 4a. Its pathway is the reference, R1 then rejoin. The agent cites the use case and extension instead of reasoning the fix out again. The catalogue's R7 and R8 show the same for the research use case (UC2 `*b` and `*c`).

## 3. The doctor (UC-D)

[doctor.views.md](doctor.views.md), generated:

**Main success scenario**
1. The **Core** records the symptom at its extension point: use case, extension, refusal code and evidence.
2. The **Doctor** (its own actor, with its own model assignment) matches the symptom against the remedy catalogue.
3. The **Core** computes the remedy's blast radius.
4. The **Doctor** runs the remedy's workflow.
5. The **Core** re-runs only the checks inside the blast radius.
6. The **Helper** validates that the symptom is gone at its extension point.
7. The **Core** records the case in the catalogue's history: symptom, remedy, result.
8. The **Doctor** returns control to the step the extension rejoins.

**Extensions**
- **2a. No match: a new shape.**
  1. The Doctor drafts a diagnosis from the nearest catalogued cases.
  2. The Core hands the case to tier 0, which resolves it and may propose a new remedy (UC-L).
  3. The use case ends **escalated**.
- **3a. Outside the doctor's scope** (irreversible, too wide, or a person's decision).
  1. The Owner decides.
  2. If the Owner approves, rejoin at 4. If not, the use case ends **declined**, and the calling use case pauses.
- **5a. A check fails after the remedy.**
  1. The Core rolls the remedy back by its compensation step.
  2. If another remedy is left, within two attempts, rejoin at 2. If none is left, escalate as in 2a.

On the doctor's main scenario the Owner and tier 0 have **no step at all**: they appear only in extensions 2a and 3a.

**The doctor's scope is the catalogue, and the blast radius gates it.** Step 3 is workstream W3's change-impact detection applied to a remedy: what the remedy will touch. Step 5 is the same tool used the other way: re-run only what the remedy touched.

R1 shows why the gate matters. Re-surveying a root should touch only that root's groups. Today every folder accept rebuilds every group (OP2), so R1's real radius is the whole library, and the scope check sends it to the Owner. When Geo-Grapher's rebuild is fixed, the same entry becomes a remedy the doctor runs alone.

## 4. The catalogue

[remedy-catalogue.yaml](remedy-catalogue.yaml) has eight entries. Each is keyed by **where** a failure arrives (use case and extension) and **what it looks like** (refusal code and shape). Each names:
- the remedy workflow, a YAML workflow over registered actions;
- its scope: side effects, reversibility, model calls and blast radius;
- the step the caller rejoins;
- its history: what the as-is run shows.

Six entries come from failures the tier-0 agent resolved by hand on 19–20 November. They are the doctor's first cases, with the fixes already known.

None of the remedy workflows exists yet (`status: proposed`), except `request_budget` (R8).

## 5. How the doctor grows

UC-L ([learn.views.md](learn.views.md)) is the only way the doctor's scope widens:
1. Tier 0 resolves an escalated case.
2. Tier 0 proposes a catalogue entry.
3. The Core validates it: the workflow exists, the scope is declared, the radius is bounded.
4. The Owner accepts it.
5. The entry is pinned to its digest.

Each escalation is therefore a chance to remove the next one.

The matching in step 2 can grow in stages, each needing more history than the last:

| Stage | Matches by | Needs |
|---|---|---|
| 1 | Exact key: use case, extension and refusal code | The catalogue as written |
| 2 | Shape: the symptom's fields, such as "queued 0 where the survey found N" | A few cases per entry |
| 3 | Similarity to past cases' evidence (embeddings, or a small classifier trained on the history) | Enough recorded cases to learn from; it proposes a match, and the Helper validates it before anything runs |
| 4 | Remedy trust tiers: success rate per entry maps to bronze (the Owner approves each run), silver (the doctor runs it, the Helper checks) and gold (it runs as part of the workflow) | Measured success and rollback rates (workstream W5's tiers, applied to remedies) |

The history the Core records at step 7 is the training data. The blast radius bounds what any learned match may do, so the doctor's influence grows only as far as its record and its declared scope allow.

## 6. What this leaves to build

| Piece | Workstream |
|---|---|
| The ingestion as a workflow the Core runs (`ingest-folder`), so a Lead can run it | W1 (workflows as data) |
| The doctor's symptom record at each extension point (use case, extension, code, evidence) | W1: the extension ids come from the use cases' specs |
| Blast radius for a remedy, and targeted re-checks | W3 |
| The remedy workflows R1–R6 | New; each is a small YAML workflow over existing actions |
| The oracle as a role on a workflow run: the spec set by tier 0 (or by a tier-1 Lead for a sub-run), a separate model assignment, and one hand-back to whoever set the spec | [diagram-workflows proposal, section 10](../../../../docs/proposals/diagram-workflows.md) (P6, P7) |
| Tier-0 turns counted on real runs, not only on diagrams: each return of control to tier 0 logged and graded on the same scale | New; the renderer's count is the specification for it |
| Remedy trust tiers | W5 |
| Attestation that names who accepted (the policy or a person, never "person" for an agent) | W7 (finding F2 in the as-is example) |

Nothing here is built, and nothing is committed.
