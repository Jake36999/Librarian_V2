"""Offline guardrails for the bounded DeepInfra validation harness."""
from __future__ import annotations

import json
import importlib.util
import sys
from pathlib import Path

import pytest

from resource_librarian import providers
from resource_librarian.providers import ProviderError


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_deepinfra_current.py"
_SPEC = importlib.util.spec_from_file_location("deepinfra_validation_harness", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
validation = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = validation
_SPEC.loader.exec_module(validation)


KNOWN_MODEL = "XiaomiMiMo/MiMo-V2.6-Flash"
DEEPINFRA_CHAT = "https://api.deepinfra.com/v1/openai/chat/completions"


def _chat_body(model: str = KNOWN_MODEL) -> dict[str, object]:
    return {
        "model": model,
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": "bounded offline meter test"}],
    }


def test_meter_refuses_an_unpriced_model_while_a_cap_is_active(monkeypatch):
    called = []

    def original(*args, **kwargs):
        called.append((args, kwargs))
        return {"choices": [{"message": {}}]}

    monkeypatch.setattr(providers, "_request", original)
    with validation.RequestMeter(0.01):
        with pytest.raises(validation.BudgetStop, match="cannot price"):
            providers._request("POST", DEEPINFRA_CHAT, {}, _chat_body("unpriced/model"))

    assert called == []


def test_meter_keeps_a_reserve_when_usage_is_missing(monkeypatch):
    calls = []

    def original(method, url, headers, body=None, timeout=120, sleep=None):
        calls.append(body)
        return {"choices": [{"message": {}, "finish_reason": "stop"}]}

    monkeypatch.setattr(providers, "_request", original)
    meter = validation.RequestMeter(0.0004)
    with meter:
        providers._request("POST", DEEPINFRA_CHAT, {}, _chat_body())
        with pytest.raises(validation.BudgetStop, match="would be exceeded"):
            providers._request("POST", DEEPINFRA_CHAT, {}, _chat_body())

    assert len(calls) == 1
    assert meter.actual_cost_usd == 0.0
    assert meter.budget_committed_usd > 0
    assert meter.records[0]["budget_charge_usd"] > 0


def test_local_fixture_or_setup_exception_is_not_counted_as_a_model_failure(tmp_path):
    meter = validation.RequestMeter(1)
    runner = validation.Validation(scratch_root=tmp_path, meter=meter, l1_repeats=1, host_timeout=1)

    def broken_fixture():
        raise RuntimeError("fixture does not match the vault schema")

    row = runner.case("example/model", "grounded_read_walk", 1, broken_fixture)

    assert row["status"] == "harness_error"
    assert row["classification"] == "local_setup"
    assert row["provider_requests"] == 0


def test_discovery_failure_skips_paid_model_cases_by_default(tmp_path, monkeypatch):
    class ListingUnavailable:
        def __init__(self, *args, **kwargs):
            pass

        def models(self):
            raise ProviderError("local transport unavailable")

    class NeverRunValidation:
        calls = 0

        def __init__(self, *args, **kwargs):
            self.cases = []

        def case(self, *args, **kwargs):
            type(self).calls += 1
            raise AssertionError("model cases must not run after failed discovery")

    output = tmp_path / "validation.json"
    monkeypatch.setattr(validation, "provision_key", lambda _path: "test")
    monkeypatch.setattr(validation, "OpenAICompatible", ListingUnavailable)
    monkeypatch.setattr(validation, "Validation", NeverRunValidation)
    monkeypatch.setattr("sys.argv", [
        "validate_deepinfra_current.py", "--models", KNOWN_MODEL,
        "--output", str(output),
    ])

    assert validation.main() == 0

    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert NeverRunValidation.calls == 0
    assert artifact["availability"]["listing_ok"] is False
    assert artifact["availability"]["model_cases_skipped"] is True
    assert artifact["availability"]["skip_reason"] == "model_discovery_unavailable"
