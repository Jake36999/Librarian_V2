"""ACCEPT-01, Workbench execution labelling: every run says which isolation it
actually had, refusals record nothing, and a failed run can be retried."""
from __future__ import annotations

import sys
import tarfile

import pytest

from resource_librarian import sandbox, workbench
from resource_librarian import tools  # noqa: F401  (registers tools)
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.rules import Refusal
from resource_librarian.workbench import Engagement, EngagementStore

from docker_fake import Docker

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


def exported(vault, engagement, producer):
    producer.dispose()
    return {"artifacts": [], "export": {"complete": True}}


def test_success_docker_execution_is_labelled_isolated(pinned, monkeypatch):
    runner = Docker(stdout="ran")
    monkeypatch.setattr(sandbox, "docker_status", lambda runner=None: (True, "docker ready"))
    monkeypatch.setattr(workbench, "_docker_stage", lambda *_: ("src-volume", "archive-hash"))
    monkeypatch.setattr(workbench, "_archive_outputs", exported)
    out = workbench.start(pinned, "eng-accept", choice="docker_isolated", command=["true"],
                          image=IMAGE, person_confirmed=True, runner=runner)
    assert out["isolation_tier"] == "docker_isolated" and out["stdout"] == "ran"
    stored = EngagementStore(pinned).get("eng-accept")
    assert stored.isolation_tier == "docker_isolated" and stored.state == "completed"
    run = runner.create_args()
    assert "--network" in run and "none" in run and "--rm" not in run
    assert out["execution"]["state"] == "disposed"


def test_a_docker_run_not_shown_stopped_is_paused_never_completed(pinned, monkeypatch):
    """MF-016: cleanup_unknown blocks the success label, whatever the exit code said."""
    runner = Docker(stdout="ran", inspect_fails=True)
    monkeypatch.setattr(sandbox, "docker_status", lambda runner=None: (True, "docker ready"))
    monkeypatch.setattr(workbench, "_docker_stage", lambda *_: ("src-volume", "archive-hash"))
    out = workbench.start(pinned, "eng-accept", choice="docker_isolated", command=["true"],
                          image=IMAGE, person_confirmed=True, runner=runner)
    assert out["exit_code"] == 0 and out["execution"]["state"] == "cleanup_unknown"
    assert out["export"]["complete"] is False and "cp" not in runner.verbs()
    stored = EngagementStore(pinned).get("eng-accept")
    assert stored.state == "paused" and stored.artifacts == []


def test_a_docker_run_without_output_permission_mounts_and_exports_nothing(pinned, monkeypatch):
    """MF-015 (owner, 2026-11-05): the output volume has no cap while the run writes, so
    it is mounted only when `sandbox_output` is allowed, which a person decides apart."""
    from resource_librarian.broker import Broker
    asked = []
    runner = Docker(stdout="ran")

    def refused(*_):
        raise AssertionError("nothing may be exported without the output permission")

    monkeypatch.setattr(sandbox, "docker_status", lambda runner=None: (True, "docker ready"))
    monkeypatch.setattr(workbench, "_docker_stage", lambda *_: ("src-volume", "archive-hash"))
    monkeypatch.setattr(workbench, "_archive_outputs", refused)
    broker = Broker("auto", timeout=5)

    def listen(event):
        if event.get("type") == "permission_request":
            asked.append(event["tool"])
            broker.answer(event["id"], "deny")

    broker.subscribe(listen)
    ctx = Context(tier="curate", vault=pinned, extras={"broker": broker})
    out = workbench.start(pinned, "eng-accept", choice="docker_isolated", command=["true"],
                          image=IMAGE, person_confirmed=True, runner=runner, ctx=ctx)

    assert asked == ["sandbox_output"] and out["exit_code"] == 0
    assert not any("dst=/workspace/output" in arg for arg in runner.create_args())
    assert "cp" not in runner.verbs() and not runner.status        # removed all the same
    assert out["export"]["complete"] is False and "not permitted" in out["export"]["stopped"]


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
