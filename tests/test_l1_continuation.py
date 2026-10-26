"""ADAPT-07: the L1 probe is a two-step tool continuation."""
import pytest
from resource_librarian.hosts import (
    validate_l1_continuation,
    continuation_messages,
    CONTINUATION_TOKEN,
)
from resource_librarian.providers import Reply, ToolCall


def _reply(text="", tool_calls=None, model="test-model", reasoning_content=""):
    return Reply(text=text, tool_calls=tool_calls or [], model=model, reasoning_content=reasoning_content)


def _tool_call(id_="call-1", name="librarian_probe", arguments=None):
    return ToolCall(id=id_, name=name, arguments=arguments or {"ok": True})


class TestValidateL1Continuation:
    def test_passing_continuation(self):
        first = _reply(tool_calls=[_tool_call()])
        final = _reply(text=f"Here is the token: {CONTINUATION_TOKEN}")
        result = validate_l1_continuation(first, final, "test-model")
        assert result["passed"] is True
        assert result["checks"]["tool_call_ids_unique"] is True
        assert result["checks"]["final_without_tool_call"] is True
        assert result["checks"]["final_answer"] is True
        assert result["checks"]["returned_model"] is True
        assert result["failure_codes"] == []

    def test_repeated_tool_call_fails(self):
        first = _reply(tool_calls=[_tool_call(id_="a")])
        final = _reply(text=CONTINUATION_TOKEN, tool_calls=[_tool_call(id_="b")])
        result = validate_l1_continuation(first, final, "test-model")
        assert result["passed"] is False
        assert "repeated_tool_call" in result["failure_codes"]

    def test_missing_token_fails(self):
        first = _reply(tool_calls=[_tool_call()])
        final = _reply(text="no token here")
        result = validate_l1_continuation(first, final, "test-model")
        assert result["passed"] is False
        assert "final_answer_missing" in result["failure_codes"]

    def test_duplicate_ids_fails(self):
        first = _reply(tool_calls=[_tool_call(id_="dup")])
        final = _reply(text=CONTINUATION_TOKEN, tool_calls=[_tool_call(id_="dup")])
        result = validate_l1_continuation(first, final, "test-model")
        assert result["passed"] is False
        assert "tool_call_ids" in result["failure_codes"]

    def test_empty_id_fails(self):
        first = _reply(tool_calls=[_tool_call(id_="")])
        final = _reply(text=CONTINUATION_TOKEN)
        result = validate_l1_continuation(first, final, "test-model")
        assert result["passed"] is False
        assert "tool_call_ids" in result["failure_codes"]

    def test_model_mismatch_fails(self):
        first = _reply(tool_calls=[_tool_call()], model="model-a")
        final = _reply(text=CONTINUATION_TOKEN, model="model-b")
        result = validate_l1_continuation(first, final, "model-a")
        assert result["passed"] is False
        assert "returned_model_mismatch" in result["failure_codes"]

    def test_reasoning_returned_informational(self):
        first = _reply(tool_calls=[_tool_call()], reasoning_content="deep thought")
        final = _reply(text=CONTINUATION_TOKEN)
        result = validate_l1_continuation(first, final, "test-model")
        assert result["passed"] is True
        assert result["reasoning_content_returned"] is True
        assert result["reasoning_replayed"] is True

    def test_reasoning_not_returned(self):
        first = _reply(tool_calls=[_tool_call()])
        final = _reply(text=CONTINUATION_TOKEN)
        result = validate_l1_continuation(first, final, "test-model")
        assert result["passed"] is True
        assert result["reasoning_content_returned"] is False
        assert result["reasoning_replayed"] is False


class TestContinuationMessages:
    def test_builds_correct_sequence(self):
        prompt = [{"role": "user", "content": "hello"}]
        first = _reply(text="ok", tool_calls=[_tool_call(id_="abc")])
        msgs = continuation_messages(prompt, first)
        assert len(msgs) == 3
        assert msgs[0] == prompt[0]
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["tool_calls"][0]["id"] == "abc"
        assert msgs[2]["role"] == "tool"
        assert msgs[2]["tool_call_id"] == "abc"
        import json
        content = json.loads(msgs[2]["content"])
        assert content == {"ok": True, "token": CONTINUATION_TOKEN}

    def test_reasoning_content_replayed(self):
        prompt = [{"role": "user", "content": "hello"}]
        first = _reply(text="ok", tool_calls=[_tool_call(id_="abc")], reasoning_content="thinking...")
        msgs = continuation_messages(prompt, first)
        assert msgs[1].get("reasoning_content") == "thinking..."
