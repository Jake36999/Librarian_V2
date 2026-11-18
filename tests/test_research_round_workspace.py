"""An uncovered research round says what the library's own working documents hold (2026-11-18:
before promotion, rounds saw only folder stubs while the documents sat indexed and unsearched)."""
from types import SimpleNamespace

from test_mvp_fixes import to_search
from test_sessions import Model, library  # noqa: F401  (fixture)


def test_an_uncovered_round_reports_workspace_leads(library, monkeypatch):
    from resource_librarian.tools import sessions
    real = sessions.search

    def fake(engine, query, intent, constraints=None, limit=10, *a, **k):
        if intent == "workspace":
            return SimpleNamespace(to_dict=lambda: {"results": [
                {"name": "workspace:docs-1/relay-design.md", "why": "matched mtls relay"}]})
        return real(engine, query, intent, constraints, limit=limit, *a, **k)
    monkeypatch.setattr(sessions, "search", fake)
    m = Model(library)
    to_search(m)
    out = m.ok("research_round", queries=["zzqx mtls relay nothing in the catalogue"], brief="B1")
    entry = out["queries"][0]
    assert entry["verdict"] in ("uncovered", "thin")
    assert entry["workspace"] == [{"name": "workspace:docs-1/relay-design.md", "why": "matched mtls relay"}]
    assert out["new_candidates"] == []                     # leads to read, not Sources to decide
