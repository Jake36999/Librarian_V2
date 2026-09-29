"""The agenda (Co-work Roadmap 2C): every open, dated task across the vault,
bucketed by when it falls, scanned fresh from checkboxes - no store of its
own, so a task typed straight into Obsidian counts the same as task_add's."""
from datetime import date, timedelta

from resource_librarian import agenda, notes, tools  # noqa: F401  (registers tools)
from resource_librarian.registry import REGISTRY, Context

from conftest import write_note


def ctx(vault, tier="contribute"):
    return Context(tier=tier, vault=vault)


def _pursuit(vault, name="Host Watch"):
    REGISTRY.call("create_project", {"name": name, "stage": "active", "summary": "s"}, ctx(vault))
    return name


def test_buckets_by_due_date_relative_to_today(vault):
    project = _pursuit(vault)
    today = date.today()
    due = {
        "overdue": today - timedelta(days=2),
        "today": today,
        "this_week": today + timedelta(days=3),
        "later": today + timedelta(days=30),
    }
    for bucket, when in due.items():
        REGISTRY.call("task_add", {"note": project, "text": bucket, "due": when.isoformat()},
                     ctx(vault))
    REGISTRY.call("task_add", {"note": project, "text": "no date at all"}, ctx(vault))

    out = REGISTRY.call("agenda", {}, ctx(vault))
    assert [t["text"] for t in out["overdue"]] == ["overdue"]
    assert [t["text"] for t in out["today"]] == ["today"]
    assert [t["text"] for t in out["this_week"]] == ["this_week"]
    assert [t["text"] for t in out["later"]] == ["later"]
    assert [t["text"] for t in out["undated"]] == ["no date at all"]
    assert out["overdue"][0]["note"] == project
    assert out["overdue"][0]["path"] == "Projects/Host Watch.md"


def test_the_boundary_of_this_week_is_inclusive_of_six_days_out(vault):
    project = _pursuit(vault)
    today = date.today()
    REGISTRY.call("task_add", {"note": project, "text": "day six",
                               "due": (today + timedelta(days=6)).isoformat()}, ctx(vault))
    REGISTRY.call("task_add", {"note": project, "text": "day seven",
                               "due": (today + timedelta(days=7)).isoformat()}, ctx(vault))
    out = REGISTRY.call("agenda", {}, ctx(vault))
    assert [t["text"] for t in out["this_week"]] == ["day six"]
    assert [t["text"] for t in out["later"]] == ["day seven"]


def test_a_checked_task_never_appears(vault):
    project = _pursuit(vault)
    REGISTRY.call("task_add", {"note": project, "text": "finish this",
                               "due": date.today().isoformat()}, ctx(vault))
    REGISTRY.call("task_done", {"note": project, "text": "finish this"}, ctx(vault))
    out = REGISTRY.call("agenda", {}, ctx(vault))
    assert all(not b for b in out.values())


def test_a_bad_date_is_treated_as_undated_rather_than_dropped(vault):
    write_note(vault.root, "Projects/Freeform.md", "type: project\nstatus: active\n"
              "stage: active\npursuit_kind: project",
              notes.compose("Freeform", [("Milestones", "- [ ] not a real date 📅 2026-02-30")]))
    out = REGISTRY.call("agenda", {}, ctx(vault))
    assert [t["text"] for t in out["undated"]] == ["not a real date"]


def test_a_hand_written_checkbox_counts_the_same_as_task_add(vault):
    write_note(vault.root, "Projects/Freeform.md", "type: project\nstatus: active\n"
              "stage: active\npursuit_kind: project",
              notes.compose("Freeform", [("Milestones", "- [ ] typed straight into Obsidian "
                                        "\U0001F4C5 2026-01-01\n- [x] already done \U0001F4C5 2026-01-01")]))
    out = REGISTRY.call("agenda", {}, ctx(vault))
    all_tasks = [t for tasks in out.values() for t in tasks]
    assert [t["text"] for t in all_tasks] == ["typed straight into Obsidian"]


def test_multiple_notes_are_all_scanned(vault):
    a = _pursuit(vault, "Host Watch")
    b = _pursuit(vault, "Other Pursuit")
    today = date.today()
    REGISTRY.call("task_add", {"note": a, "text": "from a", "due": today.isoformat()}, ctx(vault))
    REGISTRY.call("task_add", {"note": b, "text": "from b", "due": today.isoformat()}, ctx(vault))
    out = REGISTRY.call("agenda", {}, ctx(vault))
    assert {t["text"] for t in out["today"]} == {"from a", "from b"}


def test_scan_sorts_each_bucket_by_due_date(vault):
    project = _pursuit(vault)
    today = date.today()
    REGISTRY.call("task_add", {"note": project, "text": "later one",
                               "due": (today + timedelta(days=5)).isoformat()}, ctx(vault))
    REGISTRY.call("task_add", {"note": project, "text": "sooner one",
                               "due": (today + timedelta(days=1)).isoformat()}, ctx(vault))
    out = REGISTRY.call("agenda", {}, ctx(vault))
    assert [t["text"] for t in out["this_week"]] == ["sooner one", "later one"]


def test_scan_function_accepts_an_explicit_today(vault):
    project = _pursuit(vault)
    fixed = date(2026, 6, 15)
    REGISTRY.call("task_add", {"note": project, "text": "x", "due": "2026-06-10"}, ctx(vault))
    out = agenda.scan(vault, today=fixed)
    assert [t["text"] for t in out["overdue"]] == ["x"]
