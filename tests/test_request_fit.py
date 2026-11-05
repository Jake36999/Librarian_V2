"""MF-011: every dispatched request fits its route's context window, or the
turn stops before sending.

Exercised through both first-party chat adapters' real HTTP serializers (the
REMED-07 harness), with no external or paid call. The bound is set small so
that 50 and 200 rounds of history must be trimmed to fit.
"""
from __future__ import annotations

import json
import math

import pytest

from resource_librarian.agent_runtime import AgentProfile
from resource_librarian.loop import CONTEXT_MARGIN, CONTEXT_METHOD, Loop
from resource_librarian.providers import Anthropic, OpenAICompatible, Reply, Scripted, set_dispatch_gate

from test_remed07_request_size import (FINAL, FIRST, _audited_history, _CaptureGate,  # noqa: F401
                                       provider_server)

HISTORY_TOKENS = 2_000          # the room left for history once system, tools and reply fit


def _loop(vault, server, protocol):
    base = f"http://127.0.0.1:{server.server_address[1]}/v1"
    provider = (OpenAICompatible(base, model="qualification-model") if protocol == "openai"
                else Anthropic(model="qualification-model", key_env="", base_url=base))
    return Loop(vault, provider, extras={"agent_profile": "lead"}, max_steps=1)


def _fixed(loop) -> int:
    return loop._token_estimate({"system": loop.system_prompt(),
                                 "tools": [t.__dict__ for t in loop.tools()]})


@pytest.mark.parametrize("protocol", ["openai", "anthropic"])
@pytest.mark.parametrize("rounds", [50, 200])
def test_long_histories_are_trimmed_to_fit_and_keep_what_matters(vault, provider_server,
                                                                  protocol, rounds):
    sid, history, last = _audited_history(vault, rounds)
    loop = _loop(vault, provider_server, protocol)
    loop.ctx.session = sid
    loop.restore(history)
    reserve = loop.profile_output_budget
    bound = math.ceil((_fixed(loop) + 200 + reserve + HISTORY_TOKENS) / (1 - CONTEXT_MARGIN))
    loop.context_limit = bound
    gate = _CaptureGate(FIRST, last)
    previous = set_dispatch_gate(gate)
    try:
        turn = loop.send(FINAL)
    finally:
        set_dispatch_gate(previous)

    assert turn.reply == "ok" and not turn.stopped
    sent = gate.rows[0]
    # The guarantee, measured on the wire: the rendered request plus its
    # reply reserve is within the route's window.
    assert math.ceil(sent["sent_bytes"] / 4) + reserve <= bound, (sent["sent_bytes"], bound)
    assert sent["first_retained"] and sent["last_retained"] and sent["final_retained"]
    fit = turn.request
    assert fit["trimmed_rounds"] > 0 and fit["bound"] == bound and fit["bound_source"] == "route"
    assert fit["method"] == CONTEXT_METHOD and fit["reserve"] == reserve
    # Counters only: no prompt text reaches the turn record.
    recorded = json.dumps(fit)
    assert FIRST not in recorded and last not in recorded and FINAL not in recorded


def test_a_tool_call_never_loses_its_result_when_rounds_are_trimmed(vault):
    loop = Loop(vault, Scripted(lambda *_: Reply(text="ok")), max_steps=1)
    view = [{"role": "user", "content": "the original ask"}]
    for n in range(40):
        view += [{"role": "user", "content": f"round {n} " + "u" * 200},
                 {"role": "assistant", "content": "", "tool_calls": [
                     {"id": f"call-{n}", "type": "function",
                      "function": {"name": "search", "arguments": "{}"}}]},
                 {"role": "tool", "tool_call_id": f"call-{n}", "content": "r" * 200},
                 {"role": "assistant", "content": f"answer {n}"}]
    view.append({"role": "user", "content": "the current turn"})
    loop.context_limit = math.ceil((_fixed(loop) + loop.profile_output_budget + 1_500)
                                   / (1 - CONTEXT_MARGIN))
    system, kept, fit = loop._fit_context(loop.system_prompt(), view, loop.tools())
    assert fit["trimmed_rounds"] > 0 and not fit.get("parked")
    assert kept[0]["content"] == "the original ask" and kept[-1]["content"] == "the current turn"
    called = {c["id"] for m in kept for c in m.get("tool_calls") or []}
    answered = {m["tool_call_id"] for m in kept if m.get("role") == "tool"}
    assert called == answered                          # pairs survive whole, or go together
    assert "omitted from this request to fit the model's context window" in system


def test_a_request_that_cannot_fit_stops_the_turn_and_sends_nothing(vault, provider_server):
    loop = _loop(vault, provider_server, "openai")
    loop.context_limit = math.ceil(loop.profile_output_budget / (1 - CONTEXT_MARGIN)) + 10
    gate = _CaptureGate(FIRST, FINAL)
    previous = set_dispatch_gate(gate)
    try:
        turn = loop.send(FINAL)
    finally:
        set_dispatch_gate(previous)
    assert turn.stopped == "context_budget" and not gate.rows
    assert "never cut" in turn.error and turn.request["parked"] is True


def test_a_profile_may_declare_its_routes_context_window():
    AgentProfile("local-lead", "lead", route_policy={"context_tokens": 8192}).validate()
    for bad in (512, "8192", True, 0):
        with pytest.raises(ValueError, match="context_tokens"):
            AgentProfile("local-lead", "lead", route_policy={"context_tokens": bad}).validate()


def test_the_app_takes_a_routes_window_from_its_profile_then_its_catalogue(vault, monkeypatch):
    from resource_librarian.app import App
    from resource_librarian.keys import KeyStore
    app = App(vault, keys=KeyStore(use_keyring=False))
    try:
        declared = AgentProfile("p", "lead", route_policy={"context_tokens": 9000})
        assert app._route_context_limit({"provider": "x", "model": "y"}, declared) == 9000
        monkeypatch.setattr(app, "_route_catalogue_entry", lambda route: {"context_length": 200_000})
        assert app._route_context_limit({"provider": "x", "model": "y"},
                                        AgentProfile("q", "lead")) == 200_000
        monkeypatch.setattr(app, "_route_catalogue_entry", lambda route: {})
        assert app._route_context_limit({"provider": "x", "model": "y"}, AgentProfile("q", "lead")) == 0
    finally:
        app.close_runtime()
