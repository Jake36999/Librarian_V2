"""ADAPT-11: compact default surfaces and bounded oversized read results.

MF-012: durable references survive worker exit and Core restart."""
from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone

from resource_librarian import intake
from resource_librarian.agent_runtime import MAX_BUNDLE_TOOLS
from resource_librarian.loop import Loop
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.result_handles import (REFERENCE_RETENTION_DAYS, REFERENCE_STATUSES,
                                                RESULT_PROJECTION_CHARS, ReferenceStore,
                                                durable_text, reference_id, serialise_result)
from resource_librarian.vault import Vault

from conftest import write_note


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

    # MF-012: a handle from another Loop is expired, said as such, not a bad argument.
    assert refused["error"] == "refused" and refused["refused"] == "REFERENCE_UNRESOLVED"
    assert refused["status"] == "expired" and "ephemeral" in refused["detail"]
    assert "private" not in json.dumps(refused)
    assert second.call("read_result", {"handle": "sha256:nope"})["error"] == "invalid_arguments"


def test_small_and_non_read_results_keep_their_existing_shape(vault):
    loop = Loop(vault, Provider())
    small = {"found": True, "sections": {"opening": "short"}}
    large_write = {"path": "Notes/large.md", "body": "x" * 10_000}

    assert loop._result_handles.project("get_note", small) is small  # noqa: SLF001
    assert loop._result_handles.project("write_note", large_write) is large_write  # noqa: SLF001


# --- MF-012: durable references across worker exit and Core restart ---------

BIG = "Evidence line, kept exactly. " * 400            # about 11,600 characters


def big_note(vault, name="Big Finding", body=BIG):
    write_note(vault.root, f"Notes/{name}.md", "type: note", f"## Findings\n\n{body}\n")


def raw_read(vault, tool, arguments, **extras):
    """The read as an unprojected registry call makes it: what a reference vouches for."""
    return REGISTRY.call(tool, arguments, Context(tier="consult", vault=vault, extras=extras))


def page(loop, handle):
    pieces, offset = [], 0
    while True:
        chunk = loop.call("read_result", {"handle": handle, "offset": offset})
        assert "error" not in chunk, chunk
        assert len(chunk["text"]) <= 3_000
        pieces.append(chunk["text"])
        offset = chunk["next_offset"]
        if chunk["complete"]:
            return "".join(pieces)


def unresolved(out, status):
    assert out.get("error") == "refused" and out.get("refused") == "REFERENCE_UNRESOLVED", out
    assert out["status"] == status, out
    assert "text" not in out
    return out


def counting(monkeypatch, tool):
    """How many times the registry runs `tool`, inner re-reads included."""
    seen = []
    original = REGISTRY.call

    def call(name, arguments, ctx):
        if name == tool:
            seen.append(dict(arguments or {}))
        return original(name, arguments, ctx)

    monkeypatch.setattr(REGISTRY, "call", call)
    return seen


def minted(vault, name="Big Finding"):
    loop = Loop(vault, Provider())
    projected = loop.call("get_note", {"name": name})
    assert projected["oversized_result"] is True and projected["durable"] is True
    return projected


def test_a_reference_reopens_the_exact_bytes_after_its_loop_and_the_core_are_gone(
        vault, monkeypatch):
    big_note(vault)
    projected = minted(vault, "[[Big Finding]]")
    reference = projected["reference"]
    assert reference.startswith("ref:")
    assert projected["retrieval"]["arguments"]["handle"] == reference
    assert len(serialise_result(projected)) <= RESULT_PROJECTION_CHARS
    record = json.loads((vault.librarian / "references" / f"{reference[4:]}.json")
                        .read_text(encoding="utf-8"))
    assert record["arguments"] == {"name": "Big Finding"}        # pinned to the note read
    assert "Evidence line" not in json.dumps(record)              # a locator, never content

    expected = durable_text(raw_read(vault, "get_note", {"name": "Big Finding"}))
    reads = counting(monkeypatch, "get_note")
    restarted = Loop(Vault(vault.root), Provider())               # nothing in memory survives

    assert page(restarted, reference) == expected
    assert len(reads) == 1                                        # read again once, then paged
    assert json.loads(expected)["sections"]["Findings"].startswith("Evidence line, kept")
    # The ended Loop's ephemeral handle is not presented as durable.
    unresolved(restarted.call("read_result", {"handle": projected["result_handle"]}), "expired")


def test_a_helpers_reference_outlives_the_helper(vault):
    from resource_librarian import effort
    from resource_librarian.providers import Reply, ToolCall
    from test_effort import Scripted
    big_note(vault)

    def helper_step(messages, tools):
        if not any(message["role"] in {"assistant", "tool"} for message in messages):
            return Reply(tool_calls=[ToolCall("g", "get_note", {"name": "Big Finding"})])
        return Reply(text="the finding is in Big Finding")

    provider = Scripted([helper_step] * 6)
    lead = Context(tier="contribute", vault=vault,
                   extras={"effort": effort.profile(1), "agent_provider": lambda tier: provider})
    out = REGISTRY.call("delegate", {"questions": ["where is the finding?"], "tier": 1}, lead)

    listed = out["results"][0]["references"]
    assert [(item["tool"], item["reference"][:4]) for item in listed] == [("get_note", "ref:")]
    parent = Loop(vault, Provider())                              # the helper's Loop is gone
    assert page(parent, listed[0]["reference"]) == durable_text(
        raw_read(vault, "get_note", {"name": "Big Finding"}))


def test_a_changed_or_deleted_source_is_said_so_never_returned_as_the_cited_bytes(vault):
    big_note(vault)
    reference = minted(vault)["reference"]
    big_note(vault, body=BIG + "A LATER EDIT.")

    changed = unresolved(Loop(vault, Provider()).call("read_result", {"handle": reference}),
                         "changed")
    assert "A LATER EDIT" not in json.dumps(changed)
    assert "get_note shows the current version" in changed["detail"]

    (vault.root / "Notes" / "Big Finding.md").unlink()
    unresolved(Loop(vault, Provider()).call("read_result", {"handle": reference}), "missing")


def test_an_expired_reference_lapses_without_reading_its_source(vault, monkeypatch):
    big_note(vault)
    raw = raw_read(vault, "get_note", {"name": "Big Finding"})
    record = ReferenceStore(vault).mint(
        "get_note", {"name": "Big Finding"}, raw, durable_text(raw),
        now=datetime.now(timezone.utc) - timedelta(days=REFERENCE_RETENTION_DAYS + 1))
    reads = counting(monkeypatch, "get_note")

    out = unresolved(Loop(vault, Provider()).call("read_result",
                                                  {"handle": record["reference"]}), "expired")

    assert reads == [] and f"{REFERENCE_RETENTION_DAYS} days" in out["detail"]


def test_a_reader_without_access_now_is_refused_and_learns_nothing_about_the_source(
        vault, tmp_path):
    from resource_librarian.init import init
    big_note(vault)
    projected = minted(vault)
    reference = projected["reference"]

    narrow = Loop(vault, Provider())
    narrow.only = frozenset({"read_result"})                     # an allowlist without get_note
    refused = unresolved(narrow.call("read_result", {"handle": reference}), "forbidden")

    init(tmp_path / "other", name="Other Vault")
    elsewhere = unresolved(Loop(Vault(tmp_path / "other"), Provider()).call(
        "read_result", {"handle": reference}), "unknown")
    for out in (refused, elsewhere):
        shown = json.dumps(out)
        assert "Big Finding" not in shown and "Evidence line" not in shown
        assert str(projected["characters"]) not in shown
        assert projected["reference_sha256"] not in shown and "get_note" not in out["detail"]


def test_a_reference_survives_a_phase_bundle_without_reopening_the_registry(vault):
    big_note(vault)
    reference = minted(vault)["reference"]
    loop = Loop(vault, Provider())
    loop.ctx.extras.update(enforce_active_bundle=True, active_bundle=["read_result"])

    assert loop.call("get_note", {"name": "Big Finding"})["refused"] == "TOOL_BUNDLE_REFUSED"
    assert page(loop, reference).startswith('{"found":true')
    assert "reference_rehydration" not in loop.ctx.extras


def test_a_withdrawn_reference_stops_everywhere_and_is_not_revived(vault, monkeypatch):
    big_note(vault)
    reference = minted(vault)["reference"]
    contribute = Context(tier="contribute", vault=vault)
    assert REGISTRY.call("withdraw_reference", {"reference": reference},
                         contribute)["refused"] == "TIER_REFUSED"

    person = Context(tier="curate", vault=vault, extras={"caller_kind": "person"})
    done = REGISTRY.call("withdraw_reference", {"reference": reference, "reason": "private"},
                         person)
    assert done["suppresses"] == "retrieval" and done["withdrawn_at"]
    reads = counting(monkeypatch, "get_note")

    out = unresolved(Loop(Vault(vault.root), Provider()).call("read_result",
                                                             {"handle": reference}),
                     "withdrawn")
    assert reads == [] and "not deleted" in out["detail"]
    assert (vault.root / "Notes" / "Big Finding.md").is_file()   # retrieval, not deletion
    assert ReferenceStore(vault).load(reference) is not None      # the record stays for audit

    again = Loop(vault, Provider())
    projected = again.call("get_note", {"name": "Big Finding"})
    assert projected["durable"] is False and "reference" not in projected
    assert page(again, projected["result_handle"])                # this Loop's own read still pages


def test_no_reference_opens_a_file_or_runs_another_tool(vault, monkeypatch):
    (vault.root / "secret.txt").write_text("TOP SECRET", encoding="utf-8")
    loop = Loop(vault, Provider())
    assert loop.call("read_result", {"handle": "ref:../../secret"})["error"] == "invalid_arguments"

    folder = vault.librarian / "references"
    folder.mkdir(parents=True, exist_ok=True)
    forged_args = {"path": "secret.txt"}
    forged = reference_id("read_file", forged_args, "0" * 64)
    (folder / f"{forged[4:]}.json").write_text(json.dumps({
        "reference": forged, "tool": "read_file", "arguments": forged_args, "sha256": "0" * 64,
        "representation": "tool-result/v1", "kept_until": "2999-01-01T00:00:00+00:00"}),
        encoding="utf-8")
    reads = counting(monkeypatch, "read_file")
    out = unresolved(loop.call("read_result", {"handle": forged}), "unknown")
    assert reads == [] and "TOP SECRET" not in json.dumps(out)

    big_note(vault)
    big_note(vault, "Other Finding")
    reference = minted(vault)["reference"]
    path = folder / f"{reference[4:]}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["arguments"]["name"] = "Other Finding"                 # tampered: id no longer matches
    path.write_text(json.dumps(record), encoding="utf-8")
    unresolved(Loop(vault, Provider()).call("read_result", {"handle": reference}), "unknown")


def test_search_results_stay_ephemeral_and_say_so(vault):
    loop = Loop(vault, Provider())
    projected = loop._result_handles.project(  # noqa: SLF001
        "search", {"results": [{"note": "x" * 7_000}]}, {"query": "x"})

    assert projected["durable"] is False and "reference" not in projected
    assert "not durably referenced" in projected["lifetime"]
    assert not any((vault.librarian / "references").glob("*.json"))


def test_a_repository_file_reference_reads_the_surveyed_bytes_again_or_says_unavailable(vault):
    from test_upkeep import surveyed
    surveyed(vault, tree="abc123")
    api = "https://api.github.com/repos/example/planner"
    code = "".join(f"def step_{i}():\n    return {i}\n" for i in range(500))
    responses = {
        f"{api}/git/trees/abc123?recursive=1": {"tree": [
            {"path": "src/plan.py", "type": "blob", "sha": "b1"}]},
        f"{api}/git/blobs/b1": {"content": base64.b64encode(code.encode()).decode()}}
    first = Loop(vault, Provider(), extras={"fetcher": intake.Replay(dict(responses))})
    projected = first.call("read_source_file", {"source": "planner", "path": "src/plan.py",
                                                "max_chars": 60_000})
    reference = projected["reference"]

    restarted = Loop(Vault(vault.root), Provider(),
                     extras={"fetcher": intake.Replay(dict(responses))})
    text = page(restarted, reference)
    assert json.loads(text)["text"] == code
    assert json.loads(text)["version"].startswith("tree abc123")

    offline = Loop(Vault(vault.root), Provider(), extras={"fetcher": intake.Replay({})})
    out = unresolved(offline.call("read_result", {"handle": reference}), "unavailable")
    assert "def step_" not in json.dumps(out)


def test_every_status_is_one_of_the_declared_ones():
    assert set(REFERENCE_STATUSES) == {"changed", "missing", "expired", "forbidden",
                                       "withdrawn", "unavailable", "unknown"}
