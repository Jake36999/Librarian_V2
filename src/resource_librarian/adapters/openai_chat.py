"""Trusted rendering/parsing for OpenAI-compatible chat, separated from transport/auth.

This adapter exists so that the wire format (request body construction and
response parsing) can be tested and evolved independently of the HTTP
transport and authentication logic that lives in the provider layer.
"""

from __future__ import annotations

import json
from typing import Any

from ..providers import (
    OutputBudgetError,
    Reply,
    ToolCall,
    _safe_request_id,
    _safe_usage,
    synthetic_call_id,
)


class OpenAIChatAdapter:
    """Stateless adapter that builds request bodies and parses responses."""

    @staticmethod
    def wire_messages(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = [{"role": "system", "content": system}] if system else []
        for m in messages:
            if m["role"] == "assistant" and m.get("tool_calls"):
                assistant = {"role": "assistant", "content": m.get("content") or None,
                             "tool_calls": [{"id": c["id"], "type": "function",
                                             "function": {"name": c["name"],
                                                          "arguments": json.dumps(c["arguments"])}}
                                            for c in m["tool_calls"]]}
                # ``reasoning_content`` is a provider continuation field, not
                # generic system context. Render it only on the exact
                # assistant tool-call message that produced it.
                if isinstance(m.get("reasoning_content"), str) and m["reasoning_content"]:
                    assistant["reasoning_content"] = m["reasoning_content"]
                out.append(assistant)
            elif m["role"] == "tool":
                out.append({"role": "tool", "tool_call_id": m["tool_call_id"],
                            "content": m["content"]})
            else:
                out.append({"role": m["role"], "content": m.get("content") or ""})
        return out

    @staticmethod
    def render(
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[Any],
        max_tokens: int = 4096,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Build the exact JSON body for a chat completion request.

        Key order is deliberately maintained: model, max_tokens, messages,
        then temperature (if not None), then tools (if any).
        """
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": OpenAIChatAdapter.wire_messages(system, messages),
        }
        if temperature is not None:
            body["temperature"] = temperature
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
        return body

    @staticmethod
    def parse(
        reply: dict[str, Any], request_id_source: Any = None
    ) -> Reply:
        """Parse an OpenAI-compatible chat completion response into a Reply.

        ``request_id_source``, when given, is used to extract the request id
        via ``_safe_request_id``; otherwise the ``reply`` dict itself is used.
        """
        choice = (reply.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        calls: list[ToolCall] = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {"_unparsed": function.get("arguments")}
            calls.append(
                ToolCall(
                    str(call.get("id") or synthetic_call_id()),
                    str(function.get("name") or ""),
                    arguments if isinstance(arguments, dict) else {},
                )
            )
        text = message.get("content") if isinstance(message.get("content"), str) else ""
        # A missing response identity must remain missing.  Substituting the
        # requested model would turn absence into a false match in the
        # invocation runtime's exact-route evidence.
        observed_model = str(reply.get("model") or "")
        stop = str(choice.get("finish_reason") or "")
        usage = _safe_usage(reply.get("usage"))
        request_id = _safe_request_id(
            getattr(request_id_source if request_id_source is not None else reply, "request_id", "")
        )
        if not text and not calls and stop == "length":
            raise OutputBudgetError(
                observed_model=observed_model,
                stop_reason=stop,
                usage=usage,
                request_id=request_id,
            )
        reasoning = message.get("reasoning_content")
        return Reply(
            text,
            calls,
            observed_model,
            stop,
            usage,
            request_id,
            reasoning if calls and isinstance(reasoning, str) else "",
        )
