param([switch]$OpenBrowser)
$ErrorActionPreference = 'Stop'
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$root = Split-Path $PSScriptRoot -Parent
$url = 'http://127.0.0.1:8092'
$config = Get-Content -LiteralPath (Join-Path $root 'config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
& (Join-Path $root 'tools\easyerp-db.ps1') start | Out-Null
function Test-Frontend {
    try {
        $health = Invoke-RestMethod -Uri "$url/api/health" -TimeoutSec 2
        return ($health.ok -eq $true -and $health.query_read_only -eq $true -and $health.manual_entry -eq $true -and $health.import_interface -eq $true)
    } catch { return $false }
}
if (-not (Test-Frontend)) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort 8092 -ErrorAction SilentlyContinue
    if ($listener) { throw '8092 端口已被占用，请检查前端日志。' }
    Start-Process -FilePath $config.python -ArgumentList @((Join-Path $root 'app\server.py')) -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $root 'var\log\frontend-console.log') -RedirectStandardError (Join-Path $root 'var\log\frontend-error.log') | Out-Null
    $ready = $false
    for ($attempt=0; $attempt -lt 20; $attempt++) {
        if (Test-Frontend) { $ready=$true; break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw '前端未能启动，请检查 var\log\frontend-error.log。' }
}
if ($OpenBrowser) { Start-Process $url }
Write-Output "easyERP 前端已就绪：$url"
