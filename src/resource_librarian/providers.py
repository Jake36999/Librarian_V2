"""The provider layer: two protocols behind one interface.

The standalone agent loop talks to a model through a `Provider`: a list of
messages and a list of tools in, a `Reply` (text and tool calls) out. Two
protocols cover every provider V2 supports:

- **OpenAI-compatible** `/chat/completions`: OpenAI, DeepInfra, and a local
  server (LM Studio or any compatible URL, no key needed);
- **Anthropic's Messages API**.

Messages are kept in one neutral shape and translated at the edge, so the loop
never knows which protocol it is speaking. Keys are read from the environment
of the core process, by name, and never returned: `check()` reports whether a
key is present and what the provider's live model listing says, which is also
where model ids come from (never a hard-coded list). Standard library only.

The neutral message shape:
- `{"role": "user", "content": str}`
- `{"role": "assistant", "content": str, "tool_calls": [{"id", "name", "arguments": dict}]}`
- `{"role": "tool", "tool_call_id": str, "name": str, "content": str}`
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

PRESETS: dict[str, dict[str, str]] = {
    "openai": {"protocol": "openai", "base_url": "https://api.openai.com/v1",
               "key_env": "OPENAI_API_KEY"},
    "deepinfra": {"protocol": "openai", "base_url": "https://api.deepinfra.com/v1/openai",
                  "key_env": "DEEPINFRA_API_KEY"},
    "local": {"protocol": "openai", "base_url": "http://127.0.0.1:1234/v1", "key_env": ""},
    "anthropic": {"protocol": "anthropic", "base_url": "https://api.anthropic.com/v1",
                  "key_env": "ANTHROPIC_API_KEY"},
}
ANTHROPIC_VERSION = "2023-06-01"

# Where a person is sent to see billing directly: confirmed dashboard roots,
# not a guessed sub-page. Local has none - there is no account to bill.
DASHBOARDS: dict[str, str] = {"deepinfra": "https://deepinfra.com/dash",
                             "openai": "https://platform.openai.com/usage",
                             "anthropic": "https://console.anthropic.com/settings/billing"}

# A balance endpoint outside DeepInfra's OpenAI-compatible surface, found by
# reading a community project's code rather than in DeepInfra's own published
# API reference: unofficial, and may change or disappear without notice.
# `usage()` treats it that way - one best-effort read, never load-bearing.
_DEEPINFRA_BALANCE = "https://api.deepinfra.com/payment/checklist?compute_owed=true"


class ProviderError(RuntimeError):
    """The provider could not answer: unreachable, no key, or its own error."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "arguments": self.arguments}


@dataclass
class Reply:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    stop: str = ""

    def message(self) -> dict[str, Any]:
        out: dict[str, Any] = {"role": "assistant", "content": self.text}
        if self.tool_calls:
            out["tool_calls"] = [c.to_dict() for c in self.tool_calls]
        return out


@dataclass(frozen=True)
class ToolDef:
    """A tool as a model is shown it: the registry's name, description and schema."""
    name: str
    description: str
    parameters: dict[str, Any]


class Provider:
    name = "provider"
    model = ""

    def chat(self, system: str, messages: list[dict[str, Any]], tools: list[ToolDef],
             max_tokens: int = 4096, temperature: float | None = None) -> Reply:
        raise NotImplementedError

    def models(self) -> list[str]:
        raise NotImplementedError

    def usage(self) -> dict[str, Any]:
        """Best-effort account usage or credit balance, read live, never
        cached or trusted for anything the vault does. Most providers have
        no such call on their inference API; those raise, and the settings
        page falls back to a link to the provider's own dashboard."""
        raise ProviderError(f"{self.name} has no usage endpoint")

    def check(self) -> dict[str, Any]:
        """For the Connections page: whether a key is saved, and what the
        listing says. Never the key."""
        key_env = getattr(self, "key_env", "")
        out: dict[str, Any] = {"provider": self.name,
                               "key": ("not needed" if not key_env else
                                       "present" if os.environ.get(key_env) else "missing")}
        try:
            listed = self.models()
        except ProviderError as exc:
            return {**out, "ok": False, "error": str(exc)[:300]}
        return {**out, "ok": True, "models": len(listed),
                "status": f"Connected: {len(listed)} models available"}


# ------------------------------------------------------------------- HTTP

# A model call that times out, cannot connect, or is told the model is busy is tried
# again after these pauses before the turn gives up (2026-10-02: one read timeout on
# DeepInfra ended the owner's turn, and the next call answered in under two seconds).
TRANSIENT_RETRIES = (3.0, 10.0)
TRANSIENT_HTTP = (429, 500, 502, 503, 504)   # 500: "Response payload is not completed"


def _request(method: str, url: str, headers: dict[str, str], body: Any = None,
             timeout: float = 120, sleep: Any = None) -> dict[str, Any]:
    import time
    data = json.dumps(body).encode("utf-8") if body is not None else None
    pauses = list(TRANSIENT_RETRIES)
    while True:
        request = urllib.request.Request(url, data=data, method=method,
                                         headers={"Content-Type": "application/json",
                                                  **headers})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            if exc.code in TRANSIENT_HTTP and pauses:
                (sleep or time.sleep)(pauses.pop(0))
                continue
            raise ProviderError(f"HTTP {exc.code} from {url}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            # A refused connection is a server that is not running (a local model): asking
            # again only waits. A timeout or a dropped connection is worth another try.
            reason = getattr(exc, "reason", exc)
            if pauses and isinstance(reason, (TimeoutError, ConnectionResetError,
                                              ConnectionAbortedError)):
                (sleep or time.sleep)(pauses.pop(0))
                continue
            if isinstance(reason, TimeoutError):
                # Reached, but slow (2026-10-02): "not reachable" sent the person to check
                # their key when the model was simply busy.
                raise ProviderError(f"the model did not answer within {int(timeout)} seconds "
                                    f"({len(TRANSIENT_RETRIES) + 1} tries): the provider is slow "
                                    f"or busy right now - try again shortly, or choose another "
                                    f"model") from exc
            raise ProviderError(f"{url} is not reachable: {exc}") from exc


def _key(key_env: str) -> str:
    if not key_env:
        return ""
    key = os.environ.get(key_env, "")
    if not key:
        raise ProviderError(f"{key_env} is not set")
    return key


# ----------------------------------------------------------- OpenAI-compatible

class OpenAICompatible(Provider):
    def __init__(self, base_url: str, model: str = "", key_env: str = "", name: str = "",
                 timeout: float = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.key_env = key_env
        self.name = name or self.base_url
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        key = _key(self.key_env)
        return {"Authorization": f"Bearer {key}"} if key else {}

    def models(self) -> list[str]:
        listing = _request("GET", f"{self.base_url}/models", self._headers(),
                           timeout=self.timeout)
        return sorted(str(m.get("id")) for m in listing.get("data") or [] if m.get("id"))

    def usage(self) -> dict[str, Any]:
        if self.name != "deepinfra":
            raise ProviderError(f"no usage endpoint is known for {self.name}")
        return _request("GET", _DEEPINFRA_BALANCE, self._headers(), timeout=self.timeout)

    @staticmethod
    def wire_messages(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = [{"role": "system", "content": system}] if system else []
        for m in messages:
            if m["role"] == "assistant" and m.get("tool_calls"):
                out.append({"role": "assistant", "content": m.get("content") or None,
                            "tool_calls": [{"id": c["id"], "type": "function",
                                            "function": {"name": c["name"],
                                                         "arguments": json.dumps(c["arguments"])}}
                                           for c in m["tool_calls"]]})
            elif m["role"] == "tool":
                out.append({"role": "tool", "tool_call_id": m["tool_call_id"],
                            "content": m["content"]})
            else:
                out.append({"role": m["role"], "content": m.get("content") or ""})
        return out

    def chat(self, system: str, messages: list[dict[str, Any]], tools: list[ToolDef],
             max_tokens: int = 4096, temperature: float | None = None) -> Reply:
        if not self.model:
            raise ProviderError(f"no model chosen for {self.name}")
        body: dict[str, Any] = {"model": self.model, "max_tokens": max_tokens,
                                "messages": self.wire_messages(system, messages)}
        if temperature is not None:
            body["temperature"] = temperature
        if tools:
            body["tools"] = [{"type": "function", "function": {
                "name": t.name, "description": t.description, "parameters": t.parameters}}
                for t in tools]
        reply = _request("POST", f"{self.base_url}/chat/completions", self._headers(), body,
                         self.timeout)
        choice = (reply.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        calls = []
        for i, call in enumerate(message.get("tool_calls") or []):
            function = call.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {"_unparsed": function.get("arguments")}
            calls.append(ToolCall(str(call.get("id") or f"call_{i}"),
                                  str(function.get("name") or ""),
                                  arguments if isinstance(arguments, dict) else {}))
        return Reply(message.get("content") or "", calls, reply.get("model", self.model),
                     choice.get("finish_reason") or "")


# ------------------------------------------------------------------ Anthropic

class Anthropic(Provider):
    def __init__(self, model: str = "", key_env: str = "ANTHROPIC_API_KEY",
                 base_url: str = PRESETS["anthropic"]["base_url"], name: str = "anthropic",
                 timeout: float = 120):
        self.model = model
        self.key_env = key_env
        self.base_url = base_url.rstrip("/")
        self.name = name
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": _key(self.key_env), "anthropic-version": ANTHROPIC_VERSION}

    def models(self) -> list[str]:
        listing = _request("GET", f"{self.base_url}/models?limit=1000", self._headers(),
                           timeout=self.timeout)
        return sorted(str(m.get("id")) for m in listing.get("data") or [] if m.get("id"))

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

    def chat(self, system: str, messages: list[dict[str, Any]], tools: list[ToolDef],
             max_tokens: int = 4096, temperature: float | None = None) -> Reply:
        if not self.model:
            raise ProviderError("no Anthropic model chosen")
        body: dict[str, Any] = {"model": self.model, "max_tokens": max_tokens,
                                "messages": self.wire_messages(messages)}
        if system:
            body["system"] = system
        if temperature is not None:
            body["temperature"] = temperature
        if tools:
            body["tools"] = [{"name": t.name, "description": t.description,
                              "input_schema": t.parameters} for t in tools]
        reply = _request("POST", f"{self.base_url}/messages", self._headers(), body,
                         self.timeout)
        text, calls = [], []
        for block in reply.get("content") or []:
            if block.get("type") == "text":
                text.append(block.get("text") or "")
            elif block.get("type") == "tool_use":
                calls.append(ToolCall(str(block.get("id")), str(block.get("name")),
                                      block.get("input") or {}))
        return Reply("".join(text), calls, reply.get("model", self.model),
                     reply.get("stop_reason") or "")


# ------------------------------------------------------------------ scripted

class Scripted(Provider):
    """A function standing in for a model: `answer(system, messages, tools)`
    returns a `Reply`. Tests and replays."""

    def __init__(self, answer: Callable[[str, list[dict[str, Any]], list[ToolDef]], Reply],
                 name: str = "scripted"):
        self.answer = answer
        self.name = name
        self.model = name
        self.calls: list[dict[str, Any]] = []

    def chat(self, system: str, messages: list[dict[str, Any]], tools: list[ToolDef],
             max_tokens: int = 4096, temperature: float | None = None) -> Reply:
        self.calls.append({"system": system, "messages": [dict(m) for m in messages],
                           "tools": [t.name for t in tools]})
        return self.answer(system, messages, tools)

    def models(self) -> list[str]:
        return [self.name]


def from_settings(settings: dict[str, Any]) -> Provider | None:
    """`{provider: "deepinfra", model: "..."}`, with any preset value
    overridable (`base_url`, `key_env`)."""
    provider = str(settings.get("provider") or "")
    if not provider:
        return None
    if provider not in PRESETS and not settings.get("base_url"):
        raise ProviderError(f"unknown provider {provider!r}; one of {sorted(PRESETS)}, "
                            f"or give a base_url")
    base = {**PRESETS.get(provider, {"protocol": "openai"}),
            **{k: v for k, v in settings.items() if k in ("base_url", "key_env", "protocol")}}
    model = str(settings.get("model") or "")
    if base["protocol"] == "anthropic":
        return Anthropic(model, base["key_env"], base["base_url"], provider)
    return OpenAICompatible(base["base_url"], model, base["key_env"], provider)
