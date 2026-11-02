"""REMED-07: the Manager sees the same effective surfaces as dispatch."""
from __future__ import annotations

from resource_librarian import content_roots, tools  # noqa: F401
from resource_librarian.agent_runtime import (BUNDLES, AgentProfile, DEFAULT_PROFILES, ProfileStore,
                                               bundle_selection, select_bundle)
from resource_librarian.app import App
from resource_librarian.audit_projection import capability_manifest
from resource_librarian.keys import KeyStore
from resource_librarian.providers import Reply, Scripted
from resource_librarian.registry import Context, REGISTRY


AUDITED = ("manage", "preflight", "execute", "audit", "reduce")


def test_manifest_and_runtime_share_the_exact_audited_bundle_selection():
    profile = DEFAULT_PROFILES["lead"]
    manifest = capability_manifest(tier="contribute", profile=profile)

    assert set(AUDITED) <= {row["id"] for row in manifest["bundles"]}
    for phase in AUDITED:
        row = manifest["audited_bundles"][phase]
        actual = [spec.name for spec in select_bundle(
            "contribute", phase, profile=profile, purpose="audited", working=True)]
        assert row["offered"] == actual
        assert row["registered"] == list(bundle_selection(
            "contribute", phase, profile=profile, purpose="audited",
            working=True).registered)
        assert row["admission"] == "checked_at_call_time"
        assert "admitted" not in row


def test_a_restrictive_profile_is_reported_as_the_same_read_fallback_runtime_uses():
    profile = AgentProfile("reader", "research_helper", allowed_bundles=["read"],
                           permission_ceiling="consult")
    manifest = capability_manifest(tier="contribute", profile=profile)

    for phase in AUDITED:
        row = manifest["audited_bundles"][phase]
        assert row["allowed"] is False
        assert row["fallback"] == "profile_read_fallback"
        assert row["registered"] == [name for name in BUNDLES[phase].names
                                     if name in REGISTRY]
        assert row["offered"] == [spec.name for spec in select_bundle(
            "contribute", phase, profile=profile, purpose="audited", working=True)]


def test_live_projection_derives_profile_routes_and_roots_from_the_app(vault, tmp_path):
    attached = tmp_path / "attached"
    attached.mkdir()
    (attached / "guide.md").write_text("# Guide\n", encoding="utf-8")
    plan = content_roots.plan_attach(vault, attached)
    content_roots.apply_attach(vault, attached, plan["survey_fingerprint"])

    app = App(vault, keys=KeyStore(use_keyring=False), coordinate=True,
              provider_for=lambda choice: Scripted(lambda *_: Reply(choice["model"])))
    try:
        app.set_tiers([{"provider": "deepinfra", "model": "scripted-lead"}],
                      override="fixture")
        ctx = Context(tier="contribute", vault=vault, extras=app._extras())
        REGISTRY.call("open_session", {"purpose": "audited", "question": "q"}, ctx)

        view = REGISTRY.call("audit_projection", {}, ctx)
        manifest = view["manifest"]

        assert manifest["profile"]["id"] == "lead"
        assert manifest["routes"]["lead"]["host_id"] == "preset-deepinfra"
        assert manifest["routes"]["lead"]["model"] == "scripted-lead"
        assert manifest["routes"]["lead"]["available"] is True
        roots = {row["path"]: row for row in manifest["root_access"]}
        assert roots["."]["access"] == "read_write"
        assert roots[str(attached.resolve())] == {
            "path": str(attached.resolve()), "access": "read_only", "attached": True}
        assert "audit_projection" in manifest["audited_bundles"]["manage"]["offered"]
    finally:
        app.close_runtime()


def test_route_policy_mismatch_is_fail_closed_in_the_derived_context(vault):
    app = App(vault, keys=KeyStore(use_keyring=False), coordinate=True,
              provider_for=lambda choice: Scripted(lambda *_: Reply(choice["model"])))
    try:
        app.set_tiers([{"provider": "deepinfra", "model": "scripted-lead"}],
                      override="fixture")
        app.profiles.save(AgentProfile(
            "restricted", "lead", route_policy={"host_ids": ["somewhere-else"]},
            allowed_bundles=["research"], required_qualification="experimental"))

        found = app._capability_context("restricted")

        assert found["routes"]["lead"]["available"] is False
        assert "does not allow host" in found["routes"]["lead"]["reason"]
        missing = app._capability_context("deleted-profile")
        assert all(row["available"] is False for row in missing["routes"].values())
        assert all("selected profile unavailable" in row["reason"]
                   for row in missing["routes"].values())
    finally:
        app.close_runtime()


def test_an_unavailable_context_callback_never_falls_back_to_the_whole_vault(vault):
    def unavailable(_profile):
        raise RuntimeError("context offline")

    ctx = Context(tier="contribute", vault=vault, extras={
        "agent_profile": "lead", "profile_store": ProfileStore(vault),
        "capability_context": unavailable,
    })
    REGISTRY.call("open_session", {"purpose": "audited", "question": "q"}, ctx)

    manifest = REGISTRY.call("audit_projection", {}, ctx)["manifest"]

    assert manifest["roots"] == []
    assert all(row["available"] is False for row in manifest["routes"].values())
    assert manifest["context_errors"] == [
        "effective dispatch context unavailable: context offline"]
