param(
    [Parameter(Position=0)][string]$Action = 'status',
    [Parameter(Position=1)][string]$Value,
    [ValidateSet('easyerp_app','easyerp_read','easyerp_admin')][string]$Role = 'easyerp_app'
)
$ErrorActionPreference = 'Stop'
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = 'utf-8'
$config = Get-Content -LiteralPath (Join-Path $PSScriptRoot '..\config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$python = $config.python
if (-not (Test-Path -LiteralPath $python)) { $python = (Get-Command python -ErrorAction Stop).Source }
$runArgs = @((Join-Path $PSScriptRoot 'easyerp.py'), $Action)
if ($Value) {
    $runArgs += [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($Value))
    $runArgs += '--encoded-value'
}
$runArgs += @('--role', $Role)
& $python @runArgs
if ($LASTEXITCODE -ne 0) { throw "easyERP 操作失败，退出码 $LASTEXITCODE" }
