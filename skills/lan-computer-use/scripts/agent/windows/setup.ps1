# lan-computer-use: ensure the agent runs in the logged-on desktop session of the SSH user.
# Called by cu.py over SSH (session 0); prints "STATE <json>" on success.
#   setup-<build>.ps1 -Hash <build>  [-Idle <minutes>]   start or reuse the agent
#   setup-<build>.ps1 -Stop                               stop the agent and remove this directory
param([string]$Hash = '', [int]$Idle = 30, [switch]$Stop)
$ErrorActionPreference = 'Stop'
$dir = $PSScriptRoot
$stateFile = Join-Path $dir 'state.json'

function Get-AgentState {
    if (-not (Test-Path $stateFile)) { return $null }
    try { $s = Get-Content $stateFile -Raw | ConvertFrom-Json } catch { return $null }
    $p = Get-Process -Id $s.pid -ErrorAction SilentlyContinue
    if ($p -and $p.ProcessName -like 'lcu-agent*') { return $s }
    return $null
}

function Stop-Agent {
    Get-Process -Name 'lcu-agent*' -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path.StartsWith($dir, [StringComparison]::OrdinalIgnoreCase) } |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Remove-Item $stateFile -Force -ErrorAction SilentlyContinue
}

if ($Stop) {
    Stop-Agent
    Start-Sleep -Milliseconds 300
    Set-Location $env:TEMP
    Remove-Item $dir -Recurse -Force -ErrorAction SilentlyContinue
    'STOPPED'
    exit 0
}

$s = Get-AgentState
if ($s -and $s.build -eq $Hash) { 'STATE ' + ($s | ConvertTo-Json -Compress); exit 0 }
Stop-Agent

$exe = Join-Path $dir ("lcu-agent-$Hash.exe")
if (-not (Test-Path $exe)) {
    Get-ChildItem $dir -Include 'lcu-agent-*.exe', 'agent-*.cs', 'setup-*.ps1' -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notlike "*-$Hash.*" } | Remove-Item -Force -ErrorAction SilentlyContinue
    $csc = Join-Path ([Runtime.InteropServices.RuntimeEnvironment]::GetRuntimeDirectory()) 'csc.exe'
    if (-not (Test-Path $csc)) { $csc = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe" }
    # /noconfig: csc.rsp would add some of these again (CS1703), so every reference is explicit
    $refs = 'System', 'System.Core', 'UIAutomationClient', 'UIAutomationTypes', 'WindowsBase', 'System.Drawing', 'System.Web.Extensions', 'System.Windows.Forms' | ForEach-Object {
        $a = [Reflection.Assembly]::LoadWithPartialName($_)
        if (-not $a) { throw "assembly $_ not found" }
        '/r:' + $a.Location
    }
    $out = & $csc /noconfig /nologo /target:winexe /platform:anycpu /optimize+ ("/out:$exe") @refs (Join-Path $dir "agent-$Hash.cs") 2>&1
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $exe)) { 'COMPILE-ERROR'; $out | Where-Object { $_ -match 'error' } | Select-Object -First 15; exit 3 }
}

if (-not (Get-Process -Name explorer -ErrorAction SilentlyContinue | Where-Object { $_.SessionId -ne 0 })) {
    'NO-DESKTOP: nobody is logged on to the desktop (agent needs an interactive session)'; exit 4
}

# A scheduled task with an interactive principal is the supported way from session 0 into the user's desktop.
$name = 'lan-computer-use-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
$action = New-ScheduledTaskAction -Execute $exe -Argument "--idle $Idle --build $Hash" -WorkingDirectory $dir
$principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $name -Action $action -Principal $principal -Settings $settings -Force | Out-Null
try {
    Start-ScheduledTask -TaskName $name
    $deadline = (Get-Date).AddSeconds(15)
    while ((Get-Date) -lt $deadline) {
        $s = Get-AgentState
        if ($s -and $s.build -eq $Hash) { 'STATE ' + ($s | ConvertTo-Json -Compress); exit 0 }
        Start-Sleep -Milliseconds 150
    }
    'START-TIMEOUT: agent did not report within 15 s'; exit 5
} finally {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
}
