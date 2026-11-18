"""A tiny Streamable HTTP MCP server standing in for a library's own Geo-Grapher service:
one read-only tool, `echo(text)`, at `/mcp`, refusing any request without the token in
`X-Geo-Token` (as Geo-Grapher's service does).

Run: python fake_mcp_http_server.py PORT   (token from $FAKE_GEO_TOKEN)
"""
from __future__ import annotations

import os
import sys

import uvicorn
from mcp.server import MCPServer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

TOKEN = os.environ["FAKE_GEO_TOKEN"]
server = MCPServer("fake-geo", version="0.0.1")


@server.tool(description="Say it back.")
def echo(text: str) -> dict:
    return {"text": text}


async def guard(request, call_next):
    if request.headers.get("x-geo-token") != TOKEN:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return await call_next(request)


app = server.streamable_http_app()
app.add_middleware(BaseHTTPMiddleware, dispatch=guard)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[1]), log_level="warning")
