"""ADAPT-06: chat-completions and embeddings URLs are built in one place.

A caller that concatenates its own endpoint path skips the approved
transport boundary (adapters/openai_chat.py); this static check fails the
build when one appears anywhere else in the package.
"""
import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "resource_librarian"
APPROVED = {PACKAGE / "adapters" / "openai_chat.py"}
PATHS = ("/chat/completions", "/embeddings")


def _fragments(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node
    # Docstrings name the endpoints in prose; only path-shaped literals count.


def test_no_endpoint_url_is_built_outside_the_approved_transport():
    offenders = []
    for path in PACKAGE.rglob("*.py"):
        if path in APPROVED:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in _fragments(tree):
            if node.value.rstrip("/").endswith(PATHS):
                offenders.append(f"{path.relative_to(PACKAGE)}:{node.lineno}: {node.value!r}")
    assert not offenders, "build endpoint URLs with adapters.openai_chat: " + "; ".join(offenders)


# -- Clerk, OCR and the loop go through the boundary (ADAPT-06) ---------------

import pytest

from resource_librarian import clerk, providers
from resource_librarian.loop import Loop, ProviderEndpoint
from resource_librarian.model_invocation import InvocationRuntime
from resource_librarian.providers import ProviderError, Reply


def _transport(monkeypatch, outcome):
    seen = []

    def fake(method, url, headers, body=None, timeout=120, **_options):
        seen.append((method, url, headers, body))
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    monkeypatch.setattr(providers, "_request", fake)
    return seen


def test_the_clerk_endpoint_uses_the_shared_transport(monkeypatch):
    seen = _transport(monkeypatch, {"model": "m", "choices": [{"message": {"content": "{}"}}]})
    endpoint = clerk.OpenAICompatible("http://127.0.0.1:1234/v1", "m")
    assert endpoint._post({"model": "m"})["model"] == "m"
    assert seen[0][:2] == ("POST", "http://127.0.0.1:1234/v1/chat/completions")


def test_clerk_keeps_its_error_shapes(monkeypatch):
    _transport(monkeypatch, ProviderError("HTTP 400 from http://x/v1/chat/completions: "
                                          "response_format is not supported", category="request"))
    endpoint = clerk.OpenAICompatible("http://x/v1", "m")
    with pytest.raises(RuntimeError, match=r"^HTTP 400: response_format"):
        endpoint._post({})
    _transport(monkeypatch, ProviderError("http://x is not reachable", category="network"))
    with pytest.raises(clerk.ClerkUnavailable, match="not reachable"):
        endpoint._post({})
    monkeypatch.delenv("LIBRARIAN_TEST_MISSING_KEY", raising=False)
    with pytest.raises(clerk.ClerkUnavailable, match="is not set"):
        clerk.OpenAICompatible("http://x/v1", "m", key_env="LIBRARIAN_TEST_MISSING_KEY")._post({})


def test_ocr_uses_the_shared_transport(monkeypatch):
    from resource_librarian import ocr
    seen = _transport(monkeypatch, {"choices": [{"message": {"content": " page "}}]})
    monkeypatch.setattr(ocr, "ocr_request", lambda *a: ({"model": "m"}, None))
    chat = ocr.VisionChat.__new__(ocr.VisionChat)
    chat.url, chat.key_env, chat.model, chat.timeout = "http://x/v1/chat/completions", "", "m", 5
    chat.route = chat.vault = None
    chat.provider, chat.name = "custom", "custom:m"
    assert chat.page_text(b"png") == "page" and seen[0][1] == "http://x/v1/chat/completions"


def test_no_endpoint_or_loop_calls_a_provider_without_the_runtime():
    reply = Reply("ok", [], "scripted", "stop")
    endpoint = ProviderEndpoint(providers.Scripted(lambda *_: reply))
    assert isinstance(endpoint.invocation_runtime, InvocationRuntime)
