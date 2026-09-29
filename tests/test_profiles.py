"""Domain profiles (Co-work Roadmap §4 F3): a new library specialised for its
domain in one step - Content Model rows written at creation (choosing the
profile is the decision), lens packs, servers and workflows only suggested."""
import pytest

from resource_librarian import profiles, tools  # noqa: F401  (registers tools)
from resource_librarian.init import init
from resource_librarian.lens_packs import PackLibrary
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.vault import Vault
from resource_librarian.workflows import Library


def test_every_standard_profile_parses_and_points_at_real_things(tmp_path):
    init(tmp_path / "v", name="v")
    vault = Vault(tmp_path / "v")
    packs = {p["name"] for p in PackLibrary(vault).status()}
    flows = set(Library(vault).all())
    found = profiles.standard()
    assert {"software-systems", "course", "history"} <= set(found)
    for profile in found.values():
        assert set(profile.lens_packs) <= packs, profile.name
        assert set(profile.workflows) <= flows, profile.name


def test_a_history_library_can_hold_a_history_source(tmp_path):
    report = init(tmp_path / "History", name="History", profile="history")
    vault = Vault(tmp_path / "History")
    assert "source kind history" in report.profile["content_model_added"]
    from resource_librarian import schema
    model = schema.load(vault.root)
    assert "history" in model.kinds
    assert model.fields_for("source", "history").get("provenance") == "required"


def test_a_profile_only_suggests_and_the_checklist_follows_the_person(tmp_path):
    init(tmp_path / "History", name="History", profile="history")
    vault = Vault(tmp_path / "History")
    ctx = Context(tier="consult", vault=vault)
    listed = REGISTRY.call("library_profile", {}, ctx)
    assert listed["profile"] == "history"
    assert listed["lens_packs"] == [{"name": "history-sources", "state": "not accepted"}]
    assert PackLibrary(vault).accepted() == {}                    # nothing accepted for them
    REGISTRY.call("lens_pack_accept", {"name": "history-sources"},
                  Context(tier="curate", vault=vault))
    listed = REGISTRY.call("library_profile", {}, ctx)
    assert listed["lens_packs"][0]["state"] == "accepted"


def test_a_bad_profile_fails_before_anything_is_made(tmp_path):
    with pytest.raises(profiles.ProfileError):
        init(tmp_path / "Nope", name="Nope", profile="no-such-profile")
    assert not (tmp_path / "Nope").exists()
    bad = tmp_path / "bad.yaml"
    bad.write_text("profile: evil\ncontent_model:\n  tables:\n    - heading: \"## Rules\"\n"
                   "      rows: [\"| a |\", \"| - |\", \"| b |\"]\n", encoding="utf-8")
    with pytest.raises(profiles.ProfileError, match="not one a Content Model reads"):
        init(tmp_path / "Bad", name="Bad", profile=str(bad))


def test_a_plain_library_has_no_profile(tmp_path):
    init(tmp_path / "Plain", name="Plain")
    out = REGISTRY.call("library_profile", {}, Context(tier="consult",
                                                      vault=Vault(tmp_path / "Plain")))
    assert out["profile"] is None
