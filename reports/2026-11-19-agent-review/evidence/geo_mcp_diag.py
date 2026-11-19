"""Interactive stdio probe of geo-grapher serve-graphs (keeps stdin open for response)."""
from __future__ import annotations

import json
import subprocess
import sys

def probe(catalog: str) -> None:
    cmd = [
        r"G:\Libraries\_geo-runtime\env\Scripts\python.exe",
        "-m", "geographer", "serve-graphs",
        "--catalog", catalog,
        "--transport", "stdio", "--tools", "all",
    ]
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8",
    )
    assert proc.stdin and proc.stdout
    try:
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "p", "version": "1"}
            }},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "list_graphs", "arguments": {}}},
        ]
        for m in msgs:
            proc.stdin.write(json.dumps(m) + "\n")
            proc.stdin.flush()
            if "id" in m:
                line = proc.stdout.readline()
                print(f"REQ id={m['id']} ({m['method']}) -> len={len(line)}")
                if line:
                    obj = json.loads(line)
                    res = obj.get("result") or {}
                    print("  keys:", sorted(obj.keys()), "res_keys:", sorted(res.keys()) if isinstance(res, dict) else type(res))
                    if m["id"] == 3:
                        print("  content:", json.dumps(res.get("content"))[:400])
                        print("  structuredContent:", json.dumps(res.get("structuredContent"))[:400])
                        print("  full_preview:", line[:500])
                    elif m["id"] == 2:
                        tools = res.get("tools") or []
                        print("  tool_count:", len(tools), "sample:", [t.get("name") for t in tools[:10]])
    finally:
        proc.kill()
        proc.wait(timeout=5)


if __name__ == "__main__":
    print("=== Resource-Library catalog ===")
    probe(r"G:\Libraries\Resource-Library\.librarian\geographer\catalog.sqlite")
    print("=== Geo_Grapher named-graphs catalog ===")
    probe(r"F:\uv-data\Geo_Grapher\output\named-graphs\catalog.sqlite")
