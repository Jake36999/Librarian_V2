"""Vault-scoped canonical role-route binding persistence."""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from resource_librarian.role_routes import (RoleRouteBinding, RoleRouteStore,
                                            RoleRouteStoreError)


def route(role: str, host: str, model: str) -> RoleRouteBinding:
    return RoleRouteBinding(role=role, host_id=host, model_id=model, protocol="openai",
                            endpoint_fingerprint="f" * 64, adapter_id="openai_chat_v1",
                            evidence_kind="chat", source="explicit")


def inherited(role: str, target: str) -> RoleRouteBinding:
    return RoleRouteBinding(role=role, source="inherited", inherits_from=target)


def test_inheritance_tracks_an_updated_target_and_returns_the_requested_role(vault):
    store = RoleRouteStore(vault)
    store.initialize_if_absent({
        "lead": route("lead", "preset-openai", "lead-v1"),
        "scribe": inherited("scribe", "lead"),
        "clerk": inherited("clerk", "scribe"),
    })

    first = store.resolve("clerk")
    assert first is not None
    assert first.role == "clerk"
    assert (first.host_id, first.model_id) == ("preset-openai", "lead-v1")

    rows = store.raw()
    store.save({**rows, "lead": route("lead", "preset-openai", "lead-v2")})
    second = store.resolve("clerk")
    assert second is not None
    assert second.role == "clerk"
    assert second.model_id == "lead-v2"


def test_independently_selected_scribe_survives_a_lead_replacement(vault):
    store = RoleRouteStore(vault)
    store.save({
        "lead": route("lead", "preset-openai", "lead-a"),
        "scribe": route("scribe", "preset-deepinfra", "scribe-b"),
        "clerk": inherited("clerk", "scribe"),
    })

    rows = store.raw()
    store.save({**rows, "lead": replace(rows["lead"], model_id="lead-z", revision=2)})

    assert store.resolve("lead").model_id == "lead-z"
    assert store.resolve("scribe").model_id == "scribe-b"
    assert store.resolve("clerk").model_id == "scribe-b"


def test_reopen_preserves_only_non_secret_route_facts(vault):
    first = RoleRouteStore(vault)
    first.save({"lead": route("lead", "personal-host", "model-a")})

    reopened = RoleRouteStore(vault)
    binding = reopened.resolve("lead")
    assert binding == route("lead", "personal-host", "model-a")
    raw = (vault.librarian / "agents" / "routes.json").read_text(encoding="utf-8")
    assert "key" not in raw.casefold() and "secret" not in raw.casefold()


@pytest.mark.parametrize("payload", [
    {"schema_version": 1, "bindings": {"lead": {"role": "lead"}}},
    {"schema_version": 1, "bindings": {}, "extra": True},
    {"schema_version": 2, "bindings": {}},
])
def test_present_malformed_store_fails_closed(vault, payload):
    path = vault.librarian / "agents" / "routes.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RoleRouteStoreError):
        RoleRouteStore(vault).raw()


def test_cycle_and_missing_inherited_target_fail_closed(vault):
    store = RoleRouteStore(vault)
    with pytest.raises(RoleRouteStoreError, match="cycle"):
        store.save({"lead": inherited("lead", "scribe"),
                    "scribe": inherited("scribe", "lead")})
    with pytest.raises(RoleRouteStoreError, match="missing"):
        store.save({"clerk": inherited("clerk", "lead")})


def test_initialize_never_overwrites_an_existing_store(vault):
    store = RoleRouteStore(vault)
    store.save({"lead": route("lead", "one", "original")})

    result = store.initialize_if_absent({"lead": route("lead", "two", "replacement")})

    assert result["lead"].model_id == "original"
    assert store.resolve("lead").host_id == "one"


@pytest.mark.parametrize("revision", [True, 1.5, "1"])
def test_revision_requires_an_integer(vault, revision):
    with pytest.raises(RoleRouteStoreError, match="revision"):
        RoleRouteStore(vault).save({"lead": replace(route("lead", "host", "model"), revision=revision)})


def test_service_inheritance_and_partial_routes_are_rejected(vault):
    store = RoleRouteStore(vault)
    with pytest.raises(RoleRouteStoreError, match="service routes"):
        store.save({"lead": route("lead", "host", "model"), "ocr": inherited("ocr", "lead")})
    with pytest.raises(RoleRouteStoreError, match="host and exact model"):
        store.save({"lead": RoleRouteBinding(role="lead", host_id="host")})
