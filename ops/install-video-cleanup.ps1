param([switch]$Enable, [switch]$UpgradeToLocalOnly)
$ErrorActionPreference = 'Stop'
$sourceRoot = Split-Path -Parent $PSScriptRoot
$taskRoot = 'E:\codex-build\postiz-item79\video-cleanup'
$taskName = 'Item79-PublishedVideo-Cleanup'
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask -and !$UpgradeToLocalOnly) { throw 'Existing cleanup task: use explicit reviewed UpgradeToLocalOnly' }
$pythonPath = (Get-Command python.exe).Source
$pythonWindowless = Join-Path (Split-Path $pythonPath) 'pythonw.exe'
if (!(Test-Path -LiteralPath $pythonWindowless)) { throw 'pythonw.exe unavailable' }
if (!(Test-Path -LiteralPath (Join-Path $taskRoot 'local-map.json'))) { throw 'Enroll exact local copies first' }
New-Item -ItemType Directory -Force -Path $taskRoot | Out-Null
$userSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& icacls.exe $taskRoot '/inheritance:r' '/grant:r' "*${userSid}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Private cleanup ACL failed' }
$userName = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
if ($existingTask) {
    $taskUserSid = ([System.Security.Principal.NTAccount]::new($existingTask.Principal.UserId)).Translate([System.Security.Principal.SecurityIdentifier]).Value
    if ($taskUserSid -ne $userSid -or $existingTask.Actions.WorkingDirectory -ne $taskRoot -or $existingTask.Actions.Execute -ne $pythonWindowless) { throw 'Task identity or scope changed' }
    if ($existingTask.State -eq 'Running') { throw 'Existing cleanup still running' }
    Disable-ScheduledTask -TaskName $taskName | Out-Null
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'item79-video-cleanup.py') -Destination (Join-Path $taskRoot 'runner.py')
$action = New-ScheduledTaskAction -Execute $pythonWindowless -Argument ('"' + (Join-Path $taskRoot 'runner.py') + '" --local-only --apply') -WorkingDirectory $taskRoot
$triggers = @((New-ScheduledTaskTrigger -Daily -At '05:40'), (New-ScheduledTaskTrigger -AtLogOn -User $userName))
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew -Hidden -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 15)
$principal = New-ScheduledTaskPrincipal -UserId $userName -LogonType Interactive -RunLevel Limited
$task = New-ScheduledTask -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Description 'Item79 local copies only: consume verified completed Contabo removals, recheck public/references/OVH bytes. Daily05:40KST and at logon; restricted reader/verifier keys. Server cleanup is independent systemd. Private reports E:.'
if (!$Enable) { $task.Settings.Enabled = $false }
Register-ScheduledTask -TaskName $taskName -InputObject $task -Force:$UpgradeToLocalOnly | Out-Null
[ordered]@{
    taskName = $taskName
    enabled = [bool]$Enable
    mode = 'LOCAL_ONLY'
    runnerSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $taskRoot 'runner.py')).Hash.ToLowerInvariant()
    localMapSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $taskRoot 'local-map.json')).Hash.ToLowerInvariant()
    gateSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $PSScriptRoot 'item79-video-gate.cjs')).Hash.ToLowerInvariant()
    installedAt = [DateTimeOffset]::Now.ToString('o')
    sourceRoot = $sourceRoot
} | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $taskRoot 'installation.json')
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName,State
