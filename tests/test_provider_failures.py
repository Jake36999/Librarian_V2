"""Failure labels must describe the failed layer, not blame a model by default."""
from __future__ import annotations

import io
import urllib.error

import pytest

from resource_librarian import providers


@pytest.mark.parametrize(("error", "expected"), [
    (providers.ProviderError("[WinError 10013] A socket operation was forbidden"),
     "local_environment"),
    (providers.ProviderError("DEEPINFRA_API_KEY is not set"), "credentials"),
    (providers.ProviderError("no model chosen for deepinfra"), "route_configuration"),
    (providers.ProviderError("HTTP 429 from example: busy"), "provider_rate_limited"),
    (providers.ProviderError("HTTP 503 from example: busy"), "provider_transient"),
    (providers.ProviderError("https://example.invalid is not reachable"), "provider_transport"),
    (providers.ProviderError("HTTP 422 from example: invalid request"), "provider_rejected"),
])
def test_message_only_provider_errors_keep_a_conservative_category(error, expected):
    """Custom routes using the legacy message-only error form remain useful."""
    assert providers.provider_failure_category(error) == expected


def test_explicit_provider_error_category_wins_over_ambiguous_message():
    error = providers.ProviderError("HTTP 403: permission denied", category="local_environment")
    assert providers.provider_failure_category(error) == "local_environment"


def test_generic_permission_words_do_not_invent_a_local_windows_fault():
    """Only an actual OS exception or a distinct socket marker proves local policy."""
    assert providers.provider_failure_category(
        providers.ProviderError("provider says permission denied")) == "unknown"
    assert providers.provider_failure_category(PermissionError(13, "permission denied")) == \
        "local_environment"


def test_request_marks_windows_style_socket_policy_as_local_environment(monkeypatch):
    def forbidden(request, timeout):
        raise urllib.error.URLError(PermissionError(13, "socket access forbidden by local policy"))

    monkeypatch.setattr(providers.urllib.request, "urlopen", forbidden)
    with pytest.raises(providers.ProviderError) as raised:
        providers._request("GET", "https://example.invalid/v1", {}, sleep=lambda _: None)
    assert raised.value.category == "local_environment"
    assert providers.provider_failure_category(raised.value) == "local_environment"


def test_request_marks_http_auth_as_credentials(monkeypatch):
    def unauthorized(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "unauthorized", {}, io.BytesIO(b"bad key"))

    monkeypatch.setattr(providers.urllib.request, "urlopen", unauthorized)
    with pytest.raises(providers.ProviderError) as raised:
        providers._request("GET", "https://example.invalid/v1", {}, sleep=lambda _: None)
    assert raised.value.category == "credentials"


def test_connection_check_exposes_a_typed_failure_without_exposing_a_key(monkeypatch):
    def blocked(*args, **kwargs):
        raise providers.ProviderError("[WinError 10013] socket access forbidden",
                                     category="local_environment")

    monkeypatch.setattr(providers, "_request", blocked)
    checked = providers.OpenAICompatible("https://example.invalid/v1", "model", name="custom").check()
    assert checked["ok"] is False
    assert checked["failure_category"] == "local_environment"
    assert "key" not in checked["error"].casefold()

