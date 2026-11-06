"""MF-043a-d: the CI and release workflows hold to their own rules.

The rules are stated in `.github/workflows/ci.yml`; this file is what makes them
binding. A change that breaks one fails here, before it reaches a hosted run.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
SHA_PIN = re.compile(r"^[\w.-]+/[\w.-]+(/[\w./-]+)?@[0-9a-f]{40}$")
EXACT = re.compile(r"^\d+\.\d+\.\d+$")
ATTEST = "actions/attest-build-provenance@"
JOB_SCOPES = {"contents": "read", "id-token": "write", "attestations": "write"}


def load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["on"] = data.pop(True, data.get("on"))          # YAML 1.1 reads `on` as true
    return data


def steps(workflow: dict):
    for job_name, job in workflow["jobs"].items():
        for step in job.get("steps", []):
            yield job_name, job, step


@pytest.fixture(params=WORKFLOWS, ids=lambda p: p.name)
def workflow(request):
    return request.param, load(request.param)


def test_both_workflows_are_checked():
    assert {p.name for p in WORKFLOWS} == {"ci.yml", "release.yml"}


def test_the_token_only_reads_except_where_artifacts_are_attested(workflow):
    _, data = workflow
    assert data["permissions"] == {"contents": "read"}
    for name, job in data["jobs"].items():
        scopes = job.get("permissions", {})
        assert all(JOB_SCOPES.get(key) == value for key, value in scopes.items()), (name, scopes)
        attests = any(str(step.get("uses", "")).startswith(ATTEST) for step in job.get("steps", []))
        if scopes.get("id-token") or scopes.get("attestations"):
            assert attests, f"{name} may write attestations but attests nothing"


def test_every_action_is_pinned_to_a_commit_and_says_which_release(workflow):
    path, data = workflow
    text = path.read_text(encoding="utf-8")
    for job, _, step in steps(data):
        uses = step.get("uses")
        if uses is None:
            continue
        assert SHA_PIN.match(uses), (job, uses)
        assert re.search(re.escape(uses) + r" # v\d+", text), f"{uses}: name its release in a comment"


def test_checkout_never_leaves_credentials_behind(workflow):
    _, data = workflow
    for job, _, step in steps(data):
        if str(step.get("uses", "")).startswith("actions/checkout@"):
            assert (step.get("with") or {}).get("persist-credentials") is False, job


def test_runners_and_toolchains_are_exact(workflow):
    _, data = workflow
    for name, job in data["jobs"].items():
        assert "latest" not in str(job["runs-on"]), name
        assert isinstance(job.get("timeout-minutes"), int), f"{name} has no timeout"
        matrix = (job.get("strategy") or {}).get("matrix") or {}
        for _, _, step in steps({"jobs": {name: job}}):
            uses = str(step.get("uses", ""))
            if uses.startswith("actions/setup-python@"):
                wanted = str(step["with"]["python-version"])
                versions = matrix["python"] if "matrix.python" in wanted else [wanted]
                assert all(EXACT.match(str(v)) for v in versions), (name, versions)
            if uses.startswith("actions/setup-node@"):
                assert EXACT.match(str(step["with"]["node-version"])), name


def test_no_expression_is_pasted_into_a_script(workflow):
    _, data = workflow
    for job, _, step in steps(data):
        assert "${{" not in str(step.get("run", "")), f"{job}: {step.get('name')}"


def test_every_python_install_is_hash_locked_and_every_build_uses_the_locked_tools(workflow):
    _, data = workflow
    for job, _, step in steps(data):
        script = str(step.get("run", ""))
        for line in script.splitlines():
            if "pip install" in line:
                assert ("--require-hashes -r requirements-" in line or "--no-deps" in line), (job, line)
            if "-m build" in line:
                assert "--no-isolation" in line, (job, line)
            if "build-release.ps1" in line:
                assert "-NoBuildIsolation" in script, (job, line)


def test_the_core_suite_keeps_its_evidence_whatever_the_outcome():
    data = load(ROOT / ".github" / "workflows" / "ci.yml")
    core = data["jobs"]["core"]
    run = " ".join(str(step.get("run", "")) for step in core["steps"])
    assert "--junitxml" in run and "pip freeze" in run
    upload = next(step for step in core["steps"]
                  if str(step.get("uses", "")).startswith("actions/upload-artifact@"))
    assert upload["if"] == "always()" and int(upload["with"]["retention-days"]) >= 30


def test_dispatch_inputs_reach_scripts_only_as_checked_environment_variables():
    data = load(ROOT / ".github" / "workflows" / "release.yml")
    stable = data["jobs"]["stable"]
    names = {"RELEASE_LEADS", "REQUIREMENTS_LOCK", "WHEELHOUSE"}
    assert set(stable["env"]) >= names
    assert all(str(stable["env"][n]).startswith("${{ inputs.") for n in names)
    titles = [step.get("name", "") for step in stable["steps"]]
    check = titles.index("Check the release inputs are repository paths")
    build = titles.index("Build evidence-backed stable bundle")
    assert check < build
    guard = stable["steps"][check]["run"]
    assert all(name in guard for name in names) and r"\.\." in guard


def test_release_artifacts_are_attested_then_verified():
    data = load(ROOT / ".github" / "workflows" / "release.yml")
    for name in ("candidate", "stable"):
        titles = [step.get("name", "") for step in data["jobs"][name]["steps"]]
        sbom = titles.index("Software bill of materials")
        attest = titles.index("Attest build provenance")
        verify = titles.index("Verify the attestations")
        assert sbom < attest < verify, name
        subjects = data["jobs"][name]["steps"][attest]["with"]["subject-path"]
        assert "release-out/sbom.cdx.json" in subjects and "release-out/core/*.whl" in subjects
        assert "gh attestation verify" in data["jobs"][name]["steps"][verify]["run"]


# -- MF-043b: the locks themselves ------------------------------------------------

def pins(name: str) -> dict[str, str]:
    text = (ROOT / name).read_text(encoding="utf-8")
    entries = re.findall(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==(\S+) \\\n((?:    --hash=sha256:[0-9a-f]{64}(?: \\)?\n)+)",
                         text, flags=re.M)
    requirement_lines = [line for line in text.splitlines() if line and not line.startswith((" ", "#"))]
    assert len(entries) == len(requirement_lines), f"{name}: every requirement is pinned with hashes"
    return {canonicalize_name(n): v for n, v, _ in entries}


def test_the_dev_lock_pins_everything_the_project_declares():
    import tomllib
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    declared = [*project["dependencies"], *project["optional-dependencies"]["dev"],
                *[line for line in (ROOT / "requirements-build.in").read_text(encoding="utf-8").splitlines()
                  if line and not line.startswith("#")]]
    locked = pins("requirements-dev.txt")
    for spec in declared:
        requirement = Requirement(spec)
        name = canonicalize_name(requirement.name)
        assert name in locked, f"{requirement.name} is not in requirements-dev.txt"
        assert requirement.specifier.contains(locked[name], prereleases=True), (spec, locked[name])


def test_the_build_lock_agrees_with_the_dev_lock():
    build, dev = pins("requirements-build.txt"), pins("requirements-dev.txt")
    assert {"build", "setuptools", "wheel"} <= set(build)
    assert {name: dev.get(name) for name in build} == build
