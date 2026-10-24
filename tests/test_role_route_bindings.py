"""The existing picker persists canonical, vault-scoped role assignments."""
import json

import pytest

from resource_librarian.app import App, Settings
from resource_librarian.keys import KeyStore
from resource_librarian.providers import Scripted, Reply


@pytest.fixture
def routed_app(vault):
    app = App(vault, keys=KeyStore(use_keyring=False), coordinate=True,
              provider_for=lambda choice: Scripted(lambda *_: Reply(choice["model"])))
    try:
        yield app
    finally:
        app.close_runtime()


def route(model):
    return {"provider": "deepinfra", "model": model}


def test_picker_preserves_explicit_roles_and_inherited_defaults(routed_app):
    app = routed_app
    app.set_tiers([route("lead-a")], override="test")
    assert app.role_routes.raw()["clerk"].inherits_from == "scribe"
    app.set_lead(route("lead-b"), override="test")
    assert app.role_routes.resolve("clerk").model_id == "lead-b"
    assert app.role_routes.resolve("research_helper").model_id == "lead-b"
    assert len(app.settings.data["tiers"]) == 1

    app.set_tiers([route("lead-a"), route("notes"), route("intake")], override="test")
    app.set_lead(route("lead-c"), override="test")
    assert app.role_routes.resolve("lead").host_id == "preset-deepinfra"
    assert app.role_routes.resolve("scribe").model_id == "notes"
    assert app.role_routes.resolve("clerk").model_id == "intake"
    assert app.role_routes.resolve("research_helper").model_id == "notes"


def test_legacy_routes_migrate_once_and_reopen(vault):
    Settings(vault).update(tiers=[route("existing")])
    app = App(vault, keys=KeyStore(use_keyring=False))
    try:
        assert app.role_routes.resolve("scribe").model_id == "existing"
        rows = app.role_routes.raw()
        assert rows["lead"].endpoint_fingerprint == app.hosts.get("preset-deepinfra").endpoint_fingerprint
        assert set(rows) == {"lead", "scribe", "clerk", "research_helper", "ocr", "tts", "stt", "embeddings"}
    finally:
        app.close_runtime()
    # Shared defaults may change elsewhere; a configured vault keeps its binding.
    Settings(vault).update(tiers=[route("unrelated")])
    reopened = App(vault, keys=KeyStore(use_keyring=False))
    try:
        assert reopened.role_routes.resolve("lead").model_id == "existing"
    finally:
        reopened.close_runtime()


def test_service_slots_mirror_validated_choices_without_chat_qualification(routed_app):
    app = routed_app
    result = app.set_service("ocr", "deepinfra", "vision-example")
    assert isinstance(result, dict)
    ocr = app.role_routes.resolve("ocr")
    assert ocr.model_id == "vision-example" and ocr.evidence_kind == "service_contract"
    assert ocr.host_id == "preset-deepinfra"
    result = app.set_service("embeddings", "hash", "test-hash")
    assert isinstance(result, dict)
    assert app.role_routes.resolve("embeddings").protocol == "local"


def test_invalid_existing_bindings_release_startup_lease(vault):
    from resource_librarian.coordination import VaultCoordinator
    path = vault.librarian / "agents" / "routes.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"schema_version":999}', encoding="utf-8")
    with pytest.raises(ValueError):
        App(vault, keys=KeyStore(use_keyring=False), coordinate=True)
    lease = VaultCoordinator(vault)
    lease.acquire()
    lease.release()
    assert json.loads(path.read_text())["schema_version"] == 999
