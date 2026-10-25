"""Mirrors adapters/openai_chat.py: trusted rendering and parsing for the Anthropic Messages API,
leaving transport and authentication in the provider."""
from __future__ import annotations

from typing import Any


from ..providers import OutputBudgetError, Reply, ToolCall, _safe_request_id, _safe_usage, synthetic_call_id


class AnthropicMessagesAdapter:
    @staticmethod
    def wire_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Tool results travel as a user turn of `tool_result` blocks; a run of
        them becomes one turn, as the API requires."""
        out: list[dict[str, Any]] = []
        for m in messages:
            if m["role"] == "tool":
                block = {"type": "tool_result", "tool_use_id": m["tool_call_id"],
                         "content": m["content"]}
                if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list) \
                        and out[-1]["content"] and \
                        out[-1]["content"][-1].get("type") == "tool_result":
                    out[-1]["content"].append(block)
                else:
                    out.append({"role": "user", "content": [block]})
            elif m["role"] == "assistant":
                blocks: list[dict[str, Any]] = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for c in m.get("tool_calls") or []:
                    blocks.append({"type": "tool_use", "id": c["id"], "name": c["name"],
                                   "input": c["arguments"]})
                out.append({"role": "assistant", "content": blocks or ""})
            else:
                out.append({"role": "user", "content": m.get("content") or ""})
        return out

    @staticmethod
    def render(model: str, system: str, messages: list[dict[str, Any]], tools: list[Any],
               max_tokens: int = 4096, temperature: float | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"model": model, "max_tokens": max_tokens,
                                "messages": AnthropicMessagesAdapter.wire_messages(messages)}
        if system:
            body["system"] = system
        if temperature is not None:
            body["temperature"] = temperature
        if tools:
            body["tools"] = [{"name": t.name, "description": t.description,
                              "input_schema": t.parameters} for t in tools]
        return body

    @staticmethod
    def parse(reply: dict[str, Any]) -> Reply:
        text, calls = [], []
        for block in reply.get("content") or []:
            if block.get("type") == "text":
                text.append(block.get("text") or "")
            elif block.get("type") == "tool_use":
                calls.append(ToolCall(str(block.get("id") or synthetic_call_id()),
                                      str(block.get("name")), block.get("input") or {}))
        rendered_text = "".join(text)
        # See OpenAICompatible.chat: model identity is response evidence, not
        # a convenient echo of the model that was requested.
        observed_model = str(reply.get("model") or "")
        stop = str(reply.get("stop_reason") or "")
        usage = _safe_usage(reply.get("usage"))
        request_id = _safe_request_id(reply.get("request_id", ""))
        if not rendered_text and not calls and stop == "max_tokens":
            raise OutputBudgetError(observed_model=observed_model, stop_reason=stop,
                                    usage=usage, request_id=request_id)
        return Reply(rendered_text, calls, observed_model, stop, usage, request_id)
