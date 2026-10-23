<#
.SYNOPSIS
    Builds reproducible Librarian release candidates or a controlled stable
    bundle from this source tree.

.DESCRIPTION
    This is a release-build step, not an installer.  It uses npm ci only for
    release builds, produces Core/Obsidian/Cowork artifacts in one directory,
    and writes their SHA-256 values into a copied release manifest.  Without
    -Stable it always makes a non-installable candidate.  -Stable requires
    separately generated evidence and offline dependencies, then still needs
    sign-release.ps1 before verify-release.ps1 will accept it.
#>
[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$OutDir = "",
    # A stable build must receive real, separately generated release-lead
    # evidence and a complete offline dependency bundle.  The source-tree
    # candidates are deliberately never promoted by this switch.
    [switch]$Stable,
    [string]$ReleaseLeads = "",
    [string]$RequirementsLock = "",
    [string]$Wheelhouse = "",
    [switch]$SkipTests,
    [switch]$SkipUi
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not $OutDir) { $OutDir = Join-Path $Root "release-out" }
$OutDir = [IO.Path]::GetFullPath($OutDir)
if (Test-Path -LiteralPath $OutDir) {
    # Reusing a release directory can make an old wheel look current when a
    # build fails halfway through.  Fail rather than cleaning automatically:
    # release artifacts are evidence and an operator must choose any removal.
    $existingOutput = @(Get-ChildItem -LiteralPath $OutDir -Force -ErrorAction Stop)
    if ($existingOutput.Count -gt 0) {
        throw "Release output directory must be empty: $OutDir. Choose a fresh directory or explicitly archive/remove the old candidate."
    }
}

function Invoke-Native([string]$Description, [scriptblock]$Command) {
    Write-Host "== $Description" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Description failed (exit $LASTEXITCODE)" }
}

function Add-ManifestArtifact($Manifest, [string]$Name, [string]$Path, [string]$RootPath) {
    $item = Get-Item -LiteralPath $Path
    $Manifest.artifacts.$Name.path = [IO.Path]::GetRelativePath($RootPath, $item.FullName).Replace("\", "/")
    $Manifest.artifacts.$Name.sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $item.FullName).Hash.ToLowerInvariant()
    $Manifest.artifacts.$Name.bytes = $item.Length
}

function Set-ManifestFile($Record, [string]$Path, [string]$RootPath) {
    $item = Get-Item -LiteralPath $Path
    $Record.path = [IO.Path]::GetRelativePath($RootPath, $item.FullName).Replace("\", "/")
    $Record.sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $item.FullName).Hash.ToLowerInvariant()
    $Record.bytes = $item.Length
}

function New-DeterministicZip([string]$Source, [string]$Destination) {
    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        throw "Bundle source directory is missing: $Source"
    }
    if (Test-Path -LiteralPath $Destination) { Remove-Item -LiteralPath $Destination -Force }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $stream = [IO.File]::Open($Destination, [IO.FileMode]::CreateNew)
    try {
        $zip = [IO.Compression.ZipArchive]::new($stream, [IO.Compression.ZipArchiveMode]::Create, $false)
        try {
            # Stable path order and timestamps make the adapter bundles
            # reproducible when their input bytes are unchanged.
            $epoch = [DateTimeOffset]::new(1980, 1, 1, 0, 0, 0, [TimeSpan]::Zero)
            Get-ChildItem -LiteralPath $Source -File -Recurse |
                Sort-Object FullName | ForEach-Object {
                    $relative = [IO.Path]::GetRelativePath($Source, $_.FullName).Replace("\", "/")
                    $entry = $zip.CreateEntry($relative, [IO.Compression.CompressionLevel]::Optimal)
                    $entry.LastWriteTime = $epoch
                    $input = [IO.File]::OpenRead($_.FullName)
                    $output = $entry.Open()
                    try { $input.CopyTo($output) } finally {
                        $output.Dispose()
                        $input.Dispose()
                    }
                }
        } finally { $zip.Dispose() }
    } finally { $stream.Dispose() }
}

if (-not (Test-Path (Join-Path $Root "pyproject.toml"))) {
    throw "This script belongs in a Librarian source checkout."
}
if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    throw "Python command '$Python' was not found."
}
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue) -and -not $SkipUi) {
    throw "Node.js/npm is required for a release build."
}

$version = (Get-Content -LiteralPath (Join-Path $Root "VERSION") -Raw).Trim()
$pyproject = Get-Content -LiteralPath (Join-Path $Root "pyproject.toml") -Raw
$pyprojectVersion = [regex]::Match($pyproject, '(?ms)^\[project\]\s*.*?^version\s*=\s*"([^"]+)"').Groups[1].Value
$init = Get-Content -LiteralPath (Join-Path $Root "src\resource_librarian\__init__.py") -Raw
$initVersion = [regex]::Match($init, '(?m)^__version__\s*=\s*"([^"]+)"').Groups[1].Value
if (-not $pyprojectVersion -or -not $initVersion -or $version -ne $pyprojectVersion -or $version -ne $initVersion) {
    throw "VERSION, pyproject.toml, and resource_librarian.__version__ must match before a release build."
}
if ($Stable -and $version -notmatch '^\d+\.\d+\.\d+$') {
    throw "A stable build requires a SemVer release version (for example 2.1.0), not '$version'."
}

# Wheel builders honour SOURCE_DATE_EPOCH.  Git supplies a stable source
# timestamp when available; the fallback is the ZIP epoch for source exports.
$sourceEpoch = "315532800"
if (Get-Command git -ErrorAction SilentlyContinue) {
    $gitEpoch = (& git -C $Root log -1 --format=%ct 2>$null).Trim()
    if ($gitEpoch -match '^\d+$') { $sourceEpoch = $gitEpoch }
}
$env:SOURCE_DATE_EPOCH = $sourceEpoch

New-Item -ItemType Directory -Force -Path $OutDir, (Join-Path $OutDir "core"),
    (Join-Path $OutDir "obsidian"), (Join-Path $OutDir "cowork"),
    (Join-Path $OutDir "installer"), (Join-Path $OutDir "host") | Out-Null

if (-not $SkipUi) {
    Push-Location (Join-Path $Root "ui")
    try {
        Invoke-Native "UI dependency restore" { & npm.cmd ci --no-audit --no-fund }
        Invoke-Native "UI build" { & npm.cmd run build }
    } finally { Pop-Location }
    Push-Location (Join-Path $Root "obsidian")
    try {
        Invoke-Native "Obsidian dependency restore" { & npm.cmd ci --no-audit --no-fund }
        Invoke-Native "Obsidian build" { & npm.cmd run build }
    } finally { Pop-Location }
}

if (-not $SkipTests) {
    Invoke-Native "Core test suite" { & $Python -m pytest }
}

Invoke-Native "Core wheel build" { & $Python -m build --wheel --outdir (Join-Path $OutDir "core") $Root }
$wheel = Get-ChildItem (Join-Path $OutDir "core") -Filter "*.whl" -File |
    Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
if (-not $wheel) { throw "The Core wheel was not created." }

$obsidianZip = Join-Path $OutDir "obsidian\librarian-obsidian.zip"
New-DeterministicZip (Join-Path $Root "obsidian\dist") $obsidianZip

# The deterministic ZIP helper includes dot-directories such as
# .claude-plugin, which Compress-Archive can skip.
$coworkZip = Join-Path $OutDir "cowork\librarian-cowork.zip"
New-DeterministicZip (Join-Path $Root "plugin") $coworkZip

# The tray companion is source-controlled PowerShell, not an independently
# trusted service binary. Include its bytes in the release manifest so the
# bootstrapper never copies an unverified launcher script.
$hostCompanion = Join-Path $OutDir "host\LibrarianHost.ps1"
Copy-Item -LiteralPath (Join-Path $Root "scripts\librarian-host.ps1") -Destination $hostCompanion -Force

$manifestPath = Join-Path $Root "release-manifest.json"
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$manifest.version = $version
$revision = "source"
if (Get-Command git -ErrorAction SilentlyContinue) {
    $gitRevision = (& git -C $Root rev-parse --verify HEAD 2>$null).Trim()
    if ($gitRevision -match '^[0-9a-f]{40}$') { $revision = $gitRevision.Substring(0, 12) }
}
$manifest.ui_build_id = "${version}-${revision}"
Add-ManifestArtifact $manifest "core_wheel" $wheel.FullName $OutDir
Add-ManifestArtifact $manifest "obsidian_bundle" $obsidianZip $OutDir
Add-ManifestArtifact $manifest "cowork_bundle" $coworkZip $OutDir
Add-ManifestArtifact $manifest "host_companion" $hostCompanion $OutDir

$leadsSource = Join-Path $Root "src\resource_librarian\standard\release_leads.json"
if ($ReleaseLeads) {
    $leadsSource = [IO.Path]::GetFullPath($ReleaseLeads)
}
if (-not (Test-Path -LiteralPath $leadsSource -PathType Leaf)) { throw "Release-lead manifest is missing: $leadsSource" }
$leadsOutput = Join-Path $OutDir "release-leads.json"
Copy-Item -LiteralPath $leadsSource -Destination $leadsOutput -Force
Set-ManifestFile $manifest.release_leads $leadsOutput $OutDir
$manifest.release_leads.source = "release-leads.json"

# A production release must bring a generated hash lock and its wheelhouse.
$lock = if ($RequirementsLock) { [IO.Path]::GetFullPath($RequirementsLock) } else { Join-Path $Root "requirements.release.lock" }
$wheelhouse = if ($Wheelhouse) { [IO.Path]::GetFullPath($Wheelhouse) } else { Join-Path $Root "wheelhouse" }
if ((Test-Path $lock -PathType Leaf) -and (Test-Path $wheelhouse -PathType Container)) {
    Copy-Item -LiteralPath $lock -Destination (Join-Path $OutDir "requirements.release.lock") -Force
    Copy-Item -LiteralPath $wheelhouse -Destination (Join-Path $OutDir "wheelhouse") -Recurse -Force
    $copiedLock = Join-Path $OutDir "requirements.release.lock"
    $manifest.installer.requirements_lock = "requirements.release.lock"
    $manifest.installer.requirements_lock_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $copiedLock).Hash.ToLowerInvariant()
    $manifest.installer.wheelhouse = "wheelhouse"
    $manifest.installer.hash_locked = $true
} elseif ($Stable) {
    throw "A stable build requires a hash-locked requirements file and wheelhouse."
}

# A release bundle is self-contained: the user receives the verifier and
# bootstrapper beside the signed manifest instead of being asked to run code
# from a source checkout.  The stable manifest hashes both scripts; the
# distribution channel still needs to Authenticode-sign the bootstrapper
# itself before a user executes it.
$bootstrapperOutput = Join-Path $OutDir "installer\bootstrapper.ps1"
$verifierOutput = Join-Path $OutDir "installer\verify-release.ps1"
Copy-Item -LiteralPath (Join-Path $Root "scripts\bootstrapper.ps1") -Destination $bootstrapperOutput -Force
Copy-Item -LiteralPath (Join-Path $Root "scripts\verify-release.ps1") -Destination $verifierOutput -Force
Set-ManifestFile $manifest.installer.bootstrapper $bootstrapperOutput $OutDir
Set-ManifestFile $manifest.installer.verifier $verifierOutput $OutDir

if ($Stable) {
    $leadData = Get-Content -LiteralPath $leadsOutput -Raw | ConvertFrom-Json
    if ($leadData.release_status -ne "stable") {
        throw "A stable build requires a stable, evidence-backed release-lead manifest."
    }
    $manifest.release_status = "stable"
    $manifest.release_leads.status = "verified_release"
} else {
    # Keep a candidate build visibly non-installable even if a developer has
    # a local wheelhouse or experiments with a stable evidence file.
    $manifest.release_status = "development_template"
    $manifest.release_leads.status = "pending_release_ci"
}

$outManifest = Join-Path $OutDir "release-manifest.json"
[IO.File]::WriteAllText($outManifest, ($manifest | ConvertTo-Json -Depth 12) + [Environment]::NewLine,
    [Text.UTF8Encoding]::new($false))
Write-Host "Release candidate written to $OutDir"
Write-Host "Run scripts\verify-release.ps1 against it before signing or publishing."
