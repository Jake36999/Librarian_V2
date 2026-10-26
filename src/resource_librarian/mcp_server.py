"""The MCP server: the registry's tools, run by the vault's active Core.

Every registered tool the connection's tier grants is listed with the
registry's own schema, description and effect hints. Every call goes to the
vault's running Librarian Core over its authenticated MCP endpoint (CORE-04A),
where `Registry.call` applies the tier check, argument coercion, the session's
phase gate and budget, and the envelope - through the same writer, index
service, document leases and permission broker as every other Core call.

**This process holds no vault state.** It never opens the vault, its SQLite
index, its writer or its session logs: a second writer beside the Core is the
two-writer race the vault lease exists to prevent, and it would bypass the
Obsidian dirty-note protection. With no live Core for the vault, every call is
refused with `CORE_REQUIRED` and nothing is written.

**One research thread per connection.** A connection starts with no session.
`open_session` and `resume_session` attach one; every later call on the
connection runs inside it, so its writes are phase-gated and its results carry
the envelope. `close_session` detaches it. A client never passes a session id
by hand, which is how V1's Reader tools came to be called outside any thread.

**The tier is fixed at launch, and an agent's.** A Reader (an agent working
from another project) connects at `consult`; the Cowork plugin, where Claude is
the Librarian, launches at `contribute`. `curate` is a person's own authority:
an MCP connection is capped at `contribute`, here and again in the Core. Tools
above the tier are not listed, and are refused by name if called anyway.

**The clerk is the Core's.** Clerk and routing tasks use the Core's configured
clerk; with none they wait in the clerk queue, which this connection's model can
answer with `clerk_next` and `clerk_submit`. (Answering them through MCP
sampling would need the Core to call back into this process; that route is not
offered while calls run in the Core.)

**Approvals** are both the host's and the Core's: a Cowork or Claude Code client
asks its person before a tool whose hints say it writes, and the Core's Modes
setting (Plan, Ask or Auto) applies as it does to every agent - in Ask, a write
waits for a person in the Librarian window. The registry's tiers, the phase gate
and the vault's own rules (`PERSON_CONFIRMS`, `SENSITIVITY_REVIEW`) hold either way.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import anyio
import anyio.to_thread
import mcp_types as types
from mcp_types.version import MODERN_PROTOCOL_VERSIONS
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from . import __version__, connection, process_identity
from . import tools  # noqa: F401  (registers the tools)
from .registry import REGISTRY, TIERS, ToolSpec
from .rules import Refusal

# Which part of the surface a tool belongs to, by the module that declares it.
GROUPS = {"core": "read", "library": "search", "sessions": "session", "staging": "write",
          "intake": "intake", "scout": "intake", "workflows": "workflows", "vault": "write"}

#: The highest tier an MCP connection holds; the Core enforces the same cap.
MCP_TIER_CEILING = "contribute"
#: The Core's permission broker may wait up to 600 s for a person in Ask mode.
CALL_TIMEOUT = 660.0

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


def _core_required(detail: str) -> dict[str, Any]:
    return {"error": "refused", **Refusal("CORE_REQUIRED", detail).to_dict()}


def call_core(root: Path | None, payload: dict[str, Any], *,
              timeout: float = CALL_TIMEOUT) -> dict[str, Any]:
    """Run one tool call in the vault's active Core, or refuse.

    The Core is found through its owner-only connection record and checked
    with the same process identity the Host uses. A missing, stopped,
    unreachable or non-loopback Core is a `CORE_REQUIRED` refusal - never a
    reason to open the vault here instead.
    """
    if root is None:
        return _core_required("no vault: launch with --vault, set LIBRARIAN_VAULT, or start "
                              "from inside a vault")
    record = connection.load(root)
    if record is None:
        return _core_required(f"no Librarian Core is running for {root}")
    if not process_identity.is_alive(int(record.get("pid") or 0), record.get("process_start")):
        return _core_required(f"the Core recorded for {root} is no longer running")
    url = str(record.get("url") or "").rstrip("/")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "::1", "localhost"):
        return _core_required("the recorded Core is not on a loopback address; refusing to connect")
    request = urllib.request.Request(
        url + "/api/mcp/call", data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json",
                 "X-Librarian-Token": str(record.get("token") or ""), "Origin": url})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            body = {}
        detail = str((body or {}).get("error") or exc)[:300]
        if exc.code in (403, 503):
            return _core_required(f"the Core did not accept this call ({exc.code}): {detail}")
        return {"error": "failed", "detail": f"the Core answered {exc.code}: {detail}"}
    except (OSError, ValueError) as exc:
        return _core_required(f"the recorded Core could not be reached ({str(exc)[:200]}); "
                              f"no direct vault access was attempted")
    if not isinstance(data, dict) or not isinstance(data.get("result"), dict):
        return {"error": "failed", "detail": "the Core returned an unexpected reply"}
    return data


class LibrarianServer:
    """The registry's tools for one MCP client process; their calls, the Core's."""

    def __init__(self, vault: Any, tier: str = "consult", *, timeout: float = CALL_TIMEOUT):
        if tier not in TIERS:
            raise ValueError(f"tier is one of {TIERS}")
        if TIERS.index(tier) > TIERS.index(MCP_TIER_CEILING):
            print(f"resource-librarian mcp: tier {tier!r} is a person's; this connection is "
                  f"{MCP_TIER_CEILING!r}", file=sys.stderr)
            tier = MCP_TIER_CEILING
        # A Vault or a path: only the vault's root is kept.  (A Path has its own
        # `.root` - the drive - so unwrap only a non-path object.)
        root = vault if vault is None or isinstance(vault, (str, Path)) else vault.root
        self.root = Path(root).resolve() if root else None
        self.tier = tier
        self.timeout = timeout
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
        connection_ = getattr(getattr(request, "session", None), "_connection", None)
        state = getattr(connection_, "state", None)
        if isinstance(state, dict) and \
                getattr(connection_, "protocol_version", "") not in MODERN_PROTOCOL_VERSIONS:
            return state
        key = str(getattr(connection_, "session_id", "") or "")
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
        result = await anyio.to_thread.run_sync(
            self.call, params.name, dict(params.arguments or {}), state)
        return as_result(result)

    def call(self, name: str, arguments: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        """One call on one connection, run in the Core: the session it carries
        goes in, and the session the call opened, resumed or closed comes out."""
        outcome = call_core(self.root, {"tool": name, "arguments": arguments,
                                        "session": state.get("session") or "", "tier": self.tier},
                            timeout=self.timeout)
        if "result" not in outcome:
            return outcome
        result = outcome["result"]
        if "error" not in result:
            if name == "close_session" and result.get("closed"):
                state.pop("session", None)
            elif outcome.get("session"):
                state["session"] = outcome["session"]
        return result

    # -- running -------------------------------------------------------------
    async def run_stdio(self) -> None:
        async with stdio_server() as (read, write):
            await self.server.run(read, write, self.server.create_initialization_options())


def serve(vault_path: str | None, tier: str = "consult") -> int:
    """`--vault`, else `LIBRARIAN_VAULT`, else the vault holding the working
    directory (the plugin launches without a path; the host sets one of these).
    Only the vault's root is kept, to find its Core."""
    import os
    from .vault import Vault
    try:
        root: Path | None = Vault.find(vault_path or os.environ.get("LIBRARIAN_VAULT") or None).root
    except Refusal as refusal:
        # Loud, on stderr (stdout is the protocol): every call will refuse
        # with CORE_REQUIRED, and the tool list still answers.
        print(f"resource-librarian mcp: no vault ({refusal}); serving without one",
              file=sys.stderr)
        root = None
    anyio.run(LibrarianServer(root, tier).run_stdio)
    return 0
