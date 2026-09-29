<#
.SYNOPSIS
    Opens (creating it if needed) the library for a domain, registers the
    current project in it as a pursuit, then launches the app. Or, without
    -Domain, a one-off vault at .\.librarian-app as before.

.DESCRIPTION
    One library per domain (Co-work Roadmap §4 F): everything about software
    systems in one library, a course in another, history in a third. Projects
    live inside their domain's library as pursuits, so what one project
    learns is there for the next.

    With -Domain, run this from inside a project directory: the domain's
    library is created (with -Profile, specialised for its domain) or reopened
    at <LibrariesRoot>\<Domain>, and the current directory is registered in it
    as a pursuit - once; re-running only reopens. It never touches Resource
    Library (V1) or any other library's data.

    Without -Domain it behaves as it always has: a one-off vault at
    <current dir>\.librarian-app.

    Safe to re-run either way.

.PARAMETER Domain
    The domain library to open or create, e.g. "Software", "History", "Databases Course".

.PARAMETER Profile
    Only used when the domain library is first created: a standard profile
    (software-systems, course, history) or a path to a profile file. It adds
    the domain's note fields, and suggests lens packs, outside servers and
    workflows - each still accepted or enabled by you in Settings -> Library.

.PARAMETER LibrariesRoot
    Where domain libraries live. Defaults to $env:LIBRARIAN_LIBRARIES, else
    $HOME\Libraries.

.PARAMETER Project
    The pursuit to register for the current directory. Defaults to the
    directory's name.

.PARAMETER NoProject
    Open the domain library without registering the current directory.

.PARAMETER Name
    Without -Domain: the one-off vault's title. Defaults to the directory's name.

.PARAMETER Port
    Port for the local app server. Defaults to 8323.

.PARAMETER NoLaunch
    Create (if needed) but don't start the app - just print the command.

.EXAMPLE
    D:\Resource-Library\.v2\scripts\new-vault.ps1 -Domain Software -Profile software-systems
    (run from D:\Projects\Harness - opens or creates $HOME\Libraries\Software,
    registers "Harness" as a pursuit there, and opens it in the browser)

.EXAMPLE
    D:\Resource-Library\.v2\scripts\new-vault.ps1
    (run from D:\Projects\Thesis - a one-off vault at D:\Projects\Thesis\.librarian-app)
#>
param(
    [string]$Domain = "",
    [string]$Profile = "",
    [string]$LibrariesRoot = "",
    [string]$Project = (Split-Path -Leaf (Get-Location)),
    [switch]$NoProject,
    [string]$Name = (Split-Path -Leaf (Get-Location)),
    [int]$Port = 8323,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command resource-librarian -ErrorAction SilentlyContinue)) {
    Write-Error "resource-librarian isn't installed. Run: pip install -e `"D:\Resource-Library\.v2[dev]`""
    exit 1
}

# Works around an OpenBLAS "memory allocation failed" crash on this machine
# when numpy loads under load; harmless elsewhere.
$env:OPENBLAS_NUM_THREADS = "1"
$env:OMP_NUM_THREADS = "1"

if ($Domain) {
    if (-not $LibrariesRoot) {
        $LibrariesRoot = if ($env:LIBRARIAN_LIBRARIES) { $env:LIBRARIAN_LIBRARIES } else { Join-Path $HOME "Libraries" }
    }
    $vaultPath = Join-Path $LibrariesRoot $Domain
    $title = $Domain
} else {
    if ($Profile) { Write-Warning "-Profile is only used with -Domain; ignoring it for a one-off vault." }
    $vaultPath = Join-Path (Get-Location) ".librarian-app"
    $title = $Name
}
$configPath = Join-Path $vaultPath ".librarian\config.toml"

if (Test-Path $configPath) {
    Write-Host "Reopening the library at $vaultPath"
    if ($Domain -and $Profile) { Write-Host "  (it already exists, so -Profile is not applied again)" }
} else {
    Write-Host "Creating the library at $vaultPath"
    $initArgs = @("init", $vaultPath, "--name", $title)
    if ($Domain -and $Profile) { $initArgs += @("--profile", $Profile) }
    resource-librarian @initArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Error "init failed (exit $LASTEXITCODE)"
        exit $LASTEXITCODE
    }
}

# Register the current directory as a pursuit in its domain library - once.
$here = (Get-Location).Path
if ($Domain -and -not $NoProject -and -not $here.StartsWith($vaultPath, [StringComparison]::OrdinalIgnoreCase)) {
    $projectNote = Join-Path $vaultPath "Projects\$Project.md"
    if (Test-Path $projectNote) {
        Write-Host "Pursuit '$Project' is already in $Domain"
    } else {
        $kind = "project"
        $profileRecord = Join-Path $vaultPath ".librarian\profile.json"
        if (Test-Path $profileRecord) {
            $recorded = (Get-Content $profileRecord -Raw | ConvertFrom-Json).pursuit_kind
            if ($recorded) { $kind = $recorded }
        }
        Write-Host "Registering '$Project' as a $kind in $Domain"
        resource-librarian --vault $vaultPath create_project --name $Project --stage active `
            --summary "Registered from $here" --pursuit-kind $kind --repository $here | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Could not register '$Project' (exit $LASTEXITCODE); the library opens anyway."
        }
    }
}

if ($NoLaunch) {
    Write-Host ""
    Write-Host "Library ready. Launch it later with:"
    Write-Host "  resource-librarian --vault `"$vaultPath`" app --port $Port --open"
    exit 0
}

resource-librarian --vault $vaultPath app --port $Port --open
