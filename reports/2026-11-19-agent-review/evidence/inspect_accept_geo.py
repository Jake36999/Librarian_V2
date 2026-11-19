"""Read-only inspection of ACCEPT-02 Geo DBs and Resource-Library code graphs + F:/uv-data/Geo_Grapher MCP check."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def check_db(label: str, path: Path) -> None:
    if not path.is_file():
        print(label, "MISSING:", path)
        return
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    counts = {}
    for t in tables:
        if any(k in t for k in ("entit", "rel", "node", "edge", "file", "snap", "doc", "claim", "symbol")):
            try:
                counts[t] = con.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
            except Exception:
                pass
    print(f"=== {label}: {path.name} ({path.stat().st_size}B) ===")
    print("  key table counts:", counts)
    con.close()


def main() -> None:
    acc = Path(r"C:\Users\jakem\Librarian ACCEPT-02 Vault\.librarian\geographer\graphs")
    for gdir in sorted(acc.iterdir()) if acc.is_dir() else []:
        for db in sorted(gdir.glob("*.sqlite")):
            check_db(f"ACCEPT-02/{gdir.name}", db)

    # Also check E:\DataManagement subdirectories
    dm = Path(r"E:\DataManagement")
    if dm.is_dir():
        subs = [(p.name, len(list(p.rglob("*"))) if p.is_dir() else 1) for p in sorted(dm.iterdir())]
        print("E:/DataManagement entries:", subs[:25])

    # Check Geo_Grapher server/frontend source lines for browse-root & scissors & compare
    geo_src = Path(r"F:\uv-data\Geo_Grapher")
    for fp in sorted((geo_src / "src" / "geographer").rglob("*.py")):
        txt = fp.read_text(encoding="utf-8", errors="replace")
        for needle in ("browse_root", "browse-root", "prune", "derive-preview", "/api/graphs/compare"):
            if needle in txt:
                print(f"PY_MATCH {fp.relative_to(geo_src)}: {needle}")
    for fp in sorted((geo_src / "frontend" / "src").rglob("*.ts*")):
        txt = fp.read_text(encoding="utf-8", errors="replace")
        for needle in ("Scissors", "scissors", "Keep only", "browse-root", "No folders are browsable", "Inspector width"):
            if needle in txt:
                print(f"TS_MATCH {fp.relative_to(geo_src)}: {needle}")


if __name__ == "__main__":
    main()
