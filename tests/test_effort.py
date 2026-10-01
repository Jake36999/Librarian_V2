"""The effort control (owner, 2026-10-01): one slider moving every quantity in proportion -
helpers, parallel calls, steps and time per reply, call budgets, how much is reviewed."""
import threading

import pytest

from resource_librarian import effort
from resource_librarian.loop import Loop
from resource_librarian.providers import Reply, ToolCall
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.session import SessionStore
from resource_librarian.tools.staging import clerk_endpoint
from resource_librarian.vault import render_config

from test_sessions import library  # noqa: F401  (fixture)


def test_each_quantity_moves_with_the_slider_between_its_ends():
    low, high = effort.profile(1), effort.profile(10)
    assert (low["lead_agents"], low["tier2_agents"], low["tier3_agents"]) == (1, 3, 5)
    assert (high["lead_agents"], high["tier2_agents"], high["tier3_agents"]) == (4, 12, 25)
    assert low["budget_scale"] == 0.5 and high["budget_scale"] == 2.0
    assert effort.profile(effort.DEFAULT)["budget_scale"] == 1.0      # the default changes nothing
    steps = [effort.profile(n)["turn_steps"] for n in range(1, 11)]
    assert steps == sorted(steps) and steps[0] == 12 and steps[-1] == 80
    assert not low["review_offerings"] and high["review_replies"]
    assert effort.profile(99)["level"] == 10 and effort.profile("x")["level"] == effort.DEFAULT
    # well inside DeepInfra's 200 concurrent requests per model
    assert high["lead_agents"] + high["tier2_agents"] + high["tier3_agents"] < 200


def test_a_sessions_budgets_follow_the_effort_it_runs_under(library):
    c = Context(tier="contribute", vault=library, extras={"effort": effort.profile(10)})
    REGISTRY.call("open_session", {"purpose": "explore", "question": "q"}, c)
    store = SessionStore(library)
    high = store.load(c.session).budget_left()
    store.append(c.session, {"type": "effort", "level": 1, "budget_scale": 0.5})
    low = store.load(c.session).budget_left()
    plain = Context(tier="contribute", vault=library)
    REGISTRY.call("open_session", {"purpose": "explore", "question": "q"}, plain)
    normal = store.load(plain.session).budget_left()
    assert high == 2 * normal and low == normal // 2


def test_the_clerks_parallel_calls_follow_effort(library):
    config = library.config()
    config["clerk"] = {"provider": "deepinfra", "model": "m"}
    library.config_path.write_text(render_config(config))
    for level, n in ((1, 5), (10, 25)):
        c = Context(tier="contribute", vault=library, extras={"effort": effort.profile(level)})
        assert clerk_endpoint(c).concurrency == n
    assert clerk_endpoint(Context(tier="contribute", vault=library)).concurrency == 4  # preset


class Scripted:
    """A provider answering from a script; a helper's or the lead's."""
    name = "scripted"

    def __init__(self, script):
        self.script, self.lock = list(script), threading.Lock()

    def chat(self, system, messages, tools, **kwargs):
        with self.lock:
            step = self.script.pop(0) if self.script else Reply(text="done")
        return step(messages, tools) if callable(step) else step


def test_a_reply_stops_at_its_time_limit(library):
    import time
    def slow(messages, tools):
        time.sleep(0.2)
        return Reply(tool_calls=[ToolCall("c", "search", {"query": "x"})])
    lp = Loop(library, Scripted([slow] * 10), tier="contribute")
    lp.turn_seconds = 0.3
    turn = lp.send("hello")
    assert turn.stopped == "time_limit" and turn.steps < 10


def test_helpers_run_at_once_read_only_and_within_the_effort_cap(library):
    seen = []

    def helper_step(messages, tools):
        names = {t.name for t in tools}
        seen.append(names)
        if len(messages) == 1:                       # first step: try to write, then search
            return Reply(tool_calls=[ToolCall("w", "write_note", {"folder": "Notes", "name": "x",
                                                                  "body": "y"}),
                                     ToolCall("s", "search", {"query": "operating system"})])
        return Reply(text=f"found osquery ({messages[0]['content'][:20]})")

    provider = Scripted([helper_step] * 20)
    c = Context(tier="contribute", vault=library,
                extras={"effort": effort.profile(1), "agent_provider": lambda tier: provider})
    too_many = REGISTRY.call("delegate", {"questions": ["a", "b"], "tier": 1}, c)
    assert too_many["error"] == "invalid_arguments" and "allows 1" in too_many["detail"]
    out = REGISTRY.call("delegate", {"questions": ["what queries the OS?", "what about SQL?"],
                                     "tier": 2}, c)
    assert out["agents"] == 2 and all("found osquery" in r["answer"] for r in out["results"])
    assert all(names <= {"search", "get_note", "web_search", "read_url", "read_file",
                         "read_source_file", "list_files", "search_work", "topics_list"}
               for names in seen)
    assert not (library.root / "Notes" / "x.md").exists()            # the write was refused
    assert all("write_note" in r["tools"] for r in out["results"])


def test_no_models_no_helpers(library):
    out = REGISTRY.call("delegate", {"questions": ["a"]}, Context(tier="contribute",
                                                                  vault=library))
    assert out["error"] == "invalid_arguments" and "no model" in out["detail"]


@pytest.mark.parametrize("level", [1, 10])
def test_the_app_keeps_and_applies_the_setting(served, level):
    app, client, _ = served
    chosen = client.post("/api/effort", {"level": level})[1]
    assert chosen["level"] == level and app.settings.data["effort"] == level
    assert client.get("/api/state")[1]["effort"]["level"] == level


from test_app import served  # noqa: E402,F401  (fixture)
