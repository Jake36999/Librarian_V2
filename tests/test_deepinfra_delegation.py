"""The development delegation runner must fail closed before any paid call."""
from __future__ import annotations

import importlib.util
import json
import os
import time
from argparse import Namespace
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "delegate_deepinfra.py"
SPEC = importlib.util.spec_from_file_location("delegate_deepinfra", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
delegate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(delegate)


def test_export_is_repository_confined_and_secret_scanned(tmp_path, monkeypatch):
    repository = tmp_path / "repo"
    repository.mkdir()
    safe = repository / "safe.py"
    safe.write_text("answer = 42\n", encoding="utf-8")
    secret = repository / "secret.py"
    secret.write_text('api_key = "this-is-a-secret-value"\n', encoding="utf-8")
    outside = tmp_path / "outside.py"
    outside.write_text("outside = True\n", encoding="utf-8")
    monkeypatch.setattr(delegate, "REPOSITORY", repository)

    assert delegate.resolve_export("safe.py") == safe.resolve()
    with pytest.raises(SystemExit, match="outside the repository"):
        delegate.resolve_export(str(outside))
    with pytest.raises(SystemExit, match="possible secret"):
        delegate.checked_text(secret, max_bytes=10_000)


def test_packet_manifest_hashes_exact_exported_bytes(tmp_path, monkeypatch):
    repository = tmp_path / "repo"
    repository.mkdir()
    source = repository / "module.py"
    source.write_bytes(b"value = 1\n")
    monkeypatch.setattr(delegate, "REPOSITORY", repository)
    args = Namespace(file=["module.py"], max_file_bytes=1000,
                     max_packet_bytes=1000, instruction="Review it.",
                     task="test-task", lens="correctness")

    payload, manifest = delegate.packet(args)

    assert '<file path="module.py">' in payload
    assert manifest == [{"path": "module.py", "bytes": 10,
                         "sha256": delegate.sha256(b"value = 1\n")}]


def test_existing_budget_ledger_cannot_silently_change_ceilings(tmp_path):
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"budget_usd": 10, "committed_usd": 1, "calls": []}),
                      encoding="utf-8")
    with pytest.raises(SystemExit, match=r"not requested \$12.00"):
        delegate.read_ledger(ledger, 12.0)


def test_preflight_reserve_uses_pinned_input_and_maximum_output_rates():
    body = {"max_tokens": 1000, "messages": [{"role": "user", "content": "x" * 3500}]}
    card = {"input_per_1m": 1.0, "output_per_1m": 2.0}

    input_guess, reserve = delegate.reserve_cost(body, card)

    assert input_guess >= 1000
    assert reserve >= 0.003


def test_ledger_concurrency_two_interleaved_invocations(tmp_path):
    """Two simulated invocations leave both entries and correct committed_usd."""
    ledger_path = tmp_path / "ledger.json"
    budget = 10.0
    # Initialise empty ledger.
    delegate.atomic_json(ledger_path, {"schema": 1, "budget_usd": budget, "committed_usd": 0.0, "calls": []})

    run_id_a = "20260101T000000-aaaa"
    run_id_b = "20260101T000001-bbbb"
    entry_a = {"run_id": run_id_a, "task": "a", "agent": "claude", "status": "started", "charged_usd": 0.5}
    entry_b = {"run_id": run_id_b, "task": "b", "agent": "chatgpt", "status": "started", "charged_usd": 0.3}

    # Reserve both.
    delegate.reserve_call(ledger_path, budget, run_id_a, entry_a, 0.5, 1.0)
    delegate.reserve_call(ledger_path, budget, run_id_b, entry_b, 0.3, 1.0)

    # Settle both.
    delegate.settle_call(ledger_path, budget, run_id_a, "completed", 0.4, 0.5, "receipt_a.json")
    delegate.settle_call(ledger_path, budget, run_id_b, "completed", 0.2, 0.3, "receipt_b.json")

    ledger = delegate.read_ledger(ledger_path, budget)
    assert len(ledger["calls"]) == 2
    assert ledger["committed_usd"] == pytest.approx(0.6)
    call_a = next(c for c in ledger["calls"] if c["run_id"] == run_id_a)
    call_b = next(c for c in ledger["calls"] if c["run_id"] == run_id_b)
    assert call_a["status"] == "completed"
    assert call_a["charged_usd"] == 0.4
    assert call_b["status"] == "completed"
    assert call_b["charged_usd"] == 0.2


def test_budget_check_under_lock_refuses_excess_reserve(tmp_path):
    """A reserve that would exceed budget after another committed entry is refused."""
    ledger_path = tmp_path / "ledger.json"
    budget = 1.0
    delegate.atomic_json(ledger_path, {"schema": 1, "budget_usd": budget, "committed_usd": 0.0, "calls": []})

    run_id_a = "20260101T000000-aaaa"
    run_id_b = "20260101T000001-bbbb"
    entry_a = {"run_id": run_id_a, "task": "a", "agent": "claude", "status": "started", "charged_usd": 0.8}
    entry_b = {"run_id": run_id_b, "task": "b", "agent": "chatgpt", "status": "started", "charged_usd": 0.5}

    delegate.reserve_call(ledger_path, budget, run_id_a, entry_a, 0.8, 1.0)
    with pytest.raises(SystemExit, match="exceed total budget"):
        delegate.reserve_call(ledger_path, budget, run_id_b, entry_b, 0.5, 1.0)


def test_stale_lock_broken_fresh_lock_times_out(tmp_path, monkeypatch):
    """A lock older than 120 s is broken; a fresh one raises SystemExit after timeout."""
    ledger_path = tmp_path / "ledger.json"
    lock_path = ledger_path.with_suffix(ledger_path.suffix + ".lock")
    delegate.atomic_json(ledger_path, {"schema": 1, "budget_usd": 10.0, "committed_usd": 0.0, "calls": []})

    # Create a stale lock.
    lock_path.write_text("stale")
    stale_mtime = time.time() - 200
    os.utime(str(lock_path), (stale_mtime, stale_mtime))

    # Should succeed by breaking the stale lock.
    with delegate.ledger_lock(ledger_path, timeout=1):
        pass
    assert not lock_path.exists()

    # Create a fresh lock and try to acquire with a very short timeout.
    lock_path.write_text("fresh")
    with pytest.raises(SystemExit, match="Could not acquire ledger lock"):
        with delegate.ledger_lock(ledger_path, timeout=0.1):
            pass
    # Clean up.
    lock_path.unlink(missing_ok=True)


def test_instruction_file_read_and_secret_scanned(tmp_path, monkeypatch):
    """--instruction-file is read and secret-scanned; both/neither fails."""
    repository = tmp_path / "repo"
    repository.mkdir()
    monkeypatch.setattr(delegate, "REPOSITORY", repository)

    inst_file = tmp_path / "instruction.txt"
    inst_file.write_text("Review the code.", encoding="utf-8")

    # Both --instruction and --instruction-file should fail.
    with pytest.raises(SystemExit):
        delegate.parse_args(["--task", "t", "--model", "deepseek-ai/DeepSeek-V4.1-Flash-1017",
                             "--instruction", "x", "--instruction-file", str(inst_file)])

    # Neither should fail.
    with pytest.raises(SystemExit):
        delegate.parse_args(["--task", "t", "--model", "deepseek-ai/DeepSeek-V4.1-Flash-1017"])

    # Valid --instruction-file.
    args = delegate.parse_args(["--task", "t", "--model", "deepseek-ai/DeepSeek-V4.1-Flash-1017",
                                "--instruction-file", str(inst_file)])
    assert args.instruction_file == inst_file

    # Secret in instruction file.
    secret_file = tmp_path / "secret_instruction.txt"
    secret_file.write_text('api_key = "this-is-a-secret-value"', encoding="utf-8")
    args = delegate.parse_args(["--task", "t", "--model", "deepseek-ai/DeepSeek-V4.1-Flash-1017",
                                "--instruction-file", str(secret_file)])
    monkeypatch.setattr(delegate, "parse_args", lambda: args)
    with pytest.raises(SystemExit, match="possible secret"):
        delegate.main()  # reads the file and scans it before any call


def test_main_makes_exactly_one_provider_request(tmp_path, monkeypatch):
    """main() calls _request exactly once with retries=()."""
    repository = tmp_path / "repo"
    repository.mkdir()
    monkeypatch.setattr(delegate, "REPOSITORY", repository)
    monkeypatch.setattr(delegate, "DEFAULT_LEDGER", tmp_path / "ledger.json")
    monkeypatch.setattr(delegate, "DEFAULT_OUTPUT_DIR", tmp_path / "runs")
    monkeypatch.setattr(delegate, "DEFAULT_KEY_FILE", tmp_path / ".env")
    monkeypatch.setenv("DEEPINFRA_API_KEY", "fake-key")

    call_count = 0

    def fake_request(method, url, headers, body, timeout, retries):
        nonlocal call_count
        call_count += 1
        assert retries == ()
        return {
            "model": "deepseek-ai/DeepSeek-V4.1-Flash-1017",
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2},
        }

    monkeypatch.setattr(delegate.providers, "_request", fake_request)

    # We need to bypass argparse and call main logic directly, or simulate argv.
    # Simulate by calling the internal functions with a crafted Namespace.
    args = Namespace(
        task="test",
        lens="correctness",
        model="deepseek-ai/DeepSeek-V4.1-Flash-1017",
        instruction="Hello",
        instruction_file=None,
        file=[],
        max_output_tokens=100,
        temperature=0.1,
        timeout=10,
        call_cap_usd=1.0,
        total_budget_usd=10.0,
        ledger=tmp_path / "ledger.json",
        output_dir=tmp_path / "runs",
        key_file=tmp_path / ".env",
        max_file_bytes=500_000,
        max_packet_bytes=1_500_000,
        dry_run=False,
        agent="test-agent",
    )
    # Patch parse_args to return our crafted args.
    monkeypatch.setattr(delegate, "parse_args", lambda: args)

    exit_code = delegate.main()
    assert exit_code == 0
    assert call_count == 1
