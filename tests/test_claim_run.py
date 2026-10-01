"""G3, running a claim's failing input (owner's decisions, 2026-10-01): function calls as
data, a person's action only, no network, Docker only - and every outcome kept."""
import json
import subprocess
import sys
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from resource_librarian import claim_run, clerk
from resource_librarian.evidence import EvidenceStore
from resource_librarian.loop import narrowed
from resource_librarian.registry import REGISTRY, Context

from conftest import add_source
from test_review_gate import CLAIM, SUMMARY, reviewing, to_synthesise
from test_sessions import OSQUERY_LINE, Model, library  # noqa: F401  (fixture)

GOOD = {"call": "dates.parse:parse_date", "args": ["31/02/2020"], "kwargs": {"strict": True},
        "expect": "raises", "value": "ValueError"}


@pytest.mark.parametrize("bad", [
    {**GOOD, "call": "os.system"},                         # no function named
    {**GOOD, "call": "x:y; rm -rf /"},
    {**GOOD, "call": "__import__('os'):system"},
    {**GOOD, "kwargs": {"not a name": 1}},
    {**GOOD, "args": "31/02/2020"},
    {**GOOD, "args": [float("nan")]},
    {**GOOD, "args": ["x" * 5000]},
    {**GOOD, "expect": "prints"},
    {**GOOD, "value": "ValueError(); import os"},
])
def test_a_failing_input_is_one_call_with_plain_json(bad):
    with pytest.raises(TypeError):
        claim_run.validate(bad)


def test_the_review_task_decodes_strings_and_drops_what_is_not_a_call():
    fi = clerk.failing_input({"call": "dates.parse:parse_date", "expect": "returns",
                              "arguments": '{"args": ["2020-02-31"], "kwargs": {}}',
                              "value": "null"})
    assert fi == {"call": "dates.parse:parse_date", "args": ["2020-02-31"], "kwargs": {},
                  "expect": "returns", "value": None}
    assert clerk.failing_input({"call": "m:f", "arguments": "[1, 2]", "expect": "raises",
                                "value": "KeyError"})["args"] == [1, 2]
    with pytest.raises(TypeError):
        clerk.failing_input({"call": "m:f", "arguments": "print(1)", "expect": "raises",
                             "value": "KeyError"})


def scripted_review(verdict, counter="", failing=None):
    def answer(payload):
        if payload["task"] != "review":
            return {}
        return {"verdict": verdict, "counter_quote": counter, "reason": "checked",
                "failing_input": failing or {"call": "", "arguments": "", "expect": "none",
                                             "value": ""}}
    return clerk.Scripted(answer)


def test_a_challenge_with_a_failing_input_is_kept_for_a_person_and_never_run(library):
    reviewing(library)
    m = Model(library)
    m.ctx.extras["clerk"] = scripted_review(
        "fails", OSQUERY_LINE[:40], {"call": "osquery.tables:query", "expect": "raises",
                                     "arguments": '{"args": ["SELECT 1"]}', "value": "KeyError"})
    to_synthesise(m)
    out = m("draft_offering", title="Host Watch Starter", summary=SUMMARY, claims=[CLAIM])
    assert out["refused"] == "REVIEW_CHALLENGED"
    [runnable] = out["runnable"]
    assert runnable["input"] == 'osquery.tables:query("SELECT 1") raises KeyError'
    assert f"claim run {runnable['run_id']}" in out["detail"]
    [listed] = REGISTRY.call("list_claim_runs", {}, Context(tier="consult", vault=library))["runs"]
    assert listed["verdict"] == "not run" and listed["source"] == "osquery"
    # kept with a rebuttal: the staged offering says so, and that nothing ran
    keep = {**CLAIM, "rebuttal": "the docs say otherwise"}
    out = m.ok("draft_offering", title="Host Watch Starter", summary=SUMMARY, claims=[keep])
    text = (library.root / out["staged"]).read_text(encoding="utf-8")
    assert "Failing input given: `osquery.tables:query(\"SELECT 1\") raises KeyError` - not run" \
        in text


def test_only_a_person_runs_one(library):
    assert "run_claim_input" not in {s.name for s in narrowed("contribute", projects_on=True)}
    out = REGISTRY.call("run_claim_input", {"run_id": "x"}, Context(tier="contribute",
                                                                    vault=library))
    assert out["refused"] == "TIER_REFUSED"


# -- the sandbox, with Docker and git faked: what is asked of Docker is the point

@pytest.fixture
def repo(tmp_path, library):
    """A real tiny repository the run clones, and its surveyed tree recorded as evidence."""
    root = tmp_path / "clone"
    (root / "dates").mkdir(parents=True)
    (root / "dates" / "__init__.py").write_text("")
    (root / "dates" / "parse.py").write_text("def parse_date(s, strict=False):\n"
                                             "    d, m, y = map(int, s.split('/'))\n"
                                             "    if d > 28 and m == 2:\n"
                                             "        raise ValueError('no such day')\n"
                                             "    return [y, m, d]\n")
    git = lambda *a: subprocess.run(["git", "-C", str(root), *a], check=True,  # noqa: E731
                                    capture_output=True)
    git("init", "-q")
    git("-c", "user.email=t@t", "-c", "user.name=t", "add", ".")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x")
    tree = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD^{tree}"],
                          capture_output=True, text=True).stdout.strip()
    survey = EvidenceStore(library).put("survey", "https://github.com/example/dates",
                                        {"tree_sha": tree})
    add_source(library.root, "Dates", "Parses dates.",
               extra_fm=f"evidence: [{survey.id}]".replace("[", "['").replace("]", "']"))
    return root


@contextmanager
def cloned(root):
    yield root


class FakeDocker:
    def __init__(self, outcome=None, running=True):
        self.calls, self.outcome, self.running = [], outcome, running

    def __call__(self, args, timeout):
        self.calls.append(args)
        if args[:2] == ["docker", "info"]:
            return SimpleNamespace(returncode=0 if self.running else 1, stdout="29.4.3",
                                   stderr="")
        return SimpleNamespace(returncode=0, stderr="",
                               stdout="noise\n" + claim_run.MARK + json.dumps(self.outcome))


def test_a_run_is_contained_and_its_verdict_kept_as_evidence(library, repo):
    store = claim_run.RunnableStore(library)
    run_id = store.add("parse_date accepts any day", "Dates", GOOD, "reply")
    assert store.add("parse_date accepts any day", "Dates", GOOD, "reply") == run_id  # once
    docker = FakeDocker({"stage": "call", "raised": "ValueError",
                         "qualified": "builtins.ValueError", "message": "no such day"})
    out = claim_run.run(library, run_id, runner=docker, cloner=lambda url: cloned(repo))
    assert out["verdict"] == "confirmed" and out["version"] == "the surveyed version"
    run = docker.calls[-1]
    for flag in (["--network", "none"], ["--cap-drop", "ALL"], ["--user", "65534:65534"],
                 ["--read-only"], ["--rm"]):
        assert any(run[i:i + len(flag)] == flag for i in range(len(run))), flag
    assert f"type=bind,source={repo},target=/src,readonly" in run
    assert [a for a in run if a.startswith("DEEPINFRA") or "KEY" in a] == []
    assert run[-4:] == [claim_run.IMAGE, "python", "-I", "/job/runner.py"]
    record = EvidenceStore(library).get(out["evidence"])
    assert record.kind == "execution" and record.payload["verdict"] == "confirmed"
    assert record.payload["network"] == "none"
    assert store.get(run_id)["verdict"] == "confirmed"


@pytest.mark.parametrize("outcome, verdict", [
    ({"stage": "call", "returned": [2020, 2, 31], "json": True}, "not_confirmed"),
    ({"stage": "call", "raised": "TypeError", "qualified": "builtins.TypeError",
      "message": "x"}, "not_confirmed"),
    ({"stage": "import", "error": "ModuleNotFoundError", "message": "No module named 'arrow'"},
     "could_not_run"),
])
def test_what_the_call_did_decides_the_verdict(library, repo, outcome, verdict):
    run_id = claim_run.RunnableStore(library).add("c", "Dates", GOOD, "reply")
    out = claim_run.run(library, run_id, runner=FakeDocker(outcome),
                        cloner=lambda url: cloned(repo))
    assert out["verdict"] == verdict
    if verdict == "could_not_run":
        assert "no network" in out["detail"]


def test_no_docker_no_run_and_never_the_host(library, repo, monkeypatch):
    run_id = claim_run.RunnableStore(library).add("c", "Dates", GOOD, "reply")
    docker = FakeDocker(running=False)
    # the tool, as a person calls it - with Docker reported down (a test never runs Docker)
    monkeypatch.setattr(claim_run, "docker_status", lambda runner=None: (False, "not running"))
    out = REGISTRY.call("run_claim_input", {"run_id": run_id},
                        Context(tier="curate", vault=library))
    assert out["refused"] == "EXECUTION_SANDBOX_ONLY"
    monkeypatch.undo()
    with pytest.raises(Exception) as caught:
        claim_run.run(library, run_id, runner=docker, cloner=lambda url: cloned(repo))
    assert getattr(caught.value, "code", "") == "EXECUTION_SANDBOX_ONLY"
    assert [c[:2] for c in docker.calls] == [["docker", "info"]]          # nothing else ran


def test_only_a_repositorys_own_code_runs(library):
    add_source(library.root, "A Paper", "About dates.", kind_folder="paper",
               extra_fm="kind: paper")
    with pytest.raises(TypeError):
        claim_run.repository_of(library, "A Paper")


def test_the_runner_itself(tmp_path, repo):
    """The fixed runner, run here on a fixture package (our own code, not a source's)."""
    job = tmp_path / "job"
    job.mkdir()
    spec = {"call": "dates.parse:parse_date", "args": ["31/02/2020"], "kwargs": {},
            "paths": [str(repo)]}
    (job / "spec.json").write_text(json.dumps(spec))
    (job / "runner.py").write_text(claim_run.RUNNER.replace("/job/spec.json",
                                                            str(job / "spec.json").replace("\\", "/")))
    done = subprocess.run([sys.executable, "-I", str(job / "runner.py")], capture_output=True,
                          text=True, timeout=60)
    outcome = claim_run.parse(done.stdout)
    assert outcome["raised"] == "ValueError" and outcome["message"] == "no such day"
    spec["args"] = ["01/03/2020"]
    (job / "spec.json").write_text(json.dumps(spec))
    done = subprocess.run([sys.executable, "-I", str(job / "runner.py")], capture_output=True,
                          text=True, timeout=60)
    assert claim_run.parse(done.stdout) == {"stage": "call", "returned": [2020, 3, 1],
                                            "json": True}
