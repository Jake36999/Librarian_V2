"""Bounded retrieval of an oversized result already returned to this Loop."""
from __future__ import annotations

from ..registry import Card, Context, tool
from ..result_handles import RESULT_CHUNK_CHARS, ResultHandleStore


@tool("read_result", tier="consult", effect="read", needs_vault=False,
      returns=("result_handle", "offset", "text", "next_offset", "complete", "characters"),
      card=Card("Read one bounded chunk of an oversized result by its content-addressed handle",
                "read_source_file, get_note or search returned an oversized_result and its "
                "preview was not enough",
                "The handle is private to this conversation loop and grants no new vault, "
                "network or mutation authority"))
def read_result(ctx: Context, handle: str, offset: int = 0,
                max_chars: int = RESULT_CHUNK_CHARS) -> dict:
    store = ctx.extras.get("_result_handles")
    if not isinstance(store, ResultHandleStore):
        raise TypeError("result handles are available only inside the conversation that made them")
    return store.read(handle, offset, max_chars)
