param(
    [Parameter(Mandatory=$true)][string]$ArgumentsBase64,
    [ValidateRange(5,300)][int]$TimeoutSeconds = 60
)
# Invoke once in the current user's interactive Windows session, never SYSTEM.
$ErrorActionPreference = 'Stop'
$json = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($ArgumentsBase64))
if (!$json.TrimStart().StartsWith('[')) { throw 'Supply a JSON array of agent-desktop arguments.' }
$arguments = ConvertFrom-Json $json
if (!$arguments.Count) { throw 'Supply a JSON array of agent-desktop arguments.' }
foreach ($argument in $arguments) { if ($argument -isnot [string]) { throw 'Arguments must be strings.' } }
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$taskName = 'agent-desktop-once-' + [Guid]::NewGuid().ToString('N')
$jobDir = Join-Path $env:LOCALAPPDATA $taskName
New-Item -ItemType Directory $jobDir | Out-Null
$registered = $false
try {
    $entry = (Get-Command agent-desktop.cmd -ErrorAction Stop).Source
    # Use the bundled native binary, avoiding cmd.exe argument expansion.
    $package = Join-Path (Split-Path $entry) 'node_modules\agent-desktop'
    $architecture = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64') { 'arm64' } else { 'x64' }
    $bins = @(Get-ChildItem $package -Recurse -Filter ('agent-desktop-win32-' + $architecture + '.exe'))
    if ($bins.Count -ne 1) { throw 'Cannot resolve a unique native agent-desktop binary.' }
    @{ binary=$bins[0].FullName; arguments=[string[]]$arguments } | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $jobDir 'request.json') -Encoding UTF8
    @'
$ErrorActionPreference = 'Stop'
$dir = Split-Path $MyInvocation.MyCommand.Path
try {
    $request = Get-Content (Join-Path $dir 'request.json') -Raw | ConvertFrom-Json
    $argv = @($request.arguments)
    & $request.binary @argv 1> (Join-Path $dir 'stdout.txt') 2> (Join-Path $dir 'stderr.txt')
    $LASTEXITCODE | Set-Content (Join-Path $dir 'exit.pending')
} catch {
    $_ | Out-String | Set-Content (Join-Path $dir 'stderr.txt')
    1 | Set-Content (Join-Path $dir 'exit.pending')
}
Move-Item (Join-Path $dir 'exit.pending') (Join-Path $dir 'exit.txt')
'@ | Set-Content (Join-Path $jobDir 'run.ps1') -Encoding UTF8
    $action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\conhost.exe" -Argument ('--headless "' + "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" + '" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + (Join-Path $jobDir 'run.ps1') + '"')
    $principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Seconds $TimeoutSeconds)
    Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings | Out-Null
    $registered = $true
    Start-ScheduledTask -TaskName $taskName
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while (!(Test-Path (Join-Path $jobDir 'exit.txt'))) {
        if ([DateTime]::UtcNow -gt $deadline) { throw 'Interactive command timed out. Delivery is unknown; observe before retrying any action.' }
        Start-Sleep -Milliseconds 200
    }
    Get-Content (Join-Path $jobDir 'stdout.txt') -Raw -ErrorAction SilentlyContinue
    $stderr = Get-Content (Join-Path $jobDir 'stderr.txt') -Raw -ErrorAction SilentlyContinue
    if ($stderr) { [Console]::Error.Write($stderr) }
    $result = [int](Get-Content (Join-Path $jobDir 'exit.txt'))
} finally {
    if ($registered) {
        Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    }
    Remove-Item $jobDir -Recurse -Force -ErrorAction SilentlyContinue
}
exit $result
