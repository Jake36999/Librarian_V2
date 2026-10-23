"""Bounded source capability extraction tools."""
from __future__ import annotations

from .. import extract
from ..registry import Card, Context, REGISTRY


@REGISTRY.tool("extract_plan", tier="consult", effect="read", resolve={"source": "note"},
               card=Card("Plan bounded, revision-pinned repository capability extraction.",
                         "you need files and dependencies for a repository capability without executing code"),
               returns=("source", "revision", "files", "unresolved"))
def extract_plan(ctx: Context, source: str, seed: str = "", include_tests: bool = False,
                 max_files: int = 20, max_chars: int = 80_000) -> dict:
    return extract.plan(ctx.vault, source, seed, include_tests, max_files, max_chars,
                        index_service=ctx.extras.get("index_service"))


@REGISTRY.tool("extract_materialize", tier="curate", effect="write", scope="library",
               open_world=True, resolve={"source": "note"},
               card=Card("Fetch bounded source excerpts at a pinned surveyed revision.",
                         "a person reviewed an extract plan and needs the attributed code material"),
               returns=("source", "revision", "excerpts", "cache"))
def extract_materialize(ctx: Context, source: str, seed: str = "", include_tests: bool = False,
                        max_files: int = 20, max_chars: int = 80_000) -> dict:
    return extract.materialize(ctx.vault, source, seed=seed, include_tests=include_tests,
                               max_files=max_files, max_chars=max_chars,
                               fetcher=ctx.extras.get("fetcher"),
                               index_service=ctx.extras.get("index_service"))
