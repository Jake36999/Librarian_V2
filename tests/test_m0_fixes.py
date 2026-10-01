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
