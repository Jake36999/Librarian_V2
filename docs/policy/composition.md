# Composition: how processes are built and kept

**Status:** normative (owner, 21 November 2026). The words are defined in [../terminology.md](../terminology.md#composition). The design and its reasoning are in [the diagram-workflows proposal](../proposals/diagram-workflows.md), section 11. What is built so far is in the plan (rank 6).

## The order

Every unit of work is a **process**, of one of four kinds, in this order:

**action → workflow → pipeline → sprint**

1. **A process is built only from processes earlier in the order**, or of its own kind without a cycle. It is never built from a later one: a pipeline is never a component of an action. This keeps composition free of loops.
2. **A process may use any earlier kind directly.** An action may sit in a pipeline or a sprint, not only inside a workflow.
3. **Granularity is chosen by which process is invoked.** The same `review` workflow can run as one step, or its actions can run one by one where more granularity is wanted. Neither copy is a different process.
4. **New work is composed from what exists.** A new action, or a new use of existing actions, becomes a workflow. Workflows, in new orders and mixed with single actions, become pipelines. Sprints are named for planning room; none needs to exist yet.

## What a process may contain

5. **Only registered actions do anything.** A process holds no code between steps and cannot run shell text. Every step goes through the registry, so tiers, phases, budgets and the permission broker apply as if a model had made the call.
6. **A process is validated before it is saved, and pinned when it runs.** A run executes the exact text it started with, never whatever a name means later.
7. **A step's labels never understate it.** A step's side-effect class is derived from its action. A declared class may overstate it, never understate it.
8. **A compensation is shown, never run by the runner.** A person decides whether to undo a step after a failure.

## Using a process inside a parent process

9. **A component must fit its parent's mandate.** A parent process states the highest tier, the effects and the outside access it allows, and what it denies. A component whose manifest exceeds that is not integrated, and each action that does not fit is named.
10. **The fit is judged from the manifest, not by reading the component.** A manifest is compiled from the process's definition and the registry, carries the same digest a run pins, and is regenerated whenever the definition changes. It is never edited by hand.

## Keeping a process: the repertoire

11. **A process joins the repertoire only by promotion.** It is validated, accepted by the Owner, and its digest pinned, with its manifest and provenance recorded. An agent may propose a promotion; it never makes one.
12. **Composition starts from the repertoire.** Before drafting a process, look for an accepted one that covers the need, lowest layer first. A draft that duplicates an accepted process is not kept: the existing one is used.
13. **A role is limited by its mount, not by a list of prohibitions.** A role sees, and composes from, only its subset of the repertoire, as a session phase offers only its bundle. A prose "forbidden" list is never the safeguard.

## What a model decides

14. **Code checks what code can check.** A threshold, a schema, a reference or a count is checked as code first. A model is given a closed choice between named options, never an open-ended check.

## Not yet enforced

Enforced today by `workflows.py`: rule 1, more strictly than written (a workflow holds only actions, a pipeline only workflows and routes, and `closure()` refuses a cycle), and rules 5–8.

Planned:
- rule 2's direct uses: an action in a pipeline, and a workflow inside a workflow;
- sprints;
- manifests and the mandate check (rules 9–10);
- the repertoire and promotion (rules 11–12).

Until each is built, an agent follows the rule by hand and says so, and never claims the Core enforces it.
