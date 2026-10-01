"""Topics, as tools (see `taxonomy.py`). Proposing is the librarian's; accepting a topic
is a person's (`staging_decide` on a `topic` item, from Settings -> Library)."""
from __future__ import annotations

from .. import taxonomy
from ..promote import UNFILED
from ..registry import Card, Context, tool
from .library import engine_for
from .staging import clerk_endpoint


@tool("topics_list", tier="consult", effect="read",
      returns=("topics", "unfiled", "proposed"),
      card=Card("The accepted topics with their source counts, how many sources are Unfiled, "
                "and the topics proposed for a person to accept",
                "before filing, or to see whether the library needs topics"))
def topics_list(ctx: Context) -> dict:
    from ..staging import StagingStore
    counts: dict[str, int] = {}
    for s in taxonomy.sources(engine_for(ctx)):
        counts[s["topic"]] = counts.get(s["topic"], 0) + 1
    return {"topics": [{"topic": t, "sources": counts.get(t, 0)} for t in ctx.vault.topics()],
            "unfiled": counts.get(UNFILED, 0),
            "not_accepted": sorted(set(counts) - set(ctx.vault.topics())),
            "proposed": [{"id": i["id"], "name": i["name"], "sources": len(i.get("members", [])),
                          **({"duplicate_of": i["duplicate_of"]} if i.get("duplicate_of")
                             else {})}
                         for i in StagingStore(ctx.vault).items("topic", "staged")]}


@tool("topic_propose", tier="contribute", effect="write", scope="library",
      returns=("proposed", "refile", "considered"),
      card=Card("Propose topics from the sources the library holds, staged for a person to "
                "accept, with examples, coverage and alias suggestions",
                "many sources are Unfiled, or the topic list no longer fits the library",
                "Proposes only: a topic joins About/Topics.md when a person accepts it. "
                "Sources that fit an accepted topic come back as refile suggestions. Runs on "
                "the clerk channel"))
def topic_propose(ctx: Context, only_unfiled: bool = True) -> dict:
    return taxonomy.propose(ctx.vault, engine_for(ctx), clerk_endpoint(ctx), only_unfiled)


@tool("refile_source", tier="contribute", effect="vault_write", scope="library",
      resolve={"sources": "note"}, returns=("results",),
      card=Card("File catalogued sources under an accepted topic, and rewrite the topic "
                "indexes this changes", "a topic_propose refile suggestion, or a source "
                "filed under the wrong topic", "Accepted topics only (About/Topics.md)"))
def refile_source(ctx: Context, sources: list[str], topic: str) -> dict:
    return {"results": taxonomy.refile(ctx.vault, engine_for(ctx), sources, topic)}


@tool("views_refresh", tier="contribute", effect="vault_write", scope="library",
      returns=("written", "not_accepted"),
      card=Card("Rewrite the generated topic indexes and the Master Index from the notes",
                "after notes were edited or refiled outside the librarian, or the indexes "
                "look stale"))
def views_refresh(ctx: Context) -> dict:
    return taxonomy.refresh_views(ctx.vault, engine_for(ctx))
