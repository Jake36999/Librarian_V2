"""DELEG-06: the controller applies, checks and repairs; the worker only proposes."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


REPOSITORY = Path(__file__).parents[1]
SCRIPTS = REPOSITORY / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("delegation_controller",
                                              SCRIPTS / "delegation_controller.py")
assert SPEC is not None and SPEC.loader is not None
controller = importlib.util.module_from_spec(SPEC)
sys.modules["delegation_controller"] = controller
SPEC.loader.exec_module(controller)
import check_work_package  # noqa: E402  (on the path through the controller)

VENV_PYTHON = Path(sys.executable)
CALC = "def double(x):\n    return x + x\n"
GOOD = ("<<<FILE src/toy/calc.py>>>\ndef double(x):\n    return x + x\n\n\n"
        "def triple(x):\n    return 3 * x\n<<<END FILE>>>")
WRONG = ("<<<FILE src/toy/calc.py>>>\ndef double(x):\n    return x + x\n\n\n"
         "def triple(x):\n    return 2 * x\n<<<END FILE>>>")


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), "-c", "core.autocrlf=false",
                           "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
                          capture_output=True, check=True, text=True).stdout


def write(root: Path, path: str, text: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")


def committed(repo: Path, path: str) -> str:
    data = subprocess.run(["git", "-C", str(repo), "show", f"HEAD:{path}"],
                          capture_output=True, check=True).stdout
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def toy(tmp_path):
    """A tiny repository whose goldens are committed in the base, as the contract requires."""
    repo = tmp_path / "toy"
    repo.mkdir()
    git(repo, "init", "-q")
    write(repo, "pyproject.toml", "[project]\nname = \"toy\"\nversion = \"0\"\n")
    write(repo, "src/toy/__init__.py", "")
    write(repo, "src/toy/calc.py", CALC)
    write(repo, "tests/test_calc.py",
          "from toy.calc import triple\n\n\ndef test_triple():\n    assert triple(3) == 9\n")
    write(repo, "tests/test_existing.py",
          "from toy.calc import double\n\n\ndef test_double():\n    assert double(4) == 8\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base with goldens")
    return repo


def package(repo: Path, tmp_path: Path, **admission) -> Path:
    python = subprocess.run([str(VENV_PYTHON), "-c",
                             "import platform; print(platform.python_version())"],
                            capture_output=True, text=True, check=True).stdout.strip()
    venv = ".venv/Scripts/python.exe"
    wp = {"schema_version": 1, "admission": {
        "package_id": "TOY-1-wp1", "task_id": "TOY-1",
        "objective": "Add triple(x) to toy.calc without changing double.",
        "class": "implementation", "base_revision": git(repo, "rev-parse", "HEAD").strip(),
        "write_targets": ["src/toy/calc.py"],
        "read_targets": ["tests/test_calc.py", "tests/test_existing.py"],
        "forbidden_targets": ["tests/"],
        "protected_targets": [{"path": p, "sha256": committed(repo, p)}
                              for p in ("tests/test_calc.py", "tests/test_existing.py")],
        "preserve": ["double keeps its behaviour"],
        "checks": [
            {"id": "oracle", "command": f"{venv} -m pytest tests/test_calc.py -q -p no:cacheprovider",
             "kind": "oracle", "expected_before": "fail", "covers": ["P1"]},
            {"id": "existing", "command": f"{venv} -m pytest tests/test_existing.py -q -p no:cacheprovider",
             "kind": "regression", "expected_before": "pass", "covers": ["P2"]},
            {"id": "suite", "command": f"{venv} -m pytest tests -q -p no:cacheprovider",
             "kind": "suite", "expected_before": "pass", "covers": ["P2"]}],
        "acceptance_predicates": [
            {"id": "P1", "kind": "behaviour", "text": "triple(3) == 9"},
            {"id": "P2", "kind": "integrates", "text": "existing tests still pass"}],
        "environment": {"python": python, "venv": ".venv",
                        "dependency_sha256": committed(repo, "pyproject.toml")},
        "owner_host_gate": False,
        "roles": {"drafter_model": "deepseek-ai/DeepSeek-V4-Pro",
                  "reviewer_model": "anthropic/claude", "merge_owner": "owner"},
        "budget": {"pool": "claude", "task_usd": 0.2, "max_calls": 3,
                   "max_repair_rounds": 2, "wall_clock_s": 600},
        "stop_conditions": ["a protected test would need to change"],
        "documentation_consequence": "none"}}
    wp["admission"].update(admission)
    path = tmp_path / "package.json"
    path.write_text(json.dumps(wp), encoding="utf-8")
    return path


class FakeWorker:
    """Replies in order; records what the controller sent."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, instruction, files, worktree, parent_run, round_no):
        self.calls.append({"instruction": instruction, "files": files, "worktree": worktree,
                           "parent_run": parent_run, "round": round_no})
        reply = self.replies.pop(0)
        if isinstance(reply, controller.WorkerResult):
            return reply
        return controller.WorkerResult(f"run-{round_no}", reply, 0, "")


def run(toy, tmp_path, worker, **admission):
    brief = tmp_path / "brief.txt"
    brief.write_text("Add triple(x) returning three times x.", encoding="utf-8")
    return controller.run_package(package(toy, tmp_path, **admission), brief, worker=worker,
                                  repository=toy, venv_python=VENV_PYTHON,
                                  out_dir=tmp_path / "out")


def test_a_correct_first_reply_is_applied_checked_and_committed(toy, tmp_path):
    worker = FakeWorker(GOOD)
    record = run(toy, tmp_path, worker)
    done = record["completion"]
    assert done["proposed_disposition"] == "accept"
    assert done["predicates"] == {"P1": "met", "P2": "met"}
    assert {r["id"] for r in done["check_results"]} == {"oracle", "existing", "suite"}
    assert all(r["ran_by"] == "controller" and r["exit_code"] == 0 for r in done["check_results"])
    assert done["protected_targets_intact"] is True
    assert [f["path"] for f in done["changed_files"]] == ["src/toy/calc.py"]
    worktree = Path(record["execution"]["worktree"])
    assert git(worktree, "rev-parse", "HEAD").strip() == done["artifact"]["ref"]
    assert "def triple" in (worktree / "src/toy/calc.py").read_text(encoding="utf-8")
    assert (toy / "src/toy/calc.py").read_text(encoding="utf-8") == CALC  # base untouched
    assert check_work_package.schema_errors(record) == []
    assert check_work_package.rule_errors(record) == []
    assert json.loads((tmp_path / "out" / "package.json").read_text(encoding="utf-8")) == record
    sent = worker.calls[0]
    assert sorted(sent["files"]) == ["src/toy/calc.py", "tests/test_calc.py", "tests/test_existing.py"]
    assert "<<<FILE" in sent["instruction"] and "src/toy/calc.py" in sent["instruction"]


def test_a_failing_check_is_fed_back_for_a_repair_round(toy, tmp_path):
    worker = FakeWorker(WRONG, GOOD)
    record = run(toy, tmp_path, worker)
    assert record["completion"]["proposed_disposition"] == "accept"
    assert record["execution"]["repair_rounds"] == 1 == record["completion"]["repair_rounds"]
    repair = worker.calls[1]
    assert repair["parent_run"] == "run-0" and repair["round"] == 1
    assert "oracle" in repair["instruction"] and "assert" in repair["instruction"]
    assert record["completion"]["run_ids"] == ["run-0", "run-1"]


def test_repairs_stop_at_the_admitted_limit_and_escalate(toy, tmp_path):
    budget = {"pool": "claude", "task_usd": 0.2, "max_calls": 3,
              "max_repair_rounds": 1, "wall_clock_s": 600}
    worker = FakeWorker(WRONG, WRONG)
    record = run(toy, tmp_path, worker, budget=budget)
    assert len(worker.calls) == 2
    assert record["escalation"]["reason"] == "repeated_failure"
    assert record["completion"]["proposed_disposition"] == "escalate"
    assert record["completion"]["predicates"]["P1"] == "unmet"
    assert record["resume"]["last_good_artifact"] == record["admission"]["base_revision"]
    assert record["resume"]["open_run_ids"] == []  # both calls answered
    assert record["completion"]["protected_targets_intact"] is True
    assert check_work_package.schema_errors(record) == []
    assert not any(g.startswith("record check") for g in record["completion"]["declared_gaps"])


def test_a_file_outside_the_write_targets_is_rejected_without_repair(toy, tmp_path):
    reply = GOOD + "\n<<<FILE tests/test_calc.py>>>\ndef test_triple():\n    pass\n<<<END FILE>>>"
    worker = FakeWorker(reply, GOOD)
    record = run(toy, tmp_path, worker)
    assert len(worker.calls) == 1
    assert record["completion"]["proposed_disposition"] == "reject"
    assert any("tests/test_calc.py" in f for f in record["completion"]["unresolved_findings"])


def test_a_truncated_reply_costs_a_round(toy, tmp_path):
    worker = FakeWorker(controller.WorkerResult("run-0", "<<<FILE src/toy/calc.py>>>\ndef", 3, ""),
                        GOOD)
    record = run(toy, tmp_path, worker)
    assert record["completion"]["proposed_disposition"] == "accept"
    assert record["execution"]["repair_rounds"] == 1
    assert "truncated" in worker.calls[1]["instruction"].lower()


def test_a_refused_call_escalates_with_its_reason(toy, tmp_path):
    refused = controller.WorkerResult("", "", 1, "task call limit reached: 3 of 3 calls")
    record = run(toy, tmp_path, FakeWorker(refused))
    assert record["escalation"]["reason"] == "budget_exhausted"
    assert record["completion"]["proposed_disposition"] == "escalate"


def test_an_oracle_that_already_passes_is_ambiguous(toy, tmp_path):
    write(toy, "src/toy/calc.py", CALC + "\n\ndef triple(x):\n    return 3 * x\n")
    git(toy, "commit", "-qam", "triple already exists")
    worker = FakeWorker()
    record = run(toy, tmp_path, worker)
    assert worker.calls == []
    assert record["escalation"]["reason"] == "ambiguity"
    assert "oracle" in record["escalation"]["detail"]


def test_an_oracle_that_cannot_run_is_not_a_failing_oracle(toy, tmp_path):
    checks = json.loads(package(toy, tmp_path).read_text(encoding="utf-8"))["admission"]["checks"]
    checks[0]["command"] = ".venv/Scripts/python.exe -m pytest tests/test_missing.py -q"
    worker = FakeWorker()
    record = run(toy, tmp_path, worker, checks=checks)
    assert worker.calls == []
    assert record["escalation"]["reason"] == "ambiguity"
    assert "could not run" in record["escalation"]["detail"]
    assert record["completion"]["check_results"] == []
    assert check_work_package.schema_errors(record) == []


def test_a_relative_out_dir_still_tests_the_worktree(toy, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    brief = tmp_path / "brief.txt"
    brief.write_text("Add triple(x).", encoding="utf-8")
    record = controller.run_package(package(toy, tmp_path).relative_to(tmp_path), brief,
                                    worker=FakeWorker(GOOD), repository=toy,
                                    venv_python=VENV_PYTHON, out_dir=Path("out"))
    assert record["completion"]["proposed_disposition"] == "accept"
    assert Path(record["execution"]["worktree"]).is_absolute()


def test_an_environment_mismatch_stops_before_any_call(toy, tmp_path):
    worker = FakeWorker()
    record = run(toy, tmp_path, worker, environment={
        "python": "2.7.18", "venv": ".venv", "dependency_sha256": "0" * 64})
    assert worker.calls == []
    assert record["escalation"]["reason"] == "environment_mismatch"


def test_fixtures_must_be_committed_in_the_base(toy, tmp_path):
    wp = package(toy, tmp_path)
    data = json.loads(wp.read_text(encoding="utf-8"))
    data["admission"]["protected_targets"][0]["sha256"] = "0" * 64
    wp.write_text(json.dumps(data), encoding="utf-8")
    brief = tmp_path / "brief.txt"
    brief.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit, match="committed in base_revision"):
        controller.run_package(wp, brief, worker=FakeWorker(), repository=toy,
                               venv_python=VENV_PYTHON, out_dir=tmp_path / "out")


def test_a_target_too_large_for_a_whole_file_reply_escalates_at_admission(toy, tmp_path):
    """E2' A0: hosts.py and app.py could not come back whole; refuse before any work."""
    worker = FakeWorker()
    brief = tmp_path / "brief.txt"
    brief.write_text("Add triple(x).", encoding="utf-8")
    record = controller.run_package(package(toy, tmp_path), brief, worker=worker, repository=toy,
                                    venv_python=VENV_PYTHON, out_dir=tmp_path / "out",
                                    max_reply_tokens=5)  # calc.py is about 11 tokens
    assert worker.calls == []
    assert record["escalation"]["reason"] == "scope_change"
    assert "src/toy/calc.py" in record["escalation"]["detail"]
    assert not (tmp_path / "out" / "worktree").exists()
    assert check_work_package.schema_errors(record) == []


def test_an_output_limit_above_the_runner_cap_is_refused_before_anything_runs(tmp_path):
    with pytest.raises(SystemExit, match="--max-output-tokens must be between 1 and 16384"):
        controller.main([str(tmp_path / "missing.json"), str(tmp_path / "brief.txt"),
                         "--model", "m", "--pool", "claude", "--total-budget-usd", "8",
                         "--max-output-tokens", "20000"])


def test_owner_host_packages_stay_lead_led(toy, tmp_path):
    with pytest.raises(SystemExit, match="lead-led"):
        run(toy, tmp_path, FakeWorker(), owner_host_gate=True)


def test_reply_parsing():
    files = controller.parse_files("intro\n<<<FILE a/b.py>>>\nx = 1\n<<<END FILE>>>\ntail")
    assert files == {"a/b.py": "x = 1\n"}
    assert controller.parse_files("no blocks") == {}
    # A worker that echoes the packet's <file path="..."> style is still in scope.
    assert controller.parse_files('<<<FILE path="a/b.py">>>\nx\n<<<END FILE>>>') == {"a/b.py": "x\n"}
    with pytest.raises(ValueError):
        controller.parse_files("<<<FILE a.py>>>\n1\n<<<END FILE>>>\n<<<FILE a.py>>>\n2\n<<<END FILE>>>")


def test_checks_must_use_the_venv():
    assert controller.venv_command(".venv\\Scripts\\python.exe -m pytest -q", VENV_PYTHON)[0] == str(VENV_PYTHON)
    with pytest.raises(ValueError):
        controller.venv_command("pytest -q", VENV_PYTHON)
