"""The Desk (Co-work Roadmap 2B): a persisted, per-pursuit working set -
pinned notes, then automatically-ranked recent ones from a pursuit's own
sessions and from touches recorded directly (a pane open, say)."""
from resource_librarian import desk, tools  # noqa: F401  (registers tools)
from resource_librarian.registry import REGISTRY, Context

from conftest import add_source


def ctx(vault, tier="contribute"):
    return Context(tier=tier, vault=vault)


def _pursuit(vault, name="Host Watch"):
    REGISTRY.call("create_project", {"name": name, "stage": "active", "summary": "s"}, ctx(vault))
    return name


def _to_search_phase(vault, c, project: str) -> None:
    opened = REGISTRY.call("open_session", {"purpose": "explore", "question": "q",
                                            "project": project}, c)
    c.session = opened["opened"]
    REGISTRY.call("advance", {}, c)                                    # frame -> map
    REGISTRY.call("update_plan", {"fields": {"map": "x"}}, c)
    REGISTRY.call("advance", {}, c)                                    # map -> need
    REGISTRY.call("advance", {}, c)                                    # need -> search


def test_desk_pin_shows_up_first_and_never_decays(vault):
    add_source(vault.root, "Alpha", "Alpha parses SQL into lineage graphs.")
    project = _pursuit(vault)
    out = REGISTRY.call("desk_pin", {"project": project, "note": "Alpha"}, ctx(vault))
    assert out == {"project": project, "note": "Alpha"}
    shown = REGISTRY.call("desk_show", {"project": project}, ctx(vault))
    assert shown["project"] == project
    row = shown["working_set"][0]
    assert row["note"] == "Alpha" and row["pinned"] is True and row["why"] == "pinned"


def test_desk_pin_refuses_an_unknown_note_or_pursuit(vault):
    project = _pursuit(vault)
    bad_note = REGISTRY.call("desk_pin", {"project": project, "note": "Nope"}, ctx(vault))
    assert bad_note["error"] == "invalid_arguments" and "no note named" in bad_note["detail"]
    add_source(vault.root, "Alpha", "x")
    bad_project = REGISTRY.call("desk_pin", {"project": "Nope", "note": "Alpha"}, ctx(vault))
    assert bad_project["error"] == "invalid_arguments" and "no pursuit named" in bad_project["detail"]


def test_desk_unpin_stops_it_decaying_but_leaves_it_on_the_desk(vault):
    add_source(vault.root, "Alpha", "x")
    project = _pursuit(vault)
    REGISTRY.call("desk_pin", {"project": project, "note": "Alpha"}, ctx(vault))
    out = REGISTRY.call("desk_unpin", {"project": project, "note": "Alpha"}, ctx(vault))
    assert out == {"project": project, "note": "Alpha", "unpinned": True}
    row = REGISTRY.call("desk_show", {"project": project}, ctx(vault))["working_set"][0]
    assert row["pinned"] is False
    again = REGISTRY.call("desk_unpin", {"project": project, "note": "Alpha"}, ctx(vault))
    assert again["unpinned"] is False                        # already unpinned


def test_desk_touch_ranks_the_most_recently_touched_first(vault):
    add_source(vault.root, "Alpha", "x")
    add_source(vault.root, "Beta", "y")
    project = _pursuit(vault)
    REGISTRY.call("desk_touch", {"project": project, "note": "Alpha"}, ctx(vault))
    REGISTRY.call("desk_touch", {"project": project, "note": "Beta"}, ctx(vault))
    REGISTRY.call("desk_touch", {"project": project, "note": "Alpha"}, ctx(vault))
    shown = REGISTRY.call("desk_show", {"project": project}, ctx(vault))["working_set"]
    assert [r["note"] for r in shown] == ["Alpha", "Beta"]
    alpha = shown[0]
    assert alpha["touches"] == 2 and alpha["why"] == "opened" and alpha["pinned"] is False


def test_desk_touch_refuses_an_unknown_note_or_pursuit(vault):
    project = _pursuit(vault)
    add_source(vault.root, "Alpha", "x")
    assert REGISTRY.call("desk_touch", {"project": "Nope", "note": "Alpha"},
                        ctx(vault))["error"] == "invalid_arguments"
    assert REGISTRY.call("desk_touch", {"project": project, "note": "Nope"},
                        ctx(vault))["error"] == "invalid_arguments"


def test_desk_show_limits_the_working_set(vault):
    project = _pursuit(vault)
    for i in range(5):
        add_source(vault.root, f"Note {i}", "x")
        REGISTRY.call("desk_touch", {"project": project, "note": f"Note {i}"}, ctx(vault))
    shown = REGISTRY.call("desk_show", {"project": project, "limit": 2}, ctx(vault))
    assert len(shown["working_set"]) == 2


def test_desk_show_picks_up_a_pursuits_own_session_uses_and_writes(vault):
    add_source(vault.root, "Alpha", "x")
    project = "Host Watch"
    framing = ctx(vault)
    opened = REGISTRY.call("open_session", {"purpose": "add_project", "question": "q"}, framing)
    framing.session = opened["opened"]
    REGISTRY.call("create_project", {"name": project, "stage": "active", "summary": "s"}, framing)

    researching = ctx(vault)
    _to_search_phase(vault, researching, project)
    REGISTRY.call("log_use", {"source": "Alpha", "used_for": "reading"}, researching)

    shown = REGISTRY.call("desk_show", {"project": project}, ctx(vault))["working_set"]
    names = {r["note"]: r for r in shown}
    assert names["Alpha"]["why"] == "used"
    assert names["Host Watch"]["why"] == "written"             # create_project's own write event,
                                                                # from a *different* session on
                                                                # the same pursuit


def test_desk_show_never_mixes_a_different_pursuits_sessions_in(vault):
    add_source(vault.root, "Alpha", "x")
    a = _pursuit(vault, "Host Watch")
    b = _pursuit(vault, "Other Pursuit")
    c = ctx(vault)
    _to_search_phase(vault, c, a)
    REGISTRY.call("log_use", {"source": "Alpha", "used_for": "reading"}, c)
    other = REGISTRY.call("desk_show", {"project": b}, ctx(vault))["working_set"]
    assert not any(r["note"] == "Alpha" for r in other)


def test_score_decays_with_age_and_never_for_a_pin():
    from resource_librarian.vault import now_iso
    assert desk._score(now_iso()) > 0.9
    old = "2000-01-01T00:00:00+00:00"
    assert desk._score(old) < 0.0001


def test_age_days_is_defensive_about_bad_timestamps():
    assert desk._age_days("not a timestamp") == 999.0
    assert desk._age_days("") == 999.0
