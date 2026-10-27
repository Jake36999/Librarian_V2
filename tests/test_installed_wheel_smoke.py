"""Contract for the clean installed-wheel acceptance harness.

The end-to-end script runs in release CI because it creates a venv and installs
dependencies.  These fast tests keep its important isolation and lifecycle
properties in the default source suite.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "smoke-installed-wheel.ps1"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_smoke_requires_an_exact_wheel_and_fresh_external_work_root() -> None:
    text = source()
    assert "[string]$Python" in text
    assert "[string]$Wheel" in text
    assert "[string]$WorkRoot" in text
    assert 'GetExtension($WheelPath) -ne ".whl"' in text
    assert "WorkRoot must be outside the source checkout" in text
    assert "WorkRoot must be fresh and must not already exist" in text


def test_every_installed_process_isolated_from_the_checkout() -> None:
    text = source()
    assert 'start.Environment.Remove("PYTHONPATH")' in text
    assert 'start.Environment.Remove("PYTHONHOME")' in text
    assert 'package imported outside isolated venv' in text
    assert 'distribution("resource-librarian")' in text
    assert '$install += "$WheelPath[mcp]"' in text
    assert "pip install -e" not in text


def test_smoke_checks_packaged_resources_and_both_console_scripts() -> None:
    text = source()
    for resource in (
        "ui/index.html",
        "ui/app.js",
        "ui/app.css",
        "standard/model_expectations/core.json",
        "standard/service_expectations/core.json",
    ):
        assert resource in text
    assert 'Scripts\\librarian.exe' in text
    assert 'Scripts\\resource-librarian.exe' in text


def test_smoke_uses_the_installed_host_and_real_mcp_protocol() -> None:
    text = source()
    assert '@("host", "start", "--vault", $VaultRoot)' in text
    assert 'Invoke-WebRequest -Uri "$BaseUrl/app.js"' in text
    assert 'Invoke-WebRequest -Uri "$BaseUrl/api/meta"' in text
    assert "from mcp import Client, StdioServerParameters" in text
    assert 'await client.call_tool("vault_status", {})' in text
    assert '@("host", "stop", "--vault", $VaultRoot)' in text


def test_smoke_has_offline_dependencies_and_failure_cleanup() -> None:
    text = source()
    assert "[string]$Wheelhouse" in text
    assert '@("--no-index", "--find-links", $Wheelhouse)' in text
    assert "finally {" in text
    assert '@("host", "stop", "--vault", $VaultRoot, "--force")' in text
    start_returned = text.index('$startedResult = Invoke-Isolated -FilePath $Librarian')
    cleanup_armed = text.index('$HostStarted = $true', start_returned)
    response_parsed = text.index('$started = Convert-CommandJson', start_returned)
    assert cleanup_armed < response_parsed
    assert "vault.lease.json" in text
    assert "Core discovery record remained after clean shutdown" in text


def test_supported_python_and_release_workflows_run_the_artifact_smoke() -> None:
    ci = CI_WORKFLOW.read_text(encoding="utf-8")
    release = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "wheel-smoke:" in ci
    assert 'python: ["3.11", "3.12", "3.13"]' in ci
    assert "python -m build --wheel --outdir wheel-out ." in ci
    assert "./scripts/smoke-installed-wheel.ps1" in ci

    assert release.count("./scripts/smoke-installed-wheel.ps1") == 2
    assert "Smoke candidate Core wheel" in release
    assert "Smoke stable Core wheel before signing" in release
    assert "-Wheelhouse (Resolve-Path -LiteralPath release-out/wheelhouse).Path" in release
    assert release.index("Smoke stable Core wheel before signing") < release.index(
        "Import protected signing certificate"
    )
