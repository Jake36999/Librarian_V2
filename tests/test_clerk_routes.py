"""Routing one clerk task to a different provider (Co-work Roadmap §4 C1):
the evaluation's split - a local 4B for the bulk and for checking, an API
model only for finding stances - set with a flat `route_<task>` key."""
import threading
import time

import pytest

from resource_librarian import clerk


def test_a_route_sends_one_task_to_another_provider():
    router = clerk.from_config({"provider": "lmstudio", "model": "qwen/qwen3-4b-2507",
                                "route_lens_perspective": "deepinfra:deepseek-ai/DeepSeek-V4-Pro",
                                "route_points": "deepinfra"})
    assert isinstance(router, clerk.Router)
    perspective = router.for_task("lens_perspective")
    assert perspective.base_url.startswith("https://api.deepinfra.com")
    assert perspective.model == "deepseek-ai/DeepSeek-V4-Pro"
    assert router.for_task("points").model == clerk.PRESETS["deepinfra"]["model"]  # preset default
    assert router.for_task("terms").base_url.startswith("http://127.0.0.1")        # the default
    assert clerk.is_local(router)                     # the bulk runs here: the ten-minute rule holds


def test_a_route_can_give_a_reasoning_model_more_room_and_time():
    # G5: GLM-5.3 as a reviewer needs ~32k output tokens, far over the task's own ask.
    router = clerk.from_config({"provider": "lmstudio", "model": "m",
                                "route_review": "deepinfra:zai-org/GLM-5.3",
                                "min_tokens_review": 32000, "timeout_review": "900"})
    review = router.for_task("review")
    assert (review.model, review.min_tokens, review.timeout) == ("zai-org/GLM-5.3", 32000, 900)
    assert router.for_task("points").min_tokens != 32000           # only that route


def test_no_route_means_the_plain_endpoint_as_before():
    assert isinstance(clerk.from_config({"provider": "lmstudio", "model": "m"}),
                      clerk.OpenAICompatible)
    assert clerk.from_config({}) is None


def test_an_unknown_route_provider_is_refused():
    with pytest.raises(clerk.ClerkUnavailable, match="not a clerk provider"):
        clerk.from_config({"provider": "lmstudio", "route_points": "nowhere:x"})


def _recording(label: str, concurrency: int, seen: list, peak: dict):
    lock = threading.Lock()
    active = {"n": 0}

    def answer(payload):
        with lock:
            active["n"] += 1
            peak[label] = max(peak.get(label, 0), active["n"])
        time.sleep(0.05)
        with lock:
            active["n"] -= 1
        seen.append((label, payload["task"]))
        return {"bullets": []} if payload["task"] != "lens_perspective" else \
            {"has_perspective": False, "name": "", "explanation": "", "source_quote": ""}
    return clerk.Scripted(answer, concurrency=concurrency)


def test_tasks_are_grouped_by_endpoint_each_at_its_own_concurrency():
    seen, peak = [], {}
    local = _recording("local", 1, seen, peak)
    api = _recording("api", 4, seen, peak)
    router = clerk.Router(local, {"lens_perspective": api})
    tasks = [clerk.points(f"text {i}") for i in range(4)] + \
        [clerk.lens_perspective(f"text {i}") for i in range(4)]
    results = clerk.run(tasks, router)
    assert [r.task for r in results] == [t.kind.name for t in tasks]      # order kept
    assert {label for label, task in seen if task == "points"} == {"local"}
    assert {label for label, task in seen if task == "lens_perspective"} == {"api"}
    assert peak["local"] == 1                          # a local model: one task at a time
    assert peak["api"] > 1                             # an API route: in parallel


def test_with_no_default_an_unrouted_task_waits_in_the_queue(tmp_path):
    router = clerk.Router(None, {"lens_perspective": clerk.Scripted(lambda p: {})})
    [result] = clerk.run([clerk.points("text")], router, tmp_path)
    assert result.status == "queued"


def test_route_keys_survive_the_app_rewriting_the_config(vault):
    vault.set_setting("clerk", "provider", "lmstudio")
    vault.set_setting("clerk", "route_lens_perspective", "deepinfra:deepseek-ai/DeepSeek-V4-Pro")
    vault.set_setting("promotion", "mode", "person")               # any later rewrite
    assert vault.config()["clerk"]["route_lens_perspective"] == \
        "deepinfra:deepseek-ai/DeepSeek-V4-Pro"
    assert isinstance(clerk.from_config(vault.config()["clerk"]), clerk.Router)


def test_doctor_says_when_a_routed_provider_has_no_key(vault, monkeypatch):
    from resource_librarian import doctor
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
    vault.set_setting("clerk", "route_lens_perspective", "deepinfra:deepseek-ai/DeepSeek-V4-Pro")
    [check] = [c for c in doctor.checks(vault) if c.name == "clerk route: lens_perspective"]
    assert not check.ok and "DEEPINFRA_API_KEY" in check.detail
    monkeypatch.setenv("DEEPINFRA_API_KEY", "sk-test-not-real-0000")
    [check] = [c for c in doctor.checks(vault) if c.name == "clerk route: lens_perspective"]
    assert check.ok
