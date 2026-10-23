"""Runtime, rather than prompt-only, enforcement for agent profiles."""
from __future__ import annotations

import pytest

from resource_librarian import effort, tools  # noqa: F401  (register delegated helper tool)
from resource_librarian.agent_runtime import (AgentProfile, ProfileCapacityError, ProfileRunGate,
                                               ProfileStore, ProfiledEndpoint, route_permitted)
from resource_librarian.clerk import ClerkUnavailable, Scripted
from resource_librarian.hosts import Host, HostLimiter, HostRegistry
from resource_librarian.loop import Loop, ProviderEndpoint
from resource_librarian.providers import Provider, ProviderError, Reply, ToolCall
from resource_librarian.registry import Context, REGISTRY


class CaptureProvider(Provider):
    name = "capture"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def chat(self, system, messages, tools, max_tokens=4096, temperature=None):
        self.calls.append({"system": system, "messages": messages, "tools": tools,
                           "max_tokens": max_tokens})
        return Reply(text="bounded reply")


class HiddenToolProvider(Provider):
    """Simulates a permissive endpoint returning a tool absent from its schema."""

    name = "hidden-tool"

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, system, messages, tools, max_tokens=4096, temperature=None):
        self.calls += 1
        if self.calls == 1:
            return Reply(tool_calls=[ToolCall("hidden", "filters", {})])
        return Reply(text="I will use an offered tool instead.")


def test_profile_output_budget_is_sent_to_the_provider(vault):
    provider = CaptureProvider()
    loop = Loop(vault, provider)
    loop.configure_profile(AgentProfile("tight", "lead", output_budget=37))

    turn = loop.send("hello")

    assert turn.reply == "bounded reply"
    assert provider.calls[0]["max_tokens"] == 37


def test_profile_token_and_unpriced_cost_budgets_fail_before_a_provider_call(vault):
    provider = CaptureProvider()
    loop = Loop(vault, provider)
    loop.configure_profile(AgentProfile("tokens", "lead", token_budget=10, output_budget=8))
    turn = loop.send("hello")
    assert turn.stopped == "profile_budget"
    assert "token budget" in turn.error
    assert provider.calls == []

    priced = Loop(vault, provider)
    priced.configure_profile(AgentProfile("cost", "lead", cost_budget_usd=0.01))
    turn = priced.send("hello")
    assert turn.stopped == "profile_budget"
    assert "rate card" in turn.error
    assert provider.calls == []


def test_profiled_background_endpoint_enforces_role_budget_and_queues_on_route_refusal():
    """Clerk/Scribe routes cannot bypass the same profile boundary as chat."""
    seen: list[dict] = []
    endpoint = Scripted(lambda payload: (seen.append(payload), {"bullets": []})[1], concurrency=4)
    profile = AgentProfile("bounded-clerk", "clerk", output_budget=17, token_budget=1_000,
                           concurrency_limit=2)
    guarded: list[tuple[str, str]] = []
    wrapped = ProfiledEndpoint(
        endpoint, profile, gate=ProfileRunGate(),
        route_guard=lambda current, target: guarded.append((current.id, target.name)) or
        {"input_per_1m": 1, "output_per_1m": 1},
    )
    raw, model = wrapped.complete({"task": "inside", "system": "s", "user": "u",
                                   "schema": {}, "temperature": 0, "max_tokens": 500})

    assert model == "scripted" and raw == '{"bullets": []}'
    assert seen[0]["max_tokens"] == 17
    assert guarded == [("bounded-clerk", "scripted")]
    assert wrapped.concurrency == 2

    def blocked(*_args):
        raise ValueError("route lacks fresh Clerk qualification")

    refused = ProfiledEndpoint(endpoint, profile, route_guard=blocked)
    with pytest.raises(ClerkUnavailable, match="lacks fresh Clerk qualification"):
        refused.complete({"task": "inside", "system": "s", "user": "u",
                          "schema": {}, "temperature": 0, "max_tokens": 5})


def test_background_provider_endpoint_inherits_the_host_concurrency_limit():
    provider = CaptureProvider()
    provider.host = type("HostLimit", (), {"concurrency_limit": 3})()
    endpoint = ProviderEndpoint(provider)
    effort.apply_concurrency(endpoint, 25)

    assert endpoint.concurrency == 25  # legacy effort API remains source-compatible
    assert ProfiledEndpoint(endpoint, AgentProfile("role", "clerk", concurrency_limit=7)).concurrency == 3


def test_compact_bundle_is_also_an_execution_boundary(vault):
    """A server cannot smuggle a tool call that was not in this turn's schema."""
    provider = HiddenToolProvider()
    store = ProfileStore(vault)
    loop = Loop(vault, provider, extras={"use_tool_bundles": True,
                                         "agent_profile": "research_helper",
                                         "profile_store": store})

    turn = loop.send("Please help")

    assert turn.reply == "I will use an offered tool instead."
    assert turn.calls[0]["refused"] == "TOOL_BUNDLE_REFUSED"
    assert "macro_expansion_depth" not in loop.ctx.extras


def test_delegated_helper_uses_its_versioned_read_only_profile(vault):
    provider = CaptureProvider()
    store = ProfileStore(vault)
    store.save(AgentProfile("research_helper", "research_helper", output_budget=29,
                            concurrency_limit=1, allowed_bundles=["read"],
                            permission_ceiling="consult"))
    guarded: list[tuple[str, int]] = []

    def guard(profile, tier):
        guarded.append((profile.id, tier))
        return {"input_per_1m": 1.0, "output_per_1m": 1.0}

    ctx = Context(tier="contribute", vault=vault, extras={
        "effort": effort.profile(1), "agent_provider": lambda _: provider,
        "profile_store": store, "profile_gate": ProfileRunGate(),
        "helper_profile_guard": guard,
    })
    out = REGISTRY.call("delegate", {"questions": ["find a source"], "tier": 1}, ctx)

    assert out["agents"] == 1 and out["results"][0]["answer"] == "bounded reply"
    assert provider.calls[0]["max_tokens"] == 29
    assert guarded == [("research_helper", 1)]


def test_profile_gate_and_route_allow_lists_are_runtime_constraints():
    profile = AgentProfile("restricted", "lead", concurrency_limit=1,
                           route_policy={"host_ids": ["personal-openai"],
                                         "model_ids": ["gpt-test"]})
    gate = ProfileRunGate()
    release = gate.acquire(profile)
    with pytest.raises(ProfileCapacityError):
        gate.acquire(profile)
    release()
    assert gate.status() == {}

    assert route_permitted(profile, {"host_id": "personal-openai", "model": "gpt-test"}) == (True, "")
    allowed, detail = route_permitted(profile, {"host_id": "elsewhere", "model": "gpt-test"})
    assert not allowed and "does not allow host" in detail


def test_host_circuit_breaker_stops_repeated_transient_failures_without_failover():
    host = Host("test-host", "Test host", "openai", "https://example.invalid/v1").normalise()
    limiter = HostLimiter()

    def unavailable():
        raise ProviderError("HTTP 503: provider busy")

    for _ in range(3):
        with pytest.raises(ProviderError, match="503"):
            limiter.run(host, unavailable)
    with pytest.raises(ProviderError, match="circuit is open"):
        limiter.run(host, unavailable)


def test_host_registry_keeps_a_bounded_non_secret_health_history(tmp_path):
    registry = HostRegistry(tmp_path / "hosts.json")
    registry.upsert({"id": "lab", "display_name": "Lab", "protocol": "openai",
                     "base_url": "http://127.0.0.1:1234/v1"})
    registry.mark_health("lab", ok=False, detail="offline", model="m1")
    registry.mark_health("lab", ok=True, detail="connected", model="m1")

    row = registry.get("lab").public()
    assert row["health"]["status"] == "ready"
    assert [entry["status"] for entry in row["health_history"]] == ["error", "ready"]
    assert "key" not in str(row["health_history"]).casefold()


def test_profile_store_versions_each_vault_scoped_edit(vault):
    store = ProfileStore(vault)
    first = store.save(AgentProfile("field-research", "lead", output_budget=100))
    second = store.save(AgentProfile("field-research", "lead", output_budget=200))

    assert second["revision"] == first["revision"] + 1
    history = store.history("field-research")
    assert [row["profile"]["output_budget"] for row in history] == [200, 100]
