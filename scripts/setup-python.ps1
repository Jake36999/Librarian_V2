# Interpreter selection shared by setup.ps1 and its deterministic regression.
# Librarian releases support exactly Python 3.11 through 3.13.
$script:LibrarianSupportedPythonMinors = @(13, 12, 11)

function Get-LibrarianPythonVersion {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [object[]]$Lead = @()
    )
    if (-not (Get-Command $Exe -ErrorAction SilentlyContinue)) { return $null }
    $probe = "import sys; print('%d.%d' % sys.version_info[:2])"
    try {
        $raw = & $Exe @Lead -c $probe 2>$null
    } catch {
        return $null
    }
    if ($LASTEXITCODE -ne 0 -or -not $raw) { return $null }
    $match = [regex]::Match("$raw".Trim(), '^(?<major>\d+)\.(?<minor>\d+)$')
    if (-not $match.Success) { return $null }
    $major = [int]$match.Groups['major'].Value
    $minor = [int]$match.Groups['minor'].Value
    if ($major -ne 3 -or $minor -notin $script:LibrarianSupportedPythonMinors) {
        return $null
    }
    return "$major.$minor"
}

function Find-LibrarianPython {
    param([string]$Requested = "")
    $candidates = @()
    if ($Requested) {
        # An explicit interpreter is a contract, not a hint. Falling back to
        # another command would make Setup report success with the wrong
        # Python after the requested one proved unsupported.
        $candidates += , @($Requested)
    } else {
        foreach ($minor in $script:LibrarianSupportedPythonMinors) {
            $candidates += , @("py", "-3.$minor")
        }
        $candidates += , @("python")
        $candidates += , @("python3")
    }
    foreach ($candidate in $candidates) {
        $exe = $candidate[0]
        $lead = @()
        if ($candidate.Count -gt 1) { $lead = @($candidate[1..($candidate.Count - 1)]) }
        $version = Get-LibrarianPythonVersion -Exe $exe -Lead $lead
        if ($version) {
            return @{ Exe = $exe; Lead = $lead; Version = $version }
        }
    }
    return $null
}
