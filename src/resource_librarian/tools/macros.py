"""Registry surface for compact audited composite actions."""
from __future__ import annotations

from typing import Any

from ..agent_runtime import MACROS, macro_plan, run_macro
from ..registry import Card, Context, REGISTRY


@REGISTRY.tool("macro_plan", tier="consult", effect="read",
               card=Card("Show the audited steps and checkpoints of a macro.",
                         "you want a compact repeatable research path before running it"),
               returns=("id", "steps"))
def show_macro_plan(ctx: Context, macro: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read-only: a macro is an explicit sequence of ordinary registry tools."""
    plan = macro_plan(macro)
    if inputs:
        # This is still read-only: it simply resolves the supplied values so
        # a person can inspect the precise expanded sequence before approval.
        from ..agent_runtime import MACROS, _expanded_plan
        if macro in MACROS:
            plan = _expanded_plan(MACROS[macro], inputs)
    return plan


@REGISTRY.tool("macro_run", tier="contribute", effect="vault_write",
               card=Card("Run an audited multi-step macro through normal policy gates.",
                         "a known path such as inspect-map-source or intake-to-stage fits"),
               scope="session", idempotent=False, returns=("status", "steps"))
def execute_macro(ctx: Context, macro: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Every contained tool still passes the registry, phase hooks and broker."""
    if macro not in MACROS:
        raise TypeError(f"macro is one of {sorted(MACROS)}")
    if not isinstance(inputs, dict):
        raise TypeError("inputs is an object")
    return run_macro(ctx, macro, inputs)
