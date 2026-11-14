$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $root
$query = @'
SELECT count(*) FROM finance."人员档案表";
'@
$output = & .\tools\easyerp-db.ps1 query $query -Role easyerp_read
if (($output -join '').Trim() -ne '0') { throw 'PowerShell quoted Chinese SQL failed' }
& .\tools\easyerp-db.ps1 start
& .\tools\easyerp-db.ps1 start
Write-Output 'PASS Windows PowerShell query and repeated start'
