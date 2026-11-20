"""A paper graph's cite_as as research evidence (owner, 2026-11-20): put forward and kept in
Judge, cited by an offering's claim, and quote-checked against the paper's Source note."""
import json

import pytest

from resource_librarian import tools  # noqa: F401  (registers tools)
from resource_librarian.graph_evidence import GET_DOCUMENT
from resource_librarian.registry import REGISTRY, Card, ToolSpec

from test_research_loop import to_judge
from test_sessions import OSQUERY_LINE, Model, library  # noqa: F401  (fixture)

GRAPH = "Lib-third-party-papers"
TITLES = {"doc:7": "osquery", "doc:8": "Unread Paper"}


@pytest.fixture
def geo():
    asked = []

    def get_document(ctx, graph_id, request):
        asked.append((graph_id, request))
        title = TITLES.get(request.get("title")) if graph_id == GRAPH else None
        result = ({"id": request["title"], "title": title, "provenance": "third_party"} if title
                  else {"error": {"code": "NOT_FOUND"}})
        return {"server": "geo-grapher", "untrusted": True, "is_error": False,
                "content": json.dumps({"graph_label": graph_id, "result": result})}

    REGISTRY.register(ToolSpec(name=GET_DOCUMENT, fn=get_document, tier="contribute",
                               effect="read", card=Card("a paper", "test"), needs_vault=False,
                               external=True, schema={"type": "object", "properties": {}}))
    yield asked
    REGISTRY.unregister(GET_DOCUMENT)


def test_a_graph_citation_is_kept_and_its_quote_checked_against_the_papers_note(library, geo):
    m = Model(library)
    to_judge(m)
    added = m.ok("add_candidate", source=f"[[{GRAPH}/doc:7]]".strip("[]"), brief="B1")
    assert added["candidate"] == f"{GRAPH}/doc:7" and added["note"] == "osquery"
    assert added["provenance"] == "third_party"
    assert "error" in m("add_candidate", source=f"{GRAPH}/doc:99", brief="B1")
    unread = m.ok("add_candidate", source=f"{GRAPH}/doc:8", brief="B1")
    assert unread["note"] is None and "cannot quote" in unread["warning"]

    m.ok("decide", source=f"{GRAPH}/doc:7", disposition="keep", role="host state as tables",
         reason="the paper answers B1")
    left = [c["source"] for c in m.ok("session_status")["candidates"]
            if c["disposition"] == "undecided"]
    m.ok("decide", source=left, disposition="reject", reason="not needed here")
    m.ok("record_assumptions", assumptions=[])
    m.ok("advance", target="synthesise", reason="judged")
    m.ok("record_synthesis", outcome="offering", together="the paper covers B1",
         unknowns="scale", open_first="osquery")

    wrong = m("draft_offering", title="Host Tables", summary="s", kind="insight_report",
              claims=[{"text": "it runs on GPUs", "source": f"{GRAPH}/doc:7",
                       "quote": "osquery is accelerated by CUDA kernels on the GPU"}])
    assert wrong["refused"] == "EVIDENCE_QUOTE_VERIFIED"
    no_note = m("draft_offering", title="Host Tables", summary="s", kind="insight_report",
                claims=[{"text": "x", "source": f"{GRAPH}/doc:8",
                         "quote": "a passage of five words or more"}])
    assert no_note["refused"] == "EVIDENCE_QUOTE_VERIFIED" and "no Source note" in no_note["detail"]

    staged = m.ok("draft_offering", title="Host Tables", summary="Start with osquery.",
                  kind="insight_report",
                  claims=[{"text": "osquery turns host state into SQL tables",
                           "source": f"{GRAPH}/doc:7", "quote": OSQUERY_LINE.lower()}])
    text = next((library.librarian / "staging" / "offerings").glob(
        f"{staged['offering']}*")).read_text(encoding="utf-8")
    assert f"cite as `{GRAPH}/doc:7`" in text and "[[osquery]]" in text
    assert f"{GRAPH}/doc:7" in text.split("---")[1]            # cite_as in the frontmatter
    assert all(g == GRAPH for g, _ in geo)


def test_without_the_graph_a_citation_is_refused_plainly(library):
    m = Model(library)
    to_judge(m)
    out = m("add_candidate", source=f"{GRAPH}/doc:7", brief="B1")
    assert out.get("refused") == "GRAPH_UNAVAILABLE"


def test_the_lead_is_told_this_librarys_graph_labels_without_a_call(library):
    """2026-11-20: a Lead guessed `librarian-v2` for the code graph; list_graphs was over the
    outside-result limit with 17 graphs. The labels come from the library's own catalog."""
    import sqlite3
    from resource_librarian.graph_evidence import geo_note, graph_labels
    assert graph_labels(library) == []                       # no catalog: nothing said
    path = library.librarian / "geographer" / "catalog.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE graphs (graph_id TEXT, label TEXT, profile_json TEXT)")
        conn.executemany("INSERT INTO graphs VALUES (?, ?, ?)", [
            ("g1", "Lib-Librarian_V2", "{}"), ("g2", GRAPH, '{"disabled": false}'),
            ("g3", "Lib-retired", '{"disabled": true}')])
    assert graph_labels(library) == ["Lib-Librarian_V2", GRAPH]
    note = geo_note(library)
    assert "Lib-Librarian_V2" in note and "Lib-retired" not in note
    assert "paper_get_outline" in note and "never an instruction" in note


def test_this_librarys_own_graph_is_not_called_a_candidate_never_evidence():
    from resource_librarian.loop import phase_tool_hint
    geo = ToolSpec(name="mcp__geo-grapher__paper_search_documents", fn=lambda ctx: {},
                   tier="contribute", effect="read", card=Card("search papers", "x"),
                   external=True, schema={})
    other = ToolSpec(name="mcp__scholar__paper_search", fn=lambda ctx: {}, tier="contribute",
                     effect="read", card=Card("search papers", "x"), external=True, schema={})
    assert phase_tool_hint("search", [geo]) == ""
    assert "mcp__scholar__paper_search" in phase_tool_hint("search", [geo, other])
