"""Standard model catalogues: adopt a provider's already-profiled models
instead of profiling each one again in every vault (`model_catalog.py`)."""
from __future__ import annotations

from .. import model_catalog
from ..registry import Card, Context, tool
from .library import IndexGateway, with_engine


@tool("model_catalog_status", tier="consult", effect="read",
      returns=("catalogues",),
      card=Card("Standard model catalogues this install ships, and how much of each this "
                "vault already holds",
                "picking a chat model with none profiled yet, or after a new provider's "
                "catalogue is added"))
def model_catalog_status(ctx: Context) -> dict:
    return {"catalogues": with_engine(ctx, lambda engine: model_catalog.status(ctx.vault, engine), refresh=False)}


@tool("model_catalog_adopt", tier="curate", effect="vault_write", scope="library",
      orchestrates=True,
      returns=("provider", "written", "already_held", "failed"),
      card=Card("Adopt a standard model catalogue: its models join this vault as accepted "
                "sources, already-reviewed evidence and all",
                "a provider's catalogue is ready and the person wants its models available "
                "without profiling each one by hand",
                "Person-only: each entry was reviewed once already; adopting it is reusing "
                "that review, not a fresh unreviewed draft. Already-held models (by note name) are "
                "skipped, not duplicated"))
def model_catalog_adopt(ctx: Context, provider: str) -> dict:
    gateway = IndexGateway(ctx, include_vectors=False)
    writer = ctx.extras.get("vault_writer")
    def commit(fn, plan):
        if writer is not None:
            return writer.submit(fn, caller="model-catalog", targets=plan["targets"],
                                 preconditions=dict(plan["observed"]))
        return fn()  # Offline CLI retains its outer interprocess mutation lease.
    try:
        result = model_catalog.adopt(ctx.vault, None, provider, accepted_by="person",
            index_call=gateway.run, write_call=commit, leases=ctx.extras.get("document_leases"),
            cancelled=(ctx.extras["cancel"].is_set if ctx.extras.get("cancel") is not None else None),
            defer_embedding=writer is not None)
    except ValueError as exc:
        raise TypeError(str(exc)) from None
    conflicts = [f for f in result["failed"] if f.get("refused") == "DOCUMENT_ACTIVE"]
    checkpoints = ctx.extras.get("checkpoints")
    if conflicts and checkpoints is not None:
        create = lambda: checkpoints.create("write_conflict", "Catalogue adoption needs review",
            evidence={"tool": "model_catalog_adopt", "provider": provider,
                      "written": result["written"], "conflicts": conflicts[:10]},
            choices=["wait", "retry_after_review", "cancel"], requester="person")
        result["checkpoint"] = writer.submit(create, caller="catalogue-conflict") if writer else create()
    return result
