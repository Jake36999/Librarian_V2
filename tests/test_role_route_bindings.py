"""The existing picker persists canonical, vault-scoped role assignments."""
import json

import pytest

from resource_librarian.app import ApiError, App, Settings
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
        assert reopened.settings.data["tiers"][0]["model"] == "existing"
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


def test_execution_uses_bound_roles_even_if_legacy_settings_differ(routed_app):
    from dataclasses import replace
    app = routed_app
    app.set_tiers([route("lead"), route("notes"), route("intake")], override="test")
    rows = app.role_routes.raw()
    rows["research_helper"] = replace(rows["lead"], role="research_helper", model_id="helper")
    app._serialized("test-route", lambda: app.role_routes.save(rows))
    app.set_lead(route("lead"), override="test")
    assert app.role_routes.resolve("research_helper").model_id == "helper"
    app.settings.update(tiers=[route("unrelated")])
    assert app._loop().send("hello").reply == "lead"
    extras = app._extras()
    assert extras["clerk"].provider.chat("", [], []).text == "intake"
    assert extras["scribe"].provider.chat("", [], []).text == "notes"
    assert extras["helper_provider"](2).chat("", [], []).text == "helper"
    assert extras["helper_provider"](1).chat("", [], []).text == "lead"


def test_changed_or_disabled_host_cannot_fall_back_to_another_role(routed_app):
    app = routed_app
    app.set_tiers([route("lead"), route("notes")], override="test")
    host = app.hosts.get("preset-deepinfra")
    previous = host.base_url
    host.base_url = "https://changed.example/v1"
    from resource_librarian.hosts import endpoint_fingerprint
    host.endpoint_fingerprint = endpoint_fingerprint(host)
    with pytest.raises(ApiError, match="endpoint changed"):
        app.role_provider("scribe")
    host.base_url = previous
    host.endpoint_fingerprint = endpoint_fingerprint(host)
    host.enabled = False
    with pytest.raises(ApiError, match="disabled"):
        app.role_provider("scribe")


def test_no_chat_binding_keeps_legacy_clerk_configuration_available(routed_app):
    assert routed_app._extras().get("clerk") is None
    assert routed_app.role_routes.resolve("clerk") is None


def test_a_second_uncoordinated_app_cannot_migrate_beside_core(routed_app, vault):
    before = routed_app.role_routes.path.read_bytes()
    with pytest.raises(ApiError, match="CORE_REQUIRED"):
        App(vault, keys=KeyStore(use_keyring=False))
    assert routed_app.role_routes.path.read_bytes() == before


def test_unavailable_clerk_does_not_block_lead_or_use_legacy_fallback(routed_app):
    from dataclasses import replace
    from resource_librarian.clerk import ClerkUnavailable, UnavailableEndpoint
    from resource_librarian.registry import Context
    from resource_librarian.tools.staging import clerk_endpoint
    app = routed_app
    app.set_tiers([route("lead"), route("notes"), route("intake")], override="test")
    rows = app.role_routes.raw()
    rows["clerk"] = replace(rows["clerk"], endpoint_fingerprint="changed")
    app._serialized("test-route", lambda: app.role_routes.save(rows))
    assert app._loop().send("hello").reply == "lead"
    endpoint = clerk_endpoint(Context(tier="consult", vault=app.vault, extras=app._extras()))
    assert isinstance(endpoint, UnavailableEndpoint)
    with pytest.raises(ClerkUnavailable, match="endpoint changed"):
        endpoint.complete({"task": "test"})


def test_custom_profile_explicitly_selects_binding_and_uses_its_rate_card(routed_app, monkeypatch):
    app = routed_app
    app.set_tiers([route("lead"), route("notes")], override="test")
    app._loop()
    app.profile_save({"id": "analyst", "role": "analyst", "required_qualification": "experimental",
                      "route_policy": {"binding_role": "scribe"}, "allowed_bundles": ["read"]})
    seen = []
    monkeypatch.setattr(app, "_route_rate_card", lambda route, profile: seen.append(route) or None)
    app.set_agent_profile("analyst")
    assert seen[-1]["model"] == "notes"
    assert app._loop().send("hello").reply == "notes"


def test_lead_profile_checks_qualification_for_the_route_it_will_execute(routed_app):
    app = routed_app
    app.set_tiers([route("lead"), route("untested-notes")], override="Lead only")
    app.profile_save({"id": "notes-as-lead", "role": "lead", "required_qualification": "screened",
                      "route_policy": {"binding_role": "scribe"}, "allowed_bundles": ["read"]})
    app.set_agent_profile("notes-as-lead")
    with pytest.raises(ApiError, match="requires screened lead qualification") as refused:
        app._loop()
    assert refused.value.body["plan"]["model"] == "untested-notes"


def test_custom_task_role_cannot_borrow_qualification_from_its_selected_slot(routed_app):
    app = routed_app
    app.set_tiers([route("lead"), route("notes")], override="test")
    app.profile_save({"id": "analyst", "role": "analyst", "required_qualification": "screened",
                      "route_policy": {"binding_role": "scribe"}, "allowed_bundles": ["read"]})
    app.set_agent_profile("analyst")
    with pytest.raises(ApiError, match="qualification for role 'analyst'") as refused:
        app._loop()
    assert refused.value.body["plan"]["role"] == "analyst"


def test_offline_mutation_takes_the_lease_and_rechecks_a_new_core(vault):
    from resource_librarian.coordination import VaultCoordinator
    app = App(vault, keys=KeyStore(use_keyring=False))
    try:
        assert app._serialized("check-owner", lambda: VaultCoordinator.held_here(vault))
        assert not VaultCoordinator.held_here(vault)
        core = VaultCoordinator(vault)
        core.acquire()
        try:
            with pytest.raises(ApiError, match="CORE_REQUIRED"):
                app.settings.update(reply_length="must not persist")
            assert app.settings.data["reply_length"] != "must not persist"
        finally:
            core.release()
    finally:
        app.close_runtime()


def test_background_profiles_honor_slot_choice_and_stop_after_assignment_changes(routed_app):
    from resource_librarian.clerk import ClerkUnavailable
    app = routed_app
    app.set_tiers([route("lead"), route("notes"), route("intake")], override="test")
    for role in ("clerk", "research_helper"):
        profile = app.profiles.get(role).public()
        profile.update(required_qualification="experimental", route_policy={"binding_role": "scribe"})
        app.profile_save(profile)
    endpoint = app._extras()["clerk"]
    assert endpoint.provider.chat("", [], []).text == "notes"
    assert app._helper_provider(2).chat("", [], []).text == "notes"
    guarded = app._background_profile_endpoint("clerk", endpoint, 3)
    payload = {"task": "test", "user": "hello", "system": "test", "temperature": 0}
    assert guarded.complete(payload)[0] == "notes"
    app.set_tiers([route("lead"), route("new-notes"), route("intake")], override="test")
    with pytest.raises(ClerkUnavailable, match="route changed"):
        guarded.complete(payload)


def test_canonical_preset_keeps_legacy_allow_lists_and_price_cards(routed_app, monkeypatch):
    from resource_librarian import app as module
    from resource_librarian.agent_runtime import route_permitted
    app = routed_app
    app.set_tiers([route("priced")], override="test")
    profile = app.profiles.get("lead")
    profile.route_policy = {"providers": ["deepinfra"]}
    chosen = app._role_choice("lead")
    assert route_permitted(profile, chosen)[0]
    monkeypatch.setattr(module, "_shipped_profiles", lambda: {
        ("deepinfra", "priced"): {"price_input_per_1m": 1, "price_output_per_1m": 2}})
    assert app._route_rate_card(chosen, profile) == {"price_input_per_1m": 1, "price_output_per_1m": 2}


def test_legacy_local_picker_selection_pins_the_same_custom_url(routed_app):
    app = routed_app
    app.settings.update(base_urls={"local": "http://127.0.0.1:11999/v1"})
    selected = app.set_tiers([{"provider": "local", "model": "local-model"}], override="test")
    binding = app.role_routes.resolve("lead")
    assert binding.host_id.startswith("legacy-local-")
    assert app.hosts.get(binding.host_id).base_url == "http://127.0.0.1:11999/v1"
    assert selected["tiers"][0]["host_id"] == binding.host_id
    # Clearing and choosing through the old API still resolves the same host.
    app.set_tiers([])
    app.set_tiers([{"provider": "local", "model": "local-model"}], override="test")
    assert app.role_routes.resolve("lead").host_id == binding.host_id


def test_explicit_host_id_cannot_be_reinterpreted_as_a_provider_alias(routed_app):
    app = routed_app
    app.hosts.upsert({"id": "deepinfra", "display_name": "My endpoint", "protocol": "openai",
                      "base_url": "http://127.0.0.1:11999/v1", "auth_ref": ""})
    app.set_tiers([{"host_id": "deepinfra", "model": "custom"}], override="test")
    assert app.role_routes.resolve("lead").host_id == "deepinfra"
    assert app._role_choice("lead")["host_id"] == "deepinfra"
