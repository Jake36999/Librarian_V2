"""The post-MVP fixes (2026-09-30), made in another session and tested here: research
rounds that don't flood, a missing Project note that refuses instead of crashing, sources
tracked on the session they were found for, and a turn a person can stop."""
import threading

from resource_librarian import intake, providers, tools  # noqa: F401  (registers tools)
from resource_librarian.loop import Loop
from resource_librarian.providers import Reply, ToolCall
from resource_librarian.registry import REGISTRY, Context

from conftest import add_source
from test_intake import RESPONSES
from test_sessions import Model, library  # noqa: F401  (fixture)


def to_search(m, need="query operating system state"):
    m.ok("open_session", purpose="explore", question="host monitoring")
    m.ok("advance")
    m.ok("update_plan", fields={"map": "host tooling"})
    m.ok("advance")
    m.ok("open_brief", need=need, disqualifiers=["needs a GPU"])
    assert m.ok("advance")["moved"] == "search"


def test_a_round_lists_only_sources_its_words_matched(library):
    # With a constraint, search lists every note that passes it even when no term
    # matched; a research round must not take those as finds.
    m = Model(library)
    to_search(m)
    out = m.ok("research_round", queries=["zzqx nothing matches this"], brief="B1")
    assert out["new_candidates"] == []


def test_model_profiles_stay_out_of_ordinary_research(library):
    add_source(library.root, "gpt-oss-20b", "An open-weight model for operating system state "
               "queries.", kind_folder="model",
               extra_fm="kind: model")
    m = Model(library)
    to_search(m, need="zzqx a need the library does not cover")   # so Search is not skipped
    out = m.ok("research_round", queries=["operating system state"], brief="B1")
    assert "osquery" in out["new_candidates"] and "gpt-oss-20b" not in out["new_candidates"]
    # ...but research about models does include them.
    out = m.ok("research_round", queries=["LLM operating system state"], brief="B1")
    assert "gpt-oss-20b" in out["new_candidates"]


def test_a_missing_project_note_is_a_refusal_with_the_remedy(library):
    m = Model(library)
    m.ok("open_session", purpose="explore", question="q")
    m.ok("advance")
    m.ok("update_plan", fields={"map": "m"})
    m.ok("advance")
    from resource_librarian.session import SessionStore
    SessionStore(library).append(m.ctx.session, {"type": "plan",
                                                  "fields": {"project": "Never Written"}})
    out = m("open_brief", need="x", disqualifiers=["y"])
    assert out["error"] == "invalid_arguments" and "create_project" in out["detail"]


def test_ingested_and_accepted_sources_are_tracked_on_their_session(library):
    m = Model(library)
    m.ctx.extras["fetcher"] = intake.Replay(RESPONSES)
    to_search(m)
    staged = m.ok("ingest", ref="acme/rowstream", brief="B1")
    envelope = m.ok("session_status")
    assert envelope["library_item_counts"] == {"staged": 1}
    person = Context(tier="curate", vault=library, extras={"fetcher": intake.Replay(RESPONSES)})
    REGISTRY.call("staging_decide", {"item_ids": [staged["item"]], "decision": "accept",
                                     "bottom_line": "Streams Postgres row changes.",
                                     "what_it_solves": "Change data capture."}, person)
    items = m.ok("session_status")["library_items"]
    accepted = [i for i in items if i["id"] == staged["item"]]
    assert accepted and accepted[0]["status"] == "accepted" and accepted[0]["path"]


def test_a_person_can_stop_a_turn_between_steps(vault):
    stop = threading.Event()
    calls = []

    def answer(system, messages, tools_):
        calls.append(1)
        stop.set()                                   # the person presses Stop mid-turn
        return Reply(tool_calls=[ToolCall("1", "vault_status", {})])
    loop = Loop(vault, providers.Scripted(answer))
    turn = loop.send("status please", cancel=stop)
    assert turn.stopped == "cancelled" and len(calls) == 1
