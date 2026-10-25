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
This is manual recovery guidance, not automatic exactly-once macro resume:
restarting a macro reruns completed steps. A persistent resume cursor and
automatic retries are not claimed by this change.
