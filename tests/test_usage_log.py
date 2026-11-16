"""The Core keeps a durable, compact record of every model call's usage (owner pilot, 2026-11-16).

The pilot's spend could not be audited: the Core kept no per-call record, so the shared pool ledger
never saw it. Rows hold role, models, outcome and tokens, never prompts or hidden reasoning.
"""
import json

import pytest

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


# -- spend: OCR and cleanup calls, and a library ceiling ---------------------------------------

def test_record_call_adds_a_priced_row_and_spent_sums_it(vault):
    from resource_librarian import usage_log
    usage_log.record_call(vault, role="ocr", task="page", model="m", tokens_in=100, tokens_out=50, usd=0.003)
    usage_log.record_call(vault, role="ocr", task="page", model="m", usd=0.002)
    assert usage_log.spent_usd(vault) == pytest.approx(0.005)


def test_unpriced_tokens_are_priced_only_by_a_library_setting(vault):
    from resource_librarian import usage_log
    usage_log.record_call(vault, role="cleanup", task="pdf_to_markdown", model="m", tokens_in=1_000_000, tokens_out=500_000)
    assert usage_log.spent_usd(vault) == 0.0                           # unknown, never guessed
    vault.set_setting("budget", "cleanup_usd_per_mtok_in", 0.2)
    vault.set_setting("budget", "cleanup_usd_per_mtok_out", 0.8)
    assert usage_log.spent_usd(vault) == pytest.approx(0.2 + 0.4)


def test_the_ceiling_is_a_library_setting_and_blocks_when_reached(vault):
    from resource_librarian import usage_log
    assert usage_log.budget(vault) == {"ceiling_usd": None, "spent_usd": 0.0, "over": False}
    vault.set_setting("budget", "ceiling_usd", 0.004)
    usage_log.record_call(vault, role="ocr", task="page", model="m", usd=0.003)
    assert usage_log.budget(vault)["over"] is False
    usage_log.record_call(vault, role="ocr", task="page", model="m", usd=0.002)
    state = usage_log.budget(vault)
    assert state["over"] is True and state["ceiling_usd"] == 0.004


def test_ocr_pages_are_recorded_and_stop_at_the_ceiling(vault, tmp_path):
    from resource_librarian import clerk, ocr, tools  # noqa: F401
    from resource_librarian import usage_log
    from resource_librarian.registry import REGISTRY, Context
    from conftest import pdf_bytes
    (vault.root / "Inbox").mkdir(exist_ok=True)
    (vault.root / "Inbox" / "scan.pdf").write_bytes(pdf_bytes([[], [], [], []]))
    vault.set_setting("budget", "ceiling_usd", 0.0035)

    class Reader:
        name = "fake:ocr"
        concurrency = 1
        last_response = {}
        def page_text(self, png):
            self.last_response = {"usage": {"prompt_tokens": 10, "completion_tokens": 5, "estimated_cost": 0.002}}
            return "a page"
    ctx = Context(tier="curate", vault=vault, extras={"ocr_endpoint": Reader()})
    out = REGISTRY.call("ocr_pdf", {"file": "Inbox/scan.pdf"}, ctx)
    assert out["read"] == 2                                            # 0.002, 0.004 >= ceiling: stop
    assert any("budget" in str(e.get("error", "")).lower() for e in out["errors"])
    assert usage_log.spent_usd(vault) == pytest.approx(0.004)


def test_cleanup_calls_are_recorded_with_their_tokens(vault):
    from resource_librarian import pdf_markdown, tools, usage_log  # noqa: F401
    from resource_librarian.providers import Reply
    from resource_librarian.registry import REGISTRY, Context
    from conftest import pdf_bytes
    (vault.root / "Inbox").mkdir(exist_ok=True)
    (vault.root / "Inbox" / "t.pdf").write_bytes(pdf_bytes([["A page of real text."]]))

    class Endpoint:
        def chat(self, system, messages, tools, max_tokens=0):
            return Reply(text="# cleaned", usage={"input_tokens": 120, "output_tokens": 30})
    ctx = Context(tier="curate", vault=vault, extras={"pdf_endpoint": Endpoint()})
    out = REGISTRY.call("pdf_to_markdown", {"file": "Inbox/t.pdf"}, ctx)
    assert "error" not in out, out
    rows = [json.loads(t) for p in (vault.librarian / "runtime").glob("usage-*.jsonl")
            for t in p.read_text().splitlines()]
    assert [(r["role"], r["in"], r["out"]) for r in rows] == [("cleanup", 120, 30)]


def test_cleanup_refuses_over_the_ceiling(vault):
    from resource_librarian import tools, usage_log  # noqa: F401
    from resource_librarian.registry import REGISTRY, Context
    from conftest import pdf_bytes
    (vault.root / "Inbox").mkdir(exist_ok=True)
    (vault.root / "Inbox" / "u.pdf").write_bytes(pdf_bytes([["A page of real text."]]))
    vault.set_setting("budget", "ceiling_usd", 0.001)
    usage_log.record_call(vault, role="ocr", task="page", model="m", usd=0.002)
    out = REGISTRY.call("pdf_to_markdown", {"file": "Inbox/u.pdf"}, Context(tier="curate", vault=vault, extras={}))
    assert "error" in out and "budget" in str(out.get("detail", "")).lower()
