# Audited macro scheduling

Status: writer-wait hardening implemented. This is not the long-horizon
AuditedEngagement harness.

`macro_run` remains a write-capable registered tool, with the same tier,
session, permission, budget, and expanded-plan checkpoint requirements. It is
the only first-party tool marked as an orchestrator. Dynamic MCP tools cannot
claim that marker, and a macro nested inside an already-held writer operation
is refused before asking for permission.

The macro's control flow runs outside VaultWriter. Its checkpoint creation
and every contained mutation still go through that writer. Consequently a
person's answer, checkpoint resolution, or unrelated write can run while a
macro step waits for permission; no queue is pumped inside an unfinished
write. The atomic boundary is one write step, not the whole macro. All step
preconditions and document leases are checked again at that boundary.

Approval of an expanded plan is deliberately **not** a blanket broker grant.
The existing per-step permission controls, Plan mode, Deny settings, phase
gates, sensitivity/promotion policy and budgets remain authoritative. This
closes the deadlock without widening authority or removing existing approval
controls. A later optimization may unify redundant approvals only with an
equally narrow, tested grant contract.

Checkpoint scope includes the expanded plan as well as macro version and
inputs. Changing steps without bumping the version can no longer reuse an
approval for an older plan. Existing pending approvals may therefore require
fresh review after this upgrade.

An error, refusal, or unanswered person decision pauses the macro. Completed
durable work remains intact. The response identifies the refused step,
arguments, completed-step count and its conflict checkpoint when present.

**Step journal (MF-018).** An approved write-capable run keeps a durable step
log, `.librarian/runs/macro-<checkpoint id>.jsonl`. Each step logs `dispatch`
before it runs, then `done` after it, or `stopped` for a refusal or question.
Running the macro again with the same `checkpoint_id` continues that run:
- **A done step** is reused, not repeated.
- **A stopped step** is tried again.
- **A completed run** returns its record and repeats nothing.
- **A step dispatched with no outcome** (the app stopped part way) may or may
  not have taken effect:
  - a read or idempotent step is simply run again;
  - a step that changes something returns `outcome_unknown`. A person then
    checks and runs the macro again with `unknown_step` set to `retry` or
    `applied`. An agent cannot give that answer, and it is not part of the
    approved scope.

Read-only macros keep no log: running one again repeats only reads.
Workflows and pipelines follow the same rule through `run_resume` choices
(`workflows.py`). This is at-most-once for changing steps unless a person says
otherwise, not exactly-once: exactly-once would need each tool to be
idempotent.
