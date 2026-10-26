"""ADAPT-10: source-linked expectation proposals through human staging."""
from __future__ import annotations

import json
import queue
import threading

import pytest

from resource_librarian import model_expectation_authoring
from resource_librarian.app import App
from resource_librarian.evidence import EvidenceStore
from resource_librarian.keys import KeyStore, config_dir
from resource_librarian.model_invocation import (ExactRoute, ExpectationRegistry,
                                                 InvocationRuntime, LEGACY_OPENAI_CHAT)
from resource_librarian.registry import Context, REGISTRY
from resource_librarian.staging import StagingStore


URL = "https://models.example.test/acme/model-1"


def _source(vault, item_id="model-card"):
    evidence = EvidenceStore(vault).put(
        "page", URL, {"text": "Model 1 declares tool use through the hosted API."},
        "2026-10-26T10:00:00+00:00")
    StagingStore(vault).add({
        "id": item_id, "kind": "source", "source_kind": "model",
        "name": "Acme Model 1", "canonical_url": URL,
        "evidence": [{"id": evidence.id, "kind": evidence.kind,
                      "source": evidence.source, "fetched_at": evidence.fetched_at}],
    })
    return evidence


def _record(**updates):
    row = {
        "id": "acme-model-1-tools", "version": "2026-10-26", "protocol": "openai",
        "adapter_id": "legacy_openai_chat", "adapter_abi": 1,
        "model_id": "acme/model-1", "host_id_or_family": "acme-host",
        "capabilities": {"tool_use": "true", "tool_results": "unknown"},
        "behavior_modes": ["provider_default"], "source_revision": "card-commit-abc123",
    }
    row.update(updates)
    return row


def _ctx(vault, **extras):
    return Context(tier="curate", vault=vault,
                   extras={"caller_kind": "person", **extras})


def _stage(vault, record=None, *, ctx=None):
    _source(vault)
    context = ctx or _ctx(vault)
    return REGISTRY.call("model_expectation_propose",
                         {"source_item_id": "model-card", "record": record or _record()},
                         context)


def _revision(ctx, item_id):
    return REGISTRY.call("staging_show", {"item_id": item_id}, ctx)["staged_revision"]


def test_proposal_is_a_strict_draft_linked_to_content_addressed_card_evidence(vault):
    evidence = _source(vault)
    out = REGISTRY.call("model_expectation_propose",
                        {"source_item_id": "model-card", "record": _record()}, _ctx(vault))

    item = StagingStore(vault).load(out["item"])
    assert item["kind"] == "model_expectation" and item["status"] == "staged"
    assert item["record"]["status"] == "draft"
    assert item["record"]["provenance"] == {
        "source_url": URL, "source_revision": "card-commit-abc123",
        "source_kind": "model_card", "source_evidence_id": evidence.id,
    }
    assert "text" not in json.dumps(item["record"])
    row = REGISTRY.call("staging_list", {"kind": "model_expectation"}, _ctx(vault))["items"][0]
    assert row["source_evidence_id"] == evidence.id


def test_proposal_id_is_canonical_and_repeating_it_is_idempotent(vault):
    _source(vault)
    first = REGISTRY.call("model_expectation_propose", {
        "source_item_id": "model-card", "record": _record(id="Acme/Model One")}, _ctx(vault))
    second = REGISTRY.call("model_expectation_propose", {
        "source_item_id": "model-card", "record": _record(id="Acme/Model One")}, _ctx(vault))

    assert first == second
    assert first["record_id"] == "acme-model-one"
    assert len(list(StagingStore(vault).items("model_expectation"))) == 1


@pytest.mark.parametrize("poison", [
    {"template": "{{ system }}"},
    {"prompt_contract": {"runtime_target": "openai", "chat_template": "unsafe"}},
    {"provenance": {"source_revision": "rev", "script": "run()"}},
    {"card_text": "copy all arbitrary prose"},
    {"dialect": {"reasoning_replay": "never_replay"}},
])
def test_executable_template_and_unrecognised_card_fields_never_enter_staging(vault, poison):
    _source(vault)
    out = REGISTRY.call("model_expectation_propose",
                        {"source_item_id": "model-card", "record": {**_record(), **poison}},
                        _ctx(vault))

    assert "error" in out
    assert list(StagingStore(vault).items("model_expectation")) == []


def test_rejected_draft_changes_no_active_registry_or_route_behaviour(vault):
    runtime = InvocationRuntime()
    before = runtime.expectations.pack_fingerprint
    context = _ctx(vault, invocation_runtime=runtime)
    staged = _stage(vault, ctx=context)
    token = _revision(context, staged["item"])

    rejected = REGISTRY.call("staging_decide", {
        "decision": "reject", "reason": "claim not supported",
        "staged_revision": token, "item_ids": [staged["item"]]}, context)["results"][0]

    assert rejected["status"] == "rejected"
    assert runtime.expectations.pack_fingerprint == before
    assert not (config_dir() / "model-expectations.json").exists()
    route = ExactRoute("acme-host", "openai", "endpoint", "acme/model-1")
    unchanged = runtime.expectations.match(route, LEGACY_OPENAI_CHAT)
    assert unchanged.id == "core-legacy-openai-chat"
    assert unchanged.capability("tool_use") == "unknown"


def test_rejection_keeps_its_prepared_collision_target_during_permission_wait(vault):
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=5)
    app.set_mode("auto")
    extras = app._extras()
    extras.pop("agent_profile", None)
    extras.pop("profile_store", None)
    context = Context(tier="curate", vault=vault,
                      extras={**extras, "caller_kind": "person"})
    try:
        staged = _stage(vault, ctx=context)
        token = _revision(context, staged["item"])
        quarantine = vault.work("quarantine") / "staging"
        quarantine.mkdir(parents=True, exist_ok=True)
        collision = quarantine / f"{staged['item']}.json"
        collision.write_text('{"older": true}', encoding="utf-8")
        app.set_mode("ask")
        requests, results = queue.Queue(), []
        app.broker.subscribe(lambda event: requests.put(event)
                             if event.get("type") == "permission_request" else None)
        thread = threading.Thread(target=lambda: results.append(REGISTRY.call(
            "staging_decide", {"item_ids": [staged["item"]], "decision": "reject",
                               "reason": "not supported", "staged_revision": token},
            context)))
        thread.start()
        event = requests.get(timeout=3)
        collision.unlink()
        app.broker.answer(event["id"], "allow_once")
        thread.join(3)

        assert not thread.is_alive()
        assert results[0]["results"][0]["status"] == "rejected"
        assert not collision.exists()
        prepared = quarantine / f"{staged['item']} (2).json"
        assert json.loads(prepared.read_text(encoding="utf-8"))["reason"] == "not supported"
    finally:
        app.broker.close("test cleanup")
        app.close_runtime()


def test_person_acceptance_updates_pack_and_live_runtime_only_after_revision_review(vault):
    runtime = InvocationRuntime()
    context = _ctx(vault, invocation_runtime=runtime)
    staged = _stage(vault, ctx=context)
    reviewed = REGISTRY.call("staging_review", {"item_id": staged["item"]}, context)
    token = _revision(context, staged["item"])

    accepted = REGISTRY.call("staging_decide", {
        "item_ids": [staged["item"]], "decision": "accept", "staged_revision": token},
        context)["results"][0]

    assert reviewed["record"]["status"] == "draft"
    assert accepted["status"] == "accepted"
    payload = json.loads((config_dir() / "model-expectations.json").read_text(encoding="utf-8"))
    assert payload["records"][0]["status"] == "reviewed"
    assert payload["records"][0]["provenance"]["source_evidence_id"]
    route = ExactRoute("acme-host", "openai", "endpoint", "acme/model-1")
    active = runtime.expectations.match(route, LEGACY_OPENAI_CHAT)
    assert active is not None and active.id == "acme-model-1-tools"
    assert active.capability("tool_use") == "true"


def test_non_person_and_stale_review_cannot_activate_a_pack(vault):
    context = _ctx(vault)
    staged = _stage(vault, ctx=context)
    token = _revision(context, staged["item"])
    agent = Context(tier="curate", vault=vault, extras={"caller_kind": "agent"})
    refused = REGISTRY.call("staging_decide", {
        "item_ids": [staged["item"]], "decision": "accept", "staged_revision": token}, agent)
    assert "error" in refused

    item = StagingStore(vault).load(staged["item"])
    item["record"]["version"] = "changed-after-review"
    StagingStore(vault).save(item)
    stale = REGISTRY.call("staging_decide", {
        "item_ids": [staged["item"]], "decision": "accept", "staged_revision": token}, context)
    assert "error" in stale
    unchanged = ExpectationRegistry.active().match(
        ExactRoute("acme-host", "openai", "endpoint", "acme/model-1"),
        LEGACY_OPENAI_CHAT)
    assert unchanged.id == "core-legacy-openai-chat"


def test_changed_source_provenance_must_be_proposed_and_reviewed_again(vault):
    context = _ctx(vault)
    staged = _stage(vault, ctx=context)
    source = StagingStore(vault).load("model-card")
    source["evidence"] = []
    StagingStore(vault).save(source)

    refused = REGISTRY.call("staging_decide", {
        "item_ids": [staged["item"]], "decision": "accept",
        "staged_revision": _revision(context, staged["item"])}, context)

    assert "error" in refused
    assert StagingStore(vault).load(staged["item"])["status"] == "staged"
    assert not (config_dir() / "model-expectations.json").exists()


def test_personal_pack_cannot_replace_a_bundled_record(vault):
    context = _ctx(vault)
    staged = _stage(vault, record=_record(id="core-legacy-openai-chat"), ctx=context)
    result = REGISTRY.call("staging_decide", {
        "item_ids": [staged["item"]], "decision": "accept",
        "staged_revision": _revision(context, staged["item"])}, context)

    assert "error" in result
    assert StagingStore(vault).load(staged["item"])["status"] == "staged"


def test_failed_pack_activation_stays_visible_and_changes_no_route(monkeypatch, vault):
    context = _ctx(vault)
    staged = _stage(vault, ctx=context)
    monkeypatch.setattr(model_expectation_authoring, "atomic_write_text",
                        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")))

    result = REGISTRY.call("staging_decide", {
        "item_ids": [staged["item"]], "decision": "accept",
        "staged_revision": _revision(context, staged["item"])}, context)

    assert "error" in result
    item = StagingStore(vault).load(staged["item"])
    assert item["status"] == "staged"
    assert item["acceptance_progress"]["record_id"] == "acme-model-1-tools"
    assert not (config_dir() / "model-expectations.json").exists()
    unchanged = ExpectationRegistry.active().match(
        ExactRoute("acme-host", "openai", "endpoint", "acme/model-1"),
        LEGACY_OPENAI_CHAT)
    assert unchanged.id == "core-legacy-openai-chat"


@pytest.mark.parametrize("change", [
    {"model_id": "*"},
    {"host_id_or_family": "*"},
    {"dialect": {"sampling_profile": "deterministic"}},
    {"provenance": {"source_url": URL, "source_revision": "card-commit-abc123",
                    "source_kind": "model_card", "source_evidence_id": ""}},
])
def test_active_loader_rejects_hand_edited_records_that_bypass_authoring(tmp_path, change):
    record = {
        **_record(), "status": "reviewed",
        "provenance": {"source_url": URL, "source_revision": "card-commit-abc123",
                       "source_kind": "model_card", "source_evidence_id": "sha256:evidence"},
        **change,
    }
    path = tmp_path / "personal.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "pack_id": "librarian-personal-model-expectations",
        "records": [record],
    }), encoding="utf-8")

    active = ExpectationRegistry.active(path)

    assert active.load_error
    assert "personal model expectation pack could not be loaded" in active.load_error
    unchanged = active.match(
        ExactRoute("acme-host", "openai", "endpoint", "acme/model-1"),
        LEGACY_OPENAI_CHAT)
    assert unchanged.id == "core-legacy-openai-chat"
