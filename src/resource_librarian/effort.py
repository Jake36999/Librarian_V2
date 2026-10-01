"""The effort control (owner, 2026-10-01): one slider, 1-10, saying how much work the person
expects. Every quantity moves in proportion to the slider's position between its two ends:

| Quantity | at 1 | at 10 | What it bounds |
|---|---|---|---|
| `lead_agents` | 1 | 4 | tier 1 sub-agents one `delegate` call may run at once |
| `tier2_agents` | 3 | 12 | tier 2 sub-agents at once, and the notes model's parallel calls |
| `tier3_agents` | 5 | 25 | the small-task model's (clerk's) parallel calls |
| `turn_steps` | 12 | 80 | model steps in one reply |
| `turn_seconds` | 180 | 1800 | wall-clock time for one reply |
| `budget_scale` | 0.5 | 2.0 | every session phase's call budget |
| `review_claims` | 0 | 10 | claims the review gate checks: offerings from 3, replies from 7 |

At the default (4) the call budgets are exactly the session's own (1.0x). The ceilings sit
well inside DeepInfra's limit of 200 concurrent requests per model per account (its docs,
2026-10-01): the maximum is 4 + 12 + 25 requests in flight.
"""
from __future__ import annotations

from typing import Any

LEVELS = (1, 10)
DEFAULT = 4
RANGES: dict[str, tuple[float, float]] = {
    "lead_agents": (1, 4),
    "tier2_agents": (3, 12),
    "tier3_agents": (5, 25),
    "turn_steps": (12, 80),
    "turn_seconds": (180, 1800),
    "budget_scale": (0.5, 2.0),
    "review_claims": (0, 10),
}
REVIEW_OFFERINGS_FROM = 3          # review_claims at which offerings are reviewed
REVIEW_REPLIES_FROM = 7            # ... and chat replies


def clamp(level: Any) -> int:
    try:
        value = int(level)
    except (TypeError, ValueError):
        value = DEFAULT
    return max(LEVELS[0], min(LEVELS[1], value))


def profile(level: Any = DEFAULT) -> dict[str, Any]:
    """What a level allows, each quantity linear between its two ends."""
    level = clamp(level)
    share = (level - LEVELS[0]) / (LEVELS[1] - LEVELS[0])
    out: dict[str, Any] = {"level": level}
    for name, (low, high) in RANGES.items():
        value = low + (high - low) * share
        out[name] = round(value, 2) if name == "budget_scale" else int(round(value))
    out["review_offerings"] = out["review_claims"] >= REVIEW_OFFERINGS_FROM
    out["review_replies"] = out["review_claims"] >= REVIEW_REPLIES_FROM
    return out


def of(ctx: Any) -> dict[str, Any]:
    """The effort a call runs under: the surface's setting, else the default."""
    found = (getattr(ctx, "extras", None) or {}).get("effort")
    return found if isinstance(found, dict) else profile(DEFAULT)


def apply_concurrency(endpoint: Any, n: int) -> Any:
    """Set an endpoint's parallel calls (a router's every route too). Returns the endpoint."""
    if endpoint is None:
        return None
    for target in [endpoint, getattr(endpoint, "default", None),
                   *(getattr(endpoint, "routes", {}) or {}).values()]:
        if target is not None and hasattr(target, "concurrency"):
            target.concurrency = max(1, int(n))
    return endpoint
