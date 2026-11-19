"""Stop on a turn that is waiting for a person frees it (stress F-04, 2026-11-19).

`cancel_turn` only set a flag, so a turn blocked on a permission card or an `ask_user` question
stayed blocked until its timeout, holding "busy": Stop stayed on "Stopping…" and a new
conversation was refused with 409."""
import threading
import time
from types import SimpleNamespace

from resource_librarian import tools  # noqa: F401
from resource_librarian.app import App
from resource_librarian.keys import KeyStore
from resource_librarian.registry import REGISTRY, Context


def test_stop_releases_a_turn_waiting_on_a_permission_card(vault):
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=60)
    try:
        app.set_mode("ask")
        ctx = Context(tier="contribute", vault=vault, extras={"broker": app.broker})
        assert REGISTRY.call("open_session", {"purpose": "explore", "question": "q"}, ctx)["opened"]
        box = {}
        worker = threading.Thread(
            target=lambda: box.update(REGISTRY.call("queue_source", {"ref": "a/b"}, ctx)))
        worker.start()
        for _ in range(200):
            if app.broker.pending():
                break
            time.sleep(0.01)
        assert app.broker.pending(), "the write should be waiting on a person"
        # the chat turn this belongs to
        app.busy, app._turn_cancel = True, threading.Event()
        app.loop = SimpleNamespace(ctx=SimpleNamespace(session=ctx.session))
        assert app.cancel_turn() == {"cancelling": True}
        worker.join(5)
        assert not worker.is_alive(), "Stop left the turn waiting for its full timeout"
        assert box["refused"] == "PERMISSION_DENIED" and "stopped by a person" in box["detail"]
        assert app.broker.pending() == [] and app._turn_cancel.is_set()
    finally:
        app.busy, app._turn_cancel, app.loop = False, None, None
        app.close_runtime()
