"""The core's local API, over a real loopback server: the boundary, the chat
through the loop, permissions decided live, keys that never come back, and the
person's own calls."""
import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from resource_librarian import keys, providers
from resource_librarian.app import App, build
from resource_librarian.hosts import L1_PROBE_CONTRACT_VERSION
from resource_librarian.keys import KeyStore
from resource_librarian.providers import Reply, ToolCall

from conftest import add_source
from test_sessions import OSQUERY_LINE


class Client:
    def __init__(self, server, token):
        self.base = f"http://127.0.0.1:{server.server_address[1]}"
        self.token = token

    def request(self, method, path, body=None, headers=None, token=True):
        head = {"Content-Type": "application/json", **(headers or {})}
        if token:
            head["X-Librarian-Token"] = self.token
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=head)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                raw = response.read()
                kind = response.headers.get("Content-Type", "")
                return response.status, (json.loads(raw) if "json" in kind else raw.decode())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, body or {}, **kw)

    def upload(self, path, data: bytes, token=True):
        """The composer's paperclip sends raw bytes, not a JSON body."""
        head = {"X-Librarian-Token": self.token} if token else {}
        req = urllib.request.Request(self.base + path, data=data, method="POST", headers=head)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")


class Model:
    """A scripted chat model whose replies are set per test."""

    def __init__(self):
        self.replies = []
        self.provider = providers.Scripted(lambda s, m, t: self.replies.pop(0))


@pytest.fixture
def served(vault, tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path / "config"))
    for name in ("OPENAI_API_KEY", "DEEPINFRA_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    add_source(vault.root, "osquery", OSQUERY_LINE, "Query operating system state.")
    model = Model()
    app = App(vault, token="test-token", keys=KeyStore(use_keyring=False),
              provider_for=lambda choice: model.provider, broker_timeout=5)
    server = build(app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield app, Client(server, "test-token"), model
    server.shutdown()
    server.server_close()
    if app.mcp is not None:
        app.mcp.stop()


def wait_for(app, kind, timeout=5.0, after=0):
    end = time.time() + timeout
    while time.time() < end:
        for event in app.hub.since(after):
            if event["type"] == kind:
                return event
        time.sleep(0.02)
    raise AssertionError(f"no {kind} event; saw {[e['type'] for e in app.hub.since(after)]}")


def test_the_boundary(served):
    app, client, _ = served
    assert client.get("/api/state", token=False)[0] == 403
    assert client.get("/api/state")[0] == 200
    evil = client.post("/api/mode", {"mode": "auto"}, headers={"Origin": "https://evil.example"})
    assert evil[0] == 403 and "another origin" in evil[1]["error"]
    assert client.post("/api/mode", {"mode": "auto"},
                       headers={"Origin": "app://obsidian.md"})[0] == 200
    rebound = client.get("/api/state", headers={"Host": "evil.example:8323"})
    assert rebound[0] == 403
    status, page = client.get("/", token=False)                  # the page carries the token
    assert status == 200 and 'content="test-token"' in page and "__LIBRARIAN_TOKEN__" not in page
    req = urllib.request.Request(client.base + "/app.js")
    with urllib.request.urlopen(req) as response:
        assert response.status == 200 and "javascript" in response.headers["Content-Type"]
        assert "default-src 'self'" in response.headers["Content-Security-Policy"]
        # read-aloud audio arrives as data: URIs; without media-src none of it could play
        assert "media-src 'self' data: blob:" in response.headers["Content-Security-Policy"]
    assert client.get("/../keys.py", token=False)[0] == 404


def test_a_chat_turn_runs_the_loop_and_streams_events(served):
    app, client, model = served
    assert client.post("/api/chat", {"text": "hi"})[0] == 409     # no model chosen yet
    # R10: a lead M0 has not qualified needs a person's recorded override
    status, body = client.post("/api/tiers", {"tiers": [{"provider": "deepinfra",
                                                          "model": "m1"}]})
    assert status == 409 and body["needs_override"] and body["lead"] == "deepinfra/m1"
    assert client.post("/api/tiers", {"tiers": [{"provider": "deepinfra", "model": "m1"}],
                                      "override": "trying it out"})[0] == 200
    assert client.get("/api/state")[1]["lead"]["reason"] == "trying it out"
    model.replies = [Reply(tool_calls=[ToolCall("1", "open_session", {"purpose": "explore",
                                                                       "question": "hosts"})]),
                     Reply(text="Opened a thread on hosts.")]
    assert client.post("/api/chat", {"text": "explore hosts"})[1] == {"accepted": True}
    done = wait_for(app, "turn_done")
    assert done["reply"] == "Opened a thread on hosts."
    assert done["session"]["phase"] == "frame" and done["session"]["purpose"] == "explore"
    kinds = [e["type"] for e in app.hub.since(0)]
    assert kinds.index("user") < kinds.index("tool_call") < kinds.index("tool_result") \
        < kinds.index("turn_done")
    assert client.get("/api/state")[1]["session"]["purpose"] == "explore"
    # Busy is cleared before turn_done is announced, so sending the moment
    # it arrives is accepted rather than refused as "still answering".
    model.replies = [Reply(text="Again.")]
    assert client.post("/api/chat", {"text": "again"})[0] == 200
    wait_for(app, "turn_done", after=done["seq"])


def test_selected_profile_requires_its_own_fresh_role_qualification(served):
    """A screened Lead is not silently evidence for a different agent role."""
    app, client, model = served
    assert client.post("/api/tiers", {"tiers": [{"provider": "deepinfra", "model": "m1"}],
                                       "override": "test profile policy"})[0] == 200
    assert client.post("/api/agent-profile", {"id": "research_helper"})[0] == 200

    blocked, body = client.post("/api/chat", {"text": "help me inspect this"})
    assert blocked == 409
    assert "requires screened qualification" in body["error"]
    assert body["plan"]["role"] == "research_helper"

    fingerprints = app._qualification_fingerprints("preset-deepinfra", "m1", "research_helper")
    app.qualifications.record(host_id="preset-deepinfra", model_id="m1", role="research_helper",
                              level="L1", outcome="pass",
                              compatibility_fingerprint=fingerprints["compatibility"],
                              behavior_fingerprint=fingerprints["behavior"],
                              detail="role-specific smoke probe",
                              probe_validation={"contract_version": L1_PROBE_CONTRACT_VERSION,
                                                "passed": True})
    model.replies = [Reply(text="I can help with the supplied read-only profile.")]
    assert client.post("/api/chat", {"text": "help me inspect this"}) == (200, {"accepted": True})
    assert wait_for(app, "turn_done")["reply"] == "I can help with the supplied read-only profile."


def test_experimental_lead_selection_uses_a_route_scoped_ui_checkpoint(served):
    """The compatibility override is now an auditable UI decision, not prompt prose."""
    app, client, _ = served
    route = [{"provider": "deepinfra", "model": "checkpoint-model"}]

    status, waiting = client.post("/api/tiers", {"tiers": route})
    assert status == 409 and waiting["needs_override"]
    checkpoint = waiting["checkpoint_record"]
    assert checkpoint["type"] == "host_model_override"
    assert checkpoint["resolution"] == ""
    assert app.checkpoint_resolve(checkpoint["id"], "approve")["resolution"] == "approve"

    status, selected = client.post("/api/tiers", {"tiers": route, "checkpoint_id": checkpoint["id"]})
    assert status == 200, selected
    assert selected["lead"]["status"] == "override"
    assert app.checkpoint_list()["checkpoints"][-1]["scope"] == checkpoint["scope"]


def test_verified_release_lead_first_run_requires_a_visible_l1_checkpoint_then_selects(served, monkeypatch):
    """A release result is not silently trusted or silently made chargeable."""
    import resource_librarian.app as app_module
    import resource_librarian.hosts as hosts_module
    from resource_librarian.hosts import (RELEASE_PROMPT_CONTRACT_VERSION,
                                          RELEASE_TOOL_CONTRACT_VERSION, digest,
                                          endpoint_fingerprint)

    app, client, _ = served
    route = app._release_contract("preset-openai")
    endpoint = route["endpoint"]
    model_id = "release-model-2026-10-01"
    lead = {
        "id": "release-openai-test", "provider": "openai", "host_id": "preset-openai",
        "model": model_id, "model_version": model_id, "role": "lead",
        "qualification": "verified_release",
        "model_fingerprint": digest({"provider": "openai", "model": model_id,
                                      "model_version": model_id}),
        "endpoint": endpoint, "endpoint_fingerprint": endpoint_fingerprint(endpoint),
        "l3_runs": 5, "tested_at": "2026-10-01T00:00:00+00:00",
        "expires_at": "2027-01-01T00:00:00+00:00",
        "qualification_artifacts": [{"id": "ci://golden/openai", "sha256": "b" * 64}],
    }
    manifest = {
        "schema_version": 2, "release_status": "stable", "release_version": "2.1.0",
        "signing": {"status": "signed", "verification": {
            "id": "ci-signature", "verified_at": "2026-10-01T01:00:00+00:00"}},
        "contract": {"protocol_version": route["protocol_version"],
                     "tool_contract_version": RELEASE_TOOL_CONTRACT_VERSION,
                     "prompt_contract_version": RELEASE_PROMPT_CONTRACT_VERSION,
                     "core_version_range": ">=2.1.0,<2.2.0"}, "leads": [lead],
    }
    manifest["integrity"] = digest(manifest)
    from resource_librarian.hosts import release_leads
    path = app.vault.librarian / "test-release-leads.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(app_module, "release_leads", lambda: release_leads(path))
    # ``lead_status`` intentionally rechecks the same bundled file before
    # accepting the tier, so model its production source rather than only the
    # first-run UI reader.
    monkeypatch.setattr(hosts_module, "release_leads", lambda: release_leads(path))
    probe_provider = providers.Scripted(
        lambda *_: Reply(tool_calls=[ToolCall("probe", "librarian_probe", {"ok": True})],
                         model=model_id), name=model_id)
    monkeypatch.setattr(app, "_configured_provider", lambda _choice: probe_provider)

    status, waiting = client.post("/api/release-leads/select", {
        "id": "release-openai-test", "key": "test-secret"})
    assert status == 409
    checkpoint = waiting["checkpoint_record"]
    assert checkpoint["type"] == "evaluation_spend"
    assert app.checkpoint_resolve(checkpoint["id"], "approve")["resolution"] == "approve"

    status, selected = client.post("/api/release-leads/select", {
        "id": "release-openai-test", "checkpoint_id": checkpoint["id"]})
    assert status == 200, selected
    assert selected["selected"] is True, json.dumps(selected, indent=2)
    assert selected["tiers"] == [{"host_id": "preset-openai", "provider": "preset-openai",
                                   "model": model_id}]
    assert selected["lead_status"]["result"] == "verified_release"
    # The account probe is evidence for this exact bundled lead rather than
    # an indistinguishable default smoke test.
    assert selected["probe"]["run"]["scenario"] == "release:release-openai-test"


@pytest.mark.parametrize(("reply", "failure"), [
    (Reply(model="m1"), "tool_call_count"),
    (Reply(tool_calls=[ToolCall("probe", "wrong_probe", {"ok": True})], model="m1"), "tool_name"),
    (Reply(tool_calls=[ToolCall("probe", "librarian_probe", {"ok": "true"})], model="m1"),
     "tool_arguments"),
    (Reply(tool_calls=[ToolCall("probe", "librarian_probe", {"ok": True, "extra": 1})], model="m1"),
     "tool_arguments"),
    (Reply(tool_calls=[ToolCall("one", "librarian_probe", {"ok": True}),
                       ToolCall("two", "librarian_probe", {"ok": True})], model="m1"), "tool_call_count"),
    (Reply(tool_calls=[ToolCall("probe", "librarian_probe", {"ok": True})]), "returned_model_missing"),
    (Reply(tool_calls=[ToolCall("probe", "librarian_probe", {"ok": True})], model="other-model"),
     "returned_model_mismatch"),
])
def test_l1_rejects_any_non_strict_tool_or_route_contract(served, monkeypatch, reply, failure):
    """A reachable route is not screened until its full L1 contract passes."""
    app, _, _ = served
    provider = providers.Scripted(lambda *_: reply, name="m1")
    monkeypatch.setattr(app, "_configured_provider", lambda _choice: provider)

    result = app.run_qualification("preset-deepinfra", "m1", "lead", "L1", True)

    run = result["run"]
    assert run["outcome"] == "fail"
    assert run["probe_validation"]["contract_version"] == L1_PROBE_CONTRACT_VERSION
    assert run["probe_validation"]["passed"] is False
    assert failure in run["probe_validation"]["failure_codes"]
    assert result["status"]["qualification"]["status"] == "experimental"


def test_l1_records_strict_route_and_tool_evidence(served, monkeypatch):
    app, _, _ = served
    provider = providers.Scripted(
        lambda *_: Reply(tool_calls=[ToolCall("probe", "librarian_probe", {"ok": True})], model="m1"),
        name="m1",
    )
    monkeypatch.setattr(app, "_configured_provider", lambda _choice: provider)

    result = app.run_qualification("preset-deepinfra", "m1", "lead", "L1", True)

    run = result["run"]
    assert run["outcome"] == "pass"
    assert run["probe_validation"] == {
        "contract_version": L1_PROBE_CONTRACT_VERSION,
        "passed": True,
        "checks": {"exactly_one_call": True, "tool_name": True,
                   "arguments": True, "returned_model": True},
        "failure_codes": [], "requested_model": "m1", "observed_model": "m1",
    }
    assert result["status"]["qualification"]["status"] == "screened"


def test_host_controls_have_an_explicit_partial_update_contract(served):
    app, client, _ = served
    app.hosts.mark_health("preset-deepinfra", ok=True, detail="previous check", model="m1")
    before = app.hosts.get("preset-deepinfra")
    identity = (before.protocol, before.base_url, before.auth_ref, before.endpoint_fingerprint)
    history = list(before.health_history)

    status, body = client.post("/api/hosts", {"host": {"id": "preset-deepinfra", "timeout": 30}})
    assert status == 400
    assert body["error"] == "host_requires_full_record"
    assert set(body["missing_fields"]) == {"display_name", "protocol"}

    status, saved = client.post("/api/hosts/controls", {
        "host_id": "preset-deepinfra", "timeout": 30, "concurrency_limit": 2, "rate_limit": 8,
    })
    assert status == 200
    assert (saved["timeout"], saved["concurrency_limit"], saved["rate_limit"]) == (30, 2, 8)
    assert (saved["protocol"], saved["base_url"], saved["auth_ref"], saved["endpoint_fingerprint"]) == identity
    assert saved["health_history"] == history

    status, refused = client.post("/api/hosts/controls", {
        "host_id": "preset-deepinfra", "auth_ref": "other-key",
    })
    assert status == 400 and "host_controls_only_accept" in refused["error"]


def test_route_readiness_reuses_seeded_host_evidence_without_probe_spend(served):
    app, client, _ = served
    app.settings.update(tiers=[{"host_id": "preset-deepinfra", "provider": "preset-deepinfra",
                                "model": "m1"}])

    status, readiness = client.get("/api/routes/readiness")

    assert status == 200
    assert readiness["core"]["ok"] is True
    route = next(row for row in readiness["routes"]
                 if row["host_id"] == "preset-deepinfra" and row["model"] == "m1")
    assert route["qualification"]["status"] == "experimental"
    assert route["core_workflow"]["ok"] is True
    assert route["fixture_preflight"]["status"] == "not_run"
    # Legacy model cards retain their provider key while persisted tiers use
    # the seeded registry id, so the response deliberately has this alias.
    assert any(row["host_id"] == "deepinfra" and row["model"] == "m1"
               for row in readiness["routes"])


def test_route_readiness_is_passive_and_does_not_refresh_qualification(served, monkeypatch):
    """Opening the existing picker must not queue or spend evaluation work."""
    app, client, _ = served
    app.settings.update(tiers=[{"host_id": "preset-deepinfra", "provider": "preset-deepinfra",
                                "model": "m1"}])

    def qualification_read_would_mutate(*_args, **_kwargs):
        raise AssertionError("route readiness must not refresh qualification evidence")

    monkeypatch.setattr(app, "qualification_status", qualification_read_would_mutate)
    status, readiness = client.get("/api/routes/readiness")

    assert status == 200
    assert readiness["core"]["ok"] is True


def test_route_readiness_keeps_the_existing_picker_available_if_its_self_check_fails(
        served, monkeypatch):
    """Diagnostic readiness must not turn a recoverable Core check into a UI outage."""
    app, client, _ = served
    app.settings.update(tiers=[{"host_id": "preset-deepinfra", "provider": "preset-deepinfra",
                                "model": "m1"}])
    monkeypatch.setattr(app, "_l0_contract_check",
                        lambda: (_ for _ in ()).throw(RuntimeError("test-only fault")))

    status, readiness = client.get("/api/routes/readiness")

    assert status == 200
    assert readiness["core"] == {
        "ok": False,
        "status": "error",
        "detail": "Core workflow self-check is unavailable; route selection remains available.",
        "profile": "lead",
        "session": "",
    }
    assert any(row["model"] == "m1" for row in readiness["routes"])


def test_route_readiness_flags_a_selected_profile_that_cannot_lead_project_walks(served):
    """The existing picker must not report a read-only Lead surface as ready."""
    app, client, _ = served
    status, saved = client.post("/api/profiles", {"profile": {
        "id": "restricted-lead", "role": "lead", "permission_ceiling": "consult",
        "allowed_bundles": ["read"],
    }})
    assert status == 200 and saved["id"] == "restricted-lead"
    assert client.post("/api/agent-profile", {"id": "restricted-lead"})[0] == 200

    status, readiness = client.get("/api/routes/readiness")

    assert status == 200
    assert readiness["core"]["ok"] is False
    assert readiness["core"]["status"] == "blocked"
    assert readiness["core"]["profile"] == "restricted-lead"
    assert "create_project" in readiness["core"]["detail"]


def test_route_readiness_uses_the_selected_profiles_runtime_role_for_evidence(served, monkeypatch):
    """A custom profile id must not fork the Lead qualification namespace."""
    app, _, _ = served
    app.profile_save({"id": "field-lead", "role": "lead", "permission_ceiling": "contribute",
                      "allowed_bundles": ["session", "research"]})
    observed_roles = []
    original = app._qualification_fingerprints

    def capture(host_id, model, role):
        observed_roles.append(role)
        return original(host_id, model, role)

    monkeypatch.setattr(app, "_qualification_fingerprints", capture)
    readiness = app.route_readiness("field-lead")

    assert readiness["core"]["profile"] == "field-lead"
    assert observed_roles and set(observed_roles) == {"lead"}


def test_custom_host_model_discovery_routes_by_registry_id(served, monkeypatch):
    app, client, _ = served
    status, saved = client.post("/api/hosts", {"host": {
        "id": "studio-lan", "display_name": "Studio LAN", "protocol": "openai",
        "base_url": "http://127.0.0.1:1234/v1", "auth_ref": "", "enabled": True,
        "timeout": 30, "concurrency_limit": 2, "rate_limit": 12,
    }})
    assert status == 200 and saved["id"] == "studio-lan"
    calls = []
    custom = providers.Scripted(lambda *_: Reply(), name="local-tool-model")

    def configured(choice):
        calls.append(choice)
        return custom

    monkeypatch.setattr(app, "_provider_for", configured)
    status, listing = client.get("/api/models?provider=studio-lan")
    assert status == 200
    assert listing["models"][0]["id"] == "local-tool-model"
    assert calls == [{"host_id": "studio-lan"}]


def test_ask_mode_waits_for_the_person_and_a_mode_switch_releases_it(served):
    app, client, model = served
    client.post("/api/tiers", {"tiers": [{"provider": "deepinfra", "model": "m1"}], "override": "test"})
    client.post("/api/mode", {"mode": "ask"})
    model.replies = [Reply(tool_calls=[ToolCall("1", "create_project", {
        "name": "Host Watch", "stage": "idea", "summary": "Watch hosts."})]),
        Reply(text="Created.")]
    client.post("/api/chat", {"text": "make the project"})
    request = wait_for(app, "permission_request")
    assert request["tool"] == "create_project"
    assert client.get("/api/state")[1]["pending"][0]["id"] == request["id"]
    assert client.post("/api/mode", {"mode": "auto"})[1]["released"] == [request["id"]]
    assert wait_for(app, "turn_done")["reply"] == "Created."
    assert (app.vault.root / "Projects" / "Host Watch.md").is_file()


def test_a_denied_request_reaches_the_model_as_a_refusal(served):
    app, client, model = served
    client.post("/api/tiers", {"tiers": [{"provider": "deepinfra", "model": "m1"}], "override": "test"})
    model.replies = [Reply(tool_calls=[ToolCall("1", "create_project", {
        "name": "Nope", "stage": "idea", "summary": "x"})]), Reply(text="Understood.")]
    client.post("/api/chat", {"text": "make it"})
    request = wait_for(app, "permission_request")
    assert client.post("/api/permission", {"id": request["id"], "answer": "deny"})[0] == 200
    wait_for(app, "turn_done")
    result = [e for e in app.hub.since(0) if e["type"] == "tool_result"][0]["result"]
    assert result["refused"] == "PERMISSION_DENIED"
    assert not (app.vault.root / "Projects" / "Nope.md").exists()


def test_answering_a_question_wakes_the_waiting_turn(served):
    """The gate bug: answering a question the model asked used to be inert -
    nothing fed it back to the loop, or resumed the turn. `ask_user` now
    really blocks the turn's own thread (Waiters, tools/sessions.py), the
    same handshake a permission gate already uses, so the model sees the
    real answer and finishes the SAME turn - no second message needed."""
    app, client, model = served
    client.post("/api/tiers", {"tiers": [{"provider": "deepinfra", "model": "m1"}], "override": "test"})
    model.replies = [
        Reply(tool_calls=[ToolCall("1", "open_session", {"purpose": "explore",
                                                          "question": "hosts"})]),
        Reply(tool_calls=[ToolCall("2", "ask_user", {"question": "Which host?"})]),
        Reply(text="Noted: Prod-01."),
    ]
    client.post("/api/chat", {"text": "explore hosts"})
    asked = wait_for(app, "question_asked")
    assert asked["question"] == "Which host?"
    answered = client.post("/api/tool/answer", {
        "arguments": {"question_id": asked["question_id"], "answer": "Prod-01"},
        "session": asked["session"]})
    assert answered[0] == 200 and answered[1]["resumed"] is True
    wait_for(app, "question_answered")
    done = wait_for(app, "turn_done")
    assert done["reply"] == "Noted: Prod-01."
    tool_results = [e["result"] for e in app.hub.since(0)
                    if e["type"] == "tool_result" and e["tool"] == "ask_user"]
    assert tool_results[-1]["answer"] == "Prod-01"
    assert "needs_person" not in tool_results[-1]


def test_keys_are_saved_confirmed_and_never_returned(served, tmp_path, monkeypatch):
    app, client, _ = served
    secret = "sk-test-SECRET-7f3a"
    saved = client.post("/api/keys", {"provider": "deepinfra", "key": secret})
    assert saved[0] == 200 and saved[1]["last4"] == "7f3a" and saved[1]["saved"]
    again = client.post("/api/keys", {"provider": "deepinfra", "key": "sk-other-key-1111"})
    assert again[0] == 409 and "Replace the saved DeepInfra key?" in again[1]["confirm"]
    everything = json.dumps([client.get("/api/state")[1], client.get("/api/keys")[1],
                             app.hub.since(0)])
    assert secret not in everything and "SECRET" not in everything
    stored = tmp_path / "config" / ".env"
    assert stored.is_file() and keys.owner_only(stored)      # 0600, or its Windows ACL
    assert not list(app.vault.root.rglob(".env"))                 # never inside the vault
    assert client.post("/api/keys/remove", {"provider": "deepinfra"})[0] == 409
    removed = client.post("/api/keys/remove", {"provider": "deepinfra", "confirm": True})
    assert removed[1]["saved"] is False


def test_the_persons_own_calls_and_settings(served):
    app, client, _ = served
    status, found = client.post("/api/tool/search", {"arguments": {"query": "operating system"}})
    assert status == 200 and found["results"][0]["name"] == "osquery"
    tools = client.get("/api/tools")[1]["tools"]
    assert "accept_workflow" in {t["name"] for t in tools}          # the person is curate
    context = client.post("/api/context", {"working_context": "a thesis on hosts",
                                           "reply_length": "short"})[1]
    assert context == {"working_context": "a thesis on hosts", "reply_length": "short",
                       "stance": "answer"}
    assert json.loads((app.vault.librarian / "app.json").read_text())["reply_length"] == "short"
    assert client.post("/api/context", {"stance": "coach"})[1]["stance"] == "coach"
    assert client.post("/api/context", {"stance": "nope"})[0] == 400
    library = client.post("/api/library", {"promotion_mode": "agent"})[1]
    assert library["promotion"]["mode"] == "agent" and library["doctor"]
    assert client.post("/api/tiers", {"tiers": [{"provider": "nope", "model": "x"}]})[0] == 400


def test_choosing_a_lead_keeps_the_scribe_and_clerk_positions(served, vault):
    """ROUTE-01: "Use as lead" used to send a one-item tier list and silently
    drop positions 2-3."""
    from resource_librarian.app import Settings
    app, client, model = served
    three = [{"provider": "deepinfra", "model": "lead-a"},
             {"provider": "deepinfra", "model": "scribe-b"},
             {"provider": "deepinfra", "model": "clerk-c"}]
    assert client.post("/api/tiers", {"tiers": three, "override": "test"})[0] == 200
    status, body = client.post("/api/lead", {"route": {"provider": "deepinfra", "model": "lead-z"},
                                             "override": "test"})
    assert status == 200
    assert [t["model"] for t in body["tiers"]] == ["lead-z", "scribe-b", "clerk-c"]
    # Reopen: the saved settings carry all three positions.
    assert [t["model"] for t in Settings(vault).data["tiers"]] == ["lead-z", "scribe-b", "clerk-c"]
    # With only a lead chosen, choosing another adds no phantom positions.
    client.post("/api/tiers", {"tiers": three[:1], "override": "test"})
    assert [t["model"] for t in client.post("/api/lead", {"route": three[1], "override": "test"})[1]["tiers"]] \
        == ["scribe-b"]
    assert client.post("/api/lead", {"route": "not-a-route"})[0] == 400


def test_tiers_fall_back_upward(served):
    app, client, model = served
    client.post("/api/tiers", {"tiers": [{"provider": "deepinfra", "model": "big"}], "override": "test"})
    assert app.tier(3) is model.provider                           # tier 3 -> 2 -> 1
    client.post("/api/tiers", {"tiers": []})                       # clear selection
    assert app.tier(1) is None


def test_existing_provider_tiers_migrate_to_explicit_seeded_or_custom_hosts(vault, tmp_path, monkeypatch):
    """Old global base URLs become visible host records without losing their route."""
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path / "config"))
    app_state = vault.librarian / "app.json"
    state = json.loads(app_state.read_text(encoding="utf-8")) if app_state.is_file() else {}
    state.update({
        "tiers": [{"provider": "deepinfra", "model": "legacy-default"},
                  {"provider": "local", "model": "legacy-local"}],
        "base_urls": {"local": "http://127.0.0.1:11999/v1"},
    })
    app_state.write_text(json.dumps(state), encoding="utf-8")
    app = App(vault, keys=KeyStore(use_keyring=False), provider_for=lambda _choice: None)
    try:
        first, second = app.settings.data["tiers"]
        assert first == {"host_id": "preset-deepinfra", "provider": "preset-deepinfra",
                         "model": "legacy-default"}
        assert second["host_id"].startswith("legacy-local-")
        assert second["provider"] == second["host_id"] and second["model"] == "legacy-local"
        assert app.hosts.get(second["host_id"]).base_url == "http://127.0.0.1:11999/v1"
        assert app.settings.data["host_route_migration"] == 1
    finally:
        app.close_runtime()


def test_a_queued_action_asks_in_ask_mode_and_can_be_cancelled(served):
    app, client, _ = served
    status, action = client.post("/api/actions", {"name": "run-queue"})
    assert status == 200 and action["status"] == "running"
    request = wait_for(app, "permission_request")                # its write waits, in Ask
    assert request["tool"] == "intake_run"
    assert client.post(f"/api/actions/{action['id']}/cancel")[1] == {"cancelling": action["id"]}
    client.post("/api/permission", {"id": request["id"], "answer": "allow_once"})
    done = wait_for(app, "action_done")
    assert done["id"] == action["id"] and done["status"] == "finished"

    client.post("/api/mode", {"mode": "auto"})
    after = app.hub.last()
    second = client.post("/api/actions", {"name": "run-queue"})[1]
    done = wait_for(app, "action_done", after=after)
    assert done["id"] == second["id"] and done["status"] == "finished"
    assert not [e for e in app.hub.since(after) if e["type"] == "permission_request"]
    assert client.post("/api/actions", {"name": "no-such-pipeline"})[0] == 404
    assert client.post("/api/actions/zzz/cancel")[0] == 404


def test_a_cancelled_run_pauses_before_its_next_step(vault):
    from resource_librarian import workflows
    from resource_librarian.registry import Context
    from resource_librarian.tools.workflows import _library
    cancel = threading.Event()
    cancel.set()
    ctx = Context(tier="contribute", vault=vault, extras={"cancel": cancel})
    out = workflows.Runner(_library(ctx), ctx).start("run-queue")
    assert out["status"] == "paused" and out["reason"] == "cancelled by a person"
    cancel.clear()
    resumed = workflows.Runner(_library(ctx), ctx).resume(out["run"])
    assert resumed["status"] == "finished"


def test_only_a_host_origin_may_read_across_origins(served):
    app, client, _ = served
    status, _ = client.request("OPTIONS", "/api/state", token=False,
                               headers={"Origin": "app://obsidian.md"})
    assert status == 204
    assert client.request("OPTIONS", "/api/state", token=False,
                          headers={"Origin": "https://evil.example"})[0] == 403
    req = urllib.request.Request(client.base + "/api/state", headers={
        "X-Librarian-Token": client.token, "Origin": "app://obsidian.md"})
    with urllib.request.urlopen(req) as response:
        assert response.headers["Access-Control-Allow-Origin"] == "app://obsidian.md"
    req = urllib.request.Request(client.base + "/api/state", headers={
        "X-Librarian-Token": client.token, "Origin": "https://evil.example"})
    with urllib.request.urlopen(req) as response:
        assert response.headers["Access-Control-Allow-Origin"] is None


def test_the_pane_reads_the_vaults_notes_and_nothing_else(served):
    app, client, _ = served
    status, top = client.get("/api/files")
    names = {e["name"]: e for e in top["entries"]}
    assert status == 200 and names["Sources"]["kind"] == "dir"
    assert not [n for n in names if n.startswith(".")]            # .librarian, .obsidian...
    assert top["entries"][0]["kind"] == "dir"                       # folders first
    inner = client.get("/api/files?dir=Sources/repository")[1]
    assert {"name": "osquery", "kind": "file", "path": "Sources/repository/osquery.md"} in inner["entries"]

    by_path = client.get("/api/file?path=Sources/repository/osquery")[1]
    assert by_path["name"] == "osquery" and by_path["text"].startswith("---\n")
    by_name = client.get("/api/file?path=osquery")[1]              # what a bare [[link]] holds
    assert by_name["path"] == "Sources/repository/osquery.md"
    assert client.get("/api/file?path=Sources/repository/osquery.md")[1]["path"] == by_name["path"]

    assert client.get("/api/file?path=.librarian/config.toml")[0] == 403
    assert client.get("/api/file?path=.librarian/app")[0] == 403
    assert client.get("/api/files?dir=../..")[0] == 403
    assert client.get("/api/file?path=../../etc/passwd")[0] == 403
    assert client.get("/api/file?path=nothing-by-this-name")[0] == 404
    assert client.get("/api/files", token=False)[0] == 403


def test_attach_saves_a_file_a_person_can_then_ingest(served, monkeypatch):
    """The composer's paperclip: a file lands in Inbox/, a name collision
    doesn't clobber the first one, and the path it hands back is exactly what
    `ingest` already knows how to take (see test_intake's file capture)."""
    app, client, _ = served
    status, out = client.upload("/api/attach?name=paper.pdf", b"%PDF-1.4 not a real pdf")
    assert status == 200, out
    assert out == {"path": "Inbox/paper.pdf", "name": "paper.pdf"}
    assert (app.vault.root / "Inbox" / "paper.pdf").read_bytes() == b"%PDF-1.4 not a real pdf"

    status2, out2 = client.upload("/api/attach?name=paper.pdf", b"a second, different file")
    assert status2 == 200 and out2["path"] == "Inbox/paper (1).pdf"
    assert (app.vault.root / "Inbox" / "paper.pdf").read_bytes() == b"%PDF-1.4 not a real pdf"

    assert client.upload("/api/attach?name=x.txt", b"x", token=False)[0] == 403
    assert client.upload("/api/attach?dir=..&name=x.txt", b"x")[0] == 403

    import resource_librarian.app as app_module
    monkeypatch.setattr(app_module, "MAX_UPLOAD", 4)
    status3, out3 = client.upload("/api/attach?name=big.bin", b"too many bytes")
    assert status3 == 413, out3


def test_models_shows_profiled_queued_and_unprofiled(served, monkeypatch):
    """The Model tile's whole point: a catalogued model Source shows its real
    specs, a staged one says it is awaiting review, and only a genuinely
    unprofiled one is unprofiled."""
    from resource_librarian import clerk, intake
    from resource_librarian.registry import Context
    from test_intake import MODEL_PAGE, model_answers

    app, client, model = served
    model.provider.models = lambda: ["openai/gpt-oss-20b", "acme/still-unprofiled",
                                     "acme/queued-model"]

    c = Context(tier="curate", vault=app.vault, extras={
        "clerk": clerk.Scripted(model_answers),
        "fetcher": intake.Replay({"https://deepinfra.com/openai/gpt-oss-20b": MODEL_PAGE})})
    profiled = REGISTRY_CALL(c, "ingest", ref="model:deepinfra:openai/gpt-oss-20b")
    REGISTRY_CALL(c, "staging_decide", item_ids=[profiled["item"]], decision="accept")
    # queued: staged, no draft, left waiting (as a real "no clerk endpoint" run would)
    queued_ctx = Context(tier="curate", vault=app.vault, extras={
        "fetcher": intake.Replay({"https://deepinfra.com/acme/queued-model": MODEL_PAGE})})
    REGISTRY_CALL(queued_ctx, "ingest", ref="model:deepinfra:acme/queued-model")

    listing = client.get("/api/models?provider=deepinfra")[1]
    by_id = {m["id"]: m for m in listing["models"]}
    done = by_id["openai/gpt-oss-20b"]
    assert done["profile"]["tool_calling"] is True and done["profile"]["suggested_tier"] == "Tier_3"
    assert done["profile"]["best_for"] == ["Small_Coding_Tasks"]
    assert done["profile"]["context_length"] == 131072
    assert done["profile"]["path"].startswith("Sources/model/")
    # Adapter data is passive picker evidence: it must not turn a descriptive
    # catalogue flag into a claimed, model-specific tool guarantee.
    assert done["adapter"]["id"] == "legacy_provider_chat"
    assert done["adapter"]["capabilities"]["tool_use"] == "unknown"
    assert by_id["acme/queued-model"].get("profiling") == "queued"
    assert "profile" not in by_id["acme/still-unprofiled"] and \
        "profiling" not in by_id["acme/still-unprofiled"]


def test_unassessed_tool_calling_is_unknown_not_false(served, monkeypatch):
    """ROUTE-02: `bool(None)` used to turn "not yet assessed" into "no", and the
    tile blocks an explicit "no" from leading."""
    from resource_librarian import app as app_module
    app, client, model = served
    model.provider.models = lambda: ["acme/yes", "acme/no", "acme/unassessed"]
    shipped = {("deepinfra", "acme/yes"): {"tool_calling": True},
               ("deepinfra", "acme/no"): {"tool_calling": "false"},
               ("deepinfra", "acme/unassessed"): {"modality": "Text_Generation"}}
    monkeypatch.setattr(app_module, "_shipped_profiles", lambda: shipped)
    by_id = {m["id"]: m for m in client.get("/api/models?provider=deepinfra")[1]["models"]}
    assert by_id["acme/yes"]["profile"]["tool_calling"] is True
    assert by_id["acme/no"]["profile"]["tool_calling"] is False
    assert by_id["acme/unassessed"]["profile"]["tool_calling"] is None
    assert by_id["acme/unassessed"]["profile"]["reasoning"] is None


def REGISTRY_CALL(ctx, name, **arguments):
    from resource_librarian.registry import REGISTRY
    result = REGISTRY.call(name, arguments, ctx)
    assert "error" not in result, result
    return result


def test_api_usage_falls_back_to_the_dashboard_link(served):
    """The scripted provider (like most real providers) has no usage endpoint:
    the settings page must still get a dashboard link, never a 500."""
    _, client, _ = served
    out = client.get("/api/usage?provider=deepinfra")[1]
    assert out["ok"] is False and out["dashboard"] == "https://deepinfra.com/dash"
    assert "usage endpoint" in out["error"]
    unknown = client.get("/api/usage?provider=nope")[1]
    assert unknown["ok"] is False and unknown["dashboard"] == ""


def test_api_usage_reports_a_working_deepinfra_balance(served, monkeypatch):
    app, client, model = served
    model.provider.usage = lambda: {"stripe_balance": 4.2, "suspended": False,
                                    "billing_type": "prepaid"}
    out = client.get("/api/usage?provider=deepinfra")[1]
    assert out == {"ok": True, "dashboard": "https://deepinfra.com/dash", "unofficial": True,
                  "balance": 4.2, "currency": "USD", "suspended": False,
                  "billing_type": "prepaid"}


# -- MCP servers (Co-work Roadmap §3, Phase 1) -----------------------------------

pytest.importorskip("mcp")
FAKE_MCP_SERVER = str(Path(__file__).parent / "fixtures" / "fake_mcp_server.py")


def test_api_mcp_status_is_empty_with_no_servers_configured(served):
    _, client, _ = served
    status, out = client.get("/api/mcp")
    assert status == 200 and out["servers"] == {}


def test_api_mcp_save_a_server_needs_acceptance_before_it_connects(served):
    import sys
    _, client, _ = served
    status, out = client.post("/api/mcp/config", {
        "mcpServers": {"fake": {"command": sys.executable, "args": [FAKE_MCP_SERVER]}}})
    assert status == 200
    assert out["servers"]["fake"]["accepted"] is False
    assert out["servers"]["fake"]["connected"] is False
    assert out["servers"]["fake"]["command"] == sys.executable
    assert "env" not in out["servers"]["fake"] or out["servers"]["fake"]["env"] == []


def test_api_mcp_accept_connects_and_registers_its_tools(served):
    import sys
    from resource_librarian.registry import REGISTRY
    app, client, _ = served
    client.post("/api/mcp/config", {
        "mcpServers": {"fake": {"command": sys.executable, "args": [FAKE_MCP_SERVER]}}})
    status, out = client.post("/api/mcp/accept", {"name": "fake"})
    assert status == 200
    assert out["servers"]["fake"]["accepted"] is True
    # Accepted for the person, but each library decides for itself (§4 F1):
    # not running here until this library turns it on.
    assert out["servers"]["fake"]["connected"] is False
    assert out["servers"]["fake"]["library_enabled"] is False
    status, out = client.post("/api/mcp/library", {"name": "fake", "enabled": True})
    assert status == 200 and out["servers"]["fake"]["library_enabled"] is True
    assert out["servers"]["fake"]["connected"] is True
    assert out["servers"]["fake"]["tools"] == 2
    assert sorted(out["servers"]["fake"]["tool_names"]) == ["mcp__fake__boom", "mcp__fake__echo"]
    assert out["tool_settings"]["mcp__fake__echo"] == "ask"
    assert "mcp__fake__echo" in REGISTRY.external_names()
    assert app.broker.settings["mcp__fake__echo"] == "ask"


def test_api_mcp_accept_refuses_an_unknown_server(served):
    _, client, _ = served
    status, out = client.post("/api/mcp/accept", {"name": "nope"})
    assert status == 404


def test_api_mcp_never_returns_an_env_value(served):
    import sys
    _, client, _ = served
    status, out = client.post("/api/mcp/config", {
        "mcpServers": {"fake": {"command": sys.executable, "args": [FAKE_MCP_SERVER],
                               "env": {"SOME_TOKEN": "literal-secret-value"}}}})
    assert status == 200
    body = json.dumps(out)
    assert "literal-secret-value" not in body
    assert out["servers"]["fake"]["env"] == ["SOME_TOKEN"]


def test_api_mcp_server_installs_and_accepts_in_one_step(served):
    import sys
    _, client, _ = served
    status, out = client.post("/api/mcp/server", {
        "name": "fake", "server": {"command": sys.executable, "args": [FAKE_MCP_SERVER]}})
    assert status == 200
    assert out["servers"]["fake"]["accepted"] is True
    assert out["servers"]["fake"]["connected"] is True
    assert out["servers"]["fake"]["tools"] == 2


def test_api_mcp_server_needs_a_name(served):
    import sys
    _, client, _ = served
    status, out = client.post("/api/mcp/server", {
        "server": {"command": sys.executable, "args": [FAKE_MCP_SERVER]}})
    assert status == 400


def test_api_mcp_enable_toggles_without_losing_acceptance(served):
    import sys
    _, client, _ = served
    client.post("/api/mcp/server", {
        "name": "fake", "server": {"command": sys.executable, "args": [FAKE_MCP_SERVER]}})
    status, out = client.post("/api/mcp/enable", {"name": "fake", "enabled": False})
    assert status == 200 and out["servers"]["fake"]["connected"] is False
    status, out = client.post("/api/mcp/enable", {"name": "fake", "enabled": True})
    assert status == 200
    assert out["servers"]["fake"]["accepted"] is True      # never had to re-accept
    assert out["servers"]["fake"]["connected"] is True


def test_api_mcp_enable_refuses_an_unknown_server(served):
    _, client, _ = served
    status, out = client.post("/api/mcp/enable", {"name": "nope", "enabled": True})
    assert status == 404


def test_api_mcp_remove_disconnects_and_forgets_the_server(served):
    import sys
    from resource_librarian.registry import REGISTRY
    _, client, _ = served
    client.post("/api/mcp/server", {
        "name": "fake", "server": {"command": sys.executable, "args": [FAKE_MCP_SERVER]}})
    status, out = client.post("/api/mcp/remove", {"name": "fake"})
    assert status == 200 and out["servers"] == {}
    assert REGISTRY.external_names() == []


def test_api_mcp_registry_proxies_the_search_server_side(served, monkeypatch):
    import resource_librarian.mcp_client as mcp_client
    _, client, _ = served
    monkeypatch.setattr(mcp_client, "REGISTRY_SEARCH_URL", "http://127.0.0.1:1/v0/servers")
    status, out = client.get("/api/mcp/registry?q=semantic")
    assert status == 200 and out["servers"] == [] and "error" in out



def test_settings_turn_the_review_gate_on_and_save_a_search_key(served):
    """Owner checks O4/O5 and O3b (2026-10-01): no switch for the review gate, and no
    place for a web search key."""
    app, client, _ = served
    status, lib = client.post("/api/library", {"review": {"review_replies": True,
                                                          "review_offerings": True}})
    assert status == 200 and lib["clerk"]["review_replies"] is True
    assert app.vault.config()["clerk"]["review_offerings"] is True
    assert client.post("/api/library", {"review": {"review_everything": True}})[0] == 400
    assert client.post("/api/library", {"promotion_mode": "agent"})[1]["promotion"]["mode"] == "agent"
    status, out = client.post("/api/keys", {"provider": "tavily", "key": "tvly-test-0123456789"})
    assert status == 200 and out["saved"] and out["check"]["ok"]
    assert "Tavily" in out["check"]["status"]
    keys = {k["provider"]: k for k in client.get("/api/keys")[1]["keys"]}
    assert keys["tavily"]["saved"] and keys["tavily"]["last4"] == "6789"
    assert not keys["brave"]["saved"]



def test_the_capability_list_names_each_keys_store_entry(served):
    """A key row in Settings -> Library opens a box to set that key (owner, 2026-10-02)."""
    app, client, _ = served
    rows = {c["name"]: c for c in client.get("/api/library")[1]["doctor"]}
    assert rows["key: Tavily (web search)"]["key"] == "tavily"
    assert rows["key: GitHub"]["key"] == "github" and rows["key: DeepInfra"]["key"] == "deepinfra"
    assert "key" not in rows["pyyaml"]
    status, out = client.post("/api/keys", {"provider": "github", "key": "ghp_test0123456789"})
    assert status == 200 and out["saved"] and "Repository intake" in out["check"]["status"]
    rows = {c["name"]: c for c in client.get("/api/library")[1]["doctor"]}
    assert rows["key: GitHub"]["ok"]
