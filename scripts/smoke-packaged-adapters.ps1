<#
.SYNOPSIS
    Accepts the packaged Browser and Cowork adapter paths against one installed Core.

.DESCRIPTION
    Installs an exact wheel into a fresh external virtual environment, unpacks
    the actual Cowork ZIP with traversal checks, and launches its declared MCP
    command while a real Edge/Chrome page remains connected to the same Core.
    This is packaged-protocol evidence; it does not impersonate the Claude UI.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Python,
    [Parameter(Mandatory = $true)][string]$Wheel,
    [Parameter(Mandatory = $true)][string]$CoworkZip,
    [Parameter(Mandatory = $true)][string]$WorkRoot,
    [string]$Wheelhouse = "",
    [string]$Browser = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$WheelPath = [IO.Path]::GetFullPath($Wheel)
$CoworkZipPath = [IO.Path]::GetFullPath($CoworkZip)
$SmokeRoot = [IO.Path]::GetFullPath($WorkRoot)

function Test-Inside([string]$Path, [string]$Root) {
    $fullPath = [IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
    $fullRoot = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    return $fullPath.Equals($fullRoot, [StringComparison]::OrdinalIgnoreCase) -or
        $fullPath.StartsWith($fullRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase)
}

function New-IsolatedStartInfo {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @(),
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [hashtable]$Environment = @{}
    )
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $FilePath
    $start.WorkingDirectory = $WorkingDirectory
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    foreach ($argument in $Arguments) { [void]$start.ArgumentList.Add($argument) }
    [void]$start.Environment.Remove("PYTHONPATH")
    [void]$start.Environment.Remove("PYTHONHOME")
    foreach ($entry in $Environment.GetEnumerator()) {
        $start.Environment[[string]$entry.Key] = [string]$entry.Value
    }
    return $start
}

function Start-IsolatedProcess {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @(),
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [hashtable]$Environment = @{}
    )
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = New-IsolatedStartInfo -FilePath $FilePath -Arguments $Arguments `
        -WorkingDirectory $WorkingDirectory -Environment $Environment
    if (-not $process.Start()) { throw "Could not start $FilePath" }
    return [pscustomobject]@{
        Process = $process
        Stdout = $process.StandardOutput.ReadToEndAsync()
        Stderr = $process.StandardError.ReadToEndAsync()
    }
}

function Wait-IsolatedProcess {
    param(
        [Parameter(Mandatory = $true)]$Running,
        [int]$TimeoutSeconds = 300,
        [switch]$AllowFailure
    )
    $process = $Running.Process
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        $process.Kill($true)
        throw "$($process.StartInfo.FileName) timed out after $TimeoutSeconds seconds"
    }
    $Running.Stdout.Wait()
    $Running.Stderr.Wait()
    $result = [pscustomobject]@{
        ExitCode = $process.ExitCode
        Stdout = $Running.Stdout.Result
        Stderr = $Running.Stderr.Result
    }
    if (-not $AllowFailure -and $result.ExitCode -ne 0) {
        throw "$($process.StartInfo.FileName) failed with exit $($result.ExitCode).`nstdout:`n$($result.Stdout)`nstderr:`n$($result.Stderr)"
    }
    return $result
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
    $running = Start-IsolatedProcess -FilePath $FilePath -Arguments $Arguments `
        -WorkingDirectory $WorkingDirectory -Environment $Environment
    try {
        return Wait-IsolatedProcess -Running $running -TimeoutSeconds $TimeoutSeconds `
            -AllowFailure:$AllowFailure
    } finally {
        $running.Process.Dispose()
    }
}

function Convert-CommandJson($Result, [string]$Description) {
    try { return $Result.Stdout | ConvertFrom-Json -ErrorAction Stop }
    catch { throw "$Description did not return JSON.`nstdout:`n$($Result.Stdout)`nstderr:`n$($Result.Stderr)" }
}

function Expand-SafeZip([string]$ArchivePath, [string]$Destination) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    New-Item -ItemType Directory -Path $Destination | Out-Null
    $archive = [IO.Compression.ZipFile]::OpenRead($ArchivePath)
    try {
        foreach ($entry in $archive.Entries) {
            $target = [IO.Path]::GetFullPath((Join-Path $Destination $entry.FullName))
            if (-not (Test-Inside $target $Destination)) {
                throw "Cowork ZIP entry escapes its extraction root: $($entry.FullName)"
            }
            if ([string]::IsNullOrEmpty($entry.Name)) {
                New-Item -ItemType Directory -Force -Path $target | Out-Null
                continue
            }
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
            $input = $entry.Open()
            $output = [IO.File]::Open($target, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
            try { $input.CopyTo($output) }
            finally { $output.Dispose(); $input.Dispose() }
        }
    } finally { $archive.Dispose() }
}

foreach ($artifact in @(@($WheelPath, ".whl", "Wheel"), @($CoworkZipPath, ".zip", "CoworkZip"))) {
    if (-not (Test-Path -LiteralPath $artifact[0] -PathType Leaf) -or
        [IO.Path]::GetExtension($artifact[0]) -ne $artifact[1]) {
        throw "$($artifact[2]) must name an existing $($artifact[1]) file: $($artifact[0])"
    }
}
if (Test-Inside $SmokeRoot $RepoRoot) { throw "WorkRoot must be outside the source checkout: $SmokeRoot" }
if (Test-Path -LiteralPath $SmokeRoot) { throw "WorkRoot must be fresh: $SmokeRoot" }
if ($Wheelhouse) {
    $Wheelhouse = [IO.Path]::GetFullPath($Wheelhouse)
    if (-not (Test-Path -LiteralPath $Wheelhouse -PathType Container)) {
        throw "Wheelhouse must name an existing directory: $Wheelhouse"
    }
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js is required for packaged Browser smoke" }
$BrowserDriver = Join-Path $RepoRoot "ui\packaged-smoke.mjs"
if (-not (Test-Path -LiteralPath $BrowserDriver -PathType Leaf)) { throw "Packaged Browser driver is missing" }

New-Item -ItemType Directory -Path $SmokeRoot | Out-Null
$RunRoot = Join-Path $SmokeRoot "run"
$VenvRoot = Join-Path $SmokeRoot "venv"
$ConfigRoot = Join-Path $SmokeRoot "config"
$VaultRoot = Join-Path $SmokeRoot "vault"
$PluginRoot = Join-Path $SmokeRoot "cowork"
New-Item -ItemType Directory -Path $RunRoot, $ConfigRoot | Out-Null

Write-Host "== Create isolated environment and install exact wheel" -ForegroundColor Cyan
Invoke-Isolated -FilePath $Python -Arguments @("-m", "venv", $VenvRoot) `
    -WorkingDirectory $RunRoot -TimeoutSeconds 180 | Out-Null
$VenvPython = Join-Path $VenvRoot "Scripts\python.exe"
$Librarian = Join-Path $VenvRoot "Scripts\librarian.exe"
$VenvScripts = Join-Path $VenvRoot "Scripts"
$install = @("-m", "pip", "install", "--disable-pip-version-check")
if ($Wheelhouse) { $install += @("--no-index", "--find-links", $Wheelhouse) }
$install += "$WheelPath[mcp]"
Invoke-Isolated -FilePath $VenvPython -Arguments $install -WorkingDirectory $RunRoot `
    -TimeoutSeconds 600 | Out-Null
if (-not (Test-Path -LiteralPath $Librarian -PathType Leaf)) { throw "Installed librarian console script is missing" }

Write-Host "== Extract and validate actual Cowork bundle" -ForegroundColor Cyan
Expand-SafeZip $CoworkZipPath $PluginRoot
$ManifestPath = Join-Path $PluginRoot ".mcp.json"
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { throw "Cowork ZIP has no root .mcp.json" }
$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$servers = @($manifest.mcpServers.PSObject.Properties)
if ($servers.Count -ne 1 -or $servers[0].Name -ne "librarian") {
    throw "Cowork bundle must declare exactly the librarian MCP server"
}
$server = $servers[0].Value
$declaredArgs = @($server.args | ForEach-Object { [string]$_ })
if ([string]$server.command -ne "resource-librarian" -or
    $declaredArgs.Count -ne 3 -or $declaredArgs[0] -ne "mcp" -or
    $declaredArgs[1] -ne "--tier" -or $declaredArgs[2] -ne "contribute") {
    throw "Cowork bundle declares an unexpected Librarian command"
}

$runtimeEnvironment = @{
    LIBRARIAN_CONFIG_DIR = $ConfigRoot
    LIBRARIAN_VAULT = $VaultRoot
    PATH = "$VenvScripts$([IO.Path]::PathSeparator)$env:PATH"
}
Invoke-Isolated -FilePath $Librarian -Arguments @("init", $VaultRoot, "--name", "Packaged Adapter Smoke") `
    -WorkingDirectory $RunRoot -Environment $runtimeEnvironment | Out-Null

$HostStarted = $false
$BrowserRunning = $null
$BrowserReleased = $false
try {
    Write-Host "== Start one installed Host Core" -ForegroundColor Cyan
    $startedResult = Invoke-Isolated -FilePath $Librarian `
        -Arguments @("host", "start", "--vault", $VaultRoot) `
        -WorkingDirectory $RunRoot -Environment $runtimeEnvironment -TimeoutSeconds 60
    $HostStarted = $true
    $started = Convert-CommandJson $startedResult "Installed librarian host start"
    if (-not $started.started -or $started.status -ne "running") { throw "Host did not start freshly" }
    $BaseUrl = ([string]$started.process.url).TrimEnd('/')
    $records = @(Get-ChildItem -LiteralPath (Join-Path $ConfigRoot "cores") -Filter "*.json" -File)
    if ($records.Count -ne 1) { throw "Expected exactly one installed Core discovery record" }
    $record = Get-Content -LiteralPath $records[0].FullName -Raw | ConvertFrom-Json
    if (([string]$record.url).TrimEnd('/') -ne $BaseUrl -or -not $record.token) {
        throw "Installed Core discovery record does not match Host start"
    }

    Write-Host "== Keep a real packaged Browser connected" -ForegroundColor Cyan
    $readyFile = Join-Path $RunRoot "browser-ready.json"
    $releaseFile = Join-Path $RunRoot "browser-release"
    $browserArgs = @($BrowserDriver, "--ready-file", $readyFile,
        "--release-file", $releaseFile, "--hold-timeout", "180")
    if ($Browser) { $browserArgs += @("--browser", [IO.Path]::GetFullPath($Browser)) }
    $browserEnvironment = @{
        LIBRARIAN_PACKAGED_URL = $BaseUrl
        LIBRARIAN_PACKAGED_TOKEN = [string]$record.token
    }
    $BrowserRunning = Start-IsolatedProcess -FilePath "node" -Arguments $browserArgs `
        -WorkingDirectory (Join-Path $RepoRoot "ui") -Environment $browserEnvironment
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    while (-not (Test-Path -LiteralPath $readyFile)) {
        if ($BrowserRunning.Process.HasExited) {
            $failed = Wait-IsolatedProcess -Running $BrowserRunning -AllowFailure
            throw "Packaged Browser exited before readiness.`nstdout:`n$($failed.Stdout)`nstderr:`n$($failed.Stderr)"
        }
        if ([DateTime]::UtcNow -ge $deadline) { throw "Packaged Browser did not become ready within 60 seconds" }
        Start-Sleep -Milliseconds 200
    }
    $browserReady = Get-Content -LiteralPath $readyFile -Raw | ConvertFrom-Json
    if (-not $browserReady.title -or -not $browserReady.browser) { throw "Packaged Browser readiness evidence is incomplete" }

    Write-Host "== Drive the command declared by the packaged Cowork plugin" -ForegroundColor Cyan
    $mcpDriver = Join-Path $RunRoot "mcp_from_bundle.py"
    $mcpSource = @'
import json
import os
import shutil
import sys
from pathlib import Path

import anyio
from mcp import Client, StdioServerParameters


async def main():
    manifest_path = Path(sys.argv[1]).resolve()
    venv_scripts = Path(sys.argv[2]).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    servers = manifest.get("mcpServers")
    if not isinstance(servers, dict) or list(servers) != ["librarian"]:
        raise RuntimeError("packaged manifest must contain exactly librarian")
    server = servers["librarian"]
    command = server.get("command")
    args = server.get("args")
    resolved = shutil.which(command or "")
    if not resolved or Path(resolved).resolve().parent != venv_scripts:
        raise RuntimeError(f"packaged command did not resolve inside venv: {resolved!r}")
    params = StdioServerParameters(command=command, args=args, env=dict(os.environ))
    async with Client(params) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}
        if "vault_status" not in names:
            raise RuntimeError("packaged Cowork server did not list vault_status")
        result = await client.call_tool("vault_status", {})
        payload = result.structured_content
        expected = Path(os.environ["LIBRARIAN_VAULT"]).resolve()
        if not isinstance(payload, dict) or Path(payload.get("vault", "")).resolve() != expected:
            raise RuntimeError(f"packaged Cowork call missed live Core: {payload!r}")
        print(json.dumps({"command": command, "resolved": resolved,
                          "tool_count": len(names), "vault": str(expected)}))


anyio.run(main)
'@
    [IO.File]::WriteAllText($mcpDriver, $mcpSource, [Text.UTF8Encoding]::new($false))
    $mcpResult = Invoke-Isolated -FilePath $VenvPython `
        -Arguments @($mcpDriver, $ManifestPath, $VenvScripts) -WorkingDirectory $RunRoot `
        -Environment $runtimeEnvironment -TimeoutSeconds 120
    $mcpEvidence = Convert-CommandJson $mcpResult "Packaged Cowork MCP smoke"
    if ([int]$mcpEvidence.tool_count -lt 1) { throw "Packaged Cowork listed no tools" }

    Write-Host "== Release Browser after simultaneous MCP operation" -ForegroundColor Cyan
    [IO.File]::WriteAllText($releaseFile, "release`n", [Text.UTF8Encoding]::new($false))
    $BrowserReleased = $true
    $browserResult = Wait-IsolatedProcess -Running $BrowserRunning -TimeoutSeconds 60
    $browserEvidence = $browserResult.Stdout.Trim() | ConvertFrom-Json
    if (-not $browserEvidence.post_release_api) { throw "Browser did not recheck the live Core after MCP" }
    $BrowserRunning.Process.Dispose()
    $BrowserRunning = $null

    $runningStatus = Convert-CommandJson (Invoke-Isolated -FilePath $Librarian `
        -Arguments @("host", "status") -WorkingDirectory $RunRoot `
        -Environment $runtimeEnvironment) "Host status during packaged adapters"
    if ($runningStatus.status -ne "running" -or @($runningStatus.cores).Count -ne 1) {
        throw "Packaged adapters did not share exactly one running Core"
    }

    Write-Host "== Stop shared installed Core cleanly" -ForegroundColor Cyan
    $stopped = Convert-CommandJson (Invoke-Isolated -FilePath $Librarian `
        -Arguments @("host", "stop", "--vault", $VaultRoot) `
        -WorkingDirectory $RunRoot -Environment $runtimeEnvironment -TimeoutSeconds 60) `
        "Installed librarian host stop"
    if (-not $stopped.stopped) { throw "Installed Host did not stop cleanly" }
    $HostStarted = $false
} finally {
    if ($BrowserRunning) {
        if (-not $BrowserReleased) {
            [IO.File]::WriteAllText((Join-Path $RunRoot "browser-release"), "cleanup`n",
                [Text.UTF8Encoding]::new($false))
        }
        if (-not $BrowserRunning.Process.WaitForExit(5000)) { $BrowserRunning.Process.Kill($true) }
        $BrowserRunning.Process.Dispose()
    }
    if ($HostStarted) {
        try {
            Invoke-Isolated -FilePath $Librarian `
                -Arguments @("host", "stop", "--vault", $VaultRoot, "--force") `
                -WorkingDirectory $RunRoot -Environment $runtimeEnvironment `
                -TimeoutSeconds 60 -AllowFailure | Out-Null
        } catch { Write-Warning "Emergency Host cleanup failed: $_" }
    }
}

$status = Convert-CommandJson (Invoke-Isolated -FilePath $Librarian -Arguments @("host", "status") `
    -WorkingDirectory $RunRoot -Environment $runtimeEnvironment) "Final Host status"
if ($status.status -ne "stopped" -or @($status.cores).Count -ne 0) { throw "Host remains live after adapter smoke" }
if (Test-Path -LiteralPath (Join-Path $VaultRoot ".librarian\runtime\vault.lease.json")) {
    throw "Vault lease metadata remained after adapter smoke"
}
$connections = @(Get-ChildItem -LiteralPath (Join-Path $ConfigRoot "cores") `
    -Filter "*.json" -File -ErrorAction SilentlyContinue)
if ($connections.Count -ne 0) { throw "Core discovery record remained after adapter smoke" }

Write-Host "Packaged-adapter smoke passed: one Browser, packaged Cowork command, $($mcpEvidence.tool_count) tools." -ForegroundColor Green
