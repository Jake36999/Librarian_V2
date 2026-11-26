"""Review kept apart from the work (implementation plan M4; policy, review).

The oracle has a role slot of its own. Assigned, and resolving to a model other than the Lead's (who
drafted the claims), it reviews an offering's claims; unassigned, the Clerk's route reviews them as
before; assigned but resolving to the Lead's own model, it is not used and a ticket says so. A claim
no review completed is still staged, as before, and held as a ticket for the Lead (as-is W-VER-02).
"""
from __future__ import annotations

from resource_librarian import clerk, notes
from resource_librarian.oracle import independence
from resource_librarian.role_routes import CHAT_ROLES, RoleRouteBinding, RoleRouteStore
from resource_librarian.tickets import TicketStore

from test_review_gate import CLAIM, SUMMARY, reviewer, reviewing, to_synthesise
from test_sessions import Model, library  # noqa: F401  (fixture)


def assign(vault, **models):
    rows = RoleRouteStore(vault).raw()
    for role, model in models.items():
        rows[role] = RoleRouteBinding(role=role, host_id="preset-deepinfra", model_id=model,
                                      protocol="openai_chat", source="explicit")
    RoleRouteStore(vault).save(rows)


def test_the_oracle_and_repair_roles_are_slots_of_their_own():
    assert "oracle" in CHAT_ROLES and "repair" in CHAT_ROLES


def test_independence_compares_the_resolved_model_not_the_route(library):
    assert independence(library, "lead", "oracle")["status"] == "unassigned"
    assign(library, lead="zai-org/GLM-5.3", oracle="other-host/glm-5.3")
    assert independence(library, "lead", "oracle")["status"] == "same_model"
    assign(library, oracle="google/gemma-4-26B-A4B-it")
    assert independence(library, "lead", "oracle")["status"] == "independent"


def test_without_an_oracle_the_clerk_reviews_as_before(library):
    reviewing(library)
    m = Model(library)
    m.ctx.extras["clerk"] = reviewer("holds")
    to_synthesise(m)
    out = m.ok("draft_offering", title="Host Watch Starter", summary=SUMMARY, claims=[CLAIM])
    review = notes.load(library.root / out["staged"]).frontmatter["review"]
    assert review["holds"] == 1 and review["reviewer"] == "clerk"
    assert review["independence"] == "no oracle assigned"


def test_an_independent_oracle_reviews_the_claims_instead_of_the_clerk(library):
    reviewing(library)
    assign(library, lead="zai-org/GLM-5.3", oracle="google/gemma-4-26B-A4B-it")
    m = Model(library)
    worker_clerk, oracle = reviewer("holds"), reviewer("holds")
    m.ctx.extras["clerk"], m.ctx.extras["oracle"] = worker_clerk, oracle
    to_synthesise(m)
    out = m.ok("draft_offering", title="Host Watch Starter", summary=SUMMARY, claims=[CLAIM])
    review = notes.load(library.root / out["staged"]).frontmatter["review"]
    assert review["reviewer"] == "oracle" and review["independence"] == "independent"
    assert [p for p in oracle.payloads if p["task"] == "review"]
    assert not [p for p in worker_clerk.payloads if p["task"] == "review"]


def test_an_oracle_on_the_leads_own_model_is_not_used_and_a_ticket_says_so(library):
    reviewing(library)
    assign(library, lead="zai-org/GLM-5.3", oracle="zai-org/GLM-5.3")
    m = Model(library)
    worker_clerk, oracle = reviewer("holds"), reviewer("holds")
    m.ctx.extras["clerk"], m.ctx.extras["oracle"] = worker_clerk, oracle
    to_synthesise(m)
    out = m.ok("draft_offering", title="Host Watch Starter", summary=SUMMARY, claims=[CLAIM])
    review = notes.load(library.root / out["staged"]).frontmatter["review"]
    assert review["reviewer"] == "clerk" and review["independence"] == "same_model"
    assert not [p for p in oracle.payloads if p["task"] == "review"]
    [ticket] = TicketStore(library).all(open_only=True)
    assert ticket["class"] == "oracle_unavailable" and ticket["owner"] == "owner"


def test_a_claim_no_review_completed_is_staged_and_held_as_a_ticket(library):
    reviewing(library)
    m = Model(library)
    m.ctx.extras["clerk"] = clerk.Scripted(lambda payload: {"verdict": "maybe"}
                                           if payload["task"] == "review" else {})
    to_synthesise(m)
    out = m.ok("draft_offering", title="Host Watch Starter", summary=SUMMARY, claims=[CLAIM])
    assert out["staged"]                                     # still staged, as before
    [ticket] = TicketStore(library).all(open_only=True)
    assert ticket["class"] == "held_claim" and ticket["owner"] == "lead"
    assert ticket["scope"].endswith("/claim:1")


def test_a_picker_change_keeps_the_oracles_own_assignment(vault):
    from resource_librarian.app import App
    from resource_librarian.keys import KeyStore
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=5)
    try:
        assign(vault, oracle="google/gemma-4-26B-A4B-it")
        rows = app._chat_bindings_for_tiers([{"provider": "deepinfra", "model": "zai-org/GLM-5.3"}])
        assert rows["oracle"].model_id == "google/gemma-4-26B-A4B-it"
    finally:
        app.close_runtime()
