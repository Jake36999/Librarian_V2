from typing import Literal

import pytest

from resource_librarian.registry import MAX_LIMIT, MAX_TEXT, Card, Context, Registry, ToolSpec


@pytest.fixture
def reg() -> Registry:
    r = Registry()

    @r.tool("echo", tier="consult", effect="read", needs_vault=False, card=Card("Echo"))
    def echo(ctx, text: str, limit: int = 5, flag: bool = False,
             items: list[str] | None = None, mode: Literal["a", "b"] = "a") -> dict:
        """Say it back."""
        return {"text": text, "limit": limit, "flag": flag, "items": items, "mode": mode}

    @r.tool("write", tier="curate", effect="vault_write", scope="library", needs_vault=False,
            card=Card("Write"))
    def write(ctx) -> dict:
        return {"ok": True}

    @r.tool("needs", tier="consult", effect="read", card=Card("Needs a vault"))
    def needs(ctx) -> dict:
        return {"ok": True}

    @r.tool("boom", tier="consult", effect="read", needs_vault=False, card=Card("Raises"))
    def boom(ctx) -> dict:
        raise RuntimeError("kaput")

    return r


def test_unregistered_tool_is_refused(reg):
    out = reg.call("rm_rf", {}, Context(tier="curate"))
    assert out["refused"] == "CLOSED_ACTION_REGISTRY"


def test_tier_is_enforced_by_name(reg):
    out = reg.call("write", {}, Context(tier="consult"))
    assert out["refused"] == "TIER_REFUSED" and "curate" in out["detail"]
    assert reg.call("write", {}, Context(tier="curate")) == {"ok": True}


def test_vault_required(reg):
    assert reg.call("needs", {}, Context())["refused"] == "VAULT_REQUIRED"


def test_exceptions_become_structured_errors(reg):
    out = reg.call("boom", {}, Context())
    assert out["error"] == "failed" and "kaput" in out["detail"]


def test_unknown_arguments_are_refused_not_dropped(reg):
    out = reg.call("echo", {"text": "hi", "limt": 3}, Context())
    assert out["error"] == "invalid_arguments" and "limt" in out["detail"]


def test_missing_required_argument(reg):
    assert reg.call("echo", {}, Context())["error"] == "invalid_arguments"


def test_coercion_is_reported(reg):
    out = reg.call("echo", {"text": 42, "limit": "999", "flag": "yes", "items": "one"},
                   Context())
    assert out["text"] == "42" and out["limit"] == MAX_LIMIT and out["flag"] is True
    assert out["items"] == ["one"]
    joined = " ".join(out["adjusted_arguments"])
    assert "clamped" in joined and "flag" in joined and "one-item list" in joined


def test_text_is_bounded_and_control_characters_removed(reg):
    out = reg.call("echo", {"text": "a\x00b" + "x" * (MAX_TEXT + 10)}, Context())
    assert len(out["text"]) <= MAX_TEXT and "\x00" not in out["text"]


def test_enum_is_enforced(reg):
    assert reg.call("echo", {"text": "t", "mode": "c"}, Context())["error"] == "invalid_arguments"


def test_schema_is_generated_from_the_signature(reg):
    schema = reg.get("echo").json_schema()
    assert schema["required"] == ["text"]
    assert schema["properties"]["limit"] == {"type": "integer", "default": 5}
    assert schema["properties"]["items"]["type"] == "array"
    assert schema["properties"]["mode"]["enum"] == ["a", "b"]
    assert schema["additionalProperties"] is False


def test_for_tier_is_cumulative(reg):
    assert {t.name for t in reg.for_tier("consult")} == {"echo", "needs", "boom"}
    assert "write" in {t.name for t in reg.for_tier("curate")}


def test_declaration_errors():
    r = Registry()
    with pytest.raises(ValueError):
        r.tool("x", tier="admin", effect="read", card=Card("x"))
    with pytest.raises(TypeError):
        @r.tool("y", tier="consult", effect="read", card=Card("y"))
        def y(text: str):
            return {}

    @r.tool("z", tier="consult", effect="read", card=Card("z"))
    def z(ctx):
        return {}
    with pytest.raises(ValueError):
        r.tool("z", tier="consult", effect="read", card=Card("z"))(z)


def test_annotations_follow_effect(reg):
    assert reg.get("echo").annotations()["readOnlyHint"] is True
    assert reg.get("write").annotations()["readOnlyHint"] is False


# -- dynamic registration (MCP servers) -----------------------------------------

def _bridge(ctx, **kwargs):
    return kwargs


def external_spec(name="mcp__demo__search", schema=None):
    return ToolSpec(
        name=name, fn=_bridge, tier="contribute", effect="read", card=Card("An MCP tool"),
        needs_vault=False, external=True,
        schema=schema or {"type": "object", "properties": {
            "query": {"type": "string"}, "limit": {"type": "integer", "default": 5},
            "mode": {"type": "string", "enum": ["a", "b"]}},
            "required": ["query"], "additionalProperties": False})


def test_register_adds_an_external_tool_and_it_is_callable(reg):
    reg.register(external_spec())
    out = reg.call("mcp__demo__search", {"query": "x"}, Context(tier="contribute"))
    assert out == {"query": "x"}


def test_register_refuses_a_non_external_spec(reg):
    with pytest.raises(ValueError):
        reg.register(ToolSpec(name="not_external", fn=_bridge, tier="consult", effect="read",
                              card=Card("x"), needs_vault=False))


def test_register_refuses_to_shadow_a_vault_tool_name(reg):
    with pytest.raises(ValueError):
        reg.register(external_spec(name="echo"))


def test_register_replaces_an_existing_external_tool_on_reconnect(reg):
    reg.register(external_spec())
    reg.register(external_spec(schema={"type": "object", "properties": {
        "query": {"type": "string"}}, "required": ["query"], "additionalProperties": False}))
    assert "limit" not in reg.get("mcp__demo__search").json_schema()["properties"]


def test_unregister_removes_only_external_tools(reg):
    reg.register(external_spec())
    reg.unregister("mcp__demo__search")
    assert "mcp__demo__search" not in reg
    reg.unregister("echo")                          # a vault tool: silently left alone
    assert "echo" in reg


def test_external_names_lists_only_external_tools(reg):
    reg.register(external_spec())
    assert reg.external_names() == ["mcp__demo__search"]


def test_coerce_uses_the_external_schema_not_fn_hints(reg):
    reg.register(external_spec())
    out = reg.call("mcp__demo__search", {"query": "x", "limit": "3"}, Context(tier="contribute"))
    assert out == {"query": "x", "limit": 3}
    missing = reg.call("mcp__demo__search", {}, Context(tier="contribute"))
    assert missing["error"] == "invalid_arguments"
    unknown = reg.call("mcp__demo__search", {"query": "x", "nope": 1}, Context(tier="contribute"))
    assert unknown["error"] == "invalid_arguments" and "nope" in unknown["detail"]
    bad_enum = reg.call("mcp__demo__search", {"query": "x", "mode": "c"}, Context(tier="contribute"))
    assert bad_enum["error"] == "invalid_arguments"
