"""Bounded retrieval of oversized results, and withdrawing a durable reference."""
from __future__ import annotations

from ..registry import Card, Context, tool
from ..result_handles import (REFERENCE_PREFIX, RESULT_CHUNK_CHARS, ReferenceStore,
                              ResultHandleStore, read_reference)


@tool("read_result", tier="consult", effect="read", needs_vault=False,
      returns=("offset", "text", "next_offset", "complete", "characters"),
      card=Card("Read one bounded chunk of an oversized result by its handle or durable "
                "reference",
                "read_source_file, get_note or search returned an oversized_result and its "
                "preview was not enough, or a helper or an earlier conversation cited a "
                "reference",
                "A sha256: handle lasts only for this conversation loop. A ref: reference "
                "outlives it (a helper finishing, the app restarting): it reads the source "
                "again under your access now and returns the cited bytes only if they are "
                "unchanged, or says why not. Neither grants new vault, network or mutation "
                "authority"))
def read_result(ctx: Context, handle: str, offset: int = 0,
                max_chars: int = RESULT_CHUNK_CHARS) -> dict:
    store = ctx.extras.get("_result_handles")
    store = store if isinstance(store, ResultHandleStore) else None
    handle = str(handle).strip()
    if handle.startswith(REFERENCE_PREFIX):
        return read_reference(ctx, handle, offset, max_chars, store=store)
    if store is None:
        raise TypeError("result handles are available only inside the conversation that made "
                        "them; a durable ref: reference can be read anywhere in its library")
    return store.read(handle, offset, max_chars)


@tool("withdraw_reference", tier="curate", effect="write", scope="library",
      returns=("reference", "withdrawn_at", "suppresses", "kept"),
      card=Card("Withdraw a durable result reference from retrieval",
                "a person no longer wants a cited oversized read reopened by any "
                "conversation or helper",
                "Retrieval only: the reference stops resolving everywhere, now and after a "
                "restart, and a later identical read does not revive it. Its record is kept "
                "for audit; the note or file it points at is not touched"))
def withdraw_reference(ctx: Context, reference: str, reason: str = "") -> dict:
    caller = str(ctx.extras.get("caller") or ctx.extras.get("caller_kind") or ctx.tier)
    return ReferenceStore(ctx.vault).withdraw(str(reference).strip(), by=caller, reason=reason)
