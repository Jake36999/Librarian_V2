"""The Core keeps a durable, compact record of every model call's usage (owner pilot, 2026-11-16).

The pilot's spend could not be audited: the Core kept no per-call record, so the shared pool ledger
never saw it. Rows hold role, models, outcome and tokens, never prompts or hidden reasoning.
"""
import json

from resource_librarian.init import init
from resource_librarian.vault import Vault

ROW = {"plan": {"plan_id": "p1", "route": {"host_id": "preset-deepinfra", "requested_model": "google/gemma-4-26B-A4B-it"},
                "scope": {"role": "clerk", "task_kind": "claims", "task_id": "t1"}, "max_output_tokens": 500},
       "compatibility": {"accepted": True}, "result": {
           "requested_model": "google/gemma-4-26B-A4B-it", "observed_model": "google/gemma-4-26B-A4B-it",
           "outcome": "ok", "elapsed_ms": 1234,
           "telemetry": {"usage": {"prompt_tokens": 1500, "completion_tokens": 300, "total_tokens": 1800}}}}


def test_rows_are_compact_and_carry_no_prompt_text(tmp_path):
    from resource_librarian.usage_log import UsageLog
    vault = Vault(tmp_path / "lib"); init(vault.root, name="lib")
    log = UsageLog(vault)
    log.record(ROW)
    rows = [json.loads(line) for line in log.today_path().read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    row = rows[0]
    assert row["role"] == "clerk" and row["task"] == "claims" and row["host"] == "preset-deepinfra"
    assert row["model"] == "google/gemma-4-26B-A4B-it" and row["outcome"] == "ok" and row["ms"] == 1234
    assert (row["in"], row["out"]) == (1500, 300) and row["ts"]
    assert len(json.dumps(row)) < 400


def test_unavailable_usage_is_recorded_as_unknown_not_zero(tmp_path):
    from resource_librarian.usage_log import UsageLog
    vault = Vault(tmp_path / "lib"); init(vault.root, name="lib")
    bad = json.loads(json.dumps(ROW)); bad["result"]["telemetry"]["usage"] = "unavailable"
    UsageLog(vault).record(bad)
    row = json.loads(UsageLog(vault).today_path().read_text(encoding="utf-8").splitlines()[0])
    assert row["in"] is None and row["out"] is None


def test_summary_totals_tokens_by_model_and_role(tmp_path):
    from resource_librarian.usage_log import UsageLog
    vault = Vault(tmp_path / "lib"); init(vault.root, name="lib")
    log = UsageLog(vault)
    for _ in range(3):
        log.record(ROW)
    total = log.summary()
    key = "clerk|google/gemma-4-26B-A4B-it"
    assert total[key] == {"calls": 3, "in": 4500, "out": 900, "unknown": 0}


def test_a_failing_log_never_breaks_a_model_call(tmp_path):
    from resource_librarian.usage_log import UsageLog
    vault = Vault(tmp_path / "lib"); init(vault.root, name="lib")
    log = UsageLog(vault)
    log.record({"not": "a trace row"})              # must not raise


def test_the_core_wires_its_runtime_to_the_vault_log(tmp_path):
    from resource_librarian.app import App
    from resource_librarian.keys import KeyStore
    vault = Vault(tmp_path / "lib"); init(vault.root, name="lib")
    app = App(vault, token="t", keys=KeyStore(use_keyring=False))
    try:
        assert callable(app.invocation_runtime.trace_sink)
        app.invocation_runtime.trace_sink(ROW)
        assert list((vault.librarian / "runtime").glob("usage-*.jsonl"))
    finally:
        app.close_runtime()
