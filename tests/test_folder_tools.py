"""Folder review on every surface (implementation plan M1a; as-is W-ACT-01).

Policy: a folder the person connected, or routed an agent to, is open to that library's agents through
the same actions the Web UI uses. Before this, folder review was reachable only through
`/api/folders/*`, so no MCP caller or workflow could survey or queue a folder. Who decides is
unchanged: a person accepts one folder; an agent accepts by policy only under promotion mode agent.
"""
from __future__ import annotations

import pytest

from resource_librarian import tools  # noqa: F401 - registers the folder tools
from resource_librarian.app import ApiError, App
from resource_librarian.folder_service import FolderService, refusal_of
from resource_librarian.init import init
from resource_librarian.keys import KeyStore
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.vault import Vault

from test_folder_review import fake_planner


@pytest.fixture
def library(tmp_path):
    vault = Vault(tmp_path / "library"); init(vault.root, name="library")
    source = tmp_path / "source"; source.mkdir()
    for name in ["src/a.py", "third_party_alpha/a.py", "third_party_beta/b.py", "docs/note.md", "docs/paper.pdf"]:
        path = source / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic fixture\n")
    applied: list = []
    service = FolderService(vault, planner=fake_planner, applier=lambda request: applied.append(request) or {"graphs": []})
    return vault, source, service, applied


def agent(vault, service, tier="contribute"):
    return Context(tier=tier, vault=vault, extras={"caller_kind": "mcp", "caller": "mcp", "folder_service": service})


def person(vault, service):
    return Context(tier="curate", vault=vault, extras={"caller_kind": "person", "folder_service": service})


def test_a_folder_error_names_its_rule():
    assert refusal_of(ValueError("FOLDER_STALE: survey again")).to_dict()["refused"] == "FOLDER_STALE"
    assert refusal_of(ValueError("SPEND_APPROVAL_REQUIRED")).code == "SPEND_APPROVAL_REQUIRED"
    assert refusal_of(ValueError("not a code")) is None


def test_an_agent_surveys_a_connected_folder_and_reads_its_cards(library):
    vault, source, service, _ = library
    out = REGISTRY.call("folder_survey", {"path": str(source)}, agent(vault, service))
    assert "error" not in out, out
    cards = REGISTRY.call("folder_overview", {}, agent(vault, service, tier="consult"))["cards"]
    assert {c["path"] for c in cards} == {"src", "third_party_alpha", "third_party_beta", "docs"}
    assert not any(c["queueable"] for c in cards)          # nothing accepted yet
    assert {c["state_label"] for c in cards} == {"Waiting for a decision"}


def test_accepting_one_folder_stays_the_persons(library):
    vault, source, service, applied = library
    REGISTRY.call("folder_survey", {"path": str(source)}, agent(vault, service))
    card = next(c for c in REGISTRY.call("folder_overview", {}, agent(vault, service))["cards"] if c["path"] == "docs")
    args = {"id": card["id"], "folder_fingerprint": card["folder_fingerprint"], "purpose": "own-docs", "graph": "library-docs"}
    assert REGISTRY.call("folder_accept", args, agent(vault, service))["refused"] == "TIER_REFUSED"
    declared = Context(tier="curate", vault=vault,
                       extras={"caller_kind": "person", "actor": {"kind": "agent", "name": "tier0"}, "folder_service": service})
    assert REGISTRY.call("folder_accept", args, declared)["refused"] == "PERSON_CONFIRMS"
    out = REGISTRY.call("folder_accept", args, person(vault, service))
    assert out.get("status") == "accepted", out
    assert applied
    cards = REGISTRY.call("folder_overview", {}, agent(vault, service))["cards"]
    docs = next(c for c in cards if c["path"] == "docs")
    assert docs["queueable"] is True                       # own-docs is queueable on every surface
    assert docs["state_label"] == "Decided and applied by a person"   # W-FOL-05: one meaning per state


def test_policy_acceptance_needs_promotion_mode_agent_as_a_named_refusal(library):
    vault, source, service, _ = library
    REGISTRY.call("folder_survey", {"path": str(source)}, agent(vault, service))
    out = REGISTRY.call("folder_accept_policy", {"root": str(source)}, agent(vault, service))
    assert out["refused"] == "PROMOTION_MODE" and "promotion" in out["rule"]


def test_queueing_an_unaccepted_folder_is_refused_by_name(library):
    vault, source, service, _ = library
    REGISTRY.call("folder_survey", {"path": str(source)}, agent(vault, service))
    out = REGISTRY.call("folder_queue_sources", {"folder": str(source / "docs")}, agent(vault, service))
    assert out["refused"] == "FOLDER_SOURCES"


def test_an_agent_queues_an_accepted_folders_documents_with_its_own_authority(library):
    vault, source, service, _ = library
    REGISTRY.call("folder_survey", {"path": str(source)}, agent(vault, service))
    card = next(c for c in REGISTRY.call("folder_overview", {}, agent(vault, service))["cards"] if c["path"] == "docs")
    REGISTRY.call("folder_accept", {"id": card["id"], "folder_fingerprint": card["folder_fingerprint"],
                                    "purpose": "own-docs", "graph": "library-docs"}, person(vault, service))
    out = REGISTRY.call("folder_queue_sources", {"folder": str(source / "docs")}, agent(vault, service))
    assert "error" not in out, out
    assert out["documents"] == 1 and out["queued"] == 1        # the PDF, the default scope


@pytest.fixture
def core(library, monkeypatch):
    vault, source, service, _ = library
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=5)
    app.broker.set_mode("auto")        # MCP writes still ask in Ask mode; the envelope is M2
    real = app._folder_service
    monkeypatch.setattr(app, "_folder_service", lambda: FolderService(
        vault, writer=app.writer, lock=app._folder_operation, serialized=app._serialized,
        counted=app._counted_mutation, planner=service.planner, applier=service.applier))
    assert real is not None
    yield app, source
    app.close_runtime()


def test_the_web_ui_routes_call_the_same_tools_and_keep_their_codes(core):
    app, source = core
    out = app.survey_folders(str(source))
    assert "error" not in out
    cards = app.folders()["cards"]
    card = next(c for c in cards if c["path"] == "src")
    with pytest.raises(ApiError) as stale:
        app.accept_folder({"id": card["id"], "folder_fingerprint": "not-the-fingerprint",
                           "purpose": "own-current", "graph": "library-code"})
    assert stale.value.status == 409 and str(stale.value).startswith("FOLDER_STALE")
    with pytest.raises(ApiError) as policy:
        app.accept_folders_by_policy({"root": str(source)})
    assert policy.value.status == 409 and "PROMOTION_MODE" in str(policy.value)
    accepted = app.accept_folder({"id": card["id"], "folder_fingerprint": card["folder_fingerprint"],
                                  "purpose": "own-current", "graph": "library-code"})
    assert accepted["status"] == "accepted"
    surfaces = [line for line in app.call_log.today_path().read_text(encoding="utf-8").splitlines()]
    assert any('"tool":"folder_accept"' in line for line in surfaces)


def test_an_mcp_caller_reaches_folder_review_through_the_core(core):
    app, source = core
    out = app.mcp_call("folder_survey", {"path": str(source)}, tier="contribute")["result"]
    assert "error" not in out, out
    refused = app.mcp_call("folder_approve_batch", {"items": ["x"]}, tier="contribute")["result"]
    assert refused["refused"] == "TIER_REFUSED"


def test_selected_for_the_batch_never_reads_as_decided():
    from resource_librarian.folder_service import state_label
    assert state_label({"status": "approved"}) == "Selected for the description batch; not decided yet"
    assert state_label({"status": "accepted", "decision": {"accepted_by": "agent-policy"}}) == \
        "Decided and applied by the agent policy"
    assert state_label({"status": "staged"}) == "Waiting for a decision"
