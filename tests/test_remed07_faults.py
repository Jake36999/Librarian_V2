"""REMED-07 deterministic retry and cancellation qualification.

The production retry/cancellation path is reused unchanged.  An Event-like
virtual clock records the configured backoff and chooses whether that wait
completes or is cancelled, so these cases need no timer, sleep, or network.
"""
from __future__ import annotations

from collections.abc import Iterable

import pytest

from resource_librarian.hosts import Host, HostLimiter, LimitedProvider
from resource_librarian.providers import (
    Provider,
    ProviderCancelledError,
    ProviderError,
    Reply,
)


class VirtualCancel:
    """The Event surface used by the provider path, with virtual waits."""

    def __init__(self, *, set_initially: bool = False,
                 cancel_on_wait: bool = False) -> None:
        self._set = set_initially
        self.cancel_on_wait = cancel_on_wait
        self.waits: list[float] = []

    def is_set(self) -> bool:
        return self._set

    def wait(self, seconds: float) -> bool:
        self.waits.append(seconds)
        if self.cancel_on_wait:
            self._set = True
        return self._set


class FaultProvider(Provider):
    name = model = "fault-model"

    def __init__(self, outcomes: Iterable[Reply | BaseException]) -> None:
        self.outcomes = iter(outcomes)
        self.calls = 0

    def chat(self, system, messages, tools, max_tokens=4096, temperature=None):
        self.calls += 1
        outcome = next(self.outcomes)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def transient() -> ProviderError:
    return ProviderError("HTTP 503: scripted busy", category="provider_transient")


def route() -> Host:
    return Host(
        "remed07-scripted", "REMED-07 scripted route", "openai",
        "https://example.invalid/v1", timeout=2, concurrency_limit=1,
    ).normalise()


def test_bounded_profile_retries_once_then_succeeds_with_virtual_time() -> None:
    provider = FaultProvider([transient(), Reply(text="ok", model="fault-model")])
    limiter = HostLimiter()
    limited = LimitedProvider(provider, route(), limiter, retry_policy="bounded")
    clock = VirtualCancel()

    reply = limited.chat_cancellable("system", [], [], cancel=clock)

    assert reply.text == "ok"
    assert provider.calls == 2
    assert clock.waits == [0.25]
    state = limiter._limit(limited.host)
    assert state.interactive == 0 and state.transient_failures == 0


def test_none_profile_exposes_the_first_typed_transient_without_a_wait() -> None:
    provider = FaultProvider([transient()])
    limiter = HostLimiter()
    limited = LimitedProvider(provider, route(), limiter, retry_policy="none")
    clock = VirtualCancel()

    with pytest.raises(ProviderError) as failed:
        limited.chat_cancellable("system", [], [], cancel=clock)

    assert failed.value.category == "provider_transient"
    assert provider.calls == 1 and clock.waits == []
    state = limiter._limit(limited.host)
    assert state.interactive == 0 and state.transient_failures == 1


def test_cancel_during_bounded_backoff_is_typed_and_leaks_no_slot() -> None:
    provider = FaultProvider([transient()])
    limiter = HostLimiter()
    limited = LimitedProvider(provider, route(), limiter, retry_policy="bounded")
    clock = VirtualCancel(cancel_on_wait=True)

    with pytest.raises(ProviderCancelledError) as cancelled:
        limited.chat_cancellable("system", [], [], cancel=clock)

    assert cancelled.value.category == "cancelled"
    assert provider.calls == 1 and clock.waits == [0.25]
    state = limiter._limit(limited.host)
    assert state.interactive == 0 and state.transient_failures == 1
    assert limiter.run(limited.host, lambda: "slot available") == "slot available"


def test_already_cancelled_route_makes_no_provider_call() -> None:
    provider = FaultProvider([Reply(text="must not run")])
    limiter = HostLimiter()
    limited = LimitedProvider(provider, route(), limiter, retry_policy="bounded")
    clock = VirtualCancel(set_initially=True)

    with pytest.raises(ProviderCancelledError):
        limited.chat_cancellable("system", [], [], cancel=clock)

    assert provider.calls == 0 and clock.waits == []
    assert limiter._limit(limited.host).interactive == 0
