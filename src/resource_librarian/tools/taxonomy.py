"""Topics, as tools (see `taxonomy.py`). Proposing is the librarian's; accepting a topic
is a person's (`staging_decide` on a `topic` item, from Settings -> Library)."""
from __future__ import annotations

from .. import revisions, taxonomy
from ..promote import UNFILED
from ..registry import Card, Context, tool
from ..revisions import WriteIntent
from .library import IndexGateway, with_engine
from .staging import _snapshot, clerk_endpoint


@tool("topics_list", tier="consult", effect="read",
      returns=("topics", "unfiled", "proposed"),
      card=Card("The accepted topics with their source counts, how many sources are Unfiled, "
                "and the topics proposed for a person to accept",
                "before filing, or to see whether the library needs topics"))
def topics_list(ctx: Context) -> dict:
    from ..staging import StagingStore
    counts: dict[str, int] = {}
    for s in with_engine(ctx, taxonomy.sources):
        counts[s["topic"]] = counts.get(s["topic"], 0) + 1
    proposed = []
    for path in sorted(StagingStore(ctx.vault).folder("topic").glob("*.json")):
        item, state, stamp = _snapshot(ctx, path.stem)
        if item.get("status") != "staged":
            continue
        progress = item.get("acceptance_progress") or {}
        proposed.append({"id": item["id"], "name": item["name"], "sources": len(item.get("members", [])),
            "staged_revision": revisions.issue(ctx, state, stamp),
            **({"duplicate_of": item["duplicate_of"]} if item.get("duplicate_of") else {}),
            **({"acceptance_progress": {"topic": progress["topic"],
                "refile": progress["request"]["refile"], "completed_paths": progress["completed_paths"]}}
               if progress else {})})
    return {"topics": [{"topic": t, "sources": counts.get(t, 0)} for t in ctx.vault.topics()],
            "unfiled": counts.get(UNFILED, 0),
            "not_accepted": sorted(set(counts) - set(ctx.vault.topics())),
            "proposed": proposed}


@tool("topic_propose", tier="contribute", effect="write", scope="library",
      returns=("proposed", "refile", "considered"),
      card=Card("Propose topics from the sources the library holds, staged for a person to "
                "accept, with examples, coverage and alias suggestions",
                "many sources are Unfiled, or the topic list no longer fits the library",
                "Proposes only: a topic joins About/Topics.md when a person accepts it. "
                "Sources that fit an accepted topic come back as refile suggestions. Runs on "
                "the clerk channel"))
def topic_propose(ctx: Context, only_unfiled: bool = True) -> dict:
    return taxonomy.propose(ctx.vault, None, clerk_endpoint(ctx), only_unfiled,
                            index_call=IndexGateway(ctx).run)


def _intent(plan: dict) -> WriteIntent:
    return WriteIntent(tuple(plan["targets"]), observed=tuple(plan["observed"]), prepared=plan)


def _refile_intent(ctx: Context, kwargs: dict) -> WriteIntent:
    return _intent(taxonomy.prepare_refile(ctx.vault, None, kwargs["sources"], kwargs["topic"],
                                               index_call=IndexGateway(ctx).run))


def _views_intent(ctx: Context, kwargs: dict) -> WriteIntent:
    return _intent(taxonomy.prepare_views(ctx.vault, None, index_call=IndexGateway(ctx).run))


@tool("refile_source", tier="contribute", effect="vault_write", scope="library", intent=_refile_intent,
      resolve={"sources": "note"}, returns=("results",),
      card=Card("File catalogued sources under an accepted topic, and rewrite the topic "
                "indexes this changes", "a topic_propose refile suggestion, or a source "
                "filed under the wrong topic", "Accepted topics only (About/Topics.md)"))
def refile_source(ctx: Context, sources: list[str], topic: str) -> dict:
    return {"results": taxonomy.refile(ctx.vault, None, sources, topic, index_call=IndexGateway(ctx).run,
                                      prepared=ctx.extras.get("_prepared_write"),
                                      leases=ctx.extras.get("document_leases"))}


@tool("views_refresh", tier="contribute", effect="vault_write", scope="library", intent=_views_intent,
      returns=("written", "not_accepted"),
      card=Card("Rewrite the generated topic indexes and the Master Index from the notes",
                "after notes were edited or refiled outside the librarian, or the indexes "
                "look stale"))
def views_refresh(ctx: Context) -> dict:
    return taxonomy.refresh_views(ctx.vault, None, index_call=IndexGateway(ctx).run,
                                  prepared=ctx.extras.get("_prepared_write"),
                                  leases=ctx.extras.get("document_leases"))
