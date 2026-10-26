"""Loop-local, content-addressed storage for oversized tool results.

The registry remains the authority boundary: this store cannot execute a tool
or read a vault.  It only lets the same Loop retrieve bytes that one of its
already-authorised read calls returned.  Results deliberately remain in
memory, scoped to that loop, rather than becoming an unreviewed vault or disk
artifact.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


RESULT_HANDLE_THRESHOLD = 6_000
RESULT_PROJECTION_CHARS = 4_800
RESULT_CHUNK_CHARS = 3_000
HANDLED_TOOLS = frozenset({"read_source_file", "get_note", "search"})


def serialise_result(result: dict[str, Any]) -> str:
    """One deterministic representation: both the digest and retrieval bytes."""
    return json.dumps(result, ensure_ascii=False, default=str, sort_keys=True,
                      separators=(",", ":"))


class ResultHandleStore:
    """Exact result text keyed by its SHA-256 digest, private to one Loop."""

    def __init__(self) -> None:
        self._items: dict[str, str] = {}

    def project(self, tool: str, result: dict[str, Any]) -> dict[str, Any]:
        """Return a bounded preview for a supported oversized read result."""
        if tool not in HANDLED_TOOLS or "error" in result:
            return result
        content = serialise_result(result)
        if len(content) <= RESULT_HANDLE_THRESHOLD:
            return result
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        handle = f"sha256:{digest}"
        self._items[handle] = content

        # Keep the current workflow envelope visible even when the result body
        # is large.  It is Core-authored state, not part of the untrusted
        # preview, and tells the model which phase/action is legal next.
        session = result.get("session")
        if not isinstance(session, dict):
            session = None
        projected: dict[str, Any] = {
            "oversized_result": True,
            "tool": tool,
            "result_handle": handle,
            "sha256": digest,
            "characters": len(content),
            "preview": "",
            "retrieval": {
                "tool": "read_result",
                "arguments": {"handle": handle, "offset": 0},
                "note": "Read bounded chunks only when the preview does not answer the task.",
            },
        }
        if session is not None:
            projected["session"] = session

        def fit_preview() -> None:
            # JSON escaping can expand a preview, so size it against the
            # actual wire representation rather than assuming one byte per
            # character.
            low, high = 0, len(content)
            while low < high:
                middle = (low + high + 1) // 2
                projected["preview"] = content[:middle]
                if len(serialise_result(projected)) <= RESULT_PROJECTION_CHARS:
                    low = middle
                else:
                    high = middle - 1
            projected["preview"] = content[:low]

        fit_preview()
        # A pathological session envelope could consume the entire bound.
        # Preserve the fields needed to follow the workflow, then repeat the
        # sizing pass rather than returning an unbounded projection.
        if len(serialise_result(projected)) > RESULT_PROJECTION_CHARS:
            projected["session"] = {
                key: session[key] for key in ("session", "status", "phase", "budget_left", "next")
                if session is not None and key in session
            }
            fit_preview()
        if len(serialise_result(projected)) > RESULT_PROJECTION_CHARS:
            # An adversarially large Core envelope cannot defeat the bound.
            # The exact envelope remains in the content-addressed result.
            projected.pop("session", None)
            fit_preview()
        return projected

    def read(self, handle: str, offset: int = 0,
             max_chars: int = RESULT_CHUNK_CHARS) -> dict[str, Any]:
        """Read one bounded chunk without granting access to any other loop."""
        content = self._items.get(handle)
        if content is None:
            raise TypeError("unknown or expired result handle for this loop")
        start = max(0, int(offset))
        size = max(1, min(RESULT_CHUNK_CHARS, int(max_chars)))
        if start > len(content):
            raise TypeError(f"offset {start} is past the {len(content)}-character result")
        end = min(len(content), start + size)
        return {
            "result_handle": handle,
            "offset": start,
            "text": content[start:end],
            "next_offset": end,
            "complete": end == len(content),
            "characters": len(content),
        }
