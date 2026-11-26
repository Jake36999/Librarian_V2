"""The permission envelope, asked once (implementation plan M2; plan-forward W1b item 5).

An agent asks once for every write a process will make; one answer grants each tool for the session,
as "allow for this session" grants one. What the Broker checks before a session grant still applies:
Deny and Ask tool settings, Plan mode and the always-ask tools.
"""
from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest

from resource_librarian import tools  # noqa: F401
from resource_librarian.app import App
from resource_librarian.broker import Broker
from resource_librarian.keys import KeyStore
from resource_librarian.registry import REGISTRY
from resource_librarian.rules import Refusal
from resource_librarian.session import SessionStore


def ctx(session="s1"):
    return SimpleNamespace(session=session, vault=None, extras={"caller_kind": "mcp"})


def answer_when_asked(broker, answer):
    def run():
        for _ in range(200):
            pending = broker.pending()
            if pending:
                broker.answer(pending[0]["id"], answer)
                return
            time.sleep(0.01)
    thread = threading.Thread(target=run)
    thread.start()
    return thread


def test_one_answer_grants_every_tool_for_the_session_and_nothing_is_asked_again():
    broker = Broker(mode="ask", timeout=5, harness=frozenset())
    helper = answer_when_asked(broker, "allow_once")
    out = broker.envelope("s1", {"write_note": "vault_write", "intake_run": "write"}, "the run", ctx())
    helper.join()
    assert out["outcome"] == "granted" and out["tools"] == ["intake_run", "write_note"]
    verdict = broker.check(REGISTRY.get("write_note"), {"folder": "Notes", "name": "x", "body": "y"}, ctx())
    assert verdict.startswith("allowed") and broker.pending() == []
    # Another session has no grant: it is asked (and, unanswered, refused).
    other = Broker(mode="ask", timeout=0.05, harness=frozenset())
    with pytest.raises(Refusal):
        other.check(REGISTRY.get("write_note"), {}, ctx("s2"))


def test_always_ask_and_deny_stay_outside_the_envelope():
    broker = Broker(mode="ask", tool_settings={"intake_run": "deny"}, timeout=5, harness=frozenset())
    helper = answer_when_asked(broker, "allow_session")
    out = broker.envelope("s1", {"project_edit": "write", "intake_run": "write", "write_note": "vault_write"},
                          "the run", ctx())
    helper.join()
    assert out["tools"] == ["write_note"]
    assert set(out["excluded"]) == {"project_edit", "intake_run"}
    with pytest.raises(Refusal, match="PERMISSION_DENIED"):
        broker.check(REGISTRY.get("intake_run"), {}, ctx())


def test_a_denied_envelope_grants_nothing():
    broker = Broker(mode="ask", timeout=5, harness=frozenset())
    helper = answer_when_asked(broker, "deny")
    with pytest.raises(Refusal, match="PERMISSION_DENIED"):
        broker.envelope("s1", {"write_note": "vault_write"}, "the run", ctx())
    helper.join()
    assert ("s1", "write_note") not in broker._session_grants


def test_plan_mode_refuses_and_auto_mode_neither_asks_nor_grants():
    with pytest.raises(Refusal, match="PERMISSION_DENIED"):
        Broker(mode="plan", harness=frozenset()).envelope("s1", {"write_note": "vault_write"}, "x", ctx())
    auto = Broker(mode="auto", harness=frozenset())
    out = auto.envelope("s1", {"write_note": "vault_write"}, "x", ctx())
    assert out["outcome"] == "not needed" and not auto._session_grants and not auto.pending()


@pytest.fixture
def core(vault):
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=5)
    app.set_mode("ask")
    yield app
    app.close_runtime()


def test_an_mcp_agent_asks_once_for_a_processs_writes(core):
    opened = core.mcp_call("open_session", {"purpose": "explore", "question": "envelope check"},
                           tier="contribute")
    session = opened["session"]
    assert session
    helper = answer_when_asked(core.broker, "allow_once")
    out = core.mcp_call("request_envelope", {"process": "clear-enrichment-backlog"}, session=session,
                        tier="contribute")["result"]
    helper.join()
    assert out["outcome"] == "granted", out
    assert {"intake_run", "staging_review", "staging_flag"} <= set(out["tools"])
    assert all((session, t) in core.broker._session_grants for t in out["tools"])
    events = [e for e in SessionStore(core.vault).events(session) if e.get("type") == "envelope"]
    assert events and events[-1]["process"] == "clear-enrichment-backlog"


def test_an_envelope_needs_a_session(core):
    out = core.mcp_call("request_envelope", {"tools": ["write_note"]}, tier="contribute")["result"]
    assert out["error"] == "invalid_arguments" and "open_session" in out["detail"]


def test_an_external_project_at_consult_tier_never_accepts_even_with_an_envelope(core):
    # The three contexts stay distinct (M2): an envelope grants permissions, never a tier.
    opened = core.mcp_call("open_session", {"purpose": "apply", "question": "external check"}, tier="consult")
    out = core.mcp_call("staging_decide", {"item_ids": ["anything"], "decision": "accept"},
                        session=opened["session"], tier="consult")["result"]
    assert out["refused"] == "TIER_REFUSED"
