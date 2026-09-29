"""A tiny stdio MCP server for testing the client (mcp_client.py) against a
real subprocess, not just an in-process one. Two tools:

- `echo(text)`: read-only, returns {"text": text} - used to check a normal
  round trip and the untrusted-wrapping shape.
- `boom()`: raises, to check the client surfaces a tool error rather than
  crashing.

Run: python fake_mcp_server.py
"""
from __future__ import annotations

import anyio
import mcp_types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

TOOLS = [
    types.Tool(name="echo", description="Say it back.",
              input_schema={"type": "object", "properties": {"text": {"type": "string"}},
                            "required": ["text"], "additionalProperties": False},
              annotations=types.ToolAnnotations(read_only_hint=True)),
    types.Tool(name="boom", description="Always fails.",
              input_schema={"type": "object", "properties": {}, "additionalProperties": False}),
]


async def on_list_tools(request, params) -> types.ListToolsResult:
    return types.ListToolsResult(tools=TOOLS)


async def on_call_tool(request, params) -> types.CallToolResult:
    if params.name == "echo":
        text = json_text({"text": (params.arguments or {}).get("text", "")})
        return types.CallToolResult(content=[types.TextContent(type="text", text=text)],
                                    structured_content={"text": (params.arguments or {}).get("text", "")})
    if params.name == "boom":
        return types.CallToolResult(
            content=[types.TextContent(type="text", text="kaput")], is_error=True)
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=f"no such tool {params.name!r}")],
        is_error=True)


def json_text(value: dict) -> str:
    import json
    return json.dumps(value)


async def main() -> None:
    server = Server("fake-mcp", version="0.0.1", on_list_tools=on_list_tools,
                    on_call_tool=on_call_tool)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
