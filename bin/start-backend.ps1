param([switch]$OpenBrowser)
$ErrorActionPreference = 'Stop'
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = 'utf-8'
$root = Split-Path $PSScriptRoot -Parent
$config = Get-Content -LiteralPath (Join-Path $root 'config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$runArgs = @((Join-Path $PSScriptRoot 'backend.py'))
if ($OpenBrowser) { $runArgs += '--open-browser' }
& $config.python @runArgs
if ($LASTEXITCODE -ne 0) { throw 'SQL 界面启动失败，请检查 var\pgadmin 中的日志。' }
