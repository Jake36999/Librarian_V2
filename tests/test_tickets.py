"""Tickets, the hardened checkpoint store, and one agenda (implementation plan M3).

A failure or misalignment is a ticket with an owner and a review date (as-is W-DOC-02), not a code in
one call's result; a quarantined capture opens one (W-INT-02); read work waiting for acceptance has an
owner and a review date (W-STI-02); and the agenda shows the person's waiting decisions and the open
tickets beside the dated tasks (UC9).
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

import pytest

from resource_librarian import intake, tools  # noqa: F401
from resource_librarian.checkpoints import CheckpointStore
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.tickets import TicketStore, effective_owner, routing


def person(vault):
    return Context(tier="curate", vault=vault, extras={"caller_kind": "person"})


def agent(vault):
    return Context(tier="contribute", vault=vault, extras={"caller_kind": "mcp", "caller": "mcp"})


def test_every_routing_class_has_one_owner_and_a_known_queue():
    classes = routing()["classes"]
    assert len(classes) == 13
    assert classes["critical"]["review_days"] == 0
    assert "review_days" not in classes["reserved_decision"]       # waits for its owner


def test_one_open_ticket_per_failure_and_a_new_one_after_it_closes(vault):
    store = TicketStore(vault)
    first = store.ensure("unmapped_failure", "run:1/stage:read", summary="no remedy")
    assert store.ensure("unmapped_failure", "run:1/stage:read")["id"] == first["id"]
    assert first["owner"] == "lead" and first["review_by"]
    store.close(first["id"], "person", "looked at it")
    assert store.ensure("unmapped_failure", "run:1/stage:read")["id"] != first["id"]


def test_a_worker_never_closes_its_own_ticket(vault):
    store = TicketStore(vault)
    ticket = store.ensure("mapped_shortfall", "x")
    with pytest.raises(ValueError, match="never by the worker"):
        store.close(ticket["id"], "doctor", "fixed it myself")


def test_an_overdue_ticket_shows_under_its_next_owner_one_step_per_period(vault):
    ticket = TicketStore(vault).ensure("quarantined_capture", "intake:abc")     # doctor, 1 day
    opened = datetime.fromisoformat(ticket["opened_at"])
    assert effective_owner(ticket, opened + timedelta(hours=12)) == ("doctor", False)
    assert effective_owner(ticket, opened + timedelta(days=1, hours=1)) == ("lead", True)
    assert effective_owner(ticket, opened + timedelta(days=2, hours=1)) == ("overseer", True)
    assert effective_owner(ticket, opened + timedelta(days=9)) == ("owner", True)
    held = TicketStore(vault).ensure("reserved_decision", "sensitivity:x")
    assert effective_owner(held, opened + timedelta(days=90)) == ("owner", False)


def test_a_handover_is_recorded_and_changes_the_owner(vault):
    store = TicketStore(vault)
    ticket = store.ensure("unmapped_failure", "y")
    out = store.note(ticket["id"], "agent:tier0", "a code change is needed", handover_to="overseer")
    assert out["owner"] == "overseer" and out["history"][-1]["event"] == "handover"


def test_two_writers_at_once_lose_no_row(vault):
    tickets, checkpoints = TicketStore(vault), CheckpointStore(vault)

    def write(n):
        for i in range(40):
            TicketStore(vault).ensure("unmapped_failure", f"w{n}-{i}")
            CheckpointStore(vault).create("ticket_escalation", f"w{n}-{i}")

    threads = [threading.Thread(target=write, args=(n,)) for n in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(tickets.all()) == 120
    assert len(checkpoints.all()) == 120


def test_the_new_checkpoint_types_are_accepted(vault):
    for kind in ("high_risk_hold", "folder_sensitivity", "ticket_escalation"):
        assert CheckpointStore(vault).create(kind, f"scope-{kind}")["type"] == kind


def test_a_quarantined_capture_opens_a_ticket_that_a_later_capture_closes(vault):
    intake._quarantine(vault, "https://example.org/missing.pdf", "fetch", "404")
    [ticket] = TicketStore(vault).all(open_only=True)
    assert ticket["class"] == "quarantined_capture" and ticket["owner"] == "doctor"
    assert ticket["evidence"]["stage"] == "fetch"
    intake._close_quarantine_ticket(vault, "https://example.org/missing.pdf")
    assert TicketStore(vault).all(open_only=True) == []
    assert TicketStore(vault).all()[0]["history"][-1]["by"] == "core-recheck"


def test_the_agenda_shows_waiting_decisions_and_open_tickets(vault):
    CheckpointStore(vault).create("high_risk_hold", "batch:start", requester="core")
    TicketStore(vault).ensure("held_claim", "report:x/claim:3", summary="no review on two routes")
    out = REGISTRY.call("agenda", {}, agent(vault))
    assert [d["type"] for d in out["decisions"]] == ["high_risk_hold"]
    assert out["tickets"][0]["class"] == "held_claim" and out["tickets"][0]["owner"] == "lead"


def test_closing_a_ticket_is_the_persons(vault):
    ticket = TicketStore(vault).ensure("unmapped_failure", "z")
    assert REGISTRY.call("ticket_close", {"ticket_id": ticket["id"], "resolution": "x"},
                         agent(vault))["refused"] == "TIER_REFUSED"
    out = REGISTRY.call("ticket_close", {"ticket_id": ticket["id"], "resolution": "seen"}, person(vault))
    assert out["status"] == "closed"
    noted = REGISTRY.call("ticket_note", {"ticket_id": ticket["id"], "text": "late"}, agent(vault))
    assert noted["error"] == "invalid_arguments" and "closed" in noted["detail"]


def test_waiting_read_work_has_an_owner_and_a_review_date(vault):
    from resource_librarian.staging import StagingStore
    store = StagingStore(vault)
    store.add({"id": "w1", "kind": "source", "name": "waiting paper", "status": "enriched"})
    item = store.load("w1"); item["status"] = "enriched"; store.save(item)
    waiting = store.awaiting_acceptance()
    assert waiting["count"] == 1 and waiting["owner"] == "owner"
    assert waiting["review_days"] == 7 and waiting["overdue"] is False
