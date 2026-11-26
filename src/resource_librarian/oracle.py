"""Review kept apart from the work: is a reviewer independent of the worker? (M4; policy, review.)

Policy: the oracle's assignment is never the worker's on the same run. Two roles can name different
routes and still resolve to one model (an inherited binding, or two hosts serving the same model), so
the check compares the resolved model, not the route string. Assignments stay revisable (assign, not
bind): this reads them and decides nothing about which model is assigned.
"""
from __future__ import annotations

from typing import Any


def resolved_model(vault: Any, role: str) -> str:
    """The model a role resolves to, normalised, or '' when the role has no assignment."""
    from .role_routes import RoleRouteStore
    try:
        binding = RoleRouteStore(vault).resolve(role)
    except Exception:                                # noqa: BLE001 - an unreadable store reads as unassigned
        return ""
    if binding is None or binding.source == "unconfigured" or not binding.model_id:
        return ""
    model = binding.model_id.strip().casefold()
    return model.rsplit("/", 1)[-1] if "/" in model else model


def independence(vault: Any, worker: str, reviewer: str) -> dict[str, Any]:
    """`independent`, `same_model` or `unassigned`, with both sides named."""
    worker_model, reviewer_model = resolved_model(vault, worker), resolved_model(vault, reviewer)
    if not reviewer_model:
        status = "unassigned"
    elif worker_model and worker_model == reviewer_model:
        status = "same_model"
    else:
        status = "independent"
    return {"worker": worker, "reviewer": reviewer, "status": status,
            "worker_model": worker_model, "reviewer_model": reviewer_model}
