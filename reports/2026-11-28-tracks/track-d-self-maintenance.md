# Track D: the Librarian maintaining itself (M6), with tier 0 reviewing

**Why (the Owner, 28 November):** the compounding step is the Librarian working on itself, with tier 0 reviewing.
- **The repair loop:** its own faults (tickets) become remedies, carried out by tiers 1 to 3 and checked by the oracle.
- **The code loop:** changes to its own code are drafted by delegated code workers, and tier 0 only reviews and lands them.

Most of the parts exist. This track joins them, within the existing authority.

**What exists to build on:**
- **Tickets** (`tickets.py`, `standard/tickets.yaml`, 13 classes): escalation by review date. A worker never closes its own ticket, and the Core's rechecks do.
- **The doctor** (`doctor.py`, the `doctor` tool): install and library checks.
- **The oracle and repair role slots** (M4): unassigned until the person assigns them. `oracle.independence` compares their models.
- **The declarations:** actions and stages (`standard/actions.yaml`, `standard/stages.yaml`) and manifests (`manifests.py`), which give change impact a blast radius.
- **Code workers** (`docs/agent-guide.md` §5, DELEG-01 to DELEG-06): `scripts/delegate_deepinfra.py` for one-shot drafts. Managed work packages run through `scripts/check_work_package.py` and `scripts/delegation_controller.py`, which apply the result in a detached worktree and run the checks there, with a reviewer from another model family and a budget.
- **The library's own code graph:** Geo-Grapher's `librarian-v2` graph, and the MCP tools `get_architecture_context` and `find_dependants`.
- **The regression audit:** `scripts/regression_audit.py`, the gate every self-made change must pass.

**Repository:** Librarian. **Read:** the implementation plan's M6, and the to-be `doctor.spec.yaml`, `oracle.spec.yaml` and `learn.spec.yaml`, with the spec audit's verdicts on them (`reports/2026-11-27-spec-vs-pack/APPENDIX.md`).

## Sprint D1: an inventory of the loop (read only)

Map each step of "a fault, then its remedy, then the check, then the review" to the code that exists, for both loops:
- **repair:** a ticket → a remedy → the oracle's recheck → closed;
- **code:** an issue → a work package → a delegated draft → the checks → tier-0 review → landed.

Mark each step present, partial or missing, with its file and line. List the remedies R1–R6 from the plan with what exists for each.

**Done when:** `reports/<date>-self-maintenance-inventory/README.md` has the map. It names the smallest set of missing pieces for one loop to run end to end in the test vault.

## Sprint D2: the design, for the Owner

Design the first loop: the repair loop for one mapped ticket class, such as `mapped_shortfall` findability with the reindex remedy R5.
- **Inside the radius:** the doctor runs the remedy as a workflow over existing actions, after the blast-radius check from the declarations.
- **Checked apart from the work:** the oracle rechecks it, on a model different from the worker's (`oracle.independence`).
- **The ticket** closes by that recheck.
- **Outside the radius**, or with no oracle assigned, the ticket goes to the Owner's agenda.
- **Never automatic:** the doctor drafts a remedy for an unmapped failure and never installs one.

**Done when:** the Owner accepts the design (who decides what, and what is never automatic), after Claude has reviewed it.

## Sprint D3: the repair loop, in the test vault

- Implement D2 on the existing tickets, workflows and roles.
- A failure inside the doctor raises a `critical` ticket instead of looping.
- A compensation step is shown, and never run by itself.
- A remedy never writes an original.

**Done when:**
- the plan's M6 done-when holds in the test vault: a mapped failure is repaired inside its radius and passes its recheck, and one outside its radius goes to the Owner;
- the regression audit and the full suite pass.

## Sprint D4: the code loop, with tier 0 reviewing

- **The Librarian's side:** it turns an open `code_change` ticket into a DELEG-06 work package, with its brief, its files from the code graph's dependants, its checks (the regression audit, the suite slice, the full suite), a budget and a reviewer family.
- **The controller's side:** it drafts, applies and checks the change in a worktree.
- **Tier 0's side:** it receives only the result: the diff, the checks and the audit. It approves or rejects.
- **Nothing lands without tier 0.** Spend follows the Owner's ceiling.

**Done when:** one real, small `code_change` ticket goes from ticket to a reviewed, landed commit, with tier 0 spending one review turn. The turns, tokens and spend are reported. The paid calls need the Owner's approval.

## Sprint D5: the repertoire (UC8.2)

A process that has run cleanly is validated, accepted by the Owner, and pinned by digest, so later runs reuse it without re-deriving it.

**Done when:** the plan's UC8.2 criteria hold, and a pinned process refuses to run after its definition changes.
