"""W2 `learn` (Co-work Roadmap §2): stewarding, not answering - goal -> baseline
-> focus -> practice -> consolidate -> next, walked through the registry.
Coach stance is forced regardless of the person's own reply-length/stance
setting (`Loop.system_prompt`, tested separately in test_loop.py)."""
import pytest

from resource_librarian import notes, tools  # noqa: F401  (registers tools)
from resource_librarian.registry import REGISTRY, Context

from conftest import write_note


@pytest.fixture
def m(vault):
    write_note(vault.root, "Concepts/Query Planning.md",
              "type: concept\nconcept_kind: pattern\nstatus: active",
              "## Definition\nHow a database decides the order to join and filter tables.\n")

    class Model:
        def __init__(self):
            self.ctx = Context(tier="contribute", vault=vault)

        def __call__(self, _tool, **arguments):
            return REGISTRY.call(_tool, arguments, self.ctx)

        def ok(self, _tool, **arguments):
            result = self(_tool, **arguments)
            assert "error" not in result, result
            return result

    return Model()


def test_walks_goal_to_next(m, vault):
    opened = m.ok("open_session", purpose="learn", question="understand query planning")
    assert opened["phases"] == ["goal", "baseline", "focus", "practice", "consolidate", "next"]

    assert m.ok("advance")["moved"] is False
    m.ok("update_plan", fields={"goal": "read an EXPLAIN plan and say what it will do",
                                "deadline": "this week"})
    assert m.ok("advance")["moved"] == "baseline"

    assert m.ok("advance")["moved"] is False
    m.ok("update_plan", fields={"baseline": "knows SQL, has never read a query plan"})
    assert m.ok("advance")["moved"] == "focus"

    assert m.ok("advance")["moved"] is False
    m.ok("search", query="query planning", intent="orient")
    m.ok("update_plan", fields={"focus": ["Query Planning"]})
    assert m.ok("advance")["moved"] == "practice"

    missing = m.ok("advance")
    assert missing["moved"] is False and "Query Planning" in missing["missing"][0]
    m.ok("understanding_record", concept="Query Planning",
        own_words="the planner picks join order by estimated row counts", confidence="ok")
    assert m.ok("advance")["moved"] == "consolidate"

    assert m.ok("advance")["moved"] is False
    m.ok("understanding_record", concept="Query Planning",
        own_words="it costs each join order and picks the cheapest", confidence="solid")
    m.ok("update_plan", fields={"consolidated": True})
    assert m.ok("advance")["moved"] == "next"

    assert m.ok("advance")["moved"] is False
    m.ok("task_add", note="Query Planning", text="Review: Query Planning", due="2026-10-01",
        heading="Understanding")
    m.ok("update_plan", fields={"scheduled": True})
    assert m.ok("advance")["moved"] is False                 # this is the last phase
    assert m.ok("close_session", summary="practised query planning", gaps="none")["closed"]

    understanding = notes.load(vault.root / "Concepts/Query Planning.md").sections()["Understanding"]
    assert "ok): the planner picks join order" in understanding
    assert "solid): it costs each join order" in understanding


def test_practice_requires_every_focus_concept_practised(m):
    write_note(m.ctx.vault.root, "Concepts/Indexing.md",
              "type: concept\nconcept_kind: pattern\nstatus: active",
              "## Definition\nA structure that speeds up lookups.\n")
    m.ok("open_session", purpose="learn", question="two concepts")
    m.ok("update_plan", fields={"goal": "understand both"})
    m.ok("advance")
    m.ok("update_plan", fields={"baseline": "new to both"})
    m.ok("advance")
    m.ok("update_plan", fields={"focus": ["Query Planning", "Indexing"]})
    m.ok("advance")
    m.ok("understanding_record", concept="Query Planning", own_words="cost-based", confidence="ok")
    missing = m.ok("advance")
    assert missing["moved"] is False and "Indexing" in missing["missing"][0]
    m.ok("understanding_record", concept="Indexing", own_words="a lookup structure",
        confidence="shaky")
    assert m.ok("advance")["moved"] == "consolidate"


def test_understanding_record_needs_a_real_concept(m):
    refused = m("understanding_record", concept="Not A Concept", own_words="x", confidence="ok")
    assert refused["error"] == "invalid_arguments"


def test_understanding_record_refuses_an_empty_explanation(m):
    write_note(m.ctx.vault.root, "Concepts/Empty Test.md",
              "type: concept\nconcept_kind: term\nstatus: active", "## Definition\nx\n")
    refused = m("understanding_record", concept="Empty Test", own_words="   ", confidence="ok")
    assert refused["error"] == "invalid_arguments"


def test_understanding_due_reads_review_tasks_off_the_concept_note(m):
    m.ok("task_add", note="Query Planning", text="Review: Query Planning", due="2020-01-01",
        heading="Understanding")
    due = m.ok("understanding_due")["due"]
    assert due == [{"concept": "Query Planning", "note": "Query Planning", "due": "2020-01-01"}]


def test_review_due_opens_one_parked_learn_session_per_due_concept(m):
    # Roadmap §2 W4's auto-open half (§4 D4).
    m.ok("task_add", note="Query Planning", text="Review: Query Planning", due="2020-01-01",
         heading="Understanding")
    out = m.ok("review_due_open")
    assert [o["concept"] for o in out["opened"]] == ["Query Planning"]
    session_id = out["opened"][0]["session"]
    listed = {r["id"]: r for r in m.ok("list_sessions")["sessions"]}
    assert listed[session_id]["status"] == "parked"
    assert listed[session_id]["question"] == "Review: Query Planning"
    # Resumed, goal, baseline and focus are already recorded: it walks to practice.
    m.ok("resume_session", session_id=session_id)
    for phase in ("baseline", "focus", "practice"):
        assert m.ok("advance")["moved"] == phase
    # Running it again opens nothing new for a concept already waiting.
    again = m.ok("review_due_open")
    assert again["opened"] == [] and again["already_waiting"] == ["Query Planning"]


def test_review_due_is_a_one_click_queued_workflow():
    from resource_librarian.app import QUEUED
    assert "review-due" in QUEUED
