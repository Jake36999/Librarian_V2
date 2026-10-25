"""Service selections execute the canonical route and share Core host policy."""
from dataclasses import replace
import json
import threading

import pytest

from resource_librarian import embed, ocr, service_routes, stt, tts
from resource_librarian.app import App
from resource_librarian.keys import KeyStore


@pytest.fixture
def core(vault):
    app = App(vault, keys=KeyStore(use_keyring=False), coordinate=True)
    try:
        yield app
    finally:
        app.close_runtime()


def custom_host(core, host_id="studio"):
    core.hosts.upsert({"id": host_id, "display_name": "Studio", "protocol": "openai",
                       "base_url": "http://127.0.0.1:11999/v1", "auth_ref": "", "concurrency_limit": 1})


def test_service_assignment_survives_projection_changes_and_restart(core):
    core.set_service("ocr", "deepinfra", "selected-vision")
    core.vault.set_setting("services", "ocr", "local:unrelated")
    assert ocr.choice(core.vault)["model"] == "selected-vision"
    vault = core.vault
    core.close_runtime()
    reopened = App(vault, keys=KeyStore(use_keyring=False), coordinate=True)
    try:
        assert ocr.choice(vault)["model"] == "selected-vision"
        assert vault.setting("services", "ocr") == "deepinfra:selected-vision"
    finally:
        reopened.close_runtime()


def test_legacy_search_vector_setting_migrates_and_explicit_clear_disables_it(vault):
    vault.set_setting("search", "vectors", "hash:32")
    app = App(vault, keys=KeyStore(use_keyring=False))
    try:
        assert embed.spec_for(vault) == "hash:32"
        app.set_service("embeddings", "", "")
        assert embed.spec_for(vault) == ""
    finally:
        app.close_runtime()


class Response:
    def __init__(self, data):
        self.data = data
    def __enter__(self):
        return self
    def __exit__(self, *_):
        pass
    def read(self):
        return json.dumps(self.data).encode()


def test_ocr_custom_host_uses_exact_endpoint_and_no_unrelated_key(core, monkeypatch):
    custom_host(core)
    core.set_service("ocr", "", "vision", host_id="studio")
    requests = []
    def send(request, timeout=0):
        requests.append(request)
        return Response({"choices": [{"message": {"content": "Observed page"}}]})
    monkeypatch.setattr(ocr.urllib.request, "urlopen", send)
    reader = ocr.endpoint(core.vault)
    assert reader.page_text(b"image") == "Observed page"
    assert requests[0].full_url == "http://127.0.0.1:11999/v1/chat/completions"
    assert not requests[0].has_header("Authorization")
    core.set_service("ocr", "deepinfra", "other")
    with pytest.raises(ocr.OcrError, match="assignment changed"):
        reader.page_text(b"image")
    assert len(requests) == 1


def test_embedding_custom_host_and_representation_remain_host_scoped(core, monkeypatch):
    custom_host(core, "deepinfra")  # Same spelling does not confer provider evidence.
    core.set_service("embeddings", "", "BAAI/bge-m3", host_id="deepinfra")
    sent = []
    def send(request, timeout=0):
        sent.append(request)
        return Response({"data": [{"index": 0, "embedding": [1.0, 0.0]}]})
    monkeypatch.setattr(embed.urllib.request, "urlopen", send)
    spec = embed.spec_for(core.vault)
    namespace, document, query, contract = embed.load_embedding_encoders(spec, vault=core.vault)
    assert document(["document"]).shape == (1, 2)
    assert query(["question"]).shape == (1, 2)
    assert all(r.full_url == "http://127.0.0.1:11999/v1/embeddings" for r in sent)
    assert contract["status"] == "unreviewed"
    assert core.hosts.get("deepinfra").endpoint_fingerprint in namespace


def test_custom_host_named_hash_is_not_a_local_encoder(core, monkeypatch):
    custom_host(core, "hash")
    core.set_service("embeddings", "", "hosted-encoder", host_id="hash")
    route = service_routes.resolve(core.vault, "embeddings", validate=True)
    assert not route.local and route.protocol == "openai"
    assert core.role_routes.resolve("embeddings").host_id == "hash"
    assert embed.spec_for(core.vault) == "api:hash:hosted-encoder"
    monkeypatch.setattr(embed.urllib.request, "urlopen", lambda *_a, **_k: Response({
        "data": [{"index": 0, "embedding": [1, 0]}]}))
    _, encode, _, _ = embed.load_embedding_encoders(embed.spec_for(core.vault), vault=core.vault)
    assert encode(["text"]).shape == (1, 2)


def test_service_and_chat_host_calls_use_the_same_concurrency_gate(core):
    custom_host(core)
    core.set_service("ocr", "", "vision", host_id="studio")
    route = service_routes.resolve(core.vault, "ocr", validate=True)
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    def chat():
        core.host_limiter.run(core.hosts.get("studio"), lambda: (started.set(), release.wait(5)))
    chat_thread = threading.Thread(target=chat)
    chat_thread.start()
    assert started.wait(2)
    service_thread = threading.Thread(target=lambda: service_routes.run(core.vault, route, finished.set))
    service_thread.start()
    try:
        assert not finished.wait(.1)
    finally:
        release.set()
        chat_thread.join(3)
        service_thread.join(3)
    assert finished.is_set()


def test_changed_disabled_missing_and_stopped_routes_never_make_a_call(core):
    core.set_service("ocr", "deepinfra", "vision")
    route = service_routes.resolve(core.vault, "ocr", validate=True)
    rows = core.role_routes.raw()
    rows["ocr"] = replace(rows["ocr"], endpoint_fingerprint="old")
    core._serialized("test-stale", lambda: core.role_routes.save(rows))
    calls = []
    with pytest.raises(service_routes.ServiceRouteError, match="endpoint changed"):
        service_routes.run(core.vault, route, lambda: calls.append(True))
    assert calls == []
    assert next(r for r in core.services()["slots"] if r["slot"] == "ocr")["route_status"] == "unavailable"
    core.close_runtime()
    with pytest.raises(service_routes.ServiceRouteError, match="stopped"):
        service_routes.run(core.vault, route, lambda: calls.append(True))
    assert calls == []


@pytest.mark.parametrize("failure", ["disabled", "missing"])
def test_unavailable_service_host_stays_visible_but_cannot_execute(core, monkeypatch, failure):
    custom_host(core)
    core.set_service("ocr", "", "vision", host_id="studio")
    if failure == "disabled":
        core.hosts.update_controls({"host_id": "studio", "enabled": False})
    else:
        core.hosts.remove("studio")
    requests = []
    monkeypatch.setattr(ocr.urllib.request, "urlopen", lambda *_a, **_k: requests.append(True))
    assert next(r for r in core.services()["slots"] if r["slot"] == "ocr")["route_status"] == "unavailable"
    with pytest.raises(ocr.OcrError, match="disabled|unavailable"):
        ocr.endpoint(core.vault)
    assert requests == []


def test_service_result_after_stop_is_discarded_and_visible_during_drain(core):
    custom_host(core)
    core.set_service("ocr", "", "vision", host_id="studio")
    route = service_routes.resolve(core.vault, "ocr", validate=True)
    entered, release = threading.Event(), threading.Event()
    results, errors = [], []
    def request():
        try:
            results.append(service_routes.run(core.vault, route, lambda: (entered.set(), release.wait(3))))
        except service_routes.ServiceRouteError as exc:
            errors.append(str(exc))
    thread = threading.Thread(target=request)
    thread.start()
    try:
        assert entered.wait(2)
        assert core.running()["service_calls"] == 1
        core.service_runtime.close()
    finally:
        release.set()
        thread.join(3)
    assert not results and errors and "stopped" in errors[0]
    assert core.service_runtime.active_calls == 0


def test_native_speech_uses_bound_credential_source(core, monkeypatch):
    import base64
    # Model a registry loaded with an owner-managed credential alias. Services
    # must not hardcode the preset environment variable at the call boundary.
    replacement = replace(core.hosts.get("preset-deepinfra"), auth_ref="LIBRARIAN_SPEECH_TEST_KEY").normalise()
    original_get = core.hosts.get
    monkeypatch.setattr(core.hosts, "get", lambda ident: replacement if ident == replacement.id else original_get(ident))
    monkeypatch.setenv("LIBRARIAN_SPEECH_TEST_KEY", "fake-test-token")
    core.set_service("tts", "deepinfra", "hexgrad/Kokoro-82M")
    core.set_service("stt", "deepinfra", "Qwen/Qwen3-ASR-0.6B")
    sent = []
    def speech(url, body, key):
        sent.append((url, key))
        return {"audio": "data:audio/mp3;base64," + base64.b64encode(b"audio").decode()}
    assert tts.speak(core.vault, "Test.", post=speech)["audio"].startswith("data:audio")
    def transcription(url, audio, filename, content_type, key):
        sent.append((url, key))
        return {"text": "Test."}
    assert stt.transcribe(core.vault, b"audio", post=transcription)["text"] == "Test."
    assert len(sent) == 2 and all(key == "fake-test-token" for _, key in sent)
    assert all(url.startswith("https://api.deepinfra.com/v1/inference/") for url, _ in sent)


def test_readiness_never_borrows_clerk_evidence_for_lead(core, monkeypatch):
    core.set_tiers([{"provider": "deepinfra", "model": "shared"}], override="test")
    fingerprints = core._qualification_fingerprints("preset-deepinfra", "shared", "clerk")
    core.qualifications.record(host_id="preset-deepinfra", model_id="shared", role="clerk",
        level="L1", outcome="pass", compatibility_fingerprint=fingerprints["compatibility"],
        behavior_fingerprint=fingerprints["behavior"],
        probe_validation={"contract_version": "2", "passed": True})
    before = core.qualifications.path.read_bytes()
    monkeypatch.setattr(core, "qualification_status", lambda *_a, **_k: pytest.fail("not a passive read"))
    row = next(r for r in core.route_readiness()["routes"] if r["host_id"] == "preset-deepinfra" and r["model"] == "shared")
    assert row["qualification_by_role"]["clerk"]["status"] == "screened"
    assert row["qualification_by_role"]["lead"]["status"] == "experimental"
    assert row["qualification"]["role"] == "lead"
    assert row["bound_roles"] == ["lead", "scribe", "clerk", "research_helper"]
    assert core.qualifications.path.read_bytes() == before


def test_readiness_uses_canonical_assignment_for_a_custom_task(core):
    core.set_tiers([{"provider": "deepinfra", "model": "lead"},
                    {"provider": "deepinfra", "model": "notes"}], override="test")
    core.profile_save({"id": "analyst", "role": "analyst", "route_policy": {"binding_role": "scribe"},
                       "required_qualification": "experimental", "allowed_bundles": ["read"]})
    core.settings.update(tiers=[{"provider": "unrelated", "model": "wrong"}])
    readiness = core.route_readiness("analyst")
    active = [r for r in readiness["routes"] if r["active_task"]]
    assert active and all(r["model"] == "notes" and r["qualification"]["role"] == "analyst" for r in active)
    assert readiness["bindings"]["scribe"]["model_id"] == "notes"
    host = core.hosts.get("preset-deepinfra")
    core.hosts.update_controls({"host_id": host.id, "enabled": False})
    row = next(r for r in core.route_readiness("analyst")["routes"] if r["host_id"] == host.id and r["model"] == "notes")
    assert row["binding_errors"]["scribe"] == "host disabled"
    assert not row["host_enabled"]
