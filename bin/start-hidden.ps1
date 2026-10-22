$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$log = Join-Path $root 'var\log\startup.log'
try {
    & (Join-Path $PSScriptRoot 'easyerp-db.ps1') start *>> $log
} catch {
    $_ | Out-File -FilePath $log -Append -Encoding utf8
    exit 1
}
