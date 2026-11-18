import threading
import time

import pytest

from resource_librarian import tools  # noqa: F401
from resource_librarian.broker import Broker
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.session import SessionStore

from conftest import add_source


@pytest.fixture
def library(vault):
    add_source(vault.root, "osquery", "Query operating system state with SQL.")
    return vault


def ctx(vault, broker, session=""):
    return Context(tier="contribute", vault=vault, session=session or None,
                   extras={"broker": broker})


def to_find(c):
    REGISTRY.call("open_session", {"purpose": "apply"}, c)
    REGISTRY.call("update_plan", {"fields": {"question": "q"}}, c)
    assert REGISTRY.call("advance", {}, c)["moved"] == "find"


def call_in_thread(name, args, context):
    box = {}
    thread = threading.Thread(target=lambda: box.update(REGISTRY.call(name, args, context)))
    thread.start()
    return thread, box


def wait_for_pending(broker, n=1):
    for _ in range(200):
        if len(broker.pending()) >= n:
            return broker.pending()
        time.sleep(0.01)
    raise AssertionError("no pending request appeared")


def test_reads_are_never_asked(library):
    broker = Broker("ask")
    assert REGISTRY.call("search", {"query": "osquery"}, ctx(library, broker))["results"]
    assert broker.pending() == []


def test_plan_mode_denies_writes_but_lets_the_model_plan(library):
    broker = Broker("plan")
    c = ctx(library, broker)
    assert REGISTRY.call("open_session", {"purpose": "explore", "question": "q"}, c)["opened"]
    assert "error" not in REGISTRY.call("update_plan", {"fields": {"notes": "n"}}, c)
    denied = REGISTRY.call("queue_source", {"ref": "a/b"}, c)
    assert denied["refused"] == "PERMISSION_DENIED" and "Plan mode" in denied["detail"]


def test_ask_waits_for_a_person_and_the_listener_hears(library):
    broker = Broker("ask")
    heard = []
    broker.subscribe(heard.append)
    thread, box = call_in_thread("queue_source", {"ref": "a/b"}, ctx(library, broker))
    request = wait_for_pending(broker)[0]
    assert request["tool"] == "queue_source" and request["arguments"]["ref"] == "a/b"
    assert heard[0]["type"] == "permission_request"
    broker.answer(request["id"], "allow_once")
    thread.join(5)
    assert box["waiting"] == 1
    assert [e["type"] for e in heard] == ["permission_request", "permission_decided"]


def test_mode_switch_releases_waiting_actions_without_resubmission(library):
    """M5 acceptance: a mode switch releases or denies a waiting action."""
    broker = Broker("ask")
    c = ctx(library, broker)
    first, box1 = call_in_thread("queue_source", {"ref": "a/one"}, c)
    second, box2 = call_in_thread("queue_source", {"ref": "a/two"}, c)
    wait_for_pending(broker, 2)
    switched = broker.set_mode("auto")
    first.join(5)
    second.join(5)
    assert len(switched["released"]) == 2 and "error" not in box1 and "error" not in box2
    broker.set_mode("ask")
    third, box3 = call_in_thread("queue_source", {"ref": "a/three"}, c)
    wait_for_pending(broker)
    assert broker.set_mode("plan")["denied"]
    third.join(5)
    assert box3["refused"] == "PERMISSION_DENIED" and "switch to plan" in box3["detail"]


def test_allow_for_session_and_tool_settings(library):
    broker = Broker("ask")
    c = ctx(library, broker)
    to_find(c)
    thread, _ = call_in_thread("log_use", {"source": "osquery", "used_for": "x"}, c)
    broker.answer(wait_for_pending(broker)[0]["id"], "allow_session")
    thread.join(5)
    assert "error" not in REGISTRY.call("log_use", {"source": "osquery", "used_for": "y"}, c)
    broker.set_tool("log_use", "deny")
    assert REGISTRY.call("log_use", {"source": "osquery", "used_for": "z"},
                         c)["refused"] == "PERMISSION_DENIED"
    auto = Broker("auto", {"queue_source": "ask"})
    thread, box = call_in_thread("queue_source", {"ref": "a/b"}, ctx(library, auto))
    auto.answer(wait_for_pending(auto)[0]["id"], "deny")
    thread.join(5)
    assert box["refused"] == "PERMISSION_DENIED" and "by a person" in box["detail"]


def test_unanswered_parks_the_session_and_never_approves(library):
    broker = Broker("ask", timeout=0.2)
    c = ctx(library, broker)
    to_find(c)
    out = REGISTRY.call("log_use", {"source": "osquery", "used_for": "x"}, c)
    assert out["refused"] == "PERMISSION_UNANSWERED"
    assert SessionStore(library).load(c.session).status == "parked"


def test_phase_gate_refuses_before_anyone_is_asked(library):
    broker = Broker("ask")
    c = ctx(library, broker)
    REGISTRY.call("open_session", {"purpose": "explore", "question": "q"}, c)
    out = REGISTRY.call("draft_offering", {"title": "t", "summary": "s", "claims": []}, c)
    assert out["refused"] == "PHASE_GATE" and broker.pending() == []


def test_a_cached_engine_works_from_any_thread(library):
    c = Context(tier="consult", vault=library)
    REGISTRY.call("search", {"query": "osquery"}, c)                  # engine cached here
    thread, box = call_in_thread("search", {"query": "osquery"}, c)
    thread.join(10)
    assert box["results"] and "error" not in box


# -- an approved workflow is pre-authorised for its own steps ---------------------------------

def granted(vault, broker, tools, label="approved ingestion"):
    return Context(tier="contribute", vault=vault, extras={
        "broker": broker, "workflow_grant": {"label": label, "tools": frozenset(tools)}})


def test_a_granted_workflow_runs_its_own_steps_without_asking(library):
    """A person approved this exact batch (or started this workflow): its steps are not asked
    about again, one write at a time, until the run is done."""
    broker = Broker("ask")
    spec = REGISTRY.get("queue_source")
    note = broker.check(spec, {"ref": "a/b"}, granted(library, broker, {"queue_source"}))
    assert note == "allowed (approved ingestion)" and broker.pending() == []


def test_a_grant_covers_only_the_tools_it_names(library):
    broker = Broker("ask", timeout=0.2)
    c = granted(library, broker, {"deep_read"})
    result = REGISTRY.call("queue_source", {"ref": "a/b"}, c)          # not in the grant
    assert result["refused"] == "PERMISSION_UNANSWERED"


def test_a_grant_never_overrides_deny_plan_or_always_ask(library):
    spec = REGISTRY.get("queue_source")
    denied = Broker("ask", {"queue_source": "deny"})
    with pytest.raises(Exception) as caught:
        denied.check(spec, {"ref": "a/b"}, granted(library, denied, {"queue_source"}))
    assert "PERMISSION_DENIED" in str(caught.value) or "Deny" in str(caught.value)
    plan = Broker("plan")
    with pytest.raises(Exception):
        plan.check(spec, {"ref": "a/b"}, granted(library, plan, {"queue_source"}))
    asked = Broker("ask", {"queue_source": "ask"}, timeout=0.2)         # a tool set to Ask stays Ask
    c = granted(library, asked, {"queue_source"})
    assert REGISTRY.call("queue_source", {"ref": "a/b"}, c)["refused"] == "PERMISSION_UNANSWERED"
    from resource_librarian.broker import ALWAYS_ASK
    assert "project_edit" in ALWAYS_ASK          # and these are never in a grant's reach
    always = Broker("ask", timeout=0.2)
    assert always._policy("project_edit", "write", False, "", granted=True) == "ask"
