"""W1 `start_pursuit` (Co-work Roadmap §2): frame -> inventory -> plan -> seed
-> check_out, walked exactly as a surface would, through the registry."""
import pytest

from resource_librarian import notes, tools  # noqa: F401  (registers tools)
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

    return Model()


def test_walks_frame_to_check_out(m, vault):
    opened = m.ok("open_session", purpose="start_pursuit", project="Databases Course")
    assert opened["phases"] == ["frame", "inventory", "plan", "seed", "check_out"]

    assert m.ok("advance")["moved"] is False                 # no project note yet
    m.ok("create_project", name="Databases Course", stage="planning", summary="A semester.",
        pursuit_kind="course", started="2026-09", horizon="2026-12",
        goal="Pass with a strong grasp of query planning.")
    assert m.ok("advance")["moved"] == "inventory"

    assert m.ok("advance")["moved"] is False                 # no inventory recorded yet
    m.ok("update_plan", fields={"inventory": "3 modules, a midterm and a final, one text"})
    m.ok("record_assumptions", assumptions=[])
    assert m.ok("advance")["moved"] == "plan"

    missing = m.ok("advance")
    assert missing["moved"] is False and "dated milestone" in missing["missing"][0]
    m.ok("task_add", note="Databases Course", text="Midterm", due="2026-10-15")
    assert m.ok("advance")["moved"] == "seed"

    assert m.ok("advance")["moved"] is False
    m.ok("queue_source", ref="https://example.org/query-planning", note="assigned reading")
    m.ok("update_plan", fields={"ingested": "queued the assigned reading"})
    assert m.ok("advance")["moved"] == "check_out"

    closed = m.ok("close_session", summary="Framed the course, midterm dated, reading queued.",
                  gaps="none yet")
    assert closed["closed"]
    focus = notes.load(vault.root / "Projects" / "Databases Course.md").sections()["Current Focus"]
    assert focus == "Framed the course, midterm dated, reading queued."


def test_plan_accepts_no_dates_as_an_alternative(m):
    m.ok("open_session", purpose="start_pursuit", project="Open Ended Research")
    m.ok("create_project", name="Open Ended Research", stage="idea", summary="TBD.",
        pursuit_kind="research")
    m.ok("advance")
    m.ok("update_plan", fields={"inventory": "no fixed structure yet"})
    m.ok("record_assumptions", assumptions=[])
    m.ok("advance")
    m.ok("update_plan", fields={"no_dates": "nothing is dated yet, still scoping"})
    assert m.ok("advance")["moved"] == "seed"


def test_capture_is_allowed_in_any_phase(m):
    # Requirements Addendum R12 (2026-09-30) reversed the old seed-only gate: capture is
    # allowed anywhere; only a fit claim needs a framed need.
    m.ok("open_session", purpose="start_pursuit", project="A Job")
    out = m.ok("ingest", ref="https://example.org/x", defer=True)
    assert out["state"] == "queued" and m.ok("session_status")["phase"] == "frame"
