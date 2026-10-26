"""Canonical service selection and the active Core's shared host gate.

No transport or credentials are stored here. Legacy configuration is read only
for a vault which has not acquired a role store; a present store is authoritative.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from .hosts import HostLimiter, HostRegistry
from .providers import PRESETS
from .role_routes import RoleRouteStore
from .vault import Vault

T = TypeVar("T")
LOCAL_ENCODERS = ("model2vec", "fastembed", "hash")
SERVICES = ("ocr", "tts", "stt", "embeddings")


class ServiceRouteError(ValueError):
    pass


@dataclass(frozen=True)
class ServiceRoute:
    service: str
    provider: str
    model: str
    host_id: str = ""
    protocol: str = ""
    endpoint_fingerprint: str = ""
    base_url: str = ""
    key_env: str = ""
    canonical: bool = False

    @property
    def local(self) -> bool:
        return self.service == "embeddings" and self.protocol == "local" and self.provider in LOCAL_ENCODERS

    def choice(self) -> dict[str, str]:
        return {"provider": self.provider, "model": self.model}

    @property
    def contract_provider(self) -> str:
        # A custom host named 'deepinfra' is not provider evidence.
        return "custom_openai" if self.host_id in PRESETS else self.provider

    def native_base(self) -> str:
        if self.host_id != "preset-deepinfra" or self.provider != "deepinfra" or \
                self.base_url.rstrip("/") != PRESETS["deepinfra"]["base_url"]:
            raise ServiceRouteError("native speech services require the reviewed DeepInfra endpoint")
        return "https://api.deepinfra.com/v1/inference"


_lock = threading.RLock()
_active: dict[str, "ServiceRuntime"] = {}


def _vault_key(vault: Vault) -> str:
    return str(vault.root.resolve()).casefold()


class ServiceRuntime:
    def __init__(self, vault: Vault, hosts: HostRegistry, limiter: HostLimiter):
        self.vault, self.hosts, self.limiter = vault, hosts, limiter
        self.closed = False
        self._lock = threading.Lock()
        self._calls = 0

    def attach(self) -> None:
        with _lock:
            _active[_vault_key(self.vault)] = self

    def close(self) -> None:
        # Keep a terminal runtime until a successor attaches: a delayed service
        # callback must not become a standalone, unmetered request after stop.
        with self._lock:
            self.closed = True

    @property
    def active_calls(self) -> int:
        with self._lock:
            return self._calls

    def _check(self, route: ServiceRoute) -> None:
        with self._lock:
            if self.closed:
                raise ServiceRouteError("the Core has stopped; restart it before using a service")
        if resolve(self.vault, route.service, validate=True) != route:
            raise ServiceRouteError(f"{route.service} assignment changed; restart the operation")

    def run(self, route: ServiceRoute, call: Callable[[], T]) -> T:
        with self._lock:
            if self.closed:
                raise ServiceRouteError("the Core has stopped; restart it before using a service")
            self._calls += 1
        try:
            def send() -> T:
                # Check again after waiting for the shared host gate. Closing
                # admission or changing the selection must not start queued IO.
                self._check(route)
                result = call()
                # A late result must not trigger cache/vector/audio commits
                # after a stop or after the route was reassigned.
                self._check(route)
                return result
            if route.local:
                return send()
            self._check(route)
            # Embedding sync is background work: on a host on this machine it
            # yields to an interactive turn (ADAPT-06).
            return self.limiter.run(self.hosts.get(route.host_id), send,
                                    background=route.service == "embeddings")
        finally:
            with self._lock:
                self._calls -= 1


def runtime(vault: Vault) -> ServiceRuntime | None:
    with _lock:
        return _active.get(_vault_key(vault))


def resolve(vault: Vault, service: str, *, validate: bool = False) -> ServiceRoute | None:
    if service not in SERVICES:
        raise ServiceRouteError(f"unknown service slot {service!r}")
    active = runtime(vault)
    hosts = active.hosts if active is not None else HostRegistry()
    store = RoleRouteStore(vault)
    canonical = store.exists()
    if canonical:
        binding = store.resolve(service)
        if binding is None or binding.source == "unconfigured":
            return None
        model, host_id = binding.model_id, binding.host_id
        if binding.protocol == "local":
            kind = host_id.removeprefix("local-")
            if service != "embeddings" or kind not in LOCAL_ENCODERS:
                raise ServiceRouteError("unsupported local service binding")
            return ServiceRoute(service, kind, model, host_id, "local", canonical=True)
    else:
        raw = str(vault.setting("services", service) or "")
        if service == "embeddings" and not raw:
            raw = str(vault.setting("search", "vectors") or "")
        if service == "embeddings" and raw.startswith("api:"):
            raw = raw[4:]
        provider, _, model = raw.partition(":")
        if not provider or not model:
            return None
        if service == "embeddings" and provider in LOCAL_ENCODERS:
            return ServiceRoute(service, provider, model, protocol="local")
        host_id = "preset-" + provider if provider in PRESETS else provider
    try:
        host = hosts.get(host_id)
    except KeyError as exc:
        if canonical and not validate:
            return ServiceRoute(service, host_id, model, host_id, binding.protocol,
                                binding.endpoint_fingerprint, canonical=True)
        raise ServiceRouteError(f"{service} host {host_id!r} is unavailable; select its route again") from exc
    if validate:
        if not host.enabled:
            raise ServiceRouteError(f"{service} host is disabled")
        if canonical and (host.protocol != binding.protocol or
                          host.endpoint_fingerprint != binding.endpoint_fingerprint):
            raise ServiceRouteError(f"{service} endpoint changed; review and select its route again")
        if service in ("ocr", "embeddings") and host.protocol != "openai":
            raise ServiceRouteError(f"{service} requires an OpenAI-compatible host")
    # Provider evidence applies to the reviewed endpoint, never merely a
    # custom host whose id happens to have a familiar provider name.
    provider = host.id
    for family, preset in PRESETS.items():
        if host.id == "preset-" + family and host.base_url.rstrip("/") == preset["base_url"].rstrip("/") \
                and host.protocol == preset["protocol"]:
            provider = family
            break
    route = ServiceRoute(service, provider, model, host.id, host.protocol,
                         host.endpoint_fingerprint, host.base_url, host.auth_ref, canonical)
    if validate and service in ("tts", "stt"):
        route.native_base()
    return route


def run(vault: Vault, route: ServiceRoute, call: Callable[[], T]) -> T:
    active = runtime(vault)
    if active is not None:
        return active.run(route, call)
    from .coordination import VaultCoordinator
    if VaultCoordinator.held_elsewhere(vault):
        raise ServiceRouteError("CORE_REQUIRED: make service calls through the active Core")
    if resolve(vault, route.service, validate=True) != route:
        raise ServiceRouteError(f"{route.service} assignment changed; restart the operation")
    return call()
