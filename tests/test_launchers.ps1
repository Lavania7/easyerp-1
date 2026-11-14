param([switch]$ColdStart)
$ErrorActionPreference='Stop'
$OutputEncoding=[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING='utf-8'
$root=Split-Path $PSScriptRoot -Parent
$config=Get-Content -LiteralPath (Join-Path $root 'config.json') -Raw -Encoding UTF8 | ConvertFrom-Json

function Stop-OwnedService([string]$RecordFile,[string]$Expected) {
    if (-not (Test-Path -LiteralPath $RecordFile)) { return }
    $record=Get-Content -LiteralPath $RecordFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $proc=Get-CimInstance Win32_Process -Filter "ProcessId=$($record.pid)"
    if ($proc) {
        if ($proc.CommandLine -notlike "*$Expected*") { throw 'Refuse to stop an unexpected process' }
        Stop-Process -Id $record.pid
    }
}

function Run-Launcher([string]$Name) {
    # Process.WaitForExit waits for the EXE only, unlike Start-Process -Wait's whole process tree.
    $info=New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName=Join-Path (Join-Path $root 'bin') $Name
    $info.Arguments='--check'
    $info.WorkingDirectory=$root
    $info.UseShellExecute=$false
    $info.CreateNoWindow=$true
    $proc=[System.Diagnostics.Process]::Start($info)
    if (-not $proc.WaitForExit(180000)) { throw "$Name timed out" }
    if ($proc.ExitCode -ne 0) { throw "$Name exited with error $($proc.ExitCode)" }
    return $proc.ExitCode
}

if ($ColdStart) {
Stop-OwnedService (Join-Path $root 'var\frontend.json') (Join-Path $root 'app\server.py')
Stop-OwnedService (Join-Path $root '.secrets\pgadmin-runtime.json') 'pgAdmin 4\web\pgAdmin4.py'
& $config.python (Join-Path $root 'tools\easyerp.py') stop
if ($LASTEXITCODE -ne 0) { throw 'Could not stop the project database for cold-start testing' }
}
$backendExit=Run-Launcher 'sqlview.exe'
$frontendExit=Run-Launcher 'dashboard.exe'
$before=Get-Content -LiteralPath (Join-Path $root '.secrets\pgadmin-runtime.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$backendRepeat=Run-Launcher 'sqlview.exe'
$frontendRepeat=Run-Launcher 'dashboard.exe'
$after=Get-Content -LiteralPath (Join-Path $root '.secrets\pgadmin-runtime.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($before.pid -ne $after.pid) { throw 'Repeated backend start created a different service process' }
$front=Invoke-RestMethod -Uri 'http://127.0.0.1:8092/api/health' -TimeoutSec 5
if (-not $front.ok) { throw 'Frontend health check failed' }
& $config.python (Join-Path $root 'tests\test_backend_api.py')
if ($LASTEXITCODE -ne 0) { throw 'pgAdmin query tool verification failed' }
[ordered]@{
    at=(Get-Date).ToString('o')
    status='PASS'
    cold_start_requested=[bool]$ColdStart
    backend_start_exit=$backendExit
    frontend_start_exit=$frontendExit
    backend_repeat_exit=$backendRepeat
    frontend_repeat_exit=$frontendRepeat
    existing_backend_process_reused=$true
    frontend_ready=$true
    database_auto_start=$true
    sql_query_tool='PASS'
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root 'reports\launcher-tests.json') -Encoding UTF8
Write-Output 'PASS: both bin EXEs start, repeated start, frontend health and actual pgAdmin SQL query.'
