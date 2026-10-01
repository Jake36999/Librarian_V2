"""Staging -> Offerings (Test Report A2 b): a person reads a staged offering before
deciding on it, and decides from there - answering the session's own question when it
asked one, and still able to when the session has moved on or closed."""
import json
import threading
import urllib.request

import pytest

from resource_librarian.app import App, build
from resource_librarian.keys import KeyStore
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.session import SessionStore
from resource_librarian.tools.sessions import (decide_offering, staged_offering,
                                               staged_offerings)

from test_review_gate import SUMMARY, to_synthesise
from test_sessions import OSQUERY_LINE, Model, library  # noqa: F401  (fixture)


def drafted(library):
    m = Model(library)
    to_synthesise(m)
    out = m.ok("draft_offering", title="Host Watch Starter", summary=SUMMARY, claims=[
        {"text": "osquery queries the OS with SQL", "source": "osquery", "quote": OSQUERY_LINE}])
    return m, out["offering"]


def person(library):
    return Context(tier="curate", vault=library)


def test_a_staged_draft_is_listed_and_shown_in_full(library):
    m, offering = drafted(library)
    [row] = staged_offerings(library)
    assert row["offering"] == offering and row["status"] == "staged"
    assert row["claims"] == 1 and row["session"] == m.ctx.session and not row["question"]
    shown = staged_offering(library, offering)
    assert OSQUERY_LINE in shown["text"] and "## Claims" in shown["text"]
    asked = m.ok("promote_offering", offering=offering)
    assert staged_offerings(library)[0]["question"] == asked["question_id"]


def test_promote_answers_the_sessions_question_and_moves_the_draft(library):
    m, offering = drafted(library)
    asked = m.ok("promote_offering", offering=offering)
    out = decide_offering(person(library), offering, "promote")
    assert out["promoted"] == "Offerings/Host Watch/Host Watch Starter.md"
    assert out["by"] == "person" and out["findable"]
    assert staged_offerings(library) == []
    session = SessionStore(library).load(m.ctx.session)
    assert session.answered("confirm", offering)["answer"] == "yes"
    assert [o["status"] for o in session.offerings] == ["promoted"]
    assert not any(q["id"] == asked["question_id"] for q in session.open_questions())


def test_a_draft_left_staged_by_a_closed_session_can_still_be_promoted(library):
    """M0 pass 3's T2 run 3: the session ended with its draft still in staging."""
    m, offering = drafted(library)
    SessionStore(library).append(m.ctx.session, {"type": "closed"})
    assert staged_offerings(library)[0]["session_status"] == "closed"
    out = decide_offering(person(library), offering, "promote")
    assert out["promoted"].endswith("Host Watch Starter.md")
    assert (library.root / out["promoted"]).is_file()


def test_decline_keeps_the_draft_and_the_agent_cannot_promote_it_after(library):
    m, offering = drafted(library)
    out = decide_offering(person(library), offering, "decline")
    assert out["declined"] == offering
    [row] = staged_offerings(library)
    assert row["status"] == "declined"
    assert "no staged offering" in m("promote_offering", offering=offering)["detail"]
    # the person may change their mind
    assert decide_offering(person(library), offering, "promote")["promoted"]


def test_a_decision_is_promote_or_decline_and_names_a_staged_draft(library):
    _, offering = drafted(library)
    with pytest.raises(TypeError):
        decide_offering(person(library), offering, "maybe")
    with pytest.raises(TypeError, match="no staged offering"):
        decide_offering(person(library), "nothing-here", "promote")


def test_the_view_over_the_local_api(library, tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path / "config"))
    _, offering = drafted(library)
    app = App(library, token="t", keys=KeyStore(use_keyring=False))
    server = build(app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def call(path, body=None):
        req = urllib.request.Request(base + path, method="POST" if body else "GET",
                                     data=json.dumps(body).encode() if body else None,
                                     headers={"X-Librarian-Token": "t",
                                              "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read())
    try:
        assert [r["offering"] for r in call("/api/offerings/staged")["offerings"]] == [offering]
        assert OSQUERY_LINE in call(f"/api/offerings/staged?id={offering}")["text"]
        out = call("/api/offerings/decide", {"id": offering, "decision": "promote"})
        assert out["promoted"] and call("/api/offerings/staged")["offerings"] == []
        assert "error" in call("/api/offerings/decide", {"id": offering, "decision": "promote"})
    finally:
        server.shutdown()
        server.server_close()
        if app.mcp is not None:
            app.mcp.stop()


def test_promote_offering_by_the_agent_is_unchanged(library):
    m, offering = drafted(library)
    asked = m.ok("promote_offering", offering=offering)
    REGISTRY.call("answer", {"question_id": asked["question_id"], "answer": "yes"},
                  Context(tier="curate", vault=library, session=m.ctx.session))
    promoted = m.ok("promote_offering", offering=offering)
    assert promoted["by"] == "person" and promoted["findable"]
