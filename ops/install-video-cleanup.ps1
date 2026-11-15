param([switch]$Enable)
$ErrorActionPreference = 'Stop'
$sourceRoot = Split-Path -Parent $PSScriptRoot
$taskRoot = 'E:\codex-build\postiz-item79\video-cleanup'
$taskName = 'Item79-PublishedVideo-Cleanup'
$pythonPath = (Get-Command python.exe).Source
$pythonWindowless = Join-Path (Split-Path $pythonPath) 'pythonw.exe'
if (!(Test-Path -LiteralPath $pythonWindowless)) { throw 'pythonw.exe unavailable' }
if (!(Test-Path -LiteralPath (Join-Path $taskRoot 'local-map.json'))) { throw 'Enroll exact local copies first' }
New-Item -ItemType Directory -Force -Path $taskRoot | Out-Null
$userSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& icacls.exe $taskRoot '/inheritance:r' '/grant:r' "*${userSid}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Private cleanup ACL failed' }
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'item79-video-cleanup.py') -Destination (Join-Path $taskRoot 'runner.py')
$userName = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $pythonWindowless -Argument ('"' + (Join-Path $taskRoot 'runner.py') + '" --apply') -WorkingDirectory $taskRoot
$trigger = New-ScheduledTaskTrigger -Daily -At '05:10'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew -Hidden
$principal = New-ScheduledTaskPrincipal -UserId $userName -LogonType Interactive -RunLevel Limited
$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Item79: public7days, no reservation references, verified independent OVH bytes; exact server and enrolled PC upload-copy cleanup. Requires this user logged in. Private reports on E:.'
if (!$Enable) { $task.Settings.Enabled = $false }
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) { throw 'Existing cleanup task: inspect before replacing' }
Register-ScheduledTask -TaskName $taskName -InputObject $task | Out-Null
[ordered]@{
    taskName = $taskName
    enabled = [bool]$Enable
    runnerSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $taskRoot 'runner.py')).Hash.ToLowerInvariant()
    localMapSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $taskRoot 'local-map.json')).Hash.ToLowerInvariant()
    gateSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $PSScriptRoot 'item79-video-gate.cjs')).Hash.ToLowerInvariant()
    installedAt = [DateTimeOffset]::Now.ToString('o')
    sourceRoot = $sourceRoot
} | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $taskRoot 'installation.json')
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName,State
