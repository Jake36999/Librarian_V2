"""Regressions for the 2026-09-27 review's P0 findings (`internal docs/Review -
Co-work Roadmap and Lens Methodology 2026-09-27.md`, Part 1.4): each test
reproduces a bug the review found, and fails on the code as it was."""
from datetime import date, timedelta

import pytest

from resource_librarian import agenda, desk, mcp_client, notes, tools  # noqa: F401
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.rules import Refusal

from conftest import write_note


def call(vault, _tool, tier="contribute", ctx=None, **arguments):
    ctx = ctx or Context(tier=tier, vault=vault)
    return REGISTRY.call(_tool, arguments, ctx), ctx


# ------------------------------------------------------ project names are paths

def test_a_project_name_cannot_walk_out_of_the_vault(vault, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("## Current Focus\nuntouched\n", encoding="utf-8")
    opened, _ = call(vault, "open_session", tier="consult", purpose="apply",
                     project="../../outside")
    assert opened["refused"] == "VAULT_REQUIRED"
    planned, _ = call(vault, "open_session", purpose="explore", question="q")
    ctx = _
    bad, _ = call(vault, "update_plan", ctx=ctx, fields={"project": "../../outside"})
    assert bad["refused"] == "VAULT_REQUIRED"
    assert outside.read_text(encoding="utf-8") == "## Current Focus\nuntouched\n"


def test_project_note_refuses_anything_but_a_plain_name(vault):
    assert vault.project_note("Host Watch").name == "Host Watch.md"
    for bad in ("../x", "a/b", "a\\b", ".hidden", "", "  "):
        with pytest.raises(Refusal):
            vault.project_note(bad)


# ------------------------------------------------------------- section writes

def test_with_section_keeps_a_repeated_heading_and_fenced_code():
    body = ("# T\n\n## Notes\nfirst\n\n```md\n## not a heading\n```\n\n"
            "## Milestones\n- [ ] a\n\n## Notes\nsecond\n")
    out = notes.with_section(body, "Milestones", "- [ ] a\n- [ ] b")
    assert "first" in out and "second" in out                  # neither Notes is lost
    assert "```md\n## not a heading\n```" in out               # the fence is untouched
    assert out.count("## Notes") == 2
    assert "- [ ] a\n- [ ] b" in out


def test_with_section_changes_nothing_else():
    body = "# T\n\nIntro text.\n\n## A\nalpha\n\n\n## B\nbeta  \n"
    out = notes.with_section(body, "A", "ALPHA")
    assert out == "# T\n\nIntro text.\n\n## A\nALPHA\n\n## B\nbeta  \n"


def test_split_sections_joins_a_repeated_heading_instead_of_dropping_one():
    sections = notes.split_sections("## N\none\n## N\ntwo\n")
    assert sections["N"] == "one\n\ntwo"


def test_task_text_cannot_open_a_section_or_fake_a_date(vault):
    call(vault, "create_project", name="P", stage="active", summary="s")
    out, _ = call(vault, "task_add", note="P", text="real\n## Injected\n- [ ] fake")
    assert out["task"] == "- [ ] real ## Injected - [ ] fake"      # one line, whatever it says
    assert "\n## Injected" not in notes.load(vault.project_note("P")).body
    assert call(vault, "task_add", note="P", text="# heading")[0].get("error")
    assert call(vault, "task_add", note="P", text="sneaky 📅 2020-01-01")[0].get("error")


# ------------------------------------------------------------------ the agenda

def test_the_agenda_reads_what_obsidian_tasks_reads(vault):
    today = date.today()
    soon = (today + timedelta(days=2)).isoformat()
    write_note(vault.root, "Projects/Tasks.md", "type: project\nstatus: active\nstage: active",
               "## Milestones\n"
               f"- [ ] plain 📅 {soon}\n"
               f"  - [ ] indented subtask 📅 {soon}\n"
               f"* [ ] star bullet 📅 {soon}\n"
               f"- [ ] with signifiers 📅 {soon} ⏫ 🔁 every week\n"
               f"- [/] in progress 📅 {soon}\n"
               f"- [x] done 📅 {soon}\n"
               "```\n- [ ] inside a fence 📅 2020-01-01\n```\n")
    out = agenda.scan(vault, today=today)
    texts = sorted(t["text"] for t in out["this_week"])
    assert texts == ["in progress", "indented subtask", "plain", "star bullet",
                     "with signifiers"]
    assert not out["overdue"]                                  # the fenced one is code


def test_anything_on_the_agenda_can_be_checked_off_and_rescheduled(vault):
    soon = (date.today() + timedelta(days=2)).isoformat()
    write_note(vault.root, "Projects/T2.md", "type: project\nstatus: active\nstage: active",
               f"## Milestones\n  - [ ] ship it 📅 {soon} ⏫ 🔁 every week\n- [ ] other\n")
    ctx = Context(tier="curate", vault=vault)
    call(vault, "task_route", ctx=ctx, note="T2", text="ship it", action="reschedule",
         new_due="2030-01-01")
    body = notes.load(vault.project_note("T2")).body
    assert "  - [ ] ship it 📅 2030-01-01 ⏫ 🔁 every week" in body   # only the date moved
    done, _ = call(vault, "task_done", note="T2", text="ship it")
    assert "error" not in done, done
    assert "  - [x] ship it 📅 2030-01-01 ⏫ 🔁 every week" in \
        notes.load(vault.project_note("T2")).body


def test_activity_refuses_a_since_it_cannot_read(vault):
    assert "error" not in call(vault, "activity", since="-1w")[0]
    assert "error" not in call(vault, "activity", since="2026-09-01")[0]
    assert call(vault, "activity", since="last week")[0].get("error")


# ---------------------------------------------------------------- phase exits

@pytest.fixture
def learner(vault):
    write_note(vault.root, "Concepts/Query Planning.md",
               "type: concept\nconcept_kind: pattern\nstatus: active",
               "## Definition\nHow a database orders joins.\n")
    ctx = Context(tier="contribute", vault=vault)

    def m(_tool, **arguments):
        return REGISTRY.call(_tool, arguments, ctx)
    m("open_session", purpose="learn", question="q")
    m("update_plan", fields={"goal": "g"})
    m("advance")
    m("update_plan", fields={"baseline": "b"})
    m("advance")
    return m


def test_a_spent_budget_is_not_practice(learner):
    learner("update_plan", fields={"focus": "Query Planning"})      # a string, not a list
    assert learner("advance")["moved"] == "practice"
    for _ in range(40):                                             # burn the whole budget
        learner("index_status")
    status = learner("session_status")
    assert status["budget_left"] == 0
    assert any("Query Planning" in item for item in status["open_items"])
    assert learner("advance")["moved"] is False                     # still not practised
    assert "complete" not in status["next"]


def test_focus_is_a_list_and_never_empty(learner):
    assert learner("update_plan", fields={"focus": []}).get("error")
    learner("update_plan", fields={"focus": "Query Planning, Indexing"})
    assert learner("session_status")["plan"]["focus"] == ["Query Planning", "Indexing"]


def test_going_back_and_forth_does_not_reset_a_budget(learner):
    learner("update_plan", fields={"focus": ["Query Planning"]})
    full = learner("session_status")["budget_left"]
    learner("advance", target="baseline")
    learner("advance")
    assert learner("session_status")["budget_left"] == full // 2


def test_advancing_to_the_current_phase_stays_put(learner):
    learner("update_plan", fields={"focus": ["Query Planning"]})
    out = learner("advance", target="focus")
    assert out["moved"] is False and learner("session_status")["phase"] == "focus"


# ----------------------------------------------------------------------- MCP

def test_an_unpinned_launcher_is_named():
    assert mcp_client.unpinned({"command": "uvx", "args": ["s2-mcp-server"]})
    assert not mcp_client.unpinned({"command": "uvx", "args": ["s2-mcp-server==1.7.4"]})
    assert mcp_client.unpinned({"command": "npx", "args": ["-y", "@scope/server"]})
    assert not mcp_client.unpinned({"command": "npx", "args": ["-y", "@scope/server@2.0.1"]})
    assert not mcp_client.unpinned({"command": "python", "args": ["-m", "server"]})


def test_secret_looking_args_are_never_shown_back():
    shown = mcp_client.redacted_args(["--api-key", "abc123", "--token=xyz", "sk-live-0123456789",
                                      "--verbose", "path/to/thing"])
    assert shown == ["--api-key", "••••", "--token=••••", "••••", "--verbose", "path/to/thing"]


def test_a_secret_inside_a_longer_argument_is_masked_too():
    # Raised by a model review of the P0 patch, and confirmed (G1's labelled set).
    shown = mcp_client.redacted_args(["--config", '{"apiKey":"sk-1234567890abcdef"}',
                                      "--config", '{"api_key": "plain123", "keyboard": "us"}',
                                      "https://host/?token=abc123&x=1"])
    assert shown == ["--config", '{"apiKey":"••••"}', "--config",
                     '{"api_key": "••••", "keyboard": "us"}', "https://host/?token=••••&x=1"]


def test_a_flag_is_secret_only_when_a_whole_part_of_its_name_is():
    shown = mcp_client.redacted_args(["--keyboard-layout", "us", "--author", "me",
                                      "--apikey", "w", "--github-token", "q"])
    assert shown == ["--keyboard-layout", "us", "--author", "me", "--apikey", "••••",
                     "--github-token", "••••"]


# ---------------------------------------------------------------------- desk

def test_the_desk_weighs_how_often_as_well_as_how_recently(vault, monkeypatch):
    store = desk.DeskStore(vault)
    for _ in range(20):
        store.touch("P", "Often")
    store.touch("P", "Once")
    ages = {"Often": 2.0, "Once": 1.0}
    rows = {r["note"]: r for r in store._rows("P")}
    monkeypatch.setattr(desk, "_age_days", lambda t: ages[next(
        n for n, r in rows.items() if r["last_touched"] == t)])
    ranked = [e["note"] for e in store.working_set("P")]
    assert ranked.index("Often") < ranked.index("Once")


def test_custom_statuses_stay_open_and_only_done_or_cancelled_close(vault):
    soon = (date.today() + timedelta(days=1)).isoformat()
    write_note(vault.root, "Projects/S.md", "type: project\nstatus: active\nstage: active",
               f"## Milestones\n- [>] deferred 📅 {soon}\n- [?] question 📅 {soon}\n"
               f"- [-] cancelled 📅 {soon}\n- [X] done 📅 {soon}\n")
    texts = sorted(t["text"] for t in agenda.scan(vault)["this_week"])
    assert texts == ["deferred", "question"]


def test_dropping_a_task_from_a_crlf_note_leaves_no_stray_carriage_return(vault):
    path = vault.root / "Projects" / "C.md"
    path.write_bytes(b"---\r\ntype: project\r\nstatus: active\r\nstage: active\r\n---\r\n\r\n"
                     b"## Milestones\r\n- [ ] keep\r\n- [ ] drop me\r\n- [ ] also keep\r\n")
    call(vault, "task_route", ctx=Context(tier="curate", vault=vault), note="C",
         text="drop me", action="drop")
    raw = path.read_bytes()
    assert b"drop me" not in raw and b"\r\r" not in raw
    assert b"keep" in raw and b"also keep" in raw


def test_a_tilde_line_inside_a_backtick_fence_is_still_code():
    body = "## A\n```\n~~~\n## not a heading\n```\n## B\nb\n"
    assert list(notes.split_sections(body)) == ["", "A", "B"]


# ------------------------------------------------ roadmap §4 A (2026-09-28)

def test_a_kind_the_model_does_not_declare_is_refused_even_with_no_kinds(vault):
    """A1: an empty Source Kinds table no longer means "any kind" - the kind
    becomes a folder name, so an unchecked one could walk out of Sources/."""
    from resource_librarian import promote
    from resource_librarian.index import Index
    from resource_librarian.search import Engine
    draft = promote.Draft(name="x", kind="../../escape", title="x",
                          canonical_url="https://example.org", bottom_line="b",
                          what_it_solves="w")
    with pytest.raises(TypeError):
        promote.promote(vault, Engine(Index(vault)), draft)
    model = vault.root / "About" / "Note Content Model.md"
    text = model.read_text(encoding="utf-8")
    start = text.index("## Source Kinds")
    model.write_text(text[:start] + text[text.index("\n## ", start + 5):], encoding="utf-8")
    with pytest.raises(TypeError, match="declares no source kinds"):
        promote.promote(vault, Engine(Index(vault)), promote.Draft(
            name="y", kind="repository", title="y", canonical_url="https://example.org",
            bottom_line="b", what_it_solves="w"))


def test_doctor_names_an_older_model_missing_the_deep_read_sections(vault):
    """A5: without Claims / Evidence & Limits a deep read silently files into
    Reading Notes - doctor now says so."""
    from resource_librarian import doctor
    assert not [c for c in doctor.checks(vault) if c.name == "content model: deep-read sections"]
    model = vault.root / "About" / "Note Content Model.md"
    text = model.read_text(encoding="utf-8")
    model.write_text(text.replace("| Claims |", "| Old Claims |"), encoding="utf-8")
    found = [c for c in doctor.checks(vault) if c.name == "content model: deep-read sections"]
    assert found and not found[0].ok and "Claims" in found[0].detail


def test_a_pursuits_agenda_and_activity_are_its_own(vault):
    """A2: the weekly review is per pursuit - its agenda and activity too."""
    soon = (date.today() + timedelta(days=1)).isoformat()
    call(vault, "create_project", name="Mine", stage="active", summary="s")
    call(vault, "create_project", name="Other", stage="active", summary="s")
    call(vault, "task_add", note="Mine", text="my task", due=soon)
    call(vault, "task_add", note="Other", text="their task", due=soon)
    mine = call(vault, "agenda", project="Mine")[0]
    assert [t["text"] for t in mine["this_week"]] == ["my task"]
    assert len(call(vault, "agenda")[0]["this_week"]) == 2           # unscoped: the vault
    _, ctx = call(vault, "open_session", purpose="explore", question="q", project="Other")
    call(vault, "search", ctx=ctx, query="anything")
    assert not call(vault, "activity", project="Mine")[0]["uses"] or all(
        u["project"] == "Mine" for u in call(vault, "activity", project="Mine")[0]["uses"])


def test_consolidation_needs_an_understanding_recorded_in_that_phase(learner):
    """A3: `consolidated` is no longer believed on the model's word."""
    learner("update_plan", fields={"focus": ["Query Planning"]})
    learner("advance")                                            # -> practice
    learner("understanding_record", concept="Query Planning", own_words="joins by cost",
            confidence="ok")
    assert learner("advance")["moved"] == "consolidate"
    learner("update_plan", fields={"consolidated": True})
    assert learner("advance")["moved"] is False                   # flag alone is not enough
    learner("understanding_record", concept="Query Planning",
            own_words="the planner costs each join order", confidence="solid")
    assert learner("advance")["moved"] == "next"
    learner("update_plan", fields={"scheduled": True})
    assert learner("advance")["moved"] is False or \
        learner("session_status")["phase"] == "next"              # no Review: task yet
    assert any("Review:" in m for m in learner("session_status")["open_items"])
