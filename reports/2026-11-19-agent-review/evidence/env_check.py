"""Environment, build, Core, and MCP reachability check (redacts all secrets/tokens)."""
from __future__ import annotations

import http.cookiejar
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, r"D:\Librarian_V2\src")
from resource_librarian import connection, usage_log
from resource_librarian.vault import Vault


def redact(text: str) -> str:
    text = re.sub(r"([?&](?:geo_)?token=)[^&\s\"'>]+", r"\1<REDACTED_TOKEN>", text)
    return text


def main() -> None:
    out: dict = {}

    # 1. Installed geographer package / wheel in D:\Librarian_V2\.venv
    try:
        import geographer  # type: ignore
        pkg_file = Path(geographer.__file__).resolve()
        dist_dir = Path(sys.prefix) / "share" / "geographer" / "frontend" / "dist" / "assets"
        pkg_assets = sorted(p.name for p in dist_dir.iterdir()) if dist_dir.is_dir() else []
        out["venv_geographer"] = {"file": str(pkg_file), "dist_assets": pkg_assets}
    except Exception as exc:
        out["venv_geographer"] = {"error": f"{type(exc).__name__}: {exc}"}

    # Also inspect D:\Librarian_V2\.venv\Lib\site-packages\*.pth / .egg-link / editable info
    sp = Path(sys.prefix) / "Lib" / "site-packages"
    geo_pth = []
    if sp.is_dir():
        for p in sp.iterdir():
            if "geo" in p.name.lower() or "librarian" in p.name.lower():
                item = {"name": p.name}
                if p.is_file() and p.suffix in (".pth", ".json") and p.stat().st_size < 4096:
                    item["text"] = p.read_text(encoding="utf-8", errors="replace").strip()
                geo_pth.append(item)
    out["venv_site_packages_matches"] = geo_pth

    # 2. Check plugin MCP definitions under C:\Users\jakem\.gemini\config\plugins
    plug_dir = Path.home() / ".gemini" / "config" / "plugins"
    plug_mcps = {}
    if plug_dir.is_dir():
        for name in ("librarian", "geo-grapher"):
            d = plug_dir / name
            files = []
            if d.is_dir():
                for fp in d.rglob("*mcp*.json"):
                    try:
                        data = json.loads(fp.read_text(encoding="utf-8"))
                        files.append({"file": str(fp), "content": data})
                    except Exception as exc:
                        files.append({"file": str(fp), "error": str(exc)})
            plug_mcps[name] = files
    out["plugin_mcp_configs"] = plug_mcps

    # 3. ACCEPT-02 Core & Geo status
    vpath = Path(r"C:\Users\jakem\Librarian ACCEPT-02 Vault")
    rec = connection.load(vpath)
    accept_info: dict = {
        "conn_url": rec.get("url") if isinstance(rec, dict) else None,
        "conn_pid": rec.get("pid") if isinstance(rec, dict) else None,
        "usage_budget": usage_log.budget(Vault(vpath)),
    }
    if isinstance(rec, dict) and rec.get("url") and rec.get("token"):
        req = urllib.request.Request(
            rec["url"].rstrip("/") + "/api/geographer",
            headers={"X-Librarian-Token": rec["token"]},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                geo = json.loads(r.read().decode("utf-8"))
            geo_redacted = {
                k: (redact(v) if isinstance(v, str) else v) for k, v in geo.items()
            }
            accept_info["geographer_status"] = geo_redacted
            # Use cookie jar to follow open_url (or fetch index with cookie)
            if geo.get("open_url"):
                cj = http.cookiejar.CookieJar()
                opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
                with opener.open(geo["open_url"], timeout=10) as gr:
                    html = gr.read().decode("utf-8", errors="replace")
                accept_info["geo_html_assets"] = re.findall(r"assets/[A-Za-z0-9_.-]+", html)
                accept_info["geo_html_title"] = re.findall(r"<title>(.*?)</title>", html)
                # Try /api/v1.1/graphs on the Geo service using the established session cookie
                try:
                    with opener.open(geo["url"].rstrip("/") + "/api/v1.1/graphs", timeout=10) as g2:
                        graphs_data = json.loads(g2.read().decode("utf-8"))
                    accept_info["geo_graphs_count"] = len(graphs_data.get("graphs") or graphs_data if isinstance(graphs_data, (list, dict)) else [])
                    accept_info["geo_graphs_sample"] = [
                        g.get("label") or g.get("graph_id") or g
                        for g in (graphs_data.get("graphs") if isinstance(graphs_data, dict) else graphs_data)[:10]
                    ] if isinstance(graphs_data, (list, dict)) else str(graphs_data)[:300]
                except Exception as exc:
                    accept_info["geo_graphs_err"] = f"{type(exc).__name__}: {exc}"
        except Exception as exc:
            accept_info["geographer_err"] = f"{type(exc).__name__}: {exc}"
    out["accept02"] = accept_info

    # 4. Also check where Geo-Grapher F:\uv-data\Geo_Grapher\output\named-graphs points
    ng = Path(r"F:\uv-data\Geo_Grapher\output\named-graphs")
    if ng.is_dir():
        out["geo_repo_named_graphs"] = sorted(p.name for p in ng.iterdir())
        cat = ng / "catalog.sqlite"
        out["geo_repo_catalog_exists"] = cat.is_file()
        out["geo_repo_catalog_size"] = cat.stat().st_size if cat.is_file() else 0

    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
