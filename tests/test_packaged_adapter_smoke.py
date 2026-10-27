"""Static contract for simultaneous packaged Browser and Cowork acceptance."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "smoke-packaged-adapters.ps1"
CI = ROOT / ".github" / "workflows" / "ci.yml"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
BROWSER = ROOT / "ui" / "packaged-smoke.mjs"


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_harness_uses_fresh_installed_artifacts_and_safe_zip_extraction() -> None:
    text = source()
    for parameter in ("$Python", "$Wheel", "$CoworkZip", "$WorkRoot"):
        assert parameter in text
    assert "WorkRoot must be outside the source checkout" in text
    assert 'start.Environment.Remove("PYTHONPATH")' in text
    assert 'start.Environment.Remove("PYTHONHOME")' in text
    assert '$install += "$WheelPath[mcp]"' in text
    assert "IO.Compression.ZipFile]::OpenRead" in text
    assert "Cowork ZIP entry escapes its extraction root" in text


def test_harness_drives_the_actual_manifest_command_inside_the_venv() -> None:
    text = source()
    assert 'Join-Path $PluginRoot ".mcp.json"' in text
    assert 'server.command -ne "resource-librarian"' in text
    assert '$declaredArgs[2] -ne "contribute"' in text
    assert "resolved = shutil.which(command or \"\")" in text
    assert "Path(resolved).resolve().parent != venv_scripts" in text
    assert "StdioServerParameters(command=command, args=args" in text
    assert 'await client.call_tool("vault_status", {})' in text


def test_browser_and_cowork_overlap_on_one_core_then_cleanup() -> None:
    text = source()
    ready = text.index("while (-not (Test-Path -LiteralPath $readyFile))")
    mcp = text.index('$mcpDriver = Join-Path $RunRoot "mcp_from_bundle.py"')
    release = text.index('[IO.File]::WriteAllText($releaseFile')
    assert ready < mcp < release
    assert "LIBRARIAN_PACKAGED_TOKEN" in text
    assert 'browserEvidence.post_release_api' in text
    assert '@($runningStatus.cores).Count -ne 1' in text
    assert 'host", "stop", "--vault", $VaultRoot, "--force"' in text
    assert "vault.lease.json" in text
    assert "Core discovery record remained after adapter smoke" in text


def test_browser_driver_is_checkout_independent_and_keeps_tokens_out_of_args() -> None:
    text = BROWSER.read_text(encoding="utf-8")
    assert "tests/ui_demo_core.py" not in text
    assert "process.env.PYTHONPATH" not in text
    assert "PYTHONPATH:" not in text
    assert 'process.env.LIBRARIAN_PACKAGED_TOKEN' in text
    assert 'args.has("token")' in text
    assert "delete process.env.LIBRARIAN_PACKAGED_TOKEN" in text
    assert 'page.waitForSelector("header nav[aria-label=\'Views\']")' in text
    assert 'new URL(response.url()).pathname === "/api/tool/search"' in text
    assert "atomicJson(readyFile, evidence)" in text
    assert "await waitForRelease(releaseFile, holdTimeout)" in text
    assert "evidence.post_release_api" in text


def test_workflows_gate_packaged_adapters_without_expanding_the_python_matrix() -> None:
    ci = CI.read_text(encoding="utf-8")
    release = RELEASE.read_text(encoding="utf-8")
    assert ci.count("smoke-packaged-adapters.ps1") == 1
    assert "adapter-release-out" in ci
    assert ci.index("Build Obsidian adapter from lockfile") < ci.index("smoke-packaged-adapters.ps1")
    assert release.count("smoke-packaged-adapters.ps1") == 2
    assert "librarian-candidate-packaged-adapters" in release
    assert "librarian-stable-packaged-adapters" in release
    stable = release[release.index("Smoke stable packaged adapters"):]
    assert "-Wheelhouse (Resolve-Path -LiteralPath release-out/wheelhouse).Path" in stable
