"""A question waiting for a person must not hold the vault writer.

Found while routing MCP through the Core (2026-10-24), and reproduced on
master: in a coordinated Core every asking tool (ask_user, request_budget,
open_brief, promote_offering, capability_install) runs on the writer thread,
and the person's answer is itself a write.  The answer queued behind the
question until the question timed out - 600 s in the product - and the
thread was parked unanswered.
"""
import threading
import time

import pytest

from resource_librarian.app import App
from resource_librarian.coordination import VaultWriter, wait_for_person


@pytest.fixture
def core(vault):
    app = App(vault, coordinate=True, broker_timeout=20.0)
    yield app
    app.close_runtime()


def test_a_writer_waiting_for_a_person_keeps_serving_its_queue(vault):
    writer = VaultWriter(vault)
    answered = threading.Event()
    try:
        asking = threading.Thread(target=lambda: writer.submit(
            lambda: wait_for_person(answered, 10), caller="ask"))
        asking.start()
        time.sleep(0.1)
        started = time.monotonic()
        writer.submit(answered.set, caller="answer")            # queued behind the question
        asking.join(5)
        assert time.monotonic() - started < 2 and not asking.is_alive()
    finally:
        writer.close()


def test_off_the_writer_thread_it_is_an_ordinary_wait():
    event = threading.Event()
    threading.Timer(0.1, event.set).start()
    assert wait_for_person(event, 5) is True
    assert wait_for_person(threading.Event(), 0.1) is False


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
