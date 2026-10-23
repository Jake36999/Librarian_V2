"""Registered advisory community-analysis tools."""
from __future__ import annotations

from .. import communities
from ..registry import Card, Context, REGISTRY


@REGISTRY.tool("community_rebuild", tier="contribute", effect="write", scope="library",
               card=Card("Build an advisory whole-library community map from indexed links.",
                         "you need to see clusters and central notes across a mature library"),
               returns=("nodes", "edges", "communities"))
def rebuild_communities(ctx: Context, iterations: int = 20) -> dict:
    """Derived index data only: it never edits notes or changes ranking."""
    return communities.rebuild(ctx.vault, iterations,
                               index_service=ctx.extras.get("index_service"))


@REGISTRY.tool("community_reports", tier="consult", effect="read",
               card=Card("Read the last advisory community map.",
                         "you need a whole-library view after community_rebuild"),
               returns=("communities",))
def community_reports(ctx: Context) -> dict:
    return communities.report(ctx.vault)


@REGISTRY.tool("community_disagreements", tier="consult", effect="read",
               card=Card("List high-link community candidates worth a person's inspection.",
                         "a community map contains bridges or ambiguous central notes"),
               returns=("candidates",))
def community_disagreements(ctx: Context, limit: int = 20) -> dict:
    return communities.disagreements(ctx.vault, limit)
