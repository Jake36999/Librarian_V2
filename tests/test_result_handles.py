"""ADAPT-11: compact default surfaces and bounded oversized read results."""
from __future__ import annotations

from resource_librarian.agent_runtime import MAX_BUNDLE_TOOLS
from resource_librarian.loop import Loop
from resource_librarian.registry import REGISTRY
from resource_librarian.result_handles import (RESULT_PROJECTION_CHARS,
                                                serialise_result)


class Provider:
    name = "test"


def test_a_bare_loop_uses_a_task_sized_bundle_by_default(vault):
    loop = Loop(vault, Provider())

    offered = {tool.name for tool in loop.tools()}

    assert 0 < len(offered) <= MAX_BUNDLE_TOOLS
    assert "open_session" in offered
    assert "read_result" in offered
    assert loop.ctx.extras["enforce_active_bundle"] is True
    assert offered == set(loop.ctx.extras["active_bundle"])


def test_an_explicit_full_surface_opt_out_and_helper_allowlist_still_win(vault):
    full = Loop(vault, Provider(), extras={"use_tool_bundles": False})
    assert len(full.tools()) > MAX_BUNDLE_TOOLS
    assert {"search", "get_note", "vault_commit"} <= {tool.name for tool in full.tools()}
    assert "enforce_active_bundle" not in full.ctx.extras

    helper = Loop(vault, Provider())
    helper.only = frozenset({"search", "get_note"})
    assert {tool.name for tool in helper.tools()} == {"search", "get_note"}


def test_a_50000_character_read_is_bounded_and_fully_retrievable(vault, monkeypatch):
    loop = Loop(vault, Provider())
    original_call = REGISTRY.call
    marker = "FULL-RESULT-END"
    original = {"source": "large", "path": "src/large.txt",
                "text": "x" * 50_000 + marker, "truncated": False}

    def large_read(name, arguments, ctx):
        if name == "read_source_file":
            return original
        return original_call(name, arguments, ctx)

    monkeypatch.setattr(REGISTRY, "call", large_read)
    projected = loop.call("read_source_file", {"source": "large", "path": "src/large.txt"})

    assert projected["oversized_result"] is True
    assert projected["result_handle"].startswith("sha256:")
    assert marker not in projected["preview"]
    assert len(serialise_result(projected)) <= RESULT_PROJECTION_CHARS

    pieces = []
    offset = 0
    while True:
        chunk = loop.call("read_result", {"handle": projected["result_handle"],
                                          "offset": offset})
        assert "error" not in chunk
        assert len(chunk["text"]) <= 3_000
        pieces.append(chunk["text"])
        offset = chunk["next_offset"]
        if chunk["complete"]:
            break

    assert "".join(pieces) == serialise_result(original)
    assert marker in pieces[-1]


def test_handles_are_scoped_to_the_loop_that_created_them(vault):
    first = Loop(vault, Provider())
    second = Loop(vault, Provider())
    projected = first._result_handles.project("get_note", {"sections": {  # noqa: SLF001
        "Evidence": "private" * 2_000}})

    refused = second.call("read_result", {"handle": projected["result_handle"]})

    assert refused["error"] == "invalid_arguments"
    assert "unknown or expired" in refused["detail"]


def test_small_and_non_read_results_keep_their_existing_shape(vault):
    loop = Loop(vault, Provider())
    small = {"found": True, "sections": {"opening": "short"}}
    large_write = {"path": "Notes/large.md", "body": "x" * 10_000}

    assert loop._result_handles.project("get_note", small) is small  # noqa: SLF001
    assert loop._result_handles.project("write_note", large_write) is large_write  # noqa: SLF001
