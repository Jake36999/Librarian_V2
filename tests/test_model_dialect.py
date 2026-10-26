"""ADAPT-08: dialect vocabulary v1."""
import dataclasses
import pytest

from resource_librarian.model_invocation import (
    DIALECT_VOCABULARY,
    REASONING_RESERVE_TOKENS,
    ModelExpectation,
    ExpectationPackError,
    _check_record_fields,
    effective_dialect,
    InvocationPlan,
    InvocationPayload,
    apply_dialect,
    digest,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_expectation(**overrides) -> ModelExpectation:
    kwargs = {
        "id": "test",
        "version": "1",
        "status": "reviewed",
        "protocol": "openai",
        "adapter_id": "legacy_provider_chat",
        "adapter_abi": 1,
        "model_id": "gpt-4o",
        "host_id_or_family": "openai",
        "endpoint_fingerprint": "fp",
        "capabilities": (),
        "behavior_modes": ("provider_default",),
        "dialect": (),
        "source_url": "",
        "source_revision": "",
        "pack_id": "",
        "pack_fingerprint": "",
    }
    kwargs.update(overrides)
    return ModelExpectation(**kwargs)


def _make_plan(**overrides) -> InvocationPlan:
    kwargs = {
        "plan_id": "p1",
        "adapter_id": "legacy_provider_chat",
        "adapter_version": "1.0",
        "adapter_abi": 1,
        "protocol": "openai",
        "host_id": "openai",
        "endpoint_fingerprint": "fp",
        "model_id": "gpt-4o",
        "role": "assistant",
        "task_id": "t1",
        "task_kind": "chat",
        "interaction": "single",
        "phase": "main",
        "session_id": "s1",
        "output_contract": "text",
        "required_capabilities": (),
        "tool_schema_fingerprint": "",
        "max_output_tokens": 100,
        "behavior_mode": "provider_default",
        "reasoning_intent": "provider_default",
        "dialect": (),
        "expectation_id": "",
        "expectation_fingerprint": "",
    }
    kwargs.update(overrides)
    return InvocationPlan(**kwargs)


def _payload(**overrides) -> InvocationPayload:
    kwargs = {
        "system": "",
        "messages": ({"role": "assistant", "content": "hi", "reasoning_content": "think"},),
        "tools": (),
        "max_tokens": 100,
        "temperature": None,
    }
    kwargs.update(overrides)
    return InvocationPayload(**kwargs)


# ---------------------------------------------------------------------------
# pack loading rejects invalid dialect
# ---------------------------------------------------------------------------

def test_unknown_dimension_rejected_by_from_row():
    with pytest.raises(ValueError, match="unknown dialect dimension"):
        ModelExpectation.from_row(
            {"id": "e1", "dialect": {"no_such_dim": "provider_default"}},
            pack_id="p", pack_fingerprint="fp",
        )


def test_unsupported_value_rejected_by_from_row():
    with pytest.raises(ValueError, match="does not support"):
        ModelExpectation.from_row(
            {"id": "e1", "dialect": {"reasoning_replay": "invalid_value"}},
            pack_id="p", pack_fingerprint="fp",
        )


def test_non_object_dialect_rejected_by_from_row():
    with pytest.raises(ValueError, match="dialect is an object"):
        ModelExpectation.from_row(
            {"id": "e1", "dialect": "not_an_object"},
            pack_id="p", pack_fingerprint="fp",
        )


def test_unknown_dimension_rejected_by_check_record_fields():
    with pytest.raises(ExpectationPackError, match="unknown dialect dimension"):
        _check_record_fields({"id": "e1", "dialect": {"no_such_dim": "provider_default"}})


def test_unsupported_value_rejected_by_check_record_fields():
    with pytest.raises(ExpectationPackError, match="does not support"):
        _check_record_fields({"id": "e1", "dialect": {"reasoning_replay": "invalid_value"}})


def test_non_object_dialect_rejected_by_check_record_fields():
    with pytest.raises(ExpectationPackError, match="dialect is an object"):
        _check_record_fields({"id": "e1", "dialect": "not_an_object"})


# ---------------------------------------------------------------------------
# effective_dialect
# ---------------------------------------------------------------------------

def test_effective_dialect_defaults():
    assert effective_dialect(None) == {dim: "provider_default" for dim in DIALECT_VOCABULARY}


def test_effective_dialect_ignores_draft():
    exp = _make_expectation(status="draft", dialect=(("reasoning_replay", "never_replay"),))
    assert effective_dialect(exp)["reasoning_replay"] == "provider_default"


def test_effective_dialect_ignores_wildcard():
    exp = _make_expectation(model_id="*", dialect=(("reasoning_replay", "never_replay"),))
    assert effective_dialect(exp)["reasoning_replay"] == "provider_default"


def test_effective_dialect_applies_exact_reviewed():
    exp = _make_expectation(dialect=(("reasoning_replay", "never_replay"),))
    assert effective_dialect(exp)["reasoning_replay"] == "never_replay"


# ---------------------------------------------------------------------------
# fingerprint stability
# ---------------------------------------------------------------------------

def test_record_without_dialect_keeps_fingerprint():
    a = _make_expectation(dialect=())
    b = _make_expectation(dialect=(("tool_schema", "provider_default"),))
    # provider_default entries are dropped, so both records are identical.
    assert a.fingerprint == b.fingerprint


def test_record_with_empty_dialect_matches_no_dialect():
    a = _make_expectation(dialect=())
    # Construct a record that never had a dialect field by bypassing the
    # normal constructor (simulating an older record).
    b = _make_expectation()
    object.__setattr__(b, "dialect", ())
    # Recompute fingerprint as if dialect were absent.
    payload = {
        "id": b.id, "version": b.version, "status": b.status,
        "protocol": b.protocol, "adapter": b.adapter_id,
        "abi": b.adapter_abi, "model": b.model_id,
        "host": b.host_id_or_family, "endpoint": b.endpoint_fingerprint,
        "capabilities": b.capabilities, "behavior_modes": b.behavior_modes,
        "source": b.source_url, "revision": b.source_revision,
    }
    object.__setattr__(b, "fingerprint", digest(payload))
    assert a.fingerprint == b.fingerprint


# ---------------------------------------------------------------------------
# apply_dialect
# ---------------------------------------------------------------------------

def test_never_replay_strips_reasoning_content():
    plan = _make_plan(dialect=(("reasoning_replay", "never_replay"),))
    payload = _payload()
    result = apply_dialect(plan, payload)
    for msg in result.messages:
        assert "reasoning_content" not in msg


def test_replay_on_tool_turn_keeps_reasoning_content():
    plan = _make_plan(dialect=(("reasoning_replay", "replay_on_tool_turn"),))
    payload = _payload()
    result = apply_dialect(plan, payload)
    assert result.messages[0].get("reasoning_content") == "think"


def test_provider_default_keeps_reasoning_content():
    plan = _make_plan(dialect=())
    payload = _payload()
    result = apply_dialect(plan, payload)
    assert result.messages[0].get("reasoning_content") == "think"


def test_reasoning_reserve_adds_tokens():
    plan = _make_plan(dialect=(("output_headroom", "reasoning_reserve"),))
    payload = _payload()
    result = apply_dialect(plan, payload)
    assert result.max_tokens == 100 + REASONING_RESERVE_TOKENS


def test_deterministic_sets_temperature_when_unset():
    plan = _make_plan(dialect=(("sampling_profile", "deterministic"),))
    payload = _payload(temperature=None)
    result = apply_dialect(plan, payload)
    assert result.temperature == 0.0


def test_deterministic_does_not_override_explicit_temperature():
    plan = _make_plan(dialect=(("sampling_profile", "deterministic"),))
    payload = _payload(temperature=0.7)
    result = apply_dialect(plan, payload)
    assert result.temperature == 0.7


# ---------------------------------------------------------------------------
# config_hash stability
# ---------------------------------------------------------------------------

def test_plan_with_no_dialect_has_same_hash_as_dialect_empty_tuple():
    a = _make_plan(dialect=())
    b = _make_plan(dialect=())
    # Force recompute without dialect key by constructing the hash payload
    # manually and patching the field.
    payload = {
        "adapter": {"id": b.adapter_id, "version": b.adapter_version,
                    "abi": b.adapter_abi, "protocol": b.protocol},
        "route": {"host": b.host_id, "endpoint": b.endpoint_fingerprint,
                  "model": b.model_id},
        "scope": {"role": b.role, "task": b.task_id,
                  "kind": b.task_kind, "interaction": b.interaction,
                  "phase": b.phase, "output": b.output_contract,
                  "needs": b.required_capabilities},
        "tools": b.tool_schema_fingerprint,
        "limits": {"max_output_tokens": b.max_output_tokens},
        "behaviour": {"mode": b.behavior_mode, "reasoning": b.reasoning_intent},
        "expectation": {"id": b.expectation_id,
                        "fingerprint": b.expectation_fingerprint},
    }
    object.__setattr__(b, "config_hash", digest(payload))
    assert a.config_hash == b.config_hash
