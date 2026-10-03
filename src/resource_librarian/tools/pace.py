"""The lead's own say in how much effort a request gets (owner, 2026-10-03).

The person's effort slider is a ceiling, not an order: a link to a presentation should not
start the whole research cycle a request to survey a field does. `set_effort` lets the lead
choose a level up to the slider for the work in hand - fewer steps and smaller budgets for a
small job, the slider's full allowance for a large one - and says why. It lasts for the
current reply (the slider applies again to the next), and an open thread's call budgets
follow it.
"""
from __future__ import annotations

from .. import effort as levels
from ..registry import Card, Context, tool
from ..session import SessionStore


@tool("set_effort", tier="consult", effect="read",
      card=Card("Choose how much effort this request needs, up to the person's setting",
                "at the start of a request: 1-3 for one link, file or quick answer; the most "
                "for a survey across many sources",
                "The person's slider is the ceiling; a level above it is held to it. Lasts "
                "for this reply"))
def set_effort(ctx: Context, level: int, reason: str = "") -> dict:
    ceiling = levels.clamp((ctx.extras.get("effort_ceiling") or {}).get("level",
                           (ctx.extras.get("effort") or {}).get("level", levels.DEFAULT)))
    wanted = levels.clamp(level)
    chosen = levels.profile(min(wanted, ceiling))
    ctx.extras["effort"] = chosen
    # The loop picks these up before its next step: this reply's step and time limits.
    ctx.extras["turn_limits"] = (chosen["turn_steps"], chosen["turn_seconds"])
    if ctx.session:
        try:
            SessionStore(ctx.vault).append(ctx.session, {
                "type": "effort", "level": chosen["level"], "by": "lead",
                "budget_scale": chosen["budget_scale"], "reason": str(reason)[:200]})
        except Exception:                                   # noqa: BLE001 - a closed thread
            pass
    return {"effort": chosen["level"], "ceiling": ceiling,
            **({"held_to_ceiling": f"{wanted} asked; the person's setting allows up to "
                                   f"{ceiling}"} if wanted > ceiling else {}),
            "steps_this_reply": chosen["turn_steps"],
            "phase_budgets": f"x{chosen['budget_scale']}"}
