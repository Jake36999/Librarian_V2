<#
.SYNOPSIS
    Runs the explicit, per-user Librarian Host tray companion on Windows.

.DESCRIPTION
    This is deliberately a small, user-controlled desktop companion rather
    than a Windows service.  It starts a Core only when Open is chosen and it
    stops one only after an explicit Stop or Quit confirmation.  In
    particular, it has no client reference counting, browser-tab liveness
    tracking, or idle shutdown policy.

    The Core itself remains the authority for a vault.  This script calls the
    normal `librarian host` commands, so it cannot bypass the vault lease,
    writer drain, active-work warning, or Obsidian-managed-secret policy.
#>
[CmdletBinding()]
param(
    # The bootstrapper supplies the exact release-local executable.  Source
    # installs can omit this and use their adjacent .venv or PATH command.
    [string]$LibrarianExe = "",
    # Optional starting selection.  Passing it does *not* start a Core.
    [string]$Vault = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    throw "LibrarianHost is a Windows tray companion. Use 'librarian host' on this platform."
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Resolve-LibrarianExe {
    param([string]$Requested)

    if ($Requested) {
        if (-not (Test-Path -LiteralPath $Requested -PathType Leaf)) {
            throw "The supplied Librarian executable does not exist: $Requested"
        }
        return [IO.Path]::GetFullPath($Requested)
    }

    $sourceRoot = Split-Path -Parent $PSScriptRoot
    $local = Join-Path $sourceRoot ".venv\Scripts\librarian.exe"
    if (Test-Path -LiteralPath $local -PathType Leaf) { return $local }

    foreach ($name in @("librarian.exe", "resource-librarian.exe")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command -and $command.Source) { return $command.Source }
    }
    throw "Librarian is not installed. Run Setup.bat or install a verified release first."
}

$script:Command = Resolve-LibrarianExe $LibrarianExe
$script:SelectedVault = if ($Vault) { [IO.Path]::GetFullPath($Vault) } else { "" }
$script:Tray = $null
$script:TrayTimer = $null
$script:AppContext = $null

function Invoke-LibrarianHost {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    # The CLI returns one JSON document.  Capturing it here keeps errors in a
    # visible dialog rather than a hidden console, while no secret-bearing
    # connection record is ever rendered by this companion.
    $raw = (& $script:Command @Arguments 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Librarian command failed:`n$raw"
    }
    try {
        return $raw | ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw "Librarian returned an unexpected response:`n$raw"
    }
}

function Show-HostError {
    param([string]$Message)
    [void][System.Windows.Forms.MessageBox]::Show(
        $Message, "Librarian Host", [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error)
}

function Show-HostInfo {
    param([string]$Message, [string]$Title = "Librarian Host")
    [void][System.Windows.Forms.MessageBox]::Show(
        $Message, $Title, [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information)
}

function Get-ReplyProperty {
    param($Object, [Parameter(Mandatory = $true)][string]$Name)

    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Select-LibrarianVault {
    param([string]$Prompt = "Choose the Librarian vault to manage.")

    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = $Prompt
    $dialog.ShowNewFolderButton = $true
    if ($script:SelectedVault -and (Test-Path -LiteralPath $script:SelectedVault -PathType Container)) {
        $dialog.SelectedPath = $script:SelectedVault
    }
    try {
        if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { return "" }
        $script:SelectedVault = [IO.Path]::GetFullPath($dialog.SelectedPath)
        return $script:SelectedVault
    } finally {
        $dialog.Dispose()
    }
}

function Get-LaunchVault {
    # Opening is the only action that may start a Core, so a chosen path need
    # not already appear in Host status.  The HostManager will still acquire
    # the vault lease or attach to an existing compatible Core.
    if ($script:SelectedVault) { return $script:SelectedVault }
    return Select-LibrarianVault "Choose the Librarian vault to open."
}

function Get-ManagedVault {
    param([switch]$AllowPicker)

    try {
        $status = Invoke-LibrarianHost @("host", "status")
    } catch {
        Show-HostError $_.Exception.Message
        return ""
    }
    $cores = @(Get-ReplyProperty $status "cores")
    if ($script:SelectedVault) {
        $selected = [IO.Path]::GetFullPath($script:SelectedVault)
        foreach ($core in $cores) {
            $coreVault = Get-ReplyProperty $core "vault"
            if ($coreVault -and [IO.Path]::GetFullPath([string]$coreVault) -eq $selected) {
                return $selected
            }
        }
        # A remembered selection is not proof that its Core is still live.
        # Do not send Stop/Restart to a stale path while another vault runs.
        $script:SelectedVault = ""
    }
    $onlyVault = if ($cores.Count -eq 1) { Get-ReplyProperty $cores[0] "vault" } else { $null }
    if ($onlyVault) {
        $script:SelectedVault = [string]$onlyVault
        return $script:SelectedVault
    }
    if ($cores.Count -gt 1 -and -not $AllowPicker) {
        Show-HostInfo "More than one Core is running. Choose a vault before managing it."
        return ""
    }
    if ($AllowPicker) { return Select-LibrarianVault }
    return ""
}

function Update-TrayState {
    # This timer only reports state.  It never starts, stops, reaps, or
    # otherwise changes a Core's lifetime.
    try {
        $status = Invoke-LibrarianHost @("host", "status")
        $running = [string](Get-ReplyProperty $status "status") -eq "running"
        $count = @(Get-ReplyProperty $status "cores").Count
        $plural = if ($count -eq 1) { "" } else { "s" }
        $suffix = if ($running) { "running ($count Core$plural)" } else { "stopped" }
        $script:Tray.Text = "Librarian Host - $suffix"
        $script:Tray.Icon = if ($running) {
            [System.Drawing.SystemIcons]::Application
        } else {
            [System.Drawing.SystemIcons]::Information
        }
    } catch {
        # The user can inspect a real diagnostic with Status; showing an
        # error icon is preferable to retrying or manipulating processes.
        $script:Tray.Text = "Librarian Host - status unavailable"
        $script:Tray.Icon = [System.Drawing.SystemIcons]::Error
    }
}

function Open-Librarian {
    $target = Get-LaunchVault
    if (-not $target) { return }
    try {
        $reply = Invoke-LibrarianHost @("host", "start", "--vault", $target)
        $process = Get-ReplyProperty $reply "process"
        $url = Get-ReplyProperty $process "url"
        if ($url) {
            Start-Process ([string]$url)
            Update-TrayState
            return
        }
        $detail = Get-ReplyProperty $reply "detail"
        if (-not $detail) { $detail = "The Core did not return a browser URL." }
        Show-HostInfo $detail
    } catch {
        Show-HostError $_.Exception.Message
    }
}

function Show-LibrarianStatus {
    try {
        $reply = Invoke-LibrarianHost @("host", "status")
        Show-HostInfo ($reply | ConvertTo-Json -Depth 6)
        Update-TrayState
    } catch {
        Show-HostError $_.Exception.Message
    }
}

function Show-LibrarianDoctor {
    try {
        $reply = Invoke-LibrarianHost @("host", "doctor")
        Show-HostInfo ($reply | ConvertTo-Json -Depth 8) "Librarian Host Doctor"
        Update-TrayState
    } catch {
        Show-HostError $_.Exception.Message
    }
}

function Restart-Librarian {
    $target = Get-ManagedVault -AllowPicker
    if (-not $target) { return }
    try {
        $reply = Invoke-LibrarianHost @("host", "restart", "--vault", $target)
        $process = Get-ReplyProperty $reply "process"
        $url = Get-ReplyProperty $process "url"
        if ($url) { Start-Process ([string]$url) }
        $detail = Get-ReplyProperty $reply "detail"
        if ($detail) { Show-HostInfo ([string]$detail) }
        Update-TrayState
    } catch {
        Show-HostError $_.Exception.Message
    }
}

function Stop-Librarian {
    param([switch]$ForQuit)

    try {
        $status = Invoke-LibrarianHost @("host", "status")
    } catch {
        Show-HostError $_.Exception.Message
        return $false
    }
    if (@(Get-ReplyProperty $status "cores").Count -eq 0) {
        if (-not $ForQuit) { Show-HostInfo "There is no running Core to stop." }
        return $true
    }
    $target = Get-ManagedVault -AllowPicker
    if (-not $target) {
        return $false
    }
    $question = if ($ForQuit) {
        "Quit stops the Librarian Core after it flushes its writer queue. Continue?"
    } else {
        "Stop the Librarian Core for:`n$target`n`nClosing browser tabs never stops a Core; this is an explicit stop. Continue?"
    }
    $answer = [System.Windows.Forms.MessageBox]::Show(
        $question, "Librarian Host", [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Warning)
    if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) { return $false }
    try {
        $reply = Invoke-LibrarianHost @("host", "stop", "--vault", $target)
        $stopped = [bool](Get-ReplyProperty $reply "stopped")
        $active = Get-ReplyProperty $reply "active"
        if (-not $stopped -and $active) {
            $force = [System.Windows.Forms.MessageBox]::Show(
                "The Core has active work and refused to stop normally.`n`nForce Quit after recording the active-work warning?",
                "Librarian Host", [System.Windows.Forms.MessageBoxButtons]::YesNo,
                [System.Windows.Forms.MessageBoxIcon]::Warning)
            if ($force -eq [System.Windows.Forms.DialogResult]::Yes) {
                $reply = Invoke-LibrarianHost @("host", "stop", "--vault", $target, "--force")
                $stopped = [bool](Get-ReplyProperty $reply "stopped")
            }
        }
        if (-not $stopped) {
            $detail = Get-ReplyProperty $reply "detail"
            if (-not $detail) { $detail = "The Core is still running." }
            Show-HostInfo $detail
            return $false
        }
        Update-TrayState
        return $true
    } catch {
        Show-HostError $_.Exception.Message
        return $false
    }
}

function Quit-LibrarianHost {
    if (-not (Stop-Librarian -ForQuit)) { return }
    $script:TrayTimer.Stop()
    $script:Tray.Visible = $false
    $script:AppContext.ExitThread()
}

$script:AppContext = New-Object System.Windows.Forms.ApplicationContext
$script:Tray = New-Object System.Windows.Forms.NotifyIcon
$script:Tray.Icon = [System.Drawing.SystemIcons]::Application
$script:Tray.Text = "Librarian Host"
$script:Tray.Visible = $true
$menu = New-Object System.Windows.Forms.ContextMenuStrip
[void]$menu.Items.Add("Open", $null, { Open-Librarian })
[void]$menu.Items.Add("Status", $null, { Show-LibrarianStatus })
[void]$menu.Items.Add("Doctor", $null, { Show-LibrarianDoctor })
[void]$menu.Items.Add("Restart", $null, { Restart-Librarian })
[void]$menu.Items.Add("Stop", $null, { [void](Stop-Librarian) })
[void]$menu.Items.Add("-")
[void]$menu.Items.Add("Quit", $null, { Quit-LibrarianHost })
$script:Tray.ContextMenuStrip = $menu
$script:Tray.add_DoubleClick({ Open-Librarian })

$script:TrayTimer = New-Object System.Windows.Forms.Timer
$script:TrayTimer.Interval = 15000
$script:TrayTimer.add_Tick({ Update-TrayState })
$script:TrayTimer.Start()
Update-TrayState

try {
    [System.Windows.Forms.Application]::Run($script:AppContext)
} finally {
    if ($script:TrayTimer) { $script:TrayTimer.Dispose() }
    if ($script:Tray) { $script:Tray.Dispose() }
    if ($menu) { $menu.Dispose() }
}
