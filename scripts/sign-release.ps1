<#
.SYNOPSIS
    Creates the detached CMS signature required for a Librarian stable bundle.

.DESCRIPTION
    Run only after release CI has replaced candidate lead data with real L3
    evidence and a human has reviewed the stable manifest. The signature covers
    the exact manifest bytes, which in turn contain every artifact digest.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ReleaseRoot,
    [Parameter(Mandatory = $true)][string]$CertificateThumbprint
)

$ErrorActionPreference = "Stop"
$ReleaseRoot = [IO.Path]::GetFullPath($ReleaseRoot)
$manifestPath = Join-Path $ReleaseRoot "release-manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "No release-manifest.json in $ReleaseRoot"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.release_status -ne "stable") {
    throw "Refusing to sign a non-stable manifest. Record real release evidence before signing."
}
if ($manifest.release_leads.status -ne "verified_release" -or -not $manifest.release_leads.path -or -not $manifest.release_leads.sha256) {
    throw "Refusing to sign without a hashed verified_release lead manifest."
}
if (-not $manifest.installer.hash_locked -or -not $manifest.installer.requirements_lock -or -not $manifest.installer.wheelhouse) {
    throw "Refusing to sign without a hash-locked installer dependency bundle."
}

$normalizedThumbprint = ($CertificateThumbprint -replace '\s', '').ToUpperInvariant()
if ($normalizedThumbprint -notmatch '^[0-9A-F]+$') { throw "CertificateThumbprint is not a hexadecimal thumbprint." }
$certificate = Get-ChildItem -Path "Cert:\CurrentUser\My\$normalizedThumbprint" -ErrorAction SilentlyContinue
if (-not $certificate) {
    $certificate = Get-ChildItem -Path "Cert:\LocalMachine\My\$normalizedThumbprint" -ErrorAction SilentlyContinue
}
if (-not $certificate -or -not $certificate.HasPrivateKey) {
    throw "No accessible signing certificate with a private key was found for $normalizedThumbprint."
}

$codeSigningOid = "1.3.6.1.5.5.7.3.3"
$hasCodeSigningUsage = @($certificate.EnhancedKeyUsageList | Where-Object { $_.ObjectId.Value -eq $codeSigningOid }).Count -gt 0
if (-not $hasCodeSigningUsage) {
    throw "The selected certificate lacks the Code Signing enhanced-key-usage OID ($codeSigningOid)."
}

$signatureRelativePath = "release-manifest.p7s"
$signaturePath = [IO.Path]::GetFullPath((Join-Path $ReleaseRoot $signatureRelativePath))
$rootWithSeparator = $ReleaseRoot.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $signaturePath.StartsWith($rootWithSeparator, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Signature path escapes the release bundle."
}

# Signing metadata must be in the bytes that are signed. Do not modify the
# manifest after this point; verify-release.ps1 checks both chain and signer.
$manifest.signing.status = "signed"
$manifest.signing.verification = [pscustomobject]@{
    scheme = "cms_detached"
    signature_path = $signatureRelativePath
    signer_thumbprint = $normalizedThumbprint
    signed_at = (Get-Date -AsUTC -Format "yyyy-MM-ddTHH:mm:ssZ")
}
[IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 12) + [Environment]::NewLine,
    [Text.UTF8Encoding]::new($false))

Add-Type -AssemblyName System.Security.Cryptography.Pkcs -ErrorAction Stop
$content = [System.Security.Cryptography.Pkcs.ContentInfo]::new([IO.File]::ReadAllBytes($manifestPath))
$cms = [System.Security.Cryptography.Pkcs.SignedCms]::new($content, $true)
$signer = [System.Security.Cryptography.Pkcs.CmsSigner]::new($certificate)
$signer.IncludeOption = [System.Security.Cryptography.X509Certificates.X509IncludeOption]::EndCertOnly
$signer.DigestAlgorithm = [System.Security.Cryptography.Oid]::new("SHA256")
$cms.ComputeSignature($signer)

$temporarySignature = "$signaturePath.tmp"
[IO.File]::WriteAllBytes($temporarySignature, $cms.Encode())
Move-Item -LiteralPath $temporarySignature -Destination $signaturePath -Force
Write-Host "Signed release manifest with $normalizedThumbprint. Run verify-release.ps1 before publishing." -ForegroundColor Green
