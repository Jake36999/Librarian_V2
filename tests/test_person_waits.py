"""A question waiting for a person never holds, or interleaves, the vault writer.

Found while routing MCP through the Core (2026-10-24), and reproduced on
master: in a coordinated Core every asking tool (ask_user, request_budget,
open_brief, promote_offering, capability_install) runs on the writer thread,
and the person's answer is itself a write, so the answer queued behind the
question until it timed out.  Serving the queue during the wait fixed the
hang but broke linearity (review, 2026-10-24): an unrelated write could land
inside an operation that had already checked its revisions.  Now the question
is recorded inside the operation and waited on after it, outside the writer.
"""
import threading
import time

import pytest

from resource_librarian.app import App
from resource_librarian.coordination import VaultWriter, on_writer_thread
from resource_librarian.registry import PERSON_WAIT, REGISTRY, Context
from resource_librarian.session import SessionStore
from resource_librarian.tools.sessions import Waiters


@pytest.fixture
def core(vault):
    app = App(vault, coordinate=True, broker_timeout=20.0)
    yield app
    app.close_runtime()


def test_writer_operations_know_they_are_on_the_writer(vault):
    writer = VaultWriter(vault)
    try:
        assert writer.submit(on_writer_thread, caller="probe") is True
        assert on_writer_thread() is False
    finally:
        writer.close()


def test_a_person_is_never_waited_on_inside_a_writer_operation(vault):
    writer = VaultWriter(vault)
    try:
        with pytest.raises(RuntimeError, match="never waited on inside"):
            writer.submit(lambda: Waiters(timeout=5).wait("k"), caller="ask")
    finally:
        writer.close()


def test_an_ask_inside_an_operation_leaves_the_writer_before_it_waits(core, vault):
    """While the question is open, the writer is free: an unrelated write runs
    at once instead of waiting for the person, and runs between operations,
    never inside the asking one."""
    sid = core.person_call("open_session", {"purpose": "explore", "question": "q"})["opened"]
    out = {}
    thread = threading.Thread(target=lambda: out.setdefault(
        "ask", core.person_call("ask_user", {"question": "which?"}, sid)))
    thread.start()
    deadline = time.monotonic() + 5
    while not core.waiters._pending and time.monotonic() < deadline:
        time.sleep(0.02)
    assert core.waiters._pending, "the question never started waiting"
    started = time.monotonic()
    core.writer.submit(lambda: None, caller="unrelated")
    assert time.monotonic() - started < 1                    # not held by the open question
    answered = core.person_call("answer", {"question_id": "q1", "answer": "this one"}, sid)
    thread.join(10)
    assert answered["resumed"] is True
    assert out["ask"]["answer"] == "this one" and PERSON_WAIT not in out["ask"]
    assert "needs_person" not in out["ask"]


def test_an_answer_landing_before_the_wait_starts_is_not_lost(vault):
    """The waiter is registered before the question is recorded."""
    waiters = Waiters(timeout=5)
    done = waiters.register("k")
    assert waiters.answer("k", "early") is True
    assert waiters.wait("k", done) == "early"


def test_a_question_asked_in_a_coordinated_core_gets_its_answer(core):
    sid = core.person_call("open_session", {"purpose": "explore", "question": "q"})["opened"]
    out = {}

    def asker():
        out["ask"] = core.person_call("ask_user", {"question": "which?"}, sid)
    thread = threading.Thread(target=asker)
    thread.start()
    time.sleep(0.5)
    started = time.monotonic()
    answered = core.person_call("answer", {"question_id": "q1", "answer": "this one"}, sid)
    thread.join(10)
    assert time.monotonic() - started < 3
    assert answered["resumed"] is True
    assert "error" not in out["ask"], out["ask"]


def test_a_nested_ask_in_an_operation_stays_open_instead_of_waiting(core, vault):
    """An ask nested in a writer operation (an audited macro's step) cannot
    wait - the writer is held - so its question stays open for the person."""
    sid = core.person_call("open_session", {"purpose": "explore", "question": "q"})["opened"]
    ctx = Context(tier="contribute", vault=vault, session=sid, extras=core._extras())
    started = time.monotonic()
    nested = core.writer.submit(lambda: REGISTRY.call("ask_user", {"question": "which?"}, ctx),
                                caller="macro")
    assert time.monotonic() - started < 2
    assert nested["needs_person"] is True and PERSON_WAIT not in nested
    assert not core.waiters._pending                          # nothing left listening
    assert SessionStore(vault).load(sid).open_questions()


def test_a_stop_releases_a_question_still_waiting(core, vault):
    sid = core.person_call("open_session", {"purpose": "explore", "question": "q"})["opened"]
    out = {}
    thread = threading.Thread(target=lambda: out.setdefault(
        "ask", core.person_call("ask_user", {"question": "which?"}, sid)))
    thread.start()
    time.sleep(0.5)
    started = time.monotonic()
    core.close_runtime()
    thread.join(10)
    assert time.monotonic() - started < 8
    assert out["ask"]["refused"] == "PERMISSION_UNANSWERED"      # parked, never answered for them
    stop = next(p for p in core.shutdown_phases if p["phase"] == "work_cancelled")
    assert stop["released_waits"] >= 1


def test_release_is_terminal_a_late_answer_wakes_nothing():
    waiters = Waiters(timeout=5)
    done = waiters.register("k")
    assert waiters.release_all() == 1 and done.is_set()
    assert waiters.answer("k", "too late") is False
    assert waiters.wait("k", done) is None
    assert waiters.register("again").is_set()                 # nothing new waits after a stop


def test_an_answer_delivered_just_before_the_stop_is_kept():
    """Delegate review (GLM-5.3, Qwen3.5): the stop cleared answers already
    delivered to a woken ask that had not yet collected it."""
    waiters = Waiters(timeout=5)
    done = waiters.register("k")
    assert waiters.answer("k", "in time") is True
    waiters.release_all()
    assert waiters.wait("k", done) == "in time"
