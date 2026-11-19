"""Run B2.2 Geo-Grapher MCP live test over stdio JSON-RPC (read-only on Resource-Library catalog)."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path

PYTHON = r"G:\Libraries\_geo-runtime\env\Scripts\python.exe"
CATALOG = r"G:\Libraries\Resource-Library\.librarian\geographer\catalog.sqlite"
OUT_LOG = Path(r"D:\Librarian_V2\reports\2026-11-19-agent-review\evidence\geo_mcp_b2_log.json")
ERR_LOG = Path(r"D:\Librarian_V2\reports\2026-11-19-agent-review\evidence\geo_mcp_b2_stderr.log")


class StdioMCP:
    def __init__(self, cmd: list[str], err_file) -> None:
        env = {**os.environ, "PYTHONUTF8": "1"}
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=err_file,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=env,
        )
        self._id = 0
        self._q: queue.Queue[str | None] = queue.Queue()
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    def _pump(self) -> None:
        assert self.proc.stdout
        for line in self.proc.stdout:
            self._q.put(line)
        self._q.put(None)

    def request(self, method: str, params: dict | None = None, timeout: float = 120.0) -> dict:
        self._id += 1
        req_id = self._id
        msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            msg["params"] = params
        assert self.proc.stdin
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        while True:
            try:
                line = self._q.get(timeout=timeout)
            except queue.Empty:
                return {"error": {"code": -32000, "message": f"TIMEOUT after {timeout}s on {method}"}}
            if line is None:
                raise RuntimeError(f"MCP EOF on {method}")
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("id") == req_id:
                return obj

    def notify(self, method: str, params: dict | None = None) -> None:
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        assert self.proc.stdin
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def call_tool(self, name: str, arguments: dict, timeout: float = 120.0) -> dict:
        t0 = time.perf_counter()
        print(f"-> calling {name}({arguments})", flush=True)
        resp = self.request("tools/call", {"name": name, "arguments": arguments}, timeout=timeout)
        dt = time.perf_counter() - t0
        ext = extract(resp)
        ext["elapsed_sec"] = round(dt, 3)
        sc = ext.get("structuredContent") or {}
        keys = list(sc.keys()) if isinstance(sc, dict) else type(sc).__name__
        print(f"<- finished {name} in {dt:.2f}s (isError={ext.get('isError')}, keys={keys})", flush=True)
        return ext

    def close(self) -> None:
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
        except OSError:
            pass
        self.proc.terminate()
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def extract(resp: dict) -> dict:
    if "error" in resp:
        return {"rpc_error": resp["error"]}
    res = resp.get("result", {})
    return {
        "isError": res.get("isError", False),
        "content_len": len(res.get("content", [])),
        "content_preview": res.get("content", [])[:1],
        "structuredContent": res.get("structuredContent"),
    }


def payload(ext: dict) -> dict:
    sc = ext.get("structuredContent")
    if not isinstance(sc, dict):
        return {}
    if isinstance(sc.get("data"), dict):
        return sc["data"]
    return sc


def save(log: dict) -> None:
    OUT_LOG.write_text(json.dumps(log, indent=2), encoding="utf-8")


def main() -> None:
    log: dict = {}
    with ERR_LOG.open("w", encoding="utf-8") as ef:
        client = StdioMCP([PYTHON, "-m", "geographer", "serve-graphs", "--catalog", CATALOG, "--transport", "stdio", "--tools", "all"], ef)
        try:
            t0 = time.perf_counter()
            init = client.request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "review-probe", "version": "1.0"},
                },
                timeout=30.0,
            )
            client.notify("notifications/initialized")
            print(f"Initialized in {time.perf_counter()-t0:.2f}s", flush=True)
            log["initialize"] = init.get("result", {})

            tools_resp = client.request("tools/list", timeout=30.0)
            tools = tools_resp.get("result", {}).get("tools", [])
            log["tool_count"] = len(tools)
            log["tools_summary"] = [
                {
                    "name": t["name"],
                    "required": t.get("inputSchema", {}).get("required", []),
                    "properties": sorted(t.get("inputSchema", {}).get("properties", {}).keys()),
                    "description": t.get("description", ""),
                }
                for t in tools
            ]
            save(log)

            # 1. list_graphs
            lg = client.call_tool("list_graphs", {})
            log["list_graphs"] = lg
            save(log)
            graphs = payload(lg).get("graphs", [])
            print(f"Found {len(graphs)} graphs", flush=True)

            code_graph = "Resource-Library-Librarian_V2"
            docs_graph = "Resource-Library-Librarian_V2-docs"

            # Q1: workflow_grant enforcement
            q1_search = client.call_tool("search_entities", {
                "graph_id": code_graph,
                "query": "where is workflow_grant permission checked when a tool runs",
                "also": ["workflow_grant"],
                "limit": 8,
            })
            log["q1_search"] = q1_search
            q1p = payload(q1_search)
            q1_entities = q1p.get("entities", [])
            q1_scope = q1p.get("identity_scope")
            print("Q1 hits:", [(e.get("entity_id"), e.get("cite_as"), e.get("kind")) for e in q1_entities[:6]], flush=True)

            q1_contents = []
            for e in q1_entities[:3]:
                args = {"graph_id": code_graph, "entity_id": e["entity_id"]}
                if q1_scope:
                    args["alias_scope"] = q1_scope
                q1_contents.append({"entity_id": e["entity_id"], "cite_as": e.get("cite_as"), "content": client.call_tool("get_entity_content", args)})
            log["q1_contents"] = q1_contents
            save(log)

            # Q2: GeoService callers & architecture context / find_dependants
            q2_search = client.call_tool("search_entities", {
                "graph_id": code_graph,
                "query": "GeoService start mcp_definition",
                "also": ["GeoService"],
                "limit": 8,
            })
            log["q2_search"] = q2_search
            q2p = payload(q2_search)
            q2_entities = q2p.get("entities", [])
            q2_scope = q2p.get("identity_scope")
            print("Q2 hits:", [(e.get("entity_id"), e.get("cite_as"), e.get("kind")) for e in q2_entities[:6]], flush=True)

            q2_deps = []
            q2_ctx = []
            q2_contents = []
            for e in q2_entities[:3]:
                eid = e["entity_id"]
                d_args = {"graph_id": code_graph, "entity_id": eid, "max_depth": 2}
                if q2_scope:
                    d_args["alias_scope"] = q2_scope
                q2_deps.append({"entity_id": eid, "result": client.call_tool("find_dependants", d_args)})
                c_args = {"graph_id": code_graph, "entity_id": eid}
                if q2_scope:
                    c_args["alias_scope"] = q2_scope
                q2_contents.append({"entity_id": eid, "cite_as": e.get("cite_as"), "content": client.call_tool("get_entity_content", c_args)})
            if q2_entities:
                focus = q2_entities[0]["entity_id"]
                ctx_args = {"graph_id": code_graph, "focus_id": focus, "radius": 1}
                if q2_scope:
                    ctx_args["alias_scope"] = q2_scope
                ctx = client.call_tool("get_architecture_context", ctx_args)
                q2_ctx.append({"focus": focus, "result": ctx})
                sc = payload(ctx)
                vid = sc.get("view_id")
                rels = sc.get("relationships", []) or sc.get("edges", [])
                if vid and rels:
                    rel0 = rels[0]
                    rid = rel0.get("relationship_id") or rel0.get("id")
                    if rid:
                        w_args = {"graph_id": code_graph, "view_id": vid, "relationship_id": rid}
                        if q2_scope:
                            w_args["alias_scope"] = q2_scope
                        log["q2_witness_sample"] = client.call_tool("inspect_relationship_witnesses", w_args)
            log["q2_deps"] = q2_deps
            log["q2_ctx"] = q2_ctx
            log["q2_contents"] = q2_contents
            save(log)

            # Q3: BUNDLES / required_bundle_actions / Session missing
            q3_search = client.call_tool("search_entities", {
                "graph_id": code_graph,
                "query": "how do BUNDLES and required_bundle_actions gate session advance and missing items",
                "also": ["required_bundle_actions"],
                "limit": 8,
            })
            log["q3_search"] = q3_search
            q3p = payload(q3_search)
            q3_entities = q3p.get("entities", [])
            q3_scope = q3p.get("identity_scope")
            print("Q3 hits:", [(e.get("entity_id"), e.get("cite_as"), e.get("kind")) for e in q3_entities[:6]], flush=True)
            q3_contents = []
            for e in q3_entities[:3]:
                args = {"graph_id": code_graph, "entity_id": e["entity_id"]}
                if q3_scope:
                    args["alias_scope"] = q3_scope
                q3_contents.append({"entity_id": e["entity_id"], "cite_as": e.get("cite_as"), "content": client.call_tool("get_entity_content", args)})
            log["q3_contents"] = q3_contents
            save(log)

            # A9 checks
            log["check_architecture"] = client.call_tool("check_architecture", {"graph_id": code_graph})
            log["federated_search"] = client.call_tool("federated_search", {
                "graph_ids": [code_graph, docs_graph],
                "query": "GeoService",
                "mode": "hybrid",
            })
            log["list_bridges"] = client.call_tool("list_bridges", {
                "graph_ids": [code_graph, docs_graph],
            })
            if q2_entities:
                raw_id = q2_entities[0]["entity_id"]
                log["compile_task_packet_prefixed"] = client.call_tool("compile_task_packet", {
                    "graph_id": code_graph,
                    "anchors": [f"entity:{raw_id}"],
                    "instruction": "Trace callers of GeoService",
                })
                log["compile_task_packet_raw"] = client.call_tool("compile_task_packet", {
                    "graph_id": code_graph,
                    "anchors": [raw_id],
                    "instruction": "Trace callers of GeoService",
                })
                log["probe_content_kind_arg"] = client.call_tool("get_entity_content", {
                    "graph_id": code_graph,
                    "entity_id": raw_id,
                    "content_kind": "documentation",
                })
                log["probe_direction_arg"] = client.call_tool("find_dependants", {
                    "graph_id": code_graph,
                    "entity_id": raw_id,
                    "direction": "outgoing",
                })
            save(log)
        finally:
            client.close()

    print(f"Wrote {OUT_LOG} ({OUT_LOG.stat().st_size} bytes)", flush=True)


if __name__ == "__main__":
    main()
