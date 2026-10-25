"""ADAPT-03: session-local, redacted invocation evidence.

The assertions intentionally inspect the JSONL serialisation rather than only
the runtime's in-memory trace: this is the boundary that must never become a
prompt, provider-body, credential, or hidden-reasoning archive.
"""
from __future__ import annotations

import json

import pytest

from resource_librarian import providers
from resource_librarian.loop import Loop
from resource_librarian.model_invocation import (
    InvocationPayload, InvocationRuntime, InvocationScope, TaskContract,
)
from resource_librarian.providers import Provider, ProviderError, Reply, ToolCall, ToolDef
from resource_librarian.session import (
    SessionStore, bind_model_session_events, model_session_trace_sink,
)


class FailingEvidenceProvider(Provider):
    name = model = "evidence-model"

    def chat(self, system, messages, tools, max_tokens=4096, temperature=None):
        raise ProviderError("API key sk-ADAPT03-NEVER-PERSIST was rejected", category="credentials")

    def models(self):
        return [self.model]


def _events(vault, session_id):
    lines = SessionStore(vault).path(session_id).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _runtime(*, ids=("evidence-plan",)):
    iterator = iter(ids)
    return InvocationRuntime(trace_sink=model_session_trace_sink,
                             id_factory=lambda: next(iterator))


def test_session_trace_persists_only_allowlisted_request_response_evidence(vault):
    store = SessionStore(vault)
    opened = store.new("explore", question="q")
    runtime = _runtime()
    provider = providers.Scripted(
        lambda _system, _messages, _tools: Reply(
            text="RESPONSE-SENTINEL-MUST-NOT-PERSIST",
            model="evidence-model", stop="stop",
            usage={"prompt_tokens": 8, "completion_tokens": 5, "untrusted": 123},
            request_id="req-secret-looking-but-safe",
            reasoning_content="HIDDEN-REASONING-MUST-NOT-PERSIST"),
        name="evidence-model")
    payload = InvocationPayload.from_legacy(
        "SYSTEM-PROMPT-SENTINEL sk-SYSTEM-KEY-MUST-NOT-PERSIST",
        [{"role": "user", "content": "USER-PAYLOAD-SENTINEL /private/vault/path"}],
        [ToolDef("lookup", "TOOL-DESCRIPTION-SENTINEL", {"type": "object"})],
        max_tokens=91)
    scope = InvocationScope(
        role="lead", task=TaskContract("evidence", "research", "single_turn"),
        phase="frame", session_id=opened.id)

    with bind_model_session_events(vault, opened.id):
        reply = runtime.invoke(provider, payload, scope=scope)

    assert reply.text == "RESPONSE-SENTINEL-MUST-NOT-PERSIST"
    events = [event for event in _events(vault, opened.id)
              if event["type"] in {"model_request", "model_response"}]
    assert [event["type"] for event in events] == ["model_request", "model_response"]
    request, response = events
    assert request["plan_id"] == response["plan_id"] == "evidence-plan"
    assert request["config_hash"] == response["config_hash"]
    assert request["route"]["requested_model"] == "evidence-model"
    assert request["adapter"]["abi"] == 1
    assert request["scope"] == {
        "role": "lead", "task_id": "evidence", "task_kind": "research",
        "interaction": "single_turn", "phase": "frame", "output_contract": "text"}
    assert response["elapsed_ms"] >= 0
    assert response["usage"] == {"input_tokens": 8, "output_tokens": 5, "total_tokens": 13}
    assert response["retry"] == {"attempts": "unavailable"}
    assert response["failure"] == {"class": "none", "retryable": False}

    raw = SessionStore(vault).path(opened.id).read_text(encoding="utf-8")
    for forbidden in (
            "SYSTEM-PROMPT-SENTINEL", "sk-SYSTEM-KEY-MUST-NOT-PERSIST",
            "USER-PAYLOAD-SENTINEL", "/private/vault/path",
            "TOOL-DESCRIPTION-SENTINEL", "RESPONSE-SENTINEL-MUST-NOT-PERSIST",
            "HIDDEN-REASONING-MUST-NOT-PERSIST", "req-secret-looking-but-safe", "untrusted"):
        assert forbidden not in raw

    # A new process folds the same durable, non-secret route evidence.
    resumed = store.load(opened.id)
    assert [event["type"] for event in resumed.model_events] == ["model_request", "model_response"]
    assert resumed.to_dict(vault)["model_events"][0]["route"]["requested_model"] == "evidence-model"


def test_failed_call_keeps_typed_failure_class_without_error_text(vault):
    store = SessionStore(vault)
    opened = store.new("explore", question="q")
    runtime = _runtime(ids=("failed-plan",))
    payload = InvocationPayload.from_legacy("SYSTEM-FAILURE-SENTINEL", [], [], max_tokens=19)

    with bind_model_session_events(vault, opened.id), pytest.raises(ProviderError):
        runtime.invoke(FailingEvidenceProvider(), payload,
                       scope=InvocationScope(session_id=opened.id))

    response = next(event for event in _events(vault, opened.id)
                    if event["type"] == "model_response")
    assert response["outcome"] == "failed"
    assert response["failure"] == {"class": "credentials", "retryable": False}
    # A resumed session folds the stored event back without losing its failure
    # class (delegate review, GLM-5.3: it folded to "unknown").
    folded = [e for e in SessionStore(vault).load(opened.id).model_events
              if e["type"] == "model_response"][0]
    assert folded["failure"] == response["failure"]
    assert folded["retry"] == response["retry"] and folded["usage"] == response["usage"]
    raw = SessionStore(vault).path(opened.id).read_text(encoding="utf-8")
    assert "sk-ADAPT03-NEVER-PERSIST" not in raw
    assert "SYSTEM-FAILURE-SENTINEL" not in raw


def test_first_invocation_is_buffered_until_its_open_session_tool(vault):
    replies = iter([
        Reply(text="Opening a thread.", model="loop-evidence-model",
              reasoning_content="HIDDEN-FIRST-THOUGHT",
              tool_calls=[ToolCall("open-1", "open_session", {"purpose": "explore"})]),
        Reply(text="The session is ready.", model="loop-evidence-model",
              usage={"prompt_tokens": 3, "completion_tokens": 2}),
    ])
    provider = providers.Scripted(lambda _system, _messages, _tools: next(replies),
                                  name="loop-evidence-model")
    runtime = _runtime(ids=("opening-plan", "in-session-plan"))
    loop = Loop(vault, provider, extras={"invocation_runtime": runtime},
                working_context="PROMPT-CONTEXT-MUST-NOT-PERSIST", on_event=lambda _event: None)

    turn = loop.send("Please open an exploratory session")

    assert turn.reply == "The session is ready."
    resumed = SessionStore(vault).load(loop.ctx.session)
    assert [event["type"] for event in resumed.model_events] == [
        "model_request", "model_response", "model_request", "model_response"]
    assert {event["plan_id"] for event in resumed.model_events} == {
        "opening-plan", "in-session-plan"}
    raw = SessionStore(vault).path(loop.ctx.session).read_text(encoding="utf-8")
    assert "HIDDEN-FIRST-THOUGHT" not in raw
    assert "PROMPT-CONTEXT-MUST-NOT-PERSIST" not in raw
