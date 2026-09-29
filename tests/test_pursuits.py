"""Pursuits (Co-work Roadmap 2A): Project extended with pursuit_kind, started,
horizon, a validated stage, and the Goal/Milestones/Current Focus/Decisions/
Reflections sections - plus task_add/task_done to manage the checkboxes."""
from resource_librarian import notes, tools  # noqa: F401  (registers tools)
from resource_librarian.registry import REGISTRY, Context


def ctx(vault, tier="contribute"):
    return Context(tier=tier, vault=vault)


def test_create_project_defaults_pursuit_kind_and_writes_new_sections(vault):
    out = REGISTRY.call("create_project", {"name": "Host Watch", "stage": "idea",
                                           "summary": "Watch our hosts."}, ctx(vault))
    assert out["created"] == "Projects/Host Watch.md"
    note = notes.load(vault.root / out["created"])
    assert note.frontmatter["pursuit_kind"] == "project"          # the back-compat default
    assert note.frontmatter["stage"] == "idea"
    sections = note.sections()
    assert sections["Goal"] == "Not yet stated."
    assert sections["Milestones"] == "None yet."
    assert sections["Current Focus"] == "Not yet started."
    assert sections["Decisions"] == "None recorded."
    assert sections["Reflections"] == "None yet."


def test_create_project_takes_pursuit_kind_started_horizon_and_goal(vault):
    out = REGISTRY.call("create_project", {"name": "CS 101", "stage": "planning",
                                           "summary": "A first course on algorithms.",
                                           "pursuit_kind": "course", "started": "2026-09-01",
                                           "horizon": "end of semester",
                                           "goal": "Pass with a solid grasp of complexity."},
                        ctx(vault))
    note = notes.load(vault.root / out["created"])
    assert note.frontmatter["pursuit_kind"] == "course"
    assert note.frontmatter["started"] == "2026-09-01"
    assert note.frontmatter["horizon"] == "end of semester"
    assert note.sections()["Goal"] == "Pass with a solid grasp of complexity."


def test_create_project_refuses_an_unknown_pursuit_kind_or_stage(vault):
    bad_kind = REGISTRY.call("create_project", {"name": "X", "stage": "idea", "summary": "s",
                                                "pursuit_kind": "hobby"}, ctx(vault))
    assert bad_kind["error"] == "invalid_arguments" and "pursuit_kind" in bad_kind["detail"]
    bad_stage = REGISTRY.call("create_project", {"name": "Y", "stage": "brewing", "summary": "s"},
                              ctx(vault))
    assert bad_stage["error"] == "invalid_arguments" and "stage" in bad_stage["detail"]
    assert not (vault.root / "Projects" / "X.md").exists()
    assert not (vault.root / "Projects" / "Y.md").exists()


def test_task_add_appends_a_dated_checkbox_to_milestones(vault):
    REGISTRY.call("create_project", {"name": "Host Watch", "stage": "active",
                                     "summary": "Watch our hosts."}, ctx(vault))
    out = REGISTRY.call("task_add", {"note": "Host Watch", "text": "Ship the first dashboard",
                                     "due": "2026-10-01"}, ctx(vault))
    assert out["task"] == "- [ ] Ship the first dashboard \U0001F4C5 2026-10-01"
    note = notes.load(vault.root / "Projects" / "Host Watch.md")
    assert out["task"] in note.sections()["Milestones"]
    assert note.sections()["Goal"] == "Not yet stated."                # untouched

    second = REGISTRY.call("task_add", {"note": "Host Watch", "text": "Add alerting"}, ctx(vault))
    assert second["task"] == "- [ ] Add alerting"
    milestones = notes.load(vault.root / "Projects" / "Host Watch.md").sections()["Milestones"]
    assert "Ship the first dashboard" in milestones and "Add alerting" in milestones


def test_task_add_validates_the_due_date_and_the_note(vault):
    REGISTRY.call("create_project", {"name": "Host Watch", "stage": "active",
                                     "summary": "s"}, ctx(vault))
    bad_date = REGISTRY.call("task_add", {"note": "Host Watch", "text": "x", "due": "next week"},
                             ctx(vault))
    assert bad_date["error"] == "invalid_arguments" and "YYYY-MM-DD" in bad_date["detail"]
    no_text = REGISTRY.call("task_add", {"note": "Host Watch", "text": "  "}, ctx(vault))
    assert no_text["error"] == "invalid_arguments"
    unknown = REGISTRY.call("task_add", {"note": "Nope", "text": "x"}, ctx(vault))
    assert unknown["error"] == "invalid_arguments" and "no note named" in unknown["detail"]


def test_task_done_checks_off_a_matching_open_task(vault):
    REGISTRY.call("create_project", {"name": "Host Watch", "stage": "active",
                                     "summary": "s"}, ctx(vault))
    REGISTRY.call("task_add", {"note": "Host Watch", "text": "Ship the first dashboard",
                               "due": "2026-10-01"}, ctx(vault))
    REGISTRY.call("task_add", {"note": "Host Watch", "text": "Add alerting"}, ctx(vault))
    out = REGISTRY.call("task_done", {"note": "Host Watch", "text": "Ship the first dashboard"},
                        ctx(vault))
    assert out["done"] == "Ship the first dashboard"
    milestones = notes.load(vault.root / "Projects" / "Host Watch.md").sections()["Milestones"]
    assert "- [x] Ship the first dashboard \U0001F4C5 2026-10-01" in milestones
    assert "- [ ] Add alerting" in milestones                  # the other task is untouched


def test_task_done_refuses_when_nothing_matches(vault):
    REGISTRY.call("create_project", {"name": "Host Watch", "stage": "active",
                                     "summary": "s"}, ctx(vault))
    REGISTRY.call("task_add", {"note": "Host Watch", "text": "Ship the first dashboard"},
                 ctx(vault))
    missing = REGISTRY.call("task_done", {"note": "Host Watch", "text": "Nope"}, ctx(vault))
    assert missing["error"] == "invalid_arguments" and "no open task" in missing["detail"]
    REGISTRY.call("task_done", {"note": "Host Watch", "text": "Ship the first dashboard"},
                 ctx(vault))
    already = REGISTRY.call("task_done", {"note": "Host Watch", "text": "Ship the first dashboard"},
                            ctx(vault))
    assert already["error"] == "invalid_arguments" and "no open task" in already["detail"]
