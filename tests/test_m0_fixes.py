"""What M0 pass 2 (2026-10-01) found the loop needing, fixed without spending anything:
a refused quote shows what to quote instead; a staged guide is not a delivered one; a
research request opened as a learn session is told so."""
from resource_librarian.registry import REGISTRY, Context

from test_review_gate import SUMMARY, to_synthesise
from test_sessions import OSQUERY_LINE, Model, library  # noqa: F401  (fixture)

PARAPHRASE = "Exposes the operating system as a database you can query using SQL."


def test_a_quote_not_found_is_answered_with_the_closest_passage(library):
    m = Model(library)
    to_synthesise(m)
    out = m("draft_offering", title="Host Watch Starter", summary=SUMMARY, claims=[
        {"text": "osquery queries the OS with SQL", "source": "osquery", "quote": PARAPHRASE}])
    assert out["refused"] == "EVIDENCE_QUOTE_VERIFIED"
    assert "closest passage" in out["detail"] and OSQUERY_LINE in out["detail"]
    # copied from the passage offered, it goes through
    assert m.ok("draft_offering", title="Host Watch Starter", summary=SUMMARY, claims=[
        {"text": "osquery queries the OS with SQL", "source": "osquery",
         "quote": OSQUERY_LINE}])["staged"]


def test_a_misnamed_source_is_answered_with_the_closest_names(library):
    m = Model(library)
    to_synthesise(m)
    out = m("draft_offering", title="Host Watch Starter", summary=SUMMARY, claims=[
        {"text": "osquery queries the OS with SQL", "source": "osqurey", "quote": OSQUERY_LINE}])
    assert "no catalogued note is named 'osqurey'" in out["detail"]
    assert "did you mean 'osquery'" in out["detail"]


def test_a_source_staged_but_not_accepted_is_named_as_such(library):
    """M0 pass 3: a draft cited a staged, never-accepted find nine times over."""
    from resource_librarian.staging import StagingStore
    StagingStore(library).add({"id": "mg-scrum", "kind": "source", "status": "staged",
                               "name": "Scrum Explained - Mountain Goat", "history": []})
    m = Model(library)
    to_synthesise(m)
    out = m("draft_offering", title="Host Watch Starter", summary=SUMMARY, claims=[
        {"text": "Scrum has three roles", "source": "Scrum Explained - Mountain Goat",
         "quote": "Scrum has three roles: product owner, scrum master and developers."}])
    assert "is staged in staging, not in the library" in out["detail"]
    nowhere = m("draft_offering", title="Host Watch Starter", summary=SUMMARY, claims=[
        {"text": "x", "source": "Completely Unknown Thing", "quote": OSQUERY_LINE}])
    assert "the sources this session can cite are: 'osquery'" in nowhere["detail"]


def test_a_closest_passage_is_never_a_heading(library):
    m = Model(library)
    to_synthesise(m)
    out = m("draft_offering", title="Host Watch Starter", summary=SUMMARY, claims=[
        {"text": "osquery queries the OS with SQL", "source": "osquery", "quote": PARAPHRASE}])
    assert "## " not in out["detail"] and OSQUERY_LINE in out["detail"]


def test_a_staged_offering_holds_synthesise_until_it_is_promoted(library):
    m = Model(library)
    to_synthesise(m)
    out = m.ok("draft_offering", title="Host Watch Starter", summary=SUMMARY, claims=[
        {"text": "osquery queries the OS with SQL", "source": "osquery", "quote": OSQUERY_LINE}])
    assert out["next"].startswith(f"promote_offering(offering='{out['offering']}')")
    assert any(item.startswith("promote the staged offering")
               for item in out["session"]["open_items"])
    held = m("advance")                                   # not done while it waits in staging
    assert held["moved"] is False and any("promote" in x for x in held["missing"])
    asked = m.ok("promote_offering", offering=out["offering"])     # promotion.mode "person"
    assert asked["needs_person"] and any(item.startswith("promote the staged offering")
                                         for item in asked["session"]["open_items"])
    REGISTRY.call("answer", {"question_id": asked["question_id"], "answer": "yes"},
                  Context(tier="curate", vault=library, session=m.ctx.session))
    promoted = m.ok("promote_offering", offering=out["offering"])
    assert promoted["promoted"] and not any(item.startswith("promote the staged offering")
                                            for item in promoted["session"]["open_items"])


def test_a_research_request_opened_as_learn_is_told_so(library):
    c = Context(tier="contribute", vault=library)
    asked = REGISTRY.call("open_session", {"purpose": "learn", "question":
                                           "find and add sources on Scrum, then a guide"}, c)
    assert "explore" in asked["advisory"]
    studying = REGISTRY.call("open_session", {"purpose": "learn", "question":
                                              "understand Scrum basics for my exam"},
                             Context(tier="contribute", vault=library))
    assert "advisory" not in studying
    research = REGISTRY.call("open_session", {"purpose": "explore", "question":
                                              "find and add sources on Scrum"},
                             Context(tier="contribute", vault=library))
    assert "advisory" not in research


def test_the_search_budget_grows_with_the_topics_asked(library):
    """M0, all three passes: a six-topic request (T1) parked in Search with its briefs open."""
    from resource_librarian import session as sessions
    from resource_librarian.session import SessionStore
    c = Context(tier="contribute", vault=library)
    REGISTRY.call("open_session", {"purpose": "explore", "question": "six topics"}, c)
    store = SessionStore(library)
    store.append(c.session, {"type": "phase", "to": "search"})
    base = sessions.DEFAULT_BUDGETS["search"]

    def with_briefs(n):
        for i in range(len(store.load(c.session).briefs), n):
            store.append(c.session, {"type": "brief", "id": f"B{i + 1}", "need": f"topic {i}",
                                     "disqualifiers": []})
        return store.load(c.session).budget_left()

    assert with_briefs(1) == base                        # one topic: as before
    assert with_briefs(5) == base + 4 * sessions.SEARCH_PER_BRIEF
    assert with_briefs(12) == base + sessions.SEARCH_EXTRA_MAX        # a ceiling
    store.append(c.session, {"type": "effort", "level": 1, "budget_scale": 0.5})
    assert store.load(c.session).budget_left() == round((base + sessions.SEARCH_EXTRA_MAX) * 0.5)


# ---- 2026-10-02: an explore thread on the owner's library (Seed-2.0-mini as lead) ----

def test_a_project_without_a_note_is_settled_in_frame(library):
    m = Model(library)
    m.ok("open_session", purpose="explore", project="BSc Computer Science at UCLan",
         question="sources for my course")
    held = m("advance")
    assert held["moved"] is False
    assert any("create_project(name='BSc Computer Science at UCLan'" in x for x in held["missing"])
    bad = m("update_plan", fields={"project": "Notes/BSc Computer Science at UCLan"})
    assert "a Project is named by its plain name" in bad["detail"]
    assert "'BSc Computer Science at UCLan'" in bad["detail"]
    m.ok("create_project", name="BSc Computer Science at UCLan", stage="active",
         summary="My first year.")
    assert m.ok("advance")["moved"]


def test_opening_a_second_thread_parks_the_first(library):
    from resource_librarian.session import SessionStore
    m = Model(library)
    first = m.ok("open_session", purpose="explore", question="q")["opened"]
    second = m.ok("open_session", purpose="explore", question="q again")
    assert first in second["parked"] and m.ctx.session == second["opened"]
    assert SessionStore(library).load(first).status == "parked"


def test_lists_and_objects_written_as_text_are_read_as_themselves(library):
    m = Model(library)
    m.ok("open_session", purpose="explore", question="q")
    out = m.ok("update_plan", fields="{'question': 'sources for my course'}")
    assert any("object written as text" in a for a in out["adjusted_arguments"])
    from resource_librarian.registry import coerce
    spec = REGISTRY.check("checkpoint", "contribute")
    args, notes = coerce(spec, {"learned": "x", "subthreads": "['a', 'b', 'c']",
                                "next_targets": '["t"]'})
    assert args["subthreads"] == ["a", "b", "c"] and args["next_targets"] == ["t"]
    assert coerce(spec, {"learned": "x", "subthreads": "[not a list"})[0]["subthreads"] == \
        ["[not a list"]


def test_a_checkpoint_naming_too_many_subthreads_keeps_four(library):
    m = Model(library)
    from test_mvp_fixes import to_search
    to_search(m)
    m.ok("research_round", queries=["operating system state database"], brief="B1")
    out = m("checkpoint", learned="x", subthreads=["a", "b", "c", "d", "e", "f"],
            next_targets=["t"], vocabulary=["v"])
    assert "error" not in out and "first 4 are kept" in out.get("note", "")


def test_a_model_call_that_times_out_is_tried_again(monkeypatch):
    """2026-10-02: one DeepInfra read timeout ended the owner's turn."""
    import io
    import urllib.error
    from resource_librarian import providers
    calls, pauses = [], []

    def flaky(request, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.URLError(TimeoutError("The read operation timed out"))
        if len(calls) == 2:
            raise urllib.error.HTTPError(request.full_url, 503, "busy", {}, io.BytesIO(b"{}"))
        return io.BytesIO(b'{"ok": true}')
    monkeypatch.setattr(providers.urllib.request, "urlopen", flaky)
    assert providers._request("POST", "https://example.invalid/v1", {}, {},
                              sleep=pauses.append) == {"ok": True}
    assert pauses == list(providers.TRANSIENT_RETRIES)

    def refused(request, timeout):
        calls.append(1)
        raise urllib.error.URLError(ConnectionRefusedError("refused"))
    calls.clear()
    monkeypatch.setattr(providers.urllib.request, "urlopen", refused)
    import pytest
    with pytest.raises(providers.ProviderError):
        providers._request("GET", "http://127.0.0.1:1/v1", {}, sleep=pauses.append)
    assert len(calls) == 1                    # a server that is not running: no waiting


def test_the_desk_finds_the_project_beside_a_note_of_the_same_name(library):
    m = Model(library)
    m.ok("open_session", purpose="add_project")
    m.ok("create_project", name="Host Watch", stage="planning", summary="Watch our hosts.")
    (library.root / "Notes").mkdir(exist_ok=True)
    (library.root / "Notes" / "Host Watch.md").write_text("# Host Watch\n\nA plain note.\n",
                                                          encoding="utf-8")
    assert "error" not in m("desk_show", project="Host Watch")


def test_a_model_that_never_answers_in_time_is_called_slow_not_unreachable(monkeypatch):
    import urllib.error
    import pytest
    from resource_librarian import providers

    def slow(request, timeout):
        raise urllib.error.URLError(TimeoutError("The read operation timed out"))
    monkeypatch.setattr(providers.urllib.request, "urlopen", slow)
    with pytest.raises(providers.ProviderError, match="did not answer within 120 seconds"):
        providers._request("POST", "https://example.invalid/v1", {}, {}, sleep=lambda s: None)


# ---- 2026-10-03: a thread stuck on a question that had timed out ----

def test_a_question_that_timed_out_no_longer_blocks_the_phase(library):
    from resource_librarian.session import SessionStore
    from resource_librarian.tools.sessions import Waiters
    m = Model(library)
    m.ctx.extras["waiters"] = Waiters(timeout=0.05)
    m.ok("open_session", purpose="explore", question="q")
    out = m("ask_user", question="what must a source not assume?")
    assert out["refused"] == "PERMISSION_UNANSWERED"
    session = SessionStore(library).load(m.ctx.session)
    assert session.status == "parked" and session.open_questions() == []
    assert [q["expired"] for q in session.questions] == [True]


def test_a_timeout_recorded_before_the_fix_also_expires(library):
    from resource_librarian.session import SessionStore
    m = Model(library)
    m.ok("open_session", purpose="explore", question="q")
    store = SessionStore(library)
    store.append(m.ctx.session, {"type": "question", "id": "q1", "question": "x?",
                                 "kind": "disqualifier"})
    store.append(m.ctx.session, {"type": "status", "status": "parked",
                                 "note": "question q1 went unanswered"})
    assert store.load(m.ctx.session).open_questions() == []


def test_a_parked_thread_still_reads(library):
    m = Model(library)
    m.ok("open_session", purpose="explore", question="q")
    m.ok("park_session")
    assert "error" not in m("search", query="osquery")
    assert m("write_note", folder="Notes", name="x", body="y")["refused"] == "SESSION_REQUIRED"


def test_the_person_grants_more_budget_by_answering_the_request(library):
    m = Model(library)
    m.ok("open_session", purpose="explore", question="q")
    before = m.ok("session_status")["budget_left"]
    asked = m.ok("request_budget", reason="The offering still needs drafting.", add=12)
    assert asked["needs_person"] and asked["options"][0] == "Extend by 12 calls"
    REGISTRY.call("answer", {"question_id": asked["question_id"], "answer": "Extend by 12 calls"},
                  Context(tier="curate", vault=library, session=m.ctx.session))
    assert m.ok("session_status")["budget_left"] == before + 12
    no = m.ok("request_budget", reason="Again.")
    REGISTRY.call("answer", {"question_id": no["question_id"], "answer": "Not now"},
                  Context(tier="curate", vault=library, session=m.ctx.session))
    assert m.ok("session_status")["budget_left"] == before + 12
