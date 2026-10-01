<#
.SYNOPSIS
    Sets up this copy of the Librarian: its own Python environment, the package with
    its extras, the interface, and a desktop shortcut that opens the library picker.

.DESCRIPTION
    Works on the copy it sits in (the folder above scripts\), wherever it is run from.
    Each copy gets an environment of its own in .venv, so each runs its own code;
    nothing is installed into the system Python. Safe to re-run: it reuses the environment,
    reinstalls the package (picking up new dependencies) and replaces the shortcut.

    Double-click Setup.bat in the copy's folder to run it.

.PARAMETER Extras
    The optional parts to install, comma-separated: mcp (the MCP server), pdf (PDF
    text), embed (semantic search), search, dev (the test suite). "" for none.
    Default: mcp,pdf,embed.

.PARAMETER Python
    A Python 3.11 or later to build the environment from. Default: the newest found
    through the py launcher, else python on PATH.

.PARAMETER ShortcutName
    The desktop shortcut's name. Default: "Librarian", or "Librarian (dev)" for the
    dev copy (a folder named .v2).

.PARAMETER NoShortcut
    Don't create the desktop shortcut.

.PARAMETER BuildUI
    Rebuild the interface from ui\src (needs Node.js). Without it the interface is
    built only when the copy has no built one; it normally ships built.
#>
param(
    [string]$Extras = "mcp,pdf,embed",
    [string]$Python = "",
    [string]$ShortcutName = "",
    [switch]$NoShortcut,
    [switch]$BuildUI
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Root ".venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
# Works around an OpenBLAS "memory allocation failed" crash on this machine when
# numpy loads (see new-vault.ps1); harmless elsewhere.
$env:OPENBLAS_NUM_THREADS = "1"
$env:OMP_NUM_THREADS = "1"

function Step([string]$Text) {
    Write-Host ""
    Write-Host "== $Text" -ForegroundColor Cyan
}

function Stop-Setup([string]$Text) {
    Write-Host ""
    Write-Host "Setup stopped: $Text" -ForegroundColor Red
    exit 1
}

function Find-Python {
    # Each candidate is a command and its leading arguments; the first that is 3.11+ wins.
    $candidates = @()
    if ($Python) { $candidates += , @($Python) }
    foreach ($minor in @("3.14", "3.13", "3.12", "3.11")) { $candidates += , @("py", "-$minor") }
    $candidates += , @("python")
    $candidates += , @("python3")
    $probe = "import sys; print('%d.%d' % sys.version_info[:2]); sys.exit(0 if sys.version_info >= (3, 11) else 3)"
    foreach ($candidate in $candidates) {
        $exe = $candidate[0]
        $lead = @()
        if ($candidate.Count -gt 1) { $lead = @($candidate[1..($candidate.Count - 1)]) }
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        try {
            $version = & $exe @lead -c $probe 2>$null
        } catch {
            continue
        }
        if ($LASTEXITCODE -eq 0 -and $version) {
            return @{ Exe = $exe; Lead = $lead; Version = "$version".Trim() }
        }
    }
    return $null
}

Write-Host "Setting up the Librarian in $Root"
if (-not (Test-Path (Join-Path $Root "pyproject.toml"))) {
    Stop-Setup "$Root has no pyproject.toml - this script belongs in a Librarian copy's scripts folder"
}

# 1. An environment of this copy's own ---------------------------------------
Step "Python environment ($Venv)"
if (Test-Path $VenvPython) {
    Write-Host "Reusing the environment already here."
} else {
    $found = Find-Python
    if (-not $found) {
        Stop-Setup "no Python 3.11 or later found. Install it from python.org (tick 'Add python.exe to PATH'), then run this again"
    }
    Write-Host "Creating it with Python $($found.Version) ($($found.Exe) $($found.Lead -join ' '))"
    $lead = $found.Lead
    & $found.Exe @lead -m venv $Venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) { Stop-Setup "could not create the environment" }
}

# 2. The package, editable, so this copy's own src is what runs --------------
Step "Installing the Librarian into it"
$target = $Root
if ($Extras) { $target = $Root + "[" + $Extras + "]" }
& $VenvPython -m pip install --disable-pip-version-check --quiet --upgrade pip
if ($LASTEXITCODE -ne 0) { Write-Warning "pip could not upgrade itself; carrying on with the one there" }
& $VenvPython -m pip install --disable-pip-version-check --quiet --editable $target
if ($LASTEXITCODE -ne 0) { Stop-Setup "pip could not install $target (see the lines above)" }
Write-Host "Installed $target"

# 3. The interface -------------------------------------------------------------
Step "Interface"
$built = Join-Path $Root "src\resource_librarian\ui\app.js"
if ($BuildUI -or -not (Test-Path $built)) {
    if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
        if (Test-Path $built) {
            Write-Warning "Node.js (npm) isn't installed, so the interface was not rebuilt; the built one stays"
        } else {
            Stop-Setup "this copy has no built interface and Node.js (npm) isn't installed: install Node.js, then run this again"
        }
    } else {
        Push-Location (Join-Path $Root "ui")
        try {
            & npm.cmd install --no-audit --no-fund
            if ($LASTEXITCODE -ne 0) { Stop-Setup "npm install failed in ui\" }
            & npm.cmd run build
            if ($LASTEXITCODE -ne 0) { Stop-Setup "the interface did not build (npm run build in ui\)" }
        } finally {
            Pop-Location
        }
    }
} else {
    Write-Host "It ships built (src\resource_librarian\ui); -BuildUI rebuilds it from ui\src."
}

# 4. Check it runs, and that it runs this copy --------------------------------
Step "Checking it"
# A file, not `python -c`: Windows PowerShell 5.1 mangles quotes in a native argument.
$checkFile = Join-Path $env:TEMP "librarian-setup-check.py"
@'
import importlib, importlib.metadata as m, json, pathlib, sys
import resource_librarian
extras = {}
for name, module in (("mcp", "mcp"), ("pdf", "pypdf"), ("embed", "model2vec")):
    try:
        importlib.import_module(module)
        extras[name] = True
    except Exception:
        extras[name] = False
print(json.dumps({"version": m.version("resource-librarian"),
                  "from": str(pathlib.Path(resource_librarian.__file__).resolve().parents[2]),
                  "python": sys.version.split()[0], "extras": extras}))
'@ | Set-Content -Path $checkFile -Encoding ASCII
$raw = & $VenvPython $checkFile
$code = $LASTEXITCODE
Remove-Item $checkFile -ErrorAction SilentlyContinue
if ($code -ne 0 -or -not $raw) { Stop-Setup "the package does not import (see the lines above)" }
$report = $raw | ConvertFrom-Json
if ((Resolve-Path $report.from).Path -ne (Resolve-Path $Root).Path) {
    Stop-Setup "the environment runs the Librarian from $($report.from), not from this copy"
}
& $VenvPython -m resource_librarian --help | Out-Null
if ($LASTEXITCODE -ne 0) { Stop-Setup "resource-librarian --help failed" }
$have = @()
foreach ($p in $report.extras.PSObject.Properties) {
    if ($p.Value) { $have += $p.Name }
}
Write-Host "resource-librarian $($report.version) on Python $($report.python), running $($report.from)"
if ($have.Count) { Write-Host "Optional parts present: $($have -join ', ')" }

# 5. The desktop shortcut: the library picker first ---------------------------
if (-not $NoShortcut) {
    Step "Desktop shortcut"
    if (-not $ShortcutName) {
        $ShortcutName = "Librarian"
        if ((Split-Path -Leaf $Root) -eq ".v2") { $ShortcutName = "Librarian (dev)" }
    }
    $desktop = [Environment]::GetFolderPath("Desktop")
    $link = Join-Path $desktop "$ShortcutName.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($link)
    $shortcut.TargetPath = Join-Path $Root "Librarian.bat"
    $shortcut.Arguments = "--pick"
    $shortcut.WorkingDirectory = $Root
    $shortcut.WindowStyle = 7                  # minimised: its window is the server; closing it stops the Librarian
    $shortcut.Description = "Open the Librarian: choose, create or open a library ($Root)"
    $icon = Join-Path $Root "scripts\librarian.ico"
    if (Test-Path $icon) { $shortcut.IconLocation = "$icon,0" }
    $shortcut.Save()
    Write-Host "Created $link"
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
if (-not $NoShortcut) {
    Write-Host "Open the Librarian from the desktop shortcut '$ShortcutName': it starts at the library picker."
}
Write-Host "Or run Librarian.bat in $Root (Librarian.bat --pick for the picker)."
exit 0
