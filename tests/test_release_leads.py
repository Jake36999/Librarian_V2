"""Release-lead evidence is useful only when it is complete and compatible."""
from __future__ import annotations

import json
import hashlib

from resource_librarian.hosts import (RELEASE_LEAD_SCHEMA_VERSION,
                                      RELEASE_PROMPT_CONTRACT_VERSION,
                                      RELEASE_TOOL_CONTRACT_VERSION, digest,
                                      endpoint_fingerprint, release_lead_for_route,
                                      release_leads, validate_release_lead_manifest)


def _stable_manifest() -> dict:
    endpoint = {"protocol": "openai", "base_url": "https://api.openai.example/v1",
                "auth_ref": "OPENAI_API_KEY"}
    lead = {
        "id": "ci-openai-lead", "provider": "openai", "host_id": "preset-openai",
        "model": "example-2026-10-01", "model_version": "example-2026-10-01",
        "model_fingerprint": digest({"provider": "openai", "model": "example-2026-10-01",
                                      "model_version": "example-2026-10-01"}),
        "role": "lead", "qualification": "verified_release", "endpoint": endpoint,
        "endpoint_fingerprint": endpoint_fingerprint(endpoint), "l3_runs": 5,
        "tested_at": "2026-10-01T00:00:00+00:00", "expires_at": "2027-01-01T00:00:00+00:00",
        "qualification_artifacts": [{"id": "ci://golden/openai", "sha256": "a" * 64}],
    }
    manifest = {
        "schema_version": RELEASE_LEAD_SCHEMA_VERSION, "release_status": "stable",
        "release_version": "2.1.0", "signing": {
            "status": "signed", "verification": {
                "id": "ci-release-signature", "verified_at": "2026-10-01T01:00:00+00:00"}},
        "contract": {"protocol_version": "2", "tool_contract_version": RELEASE_TOOL_CONTRACT_VERSION,
                     "prompt_contract_version": RELEASE_PROMPT_CONTRACT_VERSION,
                     "core_version_range": ">=2.1.0,<2.2.0"},
        "leads": [lead],
    }
    manifest["integrity"] = digest(manifest)
    return manifest


def test_complete_signed_release_lead_is_available_only_for_its_exact_contract(tmp_path):
    manifest = _stable_manifest()
    path = tmp_path / "release_leads.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    loaded = release_leads(path)
    assert loaded["integrity_valid"]
    assert loaded["manifest_valid"]
    valid, reason = validate_release_lead_manifest(loaded)
    assert valid, reason

    endpoint = manifest["leads"][0]["endpoint"]
    chosen, reason = release_lead_for_route(
        "preset-openai", "example-2026-10-01", manifest=loaded,
        contract={"protocol_version": "2", "tool_contract_version": RELEASE_TOOL_CONTRACT_VERSION,
                  "prompt_contract_version": RELEASE_PROMPT_CONTRACT_VERSION,
                  "core_version": "2.1.0", "endpoint": endpoint,
                  "endpoint_fingerprint": endpoint_fingerprint(endpoint)},
    )
    assert reason == ""
    assert chosen is not None and chosen["id"] == "ci-openai-lead"


def test_release_lead_fails_closed_when_its_endpoint_contract_changes(tmp_path):
    manifest = _stable_manifest()
    path = tmp_path / "release_leads.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    loaded = release_leads(path)
    wrong_endpoint = {"protocol": "openai", "base_url": "https://different.example/v1",
                      "auth_ref": "OPENAI_API_KEY"}

    chosen, reason = release_lead_for_route(
        "preset-openai", "example-2026-10-01", manifest=loaded,
        contract={"protocol_version": "2", "tool_contract_version": RELEASE_TOOL_CONTRACT_VERSION,
                  "prompt_contract_version": RELEASE_PROMPT_CONTRACT_VERSION,
                  "core_version": "2.1.0", "endpoint": wrong_endpoint,
                  "endpoint_fingerprint": endpoint_fingerprint(wrong_endpoint)},
    )
    assert chosen is None
    assert "endpoint" in reason


def test_development_candidate_manifest_never_becomes_verified_evidence(tmp_path):
    manifest = _stable_manifest()
    manifest["release_status"] = "development_template"
    manifest["integrity"] = digest({key: value for key, value in manifest.items() if key != "integrity"})
    path = tmp_path / "release_leads.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    loaded = release_leads(path)
    assert loaded["integrity_valid"]
    assert not loaded["manifest_valid"]
    chosen, reason = release_lead_for_route(
        "preset-openai", "example-2026-10-01", manifest=loaded,
        contract={"protocol_version": "2", "tool_contract_version": RELEASE_TOOL_CONTRACT_VERSION,
                  "prompt_contract_version": RELEASE_PROMPT_CONTRACT_VERSION},
    )
    assert chosen is None
    assert "development template" in reason


def test_installed_release_lead_override_requires_the_bundle_hash(tmp_path, monkeypatch):
    manifest = _stable_manifest()
    path = tmp_path / "release-leads.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("LIBRARIAN_RELEASE_LEADS_PATH", str(path))
    monkeypatch.setenv("LIBRARIAN_RELEASE_LEADS_SHA256", hashlib.sha256(path.read_bytes()).hexdigest())

    loaded = release_leads()
    assert loaded["integrity_valid"]
    assert loaded["manifest_valid"]


def test_damaged_installed_release_lead_override_fails_closed(tmp_path, monkeypatch):
    manifest = _stable_manifest()
    path = tmp_path / "release-leads.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("LIBRARIAN_RELEASE_LEADS_PATH", str(path))
    monkeypatch.setenv("LIBRARIAN_RELEASE_LEADS_SHA256", "0" * 64)

    loaded = release_leads()
    assert loaded["leads"] == []
    assert not loaded["integrity_valid"]
    assert "hash" in loaded["manifest_reason"]
