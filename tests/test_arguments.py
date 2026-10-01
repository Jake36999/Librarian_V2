"""Requirements Addendum R2 and R3 (2026-09-30): arguments read the way models write them,
from the exact failures seen in the Librarian-Uni sessions, and outcomes that never hide a
refusal. A reference that fits more than one thing is refused with the candidates, never
guessed."""
import json

from resource_librarian import intake, providers, tools  # noqa: F401  (registers tools)
from resource_librarian.loop import Loop
from resource_librarian.providers import Reply, ToolCall
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.session import SessionStore

from conftest import add_source, write_note
from test_intake import RESPONSES
from test_sessions import Model, library  # noqa: F401  (fixture)


def to_judge(m):
    m.ok("open_session", purpose="explore", question="host monitoring")
    m.ok("advance")
    m.ok("update_plan", fields={"map": "host tooling"})
    m.ok("advance")
    m.ok("open_brief", need="query operating system state", disqualifiers=["needs a GPU"])
    if m.ok("advance")["moved"] == "search":
        m.run_rounds(["operating system state database"], brief="B1")
        m.ok("advance")
    if "osquery" not in {c["source"] for c in m.ok("session_status")["candidates"]}:
        m.ok("add_candidate", source="osquery", brief="B1")
    assert m.ok("session_status")["phase"] == "judge"


def test_a_note_named_as_a_link_or_path_is_read_as_its_name(library):
    m = Model(library)
    to_judge(m)
    for written in ("[[osquery]]", "Sources/repository/osquery.md", "[[osquery|the tool]]"):
        out = m.ok("get_note", name=written)
        assert out.get("name", out.get("note", {}).get("name", "osquery")) and \
            any("read as 'osquery'" in a for a in out["adjusted_arguments"]), out


def test_a_reference_that_fits_two_notes_is_refused_with_both(library):
    write_note(library.root, "Concepts/Query Planning.md", "type: concept\nstatus: active",
               "## Definition\nx\n")
    write_note(library.root, "Notes/query planning.md", "type: note", "y\n")
    out = REGISTRY.call("get_note", {"name": "QUERY PLANNING"}, Context(tier="consult",
                                                                         vault=library))
    assert out["error"] == "invalid_arguments"
    assert "Query Planning" in out["detail"] and "query planning" in out["detail"]


def test_a_brief_is_found_by_its_id_in_any_case_or_by_its_own_need(library):
    m = Model(library)
    m.ok("open_session", purpose="explore", question="host monitoring")
    m.ok("advance")
    m.ok("update_plan", fields={"map": "m"})
    m.ok("advance")
    m.ok("open_brief", need="zzqx watch kernel calls", disqualifiers=["needs a module"])
    m.ok("advance")
    for written in ("b1", "brief B1", "zzqx watch kernel calls"):
        out = m.ok("research_round", queries=["kernel"], brief=written)
        assert any("read as 'B1'" in a for a in out["adjusted_arguments"])
    wrong = m("research_round", queries=["kernel"], brief="the brief about kernels")
    assert wrong["error"] == "invalid_arguments" and "B1: zzqx watch kernel calls" in wrong["detail"]


def test_with_no_briefs_the_refusal_says_to_open_one(library):
    m = Model(library)
    m.ok("open_session", purpose="add_project")
    out = m("ingest", ref="acme/rowstream", brief="Find sources on host monitoring")
    assert "open_brief" in str(out.get("detail", "")) or out.get("refused") == "PHASE_GATE"


def test_phase_and_enum_values_ignore_case(library):
    m = Model(library)
    to_judge(m)
    out = m.ok("decide", source="[[osquery]]", disposition="Keep", role="host tables")
    assert any("'Keep' read as 'keep'" in a for a in out["adjusted_arguments"])
    moved = m.ok("advance", target="Synthesise")
    assert moved.get("moved") == "synthesise" or "synthesise" in json.dumps(moved)


def test_a_pursuit_kind_is_read_as_the_one_permitted_value_it_starts(library):
    m = Model(library)
    m.ok("open_session", purpose="start_pursuit", project="Uni")
    out = m.ok("create_project", name="Uni", stage="Planning", summary="A course.",
               pursuit_kind="learn")
    note = (library.root / "Projects" / "Uni.md").read_text(encoding="utf-8")
    assert "pursuit_kind: learning" in note and "stage: planning" in note, out


def test_assumptions_settled_by_the_way_models_say_it(library):
    m = Model(library)
    m.ok("open_session", purpose="start_pursuit", project="Uni")
    m.ok("create_project", name="Uni", stage="planning", summary="s", pursuit_kind="course")
    m.ok("advance")
    m.ok("update_plan", fields={"inventory": "3 modules"})
    asked = m.ok("ask_user", question="Which campus?")
    m.person(asked["question_id"], "Preston")
    m.ok("search", query="operating system")
    m.ok("record_assumptions", assumptions=[
        {"assumption": "the campus is Preston", "settled_by": "user_answer"},
        {"assumption": "the library holds host tooling", "settled_by": "search tool results",
         "how": "osquery came back"}])
    kept = m.ok("session_status")["assumptions"]
    assert [a["settled_by"] for a in kept] == [asked["question_id"], "search"]


def test_a_multi_item_call_that_refused_every_item_says_so(library):
    c = Context(tier="curate", vault=library, extras={"fetcher": intake.Replay(RESPONSES)})
    staged = REGISTRY.call("ingest", {"ref": "acme/rowstream"}, c)
    model = Model(library)
    to_judge(model)
    out = model("staging_decide", item_ids=[staged["item"]], decision="accept")
    assert out.get("outcome") == "refused", out             # promotion waits for a person
    call = [json.loads(line) for line in SessionStore(library).path(model.ctx.session)
            .read_text(encoding="utf-8").splitlines() if '"staging_decide"' in line][-1]
    assert call["outcome"] == "refused" and call["items"][0]["id"] == staged["item"]


def test_the_trace_names_the_model_tier_phase_and_budget_of_each_call(vault):
    replies = iter([Reply(tool_calls=[ToolCall("1", "open_session",
                                               {"purpose": "explore", "question": "q"})],
                          model="lead-model-x"),
                    Reply(tool_calls=[ToolCall("2", "vault_status", {})], model="lead-model-x"),
                    Reply(text="done", model="lead-model-x")])
    loop = Loop(vault, providers.Scripted(lambda s, msgs, t: next(replies)))
    loop.send("go")
    events = [json.loads(line) for line in SessionStore(vault).path(loop.ctx.session)
              .read_text(encoding="utf-8").splitlines()]
    call = [e for e in events if e.get("type") == "call" and e["tool"] == "vault_status"][0]
    assert call["model"] == "lead-model-x" and call["tier"] == "contribute"
    assert call["phase"] == "frame" and isinstance(call["budget_before"], int)


def test_secret_looking_arguments_are_masked_in_the_trace():
    from resource_librarian.session import _trace_value
    assert _trace_value("api_key", "sk-123") == "••••" and _trace_value("query", "x") == "x"


def test_the_prompt_names_locked_tools_and_where_they_unlock(vault):
    loop = Loop(vault, providers.Scripted(lambda s, m, t: Reply(text="ok")))
    REGISTRY.call("open_session", {"purpose": "explore", "question": "q"}, loop.ctx)
    prompt = loop.system_prompt()
    assert "Not available in this phase" in prompt
    assert "decide (judge)" in prompt and "research_round (search)" in prompt
    assert "create_project (frame)" not in prompt           # frame is where we are: not locked


def calls(vault, session, tool):
    return [e for e in (json.loads(line) for line in SessionStore(vault).path(session)
                        .read_text(encoding="utf-8").splitlines())
            if e.get("type") == "call" and e["tool"] == tool]


def test_the_trace_records_the_permission_retries_and_budget_after(library):
    from resource_librarian.broker import Broker
    m = Model(library)
    m.ctx.extras["broker"] = Broker(mode="auto")
    m.ctx.extras["lead_status"] = "override: trying it out"            # R10, set by the app
    m.ok("open_session", purpose="explore", question="host monitoring")
    m.ok("advance")
    m.ok("update_plan", fields={"map": "m"})
    m.ok("advance")
    m.ok("open_brief", need="query operating system state", disqualifiers=["needs a GPU"])
    m.ok("advance")
    for _ in range(2):
        assert m("research_round", queries=["x"], brief="the kernel one")["error"]
    m.ok("research_round", queries=["operating system"], brief="b1")
    rounds = calls(library, m.ctx.session, "research_round")
    assert [c["retry"] for c in rounds] == [0, 1, 2]
    assert "B1: query operating system state" in rounds[0]["detail"]
    last = rounds[-1]
    assert last["permission"] == "allowed (auto mode)"
    assert last["lead"] == "override: trying it out"
    assert last["budget_after"] == last["budget_before"] - 1
    assert last["normalised"]["brief"] == "B1" and last["args"]["brief"] == "b1"
    m.ctx.extras["broker"] = Broker(mode="plan")
    assert m("research_round", queries=["y"], brief="B1")["refused"] == "PERMISSION_DENIED"
    assert calls(library, m.ctx.session, "research_round")[-1]["permission"] == \
        "permission_denied"


def test_each_item_keeps_why_it_went_the_way_it_did(library):
    from resource_librarian.session import _trace_item
    assert _trace_item({"id": "x", "refused": "PERSON_CONFIRMS", "detail": "a person accepts"}) \
        == {"id": "x", "status": "refused", "refused": "PERSON_CONFIRMS",
            "detail": "a person accepts"}
    assert _trace_item({"id": "y", "status": "accepted",
                        "promotion": {"path": "Sources/a.md"}})["path"] == "Sources/a.md"
