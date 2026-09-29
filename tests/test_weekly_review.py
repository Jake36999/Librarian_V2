"""W3 `weekly-review` (Co-work Roadmap §2): activity (cross-session), a
clerk-drafted reflection a person accepts themselves, and person-only overdue
triage (`task_route`) - the pipeline itself is exercised in test_workflows.py
via run_pipeline, against the real standard/pipelines/weekly-review.yaml."""
import pytest

from resource_librarian import clerk, notes, tools  # noqa: F401  (registers tools)
from resource_librarian.registry import REGISTRY, Context

from conftest import add_source


@pytest.fixture
def m(vault):
    class Model:
        def __init__(self, tier="contribute", **extras):
            self.ctx = Context(tier=tier, vault=vault, extras=extras)

        def __call__(self, _tool, **arguments):
            return REGISTRY.call(_tool, arguments, self.ctx)

        def ok(self, _tool, **arguments):
            result = self(_tool, **arguments)
            assert "error" not in result, result
            return result

    return Model()


def test_activity_crosses_every_session_since_a_cutoff(vault):
    add_source(vault.root, "osquery", "Exposes the operating system as a relational database.")
    c1 = Context(tier="contribute", vault=vault)
    REGISTRY.call("create_project", {"name": "P1", "stage": "active", "summary": "s"}, c1)
    REGISTRY.call("open_session", {"purpose": "explore", "question": "q", "project": "P1"}, c1)
    REGISTRY.call("advance", {}, c1)                     # frame -> map
    REGISTRY.call("update_plan", {"fields": {"map": "m"}}, c1)
    REGISTRY.call("advance", {}, c1)                     # map -> need
    REGISTRY.call("advance", {}, c1)                     # need -> search
    used = REGISTRY.call("log_use", {"source": "osquery", "used_for": "testing"}, c1)
    assert "error" not in used

    out = REGISTRY.call("activity", {"since": "-7d"}, Context(tier="consult", vault=vault))
    assert "error" not in out
    assert any(u["source"] == "osquery" and u["project"] == "P1" for u in out["uses"])

    future_cutoff = REGISTRY.call("activity", {"since": "9999-01-01T00:00:00+00:00"},
                                  Context(tier="consult", vault=vault))
    assert future_cutoff["uses"] == []


def test_reflection_draft_is_grounded_in_what_was_passed_and_never_written(m):
    m.ok("create_project", name="Weekly", stage="active", summary="s")

    def answer(payload):
        assert "midterm" in payload["user"]           # the gathered facts reached the prompt
        return {"reflection": "This week: the midterm was scheduled."}

    drafting = Context(tier="contribute", vault=m.ctx.vault,
                       extras={"clerk": clerk.Scripted(answer)})
    out = REGISTRY.call("reflection_draft", {
        "project": "Weekly",
        "agenda_buckets": {"overdue": [], "today": [],
                          "this_week": [{"text": "midterm", "note": "Weekly", "due": "2026-10-01"}]},
        "activity_summary": {"uses": [], "writes": []}}, drafting)
    assert out["ok"] and "midterm" in out["draft"]
    assert notes.load(m.ctx.vault.root / "Projects/Weekly.md").sections()["Reflections"] \
        == "None yet."                                 # nothing written until accepted


def test_reflection_accept_appends_to_reflections_and_is_person_only(m):
    m.ok("create_project", name="Weekly Two", stage="active", summary="s")
    refused = REGISTRY.call("reflection_accept", {"project": "Weekly Two", "text": "a reflection"},
                            Context(tier="contribute", vault=m.ctx.vault))
    assert refused["error"] == "refused" and refused["refused"] == "TIER_REFUSED"
    person = Context(tier="curate", vault=m.ctx.vault)
    out = REGISTRY.call("reflection_accept", {"project": "Weekly Two", "text": "a reflection"},
                        person)
    assert "error" not in out
    assert "a reflection" in notes.load(
        m.ctx.vault.root / "Projects/Weekly Two.md").sections()["Reflections"]


def test_task_route_needs_a_person(m):
    m.ok("create_project", name="Routing", stage="active", summary="s")
    m.ok("task_add", note="Routing", text="Old task", due="2020-01-01")
    refused = REGISTRY.call("task_route", {"note": "Routing", "text": "Old task",
                                           "action": "drop"},
                            Context(tier="contribute", vault=m.ctx.vault))
    assert refused["error"] == "refused" and refused["refused"] == "TIER_REFUSED"


def test_task_route_drop_reschedule_keep(m):
    m.ok("create_project", name="Routing Two", stage="active", summary="s")
    m.ok("task_add", note="Routing Two", text="Task A", due="2020-01-01")
    m.ok("task_add", note="Routing Two", text="Task B", due="2020-01-01")
    m.ok("task_add", note="Routing Two", text="Task C", due="2020-01-01")
    person = Context(tier="curate", vault=m.ctx.vault)

    REGISTRY.call("task_route", {"note": "Routing Two", "text": "Task A", "action": "drop"},
                 person)
    body = notes.load(m.ctx.vault.root / "Projects/Routing Two.md").body
    assert "Task A" not in body and "Task B" in body

    REGISTRY.call("task_route", {"note": "Routing Two", "text": "Task B", "action": "reschedule",
                                "new_due": "2027-01-01"}, person)
    body = notes.load(m.ctx.vault.root / "Projects/Routing Two.md").body
    assert "Task B 📅 2027-01-01" in body

    kept = REGISTRY.call("task_route", {"note": "Routing Two", "text": "Task C", "action": "keep"},
                         person)
    assert kept["action"] == "keep"
    body = notes.load(m.ctx.vault.root / "Projects/Routing Two.md").body
    assert "Task C 📅 2020-01-01" in body


def test_the_weekly_review_pipeline_gathers_and_drafts_end_to_end(m):
    m.ok("create_project", name="Pipeline Pursuit", stage="active", summary="s")
    m.ok("task_add", note="Pipeline Pursuit", text="Overdue thing", due="2020-01-01")

    def answer(payload):
        return {"reflection": "This week: one task is overdue."}

    run_ctx = Context(tier="contribute", vault=m.ctx.vault,
                      extras={"clerk": clerk.Scripted(answer)})
    out = REGISTRY.call("run_pipeline", {"name": "weekly-review",
                                         "inputs": {"project": "Pipeline Pursuit"}}, run_ctx)
    assert out["status"] == "finished", out
    assert "overdue" in out["outputs"]["draft"].lower()
    assert any(t["text"] == "Overdue thing" for t in out["outputs"]["overdue"])
