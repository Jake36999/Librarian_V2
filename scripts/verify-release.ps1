<#
.SYNOPSIS
    Verifies a signed, self-contained Librarian stable release bundle.

.DESCRIPTION
    The release manifest is a detached CMS/PKCS#7 signed statement over the
    artifact hashes, dependency lock, and release-lead evidence. Verification
    intentionally fails closed: a release candidate or a manifest with merely
    claimed signing metadata is not an installable release.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ReleaseRoot,
    # Retained for callers of the first release-candidate script. Stable
    # bundles now carry their own hashed release-leads file, so source files
    # are never trusted during verification.
    [string]$SourceRoot = ""
)

$ErrorActionPreference = "Stop"
$ReleaseRoot = [IO.Path]::GetFullPath($ReleaseRoot)
$manifestPath = Join-Path $ReleaseRoot "release-manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "No release-manifest.json in $ReleaseRoot"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json

function Resolve-BundlePath([string]$RelativePath, [string]$Name) {
    if ([string]::IsNullOrWhiteSpace($RelativePath)) {
        throw "$Name has no bundle-relative path."
    }
    $rootWithSeparator = $ReleaseRoot.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    $fullPath = [IO.Path]::GetFullPath((Join-Path $ReleaseRoot $RelativePath))
    if (-not $fullPath.StartsWith($rootWithSeparator, [StringComparison]::OrdinalIgnoreCase)) {
        throw "$Name path escapes the release bundle."
    }
    return $fullPath
}

function Assert-FileDigest($Record, [string]$Name, [switch]$RequireBytes) {
    if (-not $Record -or -not $Record.path -or -not $Record.sha256) {
        throw "$Name has no path or SHA-256."
    }
    $path = Resolve-BundlePath $Record.path $Name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "$Name is missing: $path" }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant()
    if ($actual -ne $Record.sha256.ToLowerInvariant()) { throw "$Name SHA-256 mismatch." }
    if ($RequireBytes -and ($null -eq $Record.bytes -or [int64]$Record.bytes -ne (Get-Item -LiteralPath $path).Length)) {
        throw "$Name byte count mismatch."
    }
    return $path
}

function Assert-ManifestSignature {
    if ($manifest.signing.status -ne "signed" -or -not $manifest.signing.verification) {
        throw "Stable release has no signing verification record."
    }
    $verification = $manifest.signing.verification
    if ($verification.scheme -ne "cms_detached" -or -not $verification.signature_path -or -not $verification.signer_thumbprint) {
        throw "Stable release signing record must name a detached CMS signature and signer thumbprint."
    }
    $signaturePath = Resolve-BundlePath $verification.signature_path "Manifest signature"
    if (-not (Test-Path -LiteralPath $signaturePath -PathType Leaf)) {
        throw "Manifest signature is missing: $signaturePath"
    }
    try {
        Add-Type -AssemblyName System.Security.Cryptography.Pkcs -ErrorAction Stop
        $content = [System.Security.Cryptography.Pkcs.ContentInfo]::new([IO.File]::ReadAllBytes($manifestPath))
        $cms = [System.Security.Cryptography.Pkcs.SignedCms]::new($content, $true)
        $cms.Decode([IO.File]::ReadAllBytes($signaturePath))
        # `$false` validates both the cryptographic signature and the signing
        # certificate chain. A self-signed developer certificate is not a
        # production release credential.
        $cms.CheckSignature($false)
    } catch {
        throw "Manifest CMS signature did not verify: $($_.Exception.Message)"
    }
    if ($cms.SignerInfos.Count -ne 1 -or -not $cms.SignerInfos[0].Certificate) {
        throw "Manifest signature must have exactly one certificate-backed signer."
    }
    $actualThumbprint = ($cms.SignerInfos[0].Certificate.Thumbprint -replace '\s', '').ToUpperInvariant()
    $expectedThumbprint = ($verification.signer_thumbprint -replace '\s', '').ToUpperInvariant()
    if ($actualThumbprint -ne $expectedThumbprint) {
        throw "Manifest signature signer does not match the recorded thumbprint."
    }
}

function Assert-ReleaseLead([object]$Lead, [string]$Provider) {
    if (-not $Lead -or $Lead.provider -ne $Provider -or $Lead.qualification -ne "verified_release") {
        throw "Stable release needs a verified_release $Provider lead."
    }
    foreach ($field in @("id", "host_id", "model", "model_version", "model_fingerprint", "role",
                          "endpoint_fingerprint", "protocol_version", "tool_contract_version",
                          "prompt_contract_version", "tested_at", "expires_at")) {
        if ([string]::IsNullOrWhiteSpace([string]$Lead.$field)) {
            throw "Stable $Provider lead is missing $field."
        }
    }
    if ($Lead.role -ne "lead") { throw "Stable $Provider route is not qualified for the lead role." }
    # Runtime uses its compact canonical route digest for model fingerprints;
    # artifact integrity remains a full SHA-256 below.
    if ([string]$Lead.model_fingerprint -notmatch '^[0-9a-fA-F]{24}$') {
        throw "Stable $Provider lead has an invalid model fingerprint."
    }
    if ([string]$Lead.endpoint_fingerprint -notmatch '^[0-9a-fA-F]{16,64}$') {
        throw "Stable $Provider lead has an invalid endpoint fingerprint."
    }
    if (-not $Lead.endpoint -or $Lead.endpoint.protocol -ne $Provider -or
        [string]::IsNullOrWhiteSpace([string]$Lead.endpoint.base_url) -or
        [string]::IsNullOrWhiteSpace([string]$Lead.endpoint.auth_ref)) {
        throw "Stable $Provider lead has no exact $Provider endpoint requirement."
    }
    try {
        $testedAt = [DateTimeOffset]::Parse([string]$Lead.tested_at)
        $expiresAt = [DateTimeOffset]::Parse([string]$Lead.expires_at)
    } catch { throw "Stable $Provider lead has invalid evidence dates." }
    if ($testedAt -gt [DateTimeOffset]::UtcNow.AddDays(1) -or $expiresAt -le [DateTimeOffset]::UtcNow -or
        $expiresAt -le $testedAt) {
        throw "Stable $Provider lead has stale or inconsistent evidence dates."
    }
    try { $l3Runs = [int]$Lead.l3_runs } catch { $l3Runs = 0 }
    if ($l3Runs -lt 5) { throw "Stable $Provider lead records fewer than five L3 runs." }
    $artifacts = @($Lead.qualification_artifacts)
    if ($artifacts.Count -lt 1) { throw "Stable $Provider lead has no qualification artifacts." }
    foreach ($artifact in $artifacts) {
        if (-not $artifact -or
            ([string]::IsNullOrWhiteSpace([string]$artifact.id) -and
             [string]::IsNullOrWhiteSpace([string]$artifact.uri) -and
             [string]::IsNullOrWhiteSpace([string]$artifact.path)) -or
            [string]$artifact.sha256 -notmatch '^[0-9a-fA-F]{64}$') {
            throw "Stable $Provider lead has an invalid qualification artifact."
        }
    }
}

if ($manifest.release_status -ne "stable") {
    throw "Only a stable, signed manifest is installable; found release_status '$($manifest.release_status)'."
}
if ($manifest.schema_version -ne 1 -or $manifest.product -ne "Librarian" -or
    $manifest.package -ne "resource-librarian" -or
    [string]::IsNullOrWhiteSpace([string]$manifest.version) -or
    $manifest.version -notmatch '^\d+\.\d+\.\d+$' -or
    [string]::IsNullOrWhiteSpace([string]$manifest.core_protocol_version) -or
    [string]::IsNullOrWhiteSpace([string]$manifest.compatible_adapter_range) -or
    [string]::IsNullOrWhiteSpace([string]$manifest.ui_build_id)) {
    throw "Stable release manifest has an incomplete product, version, protocol, or UI contract."
}
if (-not $manifest.installer.hash_locked -or -not $manifest.installer.requirements_lock -or
    -not $manifest.installer.wheelhouse) {
    throw "A stable release must include a hash-locked requirements file and wheelhouse."
}

Assert-ManifestSignature

foreach ($requiredArtifact in @("core_wheel", "obsidian_bundle", "cowork_bundle", "host_companion")) {
    if (-not $manifest.artifacts.$requiredArtifact) { throw "Stable release is missing artifact metadata for $requiredArtifact." }
    [void](Assert-FileDigest $manifest.artifacts.$requiredArtifact $requiredArtifact -RequireBytes)
}

foreach ($installerScript in @("bootstrapper", "verifier")) {
    if (-not $manifest.installer.$installerScript) {
        throw "Stable release has no hashed installer $installerScript."
    }
    [void](Assert-FileDigest $manifest.installer.$installerScript "Installer $installerScript" -RequireBytes)
}

$lockPath = Resolve-BundlePath $manifest.installer.requirements_lock "Requirements lock"
if (-not (Test-Path -LiteralPath $lockPath -PathType Leaf)) { throw "Requirements lock is missing." }
$lockHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $lockPath).Hash.ToLowerInvariant()
if ($lockHash -ne $manifest.installer.requirements_lock_sha256.ToLowerInvariant()) {
    throw "Requirements lock SHA-256 mismatch."
}
$wheelhouse = Resolve-BundlePath $manifest.installer.wheelhouse "Dependency wheelhouse"
if (-not (Test-Path -LiteralPath $wheelhouse -PathType Container)) { throw "Dependency wheelhouse is missing." }

if ($manifest.release_leads.status -ne "verified_release" -or -not $manifest.release_leads.path -or -not $manifest.release_leads.sha256) {
    throw "Stable release needs a hashed verified_release lead manifest."
}
$leadsPath = Resolve-BundlePath $manifest.release_leads.path "Release-lead manifest"
if (-not (Test-Path -LiteralPath $leadsPath -PathType Leaf)) { throw "Release-lead manifest is missing." }
$leadsHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $leadsPath).Hash.ToLowerInvariant()
if ($leadsHash -ne $manifest.release_leads.sha256.ToLowerInvariant()) {
    throw "Release-lead manifest SHA-256 mismatch."
}
if ($null -eq $manifest.release_leads.bytes -or [int64]$manifest.release_leads.bytes -ne
    (Get-Item -LiteralPath $leadsPath).Length) {
    throw "Release-lead manifest byte count mismatch."
}
$leads = Get-Content -LiteralPath $leadsPath -Raw | ConvertFrom-Json
if ($leads.schema_version -ne 2 -or $leads.release_status -ne "stable" -or
    [string]::IsNullOrWhiteSpace([string]$leads.integrity) -or
    [string]::IsNullOrWhiteSpace([string]$leads.release_version) -or
    $leads.release_version -ne $manifest.version -or -not $leads.contract) {
    throw "Stable release-lead manifest has an incomplete envelope."
}
foreach ($contractField in @("protocol_version", "tool_contract_version", "prompt_contract_version")) {
    if ([string]::IsNullOrWhiteSpace([string]$leads.contract.$contractField)) {
        throw "Stable release-lead manifest is missing contract $contractField."
    }
}
if ([string]$leads.contract.protocol_version -ne [string]$manifest.core_protocol_version) {
    throw "Stable release-lead protocol is incompatible with the Core manifest."
}
foreach ($provider in @("openai", "anthropic")) {
    $lead = @($leads.leads | Where-Object { $_.provider -eq $provider -and $_.qualification -eq "verified_release" })
    if ($lead.Count -ne 1) { throw "Stable release needs exactly one verified_release $provider lead." }
    Assert-ReleaseLead $lead[0] $provider
}

Write-Host "Release verification passed for Librarian $($manifest.version)." -ForegroundColor Green
