"""Roadmap §4 G2 (2026-09-28): before a commitment (an answer, a server
proposal, a plan), the model says what it is assuming and how each assumption
was settled - checked against what the session actually did, not believed."""
import pytest

from resource_librarian import tools  # noqa: F401  (registers tools)
from resource_librarian.registry import REGISTRY, Context


@pytest.fixture
def m(vault):
    class Model:
        def __init__(self):
            self.ctx = Context(tier="contribute", vault=vault)

        def __call__(self, _tool, **arguments):
            return REGISTRY.call(_tool, arguments, self.ctx)

        def ok(self, _tool, **arguments):
            result = self(_tool, **arguments)
            assert "error" not in result, result
            return result

    model = Model()
    model.ok("open_session", purpose="start_pursuit", project="Databases Course")
    model.ok("create_project", name="Databases Course", stage="planning", summary="A term.",
             pursuit_kind="course")
    model.ok("advance")                                             # -> inventory
    model.ok("update_plan", fields={"inventory": "3 modules, a midterm and a final"})
    return model


def person(m):
    return Context(tier="curate", vault=m.ctx.vault, session=m.ctx.session)


def test_the_phase_waits_for_the_assumptions(m):
    assert m.ok("advance")["moved"] is False
    assert "record_assumptions" in m.ok("session_status")["open_items"][0]
    m.ok("record_assumptions", assumptions=[
        {"assumption": "the midterm is in week 7", "settled_by": "unverifiable"}])
    assert m.ok("advance")["moved"] == "plan"
    kept = m.ok("session_status")["assumptions"]
    assert kept == [{"assumption": "the midterm is in week 7", "settled_by": "unverifiable",
                     "how": "", "phase": "inventory", "visit": 1}]


def test_an_unverifiable_assumption_follows_the_thread_as_a_caveat(m):
    from resource_librarian import providers
    from resource_librarian.loop import Loop
    from resource_librarian.providers import Reply
    loop = Loop(m.ctx.vault, providers.Scripted(lambda s, msgs, t: Reply(text="ok")))
    loop.ctx.session = m.ctx.session
    assert "unverifiable" not in loop.system_prompt()
    m.ok("record_assumptions", assumptions=[
        {"assumption": "the midterm is in week 7", "settled_by": "unverifiable"}])
    m.ok("advance")                                                 # -> plan: still carried
    assert "- the midterm is in week 7" in loop.system_prompt()


def test_a_settlement_must_be_something_this_session_did(m):
    def refused(**item):
        out = m("record_assumptions", assumptions=[{"assumption": "x", **item}])
        return out["error"] == "invalid_arguments" and "not recorded" in out["detail"]

    assert refused(settled_by="search", how="it said so")          # never called here
    assert refused(settled_by="update_plan", how="recorded")        # the harness proves nothing
    assert refused(settled_by="create_project")                    # called, but what did it show?
    assert refused(settled_by="q1")                                 # no such question yet
    asked = m.ok("ask_user", question="Is the final open-book?")
    assert refused(settled_by=asked["question_id"])                # asked, not answered
    REGISTRY.call("answer", {"question_id": asked["question_id"], "answer": "yes"}, person(m))
    m.ok("record_assumptions", assumptions=[
        {"assumption": "the final is open-book", "settled_by": f"ask_user:{asked['question_id']}"},
        {"assumption": "the project note exists", "settled_by": "create_project",
         "how": "it returned the note's path"}])
    assert m.ok("advance")["moved"] == "plan"


def test_an_empty_list_says_nothing_is_assumed_and_costs_no_budget(m):
    before = m.ok("session_status")["budget_left"]
    m.ok("record_assumptions", assumptions=[])
    assert m.ok("session_status")["budget_left"] == before
    assert m.ok("advance")["moved"] == "plan"


def test_going_back_to_the_phase_asks_again(m):
    m.ok("record_assumptions", assumptions=[])
    m.ok("advance")                                                 # -> plan
    m.ok("advance", target="inventory", reason="the syllabus changed")
    assert m.ok("advance")["moved"] is False                       # a new visit, a new record
    m.ok("record_assumptions", assumptions=[])
    assert m.ok("advance")["moved"] == "plan"
