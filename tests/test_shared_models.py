"""The owner's 2026-10-03 round: model profiles and model choices belong to the person, not
to one library; the lead chooses its own effort up to the person's setting; a library is
not made inside the folder it should have been."""
import pytest

from resource_librarian import library_picker, providers
from resource_librarian.app import App
from resource_librarian.init import init
from resource_librarian.keys import KeyStore
from resource_librarian.loop import Loop
from resource_librarian.providers import Reply, ToolCall
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.vault import Vault

from conftest import write_note


def app_for(root, listed):
    init(root, name=root.name)
    provider = providers.Scripted(lambda s, m, t: Reply(text="ok"))
    provider.models = lambda: listed
    return App(Vault(root), token="t", keys=KeyStore(use_keyring=False),
               provider_for=lambda choice: provider)


def test_a_new_library_sees_the_shipped_and_the_remembered_profiles(tmp_path):
    first = app_for(tmp_path / "Uni", ["anthropic/claude-fable-5", "acme/house-model"])
    write_note(first.vault.root, "Sources/model/house-model - deepinfra.md",
               'type: source\nkind: model\nprovider: deepinfra\nmodel_id: acme/house-model\n'
               'suggested_tier: Tier_2\ntool_calling: true\ncontext_length: 64000',
               "## Bottom Line\nA house model.\n")
    from resource_librarian.index import open_index
    open_index(first.vault)
    first.models("deepinfra")                         # this library's profile is remembered
    fresh = app_for(tmp_path / "Timeline", ["anthropic/claude-fable-5", "acme/house-model"])
    by_id = {m["id"]: m for m in fresh.models("deepinfra")["models"]}
    shipped = by_id["anthropic/claude-fable-5"]["profile"]
    assert shipped["shared"] and shipped["suggested_tier"] == "Tier_1"
    remembered = by_id["acme/house-model"]["profile"]
    assert remembered["shared"] and remembered["suggested_tier"] == "Tier_2"


def test_model_choices_follow_the_person_into_a_library_that_has_none(tmp_path):
    first = app_for(tmp_path / "Uni", [])
    first.settings.update(tiers=[{"provider": "deepinfra", "model": "deepseek-ai/DeepSeek-V4-Pro"}],
                          effort=6)
    fresh = app_for(tmp_path / "Main", [])
    assert fresh.settings.data["tiers"][0]["model"] == "deepseek-ai/DeepSeek-V4-Pro"
    assert fresh.settings.data["effort"] == 6 and "tiers" in fresh.settings.inherited
    fresh.settings.update(working_context="mine")    # a library's own choice stays its own
    third = app_for(tmp_path / "Third", [])
    assert third.settings.data["working_context"] != "mine"


def test_the_lead_chooses_less_effort_than_the_setting_and_never_more(tmp_path):
    from resource_librarian import effort
    init(tmp_path / "v", name="v")
    ceiling = effort.profile(6)
    ctx = Context(tier="contribute", vault=Vault(tmp_path / "v"),
                  extras={"effort": ceiling, "effort_ceiling": ceiling})
    low = REGISTRY.call("set_effort", {"level": 2, "reason": "one link"}, ctx)
    assert low["effort"] == 2 and ctx.extras["effort"]["level"] == 2
    assert ctx.extras["turn_limits"][0] == effort.profile(2)["turn_steps"]
    high = REGISTRY.call("set_effort", {"level": 9}, ctx)
    assert high["effort"] == 6 and "held_to_ceiling" in high


def test_a_reply_runs_under_the_effort_the_lead_chose(tmp_path):
    from resource_librarian import effort
    init(tmp_path / "v", name="v")
    replies = [Reply(text="", tool_calls=[ToolCall("1", "set_effort", {"level": 1})])] + \
        [Reply(text="", tool_calls=[ToolCall(str(i), "vault_status", {})]) for i in range(30)]
    loop = Loop(Vault(tmp_path / "v"), providers.Scripted(lambda s, m, t: replies.pop(0)),
                extras={"effort": effort.profile(8), "effort_ceiling": effort.profile(8)})
    loop.max_steps = effort.profile(8)["turn_steps"]
    turn = loop.send("add this link")
    assert turn.stopped == "max_steps" and turn.steps == effort.profile(1)["turn_steps"]


def test_naming_a_library_after_the_folder_it_is_made_in_is_refused(tmp_path):
    work = tmp_path / "Timeline-mapping"
    (work / "vault").mkdir(parents=True)
    (work / "vault" / "1914.md").write_text("notes", encoding="utf-8")
    with pytest.raises(library_picker.PickerError, match="Open a folder as a library"):
        library_picker.create(name="Timeline-mapping", parent=str(work))
    assert not (work / "Timeline-mapping").exists()
    made = library_picker.create(folder=str(work), adopt=True)
    assert Vault(made).exists() and (work / "vault" / "1914.md").read_text() == "notes"
