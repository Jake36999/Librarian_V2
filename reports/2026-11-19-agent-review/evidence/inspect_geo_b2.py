"""Summarize geo_mcp_b2_log.json for verification against D:\\Librarian_V2 source."""
from __future__ import annotations
import json
from pathlib import Path

log = json.loads(Path(r"D:\Librarian_V2\reports\2026-11-19-agent-review\evidence\geo_mcp_b2_log.json").read_text(encoding="utf-8"))

def show_search(label: str, entry: dict) -> None:
    print(f"=== {label} (elapsed={entry.get('elapsed_sec')}s) ===")
    sc = entry.get("structuredContent") or {}
    ents = sc.get("entities") or []
    print("keys:", list(sc.keys()), "omitted:", sc.get("search_hits_omitted"), "next_offset:", sc.get("next_offset"))
    for i, e in enumerate(ents[:5]):
        print(f"  [{i}] name={e.get('qualified_name') or e.get('name')} kind={e.get('kind') or e.get('entity_kind')} file={e.get('file_path') or e.get('path')} cite={e.get('cite_as')}")
        print(f"       keys={list(e.keys())}")
        if e.get("snippet") or e.get("doc_gist") or e.get("preview"):
            print(f"       snippet={str(e.get('snippet') or e.get('doc_gist') or e.get('preview'))[:140]}")

def show_contents(label: str, items: list[dict]) -> None:
    print(f"=== {label} CONTENTS ===")
    for item in items:
        sc = (item.get("content") or {}).get("structuredContent") or {}
        print("  cite:", item.get("cite_as"), "elapsed:", (item.get("content") or {}).get("elapsed_sec"))
        res = sc.get("result") or {}
        ents = sc.get("entities") or []
        chunks = sc.get("chunks") or res.get("chunks") or []
        print("  sc keys:", list(sc.keys()), "res type/keys:", list(res.keys()) if isinstance(res, dict) else type(res).__name__, "ents len:", len(ents), "chunks len:", len(chunks))
        if ents:
            e0 = ents[0]
            print("  entity[0] keys:", list(e0.keys()), "source:", e0.get("source"), "qname:", e0.get("qualified_name"))
            c0 = (e0.get("chunks") or chunks or [])[:2]
            for ch in c0:
                print("    chunk source:", ch.get("source"))
                print("    text[:300]:", repr(ch.get("text", "")[:300]))
        elif isinstance(res, dict) and res:
            print("  res snippet:", json.dumps(res)[:400])

show_search("Q1 search", log["q1_search"])
show_contents("Q1", log["q1_contents"])
show_search("Q2 search", log["q2_search"])
show_contents("Q2", log["q2_contents"])

print("=== Q2 DEPS ===")
for d in log.get("q2_deps", []):
    res = d.get("result", {})
    sc = res.get("structuredContent") or {}
    print("  entity:", d["entity_id"], "elapsed:", res.get("elapsed_sec"), "isError:", res.get("isError"), "sc keys:", list(sc.keys()))
    print("  snippet:", json.dumps(sc)[:600])

print("=== Q2 CTX ===")
for c in log.get("q2_ctx", []):
    res = c.get("result", {})
    sc = res.get("structuredContent") or {}
    print("  focus:", c["focus"], "elapsed:", res.get("elapsed_sec"), "isError:", res.get("isError"), "sc keys:", list(sc.keys()))
    print("  snippet:", json.dumps(sc)[:600])

show_search("Q3 search", log["q3_search"])
show_contents("Q3", log["q3_contents"])

for k in ["check_architecture", "federated_search", "list_bridges", "compile_task_packet_prefixed", "compile_task_packet_raw", "probe_content_kind_arg", "probe_direction_arg"]:
    entry = log.get(k, {})
    print(f"=== {k} (elapsed={entry.get('elapsed_sec')}s, isError={entry.get('isError')}, content_len={entry.get('content_len')}) ===")
    print(" ", json.dumps(entry.get("structuredContent") or entry.get("rpc_error"))[:600])
