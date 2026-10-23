"""Durable L2/L3 qualification plans never impersonate completed evidence."""
from __future__ import annotations

from resource_librarian.hosts import EvaluationJobStore
from test_app import served  # reuse the real loopback API fixture


def _plan(level: str = "L2", compatibility: str = "hard-a", behavior: str = "soft-a") -> dict:
    return {
        "host_id": "preset-openai", "model": "example-model", "role": "lead", "level": level,
        "runs": 3 if level == "L2" else 5, "fingerprints": {
            "compatibility": compatibility, "behavior": behavior,
        },
    }


def test_evaluation_job_survives_reload_and_requires_artifact_backed_slots(tmp_path):
    path = tmp_path / "evaluation-jobs.json"
    store = EvaluationJobStore(path)
    job = store.create(_plan())

    assert job.state == "queued"
    assert job.public()["remaining_runs"] == 3
    assert job.public()["requires_result_artifact"] is True

    reloaded = EvaluationJobStore(path)
    job = reloaded.get(job.id)
    assert job.id and job.completed_runs == 0 and job.state == "queued"

    reloaded.begin_result(job.id, compatibility_fingerprint="hard-a")
    job = reloaded.finish_result(job.id, "run-one", outcome="pass", detail="artifact retained")
    assert job.state == "queued" and job.completed_runs == 1

    reloaded.begin_result(job.id, compatibility_fingerprint="hard-a")
    job = reloaded.finish_result(job.id, "run-two", outcome="unavailable", detail="provider outage")
    assert job.state == "paused" and job.completed_runs == 2
    assert reloaded.resume(job.id).state == "queued"


def test_hard_change_stales_unfinished_job_but_soft_change_is_advisory(tmp_path):
    store = EvaluationJobStore(tmp_path / "evaluation-jobs.json")
    soft = store.create(_plan())
    changed = store.invalidate_route(host_id="preset-openai", model_id="example-model", role="lead",
                                     compatibility_fingerprint="hard-a", behavior_fingerprint="soft-b")
    assert changed == [soft]
    assert soft.state == "queued" and soft.advisory_stale is True

    hard = store.create(_plan("L3", compatibility="hard-a", behavior="soft-a"))
    changed = store.invalidate_route(host_id="preset-openai", model_id="example-model", role="lead",
                                     compatibility_fingerprint="hard-b", behavior_fingerprint="soft-b")
    assert soft.state == "stale" and hard.state == "stale"
    assert {job.id for job in changed} == {soft.id, hard.id}


def test_l2_http_job_needs_spend_confirmation_and_evaluator_artifacts(served):
    app, client, _ = served
    body = {"host_id": "preset-openai", "model": "example-model", "role": "lead", "level": "L2"}

    status, refused = client.post("/api/qualification/run", body)
    assert status == 409 and refused["checkpoint"] == "evaluation_spend"
    checkpoint = refused["checkpoint_record"]
    assert checkpoint["type"] == "evaluation_spend"
    status, resolved = client.post("/api/checkpoints/resolve", {"id": checkpoint["id"], "choice": "approve"})
    assert status == 200 and resolved["resolution"] == "approve"

    status, queued = client.post("/api/qualification/run", {**body, "checkpoint_id": checkpoint["id"]})
    assert status == 200 and queued["status"] == "queued"
    job = queued["job"]
    assert job["completed_runs"] == 0 and job["total_runs"] == 3
    status, listed = client.get("/api/qualification/jobs?host_id=preset-openai&model=example-model")
    assert status == 200 and [row["id"] for row in listed["jobs"]] == [job["id"]]

    status, missing = client.post("/api/qualification/jobs/result", {
        "id": job["id"], "outcome": "pass", "detail": "walk passed",
    })
    assert status == 400 and "artifact" in missing["error"]

    for number in range(1, 4):
        status, result = client.post("/api/qualification/jobs/result", {
            "id": job["id"], "outcome": "pass", "detail": f"micro walk {number}",
            "artifact": f"tests/artifacts/micro-{number}.json",
        })
        assert status == 200
    assert result["job"]["state"] == "completed"
    # L2 observations alone may screen a route later, but are never presented
    # as a completed local L3 qualification.
    assert result["status"]["qualification"]["status"] != "verified_local"
    assert len(result["status"]["runs"]) == 3
    assert set(app.evaluation_jobs.get(job["id"]).run_ids) == {
        row["id"] for row in result["status"]["runs"]
    }


def test_dependency_change_runs_l0_and_queues_requalification_without_spending(served, monkeypatch):
    """Schema/endpoint changes cannot hide behind time expiry, while a prompt
    refinement remains advisory and never fires a paid call on its own."""
    import resource_librarian.app as app_module

    app, client, _ = served
    host_id, model, role = "preset-openai", "example-model", "lead"
    first = app._qualification_fingerprints(host_id, model, role)
    app.qualifications.record(host_id=host_id, model_id=model, role=role, level="L1", outcome="pass",
                              compatibility_fingerprint=first["compatibility"],
                              behavior_fingerprint=first["behavior"], observed_model=model)

    # A soft prompt dependency change retains evidence as advisory, records a
    # deterministic L0, and only creates an inert L2 plan.
    app.settings.update(reply_length="short")
    status, soft = client.get(f"/api/qualification?host_id={host_id}&model={model}&role={role}")
    assert status == 200 and soft["requalification"]["kind"] == "soft"
    assert soft["requalification"]["l0"]["outcome"] == "pass"
    assert soft["requalification"]["required_levels"] == ["L2"]
    assert soft["requalification"]["queued_jobs"][0]["level"] == "L2"
    assert soft["requalification"]["queued_jobs"][0]["state"] == "queued"
    assert "No provider call" in soft["requalification"]["queued_jobs"][0]["detail"]

    # A hard protocol change drops the route to experimental and queues the
    # full post-L0 path; L1 still needs a person's visible spend checkpoint.
    monkeypatch.setattr(app_module, "PROTOCOL_VERSION", "qualification-test-hard-change")
    status, hard = client.get(f"/api/qualification?host_id={host_id}&model={model}&role={role}")
    assert status == 200 and hard["requalification"]["kind"] == "hard"
    assert hard["qualification"]["status"] == "experimental"
    assert hard["requalification"]["required_levels"] == ["L1", "L2", "L3"]
    assert {job["level"] for job in hard["requalification"]["queued_jobs"]} == {"L2", "L3"}

