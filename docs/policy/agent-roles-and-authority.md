# Agent roles and authority

**Status:** normative (owner, 2026-11-20).

## Three things called "tier"

The word was used for three different things, and agents confused them. Always say which sense.

| Term | Values | What it is | What it is not |
|---|---|---|---|
| **Agent tier** | 0, 1, 2, 3 | *Who* is doing the work: tier 0 is an outside agent, tiers 1–3 are the in-app roles (below) | A permission level |
| **Registry tier** | `consult`, `contribute`, `curate` | The most a caller's tool calls may do. `curate` is a person's own authority | Model quality, or who is in charge |
| **Trust tier** | `gold`, `silver`, `bronze` | How far a graph's or a source's content is trusted | Anything about agents |

### Agent tiers

| Agent tier | Who | Reaches the library through | Registry tier |
|---|---|---|---|
| **0** | An outside agent working for the owner on the platform: Claude Code, Codex, Antigravity and others | MCP (capped at `contribute`), the CLI, the Core API | `contribute` over MCP. Never `curate`: a person's decisions stay the person's |
| **1** | The **Lead**: the in-app model the person talks to | The app's chat loop, with phase-sized tool bundles | Up to `contribute` |
| **2** | The **Scribe** and the **research helper** | Delegated by the Lead, with a read-only allow-list | `consult` |
| **3** | The **Clerk** | Bounded tasks (drafts, checks, reading parts) | `consult` |

## Who finishes the work

**Each agent finishes the work it is given.** No agent may leave its own steps for another tier
to complete.

- **An in-app agent (tiers 1–3) directed by the person owns that task to the end.** It is not
  told about outside agents and must not assume one will review, finish or tidy its work. If it
  cannot finish, it says plainly what is left and why. This is in the Lead's prompt
  (`loop.BASE`).
- **An in-app agent is blind to tier 0.** Nothing in its prompt, envelope or guide describes an
  outside supervisor. When a tier-0 agent works in a library, it calls the tools itself; it does
  not direct the Lead.
- **A tier-0 agent finishes its own work too.** Reporting a step as done means the tool that did
  it returned success in this session. Its scripts stop at the first refusal and read it. On
  2026-11-19 one sent 92 refused calls in 6 seconds, then reported accepts that had not happened.
- **Neither tier speaks for the person.** Promotion-mode changes, lead-override checkpoints,
  sensitivity reviews and spending without approval stay with the person, whichever agent asks.

## Models are assigned to roles, not bound

A model is **assigned** to a role (Lead, Scribe, Clerk, research helper, OCR…). An assignment is
always revisable.

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
