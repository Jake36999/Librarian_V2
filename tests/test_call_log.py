"""The Core records every outside call into it (implementation plan M0: baselines).

Tier 0's cost could not be measured from the Core's side: nothing recorded the calls a tier-0 agent
made, what came back to it, or how many were refused. Rows hold the surface, tool, outcome, time and
result size, never arguments or result content.
"""
import json

import pytest

from resource_librarian import tools  # noqa: F401
from resource_librarian.app import App
from resource_librarian.call_log import CallLog, outcome_of
from resource_librarian.init import init
from resource_librarian.keys import KeyStore
from resource_librarian.vault import Vault


def _rows(log):
    return [json.loads(line) for line in log.today_path().read_text(encoding="utf-8").splitlines()]


def test_outcome_names_the_refusal_or_error():
    assert outcome_of({"found": True}) == "ok"
    assert outcome_of({"error": "refused", "refused": "TIER_REFUSED"}) == "TIER_REFUSED"
    assert outcome_of({"error": "invalid_arguments"}) == "invalid_arguments"
    assert outcome_of(["not", "a", "dict"]) == "ok"


def test_rows_are_compact_and_carry_no_arguments_or_content(tmp_path):
    vault = Vault(tmp_path / "lib"); init(vault.root, name="lib")
    log = CallLog(vault)
    log.record(surface="mcp", tool="get_note", started=0.0, session="s1",
               result={"found": True, "body": "SECRET BODY TEXT"})
    [row] = _rows(log)
    assert row["surface"] == "mcp" and row["tool"] == "get_note" and row["outcome"] == "ok"
    assert row["session"] == "s1" and row["bytes"] > 0
    assert "SECRET" not in log.today_path().read_text(encoding="utf-8")


def test_logging_never_breaks_a_call(tmp_path):
    vault = Vault(tmp_path / "lib"); init(vault.root, name="lib")
    log = CallLog(vault)
    (vault.librarian / "runtime").mkdir(parents=True, exist_ok=True)
    log.today_path().mkdir()                         # a directory where the file should be
    log.record(surface="mcp", tool="x", started=0.0, result={"ok": True})   # does not raise


def test_summary_counts_calls_refusals_and_result_size_per_surface(tmp_path):
    vault = Vault(tmp_path / "lib"); init(vault.root, name="lib")
    log = CallLog(vault)
    log.record(surface="mcp", tool="a", started=0.0, result={"x": "y" * 400})
    log.record(surface="mcp", tool="b", started=0.0, result={"error": "refused", "refused": "PERMISSION_DENIED"})
    log.record(surface="agent-api", tool="c", started=0.0, result={}, agent="codex")
    summary = log.summary()
    assert summary["mcp"]["calls"] == 2 and summary["mcp"]["refused"] == 1
    assert summary["mcp"]["result_tokens"] >= 100
    assert summary["agent-api|codex"]["calls"] == 1
    assert log.summary(since="2999-01-01") == {}


@pytest.fixture
def core(vault):
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=5)
    app.broker.set_mode("auto")
    yield app
    app.close_runtime()


def test_mcp_person_and_declared_agent_calls_are_each_recorded(core):
    core.mcp_call("get_note", {"name": "Nothing here"}, tier="contribute")
    core.person_call("get_note", {"name": "Nothing here"})
    core.person_call("get_note", {"name": "Nothing here"}, actor={"kind": "agent", "name": "tier0-test"})
    rows = _rows(core.call_log)
    assert [r["surface"] for r in rows] == ["mcp", "person", "agent-api"]
    assert all(r["tool"] == "get_note" for r in rows)
    assert rows[2]["agent"] == "tier0-test"
