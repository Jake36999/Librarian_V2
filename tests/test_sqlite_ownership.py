"""INDEX-01: no new direct SQLite construction outside IndexService.

The product contract says the Core's IndexService is the vault index's sole
SQLite owner, but tools still build their own `Index` through `engine_for`.
This guard freezes today's debt: a new direct call fails, and a migrated one
must be removed from DEBT (INDEX-02..04) so the list only ever shrinks.
"""
import ast
import collections
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "resource_librarian"

# The ownership machinery itself: IndexService wraps Index, and with_engine /
# with_index fall back to a direct Index only when no Core service is installed.
INFRASTRUCTURE = {
    ("index.py", "Index"): 2, ("index.py", "sqlite3.connect"): 1,
    ("tools/library.py", "Index"): 2, ("tools/library.py", "engine_for"): 1,
}
# Separate SQLite stores, not the vault index.  Reviewed under INDEX-05.
OTHER_STORES = {("desk.py", "sqlite3.connect"): 1, ("lenses.py", "sqlite3.connect"): 1}
# Serving paths still opening the vault index directly (2026-10-24: 43; 39 after INDEX-02a).
DEBT = {
    ("batch.py", "engine_for"): 2,
    ("communities.py", "Index"): 1,
    ("extract.py", "Index"): 1,
    ("tools/authoring.py", "engine_for"): 4,
    ("tools/intake.py", "engine_for"): 2,
    ("tools/model_catalog.py", "engine_for"): 2,
    ("tools/ranking.py", "engine_for"): 2,
    ("tools/scout.py", "engine_for"): 1,
    ("tools/sessions.py", "engine_for"): 12,
    ("tools/staging.py", "engine_for"): 4,
    ("tools/taxonomy.py", "engine_for"): 3,
    ("tools/upkeep.py", "engine_for"): 5,
}


def _direct_calls() -> collections.Counter:
    found: collections.Counter = collections.Counter()
    for path in sorted(ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else \
                func.attr if isinstance(func, ast.Attribute) else ""
            owner = func.value.id if isinstance(func, ast.Attribute) and \
                isinstance(func.value, ast.Name) else ""
            kind = "sqlite3.connect" if (name == "connect" and owner == "sqlite3") else \
                name if name in ("engine_for", "Index") else ""
            if kind:
                found[(path.relative_to(ROOT).as_posix(), kind)] += 1
    return found


def test_no_new_direct_sqlite_construction():
    allowed = {**INFRASTRUCTURE, **OTHER_STORES, **DEBT}
    over = {key: count for key, count in _direct_calls().items() if count > allowed.get(key, 0)}
    assert not over, (
        "new direct SQLite construction in a serving path: "
        + ", ".join(f"{path} {kind} x{count}" for (path, kind), count in sorted(over.items()))
        + " - run index work through tools.library.with_engine / with_index (IndexService)")


def test_the_debt_list_only_shrinks():
    found = _direct_calls()
    stale = {key: (allowed, found.get(key, 0)) for key, allowed in DEBT.items()
             if found.get(key, 0) < allowed}
    assert not stale, (
        "migrated call sites must leave DEBT: "
        + ", ".join(f"{path} {kind}: {allowed} -> {now}" for (path, kind), (allowed, now) in sorted(stale.items())))


def test_the_guard_sees_the_patterns_it_forbids(tmp_path, monkeypatch):
    package = tmp_path / "resource_librarian"
    (package / "tools").mkdir(parents=True)
    (package / "tools" / "fresh.py").write_text(
        "import sqlite3\nfrom ..index import Index\n"
        "def a(ctx): return engine_for(ctx)\n"
        "def b(v): return Index(v)\n"
        "def c(p): return sqlite3.connect(p)\n", encoding="utf-8")
    monkeypatch.setattr(__import__(__name__), "ROOT", package)
    assert _direct_calls() == {("tools/fresh.py", "engine_for"): 1, ("tools/fresh.py", "Index"): 1,
                               ("tools/fresh.py", "sqlite3.connect"): 1}
