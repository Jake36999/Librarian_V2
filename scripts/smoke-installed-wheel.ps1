<#
.SYNOPSIS
    Accepts a Librarian wheel from a clean, installed environment.

.DESCRIPTION
    Creates a fresh virtual environment outside the source checkout, installs
    the exact wheel with its MCP extra, and exercises the installed console
    scripts, packaged resources, Host-served UI/API, and MCP stdio adapter.
    PYTHONPATH and PYTHONHOME are removed from every child process so a source
    checkout cannot make a broken wheel appear healthy.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Python,
    [Parameter(Mandatory = $true)]
    [string]$Wheel,
    [Parameter(Mandatory = $true)]
    [string]$WorkRoot,
    # Stable-release jobs can supply their reviewed offline dependency set.
    # Candidate/CI jobs may omit it and use pip's configured package index.
    [string]$Wheelhouse = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$WheelPath = [IO.Path]::GetFullPath($Wheel)
$SmokeRoot = [IO.Path]::GetFullPath($WorkRoot)

function Test-Inside([string]$Path, [string]$Root) {
    $fullPath = [IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
    $fullRoot = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    return $fullPath.Equals($fullRoot, [StringComparison]::OrdinalIgnoreCase) -or
        $fullPath.StartsWith($fullRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase)
}

function Invoke-Isolated {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @(),
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [hashtable]$Environment = @{},
        [int]$TimeoutSeconds = 300,
        [switch]$AllowFailure
    )

    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $FilePath
    $start.WorkingDirectory = $WorkingDirectory
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    foreach ($argument in $Arguments) { [void]$start.ArgumentList.Add($argument) }
    # These are removed even when absent. A caller's editable checkout must
    # never satisfy an import made by the supposedly isolated installation.
    [void]$start.Environment.Remove("PYTHONPATH")
    [void]$start.Environment.Remove("PYTHONHOME")
    foreach ($entry in $Environment.GetEnumerator()) {
        $start.Environment[[string]$entry.Key] = [string]$entry.Value
    }

    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $start
    if (-not $process.Start()) { throw "Could not start $FilePath" }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    try {
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            $process.Kill($true)
            throw "$FilePath timed out after $TimeoutSeconds seconds"
        }
        $stdoutTask.Wait()
        $stderrTask.Wait()
        $result = [pscustomobject]@{
            ExitCode = $process.ExitCode
            Stdout = $stdoutTask.Result
            Stderr = $stderrTask.Result
        }
        if (-not $AllowFailure -and $result.ExitCode -ne 0) {
            throw "$FilePath failed with exit $($result.ExitCode).`nstdout:`n$($result.Stdout)`nstderr:`n$($result.Stderr)"
        }
        return $result
    } finally {
        $process.Dispose()
    }
}

function Convert-CommandJson($Result, [string]$Description) {
    try {
        return $Result.Stdout | ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw "$Description did not return JSON.`nstdout:`n$($Result.Stdout)`nstderr:`n$($Result.Stderr)"
    }
}

if (-not (Test-Path -LiteralPath $WheelPath -PathType Leaf) -or
    [IO.Path]::GetExtension($WheelPath) -ne ".whl") {
    throw "Wheel must name an existing .whl file: $WheelPath"
}
if (Test-Inside $SmokeRoot $RepoRoot) {
    throw "WorkRoot must be outside the source checkout: $SmokeRoot"
}
if (Test-Path -LiteralPath $SmokeRoot) {
    throw "WorkRoot must be fresh and must not already exist: $SmokeRoot"
}
if ($Wheelhouse) {
    $Wheelhouse = [IO.Path]::GetFullPath($Wheelhouse)
    if (-not (Test-Path -LiteralPath $Wheelhouse -PathType Container)) {
        throw "Wheelhouse must name an existing directory: $Wheelhouse"
    }
}

New-Item -ItemType Directory -Path $SmokeRoot | Out-Null
$RunRoot = Join-Path $SmokeRoot "run"
$VenvRoot = Join-Path $SmokeRoot "venv"
$ConfigRoot = Join-Path $SmokeRoot "config"
$VaultRoot = Join-Path $SmokeRoot "vault"
New-Item -ItemType Directory -Path $RunRoot, $ConfigRoot | Out-Null

Write-Host "== Create isolated virtual environment" -ForegroundColor Cyan
Invoke-Isolated -FilePath $Python -Arguments @("-m", "venv", $VenvRoot) `
    -WorkingDirectory $RunRoot -TimeoutSeconds 180 | Out-Null

$VenvPython = Join-Path $VenvRoot "Scripts\python.exe"
$Librarian = Join-Path $VenvRoot "Scripts\librarian.exe"
$ResourceLibrarian = Join-Path $VenvRoot "Scripts\resource-librarian.exe"
if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    throw "Virtual environment did not create its Python executable: $VenvPython"
}

Write-Host "== Install the exact wheel with the MCP extra" -ForegroundColor Cyan
$install = @("-m", "pip", "install", "--disable-pip-version-check")
if ($Wheelhouse) { $install += @("--no-index", "--find-links", $Wheelhouse) }
$install += "$WheelPath[mcp]"
Invoke-Isolated -FilePath $VenvPython -Arguments $install -WorkingDirectory $RunRoot `
    -TimeoutSeconds 600 | Out-Null

foreach ($command in @($Librarian, $ResourceLibrarian)) {
    if (-not (Test-Path -LiteralPath $command -PathType Leaf)) {
        throw "Installed console script is missing: $command"
    }
    Invoke-Isolated -FilePath $command -Arguments @("--help") -WorkingDirectory $RunRoot | Out-Null
}

$verifyDriver = Join-Path $RunRoot "verify_install.py"
$verifySource = @'
import json
import sys
from importlib.metadata import distribution
from importlib.resources import files
from pathlib import Path

import resource_librarian

package_file = Path(resource_librarian.__file__).resolve()
prefix = Path(sys.prefix).resolve()
try:
    package_file.relative_to(prefix)
except ValueError as exc:
    raise SystemExit(f"package imported outside isolated venv: {package_file}") from exc

dist = distribution("resource-librarian")
if dist.version != resource_librarian.__version__:
    raise SystemExit(f"distribution/package version mismatch: {dist.version} != {resource_librarian.__version__}")

required = (
    "ui/index.html",
    "ui/app.js",
    "ui/app.css",
    "standard/model_expectations/core.json",
    "standard/service_expectations/core.json",
)
root = files("resource_librarian")
missing = [name for name in required if not root.joinpath(*name.split("/")).is_file()]
if missing:
    raise SystemExit("wheel is missing packaged resources: " + ", ".join(missing))
print(json.dumps({"package_file": str(package_file), "version": dist.version, "resources": list(required)}))
'@
[IO.File]::WriteAllText($verifyDriver, $verifySource, [Text.UTF8Encoding]::new($false))
$verified = Invoke-Isolated -FilePath $VenvPython -Arguments @($verifyDriver) -WorkingDirectory $RunRoot
$installEvidence = Convert-CommandJson $verified "Installed-package verification"
if (-not (Test-Inside ([string]$installEvidence.package_file) $VenvRoot)) {
    throw "Installed-package probe imported outside the isolated venv: $($installEvidence.package_file)"
}

$runtimeEnvironment = @{
    LIBRARIAN_CONFIG_DIR = $ConfigRoot
    LIBRARIAN_VAULT = $VaultRoot
}

Write-Host "== Initialise vault through the installed console script" -ForegroundColor Cyan
$initialised = Invoke-Isolated -FilePath $Librarian `
    -Arguments @("init", $VaultRoot, "--name", "Installed Wheel Smoke") `
    -WorkingDirectory $RunRoot -Environment $runtimeEnvironment
[void](Convert-CommandJson $initialised "Installed librarian init")

$HostStarted = $false
try {
    Write-Host "== Start the installed Host Core on a dynamic port" -ForegroundColor Cyan
    $startedResult = Invoke-Isolated -FilePath $Librarian `
        -Arguments @("host", "start", "--vault", $VaultRoot) `
        -WorkingDirectory $RunRoot -Environment $runtimeEnvironment -TimeoutSeconds 60
    # A zero-exit Host start may already have launched the background Core.
    # Arm cleanup before parsing or asserting anything about its response.
    $HostStarted = $true
    $started = Convert-CommandJson $startedResult "Installed librarian host start"
    if (-not $started.started -or $started.status -ne "running") {
        throw "Installed Host did not report a fresh running Core: $($startedResult.Stdout)"
    }
    $BaseUrl = ([string]$started.process.url).TrimEnd('/')
    if ($BaseUrl -notmatch '^http://127\.0\.0\.1:\d+$') {
        throw "Installed Host did not publish a loopback dynamic port: $BaseUrl"
    }

    $recordPath = Get-ChildItem -LiteralPath (Join-Path $ConfigRoot "cores") `
        -Filter "*.json" -File | Select-Object -First 1
    if (-not $recordPath) { throw "Installed Core did not publish its private discovery record" }
    $record = Get-Content -LiteralPath $recordPath.FullName -Raw | ConvertFrom-Json
    if (([string]$record.url).TrimEnd('/') -ne $BaseUrl -or -not $record.token) {
        throw "Installed Core discovery record does not match the Host result"
    }

    Write-Host "== Exercise packaged UI and authenticated read-only API" -ForegroundColor Cyan
    $index = Invoke-WebRequest -Uri "$BaseUrl/" -UseBasicParsing -TimeoutSec 30
    $javascript = Invoke-WebRequest -Uri "$BaseUrl/app.js" -UseBasicParsing -TimeoutSec 30
    $stylesheet = Invoke-WebRequest -Uri "$BaseUrl/app.css" -UseBasicParsing -TimeoutSec 30
    if ($index.StatusCode -ne 200 -or $index.Content -notmatch 'app\.js') {
        throw "Installed Core did not serve the packaged UI entry point"
    }
    if ($javascript.StatusCode -ne 200 -or $javascript.RawContentLength -lt 1000) {
        throw "Installed Core did not serve the packaged JavaScript bundle"
    }
    if ($stylesheet.StatusCode -ne 200 -or $stylesheet.RawContentLength -lt 100) {
        throw "Installed Core did not serve the packaged stylesheet"
    }
    $headers = @{
        "X-Librarian-Token" = [string]$record.token
        "Origin" = $BaseUrl
    }
    $metaResponse = Invoke-WebRequest -Uri "$BaseUrl/api/meta" -UseBasicParsing `
        -Headers $headers -TimeoutSec 30
    $meta = $metaResponse.Content | ConvertFrom-Json
    if (-not $meta.core_version -or -not $meta.protocol_version -or
        $meta.non_secret_health.vault_lease -ne "held" -or
        $meta.non_secret_health.writer -ne "ready") {
        throw "Installed Core metadata did not report a healthy coordinated runtime"
    }

    $mcpDriver = Join-Path $RunRoot "mcp_smoke.py"
    $mcpSource = @'
import json
import os
import sys
from pathlib import Path

import anyio
from mcp import Client, StdioServerParameters


async def main():
    expected = Path(os.environ["LIBRARIAN_VAULT"]).resolve()
    params = StdioServerParameters(
        command=sys.argv[1],
        args=["mcp", "--tier", "contribute"],
        env=dict(os.environ),
    )
    async with Client(params) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}
        if "vault_status" not in names:
            raise RuntimeError("installed MCP server did not list vault_status")
        result = await client.call_tool("vault_status", {})
        payload = result.structured_content
        if not isinstance(payload, dict) or Path(payload.get("vault", "")).resolve() != expected:
            raise RuntimeError(f"installed MCP call did not reach the live Core: {payload!r}")
        print(json.dumps({"tool_count": len(names), "vault": str(expected)}))


anyio.run(main)
'@
    [IO.File]::WriteAllText($mcpDriver, $mcpSource, [Text.UTF8Encoding]::new($false))
    Write-Host "== Exercise installed MCP stdio against the live Core" -ForegroundColor Cyan
    $mcpResult = Invoke-Isolated -FilePath $VenvPython `
        -Arguments @($mcpDriver, $ResourceLibrarian) -WorkingDirectory $RunRoot `
        -Environment $runtimeEnvironment -TimeoutSeconds 120
    $mcpEvidence = Convert-CommandJson $mcpResult "Installed MCP smoke"
    if ([int]$mcpEvidence.tool_count -lt 1) { throw "Installed MCP server listed no tools" }

    Write-Host "== Stop the installed Host Core cleanly" -ForegroundColor Cyan
    $stopResult = Invoke-Isolated -FilePath $Librarian `
        -Arguments @("host", "stop", "--vault", $VaultRoot) `
        -WorkingDirectory $RunRoot -Environment $runtimeEnvironment -TimeoutSeconds 60
    $stopped = Convert-CommandJson $stopResult "Installed librarian host stop"
    if (-not $stopped.stopped) { throw "Installed Host did not stop cleanly: $($stopResult.Stdout)" }
    $HostStarted = $false
} finally {
    if ($HostStarted) {
        # A failed assertion must not leak a Core into later matrix jobs.
        try {
            Invoke-Isolated -FilePath $Librarian `
                -Arguments @("host", "stop", "--vault", $VaultRoot, "--force") `
                -WorkingDirectory $RunRoot -Environment $runtimeEnvironment `
                -TimeoutSeconds 60 -AllowFailure | Out-Null
        } catch {
            Write-Warning "Emergency Host cleanup failed: $_"
        }
    }
}

$statusResult = Invoke-Isolated -FilePath $Librarian -Arguments @("host", "status") `
    -WorkingDirectory $RunRoot -Environment $runtimeEnvironment
$status = Convert-CommandJson $statusResult "Installed librarian host status"
if ($status.status -ne "stopped" -or @($status.cores).Count -ne 0) {
    throw "Installed Host still reports a live Core after shutdown: $($statusResult.Stdout)"
}
$leaseInfo = Join-Path $VaultRoot ".librarian\runtime\vault.lease.json"
if (Test-Path -LiteralPath $leaseInfo) { throw "Vault lease metadata remained after clean shutdown" }
$connectionRecords = @(Get-ChildItem -LiteralPath (Join-Path $ConfigRoot "cores") `
    -Filter "*.json" -File -ErrorAction SilentlyContinue)
if ($connectionRecords.Count -ne 0) { throw "Core discovery record remained after clean shutdown" }

Write-Host "Installed-wheel smoke passed: $($installEvidence.version), $($mcpEvidence.tool_count) MCP tools." -ForegroundColor Green
