"""The development delegation runner must fail closed before any paid call."""
from __future__ import annotations

import importlib.util
import json
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
