"""Focused safety checks for the V2 remediation boundaries."""
from __future__ import annotations

import json
import sys
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from resource_librarian import ranking, workbench
from resource_librarian import tools  # noqa: F401  (register test tool surface)
from resource_librarian.checkpoints import CheckpointStore
from resource_librarian.coordination import (DocumentBusyError, DocumentLeases, VaultWatcher,
                                             VaultWriter, atomic_write_text, fingerprint)
from resource_librarian.registry import Context, REGISTRY
from resource_librarian.rules import Refusal
from resource_librarian.workbench import Engagement, EngagementStore


def test_agent_context_cannot_start_exec_select_ranking_or_stage_v1(vault):
    agent = Context(tier="curate", vault=vault)

    started = REGISTRY.call("engagement_start", {"engagement_id": "missing"}, agent)
    selected = REGISTRY.call("ranking_select", {"candidate_id": "missing"}, agent)
    imported = REGISTRY.call("v1_import_stage", {"v1_root": str(vault.root)}, agent)

    assert started["refused"] == "PERSON_CONFIRMS"
    assert selected["refused"] == "PERSON_CONFIRMS"
    assert imported["refused"] == "PERSON_CONFIRMS"


def test_workbench_library_start_also_requires_person_confirmation(vault):
    engagement = Engagement(id="eng-test", source="source", pinned_revision="abc", created_at="now")
    EngagementStore(vault).put(engagement, "proposed")

    with pytest.raises(Refusal, match="PERSON_CONFIRMS"):
        workbench.start(vault, engagement.id, choice="docker_isolated", command=["echo", "nope"])


def test_execution_and_forced_close_are_explicit_ui_checkpoints(vault):
    checkpoints = CheckpointStore(vault)
    person = Context(tier="curate", vault=vault,
                     extras={"caller_kind": "person", "checkpoints": checkpoints})
    started = REGISTRY.call("engagement_start", {
        "engagement_id": "eng-missing", "choice": "docker_isolated", "command": ["echo", "safe"],
        "image": "example/image@sha256:" + "a" * 64,
    }, person)
    assert started["status"] == "awaiting_checkpoint"
    checkpoint = started["checkpoint"]
    assert checkpoint["type"] == "docker_execution"
    resolved = checkpoints.resolve(checkpoint["id"], "approve")
    again = REGISTRY.call("engagement_start", {
        "engagement_id": "eng-missing", "choice": "docker_isolated", "command": ["echo", "safe"],
        "image": "example/image@sha256:" + "a" * 64, "checkpoint_id": resolved["id"],
    }, person)
    assert again["error"] != "refused"  # checkpoint is accepted; missing engagement is the next honest error

    forced = REGISTRY.call("engagement_close", {
        "engagement_id": "eng-missing", "force_reason": "documented abort",
    }, person)
    assert forced["status"] == "awaiting_checkpoint"
    assert forced["checkpoint"]["type"] == "forced_engagement_close"


def test_expired_checkpoint_cannot_authorize_a_later_operation(vault):
    checkpoints = CheckpointStore(vault)
    expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    first = checkpoints.create("host_model_override", "route:one",
                               choices=["approve", "cancel"], expires_at=expired)

    assert first["expired"] is True
    assert checkpoints.all(pending_only=True) == []
    with pytest.raises(ValueError, match="expired"):
        checkpoints.resolve(first["id"], "approve")

    # A retry does not resurrect the stale approval; it produces a fresh
    # review row for the current route decision.
    second = checkpoints.ensure("host_model_override", "route:one",
                                choices=["approve", "cancel"])
    assert second["id"] != first["id"]
    assert second["expired"] is False


def test_non_docker_execution_uses_pinned_archive_and_strips_provider_secret(vault, tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "marker.txt").write_text("pinned revision", encoding="utf-8")
    archive = tmp_path / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        bundle.add(source, arcname="example-test-abc")

    monkeypatch.setattr(workbench, "_repository", lambda *_: {"repo_key": "example/test",
                                                                  "surveyed_tree": "abc"})
    monkeypatch.setattr(workbench, "_download_archive", lambda *_: (archive, "archive-hash"))
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-host-command")
    engagement = Engagement(id="eng-host", source="source", pinned_revision="abc")
    command = [sys.executable, "-c", (
        "import os; from pathlib import Path; "
        "assert Path('marker.txt').read_text() == 'pinned revision'; "
        "assert not os.getenv('OPENAI_API_KEY'); print('host-run-ok')")]

    result = workbench._host_execute(vault, engagement, command)

    assert result["exit_code"] == 0, result["stderr"]
    assert result["isolation_tier"] == "non_isolated_host_exec"
    assert result["source_archive_sha256"] == "archive-hash"
    assert result["controls"]["network_containment"] is False
    assert result["controls"]["isolated_python"] is True
    assert "host-run-ok" in result["stdout"]


def test_ranking_status_reports_the_persons_active_mode(vault):
    ranking._save(vault, {"schema_version": 1, "active": "candidate-a", "history": [],
                          "candidates": [{"id": "candidate-a", "heuristics": {}}]})

    assert ranking.status(vault)["mode"] == "Candidate"


def test_vault_writer_records_preconditions_and_compact_operation_result(vault):
    """The serialized write audit remains useful without copying note content."""
    path = vault.root / "Notes" / "audited.md"
    writer = VaultWriter(vault)
    try:
        result = writer.submit(
            lambda: (atomic_write_text(path, "private note body"), {"status": "staged", "id": "n1"})[1],
            caller="test-agent",
            targets=["Notes/audited.md"],
            preconditions={"Notes/audited.md": "missing"},
        )
        assert result["status"] == "staged"
        assert writer.flush(2)
    finally:
        writer.close()

    records = [json.loads(line) for line in writer.log_path.read_text(encoding="utf-8").splitlines()]
    finished = records[-1]
    assert finished["status"] == "done"
    assert finished["caller"] == "test-agent"
    assert finished["targets"] == ["Notes/audited.md"]
    assert finished["precondition_fingerprints"]["Notes/audited.md"] == "missing"
    assert finished["observed_fingerprints"]["Notes/audited.md"] == "missing"
    assert finished["result"]["status"] == "staged"
    assert "private note body" not in json.dumps(finished)


def test_vault_writer_rejects_a_changed_expected_document_revision(vault):
    path = vault.root / "Notes" / "revision.md"
    atomic_write_text(path, "first revision")
    expected = fingerprint(path)
    atomic_write_text(path, "human revision")
    writer = VaultWriter(vault)
    try:
        with pytest.raises(DocumentBusyError, match="changed after it was read"):
            writer.submit(lambda: atomic_write_text(path, "agent overwrite"),
                          targets=["Notes/revision.md"],
                          preconditions={"Notes/revision.md": expected})
    finally:
        writer.close()

    assert path.read_text(encoding="utf-8") == "human revision"
    final = json.loads(writer.log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert final["status"] == "failed"
    assert final["observed_fingerprints"]["Notes/revision.md"] == fingerprint(path)


def test_active_document_conflict_creates_a_serialized_checkpoint(vault):
    """A document-aware refusal must be auditable and never overwrite typing."""
    leases = DocumentLeases(vault)
    writer = VaultWriter(vault, leases)
    checkpoints = CheckpointStore(vault)
    leases.heartbeat("Notes/active.md", editor="Obsidian", dirty=True)
    ctx = Context(tier="contribute", vault=vault, extras={
        "caller": "test-agent", "vault_writer": writer, "checkpoints": checkpoints,
    })
    try:
        result = REGISTRY.call("write_note", {
            "folder": "Notes", "name": "active", "body": "agent content",
        }, ctx)
        assert result["refused"] == "DOCUMENT_ACTIVE"
        assert result["checkpoint"]["type"] == "write_conflict"
        assert writer.flush(2)
    finally:
        writer.close()

    assert not (vault.root / "Notes" / "active.md").exists()
    records = [json.loads(line) for line in writer.log_path.read_text(encoding="utf-8").splitlines()]
    assert any(row["caller"] == "document-conflict-checkpoint" and row["status"] == "done"
               for row in records)


def test_watcher_treats_human_note_deletion_as_a_debounced_conflict(vault):
    path = vault.root / "Notes" / "deleted.md"
    atomic_write_text(path, "before deletion")
    leases = DocumentLeases(vault)
    watcher = VaultWatcher(vault, leases)
    watcher._known = watcher._snapshot()
    path.unlink()
    watcher.scan_once()

    with pytest.raises(DocumentBusyError, match="editor saving"):
        leases.assert_writable(["Notes/deleted.md"])
