"""Manual, offline retrieval-ranking experiment tools."""
from __future__ import annotations

from .. import ranking
from ..registry import Card, Context, REGISTRY
from ..rules import Refusal
from .library import engine_for


def _require_person(ctx: Context, action: str) -> None:
    if ctx.extras.get("caller_kind") != "person":
        raise Refusal("PERSON_CONFIRMS", f"{action} needs an explicit person action in the browser or CLI")


@REGISTRY.tool("ranking_status", tier="consult", effect="read",
               card=Card("Show local retrieval-ranking evidence, candidates and active policy.",
                         "checking whether personal search feedback supports an experiment"),
               returns=("active", "evidence", "candidates"))
def ranking_status(ctx: Context) -> dict:
    return ranking.status(ctx.vault)


@REGISTRY.tool("ranking_candidate_generate", tier="contribute", effect="write", scope="library",
               card=Card("Generate a bounded local ranking candidate from existing feedback.",
                         "enough normalised local search feedback has accumulated",
                         "It changes no live ranking; a benchmark and a person's selection still follow"),
               returns=("generated", "candidate"))
def ranking_candidate_generate(ctx: Context) -> dict:
    return ranking.generate(ctx.vault, engine_for(ctx).h)


@REGISTRY.tool("ranking_benchmark", tier="contribute", effect="write", scope="library",
               card=Card("Benchmark one retrieval-ranking candidate offline against held-out vault questions.",
                         "a candidate exists and the person wants evidence before selecting it",
                         "No traffic split or automatic adoption occurs"),
               returns=("quality", "coverage", "safety"))
def ranking_benchmark(ctx: Context, candidate_id: str, k: int = 5) -> dict:
    return ranking.benchmark(ctx.vault, engine_for(ctx), candidate_id, k)


@REGISTRY.tool("ranking_compare", tier="consult", effect="read",
               card=Card("Compare Current and Candidate rankings side by side for one query.",
                         "a person wants to inspect the practical difference before selecting a policy"),
               returns=("current", "candidate_result"))
def ranking_compare(ctx: Context, query: str, intent: str = "donor", limit: int = 10,
                    candidate_id: str = "") -> dict:
    return ranking.compare(ctx.vault, engine_for(ctx), query, intent, limit, candidate_id)


@REGISTRY.tool("ranking_select", tier="curate", effect="write", scope="library",
               card=Card("Select a locally benchmarked retrieval-ranking candidate.",
                         "a person reviewed its offline benchmark and comparison",
                         "A person chooses it; the system never percentages live traffic"),
               returns=("active", "previous"))
def ranking_select(ctx: Context, candidate_id: str) -> dict:
    _require_person(ctx, "selecting a ranking policy")
    return ranking.select(ctx.vault, candidate_id)


@REGISTRY.tool("ranking_restore", tier="curate", effect="write", scope="library",
               card=Card("Restore the previous manually selected retrieval-ranking policy.",
                         "a candidate's live local results should be rolled back"),
               returns=("active", "restored"))
def ranking_restore(ctx: Context) -> dict:
    _require_person(ctx, "restoring a ranking policy")
    return ranking.restore(ctx.vault)

