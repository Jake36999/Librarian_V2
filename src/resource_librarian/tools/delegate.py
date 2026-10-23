"""Helper agents (owner, 2026-10-01): the effort setting's "agents that can be spawned".

The lead model hands independent questions to helpers that run at once - tier 1 helpers on
the lead model, tier 2 on the notes model, as many as the person's effort allows
(`effort.py`: 1-4 tier 1, 3-12 tier 2). A helper only reads: its tools are a fixed
allowlist of read-only tools, enforced by its loop (a call to anything else is refused, not
merely hidden), it opens no session and writes nothing. Each comes back with its answer, the
tools it used and why it stopped; what to keep is still the lead model's and the person's.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

from ..registry import Card, Context, tool

HELPER_TOOLS = frozenset({"search", "get_note", "web_search", "read_url", "read_file",
                          "read_source_file", "list_files", "search_work", "topics_list"})
HELPER_BRIEF = (
    "You are a helper agent working for the librarian on one question only:\n  {question}\n"
    "Look in the library first (search, get_note), then outside it (web_search, read_url). "
    "You only read: you cannot open a session, save, capture or change anything. Stop when "
    "you can answer. End with: what you found, where (note names or URLs, exactly), and what "
    "you could not find.")


@tool("delegate", tier="contribute", effect="read", open_world=True,
      returns=("agents", "tier", "results"),
      card=Card("Hand independent questions to helper agents that research them at the same "
                "time - each reads the library and the web, and reports back",
                "a request splits into separate questions (one per topic, source or module) "
                "that can be looked into at once",
                "Helpers only read: they write, capture and decide nothing. tier=1 helpers "
                "use the lead model, tier=2 the notes model; how many may run at once follows "
                "the person's effort setting"))
def delegate(ctx: Context, questions: list[str], tier: Literal[1, 2] = 2) -> dict:
    from .. import effort
    from ..loop import Loop
    level = effort.of(ctx)
    asked = [str(q).strip() for q in questions if str(q).strip()]
    if not asked:
        raise TypeError("give at least one question")
    cap = level["lead_agents"] if tier == 1 else level["tier2_agents"]
    if len(asked) > cap:
        raise TypeError(f"effort {level['level']} allows {cap} tier {tier} helper(s) at once, "
                        f"not {len(asked)}: send fewer questions, or the person raises effort")
    provider_for = ctx.extras.get("agent_provider")
    provider = provider_for(tier) if provider_for else None
    resolved_tier = tier
    if provider is None and tier == 2 and provider_for:
        provider = provider_for(1)                   # no tier 2 chosen: the lead model helps
        resolved_tier = 1
    if provider is None:
        raise TypeError("no model to run helpers on here: helpers run in the app, on the "
                        "chosen tiers")
    helper_profile = None
    profile_store = ctx.extras.get("profile_store")
    if profile_store is not None:
        try:
            # Helpers are intentionally not the selected Lead/Scribe profile:
            # their fixed capability is the vault's versioned
            # ``research_helper`` policy and can only become more restrictive.
            helper_profile = profile_store.get("research_helper")
        except (KeyError, ValueError, TypeError) as exc:
            raise TypeError("the vault's research_helper agent profile is unavailable") from exc
    rate_card = None
    guard = ctx.extras.get("helper_profile_guard")
    if helper_profile is not None and callable(guard):
        try:
            rate_card = guard(helper_profile, resolved_tier)
        except Exception as exc:  # Core supplies a precise profile/qualification explanation
            raise TypeError(f"research_helper profile cannot run on this route: {exc}") from exc
    if helper_profile is not None:
        cap = min(cap, int(getattr(helper_profile, "concurrency_limit", 1) or 1))
        if len(asked) > cap:
            raise TypeError(f"research_helper profile allows {cap} concurrent helper(s), not {len(asked)}")
    steps = max(6, level["turn_steps"] // 3)

    child_extras: dict[str, Any] = {"effort": level, "caller": "research_helper"}
    # Keep read operations on the Core-owned index worker and preserve the
    # normal broker/checkpoint boundary.  Do not copy a writer: helpers remain
    # read-only through HELPER_TOOLS and Loop.only.
    for key in ("index_service", "broker", "checkpoints", "document_leases", "profile_store"):
        if key in ctx.extras:
            child_extras[key] = ctx.extras[key]
    if helper_profile is not None:
        child_extras["agent_profile"] = helper_profile.id
    gate = ctx.extras.get("profile_gate")

    def run(question: str) -> dict[str, Any]:
        release = lambda: None
        try:
            if helper_profile is not None and gate is not None:
                release = gate.acquire(helper_profile)
            helper = Loop(ctx.vault, provider, tier="consult", reply_length="short",
                          working_context=HELPER_BRIEF.format(question=question), scribe=None,
                          extras=dict(child_extras), max_steps=steps)
            if helper_profile is not None:
                helper.configure_profile(helper_profile, rate_card=rate_card)
            helper.only = HELPER_TOOLS
            helper.turn_seconds = helper.cap_turn_seconds(level["turn_seconds"])
            turn = helper.send(question)
        except Exception as exc:                            # noqa: BLE001
            return {"question": question, "answer": "", "error": f"{type(exc).__name__}: {exc}"}
        finally:
            release()
        return {"question": question, "answer": (turn.reply or "")[:4000],
                "tools": [c["tool"] for c in turn.calls], "steps": turn.steps,
                **({"stopped": turn.stopped} if turn.stopped else {}),
                **({"error": turn.error} if turn.error else {})}

    with ThreadPoolExecutor(max_workers=len(asked)) as pool:
        results = list(pool.map(run, asked))
    return {"agents": len(asked), "tier": tier, "effort": level["level"], "results": results}
