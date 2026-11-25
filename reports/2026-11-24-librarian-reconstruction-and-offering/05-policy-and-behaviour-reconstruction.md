# 05 — Policy and Behaviour Reconstruction: Activation Contexts, Delegated Authority, UI/MCP Interfaces & Pre-Enrichment Flows

> **Work Product 5 (Revised Follow-Up Report)** · Grounded in [2026-11-21-enrichment-baseline](file:///D:/Librarian_V2/reports/2026-11-21-enrichment-baseline/model-notes.md) (`DOC-MAP-07..09`, `DOC-MAP-28`), [2026-11-20-workflow-map](file:///D:/Librarian_V2/reports/2026-11-20-workflow-map/USE-CASES.md) (`DOC-MAP-01..06b`, `DOC-MAP-25..27`), normative policies (`DOC-POL-01..18`), Nov 17–19 UI/workflow reviews (`DOC-UIR-01..05`, `DOC-RPT-09..11`), and direct verification of `D:\Librarian_V2\src\resource_librarian` at commit `d9435e1` · **NO runtime code edits, NO normative policy edits, and NO live vault writes (`G:\Libraries\Resource-Library` untouched).**

---

## 1. Executive Summary & Epistemic Discipline

Following Phase 1's reconstruction of Librarian V2's ingestion, enrichment, and recovery mechanics ([02-current-state-systems-analysis.md](file:///D:/Librarian_V2/reports/2026-11-24-librarian-reconstruction-and-offering/02-current-state-systems-analysis.md), [03-proposed-librarian-tobe.md](file:///D:/Librarian_V2/reports/2026-11-24-librarian-reconstruction-and-offering/03-proposed-librarian-tobe.md)), this revised report reconstructs the **upstream policy, authority, UI, and MCP pathways that initiate, authorize, feed into, and receive completion from ingestion and enrichment**.

Instead of hiding caller initiation inside a single generic switch, this pass provides **both** a separate **`IMPLEMENTED_VERIFIED` current-state activation map** ([librarian-current-activation.spec.yaml](file:///D:/Librarian_V2/reports/2026-11-24-librarian-reconstruction-and-offering/diagrams/librarian-current-activation.spec.yaml)) connected to the preserved baseline enrichment contracts, and **three structurally distinct `PROPOSED_UNACCEPTED` L3 activation contexts** unified under the normative `action → workflow → pipeline → sprint` ladder (`DOC-POL-03` `composition.md`):

0. **Present-Day Baseline ([librarian-current-activation.spec.yaml](file:///D:/Librarian_V2/reports/2026-11-24-librarian-reconstruction-and-offering/diagrams/librarian-current-activation.spec.yaml) — `IMPLEMENTED_VERIFIED` at `d9435e1`):** Documents verified current UI (`Staging -> Add source`, `/api/folders/*`, `Chat + Attach`, `📎 Run a workflow`), MCP (`MCP_TIER_CEILING="contribute"`, zero folder MCP tools, `150s` `PERMISSION_UNANSWERED` in `Modes: Ask`), manual UI handover for `process_approved` (`curate`), `Applications/` logging, and explicit `kind: ref` links into [batch-enrichment-current.canvas](file:///D:/Librarian_V2/reports/2026-11-21-enrichment-baseline/batch-enrichment-current.canvas) and [source-enrichment-current.canvas](file:///D:/Librarian_V2/reports/2026-11-21-enrichment-baseline/source-enrichment-current.canvas) — without altering historical `DataManagement` [ingestion.canvas](file:///D:/Librarian_V2/reports/2026-11-20-workflow-map/examples/ingestion/ingestion.canvas).
1. **Context 1 ([librarian-context1-tier0-delegated.spec.yaml](file:///D:/Librarian_V2/reports/2026-11-24-librarian-reconstruction-and-offering/diagrams/librarian-context1-tier0-delegated.spec.yaml) — `PROPOSED_UNACCEPTED`):** User asks a Tier 0 agent to work with the Librarian. The human's **explicit instruction and stated scope are themselves the commission** (`spec_owner = tier0_on_behalf_of_person`, `commissioned_by: person`, `decided_by: agent`, no second approval prompt). Models full delegated in-scope permissions without repeated per-tool prompts; explicitly flags reconciliation with earlier `Rule 16` sensitivity/challenged-claim human reservations for Owner review (`OD-05`).
2. **Context 2 ([librarian-context2-external-project-mcp.spec.yaml](file:///D:/Librarian_V2/reports/2026-11-24-librarian-reconstruction-and-offering/diagrams/librarian-context2-external-project-mcp.spec.yaml) — `PROPOSED_UNACCEPTED`):** Tier 0 accesses Librarian via MCP while working on another project (`spec_owner = external_project_caller`), strictly within **bounded supporting-project authority** (`delegate`/`dispatch_plan` research delegation, `S1–S6b` source access, async queue or opt-in `stage_only` ingestion, **no library acceptance**, and `agent-authored / Core-stored Applications/`).
3. **Context 3 ([librarian-context3-human-platform-ui.spec.yaml](file:///D:/Librarian_V2/reports/2026-11-24-librarian-reconstruction-and-offering/diagrams/librarian-context3-human-platform-ui.spec.yaml) — `PROPOSED_UNACCEPTED`):** Human operates Librarian Web UI directly with **zero Tier 0 actor** (`spec_owner = person`); `Core` and UI handle scripted automation, `Lead (tier 1)` owns only delegated sub-run specifications (`sub_spec_owner = lead_tier1 <= person`), `Clerk`/`Scribe` propose semantic drafts, and **high-level curation decisions stay directly with the human**.

> [!IMPORTANT]
> **Proposal Qualification Rule:** Throughout this report and all companion diagrams, `librarian-current-activation` (`d9435e1`) represents **`IMPLEMENTED_VERIFIED`** present-day behaviour, whereas the 8 `to-be` / `context1..3` / `process-composition` specifications — and every change to **MCP authority, Context 1/2 commission envelopes, `workflow_grant` clearance, Web UI result drawers/filters/conflict merges, `record_application` fields, Ticket routing, and `Oracle`/`Doctor` runtime integration** — remain **`PROPOSED_UNACCEPTED` (`NOT ACCEPTED / NOT IMPLEMENTED`)**. Passing static checks on `.spec.yaml` / `.canvas` files verifies diagram structure only; it does **not** prove Owner acceptance or verify live Web UI, MCP, or DeepInfra runtime behaviour.

### Epistemic Status Taxonomy (`DOC-POL-01`)

| Status Tag | Meaning | Anchored Examples |
|---|---|---|
| **`IMPLEMENTED_VERIFIED`** | Observed directly in `src/resource_librarian/` (`d9435e1`), live Core APIs, or verified logs. | `MCP_TIER_CEILING="contribute"`, `MCP_PERMISSION_WAIT=150s`, `workflow_grant` on UI starts (`app.py:3147`), `decided_by_of(ctx)` (`staging.py:126`), `record_application` (`sessions.py:1948`), `ui/app.js:8472` discarding `action_done.result`. |
| **`ACCEPTED_NORMATIVE`** | Active Rank-1 Owner policy (`DOC-POL-01..04`). Never silently overridden. | `agent-roles-and-authority.md` (`DOC-POL-02` Core scripted vs agent proposals, model `assign` never `bind`), `composition.md` (`DOC-POL-03` Rules 1–17). |
| **`ACCEPTED_UNIMPLEMENTED`** | Settled target design/plan rule not yet built in runtime Python. | `composition.md` Rules 15–17 manifest permission envelopes, `W1b`/`W3`/`W5`/`W6`/`W8`/`W9` (`DOC-PLN-02`), `accepted-ingestion-tobe.canvas` (`DOC-MAP-03`). |
| **`PROPOSED_UNACCEPTED`** | Behavioural spec, diagram, UI/MCP change, or policy amendment proposed here (`NOT ACCEPTED / NOT IMPLEMENTED`). | All 8 refined `*-tobe` / `context1..3` `.spec.yaml` specs, `POL-AMEND-01..06`, `REC-17..REC-22`, extended `record_application` fields, `ORACLE_ROUTE_COLLISION` pause guard. |
| **`UNIMPLEMENTED_UNDROPPED`** | Earlier V1/V2 capability absent/partial in `d9435e1` with **no rejection decision**. | `find_components`, repo SCC `digest`, non-blocking empty-`sources_used` application logging, `**Not read:**` read-depth checks. |
| **`DECIDED_AGAINST`** | Explicitly rejected, retired, or forbidden. | `x4` auto-rollback (`composition.md` Rule 8), agent impersonating `person` (`F2` `staging.py:132`), opening repos directly as vaults (`DOC-POL-17`), `graphify` (`DOC-POL-06:159`). |
| **`UNRESOLVED_CONFLICT`** | Open conflict across policy, runtime code, or undecided Owner questions. | `POL-CONF-01..06` (§6) & Owner Decisions `OD-01..OD-08` (§10). |

---

## 2. Process Vocabulary, Core/Agent Ownership & Composition Hierarchy

Normative composition (`DOC-POL-03` `composition.md` Rules 1–17; `DOC-POL-04` `terminology.md`; `DOC-MAP-25` `compose.spec.yaml`) defines a strict upward ladder:

$$\text{L0 Action} \longrightarrow \text{L1 Workflow} \longrightarrow \text{L2 Pipeline} \longrightarrow \text{L3 Sprint}$$

- **Upward Composition Only (`Rules 1–4`):** A component may only belong to a layer at or above its own (no pipeline inside an action/workflow; no cycles).
- **Explicit Parent/Child `ref` Composition:** Every parent specification invokes child processes using typed `kind: ref` calls (`use_case: <child>`) verified by `render_spec.check_references` (`DOC-MAP-05`) against the child's exact `outcome` set (`resolved | declined | escalated` for Doctor; `success | partial | reused | paused | escalated` for enrichment, ingestion, and context sprints).
- **Downward Mandate Narrowing (`Rules 9 & 16`):** Each child receives a narrowed mandate slice (`roots`, `exclusions`, `tools`, `effects`, `allowed_partials`, `budget_ceiling`, `expires_at`) $\subseteq$ its parent's mandate. A child step or recovery action never widens parent scope.

### 2.0 Verified Current-State Activation Map & Preserved Baseline Scope (`IMPLEMENTED_VERIFIED`, `d9435e1`)

To avoid retrofitting present-day Web UI or MCP entry paths onto the historical `E:\DataManagement` `96`-paper run ([ingestion.canvas](file:///D:/Librarian_V2/reports/2026-11-20-workflow-map/examples/ingestion/ingestion.canvas)), current upstream activation is modeled separately in **[librarian-current-activation.spec.yaml](file:///D:/Librarian_V2/reports/2026-11-24-librarian-reconstruction-and-offering/diagrams/librarian-current-activation.spec.yaml)** ([notes](file:///D:/Librarian_V2/reports/2026-11-24-librarian-reconstruction-and-offering/diagrams/librarian-current-activation.md); `11` MSS steps, `30` scenarios; `Tier-0 turns = 0` MSS, `2 (ideal)` worst non-escalated) and linked via typed `kind: ref` calls directly into the preserved baseline maps ([batch-enrichment-current.canvas](file:///D:/Librarian_V2/reports/2026-11-21-enrichment-baseline/batch-enrichment-current.canvas) and [source-enrichment-current.canvas](file:///D:/Librarian_V2/reports/2026-11-21-enrichment-baseline/source-enrichment-current.canvas)):

- **Verified UI Surfaces (`person_call` / `start_action`):** `Staging -> Sources -> Add source` (`ui/app.js:6387`) and `/api/folders/*` (`app.py:4185-4273`) run at `tier="curate"` bypassing `Broker`, while `/api/folders/accept` & `approve-batch` hardcode `person=True`. `Chat + Attach` (`ui/app.js:8924`) asks tool-by-tool in `Ask` mode (`600s` wait) with no sprint envelope (`composition.md:53`). `📎 Run a workflow` (`App.start_action`, `app.py:3132`) runs at `tier="contribute"` with `workflow_grant` (exempting only `deep_read` at `read_access.py:114-120`), while `ui/app.js:8472` (`_result`) discards `action_done.result`.
- **Verified MCP Surface (`MCP_TIER_CEILING="contribute"`, `app.py:3088`):**
  - **Folder review:** **Zero MCP `@tool`s** exist for folder survey/draft/accept/approve (`tools/*.py`; HTTP `/api/folders/*` & CLI only).
  - **`consult` write/vault_write tools (`open_session`, `queue_source`, `record_application`, `run_workflow`, `run_pipeline`):** Pass `Registry` at `consult` tier (`tools/intake.py:92`, `tools/sessions.py:1940`, `tools/workflows.py:96-105`), **but hit `Broker.check()` (`broker.py:165-238`)** — waiting up to `150s` (`MCP_PERMISSION_WAIT`, `app.py:277`) then raising `PERMISSION_UNANSWERED` in `Ask` mode, or refusing `PERMISSION_DENIED` in `Plan` mode.
  - **`contribute` read tools (`delegate`, `dispatch_plan`):** Declare `tier="contribute", effect="read"` (`tools/delegate.py:37`, `tools/plan_dispatch.py:191`) — allowed on `contribute` MCP with **zero `Broker` Ask wait**, but refused (`TIER_REFUSED`) on `consult` MCP.
  - **`contribute` write tools (`ingest`, `intake_run`, `deep_read`, `staging_decide`, `staging_flag`):** Subject to `Broker` `Ask`/`Plan`, `decided_by_of(ctx) == "agent"` (`tools/staging.py:126-137`), `PERSON_CONFIRMS` when `promotion.mode != "agent"` (`staging.py:960`), and `SENSITIVITY_REVIEW` (`staging.py:957`).
  - **`curate`-only tools (`process_approved`, `batch_cancel`, `accept_workflow`, `clear_session_taint`):** Unconditionally **`TIER_REFUSED`** over MCP (`tools/batch.py:9-40`), forcing manual UI Staging handover or declared `actor={kind: "agent"}` local `/api/tool/<name>` (`app.py:4859-4870`).

### 2.1 Normative Division: Core Scripted Services vs Agent Authorship (`DOC-POL-02:33-42`)

Per normative `agent-roles-and-authority.md:33-42` (`OWNER, 22 November 2026`): **"The Core performs scripted work; agents own interpretation and proposals."** Earlier to-be specs blurred three boundaries (`batch.py` / `intake.py` reality vs proposed actor lanes); our revised specifications enforce the exact ownership split:

| Activity Domain | **Core Service Owns (Scripted / Deterministic, `$0`)** | **Agent Owns (Semantic / Judgmental — Clerk, Scribe, Lead, Tier 0)** | Verification Anchor (`d9435e1` & Policy) |
|---|---|---|---|
| **Static Code Structure & DIK Structural Extraction** | Parses static repository AST, imports, access points, symbols, and structural DIK Data (`dik.repository`, `dik.document` chapters/parts, `DATA_IS_UNFRAMED`). *Never assigned to `Clerk`.* | Explains **semantic** cross-chapter relationships (`relate` on `2+` read chapters with claims) and architecture/usage synthesis (`What Is Inside`, `Architecture & Mechanics`). | `DOC-POL-02:36`; `batch.py:475-525` (`_data`, `_relate`); `source-enrichment-tobe` `data` (`Core`) vs `relate` (`Clerk`) |
| **Content-Model Metadata & Readiness** | Derives mechanical facts (`facts.derive_axes`, extracted `dik` languages), validates proposed values against closed Content Model axes, runs `readiness()`, and stores values + explicit `Unknown`s. | **Proposes** semantic/inferred Content Model metadata fields (`metapropose`) from evidence, **retaining `Unknown` wherever evidence is insufficient** rather than guessing. | `DOC-POL-02:37-39`; `intake.py:698-701, 728-750`; `batch.py:536-566`; `source-enrichment-tobe` `metapropose` (`Clerk`) -> `metadata` (`Core`) |
| **W8 Human-Readable Titles & Neutral Descriptions** | Fetches immutable Bronze bytes, extracts literal filename/URL/PDF header/DOI metadata (`capture`), validates & stores proposed titles (`stage`). | **Proposes** a W8 human-readable Source title when the literal header is a slug/filename, neutral unframed description, `Bottom Line`, and W8 topic (`describe`, `clerkdraft`). | `DOC-POL-02:37-40`; `DOC-PLN-02` (`W8`); `intake.py:650-653, 734-753`; `ingestion-tobe` `capture` (`Core`) -> `describe` (`Clerk`) -> `stage` (`Core`) |
| **`Applications/` Records (Context 2)** | Validates `sources_used` citations against `IndexService`, checks append-only target path, writes `Applications/` Markdown + sidecar, and auto-enqueues fetchable `unresolved_sources`. | **Authors** external need, what was found/taken, what it replaced, project files/changes, and verification outcomes (`extapply`). | `DOC-POL-02:37-40`; `tools/sessions.py:1948-2049`; `context2` `extapply` (`External Tier 0`) -> `recordapp` (`Core`) |
| **Specifications, Dispatch, Checks & Persistence** | Stores versioned sprint/pipeline specs (`commissioned_by`, `mandate_id`), executes schema/hash/locator checks, manages `StagingStore` / `PromotionGuard` / `IndexService`, dispatches workers, and logs Tickets. | Owns sprint/session goals (`Human` / `Tier 0`), execution oversight (`Lead`), independent verdicts (`Oracle`), and bounded repair execution (`Doctor`). | `DOC-POL-02:39-42, 85-96` |

### 2.2 Explicit `kind: ref` Composition Graph & Specification Ownership (`9` Validated Diagrams)

```text
Current-State Graph (`IMPLEMENTED_VERIFIED`, d9435e1):
  librarian-current-activation (11 steps, 30 scenarios)
    ├──[ref: UI paperclip]──> source-enrichment-current (14 steps, 29 scenarios; baseline)
    └──[ref: curate batch]──> batch-enrichment-current (5 steps, 16 scenarios; baseline)
                                └──[ref: source]──────────> source-enrichment-current
  (Historical Nov 19-20 E:\DataManagement trace preserved separately at ingestion.canvas)

Proposed To-Be Composition Stack (`PROPOSED_UNACCEPTED` — NOT accepted/implemented):
  librarian-process-composition-tobe (actor-laned L3->L0: 9 steps, 22 scenarios)
    ├──[ref: Context 1]──> librarian-context1-tier0-delegated (9 steps, 16 scenarios)
    │                         ├──[ref: L2]──> librarian-ingestion-tobe (20 steps, 43 scenarios)
    │                         └──[ref: L1]──> librarian-doctor-tobe (6 steps, 13 scenarios)
    ├──[ref: Context 2]──> librarian-context2-external-project-mcp (8 steps, 12 scenarios)
    │                         ├──[ref: L2, stage_only opt]─> librarian-ingestion-tobe
    │                         └──[ref: L1]─────────────────> librarian-doctor-tobe
    └──[ref: Context 3]──> librarian-context3-human-platform-ui (12 steps, 23 scenarios; 0 Tier-0 lanes)
                              ├──[ref: L2, UI Batch]──> librarian-batch-enrichment-tobe (10 steps, 21 scenarios)
                              ├──[ref: L2, Chat Lead]─> librarian-ingestion-tobe
                              └──[ref: L1]────────────> librarian-doctor-tobe

Shared Pipeline & Child Stack (`PROPOSED_UNACCEPTED`):
  librarian-ingestion-tobe ──[ref: L2]──> librarian-batch-enrichment-tobe
                           └──[ref: L1]──> librarian-doctor-tobe (R1/R2, R1-Geo, R4, R5/R6)
  librarian-batch-enrichment-tobe ──[ref: L1]──> librarian-source-enrichment-tobe (21 steps, 23 scenarios; includes reviewchk)
                                  └──[ref: L1]──> librarian-doctor-tobe
  librarian-source-enrichment-tobe ──[ref: L1]──> librarian-doctor-tobe
```

| Activation Context / Layer | Top-Level `spec_owner` | Delegated Sub-Run `sub_spec_owner` | Attribution Recorded |
|---|---|---|---|
| **Context 1 (User -> Tier 0 -> Librarian)** | **`tier0_on_behalf_of_person`** (from user instruction + scope) | **`lead_tier1`** (`sub_spec <= parent_spec`; never widens) | `commissioned_by: person`, `decided_by: agent` |
| **Context 2 (External Project -> MCP)** | **`external_project_caller`** (Project $P$ MCP grant) | **`lead_tier1`** (`sub_spec <= Context-2 read/stage_only`) | `attested_by: "agent"`, `no vault accept` |
| **Context 3 (Direct Web UI, zero Tier 0)** | **`person`** (UI user directly) | **`lead_tier1`** (`sub_spec <= person`; delegated chat/workflow only) | `caller_kind: "person"`, `curate` / `workflow_grant` |

---

## 3. Activation Context 1 — User Asks a Tier 0 Agent to Work with the Librarian

- **Model:** [librarian-context1-tier0-delegated.spec.yaml](file:///D:/Librarian_V2/reports/2026-11-24-librarian-reconstruction-and-offering/diagrams/librarian-context1-tier0-delegated.spec.yaml) (`PROPOSED_UNACCEPTED`; `9` MSS steps, `16` scenarios; `Human user` MSS steps = **`2`** [instruct once, receive completion once]; `Tier-0 turns = 2 (ideal)` on MSS and worst non-escalated paths).

### 3.1 Single-Commission Delegation & Policy Reconciliation (`OD-05`)

When a human explicitly instructs an external Tier 0 agent (Codex, Claude Code, Antigravity) to work with the Librarian on their behalf:
- **Initiator & Commission:** The **Human user's explicit instruction and stated scope ARE the commission** (`request`, Step 1).
- **No Second Approval Step:** Tier 0 translates the user's instruction into the L3 Sprint specification (`spec_owner = tier0_on_behalf_of_person`) and approves its `Rule 15` predicted manifest envelope **on the user's behalf** (`commission`, Step 2; literally matching `composition.md:36` Rule 15). `Core` validates well-formedness & scope bounds (`denv`) and stores `mandate_id` (`commissioned_by: person`, `decided_by: agent`, `storeenv`, Step 3).
- **Reconciling Earlier `Rule 16` Human Reservations (`OD-05` — Not Silently Preserved or Erased):** Earlier policy text (`agent-roles-and-authority.md:62`, `composition.md:37` Rule 16) reserved sensitivity and challenged-claim decisions strictly for `person`, regardless of which agent asked. By contrast, the user directed that when Tier 0 acts on their behalf in Context 1, it holds the permissions needed to perform the delegated in-scope work without repeated permission gates. Therefore:
  - `librarian-context1-tier0-delegated` (`policy_note`, `commission`, `storeenv`) and `librarian-ingestion-tobe` (`dfolderauth`, `leadfolder`, `dgate2`, `leadaccept`) model full in-scope Context-1 execution (`commissioned_by: person`, `decided_by: agent`, preserving sensitivity/challenged-claim audit flags and zero repeated prompts) as **`PROPOSED_UNACCEPTED`**.
  - Whether any narrow safety/governance exception (specifically `SENSITIVITY_REVIEW`, `REVIEW_CHALLENGED`, global vault `promotion.mode` / `accept_workflow` / `capability_install`, or `ORACLE_ROUTE_COLLISION`) stays human-only even inside Context 1 is explicitly recorded as **Owner Decision `OD-05`** rather than silently assuming either the old blanket block or unflagged bypass.
  - Meanwhile, **Context 3** (human using the Web UI directly without Tier 0) remains unchanged and distinct: high-level curation and acceptance decisions remain directly with the human (`reviewgate1..reviewgate2`).
- **How Authority Flows Downward & Saves Tokens:** `storeenv` conveys `mandate_id` to `Lead (tier 1)` (`leaddispatch`, Step 4: `sub_spec_owner = lead_tier1 <= parent`), invoking `librarian-ingestion-tobe` (`callingest`, Step 5) without mid-run `Broker` Ask stalls (`F-03`) or Tier 0 manually reading chunks.

### 3.2 Routine Delegated Work vs Genuine Out-of-Scope, Critical & Hazard Surfaces (Context 1)

| Decision / Work Class | Exact Scope Inside Context 1 Commission (`PROPOSED_UNACCEPTED`) | Handling Inside `librarian-context1-tier0-delegated` |
|---|---|---|
| **Delegated Routine Work (Uninterrupted Within Instruction Scope)** | • Surveying specified roots & excluding scratch trees (`$0`)<br>• In-scope folder screening & approval (`leadfolder`)<br>• Capturing Sources, proposing W8 titles/descriptions/fields, & Gate 1 `Approve`<br>• Starting `process_approved` (`mandate_id`) + 9-stage source/folder enrichment<br>• Bounded `Doctor` R1–R6 accepted YAML repairs inside mandate (`attempt <= 1`)<br>• Gate 2 in-scope cataloguing/acceptance (`leadaccept`: `commissioned_by: person, decided_by: agent`, sensitivity/claim flags preserved) | **Zero repeated prompts.** Executed autonomously by `Lead` + DeepInfra roles + `Core`, checked by distinct `Oracle` route, and summarized once in `t0deliver -> userack` (with spend, coverage, deferrals & tickets). |
| **Out-of-Scope, Uncommissioned Governance & `OD-05` Holds (Paused cleanly)** | • Target roots, folders, or actions **outside** user's stated instruction/scope (`Rule 16` widening)<br>• Budget increases above user-stated ceiling (`MC-10` / `14a`)<br>• Uncommissioned standing global governance changes (`promotion.mode`, `accept_workflow`, `capability_install`, uncommissioned external `project_edit`/`sandbox_output`)<br>• Any Owner-retained **`OD-05`** safety exception (`SENSITIVITY_REVIEW`, `REVIEW_CHALLENGED`) & **`ORACLE_ROUTE_COLLISION`** (`review_status = unverified_route_collision`) | Rejected at preflight (`denv [2a]` -> `pausecancel -> usercancel`) or packaged as a single Ticket (`t0ticket` / `collisionrec` -> `t0surface -> userchoice -> epaused`) with spend & resume link. |
| **Critical Security, Data-Loss & Authority Breaches (Immediate Route)** | • Critical security, data-loss, or authority-boundary breaches arriving via `callingest [escalated 5d] -> dcrit` or `dverdict [6c]` | **Bypass `Doctor` retry loops** (`dcrit` routes straight to `escrec -> failnotify -> useresc -> eescalated` with Ticket ID, flags, evidence hashes, spend, & Rule-8 shown compensation). |

### 3.3 Context 1 Exits & User-Facing Notification (`t0deliver` + Agenda)

Every Context 1 path notifies the **Human user** in their active Tier 0 session AND persists an Agenda/delivery receipt in `Core` (`packagereceipt`):
- `success`: `t0deliver -> userack` reports promoted note paths/links, Geo-Grapher coverage, `MC-10` spend, deferred optional lenses/topics queued in Staging, and distinct `Oracle` verdict.
- `partial`: `partnotify -> userpartial` reports completed notes beside explicit `not_examined` coverage gaps, quarantined siblings, and open Tickets.
- `reused`: `t0notifyreuse -> userreuse` confirms unchanged `NAT-13`/folder receipts reused at `$0` extra spend.
- `paused`: `usercancel` (invalid/out-of-scope commission), `userchoice` (boundary, hazard, or `ORACLE_ROUTE_COLLISION`), or `userdecline` (declined Doctor Ticket + Rule-8 shown compensation) gives the exact resume target without mid-run hangs.
- `escalated`: `failnotify -> useresc` alerts the Human user immediately with Ticket ID, failing stage, raw evidence hashes, and Rule-8 compensation plan.

---

## 4. Activation Context 2 — Tier 0 Accesses Librarian via MCP While Working on Another Project

- **Model:** [librarian-context2-external-project-mcp.spec.yaml](file:///D:/Librarian_V2/reports/2026-11-24-librarian-reconstruction-and-offering/diagrams/librarian-context2-external-project-mcp.spec.yaml) (`PROPOSED_UNACCEPTED`; `8` MSS steps, `12` scenarios, `Tier-0 turns = 2 (ideal)`, `0` intersections).

### 4.1 Explicit Context 2 Delegated-Authority Boundaries (Distinct from Context 1 & Context 3)

Context 2 serves an **external project $P$** (e.g., coding/debugging another repository), NOT vault curation. To prevent Context 2 from silently inheriting Context 1's vault curation authority or assuming Context 3's interactive Web UI flow, its authority is explicitly bounded across five operations:

| Authority Operation in Context 2 | **Verified Current Behaviour (`d9435e1` `IMPLEMENTED_VERIFIED`)** | **Proposed Explicit Context 2 Boundary (`PROPOSED — NOT ACCEPTED / NOT IMPLEMENTED`)** | Why Distinct from Context 1 & Context 3 |
|---|---|---|---|
| **1. Parallel Research Delegation (`delegate`, `dispatch_plan`)** | `app.py:3106` wires `helper_provider` on `mcp_call`; both tools declare **`tier="contribute", effect="read"`** (`delegate.py:37`, `plan_dispatch.py:191`) — zero Broker Ask wait on `contribute` MCP, **but `TIER_REFUSED` on `consult` (Reader) MCP connections**. | Grant bounded **`consult` read-with-budget** clearance (`POL-AMEND-03`) for `delegate` and `dispatch_plan` within explicit `helper_budget` / `effort` limits, returning durable `ref:` handles under `Lead`/`Clerk`/`Scribe` without touching frontier tokens or vault state. | Parallelizes read-only research for Project $P$ without requiring write-tier (`contribute`) or vault curation grants. |
| **2. Source Access (`search`, `get_note`, `read_source_section`, `verify_source_pages`, `read_file`)** | Reads catalogued notes & Geo packets (`consult`). Direct unchunked third-party raw file reads raise `THIRD_PARTY_ROUTE_REQUIRED` (`read_access.py:132`) unless scoped through catalogue -> graph -> section -> page verify or a person checkpoint. | Preserve strict `S1–S6b/R` third-party conversion/section/page bounds (`DOC-POL-06`, `DOC-POL-08`) and `read_access` chunk isolation; prohibit raw third-party dumps into Project $P$ (`publication_review` taint guard `broker.py:198-204`). | Protects third-party copyright/scope while Project $P$ extracts verified answers. |
| **3. Missing-Source Ingestion (`queue_source`, `ingest`, `librarian-ingestion-tobe`)** | `queue_source` (`tier="consult", effect="write"`, `tools/intake.py:92`) & `ingest` (`contribute`) hit `Broker` (`150s` `PERMISSION_UNANSWERED` if UI is in Ask mode; `Plan` denies); `ingest` stops at `staged`; **zero MCP folder tools exist**; `process_approved` refuses (`TIER_REFUSED`). | **Default:** non-blocking `queue_source` / `unresolved_sources` (async `queued`, `5a`). **Conditional:** when Project $P$ explicitly authorizes scoped `stage_only` capture/enrichment (`5b`), `Lead` sets narrowed `sub_spec_owner=lead_tier1 <= Context 2` into `librarian-ingestion-tobe` — never vault-wide folder reorganizations. | Prevents Librarian intake delays from hijacking Project $P$'s build loop. |
| **4. Library Acceptance / Promotion (`staging_decide('accept')`, Topics, Lenses)** | Blocked for `promotion.mode="person"`, sensitivity (`staging.py:957-962`), & `curate` tools (`app.py:3088`). | **Explicitly EXCLUDED from Context 2 by default.** Any Sources staged/enriched under Context 2 (`5b`) stop at `staged` / `enriched` and queue on the **Librarian Agenda** (`queuepause`) for Context 3 UI review or a dedicated Context 1 curation commission. | Keeps Project $P$'s external agent from mutating canonical `Sources/` taxonomy under project urgency. |
| **5. Recording `Applications/` (`record_application`, `sessions.py:1940-2049`)** | Declares **`tier="consult", effect="vault_write"`** (passes `Registry` at `consult`, **hits `Broker` `Ask` 150s / `Plan` deny**), writes append-only `Applications/Application - <title>.md` (`attested_by: "agent"`) + sidecar, auto-enqueues fetchable `unresolved_sources`, & **refuses empty `sources_used` (`:1961`)**. | **External Tier 0 authors** the `Application` proposal (`extapply`, Step 6); **Core validates citations, stores append-only note & sidecar, and queues `unresolved_sources` (`recordapp`, Step 7)**. Proposed extensions (`POL-AMEND-06`): snapshot/locator `source_refs`, `external_constraints`, `verification`, and `sources_used=[]` workaround logging. | Links Source, Project $P$ need, and precedent cleanly even when catalogue gaps forced a workaround. |

### 4.2 Detailed `Applications/` Repeatability Contract (`record_application` — Current vs Proposed)

Direct code inspection of `src/resource_librarian/tools/sessions.py:1948-2049` shows:
- **Verified Implemented Today (`d9435e1`):** Validates `sources_used` against `IndexService` (`:1957`), auto-runs `_intake.capture` + `_intake.enqueue(..., f"named in {name}", session.id)` on fetchable `unresolved_sources` (`:1978-1986`), renders `What Was Needed`, `What Was Found And Taken`, `What It Replaced`, `What The Catalogue Should Learn`, `Not Yet In The Library`, `Project Files` (`[:60]`), and typed `Changes` (`proposed|applied` + `outcome`, `:1998-2004`), prevents accidental overwrites (`:1968`), and writes a project-sidecar JSON pointer via `_link_project_application` (`:2033-2048`).
- **Remaining Gaps & Proposed Extensions (`PROPOSED — NOT ACCEPTED / NOT IMPLEMENTED`):**
  1. **Pin Exact Source Snapshots & Locators (`source_refs`):** Bare `[[note]]` wikilinks (`:1972`) do not record `note_revision`, `evidence_sha256`, `graph_snapshot_id`, or section/page `cite_as` coordinates — future runs cannot tell whether the cited Source changed or which exact claim supported the change.
  2. **Preserve External Constraints & Repeatability Predicates:** Add structured `external_constraints` (runtime/OS/version/licence boundary) and `reusable_when` / `not_when` fields so future agents evaluate fit without rediscovering why an old workaround applied.
  3. **Preserve Verification Evidence & Lifecycle Status:** Add structured `verification` (`command_or_check`, `observed_result`) and `evaluation_status` (`applied_unverified | verified_repeatable | superseded | reverted`).
  4. **Allow `sources_used=[]` Gap/Workaround Logging (`:1961-1964`):** Removing the `TypeError` block when `sources_used` is empty lets external agents preserve `Project Files`, `Changes`, rationale, and auto-queued `unresolved_sources` when no catalogued source matched (`outcome="no_match_workaround"`).

### 4.3 Context 2 Dual Handover & User Notification (`extapply` / `recordapp` -> `userhandover`)

Every Context 2 path notifies the human in **both** places: (1) **immediate deliverable in External Project $P$** via Tier 0 (diffs, verification outcome, cited `[[Source]]` + snapshot locators or partial/queued caveat, link to `Applications/Application - <title>.md`), and (2) **asynchronous Librarian Vault notification** (`Core` Agenda / Staging count showing `queued` leads, `stage_only` enriched Sources awaiting acceptance, or `PERMISSION_UNANSWERED` / `Doctor` Tickets without blocking Project $P$).

---

## 5. Activation Context 3 — Human Uses the Librarian Platform Directly (Zero Tier 0)

- **Model:** [librarian-context3-human-platform-ui.spec.yaml](file:///D:/Librarian_V2/reports/2026-11-24-librarian-reconstruction-and-offering/diagrams/librarian-context3-human-platform-ui.spec.yaml) (`PROPOSED_UNACCEPTED`; `12` MSS steps, `23` scenarios, **zero Tier 0 lane**, `0` intersections).

In Context 3, **no Tier 0 agent is inserted or assumed**. The Librarian Web UI (`src/resource_librarian/ui/app.js`) and `Core` (`app.py`) handle deterministic scripted operations, `Lead (tier 1)` coordinates semi-automated flows, `Clerk (tier 2)` / `Scribe (tier 3)` draft semantic proposals, and the **Human retains all high-level curation and acceptance decisions**.

### 5.1 Actual UI Entry Points & Review / Staging Decisions (`d9435e1` Verified vs Proposed UI Targets)

| UI Surface / Decision Point | **Verified Current Behaviour (`d9435e1`, `ui/app.js` & `app.py`)** | **Proposed Target Behaviour (`PROPOSED — NOT ACCEPTED / NOT IMPLEMENTED`)** |
|---|---|---|
| **Initiation (`ui_entry -> dentry`)** | Three real UI paths exist (`IMPLEMENTED_VERIFIED`): (a) `Staging -> Sources -> Add source` (`URL/arXiv/DOI/repo` or `Choose a file…`, `app.js:6387-6449`); (b) `Chat` + `📎 Attach` talking to in-app `Lead` (`:8924-8955`); (c) `📎 -> Run a workflow` via `App.start_action` (`app.py:3132-3175`) attaching `workflow_grant` (`tier="contribute"`). | Allow in-app `Lead` delegation from `Chat` into `ref: librarian-ingestion-tobe` (`leaddeleg`), and generalize `read_access` chunk clearance from `workflow_grant` manifests (`POL-AMEND-04`) instead of only `spec.name == "deep_read"` (`read_access.py:114-120`). |
| **Staging Status Filter (`Which sources`)** | `app.js:6325-6332` lists `staged`, `approved`, `enriched`, `partial`, `queued`, `failed`, `deferred`. **Live Defect (`DOC-UIR-01` Item 5):** `app.js` omits `processing` and `accepted` even though `staging.py:185-186` supports both, causing `"0 waiting"` confusion while batches run or post-accept. `Show 50 more` (`:6686-6698`) already loops `offset` in 50-row pages (`:6619-6625`). | **Proposed UI Fix (`REC-19`):** Expose `processing` and `accepted` in `Which sources` + active batch count badge, plus cursor/offset parity for API/MCP callers (`F-01`). |
| **Source Gate 1 & Batch Start (`reviewgate1 -> dgate1choice -> startbatch`)** | Human inspects `View source evidence` (`Evidence beside draft` / `on demand`, `:6314`), ticks rows (`:6523-6583`) or opens single item, chooses **`Approve for ingestion`**, **`Accept as captured`**, **`Reject`**, or **`Defer`**, then clicks **`Process approved sources`** (`process_approved`, `curate` tier via `person_call`) on the `paintBanner` (`:6840-6939`) to launch `ref: librarian-batch-enrichment-tobe`. | Preserve direct Human Gate 1 & explicit batch start (`curate`), feeding into the upgraded `librarian-batch-enrichment-tobe` (with `MC-10` spend controls, Core-vs-Clerk metadata/AST separation, and `Doctor R1–R6`). |
| **Generated Summaries (`Bottom Line`, `What it solves`, `Title`)** | `Clerk` drafts via `staging_review` / `intake.describe`, flagging `not_confident` (`:7177`) and listing `dropped` ungrounded lines (`:7189`); Human edits `Bottom Line` / `What it solves` or clicks `Draft with the clerk` / `Redraft` / `Deep read`. **Live Defect (`DOC-UIR-04` `F-09`):** Concurrent background writes trigger `decisionError` showing only **`Reload item (discards form edits)`** (`app.js:6940-6949`). | **Proposed (`REC-19` + Feedback #2):** `Clerk` proposes W8 titles (when literal headers are slugs/filenames), summaries, and semantic fields (with explicit `Unknown`s) while `Core` stores them; UI preserves unsaved human `Bottom Line` / `What it solves` edits cleanly during `F-09` revision refresh. |
| **Search-Index & Findability (`promoteindex -> oracleverify -> dindex`)** | Synchronous `PromotionGuard` writes `Sources/` note + SQLite FTS (`IndexGateway`); deferred `_StagingEmbeddingContinuation` (`staging.py:25-99`) updates vectors post-write, reporting `not_findable` (`:96-99, 754-755`) and `embedding_warnings` (`app.js:7032`) without deleting the note. Users manually run `Rewrite indexes` (`views_refresh`, `:5157-5169`). `Search` UI retains `F-12` facet limits on `Unfiled`-only vaults. | **Proposed (`REC-19`, `W9`):** Distinct `Oracle` route verifies post-promotion findability; `not_findable` / `embedding_warnings` trigger bounded `Doctor R5` (`Rewrite indexes`); `ORACLE_ROUTE_COLLISION` pauses/flags cleanly on UI Agenda (`uiagenda`, `ext: 10c`) instead of claiming independent review. |
| **Workflow & Completion Notifications (`uinotify -> userdone`)** | **Live Defect (`DOC-UIR-05` Defect 1):** `ui/app.js:8472` (`const { type: _type, result: _result, at: _at, ...row } = event;`) **silently discards `action_done.result`**, leaving finished/paused `📎` workflow chips without outputs or pause details. | **Proposed UI Fix (`REC-19`, `REC-22`):** Surface an explicit **Workflow Result Drawer** rendering `action_done.result` (promoted notes, coverage, deferred tabs, `not_examined`, Ticket IDs) alongside Staging banners and Agenda badges. |

---

## 6. Authority, Routing & Policy Reconciliation (`POL-CONF-01..06` & Proposed Amendments)

Per instructions, **no normative policy file is altered or silently overridden**. The table below records six exact conflicts between current normative policy/intent, runtime code (`d9435e1`), and the three clarified activation contexts — pinpointing where UI interaction modes or static tool tiers are misapplied as security barriers.

### 6.1 Conflict & Category-Error Ledger (`UNRESOLVED_CONFLICT` vs `d9435e1`)

| Conflict ID | Normative Policy vs Verified Code (`d9435e1`) | Category Error / Practical Effect |
|---|---|---|
| **`POL-CONF-01`** | `composition.md:36` (`Rule 15`) says *"The person, **or tier 0 for an agent-run sprint**, approves the envelope... Inside it, nothing is asked again."* In `d9435e1`, `broker.py:175-188` grants `workflow_grant` ONLY to UI `App.start_action` and `batch.start` (`"an agent's call never does"`), while `app.py:277, 3107` applies `Modes: Ask` across MCP (`MCP_PERMISSION_WAIT=150s`), failing `PERMISSION_UNANSWERED` unless the human clicks Librarian's Web UI `Chat` tab (`F-03`). | **Category Error:** `Modes: Ask` is an **in-app UI interaction preference**, not an access-control boundary. Applying UI `Chat` confirmations per write tool to an already-commissioned Context 1 sprint or authorized Context 2 session stalls work across windows without adding security. |
| **`POL-CONF-02`** | `agent-roles-and-authority.md:23, 62` states *"The current MCP cap is `contribute`; delegated authority must be granted explicitly and does not include the person's reserved decisions"*, while `d9435e1` exposes **zero MCP folder review tools** and hardcodes `MCP_TIER_CEILING="contribute"` (`app.py:3088`), blocking Context 1 Tier 0 from `process_approved` (`curate` at `tools/batch.py:9`) and sensitivity/person-mode staging (`staging.py:957-962`) despite `decided_by_of` provenance attribution. | **Identity vs Delegated Commission & Policy Reconciliation Needed:** `decided_by_of(ctx)` already prevents person-impersonation (`commissioned_by: person, decided_by: agent`). Continuing blanket MCP blocks frustrates Context-1 user delegation, while removing sensitivity/challenged-claim reserves touches `agent-roles-and-authority.md:62` & `Rule 16` — explicitly placed before Owner as **`OD-05`**. |
| **`POL-CONF-03`** | `app.py:3142` runs UI `📎` workflows (`start_action`, `caller_kind="person"`) at `tier="contribute"`, forcing `read_access.py:114-120` to hardcode a single-tool exception for `spec.name == "deep_read"`. | **Routing Brittleness:** Any future or composite person-started UI workflow touching other read-access paths hits `THIRD_PARTY_ROUTE_REQUIRED` unless manifest clearance derives cleanly from `workflow_grant`. |
| **`POL-CONF-04`** | `tools/delegate.py:37` and `tools/plan_dispatch.py:191` require `tier="contribute"` with `effect="read"`, allowing `contribute` MCP callers to run DeepInfra helpers without Ask waits while blocking **`consult` Reader** MCP connections (`TIER_REFUSED`). | **Capability Conflation (Context 2):** Blocks `consult` Reader MCP connections from offloading parallel read-only research to DeepInfra helpers, pushing frontier-token consumption onto the external Tier 0 harness. |
| **`POL-CONF-05`** | `open_session`, `queue_source`, `record_application`, `run_workflow`, and `run_pipeline` sit at `tier="consult"` (`tools/intake.py:92`, `sessions.py:1940`, `workflows.py:96-105`) with `effect="write"/"vault_write"`; `_run_effect` (`broker.py:300-322`) keeps routed workflows classified `"write"` on any routed step, triggering `150s` `Ask` timeouts or `Plan` denials over MCP. | Forces interactive Web UI Chat confirmation waits on `consult`-tier MCP project tracking (`queue_source`, `record_application`) and routed synthesis in Context 2. |
| **`POL-CONF-06`** | `agent-roles-and-authority.md:69, 113-118` assigns both `Doctor` and `Oracle` currently to `GLM-5.3` while requiring separate contexts and an independent assignment when the worker shares that route. Code (`d9435e1`) has neither a runtime `Oracle`/`Doctor` engine (`W9`) nor a fail-closed fallback when zero distinct qualified `Oracle` routes exist. | Risk that a worker and reviewer sharing `GLM-5.3` falsely accept unverified output without independent review (`DOC-GEO-03:35` `FP4` lesson). |

### 6.2 Proposed Policy Amendments & Clarifications (`PROPOSED — FOR OWNER REVIEW (NOT ACCEPTED)`)

> [!WARNING]
> All six items below (`POL-AMEND-01..06`) are **proposed text for Owner review (`NOT ACCEPTED / NOT IMPLEMENTED`)**. Current `docs/policy/*.md` remains authoritative until explicitly amended by the Owner.

| Amendment ID | Target Document | Proposed Policy Revision / Clarification (**`PROPOSED — NOT ACCEPTED`**) | Reconciles |
|---|---|---|---|
| **`POL-AMEND-01`** | `agent-roles-and-authority.md` §Tier 0 & `composition.md` Rule 15–16 | *"In **Context 1** (user explicitly directs Tier 0 to work with Librarian), the user's instruction and stated scope constitute the commission; Tier 0 authors the L3 Sprint spec (`spec_owner=tier0_on_behalf_of_person`) and approves its `Rule 15` envelope on the user's behalf with **no second approval prompt**. Within that commissioned scope, `Core` grants delegated execution across folder intake, Gate 1, `process_approved`, bounded `Doctor` recovery, and Gate 2 in-scope cataloguing/acceptance, recording `commissioned_by: person, decided_by: agent` (`decided_by_of`). What escalates/pauses back to the user covers: (a) **out-of-scope expansions** or budget increases beyond stated instruction, (b) **uncommissioned global governance/repertoire changes** (`promotion.mode`, `accept_workflow`, `capability_install`, uncommissioned external writes), (c) **`ORACLE_ROUTE_COLLISION`** & critical faults, plus **`OD-05` Owner disposition** on whether `SENSITIVITY_REVIEW` and `REVIEW_CHALLENGED` stay human-only or run inside explicit Context-1 scope with flagged audit logs. In **Context 2** (`spec_owner=external_project_caller`), authority stays capped to read/helper/scoped-intake/`Applications/` without implicit library acceptance. In **Context 3** (direct UI, no Tier 0, `spec_owner=person`), high-level curation decisions remain directly with the human."* | `POL-CONF-01`, `POL-CONF-02`, `OD-05` |
| **`POL-AMEND-02`** | `agent-roles-and-authority.md` (New Subsection) | *"`Modes: Ask / Auto / Plan` controls step-by-step confirmation inside the Web UI Chat loop; it is an **interaction preference**, not an access-control boundary. Verified Context 1 commissioned sprints (`mandate_id`), scoped Context 2 helper/apply envelopes, and Context 3 `workflow_grant` UI runs lift per-write `Ask` waits inside declared bounds while enforcing `Registry` scope, `read_access`, `PromotionGuard`, and explicit boundary gates."* | `POL-CONF-01`, `POL-CONF-05`, `F-03` |
| **`POL-AMEND-03`** | `agent-roles-and-authority.md` §External Project Access & `delegate.py` / `plan_dispatch.py` | *"Strictly read-only DeepInfra research delegation (`delegate` with `HELPER_TOOLS` at internal `tier='consult'`, and `dispatch_plan` read-only DAGs) operates as **`consult` read-with-budget** governed by an explicit `helper_budget` / `effort` cap rather than `contribute` write tier, permitting Context 2 `consult` MCP connections to offload parallel reading safely."* | `POL-CONF-04`, Feedback #3 |
| **`POL-AMEND-04`** | `composition.md` Rule 15 & `app.py::start_action` | *"A person-started Web UI `📎` workflow (`Context 3`, `caller_kind='person'`) derives bounded third-party chunk-reading clearance cleanly from its validated manifest + `workflow_grant`, replacing single-tool string exceptions (`read_access.py:114`) while banning unchunked raw third-party leakage."* | `POL-CONF-03` |
| **`POL-AMEND-05`** | `agent-roles-and-authority.md` §Review & Model Assignment | *"Model choices are **assigned** via `.librarian/agents/routes.json` / adapters and stay permanently revisable (`GLM-5.3` is the current `Doctor`/`Oracle` assignment, never hard-coded). If `oracle_route == worker_route` (or `doctor_route`), `Core` first selects a distinct qualified `Oracle` route from `routes.json`. **If zero distinct qualified `Oracle` routes exist, `Core` MUST NOT mark the output or repaired Ticket independently reviewed/resolved: it stamps `review_status = 'unverified_route_collision'` and transitions required-review paths to `paused` (`Ticket: ORACLE_ROUTE_COLLISION`)** for Owner route assignment or explicit person-attested override in UI."* | `POL-CONF-06`, Feedback #4 |
| **`POL-AMEND-06`** | `docs/product-contract.md` & `tools/sessions.py::record_application` | *"`record_application` records Core-validated Vault records from agent-authored external-project proposals, supporting `source_refs` snapshots/locators (`note_revision`, `evidence_sha256`, `graph_snapshot_id`, `cite_as`), `external_constraints`, `verification`, `evaluation_status`, and optional `sources_used=[]` (`outcome='no_match_workaround'`) when `unresolved_sources` / `needed` log a catalogue gap."* | Feedback #2 & #3, `sessions.py:1948-2049` |

---

## 7. Routed Ticket Service & Revisable Model Assignment / Route-Collision Fallback

### 7.1 Canonical Structured Ticket Schema (`PROPOSED — NOT ACCEPTED / NOT IMPLEMENTED`)

Per `DOC-POL-02:90-96` and `DOC-MAP-28`, faults, hazards, and route collisions become structured **Tickets** in `.librarian/tickets/<id>.json`:

```json
{
  "ticket_id": "tkt-20261124-0042",
  "origin_diagram": "librarian-ingestion-tobe",
  "extension_id": "17c",
  "remedy_candidate": null,
  "activation_context": "context1_tier0_delegated",
  "mandate_id": "mnd-...",
  "flags": ["ORACLE_ROUTE_COLLISION", "review_status:unverified_route_collision"],
  "severity": "human_decision_hold",
  "evidence": {
    "item_id": "staged-...",
    "stage": "oraclefinal",
    "worker_route": "deepinfra/zai-org/GLM-5.3",
    "oracle_route_attempted": "deepinfra/zai-org/GLM-5.3",
    "distinct_qualified_oracle_routes": [],
    "hashes": {"source_sha256": "...", "nodes_sha256": "..."}
  },
  "accountable_owner": "Owner (assign distinct Oracle route or inspect unreviewed output)",
  "repair_history": [],
  "compensation_shown": {"tool": null, "note": "Rule 8: display only; never auto-executed"},
  "oracle_recheck": {"status": "blocked_route_collision", "independent_review_claimed": false},
  "notification": {
    "target": ["human_user_active_session", "librarian_agenda"],
    "status": "paused_pending_owner"
  }
}
```

### 7.2 Revisable `GLM-5.3` Role Assignment & Concrete `ORACLE_ROUTE_COLLISION` Fallback (Feedback #4)

1. **Adaptable Assignment (`assign`, never `bind`):** `GLM-5.3` is recorded strictly as the **current owner assignment** for `Doctor` and `Oracle` (`DOC-POL-02:113`) via `.librarian/agents/routes.json` and role adapters — replaceable at any time without modifying workflows or Core orchestration.
2. **Isolated Contexts & Raw-Evidence Input:** `Doctor` and `Oracle` never share conversation history with workers or each other (`DOC-POL-02:68-69`); `Oracle` sees only raw evidence, schemas, and deterministic Core receipts (`DATA_IS_UNFRAMED`).
3. **Concrete Fallback When `oracle_route == worker_route` (or `oracle_route == doctor_route`):**
   - **Step 1 (Adapter Lookup):** `Core` inspects `.librarian/agents/routes.json` for any secondary **qualified** `Oracle`-eligible route whose model/provider endpoint differs from `worker_route` (and `doctor_route` on recheck).
   - **Step 2 (Secondary Assignment Exists):** `Core` temporarily assigns that distinct qualified route for this isolated `Oracle` verdict and records both `assigned_route` and `collision_bypassed: true` in the Ticket/audit log.
   - **Step 3 (Zero Distinct Qualified Routes Exist — Fail-Closed):** **The system MUST NOT label the output or repaired Ticket "independently reviewed" or "resolved".** `Core` stamps `review_status = "unverified_route_collision"` (`independent_review_claimed: false`), emits a **`paused` Ticket (`ORACLE_ROUTE_COLLISION`)** across all relevant diagram checks (`Context 1 dverdict [6d]`, `Context 3 dindex [10c]`, `Ingestion dbatchscreen [14c] & doracle [17c]`, `Batch dverdict [9d]`, `Source dverdict [20d]`, `Doctor doracle [5a]`, `Process Composition dor_comp [7a]`), preserves already-completed work safely, and notifies the user (Context 1/3) so they can assign a second qualified route — or, in Context 3 UI, record an explicit person-attested unreviewed acceptance.

### 7.3 Immediate Critical Fault Routing vs. Bounded Noncritical Recovery (`TKT-CRIT-01`)

All specs cleanly separate **critical security, data-loss, or authority-boundary breaches** from **routine noncritical shortfalls** (`DOC-POL-02:76-79, 90-96`):
- **Immediate Critical Path (Zero Doctor Retry Loops):** `Context 1 dcrit` / `dverdict [6c] -> escrec -> failnotify -> useresc -> eescalated`; `Context 2 dcrit_ex -> escticket -> notifyesc -> useresc -> eescalated`; `Context 3 duicrit` / `dindex [10b] -> uiesc -> useresc -> eescalated`; `Ingestion droot [3b]` / `dgeo [7c]` / `dbatchscreen [14d]` / `doracle [17d] -> escout`; `Doctor dgrant [2b] -> haltescalate`. Carries Ticket ID, extension ID, tiered flags, raw evidence hashes, spend to failure, and Rule-8 shown compensation directly to Human user + specification owner.
- **Routine Noncritical Path:** Mapped shortfalls route through bounded accepted YAML remedies (`<= 3` steps, `<= 2` paid calls, `attempt <= 1`) in `librarian-doctor-tobe`, require distinct `Oracle` re-verification before `resolved`, and keep declined/unmapped Tickets visible on Staging/Agenda without blocking sibling work (`batch` / `source` isolation).

---

## 8. Before / After / Gap Comparison Matrix Across Contexts 1, 2 & 3

> "Before" reflects `IMPLEMENTED_VERIFIED` `d9435e1` modeled in **[librarian-current-activation.spec.yaml](file:///D:/Librarian_V2/reports/2026-11-24-librarian-reconstruction-and-offering/diagrams/librarian-current-activation.spec.yaml)** + baseline `batch/source-enrichment-current.canvas`. All **"After"** behaviours and UI/MCP targets below are **`PROPOSED_UNACCEPTED` (`NOT ACCEPTED / NOT IMPLEMENTED`)**.

| Context | **Before (`d9435e1` Verified — `librarian-current-activation`)** | **After (`PROPOSED_UNACCEPTED` Target Specs)** | **Gap (What Policy/Interface/Code Must Change)** |
|---|---|---|---|
| **Context 1: User -> Tier 0 -> Librarian** | **0 MCP folder tools**; MCP hits `MCP_TIER_CEILING="contribute"` (`app.py:3088`); `process_approved` refuses (`TIER_REFUSED`); `Modes: Ask` stalls MCP writes up to `150s` (`app.py:277`); local `/api/tool/<name>` needs manual orchestration; no Core `Lead`/`Oracle`/`Doctor` sprint loop. | User instruction + scope **IS** the commission (**no 2nd prompt**; `spec_owner=tier0_on_behalf_of_person`); Tier 0 approves `Rule 15` envelope (`mandate_id`); DeepInfra `Lead` (`sub_spec_owner=lead_tier1`)/`Clerk`/`Scribe`/`Doctor`/`Oracle` run end-to-end (`Tier-0 turns = 2`); only out-of-scope, uncommissioned global governance changes, `OD-05` exceptions, & `ORACLE_ROUTE_COLLISION` pause (`userchoice`). | **Policy:** Approve `POL-AMEND-01/02/05` & decide **`OD-05`** (`Rule 16` sensitivity/challenged-claim exceptions). **Code:** Build `mandate_id` commission store + `Lead`/`Oracle`/`Doctor` runtime (`W1b`/`W9`). |
| **Context 2: External Project -> MCP -> Librarian** | `delegate`/`dispatch_plan` work at `contribute` (`effect="read"`, zero Ask), **refuse `consult` Readers (`TIER_REFUSED`)**; `open_session`/`queue_source`/`record_application` sit at `consult` with write effects (hit `150s` Ask waits / `Plan` deny); `record_application` rejects empty `sources_used` (`:1961`) and drops snapshot/constraint/verification metadata. | Explicit 5-domain Context-2 scope (`spec_owner=external_project_caller`): `consult` read-with-budget helpers; `S1–S6b` source access; non-blocking async queue (or narrowed `stage_only`); **no vault acceptance** (`queuepause` Agenda handoff); Tier-0-authored & Core-stored repeatable `record_application` (`source_refs`, constraints, verification, `sources_used=[]`); dual notifications. | **Policy:** Approve `POL-AMEND-03/06` (`OD-06`, `OD-08`). **Code:** Decouple `delegate`/`dispatch_plan` budget tier; extend `record_application` schema (`sessions.py:1948-2049`); fast `PERMISSION_UNANSWERED` structured errors. |
| **Context 3: Direct Human Web UI (Zero Tier 0)** | `Add source` (`app.js:6387`), `Show 50 more` (`:6686`), `deep-read-staged` carveout (`read_access.py:114`), & `not_confident` draft retention landed; **open bugs:** `app.js:8472` drops `action_done.result`; `:6325` omits `processing`/`accepted` filters; `:6947` `F-09` wipes edited summaries; `Workflow` route carveout limited to `deep_read`; manual `views_refresh` on index miss. | Zero Tier 0 (`spec_owner=person`; `Lead` owns sub-runs only); human retains Gate 1, Summary, Tab & Search-Index decisions; Core owns AST/DIK (`reviewchk` Step 16) & readiness while Clerk proposes W8 titles/descriptions/fields (`Unknown` explicit); UI shows `action_done.result` drawer, all 9 source filters, non-destructive `F-09` merge, & `ORACLE_ROUTE_COLLISION` Agenda flag (`uiagenda`). | **UI (`ui/app.js`):** Fix `:8472`, `:6325-6335`, `:6947`, queued-Clerk banner. **Core (`read_access.py`):** Manifest-based `workflow_grant` clearance (`POL-AMEND-04`). |

---

## 9. Tier-0 Intervention Consolidation Audit (`PROPOSED_UNACCEPTED`)

Every item consolidated downstream relies on an explicit deterministic or isolated-role guard and leaves a durable trace for the human user:

| # | Current Tier-0 Intervention | Disposition | Target Owner | Safety Guard / Verification Evidence | How User Remains Informed |
|---|---|---|---|---|---|
| 1 | Second human manifest confirmation prompt inside Context 1 after user already instructed Tier 0 | **Consolidate into Step 1/2** *(Context 1 only)* | `Human` instruction -> `Tier 0` `Rule 15` commission (`mandate_id`) | Scope bounded strictly to user instruction (`denv`); out-of-scope/budget raises & uncommissioned global governance remain excluded (`POL-AMEND-01`). | User's initial instruction + final `t0deliver` / Agenda receipt (with spend, coverage & tickets). |
| 2 | Per-write `Ask`-mode UI `Chat` stalls on MCP writes (`ingest`, `queue_source`, `record_application`, `staging_decide`) (`broker.py:224`) | **Consolidate** (`mandate_id` / scoped MCP) | `Core` Broker | Validated `mandate_id` / scoped Context-2 envelope; denies out-of-envelope calls immediately rather than hanging `150s`. | All executed writes logged in session + final completion receipt. |
| 3 | Calling `process_approved` batch start in Context 1 (`tools/batch.py:9`) | **Consolidate** *(Context 1 commission only; excluded in Context 2)* | `Core` + `Lead (tier 1)` | Explicit Context-1 `mandate_id`, `t0admit -> bind -> admit` checkpoint validation, serial `_LIVE` lock, `MC-10` cap, `commissioned_by=person, decided_by=agent`. | Live Staging banner (`paintBanner`) + `t0deliver` receipt (`userack`). |
| 4 | Ordinary non-sensitive folder screening & approval (`folderscreen -> leadfolder`) | **Consolidate** Downstream | `Clerk (tier 2)` -> `Lead (tier 1)` | Clerk reads no raw docs; `Lead` checks licence & rejects symlinks/unlicensed nested code (`dfolderauth`). | Folder disposition & exclusion list in post-run receipt & Staging `Folders`. |
| 5 | Routine Gate 2 in-scope Source acceptance in Context 1 (`leadaccept`) | **Consolidate** *(Context 1 only; excluded in Context 2; `OD-05` boundary flagged)* | `Lead (tier 1)` -> `Core` `PromotionGuard` | Context-1 commission only (`commissioned_by=person, decided_by=agent`); grounded Clerk draft; sensitivity/claim flags preserved; `PromotionGuard` 200-file CAS; **zero implicit Lens/Topic accept**. | Promoted Source list, spend, coverage & deferred Lenses/Topics in `userack` (+ any `OD-05` Ticket). |
| 6 | Stale root (`R1`), lost route (`R2`), `FOLDER_STALE` (`R1-app`), partial (`R4`), & index (`R5`) recovery | **Consolidate** Downstream | `Doctor` -> `Core` -> Distinct `Oracle` | Accepted YAML remedies only (`<=3` steps, `<=2` paid calls, `attempt<=1`, W3 bounds $\subseteq$ mandate); critical security/data-loss/boundary faults bypass Doctor (`dcrit`, `2b`). | Ticket `repair_history` + `Oracle` status surfaced in receipt & Agenda; `declined`/`unmapped` pauses cleanly. |
| 7 | Scripted AST/DIK extraction, `reviewchk` schema/quote checks & readiness vs Clerk semantic metadata/title proposals | **Split Properly** (`DOC-POL-02:33`) | `Core` (scripted) + `Clerk` (semantic proposals, `Unknown` preserved) | Core never fabricates semantic prose; Clerk never fabricates counts/SHAs (`DATA_IS_UNFRAMED`, `provenance.check_sections`). | Proposed titles/fields/explicit `Unknown`s visible on Staging & final receipt. |
| 8 | **Out-of-scope roots, unapproved budget raises, global `promotion.mode`/`accept_workflow`/`capability_install`, `ORACLE_ROUTE_COLLISION`, critical breaches, plus Owner-retained `OD-05` exceptions** | **RETAIN at Human User** *(per `OD-05`)* | **`Human user`** (`curate` / interactive decision) | Fail-closed Ticket routing (`t0ticket`, `collisionrec`, `ORACLE_ROUTE_COLLISION` never marked independently reviewed; critical faults immediate to `escrec`). | Surfaced via single structured `t0surface -> userchoice` (Context 1), immediate critical alert (`useresc`), Agenda Ticket (Context 2), or Staging UI (Context 3). |
| 9 | **Context 2 Project-$P$ research applicability, code edits, verification & `Applications/` authoring** | **RETAIN at External Tier 0 + Project-$P$ Human** | **`Tier 0 agent (external project)`** + `Human user (ext)` | Bounded `S1–S6b` `consult` access; no vault promotion in Context 2 (`queuepause`). | Project-$P$ handover (`userhandover`) + `Applications/` note + Librarian Agenda notice. |
| 10 | **Context 3 Direct UI Source Gate 1/2, `Bottom Line` edits, `Folders`/`Lenses`/`Topics`/`Offerings` acceptance** | **RETAIN at Human User (UI)** | **`Human user (UI)`** | Zero Tier 0 actor (`spec_owner=person`); `staged_revision` CAS + `EVIDENCE_QUOTE_VERIFIED`. | Direct Web UI status banners, `action_done` drawer (proposed), & Agenda. |

---

## 10. Static Validation Record, Limits & Remaining Owner Decisions

### 10.1 Diagram Validation Results, Preserved Baselines & Explicit Limits ([validation.json](file:///D:/Librarian_V2/reports/2026-11-24-librarian-reconstruction-and-offering/diagrams/validation.json))

All **9** specs in [diagrams/README.md](file:///D:/Librarian_V2/reports/2026-11-24-librarian-reconstruction-and-offering/diagrams/README.md) passed `build_and_validate_diagrams.py` with `0` structural/reference flags (`render_spec.validate`, `cross_check`, `check_references` against all 9 models plus external `batch-enrichment-current` and `source-enrichment-current`), `0` ownership violations, `0` card overlaps, `0` edge-card intersections, `0` PNG text overflows, `0` `_at_` clones on disk, and `$0` model spend:
- `librarian-current-activation` (`IMPLEMENTED_VERIFIED`: `11` steps, `30` scenarios, `0` MSS / `2 (ideal)` worst non-escalated Tier-0 turns, `1` in-memory localization)
- `librarian-process-composition-tobe` (`PROPOSED_UNACCEPTED`: `9` steps, `22` scenarios, `1` MSS / `1` worst Tier-0 turn, `0` localizations)
- `librarian-context1-tier0-delegated` (`PROPOSED_UNACCEPTED`: `9` steps, `16` scenarios, **`2 (ideal)` Tier-0 turns**, `0` localizations)
- `librarian-context2-external-project-mcp` (`PROPOSED_UNACCEPTED`: `8` steps, `12` scenarios, **`2 (ideal)` Tier-0 turns**, `0` localizations)
- `librarian-context3-human-platform-ui` (`PROPOSED_UNACCEPTED`: `12` steps, `23` scenarios, `0` Tier-0 lanes, `0` localizations)
- `librarian-ingestion-tobe` (`PROPOSED_UNACCEPTED`: `20` steps, `43` scenarios, `3` in-memory localizations)
- `librarian-batch-enrichment-tobe` (`PROPOSED_UNACCEPTED`: `10` steps, `21` scenarios, `3` in-memory localizations)
- `librarian-source-enrichment-tobe` (`PROPOSED_UNACCEPTED`: `21` steps, `23` scenarios, `3` in-memory localizations)
- `librarian-doctor-tobe` (`PROPOSED_UNACCEPTED`: `6` steps, `13` scenarios, `2` in-memory localizations)

**Preserved Baseline Canvases (Unchanged SHA-256 Verified):** `ingestion.canvas` (`0a0b1af08f1ae2553ed4e0927d162ab60068ab1f9e2c612c949c7e6c737485b5`), `batch-enrichment-current.canvas` (`eb5a5bb6533d2d5c3ad93b0c98e36150deabd68bfe22856c439cd8e082d7fe2b`), `source-enrichment-current.canvas` (`5b050a3e80351e5a47d347f04d59e63d5cad9fae0abf43649ca499a7c3d6d76b`), and `enrichment-cycle.canvas` (`8108dcd9dd9bfcecf6dc0dfd724c6cf00075d2cc8104d6590faf5aedd6157a6c`).

> **What These Checks Do NOT Verify:** Static spec, ownership, cross-reference, and 2D geometry checks verify diagram control-flow consistency and readability only. They **do NOT verify live Web UI behaviour, live MCP tool transport or timeouts, DeepInfra role routing, `record_application` disk writes, runtime Ticket persistence, or Geo-Grapher indexing**, and they do **NOT** promote any `PROPOSED_UNACCEPTED` specification to accepted policy.

### 10.2 Remaining Unresolved Owner Decisions (`OD-01..OD-08` — Not Resolved by Assumption)

| Decision ID | Open Question Requiring Explicit Owner Ruling | Candidate Options |
|---|---|---|
| **`OD-01`** | Should `render_spec.py` (`DOC-MAP-05`) adopt `DOC-MAP-11`'s `695px` double-width `Lead` sub-columns and 4-color edge palette? | (A) Extend `render_spec.py`; (B) Keep strict single-width lanes. |
| **`OD-02`** | Which `UNIMPLEMENTED_UNDROPPED` V1 parity features (`find_components`, repo SCC `digest`, OpenAlex, strict `**Not read:**`) should enter the V2 backlog vs be retired? | Per-item Owner disposition. |
| **`OD-03`** | Should unlicensed nested repositories auto-classify as `third_party` / withheld (`DOC-POL-08` vs `DOC-RPT-11` `F15`)? | (A) Fail closed as `third_party`; (B) Flag `SENSITIVITY_REVIEW`. |
| **`OD-04`** | How should Watcher/Index contention (`402` files scanning `14.96s/30s`) be bounded in `host.py`/`index.py`? | Debounce/mtime+inode diffing vs polling interval tuning. |
| **`OD-05`** | Approve `POL-AMEND-01/02` and reconcile `Rule 16` (`agent-roles-and-authority.md:62`): confirm user instruction + scope as Context 1's single commission (`mandate_id` with `commissioned_by=person, decided_by=agent`), decouple `Modes: Ask` from MCP, **and decide whether `SENSITIVITY_REVIEW` / `REVIEW_CHALLENGED` remain human-only inside Context 1 or are delegated within explicit commission scope with preserved audit flags**? | (A) Delegate in-scope with flagged audit (keeping standing global governance & `ORACLE_ROUTE_COLLISION` human-reserved); (B) Retain human-only `SENSITIVITY_REVIEW` & `REVIEW_CHALLENGED` carveout even in Context 1. |
| **`OD-06`** | Approve `POL-AMEND-03/04`: reclassify `delegate`/`dispatch_plan` as bounded `consult` read-with-budget for Context 2, and generalize `workflow_grant` read clearance for Context 3 `📎` workflows? | (A) Adopt `POL-AMEND-03/04`; (B) Require `contribute` for `delegate` and per-tool read-access allowlists. |
| **`OD-07`** | Approve `POL-AMEND-05` & fallback threshold: require secondary distinct qualified route vs hard `pause` on `ORACLE_ROUTE_COLLISION` (`unverified_route_collision`), and whether UI `curate` override is allowed for single-route installs? | (A) Mandatory `pause` unless secondary route exists; (B) Allow optional person-attested unreviewed override in Context 3 UI only. |
| **`OD-08`** | Approve `POL-AMEND-06` (`record_application` repeatability fields + `sources_used=[]` `no_match_workaround`) and Context 2 `stage_only` opt-in grant boundary? | (A) Adopt `POL-AMEND-06` + explicit opt-in `stage_only` MCP scope; (B) Keep `record_application` catalogued-source-required and queue-only Context 2 intake. |

---

*Full mapping to `DOC-*` records, `d9435e1` code lines, and diagram nodes appears in [06-evidence-and-change-traceability.md](file:///D:/Librarian_V2/reports/2026-11-24-librarian-reconstruction-and-offering/06-evidence-and-change-traceability.md).*
