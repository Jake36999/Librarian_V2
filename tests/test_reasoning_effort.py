"""Reasoning effort is configuration (owner, 2026-11-16): per role, per model, never in code.

DeepInfra's OpenAI-compatible API documents `reasoning_effort` (none ... max). Unset, nothing is
sent and the model keeps its default; a bad value is refused, never passed through.
"""
import pytest

from resource_librarian import clerk, pdf_markdown
from resource_librarian.adapters.openai_chat import OpenAIChatAdapter
from resource_librarian.providers import OpenAICompatible, reasoning_effort_for


def test_the_adapter_sends_reasoning_effort_only_when_set():
    plain = OpenAIChatAdapter.render("m", "sys", [{"role": "user", "content": "hi"}], [], max_tokens=10)
    assert "reasoning_effort" not in plain
    tuned = OpenAIChatAdapter.render("m", "sys", [{"role": "user", "content": "hi"}], [], max_tokens=10,
                                     reasoning_effort="low")
    assert tuned["reasoning_effort"] == "low" and list(tuned)[:3] == ["model", "max_tokens", "messages"]


def test_model_beats_role_and_unset_is_the_models_default():
    config = {"reasoning": {"clerk": "low", "models": {"Qwen/Qwen3.5-397B-A17B": "none"}}}
    assert reasoning_effort_for(config, "clerk", "google/gemma-4-26B-A4B-it") == "low"
    assert reasoning_effort_for(config, "clerk", "Qwen/Qwen3.5-397B-A17B") == "none"
    assert reasoning_effort_for(config, "scribe", "google/gemma-4-26B-A4B-it") == ""
    assert reasoning_effort_for({}, "clerk", "m") == ""
    with pytest.raises(ValueError, match="reasoning"):
        reasoning_effort_for({"reasoning": {"clerk": "loads"}}, "clerk", "m")
    with pytest.raises(ValueError):
        OpenAICompatible("http://x", "m", reasoning_effort="turbo")


def test_the_provider_puts_its_effort_on_the_wire(monkeypatch):
    from resource_librarian import providers
    sent = []
    monkeypatch.setattr(providers, "_request", lambda method, url, headers, body, *a, **k:
                        sent.append(body) or {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]})
    OpenAICompatible("http://x", "m", reasoning_effort="minimal").chat("s", [{"role": "user", "content": "q"}], [])
    OpenAICompatible("http://x", "m").chat("s", [{"role": "user", "content": "q"}], [])
    assert sent[0]["reasoning_effort"] == "minimal" and "reasoning_effort" not in sent[1]


def test_the_core_applies_the_library_setting_to_each_role(vault):
    from resource_librarian.app import App
    from resource_librarian.keys import KeyStore
    vault.set_setting("reasoning", "clerk", "low")
    app = App(vault, keys=KeyStore(use_keyring=False), coordinate=True,
              provider_for=lambda choice: OpenAICompatible("http://x", choice["model"]))
    try:
        app.set_tiers([{"provider": "deepinfra", "model": "lead-m"}, {"provider": "deepinfra", "model": "notes-m"},
                       {"provider": "deepinfra", "model": "bulk-m"}], override="test")
        assert app.role_provider("clerk").reasoning_effort == "low"
        assert app.role_provider("scribe").reasoning_effort == ""
    finally:
        app.close_runtime()


def test_the_clerk_config_endpoint_and_cleanup_read_it_too(vault, monkeypatch):
    ep = clerk.from_config({"provider": "deepinfra", "model": "m", "reasoning_effort": "low",
                            "route_points": "deepinfra:p", "reasoning_effort_points": "none"})
    bodies = []
    for endpoint in (ep.default, ep.routes["points"]):
        monkeypatch.setattr(endpoint, "_post", lambda body: bodies.append(body) or
                            {"choices": [{"message": {"content": "{\"bullets\": []}"}}]})
        endpoint.complete(clerk.points("Some text.").payload(), "")
    assert [b.get("reasoning_effort") for b in bodies] == ["low", "none"]
    vault.set_setting("reasoning", "cleanup", "none")
    assert pdf_markdown.endpoint(vault).reasoning_effort == "none"


# -- OCR (owner, 2026-11-16): the thinking switch was a model-name rule in code -------------

def _ocr_bodies(monkeypatch, vault, model):
    from resource_librarian import ocr, providers
    sent = []
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test-key")
    monkeypatch.setattr(providers, "_request", lambda method, url, headers, body, *a, **kw: (
        sent.append(body) or {"choices": [{"message": {"content": "text"}, "finish_reason": "stop"}],
                              "usage": {}}))
    ocr.VisionChat("deepinfra", model, vault=vault).page_text(b"png")
    return sent


def test_ocr_sends_the_shipped_default_none_and_no_model_name_rule(monkeypatch, tmp_path):
    from resource_librarian.vault import Vault
    (body,) = _ocr_bodies(monkeypatch, Vault(tmp_path), "Qwen/Qwen3.5-27B")
    assert body["reasoning_effort"] == "none"
    assert "chat_template_kwargs" not in body          # no Qwen-only template switch in code
    (other,) = _ocr_bodies(monkeypatch, Vault(tmp_path), "google/gemma-4-26B-A4B-it")
    assert other["reasoning_effort"] == "none"          # the same configuration for any model


def test_ocr_follows_the_librarys_role_and_model_settings(monkeypatch, tmp_path):
    from resource_librarian.vault import Vault
    vault = Vault(tmp_path)
    vault.set_setting("reasoning", "ocr", "low")
    (body,) = _ocr_bodies(monkeypatch, vault, "Qwen/Qwen3.5-27B")
    assert body["reasoning_effort"] == "low"
    (vault.librarian / "config.toml").write_text(
        '[reasoning]\nocr = "low"\n\n[reasoning.models]\n"Qwen/Qwen3.5-27B" = "none"\n', encoding="utf-8")
    (body,) = _ocr_bodies(monkeypatch, vault, "Qwen/Qwen3.5-27B")
    assert body["reasoning_effort"] == "none"


def test_ocr_request_sends_reasoning_effort_only_when_given():
    from resource_librarian.service_adapters import ocr_request
    plain, _ = ocr_request("deepinfra", "Qwen/Qwen3.5-397B-A17B", "p", "data:image/png;base64,AA")
    assert "reasoning_effort" not in plain and "chat_template_kwargs" not in plain
    tuned, _ = ocr_request("deepinfra", "Qwen/Qwen3.5-397B-A17B", "p", "data:image/png;base64,AA",
                           reasoning_effort="none")
    assert tuned["reasoning_effort"] == "none"
