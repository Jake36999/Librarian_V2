"""ADAPT-04: OpenAI-compatible rendering and parsing live in a trusted adapter.

The golden files under tests/fixtures/openai_chat were captured from
`OpenAICompatible.chat` before the extraction; the adapter must reproduce
the same request bytes and the same normalised replies for every case.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from resource_librarian import providers
from resource_librarian.providers import OpenAICompatible, OutputBudgetError, ToolDef

GOLDEN = Path(__file__).parent / "fixtures" / "openai_chat"

TOOLS = [ToolDef("lookup", "Find a note", {"type": "object",
                                            "properties": {"q": {"type": "string"}}})]
HISTORY = [
    {"role": "user", "content": "find osquery"},
    {"role": "assistant", "content": "", "reasoning_content": "think",
     "tool_calls": [{"id": "c1", "name": "lookup", "arguments": {"q": "osquery"}}]},
    {"role": "tool", "tool_call_id": "c1", "content": "found"},
    {"role": "assistant", "content": "Here it is."},
    {"role": "user", "content": None},
]

REQUESTS = {
    "plain": dict(system="Be brief.", messages=[{"role": "user", "content": "hi"}], tools=[]),
    "no_system": dict(system="", messages=[{"role": "user", "content": "hi"}], tools=[],
                      max_tokens=12),
    "tools_history_temperature": dict(system="S", messages=HISTORY, tools=TOOLS,
                                      max_tokens=99, temperature=0.2),
}

REPLIES = {
    "text": {"model": "m-1", "choices": [{"message": {"content": "hello"},
                                          "finish_reason": "stop"}],
             "usage": {"prompt_tokens": 3, "completion_tokens": 1, "junk": "x"}},
    "tool_calls": {"model": "m-1", "choices": [{"finish_reason": "tool_calls", "message": {
        "content": None, "reasoning_content": "because",
        "tool_calls": [{"id": "t1", "function": {"name": "lookup", "arguments": "{\"q\": 1}"}},
                       {"id": "t2", "function": {"name": "lookup", "arguments": "not json"}},
                       {"id": "t3", "function": {"name": "lookup", "arguments": "[1]"}}]}}]},
    "no_identity": {"choices": [{"message": {"content": "x"}, "finish_reason": "stop"}]},
    "empty": {},
}


def _provider(monkeypatch, reply):
    sent = []

    def fake(method, url, headers, body=None, timeout=120):
        sent.append((method, url, body))
        return reply
    monkeypatch.setattr(providers, "_request", fake)
    return OpenAICompatible("https://example.test/v1", model="m-1", name="test"), sent


def _normalised(reply):
    out = asdict(reply)
    out["tool_calls"] = [{**c, "id": c["id"] if not c["id"].startswith("call_") else "call_*"}
                         for c in out["tool_calls"]]
    return out


@pytest.mark.parametrize("case", sorted(REQUESTS))
def test_request_bodies_are_byte_identical(monkeypatch, case):
    provider, sent = _provider(monkeypatch, REPLIES["text"])
    provider.chat(**REQUESTS[case])
    method, url, body = sent[0]
    assert (method, url) == ("POST", "https://example.test/v1/chat/completions")
    wanted = (GOLDEN / f"request_{case}.json").read_text(encoding="utf-8")
    assert json.dumps(body, ensure_ascii=False, indent=1) + "\n" == wanted


@pytest.mark.parametrize("case", sorted(REPLIES))
def test_replies_normalise_identically(monkeypatch, case):
    provider, _ = _provider(monkeypatch, REPLIES[case])
    reply = provider.chat(**REQUESTS["plain"])
    wanted = json.loads((GOLDEN / f"reply_{case}.json").read_text(encoding="utf-8"))
    assert _normalised(reply) == wanted


def test_empty_content_at_length_is_an_output_budget_failure(monkeypatch):
    provider, _ = _provider(monkeypatch, {"model": "m-1", "choices": [
        {"message": {"content": ""}, "finish_reason": "length"}]})
    with pytest.raises(OutputBudgetError):
        provider.chat(**REQUESTS["plain"])


def test_rendering_and_parsing_are_the_adapters_not_the_transports():
    from resource_librarian.adapters.openai_chat import OpenAIChatAdapter
    body = OpenAIChatAdapter.render("m-1", **REQUESTS["plain"])
    assert body["messages"][0] == {"role": "system", "content": "Be brief."}
    assert OpenAIChatAdapter.parse(REPLIES["text"]).text == "hello"
