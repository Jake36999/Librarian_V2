"""The MCP server, generated from the one tool registry.

Every registered tool the caller's tier grants is listed with the registry's
own schema, description and effect hints, and every call goes through
`Registry.call`: the tier check, argument coercion, the session's phase gate
and budget, and the envelope. Nothing here decides anything a tool, the
session or the vault would not decide the same way from the CLI or the loop.

**One research thread per connection.** A connection starts with no session.
`open_session` and `resume_session` attach one; every later call on the
connection runs inside it, so its writes are phase-gated and its results carry
the envelope. `close_session` detaches it. A client never passes a session id
by hand, which is how V1's Reader tools came to be called outside any thread.

**The tier is fixed at launch.** A Reader (an agent working from another
project) connects at `consult`; the Cowork plugin, where Claude is the
Librarian, launches at `contribute`. Tools above the tier are not listed, and
are refused by name if called anyway.

**The clerk over MCP.** When no clerk endpoint is configured and the client
offers sampling, clerk and routing tasks are sent to the client as sampling
requests carrying only the task's own system prompt and text, with
`includeContext: "none"`: the host's model answers them without the research
conversation. A client that refuses, or offers no sampling, leaves the tasks
queued, never answered by the research model in-line. (Sampling is deprecated
from protocol 2026-07-28; handshake-era clients such as Cowork's still offer
it, and the configured endpoint is the route that does not depend on it.)

**Approvals** are the host's: a Cowork or Claude Code client asks its person
before a tool whose hints say it writes. The permission broker is the
standalone app's Modes menu and is not attached here unless a caller supplies
one; the registry's tiers, the phase gate and the vault's own rules
(`PERSON_CONFIRMS`, `SENSITIVITY_REVIEW`) hold either way.
"""
from __future__ import annotations

import json
import sys
import warnings
from typing import Any

import anyio
import anyio.from_thread
import anyio.to_thread
import mcp_types as types
from mcp_types.version import MODERN_PROTOCOL_VERSIONS
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from . import __version__
from . import tools  # noqa: F401  (registers the tools)
from .clerk import ClerkUnavailable, Endpoint
from .registry import REGISTRY, TIERS, Context, ToolSpec
from .vault import Vault

# Which part of the surface a tool belongs to, by the module that declares it.
GROUPS = {"core": "read", "library": "search", "sessions": "session", "staging": "write",
          "intake": "intake", "scout": "intake", "workflows": "workflows", "vault": "write"}

INSTRUCTIONS = """\
A research library over this vault's Sources, Concepts and Projects.
Start with `open_session` (purpose: explore, add_project or suggest for the vault's own
work at contribute tier; apply when you are working on another project). The session
stays attached to this connection: every later result carries an envelope with the
phase, open items, budget left and the next step. Follow `next`. Writes open only in
their phase; a refusal names its rule, and `rules` explains any rule by code.
Use `search` before reading notes one by one, and `get_note` for a note by name."""


def group(spec: ToolSpec) -> str:
    return GROUPS.get(spec.fn.__module__.rsplit(".", 1)[-1], "read")


def describe_tool(spec: ToolSpec) -> types.Tool:
    hints = spec.annotations()
    return types.Tool(
        name=spec.name,
        description=spec.description(),
        input_schema=spec.json_schema(),
        annotations=types.ToolAnnotations(
            read_only_hint=hints["readOnlyHint"],
            destructive_hint=hints["destructiveHint"],
            idempotent_hint=hints["idempotentHint"],
            open_world_hint=hints["openWorldHint"]),
        meta={"librarian/group": group(spec), "librarian/tier": spec.tier,
              "librarian/effect": spec.effect})


def as_result(result: dict[str, Any]) -> types.CallToolResult:
    """The registry's dict, both as structured content and as JSON text for
    clients that read only text. A refusal is a tool error the model reads,
    never a protocol error."""
    text = json.dumps(result, ensure_ascii=False, default=str)
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)],
                                structured_content=json.loads(text),
                                is_error="error" in result)


class SamplingClerk(Endpoint):
    """Clerk and routing tasks answered by the client's model through MCP
    sampling, with no conversation context attached. Called from the worker
    thread a tool runs in; the request itself goes out on the event loop."""

    name = "mcp-sampling"
    concurrency = 1

    def __init__(self, session: Any):
        self.session = session
        self.requests: list[dict[str, Any]] = []

    def complete(self, payload: dict[str, Any], repair: str = "") -> tuple[str, str]:
        messages = [types.SamplingMessage(role="user", content=types.TextContent(
            type="text", text=payload["user"]))]
        if repair:
            messages.append(types.SamplingMessage(role="user", content=types.TextContent(
                type="text", text=f"That did not match the required shape: {repair}\n"
                                  f"Return only the JSON object, corrected.")))
        request = {"system_prompt": payload["system"], "include_context": "none",
                   "temperature": payload["temperature"],
                   "max_tokens": int(payload["max_tokens"])}
        self.requests.append({**request, "messages": [m.content.text for m in messages]})
        async def sample() -> Any:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")      # deprecated from 2026-07-28; see above
                return await self.session.create_message(messages, **request)
        try:
            result = anyio.from_thread.run(sample)
        except Exception as exc:                            # noqa: BLE001
            raise ClerkUnavailable(f"the client did not answer a sampling request: "
                                   f"{type(exc).__name__}: {str(exc)[:200]}") from exc
        content = result.content
        text = getattr(content, "text", None)
        if text is None and isinstance(content, list):
            text = "".join(getattr(part, "text", "") for part in content)
        return text or "", result.model or "mcp-sampling"


def offers_sampling(session: Any) -> bool:
    try:
        return bool(session.check_client_capability(
            types.ClientCapabilities(sampling=types.SamplingCapability())))
    except Exception:                                       # noqa: BLE001
        return False


class LibrarianServer:
    """The registry, served. `extras` are passed to every call (tests pass a
    scripted clerk here; the app passes its broker)."""

    def __init__(self, vault: Vault | None, tier: str = "consult",
                 extras: dict[str, Any] | None = None, sampling: bool = True):
        if tier not in TIERS:
            raise ValueError(f"tier is one of {TIERS}")
        self.vault = vault
        self.tier = tier
        self.extras = dict(extras or {})
        self.sampling = sampling
        self._states: dict[str, dict[str, Any]] = {}
        self.server: Server[Any] = Server(
            "resource-librarian", version=__version__,
            title="Librarian", instructions=INSTRUCTIONS,
            on_list_tools=self._list_tools, on_call_tool=self._call_tool)

    # -- per-connection state ------------------------------------------------
    def _state(self, request: Any) -> dict[str, Any]:
        """A handshake-era connection keeps its own state for its lifetime. A
        modern (2026-07-28) request arrives as its own exchange, so its thread
        is kept by the transport's session id: one per stdio process, one per
        HTTP session."""
        connection = getattr(getattr(request, "session", None), "_connection", None)
        state = getattr(connection, "state", None)
        if isinstance(state, dict) and \
                getattr(connection, "protocol_version", "") not in MODERN_PROTOCOL_VERSIONS:
            return state
        key = str(getattr(connection, "session_id", "") or "")
        return self._states.setdefault(key, {})

    # -- handlers ------------------------------------------------------------
    def tools(self) -> list[types.Tool]:
        return [describe_tool(s) for s in sorted(REGISTRY.for_tier(self.tier),
                                                 key=lambda s: s.name)]

    async def _list_tools(self, request: Any, params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(tools=self.tools())

    async def _call_tool(self, request: Any, params: types.CallToolRequestParams
                         ) -> types.CallToolResult:
        state = self._state(request)
        extras = dict(self.extras)
        session = getattr(request, "session", None)
        if self.sampling and session is not None and offers_sampling(session):
            extras.setdefault("clerk_fallback", SamplingClerk(session))
        result = await anyio.to_thread.run_sync(
            self.call, params.name, dict(params.arguments or {}), state, extras)
        return as_result(result)

    def call(self, name: str, arguments: dict[str, Any], state: dict[str, Any],
             extras: dict[str, Any] | None = None) -> dict[str, Any]:
        """One call on one connection: the session it carries goes in, and the
        session the call opened, resumed or closed comes out."""
        ctx = Context(tier=self.tier, vault=self.vault, session=state.get("session") or None,
                      extras=dict(self.extras if extras is None else extras))
        result = REGISTRY.call(name, arguments, ctx)
        if "error" not in result:
            if name == "close_session" and result.get("closed"):
                state.pop("session", None)
            elif ctx.session:
                state["session"] = ctx.session
        return result

    # -- running -------------------------------------------------------------
    async def run_stdio(self) -> None:
        async with stdio_server() as (read, write):
            await self.server.run(read, write, self.server.create_initialization_options())


def serve(vault_path: str | None, tier: str = "consult") -> int:
    """`--vault`, else `LIBRARIAN_VAULT`, else the vault holding the working
    directory (the plugin launches without a path; the host sets one of these)."""
    import os
    from .rules import Refusal
    try:
        vault = Vault.find(vault_path or os.environ.get("LIBRARIAN_VAULT") or None)
    except Refusal as refusal:
        # Loud, on stderr (stdout is the protocol): tools that need a vault
        # will refuse by name, and `doctor` still answers.
        print(f"resource-librarian mcp: no vault ({refusal}); serving without one",
              file=sys.stderr)
        vault = None
    anyio.run(LibrarianServer(vault, tier).run_stdio)
    return 0
