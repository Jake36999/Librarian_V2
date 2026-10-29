"""HARNESS-04: the bounded Manager projection and capability manifest."""
from __future__ import annotations

import json

import pytest

from resource_librarian import tools  # noqa: F401  (registers tools)
from resource_librarian.audit_projection import (MAX_REFERENCES, capability_manifest,
                                                 estimate_tokens, project)
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.session import SessionStore

BUDGET = 4000
REQUIREMENTS = ("R1", "R2", "R3")
PREDICATES = ("quote present", "arithmetic reproduces")
CHAT = "a long message from the person about the work " * 40


def build(store, rounds):
    """An audited session after `rounds` full rounds, with chat in every round.

    Written straight to the log for speed: the rules are HARNESS-02's tests' job,
    and every caller re-checks the result by loading it (replay validates).
    Each contract revision advances the epoch, so round n is at epoch n - 1.
    Returns the session id and the log length at the end of each round.
    """
    sid = store.new("audited", question="Summarise the three sources with checked quotes").id
    append = lambda event: store.append(sid, event)  # noqa: E731
    for rid in REQUIREMENTS:
        append({"type": "requirement", "id": rid, "revision": 1,
                "text": f"{rid}: every quoted line is checked against its source.",
                "closure": "authoritative", "predicates": list(PREDICATES), "by": "person"})
    ends = {}
    for n in range(1, rounds + 1):
        issued_at = max(0, n - 2)   # the epoch the contract is admitted against
        epoch = n - 1               # after revision n advances it (revision 1 does not)
        if n > 1:
            append({"type": "phase", "to": "manage", "round": True})
        append({"type": "message", "role": "user", "text": CHAT})
        append({"type": "plan", "fields": {"proposal": {"requirements": list(REQUIREMENTS),
                                                         "step": f"round {n}"}}})
        append({"type": "contract", "id": "C1", "revision": n,
                "requirements": list(REQUIREMENTS), "role": "lead", "epoch": issued_at,
                "targets": {"read": ["sources/a.md"], "write": ["notes/s.md"]},
                "verifiers": {f"{r}: {p}": ("quote.located" if i == 0 else "arithmetic.reproduces")
                              for r in REQUIREMENTS for i, p in enumerate(PREDICATES)}})
        for phase in ("preflight", "execute", "audit", "reduce"):
            append({"type": "phase", "to": phase})
        append({"type": "artifact", "id": f"A{n}", "path": "notes/s.md",
                "fingerprint": f"{n:020d}", "contract": "C1"})
        for rid in REQUIREMENTS:
            for p, predicate in enumerate(PREDICATES):
                failing = rid == "R1" and p == 1
                append({"type": "verifier_result", "id": f"V{n}-{rid}-{p}", "requirement": rid,
                        "contract": "C1", "contract_revision": n, "predicate": predicate,
                        "verifier": "quote.located" if p == 0 else "arithmetic.reproduces",
                        "strength": "exact", "outcome": "fail" if failing else "pass",
                        "artifacts": [f"A{n}"], "epoch": epoch})
            failing = rid == "R1"
            append({"type": "reduction", "requirement": rid,
                    "status": "partial" if failing else "verified",
                    "results": [] if failing else [f"V{n}-{rid}-0", f"V{n}-{rid}-1"],
                    "by": "core", "epoch": epoch})
        ends[n] = len(store.events(sid)) if n in (1, 10, rounds) else None
    return sid, ends


def at(store, sid, length):
    """The session and its events as they stood after the first `length` events."""
    from resource_librarian.session import Session
    events = store.events(sid)[:length]
    session = Session(id=sid, purpose="explore")
    for event in events:
        session.apply(dict(event))
    return session, events


def projection(store, sid, budget=BUDGET, length=None, **kw):
    manifest = capability_manifest(tier="contribute")
    if length is None:
        session, events = store.load(sid), store.events(sid)
    else:
        session, events = at(store, sid, length)
    assert not session.audit.invalid, session.audit.invalid  # the fixture obeys the rules
    return project(session, events, manifest=manifest, vault=store.vault,
                   token_budget=budget, **kw)


@pytest.fixture
def store(vault):
    return SessionStore(vault)


# --- the done-when: bounded, references only, 50 rounds deterministic -----------------

@pytest.fixture(scope="module")
def fifty(tmp_path_factory):
    """One 50-round session, built once; projections at rounds 1, 10 and 50."""
    from resource_librarian.init import init
    from resource_librarian.vault import Vault
    root = tmp_path_factory.mktemp("fifty") / "vault"
    init(root, name="Projection")
    store = SessionStore(Vault(root))
    sid, ends = build(store, 50)
    sizes = {rounds: projection(store, sid, length=ends[rounds]) for rounds in (1, 10)}
    sizes[50] = projection(store, sid)
    return store, sid, sizes


def test_every_projection_fits_its_token_budget(fifty):
    _, _, sizes = fifty
    for rounds, proj in sizes.items():
        assert proj["fits"] is True, rounds
        assert proj["accounting"]["tokens"] <= BUDGET
        assert estimate_tokens({k: v for k, v in proj.items() if k != "digest"}) <= BUDGET + 50


def test_fifty_rounds_stay_bounded(fifty):
    _, _, sizes = fifty
    # Older reports become counted references, so round 50 costs about what round 10 does.
    assert sizes[50]["accounting"]["tokens"] <= sizes[10]["accounting"]["tokens"] * 1.15


def test_the_projection_is_deterministic(fifty):
    store, sid, sizes = fifty
    again = projection(SessionStore(store.vault), sid)
    assert again == sizes[50]
    assert again["digest"] == sizes[50]["digest"]


def test_older_reports_are_references_only(fifty):
    _, _, sizes = fifty
    proj = sizes[50]
    text = json.dumps(proj)
    latest_ids = {v["id"] for v in proj["latest_results"].values()}
    assert all(i.startswith("V50-") for i in latest_ids)
    refs = proj["references"]
    assert len(refs["older_results"]) == MAX_REFERENCES
    assert refs["older_results_not_listed"] == 49 * 6 - MAX_REFERENCES
    assert all(not i.startswith("V50-") for i in refs["older_results"])
    # An older result appears as an id, never with its details.
    assert '"V3-R2-0"' not in text and "V1-R1-0" not in text  # beyond the cap: counted only


def test_each_predicate_keeps_its_own_outcome(fifty):
    _, _, sizes = fifty
    r1 = sizes[50]["requirements"]["R1"]
    assert r1["predicates"] == {"quote present": "pass", "arithmetic reproduces": "fail"}
    assert r1["status"] == "partial"
    # Verified requirements are referenced compactly, not repeated in full.
    assert sizes[50]["closed_requirements"] == {"R2": "verified", "R3": "verified"}


def test_conversation_text_is_not_copied(fifty):
    store, sid, sizes = fifty
    assert "a long message from the person" not in json.dumps(sizes[50])
    wide = projection(store, sid, budget=8000, recent=30)  # wide enough to reach a message
    assert "a long message from the person" not in json.dumps(wide)
    assert any(e["type"] == "message" and e["chars"] == len(CHAT)
               for e in wide["recent_events"])


# --- constraints are never cut -------------------------------------------------------

def test_active_constraints_appear_verbatim(store):
    sid, _ = build(store, 2)
    proj = projection(store, sid)
    stored = store.load(sid).audit.requirements["R1"]["text"]
    assert proj["requirements"]["R1"]["text"] == stored


def test_constraints_that_cannot_fit_stop_the_projection_instead_of_being_cut(store):
    sid = store.new("audited", question="q").id
    store.append_audit(sid, {"type": "requirement", "id": "R1", "revision": 1,
                             "text": "Keep every clause of this agreement. " * 400,
                             "closure": "authoritative", "predicates": ["p"], "by": "person"})
    proj = projection(store, sid, budget=1000)
    assert proj["fits"] is False
    assert "split the work or narrow the requirements" in proj["reason"]
    assert "requirements" not in proj  # nothing partial is offered as if it were whole


def test_a_tight_budget_trims_recent_events_first_and_says_so(store):
    sid, _ = build(store, 3)
    roomy = projection(store, sid)
    tight = projection(store, sid, budget=roomy["accounting"]["tokens"] - 150)
    assert tight["fits"] is True
    assert tight["accounting"]["trimmed"]["recent_events"] > 0
    assert len(tight.get("recent_events", [])) < len(roomy["recent_events"])
    assert tight["requirements"] == roomy["requirements"]  # essential content unchanged


# --- the capability manifest ----------------------------------------------------------

def test_the_manifest_lists_bundles_verifiers_roots_and_routes():
    manifest = capability_manifest(tier="contribute",
                                   routes={"lead": {"available": True, "reason": "screened"}})
    assert {"session", "read"} <= {b["id"] for b in manifest["bundles"]}
    assert "quote.located" in {v["id"] for v in manifest["verifiers"]}
    assert manifest["roots"] == ["."]
    assert manifest["routes"]["lead"]["available"] is True
    assert manifest["routes"]["clerk"]["available"] == "unknown"  # never assumed available


def test_a_lower_tier_sees_no_more_bundles():
    consult = {b["id"] for b in capability_manifest(tier="consult")["bundles"]}
    contribute = {b["id"] for b in capability_manifest(tier="contribute")["bundles"]}
    assert consult <= contribute


# --- the tool -------------------------------------------------------------------------

def test_the_lead_reads_its_projection_through_the_tool(vault, store):
    ctx = Context(tier="contribute", vault=vault)
    REGISTRY.call("open_session", {"purpose": "audited", "question": "q"}, ctx)
    person = Context(tier="curate", vault=vault, session=ctx.session)
    REGISTRY.call("set_requirement", {"requirement_id": "R1", "text": "Exists.",
                                      "predicates": ["exists"]}, person)
    proj = REGISTRY.call("audit_projection", {}, ctx)
    assert proj["fits"] is True and "R1" in proj["requirements"]
    other = Context(tier="contribute", vault=vault)
    REGISTRY.call("open_session", {"purpose": "explore", "question": "q"}, other)
    assert "audited session" in json.dumps(REGISTRY.call("audit_projection", {}, other))
