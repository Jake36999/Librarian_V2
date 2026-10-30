"""ACCEPT-01, Workbench execution labelling: every run says which isolation it
actually had, refusals record nothing, and a failed run can be retried."""
from __future__ import annotations

import sys
import tarfile
from types import SimpleNamespace

import pytest

from resource_librarian import sandbox, workbench
from resource_librarian import tools  # noqa: F401  (registers tools)
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.rules import Refusal
from resource_librarian.workbench import Engagement, EngagementStore

IMAGE = "example/image@sha256:" + "a" * 64


@pytest.fixture
def pinned(vault, tmp_path, monkeypatch):
    """A proposed engagement on a source whose pinned archive is local."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "marker.txt").write_text("pinned revision", encoding="utf-8")
    archive = tmp_path / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        bundle.add(source, arcname="example-test-abc")
    monkeypatch.setattr(workbench, "_repository", lambda *_: {"repo_key": "example/test",
                                                               "surveyed_tree": "abc"})
    copies = iter(range(100))

    def download(*_):
        # Each run gets its own download: execution deletes the archive after use.
        fresh = tmp_path / f"download-{next(copies)}.tar.gz"
        fresh.write_bytes(archive.read_bytes())
        return fresh, "archive-hash"

    monkeypatch.setattr(workbench, "_download_archive", download)
    engagement = Engagement(id="eng-accept", source="source", pinned_revision="abc",
                            created_at="now")
    EngagementStore(vault).put(engagement, "proposed")
    return vault


def log(vault):
    return EngagementStore(vault).path.read_bytes()


def ok(code=0):
    return [sys.executable, "-c", f"print('ran'); raise SystemExit({code})"]


def test_success_inspect_only_is_labelled_and_runs_nothing(pinned):
    out = workbench.start(pinned, "eng-accept", choice="inspect_only")
    assert out["isolation_tier"] == "inspect_only" and out["state"] == "inspected"
    assert out["run_ids"] == []


def test_success_host_execution_is_labelled_non_isolated_with_its_warning(pinned):
    out = workbench.start(pinned, "eng-accept", choice="non_isolated_host_exec", command=ok(),
                          confirm_non_isolated=True, person_confirmed=True)
    assert out["exit_code"] == 0 and out["isolation_tier"] == "non_isolated_host_exec"
    assert "No network containment is claimed" in out["warning"]
    stored = EngagementStore(pinned).get("eng-accept")
    assert stored.isolation_tier == "non_isolated_host_exec" and stored.state == "completed"
    assert stored.audit_trace[-1]["result"]["isolation_tier"] == "non_isolated_host_exec"


def test_success_docker_execution_is_labelled_isolated(pinned, monkeypatch):
    calls = []

    def runner(args, timeout):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="ran", stderr="")

    monkeypatch.setattr(sandbox, "docker_status", lambda runner=None: (True, "docker ready"))
    monkeypatch.setattr(workbench, "_docker_stage", lambda *_: ("src-volume", "archive-hash"))
    monkeypatch.setattr(workbench, "_archive_outputs", lambda *_: [])
    out = workbench.start(pinned, "eng-accept", choice="docker_isolated", command=["true"],
                          image=IMAGE, person_confirmed=True, runner=runner)
    assert out["isolation_tier"] == "docker_isolated"
    assert EngagementStore(pinned).get("eng-accept").isolation_tier == "docker_isolated"
    run = calls[-1]
    assert run[:2] == ["docker", "run"] and "--network" in run and "none" in run


@pytest.mark.parametrize("kwargs,code", [
    (dict(choice="non_isolated_host_exec", command=ok(), person_confirmed=True),
     "EXECUTION_SANDBOX_ONLY"),            # the weaker guarantee was not confirmed
    (dict(choice="non_isolated_host_exec", command=ok(), confirm_non_isolated=True),
     "PERSON_CONFIRMS"),                   # no person confirmed the run
    (dict(choice="docker_isolated", command=["true"], image=IMAGE, person_confirmed=True),
     "EXECUTION_SANDBOX_ONLY"),            # Docker is not available
])
def test_refusal_and_no_mutation_a_refused_start_records_nothing(pinned, monkeypatch, kwargs,
                                                                  code):
    monkeypatch.setattr(sandbox, "docker_status", lambda runner=None: (False, "no docker"))
    before = log(pinned)
    with pytest.raises(Refusal, match=code):
        workbench.start(pinned, "eng-accept", **kwargs)
    assert log(pinned) == before
    assert EngagementStore(pinned).get("eng-accept").state == "proposed"


def test_refusal_an_agent_cannot_start_execution(pinned):
    before = log(pinned)
    out = REGISTRY.call("engagement_start", {"engagement_id": "eng-accept",
                                             "choice": "non_isolated_host_exec",
                                             "command": ok()}, Context(tier="curate", vault=pinned))
    assert out["refused"] == "PERSON_CONFIRMS"
    assert log(pinned) == before


def test_recovery_a_failed_run_pauses_keeps_its_label_and_can_run_again(pinned):
    failed = workbench.start(pinned, "eng-accept", choice="non_isolated_host_exec",
                             command=ok(3), confirm_non_isolated=True, person_confirmed=True)
    assert failed["exit_code"] == 3 and failed["isolation_tier"] == "non_isolated_host_exec"
    assert EngagementStore(pinned).get("eng-accept").state == "paused"
    again = workbench.start(pinned, "eng-accept", choice="non_isolated_host_exec", command=ok(),
                            confirm_non_isolated=True, person_confirmed=True)
    stored = EngagementStore(pinned).get("eng-accept")
    assert again["exit_code"] == 0 and stored.state == "completed" and len(stored.run_ids) == 2
