"""CORE-02A: shutdown closes admission, cancels work, then releases resources.

Before this, `close_runtime` only flushed the writer: an active chat turn or
workflow was never told to stop, and nothing recorded how far a stop got.
"""
import json
import threading
import time

import pytest

from resource_librarian import connection
from resource_librarian.app import Action, ApiError, App
from resource_librarian.coordination import LeaseHeldError, VaultCoordinator

PHASES = ["admission_closed", "work_cancelled", "writer_drained", "index_closed",
          "lease_released"]


@pytest.fixture
def core(vault):
    app = App(vault, coordinate=True)
    yield app
    app.close_runtime()


def _phase(app, name):
    return next(p for p in app.shutdown_phases if p["phase"] == name)


def test_an_idle_stop_records_every_phase_and_releases_the_lease(core, vault):
    core.close_runtime()
    assert [p["phase"] for p in core.shutdown_phases] == PHASES
    assert _phase(core, "work_cancelled")["turn"] == "none"
    assert _phase(core, "writer_drained")["drained"] is True
    # Per-user Host state, not the vault: it is written after the lease is gone.
    record = json.loads(connection.shutdown_path(vault.root).read_text(encoding="utf-8"))
    assert [p["phase"] for p in record["phases"]] == PHASES
    assert not (vault.librarian / "runtime" / "shutdown.json").exists()
    # The lease is really gone: a new Core takes the vault without a takeover.
    successor = VaultCoordinator(vault)
    successor.acquire()
    successor.release()


def test_a_running_turn_is_cancelled_and_new_work_is_refused(core):
    cancel = threading.Event()
    with core._lock:
        core.busy, core._turn_cancel = True, cancel

    def turn():                       # a turn that stops at its next step boundary
        cancel.wait(5)
        with core._lock:
            core.busy = False
    threading.Thread(target=turn, daemon=True).start()
    core.close_runtime()
    assert cancel.is_set()
    assert _phase(core, "work_cancelled")["turn"] == "stopped"
    with pytest.raises(ApiError) as refused:
        core.chat("one more question")
    assert refused.value.status == 503


def test_a_turn_stuck_in_a_provider_call_does_not_hold_the_stop(core, monkeypatch):
    monkeypatch.setattr(App, "STOP_GRACE_SECONDS", 0.3)
    with core._lock:
        core.busy, core._turn_cancel = True, threading.Event()   # never clears
    started = time.monotonic()
    assert core.close_runtime() is False
    assert time.monotonic() - started < 3
    assert _phase(core, "work_cancelled")["turn"] == "still_running"
    assert core.shutdown_phases[-1]["phase"] == "shutdown_pending"
    assert core.shutdown_phases[-1]["reason"] == "admitted_work_still_running"
    assert core.coordinator.held
    # A stop may return promptly, but it must retain ownership while a turn
    # could still make a late mutation. Once the work has really stopped, a
    # retry completes the normal ordered teardown.
    with core._lock:
        core.busy, core._turn_cancel = False, None
    assert core.close_runtime() is True
    assert [p["phase"] for p in core.shutdown_phases] == [
        "admission_closed", "work_cancelled", "writer_drained", "shutdown_pending", *PHASES[2:]]


def test_running_actions_are_cancelled_and_new_ones_refused(core):
    action = Action("a1", "demo")
    core.actions[action.id] = action

    def run():
        action.cancel.wait(5)
        action.status = "cancelled"
    threading.Thread(target=run, daemon=True).start()
    core.close_runtime()
    assert action.cancel.is_set()
    assert _phase(core, "work_cancelled")["actions"] == {"a1": "cancelled"}
    with pytest.raises(ApiError) as refused:
        core.start_action("anything")
    assert refused.value.status == 503


def test_a_busy_writer_drains_before_the_index_and_lease_close(core, monkeypatch):
    order = []

    def slow():
        time.sleep(0.3)
        order.append("write finished")
    closing_index = core.index_service.close
    monkeypatch.setattr(core.index_service, "close",
                        lambda *a, **k: (order.append("index closed"), closing_index(*a, **k)))
    closing_lease = core.coordinator.release
    monkeypatch.setattr(core.coordinator, "release",
                        lambda *a, **k: (order.append("lease released"), closing_lease(*a, **k)))
    threading.Thread(target=lambda: core.writer.submit(slow, caller="test"), daemon=True).start()
    time.sleep(0.05)
    core.close_runtime()
    assert order == ["write finished", "index closed", "lease released"]
    assert _phase(core, "writer_drained")["drained"] is True


def test_a_timed_writer_drain_retains_the_index_and_lease_until_a_retry(core, vault, monkeypatch):
    """A writer timeout is not permission to hand the vault to a successor."""
    monkeypatch.setattr(App, "WRITER_STOP_SECONDS", 0.05)
    order, entered, release = [], threading.Event(), threading.Event()

    def slow():
        entered.set()
        assert release.wait(5)
        order.append("write finished")

    closing_index = core.index_service.close
    monkeypatch.setattr(core.index_service, "close",
                        lambda *a, **k: (order.append("index closed"), closing_index(*a, **k)))
    closing_lease = core.coordinator.release
    monkeypatch.setattr(core.coordinator, "release",
                        lambda *a, **k: (order.append("lease released"), closing_lease(*a, **k)))
    writer_call = threading.Thread(target=lambda: core.writer.submit(slow, caller="long-test"), daemon=True)
    writer_call.start()
    assert entered.wait(2)

    assert core.close_runtime() is False
    assert order == []
    assert _phase(core, "writer_drained")["drained"] is False
    assert core.shutdown_phases[-1]["phase"] == "shutdown_pending"
    assert core.shutdown_phases[-1]["reason"] == "writer_still_running"
    assert core.coordinator.held
    health = core.meta()["non_secret_health"]
    assert health["vault_lease"] == "held"
    assert health["writer"] == "draining"
    assert health["shutdown"]["state"] == "pending"

    successor = VaultCoordinator(vault)
    with pytest.raises(LeaseHeldError):
        successor.acquire()

    release.set()
    writer_call.join(5)
    assert not writer_call.is_alive()
    assert core.close_runtime() is True
    assert order == ["write finished", "index closed", "lease released"]
    successor.acquire()
    successor.release()


def test_an_admitted_configuration_mutation_stays_counted_until_its_writer_work_finishes(core, vault,
                                                                                            monkeypatch):
    """The admission count spans the writer operation, not just its enqueue."""
    monkeypatch.setattr(App, "STOP_GRACE_SECONDS", 0.05)
    monkeypatch.setattr(App, "WRITER_STOP_SECONDS", 0.05)
    entered, release, out = threading.Event(), threading.Event(), {}
    update = core.settings.update_in_operation

    def slow_update(**changes):
        entered.set()
        assert release.wait(5)
        return update(**changes)

    monkeypatch.setattr(core.settings, "update_in_operation", slow_update)
    change = threading.Thread(target=lambda: out.setdefault(
        "result", core.set_context(working_context="admitted before shutdown")), daemon=True)
    change.start()
    assert entered.wait(2)

    assert core.close_runtime() is False
    pending = core.shutdown_phases[-1]
    assert pending["phase"] == "shutdown_pending"
    # Once the active writer misses its own bounded drain, that is the
    # concrete reason final teardown remains pending (the mutation is still
    # counted too, so neither the index nor lease can be released).
    assert pending["reason"] == "writer_still_running"
    assert pending["writer_drained"] is False
    assert pending["mutations"] >= 1
    assert core.coordinator.held
    successor = VaultCoordinator(vault)
    with pytest.raises(LeaseHeldError):
        successor.acquire()

    release.set()
    change.join(5)
    assert not change.is_alive()
    assert out["result"]["working_context"] == "admitted before shutdown"
    assert core.close_runtime() is True


def test_an_admitted_reply_review_keeps_the_vault_until_its_background_write_finishes(
        core, vault, monkeypatch):
    """A completed chat turn's review is still Core-owned mutable work."""
    from types import SimpleNamespace
    from resource_librarian import reply_review

    monkeypatch.setattr(App, "STOP_GRACE_SECONDS", 0.05)
    entered, release = threading.Event(), threading.Event()
    monkeypatch.setattr(reply_review, "enabled", lambda _vault: True)

    def slow_review(*_args, **_kwargs):
        entered.set()
        assert release.wait(5)
        return {"held": 0, "unchecked": 0, "challenged": []}

    monkeypatch.setattr(reply_review, "review_reply", slow_review)
    core._review_reply(SimpleNamespace(challenges=[]), "[[a linked note]]")
    assert entered.wait(2)

    assert core.close_runtime() is False
    pending = core.shutdown_phases[-1]
    assert pending["phase"] == "shutdown_pending"
    assert pending["reason"] == "admitted_work_still_running"
    assert pending["mutations"] >= 1
    successor = VaultCoordinator(vault)
    with pytest.raises(LeaseHeldError):
        successor.acquire()

    release.set()
    deadline = time.monotonic() + 5
    while core._shutdown_health()["active_mutations"] and time.monotonic() < deadline:
        time.sleep(0.01)
    assert core._shutdown_health()["active_mutations"] == 0
    assert core.close_runtime() is True


def test_a_reply_review_does_not_start_after_shutdown_admission_closes(core, monkeypatch):
    """The post-turn thread cannot enqueue Clerk work after a stop begins."""
    from types import SimpleNamespace
    from resource_librarian import reply_review

    started = threading.Event()
    monkeypatch.setattr(reply_review, "enabled", lambda _vault: True)
    monkeypatch.setattr(reply_review, "review_reply", lambda *_args, **_kwargs: started.set())
    with core._lock:
        core._admitting = False

    core._review_reply(SimpleNamespace(challenges=[]), "[[a linked note]]")
    assert not started.wait(0.1)


def test_direct_configuration_offering_and_checkpoint_mutations_refuse_after_admission_closes(core):
    """Direct App callers receive the same lifecycle refusal as HTTP clients."""
    with core._lock:
        core._admitting = False
    for mutate in (
        lambda: core.set_context(working_context="too late"),
        lambda: core.decide_offering("not-an-offering", "decline"),
        lambda: core.checkpoint_create("review", "late"),
    ):
        with pytest.raises(ApiError) as refused:
            mutate()
        assert refused.value.status == 503


def test_an_action_registered_as_the_stop_begins_is_still_cancelled(core):
    """Reviewer finding (GLM-5.3, CORE-02A): a single snapshot of running
    actions missed one registered just before admission closed."""
    late = Action("late", "demo")

    def register_then_run():
        time.sleep(0.1)
        core.actions[late.id] = late
        late.cancel.wait(5)
        late.status = "cancelled"
    blocker = threading.Event()
    with core._lock:
        core.busy, core._turn_cancel = True, blocker

    def turn():
        blocker.wait(5)
        time.sleep(0.3)                # still busy while the late action appears
        with core._lock:
            core.busy = False
    threading.Thread(target=register_then_run, daemon=True).start()
    threading.Thread(target=turn, daemon=True).start()
    core.close_runtime()
    assert late.cancel.is_set()
    assert _phase(core, "work_cancelled")["actions"] == {"late": "cancelled"}


def test_the_outside_server_manager_is_stopped_by_its_owner_only(vault):
    class Manager:
        stopped = 0

        def attach_broker(self, broker): ...
        def use_library(self, path): ...
        def sync(self): ...

        def stop(self):
            Manager.stopped += 1
    shared = Manager()
    retiring = App(vault, mcp=shared)       # a library switch hands the manager on
    successor = App(vault, mcp=shared)
    retiring.close_runtime()
    assert Manager.stopped == 0             # the successor still uses it
    successor.close_runtime()
    assert Manager.stopped == 1


def test_a_second_close_is_a_no_op(core):
    core.close_runtime()
    phases = list(core.shutdown_phases)
    core.close_runtime()
    assert core.shutdown_phases == phases


def test_a_thread_cut_off_by_the_stop_reopens_parked_and_resumable(vault):
    """CORE-02B: the interrupted state is durable, and resume_session continues it."""
    from types import SimpleNamespace
    from resource_librarian.registry import REGISTRY, Context
    from resource_librarian.session import SessionStore
    core = App(vault, coordinate=True)
    opened = SessionStore(vault).new("explore", question="q")
    SessionStore(vault).append(opened.id, {"type": "message", "role": "user", "text": "work so far"})
    core.loop = SimpleNamespace(ctx=SimpleNamespace(session=opened.id))
    cancel = threading.Event()
    with core._lock:
        core.busy, core._turn_cancel = True, cancel

    def turn():
        cancel.wait(5)
        with core._lock:
            core.busy = False
    threading.Thread(target=turn, daemon=True).start()
    core.close_runtime()
    assert _phase(core, "session_parked")["session"] == opened.id
    parked = SessionStore(vault).load(opened.id)
    assert parked.status == "parked"
    assert [m["text"] for m in parked.messages] == ["work so far"]     # committed work intact
    successor = App(vault, coordinate=True)
    try:
        ctx = Context(tier="consult", vault=vault, extras=successor._extras())
        resumed = REGISTRY.call("resume_session", {"session_id": opened.id}, ctx)
        assert "error" not in resumed, resumed
        assert SessionStore(vault).load(opened.id).status == "open"
    finally:
        successor.close_runtime()


def test_an_idle_open_thread_is_left_open(core, vault):
    from types import SimpleNamespace
    from resource_librarian.session import SessionStore
    opened = SessionStore(vault).new("explore", question="q")
    core.loop = SimpleNamespace(ctx=SimpleNamespace(session=opened.id))
    core.close_runtime()                       # no turn was running
    assert SessionStore(vault).load(opened.id).status == "open"
    assert "session_parked" not in [p["phase"] for p in core.shutdown_phases]


# -- late work against a stopping Core (review, 2026-10-24) -------------------

def test_a_person_call_after_the_stop_is_refused(core):
    core.close_runtime()
    with pytest.raises(ApiError) as refused:
        core.person_call("session_status", {})
    assert refused.value.status == 503


def test_a_permission_asked_after_the_stop_is_refused_at_once(core, vault):
    """The broker is terminal: a call admitted just before the stop that only
    now reaches its permission check is not left waiting for nobody."""
    from resource_librarian.registry import REGISTRY, Context
    core.broker.set_mode("ask")
    core.broker.close("the Core is stopping")
    ctx = Context(tier="contribute", vault=vault,
                  extras={"broker": core.broker, "vault_writer": core.writer})
    started = time.monotonic()
    result = REGISTRY.call("gitignore_ensure", {"patterns": ["scratch/"]}, ctx)
    assert time.monotonic() - started < 2
    assert result.get("refused") == "PERMISSION_UNANSWERED", result


def test_an_mcp_call_waiting_on_a_permission_drains_before_the_writer_closes(core, vault):
    """An admitted MCP call holds no writer while it waits on the broker; the
    stop expires its request and waits for the call to return before closing
    the writer under it."""
    core.broker.set_mode("ask")
    out = {}
    thread = threading.Thread(target=lambda: out.setdefault(
        "call", core.mcp_call("gitignore_ensure", {"patterns": ["scratch/"]},
                              tier="contribute")))
    thread.start()
    deadline = time.monotonic() + 5
    while not core.broker.pending() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert core.broker.pending(), "the MCP call never reached its permission check"
    assert core.running().get("mcp_calls") == 1
    core.close_runtime()
    thread.join(5)
    assert not thread.is_alive()
    assert out["call"]["result"]["refused"] == "PERMISSION_UNANSWERED"
    assert _phase(core, "work_cancelled")["calls_still_running"] == {}
    assert _phase(core, "work_cancelled")["released_waits"] >= 1
