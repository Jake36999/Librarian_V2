"""Scouting: discovery, ranking, cohorts and the gated sweep."""
from __future__ import annotations

from .. import scout
from ..registry import Card, Context, tool
from .intake import _fetcher
from .library import engine_for
from .staging import clerk_endpoint


@tool("scout_discover", tier="contribute", effect="write", phases=("search",), open_world=True,
      returns=("added", "corroborated", "already_held", "errors"),
      card=Card("Search GitHub with the domain register's seed queries for candidates",
                "the vault is thin somewhere and you want what nobody has named yet",
                "Candidates are recorded, ranked and never ingested by this call"))
def scout_discover(ctx: Context, domain: str = "", per_query: int = 15) -> dict:
    return scout.discover(ctx.vault, _fetcher(ctx), domain, per_query)


@tool("scout_expand", tier="contribute", effect="write", phases=("search",), open_world=True,
      card=Card("Read catalogued curated lists (container: true) into candidates",
                "the vault holds awesome-lists or other curated indexes"))
def scout_expand(ctx: Context) -> dict:
    return scout.expand_containers(ctx.vault, _fetcher(ctx))


@tool("scout_rank", tier="consult", effect="read",
      card=Card("Candidates in order, with every signal that placed them",
                "choosing what to ingest next", "Ranking orders work; it never selects it"))
def scout_rank(ctx: Context, limit: int = 20) -> dict:
    usage = ctx.vault.config().get("usage", {})
    role = str(usage.get("catalogue_role") or "reference")
    posture = str(usage.get("distribution_posture") or "private")
    ranked = scout.rank(ctx.vault)
    return {"total": len(ranked), "candidates": ranked[:limit],
            "audit": {"role": role, "posture": posture,
                      "archived_unstarred_unlicensed_scores": scout.audit(role, posture)}}


@tool("cohort_freeze", tier="contribute", effect="write", phases=("search",),
      card=Card("Freeze the top candidates into a cohort and write it to a visible note",
                "before a sweep: the cohort is the reviewable unit"))
def cohort_freeze(ctx: Context, size: int = 20) -> dict:
    return scout.freeze_cohort(ctx.vault, size)


@tool("cohort_reviewed", tier="curate", effect="write", scope="library",
      card=Card("Mark a cohort as read by a person", "you have read the cohort note",
                "Person-only: the next sweep waits for this, and a model marking its own "
                "sweep read would let scouting run unattended without anyone reading it"))
def cohort_reviewed(ctx: Context, cohort_id: str) -> dict:
    return scout.mark_reviewed(ctx.vault, cohort_id, "person")


@tool("sweep", tier="contribute", effect="write", phases=("search",), open_world=True,
      returns=("cohort", "results", "stopped", "staged"),
      card=Card("Ingest the next members of the current cohort, unattended, into staging",
                "retrieval has passed its eval and the last cohort was read",
                "Refused until both gates pass (SWEEP_GATED); stops when a run of candidates "
                "brings nothing new; stages only"))
def sweep(ctx: Context, limit: int = 10) -> dict:
    return scout.sweep(ctx.vault, engine_for(ctx), clerk_endpoint(ctx), _fetcher(ctx), limit)


@tool("record_trace", tier="contribute", effect="write", scope="session",
      returns=("rounds", "checkpoints", "sources_in_rounds", "cited_links", "trace", "refs"),
      card=Card("Record another tool's research process (a Deep Research trace) as evidence "
                "and as a replayable trace", "the person brings a report from another tool",
                "Every cited link becomes evidence; nothing it claims becomes a fact until "
                "fetched and verified by ingest"))
def record_trace(ctx: Context, path: str, tool_name: str = "external research tool") -> dict:
    from pathlib import Path
    from .. import trace
    target = (ctx.vault.root / path).resolve()
    if ctx.vault.root not in target.parents or not target.is_file():
        raise TypeError(f"{path!r} is not a file inside this vault")
    return trace.record(ctx.vault, Path(target), tool_name)
