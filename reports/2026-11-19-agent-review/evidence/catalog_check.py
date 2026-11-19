"""Read-only check of Geo SQLite catalogs and ACCEPT-02 Core freshness."""
from __future__ import annotations

import json
import sqlite3
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, r"D:\Librarian_V2\src")
from resource_librarian import connection


def inspect_catalog(label: str, cat: Path) -> None:
    if not cat.is_file():
        print(label, "CATALOG_MISSING", cat)
        return
    con = sqlite3.connect(f"file:{cat}?mode=ro", uri=True)
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"=== {label}: {cat} ({cat.stat().st_size} bytes) tables={tables} ===")
    for tbl in tables:
        try:
            cnt = con.execute(f"SELECT COUNT(*) FROM [{tbl}]").fetchone()[0]
            print(f"  table {tbl}: {cnt} rows")
            if tbl == "graphs":
                for row in con.execute("SELECT * FROM graphs").fetchall():
                    print("   ", row)
        except Exception as exc:
            print(f"  table {tbl} err: {exc}")
    con.close()


def main() -> None:
    for label, cat in [
        ("Resource-Library", Path(r"G:\Libraries\Resource-Library\.librarian\geographer\catalog.sqlite")),
        ("ACCEPT-02", Path(r"C:\Users\jakem\Librarian ACCEPT-02 Vault\.librarian\geographer\catalog.sqlite")),
        ("GeoRepo-NamedGraphs", Path(r"F:\uv-data\Geo_Grapher\output\named-graphs\catalog.sqlite")),
    ]:
        inspect_catalog(label, cat)

    rec = connection.load(Path(r"C:\Users\jakem\Librarian ACCEPT-02 Vault"))
    if isinstance(rec, dict) and rec.get("url") and rec.get("token"):
        for ep in ("/api/services", "/api/skills", "/api/state"):
            req = urllib.request.Request(
                rec["url"].rstrip("/") + ep,
                headers={"X-Librarian-Token": rec["token"]},
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    body = json.loads(r.read().decode("utf-8"))
                if ep == "/api/state":
                    print("CORE /api/state busy=", body.get("busy"), "keys_in_state=", sorted(body.keys()))
                else:
                    print(f"CORE {ep}:", json.dumps(body, ensure_ascii=False)[:450])
            except Exception as exc:
                print(f"CORE {ep} ERR:", exc)


if __name__ == "__main__":
    main()
