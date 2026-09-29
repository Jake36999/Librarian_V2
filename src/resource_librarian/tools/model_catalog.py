"""Standard model catalogues: adopt a provider's already-profiled models
instead of profiling each one again in every vault (`model_catalog.py`)."""
from __future__ import annotations

from .. import model_catalog
from ..registry import Card, Context, tool
from .library import engine_for


@tool("model_catalog_status", tier="consult", effect="read",
      returns=("catalogues",),
      card=Card("Standard model catalogues this install ships, and how much of each this "
                "vault already holds",
                "picking a chat model with none profiled yet, or after a new provider's "
                "catalogue is added"))
def model_catalog_status(ctx: Context) -> dict:
    return {"catalogues": model_catalog.status(ctx.vault, engine_for(ctx, refresh=False))}


@tool("model_catalog_adopt", tier="curate", effect="vault_write",
      returns=("provider", "written", "already_held", "failed"),
      card=Card("Adopt a standard model catalogue: its models join this vault as accepted "
                "sources, already-reviewed evidence and all",
                "a provider's catalogue is ready and the person wants its models available "
                "without profiling each one by hand",
                "Person-only: each entry was reviewed once already; adopting it is reusing "
                "that review, not a fresh unreviewed draft. Already-held models (by URL) are "
                "skipped, not duplicated"))
def model_catalog_adopt(ctx: Context, provider: str) -> dict:
    try:
        return model_catalog.adopt(ctx.vault, engine_for(ctx), provider, accepted_by="person")
    except ValueError as exc:
        raise TypeError(str(exc)) from None
