"""Roadmap §4 G3 (2026-09-28): the review gate on an offering's claims. A
reviewer sees one claim, its quote and the passage around it - never the draft -
and a `fails` counts only with a counter-quote from that passage. A challenge
goes back to the lead model; a claim it keeps anyway waits for a person."""
import pytest

from resource_librarian import clerk, notes
from resource_librarian.vault import render_config

from test_sessions import OSQUERY_LINE, Model, library  # noqa: F401  (fixture)

CLAIM = {"text": "osquery lets you query the operating system with SQL", "source": "osquery",
         "quote": OSQUERY_LINE}
SUMMARY = "Start with osquery; UNIQUE-SUMMARY-MARKER."


def reviewing(vault, mode="agent"):
    config = vault.config()
    config.setdefault("clerk", {})["review_offerings"] = True
    config["promotion"]["mode"] = mode
    vault.config_path.write_text(render_config(config))


def to_synthesise(m):
    m.ok("open_session", purpose="add_project")
    m.ok("create_project", name="Host Watch", stage="planning", summary="Watch our hosts.",
         disqualifiers=["requires a GPU"])
    m.ok("advance")
    m.ok("update_plan", fields={"ingested": "none"})
    m.ok("advance")
    m.ok("search", query="operating system state", intent="orient")
    m.ok("update_plan", fields={"map": "host tooling"})
    m.ok("advance")
    m.ok("open_brief", need="query operating system state as a database")
    if m.ok("advance")["moved"] == "search":
        m.run_rounds(["operating system state database"], brief="B1")
        m.ok("advance")
    else:
        m.ok("add_candidate", source="osquery", brief="B1")
    m.decide_all(keep={"osquery"})
    m.ok("record_assumptions", assumptions=[])
    m.ok("advance")
    m.ok("record_synthesis", outcome="offering", together="osquery alone covers the need",
         unknowns="fleet scale", open_first="osquery")


def reviewer(verdict, counter=""):
    def answer(payload):
        if payload["task"] != "review":
            return {}
        return {"verdict": verdict, "counter_quote": counter, "reason": "checked"}
    return clerk.Scripted(answer)


def test_a_claim_the_passage_supports_is_staged_with_the_review_recorded(library):
    reviewing(library)
    m = Model(library)
    endpoint = reviewer("holds")
    m.ctx.extras["clerk"] = endpoint
    to_synthesise(m)
    out = m.ok("draft_offering", title="Host Watch Starter", summary=SUMMARY, claims=[CLAIM])
    note = notes.load(library.root / out["staged"])
    assert note.frontmatter["review"]["holds"] == 1
    assert note.frontmatter["review"]["challenged_kept"] == 0
    asked = [p for p in endpoint.payloads if p["task"] == "review"]
    assert len(asked) == 1 and OSQUERY_LINE in asked[0]["user"]
    # Never the draft: the reviewer sees the claim and its passage, not the summary.
    assert "UNIQUE-SUMMARY-MARKER" not in asked[0]["user"]
    assert "fleet scale" not in asked[0]["user"]


def test_a_challenge_goes_back_to_the_lead_model_with_the_passages_words(library):
    reviewing(library)
    m = Model(library)
    m.ctx.extras["clerk"] = reviewer("fails", counter=OSQUERY_LINE[:40])
    to_synthesise(m)
    out = m("draft_offering", title="Host Watch Starter", summary=SUMMARY, claims=[CLAIM])
    assert out["refused"] == "REVIEW_CHALLENGED"
    assert OSQUERY_LINE[:40] in out["detail"] and "rebuttal" in out["detail"]


def test_a_kept_challenge_is_shown_and_only_a_person_promotes_it(library):
    reviewing(library, mode="agent")                     # even where agents may promote
    m = Model(library)
    m.ctx.extras["clerk"] = reviewer("fails", counter=OSQUERY_LINE[:40])
    to_synthesise(m)
    kept = {**CLAIM, "rebuttal": "the claim restates the passage in other words"}
    out = m.ok("draft_offering", title="Host Watch Starter", summary=SUMMARY, claims=[kept])
    body = (library.root / out["staged"]).read_text(encoding="utf-8")
    assert "⚑ Challenged by review" in body and "Kept because: the claim restates" in body
    promoted = m.ok("promote_offering", offering=out["offering"])
    assert promoted["promoted"] is False and promoted["question_id"]


def test_a_fails_without_a_counter_quote_from_the_passage_is_not_counted(library):
    reviewing(library)
    m = Model(library)
    m.ctx.extras["clerk"] = reviewer("fails", counter="words that are nowhere in the passage")
    to_synthesise(m)
    out = m.ok("draft_offering", title="Host Watch Starter", summary=SUMMARY, claims=[CLAIM])
    review = notes.load(library.root / out["staged"]).frontmatter["review"]
    assert review["unchecked"] == 1 and review["challenged_kept"] == 0


def test_without_review_turned_on_nothing_is_asked(library):
    m = Model(library)
    endpoint = reviewer("fails", counter=OSQUERY_LINE[:40])
    m.ctx.extras["clerk"] = endpoint
    to_synthesise(m)
    out = m.ok("draft_offering", title="Host Watch Starter", summary=SUMMARY, claims=[CLAIM])
    assert "review" not in notes.load(library.root / out["staged"]).frontmatter
    assert not [p for p in endpoint.payloads if p["task"] == "review"]
