# Agent roles and authority

**Status:** normative (owner, 2026-11-20; role, delegation and review clarifications, 2026-11-21).

## Three things called "tier"

The word was used for three different things, and agents confused them. Always say which sense.

| Term | Values | What it is | What it is not |
|---|---|---|---|
| **Agent tier** | 0, 1, 2, 3 | *Who* is doing the work: tier 0 is an outside agent, tiers 1–3 are the in-app roles (below) | A permission level |
| **Registry tier** | `consult`, `contribute`, `curate` | The most a caller's tool calls may do. `curate` is a person's own authority | Model quality, or who is in charge |
| **Trust tier** | `gold`, `silver`, `bronze` | How far a graph's, a source's or a remedy's content is trusted | Anything about agents |

Two more words sound like tiers and are not (21 November 2026):
- a **layer** (L0 action, L1 workflow, L2 pipeline, L3 sprint) is a process's place in the order ([composition.md](composition.md));
- a **Tier A / Tier B audit** is a kind of check: deterministic, or a read-only model review.

### Agent tiers

| Agent tier | Who | Reaches the library through | Registry tier |
|---|---|---|---|
| **0** | The **Overseer**: an outside agent working for the owner in Codex, Claude, Antigravity or another harness, including using Librarian to support another project | MCP, the CLI, the Core API; may delegate work through Librarian | The current MCP cap is `contribute`; delegated authority must be granted explicitly and does not include the person's reserved decisions |
| **1** | The **Lead**: manages the main direction and delegated work; currently hosted on DeepInfra | The app's chat loop and its phase-sized tool bundles | Up to the caller's and assigned profile's authority |
| **2** | The **Clerk**: proofreads, checks claims, synthesises and directs Scribes | Bounded work delegated through the Core | Within the caller's and assigned profile's authority |
| **3** | The **Scribe**: lightweight reading and writing across many small tasks | Bounded tasks directed by a Clerk or Lead | Within the caller's and assigned profile's authority |

These are semantic roles, not instructions to swap legacy numeric configuration fields. Existing
role slots, profiles, qualification records and tool gates keep their current behaviour until an
explicit implementation change reconciles them. Drafting text does not grant a worker direct
authority to write a vault note.

## Core services and agent ownership

**The Core performs scripted work; agents own interpretation and proposals** (Owner,
22 November 2026). AST/text parsing, schema/hash/locator checks, counters, stored permission
checks, persistence and dispatch belong to Core services. The agent completing a proposal owns
its semantic organization, metadata values, explanations and judgements, even when it uses a
Core tool to submit or store them. Core-owned specification storage does not make the Core the
specification's author. Model-assisted transcription, cleanup and synthesis remain agent work;
scripts may dispatch those tasks and check their returned structure.

## Who finishes the work

**Each agent finishes the work it is given.** No agent may leave its own steps for another tier
to complete.

- **An in-app agent (tiers 1–3) owns its assigned task to the end.** It must not assume another
  agent will finish or tidy its work. A delegated run has an explicit specification owner and
  handback recipient; a person-started task does not require an outside overseer. If it cannot
  finish, it says plainly what is left and why. The existing Lead prompt (`loop.BASE`) already
  requires ownership of completion; general specification handover remains integration work.
- **Tier 0 may delegate on the owner's behalf.** It may use Librarian and its DeepInfra agents
  to parallelise its own work, or hand a specification to a Lead. The delegated work stays
  within the granted permissions, specification and budget. A Lead owns completion of that
  work; routine execution and repair should not require tier 0 to perform each lower-tier step.
  A person-started task does not depend on an outside agent being present.
- **A tier-0 agent finishes its own work too.** Reporting a step as done means the tool that did
  it returned success in this session. Its scripts stop at the first refusal and read it. On
  2026-11-19 one sent 92 refused calls in 6 seconds, then reported accepts that had not happened.
- **Neither tier speaks for the person.** Promotion-mode changes, lead-override checkpoints,
  sensitivity reviews and spending without approval stay with the person, whichever agent asks.

## Review is kept apart from the work

Owner, 21 November 2026 ([diagram-workflows](../proposals/diagram-workflows.md), section 10). A review that shares the worker's context repeats the worker's assumptions; a meta-reasoning loop told to "look at your work and correct it" produced "corrections" that were themselves wrong.

- **Three roles, three acts.** A **worker** does the task. An **oracle** judges the output against its specification and never executes or repairs. A **doctor** repairs a failure the oracle tagged, by a catalogued remedy within its blast radius, then hands back to the oracle. Each role has its own language in its prompt, so a review cannot drift into redoing the task.
- **Separate context, separate assignment.** The oracle and the doctor share no conversation with the worker or with each other. On any one run, each has a model assignment different from the worker's. The claim review already works this way: the reviewer sees one claim and its passage, never the draft.
- **A verdict is a claim, not an order.** It carries its evidence, can be rebutted with evidence (a person decides), and is itself re-checked.
- **One owner per specification.** The Owner sets a directly requested run's specification, or
  tier 0 sets it on the Owner's behalf; a tier-1 Lead sets a sub-run's specification when it
  delegates. Each run records exactly one owner. A sub-run may only narrow its parent's
  specification, never widen it.
- **Where a verdict goes:**
  - a pass goes to whoever set the specification, once;
  - a failure at a mapped extension point goes to the doctor;
  - an unmapped failure goes to the tier-1 Lead;
  - anything critical (security, data loss, a boundary crossed, a person's decision) goes to tier 0 and the Owner at once.

The roles exist in part today: the claim review, and the audited session's verifiers. Attaching an oracle to any run is planned (P6–P7 of the diagram-workflows proposal).

## Specifications and fault tickets

**Specifications belong within the Librarian Core.** The Core owns their storage and the
specification used by a run. Reports, exported YAML and canvases may describe or propose a
specification; they do not become a parallel runtime authority. The storage backend and general
run integration remain implementation work.

**The fault register is a ticket service.** A ticket carries the existing failure or extension,
its evidence, the tiered flags that apply, and who must address it. It follows the routing above:
mapped, bounded repairs go to the doctor; unmapped failures or misalignment go to the Lead;
critical cases go to tier 0 and the Owner; reserved decisions go to the Owner. A ticket records
repair attempts and the oracle's re-check before it is resolved. Existing diagnostic labels may
be attached, but a fixed four-bit mask is not the ticket model and does not decide authority.
The general ticket service is planned, not enforced by the current Core.

## Attestation names who accepted

**A record of acceptance says who actually accepted**: the person, or the agent acting under the
library's agent promotion mode. Never "person" for an agent. The Core API now accepts a declared
agent actor and records that agent's acceptance under the applicable promotion policy (`8489387`).
An outside agent must declare itself; an undeclared caller remains indistinguishable from the
person on that surface. On 20 November an agent accepted 96 papers through the person-facing
API and every note recorded `attested_by: person` (finding F2). Correcting those historical
records remains an Owner decision.

## Models are assigned to roles, not bound

A model is **assigned** to a role (Lead, Scribe, Clerk, research helper, OCR…). An assignment is
always revisable.

The owner's current assignment for **both the doctor and the oracle is GLM-5.3** (21 November
2026), selected through the existing adapter and role-assignment mechanism. They remain separate
roles and contexts even when they use the same model. This is a current choice, not a hard-coded
model restriction or evidence that the general roles are implemented. If the worker also uses
that route, the independent-review requirement must be reconciled through a suitable qualified
assignment before its output is treated as independently reviewed.

- **Passing qualification is evidence for that route at that time, not a commitment.** A model
  that passed can be replaced the moment a cheaper, better or more available one exists, or its
  endpoint changes. On 2026-11-19 a Lead endpoint that passed earlier was closed (HTTP 500).
- **Never treat an assignment as permanent**, and never write one into a document as a standing
  rule. A report that says a model was assigned records a decision made that day.
- **In code**, the stored record of an assignment is still called a binding (`RoleRouteBinding`,
  `role_routes`). That is an identifier. In prose, UI, refusal messages and agent instructions,
  say **assign**.
- Changing an assignment needs the same evidence as making one: the route's qualification for
  that role. A person decides where the role's profile requires it.
