"""Post-restart check for ACCEPT-02 Core, its Geo service, and geo-grapher CLI reachability."""
from __future__ import annotations

import http.cookiejar
import json
import re
import sqlite3
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, r"D:\Librarian_V2\src")
from resource_librarian import connection


def redact(text: str) -> str:
    return re.sub(r"([?&](?:geo_)?token=)[^&\s\"'>]+", r"\1<REDACTED_TOKEN>", text)


def main() -> None:
    vpath = Path(r"C:\Users\jakem\Librarian ACCEPT-02 Vault")
    rec = connection.load(vpath)
    out: dict = {
        "accept02_conn": {"url": rec.get("url"), "pid": rec.get("pid")} if isinstance(rec, dict) else rec
    }
    if isinstance(rec, dict) and rec.get("url") and rec.get("token"):
        for ep in ("/api/meta", "/api/skills", "/api/geographer", "/api/state"):
            req = urllib.request.Request(
                rec["url"].rstrip("/") + ep,
                headers={"X-Librarian-Token": rec["token"]},
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read().decode("utf-8"))
                if ep == "/api/geographer":
                    if data.get("open_url"):
                        cj = http.cookiejar.CookieJar()
                        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
                        with opener.open(data["open_url"], timeout=10) as gr:
                            html = gr.read().decode("utf-8", errors="replace")
                        out["geo_assets"] = re.findall(r"assets/[A-Za-z0-9_.-]+", html)
                        data["open_url"] = redact(str(data["open_url"]))
                    out["geographer"] = data
                elif ep == "/api/skills":
                    out["skills_status"] = 200
                    out["skills_title"] = data.get("title")
                elif ep == "/api/state":
                    out["state_busy"] = data.get("busy")
                    out["state_mode"] = data.get("mode")
                    out["state_lead"] = data.get("lead")
                else:
                    out["meta_health"] = data.get("non_secret_health", {}).get("lease", {})
            except Exception as exc:
                out[ep] = f"ERR:{type(exc).__name__}: {exc}"

    # Check ACCEPT-02's own catalog.sqlite graphs
    cat = vpath / ".librarian" / "geographer" / "catalog.sqlite"
    if cat.is_file():
        con = sqlite3.connect(f"file:{cat}?mode=ro", uri=True)
        out["accept02_graphs"] = [
            {"id": r[0], "label": r[3], "meta": r[7][:220]}
            for r in con.execute("SELECT * FROM graphs").fetchall()
        ]
        con.close()

    # Check G:/Libraries/_geo-runtime/env python + Resource-Library catalog CLI probe
    geo_py = Path(r"G:\Libraries\_geo-runtime\env\Scripts\python.exe")
    out["geo_runtime_exists"] = geo_py.is_file()
    if geo_py.is_file():
        proc = subprocess.run(
            [str(geo_py), "-m", "geographer", "--help"],
            capture_output=True, text=True, timeout=15,
        )
        out["geo_cli_rc"] = proc.returncode
        out["geo_cli_stdout_head"] = proc.stdout[:300]
        out["geo_cli_stderr_head"] = proc.stderr[:300]

        # Test one JSON-RPC initialize + tools/call list_graphs against serve-graphs stdio
        # using Resource-Library catalog read-only (wait: serve-graphs does not write unless mutation tool called)
        mcp_req = (
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "probe", "version": "1"}
            }}) + "\n" +
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n" +
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "list_graphs", "arguments": {}}}) + "\n"
        )
        proc2 = subprocess.run(
            [str(geo_py), "-m", "geographer", "serve-graphs", "--catalog",
             r"G:\Libraries\Resource-Library\.librarian\geographer\catalog.sqlite",
             "--transport", "stdio", "--tools", "all"],
            input=mcp_req, capture_output=True, text=True, timeout=20,
        )
        out["geo_mcp_probe_rc"] = proc2.returncode
        out["geo_mcp_probe_stderr"] = proc2.stderr[:500]
        lines = proc2.stdout.splitlines()
        out["geo_mcp_probe_line_count"] = len(lines)
        parsed_lines = []
        for idx, line in enumerate(lines):
            try:
                obj = json.loads(line)
                res = obj.get("result") or {}
                err = obj.get("error")
                parsed_lines.append({
                    "idx": idx,
                    "id": obj.get("id"),
                    "result_keys": sorted(res.keys()) if isinstance(res, dict) else str(type(res)),
                    "error": err,
                    "content": res.get("content") if isinstance(res, dict) else None,
                    "structured": res.get("structuredContent") if isinstance(res, dict) else None,
                })
            except Exception as exc:
                parsed_lines.append({"idx": idx, "raw": line[:200], "err": str(exc)})
        out["geo_mcp_lines"] = parsed_lines

    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
