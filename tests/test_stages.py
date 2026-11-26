"""The batch's stages are declared as data (implementation plan M1b; to-be stage contracts).

Before this, the stages were code and shared one flat tool grant, so a tool granted to the batch could
run at any of its stages. Now standard/stages.yaml declares each stage's tools, dependencies, recipe,
model use, risk and role; the batch reads them, and a call outside a stage's tools is reported, and
refused once `enforce: refuse` is set.
"""
from __future__ import annotations

import pytest

from resource_librarian import batch, stages, tools  # noqa: F401
from resource_librarian.registry import REGISTRY, Context

from test_staging import staged  # noqa: F401  (fixture)


def test_the_declared_stages_are_the_stages_that_run():
    contract = stages.load()
    assert [s.name for s in contract.pipelines["source"]] == [name for name, _ in batch.STAGES]
    assert [s.name for s in contract.pipelines["folder"]] == [name for name, _ in batch.FOLDER_STAGES]
    stages.validate_tools(contract, set(REGISTRY.names()))


def test_the_batch_grant_is_the_union_of_the_stages_tools_and_nothing_wider():
    assert batch.STAGE_TOOLS == {"pdf_to_markdown", "ocr_pdf", "deep_read", "staging_review"}
    contract = stages.load()
    assert contract.stage("read").tools == {"deep_read"}
    assert contract.stage("review").tools == {"staging_review"}
    assert contract.stage("validate").tools == frozenset()


def test_recipes_and_model_stages_come_from_the_declaration():
    # MF-020's reuse key reads these: the same values the code held before.
    assert batch.STAGE_RECIPES == {name: "1" for name in (
        "validate", "parse", "lenses", "data", "relate", "metadata", "review", "publish",
        "folder_validate", "folder_describe", "folder_data")}
    assert batch.MODEL_STAGES == {"parse", "read", "relate", "review", "folder_describe"}
    assert stages.load().dependencies()["publish"] == {"parse", "read", "review"}


@pytest.mark.parametrize("row, expected", [
    ({"stage": "a", "after": ["b"], "recipe": "1", "risk": "routine", "role": "core"}, "no earlier stage"),
    ({"stage": "a", "recipe": "1", "risk": "extreme", "role": "core"}, "risk is one of"),
    ({"stage": "a", "recipe": "1", "risk": "routine", "role": "core", "gate": ["vibes"]}, "unknown gate"),
    ({"stage": "a", "risk": "routine", "role": "core"}, "a recipe"),
])
def test_a_malformed_declaration_is_refused(row, expected):
    with pytest.raises(stages.StageDefinitionError, match=expected):
        stages.parse({"version": 1, "pipelines": {"source": [row]}})


def test_an_unregistered_stage_tool_is_refused():
    contract = stages.parse({"version": 1, "pipelines": {"source": [
        {"stage": "a", "tools": ["no_such_tool"], "recipe": "1", "risk": "routine", "role": "core"}]}})
    with pytest.raises(stages.StageDefinitionError, match="no_such_tool"):
        stages.validate_tools(contract, set(REGISTRY.names()))


def test_a_call_outside_its_stage_is_reported_and_its_own_inner_calls_are_not(vault):
    reported = []
    ctx = Context(tier="curate", vault=vault, extras={"caller_kind": "person"})
    ctx.extras["stage_guard"] = stages.guard(stages.load(), "validate",
                                             lambda stage, tool: reported.append((stage, tool)))
    out = REGISTRY.call("rules", {}, ctx)             # not one of validate's tools
    assert "error" not in out
    assert reported == [("validate", "rules")]
    assert ctx.extras["stage_guard"] is not None       # restored after the call


def test_refuse_mode_refuses_a_call_outside_its_stage():
    contract = stages.parse({"version": 1, "enforce": "refuse", "pipelines": {"source": [
        {"stage": "read", "tools": ["deep_read"], "recipe": "1", "risk": "bounded", "role": "clerk"}]}})
    check = stages.guard(contract, "read", lambda stage, tool: None)
    assert check("deep_read") is None
    refusal = check("write_note")
    assert refusal is not None and refusal.code == "STAGE_TOOL_REFUSED"


def _agent_mode(vault):
    from resource_librarian.vault import render_config
    config = vault.config()
    config["promotion"]["mode"] = "agent"
    vault.config_path.write_text(render_config(config))


def test_an_agent_accepting_a_captured_source_is_recorded_not_refused_by_default(staged):
    # Report first (as-is W-STI-01): nothing an agent could do before is taken away; the decision
    # records that the batch had not read the source, and the note's coverage says `captured`.
    from resource_librarian import staging
    from test_staging import ctx
    agent = ctx(staged, tier="contribute")
    REGISTRY.call("staging_review", {"item_id": "s-a"}, agent)
    _agent_mode(staged)
    out = REGISTRY.call("staging_decide", {"item_ids": ["s-a"], "decision": "accept"}, agent)["results"][0]
    assert out["status"] == "accepted", out
    history = staging.StagingStore(staged).load("s-a")["history"]
    assert "before the batch read it" in history[-1]["entry_receipt"]


def test_with_enforce_refuse_only_a_person_accepts_a_captured_source(staged, monkeypatch):
    from dataclasses import replace
    from test_staging import ctx
    agent = ctx(staged, tier="contribute")
    REGISTRY.call("staging_review", {"item_id": "s-a"}, agent)
    _agent_mode(staged)
    refusing = replace(stages.load.__wrapped__(), acceptance_enforce="refuse")
    monkeypatch.setattr(stages, "load", lambda: refusing)
    out = REGISTRY.call("staging_decide", {"item_ids": ["s-a"], "decision": "accept"}, agent)["results"][0]
    assert out["refused"] == "SOURCE_NOT_ENRICHED"
    accepted = REGISTRY.call("staging_decide", {"item_ids": ["s-a"], "decision": "accept"},
                             ctx(staged))["results"][0]                  # a person, as captured
    assert accepted["status"] == "accepted", accepted
