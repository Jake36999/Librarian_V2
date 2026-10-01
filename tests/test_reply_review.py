"""Roadmap §4 G3 on chat replies (2026-09-28): the claims a reply makes about the
notes it links are checked against those notes, after the reply; a challenge
reaches the lead model's next prompt, and the person sees the verdict."""
from resource_librarian import clerk, providers, reply_review
from resource_librarian.loop import Loop
from resource_librarian.providers import Reply
from resource_librarian.vault import render_config

from conftest import add_source
from test_app import served, wait_for  # noqa: F401  (fixture)

LINE = "Exposes the operating system as a relational database you query with SQL."
REPLY = ("[[osquery]] lets you query processes with SQL, and [[osquery]] ships a GPU "
         "accelerator. Unrelated: [[Nowhere]] is great.")


def reviewer(payload):
    if payload["task"] == "reply_claims":
        return {"claims": [
            {"claim": "osquery lets you query the operating system with SQL", "note": "osquery"},
            {"claim": "osquery ships a GPU accelerator", "note": "osquery"},
            {"claim": "Nowhere is great", "note": "Nowhere"},                 # no such note
            {"claim": "duckdb is fast", "note": "duckdb"}]}                  # not linked
    if payload["task"] == "review":
        if "GPU" in payload["user"].split("---")[0]:
            return {"verdict": "fails", "counter_quote": LINE, "reason": "it says nothing of GPUs"}
        return {"verdict": "holds", "reason": "stated"}
    return {}


def test_claims_are_checked_against_the_notes_the_reply_links(vault):
    add_source(vault.root, "osquery", LINE)
    add_source(vault.root, "duckdb", "An in-process analytical database.")
    endpoint = clerk.Scripted(reviewer)
    out = reply_review.review_reply(vault, REPLY, endpoint)
    assert out["held"] == 1
    challenged = {c["claim"]: c for c in out["challenged"]}
    assert challenged["osquery ships a GPU accelerator"]["verdict"] == "fails"
    # A link to a note nobody wrote is challenged on its own, not silently
    # dropped - the gap that let a reply cite fabricated notes go unchecked.
    assert challenged["cites [[Nowhere]]"]["verdict"] == "not_found"
    assert len(out["challenged"]) == 2
    reviewed = [p for p in endpoint.payloads if p["task"] == "review"]
    assert len(reviewed) == 2                 # claim-checking itself still skips an unreal note
    assert all(LINE in p["user"] and "Unrelated" not in p["user"] for p in reviewed)  # never the reply


def test_a_reply_that_links_no_note_is_not_reviewed(vault):
    assert reply_review.review_reply(vault, "No links here.", clerk.Scripted(reviewer)) is None


def test_a_reply_inventing_a_source_that_was_never_ingested_is_challenged(vault):
    """2026-09-28: a lead model narrated a whole research session - sources
    found, queued, ingested - and finished by citing
    [[Sources/UCLan BSc Hons Computer Science]], never once having actually
    called a tool that would create it. `held`/`unchecked` stayed at 0 either
    way; only `challenged` said anything was wrong."""
    fabricated = "See [[Sources/UCLan BSc Hons Computer Science]] for the module list."

    def claims_nothing(payload):
        return {"claims": []} if payload["task"] == "reply_claims" else {}

    out = reply_review.review_reply(vault, fabricated, clerk.Scripted(claims_nothing))
    assert out["challenged"] == [{"claim": "cites [[Sources/UCLan BSc Hons Computer Science]]",
                                  "note": "Sources/UCLan BSc Hons Computer Science",
                                  "verdict": "not_found", "counter_quote": "",
                                  "reason": "no note by this name exists in the vault"}]
    assert out["held"] == 0 and out["unchecked"] == 0


def test_a_linked_note_no_claim_was_listed_about_is_counted_unchecked(vault):
    """Test Directive A5 (2026-10-01): two replies' claims were never listed, so they
    went unreviewed and nothing said so."""
    add_source(vault.root, "osquery", LINE)
    add_source(vault.root, "falco", "Watches kernel system calls.")

    def lists_nothing(payload):
        return {"claims": []} if payload["task"] == "reply_claims" else {}

    out = reply_review.review_reply(vault, "[[osquery]] is queried with GraphQL, not SQL.",
                                    clerk.Scripted(lists_nothing))
    assert out["unchecked"] == 1 and out["not_extracted"] == ["osquery"]
    assert out["held"] == 0 and out["challenged"] == []
    # one note's claims listed, another's not: only the silent one is named
    out = reply_review.review_reply(vault, REPLY + " And [[falco]] is slow.",
                                    clerk.Scripted(reviewer))
    assert out["not_extracted"] == ["falco"] and out["held"] == 1


def test_claims_past_the_limit_are_counted_not_dropped(vault):
    add_source(vault.root, "osquery", LINE)
    out = reply_review.review_reply(vault, REPLY, clerk.Scripted(reviewer), max_claims=1)
    assert out["over_limit"] == 1 and out["unchecked"] == 1 and out["held"] == 1


def test_the_extraction_prompt_names_denials_and_restrictions_as_claims():
    prompt = clerk.reply_claims("[[osquery]] runs only on Windows.").question
    assert "denial or a restriction is a claim" in prompt


def test_a_challenge_reaches_the_next_prompt_once(vault):
    loop = Loop(vault, providers.Scripted(lambda s, m, t: Reply(text="ok")))
    loop.challenges = [{"claim": "osquery ships a GPU accelerator", "note": "osquery",
                        "reason": "it says nothing of GPUs", "counter_quote": LINE}]
    seen = []
    loop.provider = providers.Scripted(lambda s, m, t: (seen.append(s), Reply(text="ok"))[1])
    loop.send("go on")
    loop.send("and then")
    assert "osquery ships a GPU accelerator" in seen[0]
    assert "osquery ships a GPU accelerator" not in seen[1]


def test_the_app_reviews_after_the_reply_only_when_turned_on(served, monkeypatch):
    app, client, model = served
    calls = []

    def fake(vault, reply, endpoint, **_):
        calls.append(reply)
        return {"held": 1, "unchecked": 0, "challenged": [{"claim": "c", "note": "osquery",
                                                            "reason": "r", "counter_quote": "q"}]}
    monkeypatch.setattr(reply_review, "review_reply", fake)
    client.post("/api/tiers", {"tiers": [{"provider": "deepinfra", "model": "m1"}], "override": "test"})
    model.replies = [Reply(text="See [[osquery]].")]
    client.post("/api/chat", {"text": "hi"})
    wait_for(app, "turn_done")
    assert calls == []                                    # off by default

    config = app.vault.config()
    config.setdefault("clerk", {})["review_replies"] = True
    app.vault.config_path.write_text(render_config(config))
    after = len(app.hub.since(0))
    model.replies = [Reply(text="See [[osquery]] again.")]
    client.post("/api/chat", {"text": "again"})
    event = wait_for(app, "reply_reviewed", after=after)
    assert event["held"] == 1 and calls == ["See [[osquery]] again."]
    assert app.loop.challenges[0]["claim"] == "c"
