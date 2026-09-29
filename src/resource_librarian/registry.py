"""One tool registry; the CLI, the MCP server and the chat are generated from it.

V1 kept three hand-written lists of what an agent could do (the MCP `TOOLS`
table, the CLI's argument parser, the chat's schemas) and they drifted: the
2026-09-12 research pass walked around the MCP surface because the CLI could
reach things it could not. Here a tool is declared once, with its parameters,
effect, tier and card, and every surface is built from that declaration. A tool
added later reaches every surface without anybody remembering to add it.

The boundary is also here, once:

- **Closed registry.** An unregistered name is refused (`CLOSED_ACTION_REGISTRY`).
- **Tiers.** A tool outside the caller's tier is refused by name (`TIER_REFUSED`).
- **Bounds.** Arguments are coerced to their declared types and clamped to
  declared limits, and every adjustment is reported back. Silently accepting
  `limit="ten"` would be the small dishonesty `FAILURE_MUST_BE_LOUD` forbids.
- **No tracebacks.** A tool that raises returns a structured error; a
  `Refusal` returns its rule.
"""
from __future__ import annotations

import inspect
import types
import typing
from dataclasses import dataclass, field
from typing import Any, Callable

from .rules import Refusal

TIERS = ("consult", "contribute", "curate")
EFFECTS = ("read", "write", "vault_write")

MAX_TEXT = 20_000
MAX_ECHO = 160
MAX_LIMIT = 50
MAX_ITEMS = 100
MAX_ITEM_TEXT = 2_000


@dataclass(frozen=True)
class Card:
    """What a tool is for, in a few dozen tokens: enough to choose by."""
    purpose: str
    use_when: str = ""
    note: str = ""


@dataclass
class Context:
    """What a call runs with. Surfaces build one; tools read what they need."""
    tier: str = "consult"
    vault: Any = None                 # a `vault.Vault`, when the tool needs one
    session: Any = None               # filled in by the session harness (M3)
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    fn: Callable[..., Any]
    tier: str
    effect: str
    card: Card
    open_world: bool = False
    needs_vault: bool = True
    idempotent: bool = True
    # Top-level fields the result always carries, when declared. Workflow
    # validation checks bindings against them; empty means "not declared".
    returns: tuple[str, ...] = ()
    # Runs outside any session, with no envelope: the clerk's tools, whose
    # caller must see the task and nothing of the research thread.
    sessionless: bool = False
    # An MCP server's own tool, registered dynamically (Registry.register),
    # never through the `@tool` decorator: offered to the lead model only,
    # never to clerk/scribe, and always seeded "ask" in the broker regardless
    # of mode (the loop wraps its result untrusted; it gets no vault access).
    external: bool = False
    # An external tool's shape is the server's own JSON Schema, not something
    # to read off `fn` (a generic bridge, not a typed Python function) -
    # `json_schema()` and `coerce()` use this directly when it is set.
    schema: dict[str, Any] | None = None

    # -- parameters, read from the function itself ---------------------------
    def parameters(self) -> list[inspect.Parameter]:
        return [p for p in inspect.signature(self.fn).parameters.values()
                if p.name != "ctx"]

    def hints(self) -> dict[str, Any]:
        return typing.get_type_hints(self.fn)

    def json_schema(self) -> dict[str, Any]:
        if self.schema is not None:
            return self.schema
        hints = self.hints()
        properties: dict[str, Any] = {}
        required: list[str] = []
        for p in self.parameters():
            properties[p.name] = _json_type(hints.get(p.name, str))
            if p.default is inspect.Parameter.empty:
                required.append(p.name)
            else:
                properties[p.name]["default"] = p.default
        return {"type": "object", "properties": properties, "required": required,
                "additionalProperties": False}

    def description(self) -> str:
        parts = [self.card.purpose.rstrip(".") + "."]
        if self.card.use_when:
            parts.append(f"Use when {self.card.use_when.rstrip('.')}.")
        if self.card.note:
            parts.append(self.card.note.rstrip(".") + ".")
        doc = inspect.getdoc(self.fn) or ""
        if doc:
            parts.append(doc.split("\n\n")[0].replace("\n", " "))
        return " ".join(parts)

    def annotations(self) -> dict[str, bool]:
        """MCP's own vocabulary, so a client can reason about effect. Hints only:
        enforcement is `Registry.call`, never these flags."""
        return {"readOnlyHint": self.effect == "read",
                "destructiveHint": False,
                "idempotentHint": self.idempotent,
                "openWorldHint": self.open_world}


def _json_type(hint: Any) -> dict[str, Any]:
    origin = typing.get_origin(hint)
    args = [a for a in typing.get_args(hint) if a is not type(None)]
    if origin in (typing.Union, types.UnionType) and len(args) == 1:
        return _json_type(args[0])
    if origin is typing.Literal:
        return {"type": "string", "enum": list(typing.get_args(hint))}
    if origin in (list, tuple) or hint in (list, tuple):
        item = _json_type(args[0]) if args else {"type": "string"}
        return {"type": "array", "items": item}
    if origin is dict or hint is dict:
        return {"type": "object"}
    if hint is bool:
        return {"type": "boolean"}
    if hint is int:
        return {"type": "integer"}
    if hint is float:
        return {"type": "number"}
    return {"type": "string"}


def clip(value: Any, limit: int = MAX_ECHO) -> str:
    """Quote a caller's input back without letting it size the reply."""
    text = str(value)
    return text if len(text) <= limit else f"{text[:limit]}... [{len(text)} chars]"


class Registry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        # (before, after), installed by the session harness. Called for every
        # call made inside a session, so no surface can skip the phase gate.
        self.session_hooks: tuple[Callable, Callable] | None = None

    # -- declaration ---------------------------------------------------------
    def tool(self, name: str, *, tier: str, effect: str, card: Card,
             open_world: bool = False, needs_vault: bool = True,
             idempotent: bool | None = None, returns: tuple[str, ...] = (),
             sessionless: bool = False) -> Callable:
        if tier not in TIERS:
            raise ValueError(f"tier {tier!r} not in {TIERS}")
        if effect not in EFFECTS:
            raise ValueError(f"effect {effect!r} not in {EFFECTS}")

        def register(fn: Callable[..., Any]) -> Callable[..., Any]:
            if name in self._tools:
                raise ValueError(f"tool {name!r} registered twice")
            params = inspect.signature(fn).parameters
            if "ctx" not in params:
                raise TypeError(f"{fn.__name__} must take `ctx` as its first parameter")
            self._tools[name] = ToolSpec(
                name=name, fn=fn, tier=tier, effect=effect, card=card,
                open_world=open_world, needs_vault=needs_vault,
                idempotent=(effect == "read") if idempotent is None else idempotent,
                returns=tuple(returns), sessionless=sessionless)
            return fn
        return register

    # -- dynamic registration (MCP servers only) ------------------------------
    # The closed registry above is for the vault's own tools, declared once at
    # import time and never removed. An MCP server's tools come and go with the
    # server's own lifecycle (accepted, enabled, disconnected), so they go
    # through here instead - never through `tool()`, and never allowed to
    # shadow a vault tool's name.
    def register(self, spec: ToolSpec) -> None:
        if not spec.external:
            raise ValueError("Registry.register is for external (MCP) tools only; "
                             "a vault tool is declared with @tool at import time")
        existing = self._tools.get(spec.name)
        if existing is not None and not existing.external:
            raise ValueError(f"{spec.name!r} is already a vault tool; an external tool "
                             f"cannot reuse its name")
        self._tools[spec.name] = spec

    def unregister(self, name: str) -> None:
        existing = self._tools.get(name)
        if existing is not None and existing.external:
            del self._tools[name]

    def external_names(self) -> list[str]:
        return sorted(n for n, s in self._tools.items() if s.external)

    # -- lookup --------------------------------------------------------------
    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def get(self, name: str) -> ToolSpec:
        return self._tools[name]

    def names(self) -> list[str]:
        return sorted(self._tools)

    def for_tier(self, tier: str) -> list[ToolSpec]:
        rank = TIERS.index(tier)
        return [t for t in self._tools.values() if TIERS.index(t.tier) <= rank]

    # -- the boundary --------------------------------------------------------
    def check(self, name: str, tier: str) -> ToolSpec:
        if name not in self._tools:
            raise Refusal("CLOSED_ACTION_REGISTRY",
                          f"{clip(name, 80)!r} is not a registered tool. Registered: "
                          f"{', '.join(self.names())}. Report the gap rather than "
                          f"working around it.")
        spec = self._tools[name]
        if tier not in TIERS:
            raise Refusal("TIER_REFUSED", f"unknown tier {clip(tier, 40)!r}; tiers are {TIERS}")
        if TIERS.index(spec.tier) > TIERS.index(tier):
            raise Refusal("TIER_REFUSED",
                          f"{name!r} is granted at {spec.tier!r}; this caller is at "
                          f"{tier!r}.")
        return spec

    def call(self, name: str, arguments: dict[str, Any] | None,
             ctx: Context) -> dict[str, Any]:
        """Every surface calls tools through here, and nowhere else."""
        hooks = self.session_hooks if ctx.session and ctx.vault is not None else None
        if hooks and name in self._tools and self._tools[name].sessionless:
            hooks = None
        adjusted: list[str] = []
        try:
            spec = self.check(name, ctx.tier)
            if spec.needs_vault and ctx.vault is None:
                raise Refusal("VAULT_REQUIRED", f"{name!r} needs a vault")
            kwargs, adjusted = coerce(spec, arguments or {})
            if hooks:
                hooks[0](name, spec.effect, ctx)
            broker = ctx.extras.get("broker")
            if broker is not None:
                # The surface's permission mode, decided as the action runs;
                # after the phase gate, so nobody is asked about a refused write.
                broker.check(spec, kwargs, ctx)
            result = spec.fn(ctx, **kwargs)
        except Refusal as refusal:
            result = {"error": "refused", **refusal.to_dict()}
        except TypeError as exc:
            result = {"error": "invalid_arguments", "tool": name, "detail": clip(exc, 400)}
        except Exception as exc:                            # noqa: BLE001
            result = {"error": "failed", "tool": name,
                      "detail": f"{type(exc).__name__}: {clip(exc, 400)}"}
        if not isinstance(result, dict):
            result = {"result": result}
        if adjusted:
            result = {**result, "adjusted_arguments": adjusted}
        if hooks and name in self._tools and ctx.session:
            try:
                result = hooks[1](name, arguments or {}, result, ctx, self._tools[name].effect)
            except Refusal as refusal:
                result = {**result, "session_error": refusal.to_dict()}
        return result


def coerce(spec: ToolSpec, arguments: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Bring arguments to their declared types and inside the declared bounds.

    Unknown argument names are refused rather than dropped: a caller that
    misspells a constraint should hear about it, not get an unconstrained
    answer that looks constrained. Reads `spec.json_schema()` throughout, so
    an external tool (whose schema comes from the server, not from `fn`'s own
    type hints) is coerced exactly the same way a vault tool is.
    """
    schema_obj = spec.json_schema()
    properties = schema_obj.get("properties", {})
    unknown = sorted(set(arguments) - set(properties))
    if unknown:
        raise TypeError(f"unknown argument(s) {unknown}; accepted: {sorted(properties)}")
    # A normal tool's own function raises on a missing required argument, so
    # this was previously enforced only by accident; an external tool's `fn`
    # is a generic `**kwargs` bridge that would accept anything silently.
    missing = sorted(k for k in schema_obj.get("required", []) if k not in arguments)
    if missing:
        raise TypeError(f"missing required argument(s) {missing}")
    out: dict[str, Any] = {}
    changed: list[str] = []
    for key, value in arguments.items():
        schema = properties[key]
        kind = schema.get("type")
        if kind == "boolean":
            if isinstance(value, str):
                out[key] = value.strip().lower() in ("true", "yes", "1", "on")
                changed.append(f"{key} was text, read as a flag")
            else:
                out[key] = bool(value)
        elif kind == "integer":
            try:
                number = int(value)
            except (TypeError, ValueError):
                number = MAX_LIMIT if key == "limit" else 0
                changed.append(f"{key} was not a number")
            if key == "limit" or key.endswith("_limit"):
                bounded = max(1, min(MAX_LIMIT, number))
                if bounded != number:
                    changed.append(f"{key} {number} clamped to {bounded}")
                number = bounded
            out[key] = number
        elif kind == "number":
            try:
                out[key] = float(value)
            except (TypeError, ValueError):
                out[key] = 0.0
                changed.append(f"{key} was not a number")
        elif kind == "array":
            if isinstance(value, list):
                items = value
            elif value is None:
                items = []
            elif isinstance(value, str):
                items = [value]
                changed.append(f"{key} was text, read as a one-item list")
            else:
                items = []
                changed.append(f"{key} was not a list")
            if len(items) > MAX_ITEMS:
                changed.append(f"{key} truncated from {len(items)} items")
                items = items[:MAX_ITEMS]
            out[key] = [m[:MAX_ITEM_TEXT] if isinstance(m, str) else m for m in items]
        elif kind == "object":
            out[key] = value if isinstance(value, dict) else {}
            if value is not None and not isinstance(value, dict):
                changed.append(f"{key} was not an object")
        else:
            text = "" if value is None else str(value)
            if not isinstance(value, str) and value is not None:
                changed.append(f"{key} was {type(value).__name__}, read as text")
            if len(text) > MAX_TEXT:
                changed.append(f"{key} truncated from {len(text)} characters")
                text = text[:MAX_TEXT]
            text = "".join(c for c in text if c >= " " or c in "\n\t")
            if "enum" in schema and text not in schema["enum"]:
                raise TypeError(f"{key}={clip(text, 60)!r} is not one of {schema['enum']}")
            out[key] = text
    return out, changed


REGISTRY = Registry()
tool = REGISTRY.tool
