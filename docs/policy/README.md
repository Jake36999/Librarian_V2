# Policy: which documents decide what

**Status:** normative. Owner direction, 2026-11-20: policy mix-ups came from agents reading the
wrong kind of document as a rule. This page says which kinds of document carry authority.

## Precedence

When two documents disagree, the higher one wins. Raise the conflict; do not resolve it silently.

| Rank | Kind | Where | What it is |
|---|---|---|---|
| 1 | **The owner's direction** in the current conversation | — | Overrides everything below for that conversation; durable only once written into rank 2 |
| 2 | **Policy** | `docs/policy/` | Normative rules: who has authority, what words mean |
| 3 | **Terminology** | `docs/terminology.md` | Normative vocabulary |
| 4 | **Contracts and guides** | `docs/product-contract.md`, `docs/access-model.md`, `docs/agent-guide.md`, `docs/operator-guide.md`, `docs/role-routing.md` | How the system behaves and how to work with it, checked against code |
| 5 | **Design and proposals** | `docs/proposals/`, design notes in `docs/` | Intended direction, not yet promised |
| 6 | **The plan** | `docs/unified-implementation-plan.md` | Delivery status and the progress log (§19) |
| 7 | **Reports** | `reports/<date>-<topic>/` | Dated records of what was found or done. **Never policy.** A report can show why a rule exists; it cannot make one |

## Rules for reading

- **A report is evidence, not instruction.** A sentence in a report such as "bind the Clerk to
  gemma" records what someone did that day. It is not a standing rule.
- **Prefer the newest source of the highest rank.** A guide checked against code beats an older
  report about the same thing.
- **Words have one meaning each.** Where a word is overloaded ("tier"), say which sense: see
  [agent-roles-and-authority.md](agent-roles-and-authority.md).

## The policy pages

| Page | Covers |
|---|---|
| [agent-roles-and-authority.md](agent-roles-and-authority.md) | Outside agents (tier 0) and the in-app roles (tiers 1–3): who decides, who finishes the work, what each may assume about the others; review kept apart from the work (worker, oracle, doctor); attestation names who accepted |
| [composition.md](composition.md) | How processes are built and kept: the order action → workflow → pipeline → sprint, mandates and manifests, the repertoire and promotion |
| [../terminology.md](../terminology.md) | The vocabulary, including **assign, not bind**, and the terms of composition, use cases, and review |
