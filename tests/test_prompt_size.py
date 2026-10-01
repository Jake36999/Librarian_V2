"""M0 (2026-10-01): the lead's prompt was 42,000-74,000 tokens a call, almost all of it older
tool results. The model is sent a compacted view; the log keeps everything."""
import json
import tempfile
from pathlib import Path

from resource_librarian import loop as loop_mod
from resource_librarian.init import init
from resource_librarian.loop import KEEP_RESULTS, Loop
from resource_librarian.vault import Vault


class Provider:
    name = "test"


def make_loop():
    root = Path(tempfile.mkdtemp()) / "v"
    init(root, name="t")
    return Loop(Vault(root), Provider(), tier="contribute")


def test_older_results_lose_their_envelope_and_are_clipped_the_recent_are_whole():
    lp = make_loop()
    big = {"results": ["x" * 400] * 10, "session": {"phase": "search", "open_items": ["a"] * 50}}
    for i in range(KEEP_RESULTS + 24):              # a long research turn
        lp.messages.append({"role": "assistant", "content": "",
                            "tool_calls": [{"id": f"c{i}", "name": "write_note",
                                            "arguments": {"body": "y" * 2000}}]})
        lp.messages.append({"role": "tool", "tool_call_id": f"c{i}", "name": "search",
                            "content": json.dumps(big)})
    view = lp.view()
    tools = [m for m in view if m["role"] == "tool"]
    calls = [m for m in view if m.get("tool_calls")]
    assert all(m["content"] == json.dumps(big) for m in tools[-KEEP_RESULTS:])
    old = tools[0]["content"]
    assert '"session"' not in old and "older result" in old
    assert len(old) < 900
    assert len(calls[0]["tool_calls"][0]["arguments"]["body"]) < 400
    assert calls[-1]["tool_calls"][0]["arguments"]["body"] == "y" * 2000
    assert lp.messages[1]["content"] == json.dumps(big)          # the log itself is whole
    assert sum(len(json.dumps(m)) for m in view) < \
        sum(len(json.dumps(m)) for m in lp.messages) / 2


def test_upkeep_tools_are_not_offered_while_a_session_is_working():
    lp = make_loop()
    outside = {t.name for t in lp.tools()}
    assert "vault_commit" in outside and "doctor" in outside
    lp.call("open_session", {"purpose": "explore", "question": "q"})
    working = {t.name for t in lp.tools()}
    assert "vault_commit" not in working and "doctor" not in working
    assert {"web_search", "ingest", "advance", "capabilities"} <= working
    assert not working & loop_mod.UPKEEP_TOOLS
