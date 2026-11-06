"""MF-027a (spec U-B2): a reply review is bound to the exact note it checked and to the
reply it reviewed. Ambiguous names stay unchecked, unread text is never called silent,
invented links cannot flood the next prompt, and a late review stays on its own reply.

MF-027c: whether Docker can run a claim is asked before Run it is offered."""
from __future__ import annotations

from types import SimpleNamespace

from resource_librarian import claim_run, clerk, reply_review
from resource_librarian.providers import Reply
from resource_librarian.session import SessionStore
from resource_librarian.vault import render_config

from conftest import write_note
from test_app import served, wait_for  # noqa: F401  (fixture)


def scripted(claims, verdict="holds", counter=""):
    def answer(payload):
        if payload["task"] == "reply_claims":
            return {"claims": claims}
        if payload["task"] == "review":
            return {"verdict": verdict, "counter_quote": counter, "reason": "fixture"}
        return {}
    return clerk.Scripted(answer)


def test_two_notes_with_one_name_leave_a_bare_link_unchecked_and_a_folder_link_exact(vault):
    write_note(vault.root, "Notes/Alpha/Plan.md", "type: note", "The plan uses SQL.")
    write_note(vault.root, "Notes/Beta/Plan.md", "type: note", "The plan uses GraphQL.")
    bare = reply_review.review_reply(vault, "See [[Plan]].",
                                     scripted([{"claim": "it uses SQL", "note": "Plan"}]))
    assert bare["ambiguous"] == ["Plan"] and bare["unchecked"] == 1
    assert bare["challenged"] == [] and bare["held"] == 0           # never a guess

    exact = reply_review.review_reply(vault, "See [[Notes/Beta/Plan]].",
                                      scripted([{"claim": "it uses SQL", "note": "Notes/Beta/Plan"}],
                                               verdict="fails", counter="The plan uses GraphQL."))
    row = exact["challenged"][0]
    assert row["note_path"] == "Notes/Beta/Plan.md" and row["source_revision"]
    assert row["coverage"]["complete"] is True and row["coverage"]["checked_spans"][0][0] == 0


def test_unread_text_is_never_called_silent_but_a_found_contradiction_stands(vault):
    write_note(vault.root, "Notes/Long.md", "type: note",
               "Opening. " + "x" * (reply_review.NOTE_CHARS + 2000) + " The claim is here.")
    claims = [{"claim": "the claim is stated", "note": "Long"}]
    silent = reply_review.review_reply(vault, "[[Long]] says so.", scripted(claims, "unsupported"))
    assert silent["challenged"] == [] and silent["unchecked"] == 1
    partly = silent["partly_checked"][0]
    assert partly["note_path"] == "Notes/Long.md" and partly["coverage"]["truncated"] is True
    assert "not found in the first" in partly["reason"]
    contradicted = reply_review.review_reply(vault, "[[Long]] says so.",
                                             scripted(claims, "fails", counter="Opening. xxxxxxxx"))
    assert contradicted["challenged"][0]["verdict"] == "fails"


def test_invented_links_spend_the_same_cap_as_claim_checks(vault):
    reply = " ".join(f"[[Invented {n}]]" for n in range(20))
    out = reply_review.review_reply(vault, reply, scripted([]), max_claims=3)
    assert len(out["challenged"]) == 3 and out["over_limit"] == 17 and out["unchecked"] == 17


def test_a_review_names_its_reply_and_is_kept_in_the_session_log(served, monkeypatch):
    app, client, model = served
    config = app.vault.config()
    config.setdefault("clerk", {})["review_replies"] = True
    app.vault.config_path.write_text(render_config(config))
    seen = []

    def fake(vault, reply, endpoint, **kwargs):
        seen.append(kwargs)
        return {"held": 0, "unchecked": 0, "challenged": [{"claim": "c", "note": "osquery",
                                                           "reason": "r", "counter_quote": "q"}]}
    monkeypatch.setattr(reply_review, "review_reply", fake)
    client.post("/api/tiers", {"tiers": [{"provider": "deepinfra", "model": "m1"}], "override": "test"})
    model.replies = [Reply(text="See [[osquery]].")]
    client.post("/api/chat", {"text": "hi"})
    done = wait_for(app, "turn_done")
    review = wait_for(app, "reply_reviewed")
    assert done["reply_id"].startswith("r-") and done["turn_id"].startswith("t-")
    assert review["reply_id"] == done["reply_id"] and review["turn_id"] == done["turn_id"]
    assert seen[0]["reply_id"] == done["reply_id"]
    assert review["carried_to_next_prompt"] is True and app.loop.challenges[0]["claim"] == "c"
    text = next(e for e in app.hub.since(0) if e.get("type") == "text" and e.get("reply_id"))
    assert text["reply_id"] == done["reply_id"]


def test_a_review_is_kept_in_its_sessions_own_log(served, monkeypatch):
    app, _, _ = served
    config = app.vault.config()
    config.setdefault("clerk", {})["review_replies"] = True
    app.vault.config_path.write_text(render_config(config))
    session = app.person_call("open_session", {"purpose": "explore", "question": "q"})["opened"]
    monkeypatch.setattr(reply_review, "review_reply", lambda vault, reply, endpoint, **kw: {
        "held": 1, "unchecked": 0, "challenged": []})
    loop = SimpleNamespace(ctx=SimpleNamespace(session=session), current_turn_id="t-1", challenges=[])
    app._review_reply(loop, "See [[osquery]].", "r-1", "t-1")
    wait_for(app, "reply_reviewed")
    events = SessionStore(app.vault).path(session).read_text(encoding="utf-8")
    assert '"type": "reply_reviewed"' in events and '"reply_id": "r-1"' in events


def test_a_late_review_stays_on_its_own_reply(served, monkeypatch):
    app, client, model = served
    config = app.vault.config()
    config.setdefault("clerk", {})["review_replies"] = True
    app.vault.config_path.write_text(render_config(config))

    def late(vault, reply, endpoint, **kwargs):
        app.loop.current_turn_id = "t-newer"            # a new turn began meanwhile
        return {"held": 0, "unchecked": 0, "challenged": [{"claim": "late", "note": "osquery",
                                                           "reason": "r", "counter_quote": "q"}]}
    monkeypatch.setattr(reply_review, "review_reply", late)
    client.post("/api/tiers", {"tiers": [{"provider": "deepinfra", "model": "m1"}], "override": "test"})
    model.replies = [Reply(text="See [[osquery]].")]
    client.post("/api/chat", {"text": "hi"})
    review = wait_for(app, "reply_reviewed")
    assert review["late"] is True and review["carried_to_next_prompt"] is False
    assert app.loop.challenges == []                    # not carried into the newer turn


def test_docker_is_asked_once_before_run_it_and_again_when_asked_fresh(monkeypatch):
    answers = iter([SimpleNamespace(returncode=1, stdout="", stderr=""),
                    SimpleNamespace(returncode=0, stdout="29.8.1", stderr="")])
    asked = []

    def runner(args, timeout):
        asked.append(args)
        return next(answers)
    monkeypatch.setattr(claim_run, "_run", runner)
    monkeypatch.setattr(claim_run.shutil, "which", lambda name: "docker")
    claim_run._preflight.clear()
    first = claim_run.preflight()
    assert first["available"] is False and "not running" in first["detail"]
    assert claim_run.preflight() == first and len(asked) == 1        # held, not asked again
    fresh = claim_run.preflight(fresh=True)
    assert fresh["available"] is True and len(asked) == 2
    claim_run._preflight.clear()


def test_the_preflight_is_offered_to_the_ui(served, monkeypatch):
    app, client, _ = served
    monkeypatch.setattr(claim_run, "preflight", lambda runner=None, fresh=False: {
        "available": False, "detail": "Docker is not installed", "checked_at": "now"})
    status, body = client.get("/api/claims/preflight")
    assert status == 200 and body["available"] is False and "not installed" in body["detail"]
