"""RED regressions from the failed six-task live pilot of 2026-11-14.

Fixtures are the two real lead-authored ``dispatch_plan`` arguments
(``tests/fixtures/pilot_20261114``), unchanged.  Finding 1: the advertised
schema was only ``plan: {type: object}``.  Finding 2: all four Qwen3.5 Clerk
contracts spent exactly the 1,800-token visible budget and returned nothing.
"""
import json
from pathlib import Path

import pytest

from resource_librarian import effort
from resource_librarian.registry import REGISTRY, Context

FIXTURES = Path(__file__).parent / "fixtures" / "pilot_20261114"
TASK_KEYS = {"task_id", "tier", "graph_id", "anchors", "instruction", "depends_on"}


def _fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# --- Finding 1: the agent-facing plan contract ------------------------------------------

def test_advertised_schema_names_every_nested_field_and_integer_tiers():
    import resource_librarian.tools.plan_dispatch  # noqa: F401  registers the tool
    plan = REGISTRY.get("dispatch_plan").json_schema()["properties"]["plan"]
    assert plan["type"] == "object" and plan["additionalProperties"] is False
    assert set(plan["required"]) == {"plan_id", "server", "tasks"}
    task = plan["properties"]["tasks"]["items"]
    assert set(task["required"]) == TASK_KEYS and task["additionalProperties"] is False
    assert task["properties"]["tier"] == {"type": "integer", "enum": [1, 2, 3],
                                         "description": task["properties"]["tier"]["description"]}
    assert task["properties"]["anchors"]["maxItems"] == 8
    assert plan["properties"]["tasks"]["maxItems"] == 32
    # One valid example travels with the schema the model is shown.
    example = plan["examples"][0]
    assert set(example) == {"plan_id", "server", "tasks"}
    assert all(set(t) == TASK_KEYS and isinstance(t["tier"], int) for t in example["tasks"])


class _Mcp:
    def status(self):
        return {"geo_phase67_pilot_20261114": dict(enabled=True, accepted=True, connected=True)}

    def tool_names(self, server):
        return [f"mcp__{server}__compile_task_packet", f"mcp__{server}__list_graphs"]


def _ctx():
    return Context(tier="contribute", extras={"mcp": _Mcp(), "effort": effort.profile(2)})


def test_first_real_plan_gets_field_level_errors_not_a_bare_code():
    import resource_librarian.tools.plan_dispatch as pd
    with pytest.raises(ValueError) as caught:
        pd._validate(_ctx(), _fixture("lead_plan_first.json"))
    message = str(caught.value)
    assert message.startswith("PLAN_SHAPE: ")
    # The lead sent server but no plan_id, and id/level/description/dependencies per task.
    for expected in ("missing plan_id", "tasks[0,1,2,3,4,5]: missing task_id",
                     "tasks[0,1,2,3,4,5]: missing tier", "tasks[0,1,2,3,4,5]: unexpected level"):
        assert expected in message
    assert "missing server" not in message and "more" not in message
    assert len(message) <= 600


def test_schema_repair_plan_with_decimal_string_tiers_is_normalised_exactly():
    import resource_librarian.tools.plan_dispatch as pd
    plan = _fixture("lead_plan_schema_repair.json")
    assert [t["tier"] for t in plan["tasks"]] == ["3", "3", "3", "3", "2", "1"]
    tasks, waves = pd._validate(_ctx(), plan)
    assert [tasks[t]["tier"] for t in ("contract-1", "synthesis-1", "review-1")] == [3, 2, 1]
    assert waves == [["contract-1", "contract-2", "contract-3", "contract-4"],
                     ["synthesis-1"], ["review-1"]]
    assert plan["tasks"][0]["tier"] == "3"           # the caller's argument is not mutated


@pytest.mark.parametrize("tier", [True, " 3", "3.0", 3.0, "03", "4", 0, None])
def test_only_exact_tier_spellings_are_accepted(tier):
    import resource_librarian.tools.plan_dispatch as pd
    plan = dict(plan_id="p", server="geo_phase67_pilot_20261114", tasks=[dict(
        task_id="t1", tier=tier, graph_id="g", anchors=["entity:a"], instruction="Describe.",
        depends_on=[])])
    with pytest.raises(ValueError, match=r"^PLAN_SHAPE: tasks\[0\]: tier "):
        pd._validate(_ctx(), plan)


def test_dispatch_reports_which_fields_were_normalised(monkeypatch):
    import resource_librarian.tools.plan_dispatch as pd
    calls = []

    def call(ctx, server, tool, arguments):
        if tool == "list_graphs":
            return {"graphs": [dict(graph_id="g", snapshot_id="s1")]}
        calls.append(arguments)
        return dict(packet_version="task-packet-v1", graph_id="g", snapshot_id="s1",
                    instruction="Describe.", anchors=[dict(ref="entity:a", cite_as="g/entity:a",
                                                          text="def a(): pass")],
                    boundary=[], upstream=arguments["upstream"], handles=["g/entity:a"])
    monkeypatch.setattr(pd, "_call_external", call)
    monkeypatch.setattr(pd, "_run_task", lambda ctx, tier, packet: (dict(
        inputs=[], outputs=[], calls=[], claims=[], not_determinable=[]), {"model": "fake"}))
    plan = dict(plan_id="p", server="geo_phase67_pilot_20261114", tasks=[dict(
        task_id="t1", tier="3", graph_id="g", anchors=["entity:a"], instruction="Describe.",
        depends_on=[])])
    out = pd.dispatch_plan(_ctx(), plan)
    assert out["normalised"] == ["tasks[0].tier"]
    assert out["results"]["t1"]["state"] == "ok"


# --- Finding 2: Qwen3.5 Clerk output budget ---------------------------------------------

QWEN = "Qwen/Qwen3.5-397B-A17B"


def test_bundled_pack_reviews_a_reasoning_reserve_for_the_qwen35_clerk_route():
    from resource_librarian.model_invocation import (ExactRoute, ExpectationRegistry,
                                                     LEGACY_OPENAI_CHAT, effective_dialect)
    record = ExpectationRegistry.bundled().match(
        ExactRoute("preset-deepinfra", "openai", "endpoint", QWEN), LEGACY_OPENAI_CHAT)
    assert record is not None and record.status == "reviewed" and record.model_id == QWEN
    assert effective_dialect(record)["output_headroom"] == "reasoning_reserve"
    assert record.capability("native_reasoning") == "true"


def test_code_block_contract_reaches_the_wire_with_reasoning_headroom(monkeypatch):
    from resource_librarian import clerk, providers
    from resource_librarian.hosts import Host, HostLimiter, LimitedProvider
    from resource_librarian.loop import ProviderEndpoint
    from resource_librarian.model_invocation import REASONING_RESERVE_TOKENS, InvocationRuntime
    from resource_librarian.providers import OpenAICompatible

    bodies = []

    def fake(method, url, headers, body=None, timeout=120, **_):
        bodies.append(body)
        answer = dict(inputs=[], outputs=[], calls=[], claims=[], not_determinable=[])
        return {"model": QWEN, "choices": [{"finish_reason": "stop",
                                            "message": {"content": json.dumps(answer)}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10}}
    monkeypatch.setattr(providers, "_request", fake)
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test-not-a-key")
    host = Host("preset-deepinfra", "DeepInfra", "openai",
                "https://api.deepinfra.com/v1/openai", "DEEPINFRA_API_KEY").normalise()
    provider = LimitedProvider(OpenAICompatible(host.base_url, model=QWEN), host, HostLimiter())
    endpoint = ProviderEndpoint(provider, invocation_runtime=InvocationRuntime(), role="clerk")
    packet = dict(packet_version="task-packet-v1", instruction="Describe.",
                  anchors=[dict(ref="entity:a", cite_as="g/entity:a", text="def a(): pass")],
                  boundary=[], upstream=[], handles=["g/entity:a"])
    task = clerk.code_block_contract(packet)

    result = clerk.run([task], endpoint)[0]

    assert result.ok, result.problems
    assert task.kind.max_tokens == 1800                 # the visible budget is unchanged
    assert bodies[0]["max_tokens"] == 1800 + REASONING_RESERVE_TOKENS


class _HeadroomTarget:
    """A Clerk route whose reviewed dialect adds reasoning headroom on the wire."""
    name = "qwen-route"

    def __init__(self, headroom):
        self.headroom, self.seen = headroom, []

    def output_headroom_tokens(self):
        return self.headroom

    def complete(self, payload, repair=""):
        self.seen.append(payload)
        return "{}", "qwen"


def test_profile_budget_reserves_the_reasoning_headroom_actually_sent():
    """The visible cap stays 1,800, but token and cost budgets must count all 2,824."""
    from resource_librarian.agent_runtime import AgentProfile, ProfiledEndpoint
    from resource_librarian.clerk import ClerkUnavailable
    from resource_librarian.model_invocation import REASONING_RESERVE_TOKENS

    payload = {"task": "code_block_contract", "system": "s", "user": "u", "schema": {},
               "temperature": 0.2, "max_tokens": 1800}
    rate = {"input_per_1m": 0.0, "output_per_1m": 1_000_000.0}        # $1 per output token
    # Enough for 1,800 visible tokens, not for the 1,024 the adapter will add.
    profile = AgentProfile("leaf", "clerk", output_budget=1800, cost_budget_usd=2000.0)
    target = _HeadroomTarget(REASONING_RESERVE_TOKENS)
    wrapped = ProfiledEndpoint(target, profile, route_guard=lambda current, t: rate)
    with pytest.raises(ClerkUnavailable, match="cost budget"):
        wrapped.complete(dict(payload))
    assert target.seen == []

    roomy = ProfiledEndpoint(target, AgentProfile("leaf", "clerk", output_budget=1800,
                                                  cost_budget_usd=3000.0),
                             route_guard=lambda current, t: rate)
    roomy.complete(dict(payload))
    assert target.seen[0]["max_tokens"] == 1800        # visible budget unchanged
    assert roomy._reserved_cost == pytest.approx(1800 + REASONING_RESERVE_TOKENS, rel=0.01)

    # A route without a reviewed reserve reserves exactly as before.
    plain = ProfiledEndpoint(_HeadroomTarget(0), AgentProfile("leaf", "clerk", output_budget=1800,
                                                              cost_budget_usd=2000.0),
                             route_guard=lambda current, t: rate)
    plain.complete(dict(payload))


def test_provider_endpoint_reports_its_reviewed_headroom(monkeypatch):
    from resource_librarian.hosts import Host, HostLimiter, LimitedProvider
    from resource_librarian.loop import ProviderEndpoint
    from resource_librarian.model_invocation import REASONING_RESERVE_TOKENS, InvocationRuntime
    from resource_librarian.providers import OpenAICompatible

    host = Host("preset-deepinfra", "DeepInfra", "openai",
                "https://api.deepinfra.com/v1/openai", "DEEPINFRA_API_KEY").normalise()

    def endpoint(model):
        provider = LimitedProvider(OpenAICompatible(host.base_url, model=model), host, HostLimiter())
        return ProviderEndpoint(provider, invocation_runtime=InvocationRuntime(), role="clerk")
    assert endpoint(QWEN).output_headroom_tokens() == REASONING_RESERVE_TOKENS
    assert endpoint("google/gemma-4-26B-A4B-it").output_headroom_tokens() == 0


def test_bundled_pack_reserves_reasoning_headroom_for_the_gpt_oss_120b_bulk_clerk():
    """Owner card (10-Models/gpt-oss-120b): reasoning-tagged; needs max_tokens headroom or returns empty."""
    from resource_librarian.model_invocation import (ExactRoute, ExpectationRegistry,
                                                     LEGACY_OPENAI_CHAT, effective_dialect)
    record = ExpectationRegistry.bundled().match(
        ExactRoute("preset-deepinfra", "openai", "endpoint", "openai/gpt-oss-120b"), LEGACY_OPENAI_CHAT)
    assert record is not None and record.status == "reviewed"
    assert effective_dialect(record)["output_headroom"] == "reasoning_reserve"
    assert record.capability("native_reasoning") == "true"
