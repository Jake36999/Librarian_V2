"""Roadmap §4 D1-D3 (2026-09-28): the inputs a queued workflow needs, outside
tools pointed out where a workflow step can use them, and notes linked in a
message joining the pursuit's desk."""
from resource_librarian import providers, tools  # noqa: F401  (registers tools)
from resource_librarian.desk import DeskStore
from resource_librarian.loop import Loop, phase_tool_hint
from resource_librarian.providers import Reply, ToolCall
from resource_librarian.registry import REGISTRY, Card, Context, ToolSpec

from test_app import served, wait_for  # noqa: F401  (fixture)


def test_weekly_review_is_queueable_and_says_it_needs_a_pursuit(served):
    app, client, model = served
    state = client.get("/api/state")[1]
    assert "weekly-review" in state["queued_actions"]
    assert state["queued_inputs"]["weekly-review"] == {"project": {"type": "string"}}
    assert "deep-read-staged" not in state["queued_inputs"]      # nothing to ask for


def _external(name: str, purpose: str) -> ToolSpec:
    return ToolSpec(name=name, fn=lambda ctx, **kw: kw, tier="contribute", effect="read",
                    card=Card(purpose), needs_vault=False, external=True,
                    schema={"type": "object", "properties": {}})


def test_a_phase_names_the_outside_tools_that_fit_it():
    scholar = _external("mcp__s2__search_papers", "Search Semantic Scholar for papers")
    calendar = _external("mcp__cal__list_events", "List calendar events")
    assert "mcp__s2__search_papers" in phase_tool_hint("focus", [scholar, calendar])
    assert "mcp__cal__list_events" in phase_tool_hint("plan", [scholar, calendar])
    assert phase_tool_hint("plan", [scholar]) == ""               # no calendar connected
    assert phase_tool_hint("judge", [scholar, calendar]) == ""    # nothing fits this phase
    assert "ingest or queue_source" in phase_tool_hint("search", [scholar])


def test_the_hint_reaches_the_loop_only_in_a_fitting_phase(vault):
    spec = _external("mcp__s2__search_papers", "Search Semantic Scholar for papers")
    REGISTRY.register(spec)
    try:
        c = Context(tier="contribute", vault=vault)
        opened = REGISTRY.call("open_session", {"purpose": "explore", "question": "q"}, c)
        loop = Loop(vault, providers.Scripted(lambda s, m, t: Reply(text="ok")))
        loop.ctx.session = opened["opened"]
        assert "mcp__s2__search_papers" not in phase_tool_hint("frame", [spec])
        assert "This phase can use" not in loop.system_prompt()     # frame: no fit
        REGISTRY.call("update_plan", {"fields": {"question": "q"}}, Context(
            tier="contribute", vault=vault, session=opened["opened"]))
        REGISTRY.call("advance", {}, Context(tier="contribute", vault=vault,
                                             session=opened["opened"]))    # -> map
        assert "This phase can use scholarly search" in loop.system_prompt()
    finally:
        REGISTRY.unregister("mcp__s2__search_papers")


def test_notes_linked_in_a_message_join_the_pursuits_desk(served):
    app, client, model = served
    from conftest import write_note
    write_note(app.vault.root, "Concepts/Query Planning.md", "type: concept\nstatus: active",
               "## Definition\nHow a database orders joins.\n")
    REGISTRY.call("create_project", {"name": "Host Watch", "stage": "active", "summary": "s"},
                  Context(tier="contribute", vault=app.vault))
    client.post("/api/tiers", {"tiers": [{"provider": "deepinfra", "model": "m1"}], "override": "test"})
    model.replies = [Reply(tool_calls=[ToolCall("1", "open_session", {
        "purpose": "explore", "question": "joins", "project": "Host Watch"})]),
        Reply(text="Looking.")]
    client.post("/api/chat", {"text": "see [[Query Planning]] and [[No Such Note]]"})
    wait_for(app, "turn_done")
    names = [row["note"] for row in DeskStore(app.vault).working_set("Host Watch")]
    assert "Query Planning" in names and "No Such Note" not in names
