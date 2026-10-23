"""Person-controlled, source-bound execution engagement tools."""
from __future__ import annotations

import hashlib
import json

from .. import workbench
from ..registry import Card, Context, REGISTRY
from ..rules import Refusal


def _require_person(ctx: Context, action: str) -> None:
    """Execution decisions never come from a model-facing tool turn.

    Tier is a capability ceiling, not proof of who clicked the action.  The
    browser and explicit CLI mark themselves ``caller_kind=person``; agent,
    Clerk, Cowork and workflow contexts cannot manufacture that bit.
    """
    if ctx.extras.get("caller_kind") != "person":
        raise Refusal("PERSON_CONFIRMS", f"{action} needs an explicit person action in the browser or CLI")


def _checkpoint(ctx: Context, type: str, scope: str, checkpoint_id: str,
                evidence: dict) -> dict | None:
    """Return an approved operation-scoped UI checkpoint or create one.

    A typed ``confirm_*`` flag is useful for a terminal script but is not a
    record of what was reviewed.  The checkpoint includes the exact command
    digest, so changing an image, argv, or force-close reason requires a new
    decision rather than reusing an old approval.
    """
    store = ctx.extras.get("checkpoints")
    if store is None:
        raise Refusal("PERSON_CONFIRMS", "the Core checkpoint service is required before this execution decision")
    if checkpoint_id:
        try:
            row = store.get(checkpoint_id)
            if row.get("type") == type and row.get("scope") == scope and \
                    row.get("resolution") == "approve" and not row.get("expired"):
                return None
        except (KeyError, ValueError):
            pass
    return store.ensure(type, scope, evidence=evidence, choices=["approve", "cancel"],
                        default="cancel", requester="person")


def _scope(prefix: str, values: dict) -> str:
    encoded = json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"{prefix}:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:16]}"


@REGISTRY.tool("engagement_plan", tier="consult", effect="read", resolve={"source": "note"},
               card=Card("Plan a source-bound execution engagement at a pinned revision.",
                         "a catalogued repository may need inspection or execution",
                         "Agents can propose this; it does not run code"),
               returns=("source", "pinned_revision", "choices"))
def engagement_plan(ctx: Context, source: str, purpose: str = "", project: str = "",
                    session: str = "") -> dict:
    return workbench.plan(ctx.vault, source, purpose, project, session or str(ctx.session or ""))


@REGISTRY.tool("engagement_propose", tier="contribute", effect="write", scope="library",
               resolve={"source": "note"},
               card=Card("Record a proposed source-bound workbench engagement.",
                         "an agent has inspected a source and a person may later choose to execute it",
                         "Proposal only: no code starts and no host is selected"),
               returns=("engagement", "plan"))
def engagement_propose(ctx: Context, source: str, purpose: str = "", project: str = "") -> dict:
    return workbench.propose(ctx.vault, source, purpose, project, str(ctx.session or ""))


@REGISTRY.tool("engagement_start", tier="curate", effect="vault_write", scope="library",
               idempotent=False,
               card=Card("Start a person-approved source-bound execution engagement.",
                         "a person reviewed the pinned source, command, image and isolation warning",
                         "Docker is the only isolated label. Host fallback is explicitly non_isolated_host_exec"),
               returns=("engagement", "run"))
def engagement_start(ctx: Context, engagement_id: str,
                     choice: str = "inspect_only", command: list[str] | None = None,
                     image: str = "", confirm_non_isolated: bool = False,
                     checkpoint_id: str = "") -> dict:
    _require_person(ctx, "starting an execution engagement")
    if choice in ("docker_isolated", "non_isolated_host_exec"):
        kind = "docker_execution" if choice == "docker_isolated" else "non_isolated_execution"
        scope = _scope("engagement", {"id": engagement_id, "choice": choice,
                                       "command": command or [], "image": image,
                                       "non_isolated": bool(confirm_non_isolated)})
        checkpoint = _checkpoint(ctx, kind, scope, checkpoint_id, {
            "engagement_id": engagement_id, "choice": choice, "command": command or [],
            "image": image, "network_guarantee": "none" if choice == "non_isolated_host_exec"
            else "Docker --network none",
            "consequence": "The command will execute only after this approval.",
        })
        if checkpoint is not None:
            return {"status": "awaiting_checkpoint", "resumable": True,
                    "checkpoint": checkpoint,
                    "detail": "Approve or cancel the execution checkpoint, then rerun with its checkpoint_id."}
    return workbench.start(ctx.vault, engagement_id, choice=choice, command=command or [], image=image,
                           confirm_non_isolated=confirm_non_isolated, person_confirmed=True)


@REGISTRY.tool("engagement_close", tier="curate", effect="write", scope="library",
               idempotent=False,
               card=Card("Close an engagement with its application and outcome, or force-close it with a reason.",
                         "the person has used or decided not to use a workbench result"),
               returns=("state", "application", "outcome"))
def engagement_close(ctx: Context, engagement_id: str, application: str = "", outcome: str = "",
                     force_reason: str = "", checkpoint_id: str = "") -> dict:
    _require_person(ctx, "closing an execution engagement")
    if force_reason.strip():
        scope = _scope("engagement-close", {"id": engagement_id, "reason": force_reason.strip()})
        checkpoint = _checkpoint(ctx, "forced_engagement_close", scope, checkpoint_id, {
            "engagement_id": engagement_id, "force_reason": force_reason[:1000],
            "consequence": "The engagement closes without a normal application/outcome record.",
        })
        if checkpoint is not None:
            return {"status": "awaiting_checkpoint", "resumable": True,
                    "checkpoint": checkpoint,
                    "detail": "Approve or cancel the forced-close checkpoint, then rerun with its checkpoint_id."}
    return workbench.close(ctx.vault, engagement_id, application=application, outcome=outcome,
                           force_reason=force_reason)


@REGISTRY.tool("engagement_list", tier="consult", effect="read",
               card=Card("List persistent source-bound workbench engagements and audit states.",
                         "reviewing proposed, running, paused or closed execution work"),
               returns=("engagements",))
def engagement_list(ctx: Context, limit: int = 100) -> dict:
    return {"engagements": workbench.EngagementStore(ctx.vault).list(limit)}

