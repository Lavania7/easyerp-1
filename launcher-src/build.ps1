$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$tempCompiler = Join-Path $env:TEMP ('easyerp-icon-' + [guid]::NewGuid().ToString('N') + '.exe')
try {
    & $compiler /nologo /codepage:65001 /target:exe /reference:System.Drawing.dll "/out:$tempCompiler" (Join-Path $PSScriptRoot 'IconBuilder.cs')
    if ($LASTEXITCODE -ne 0) { throw 'Icon compiler failed' }
    & $tempCompiler (Join-Path $PSScriptRoot 'frontend.ico') '#285947' 'e'
    & $tempCompiler (Join-Path $PSScriptRoot 'backend.ico') '#326690' 'SQL'
    & $compiler /nologo /codepage:65001 /target:winexe /platform:anycpu /reference:System.Windows.Forms.dll /reference:System.Drawing.dll "/win32icon:$(Join-Path $PSScriptRoot 'frontend.ico')" "/out:$(Join-Path $root '启动前端.exe')" (Join-Path $PSScriptRoot 'Launcher.cs')
    if ($LASTEXITCODE -ne 0) { throw 'Frontend compiler failed' }
    & $compiler /nologo /codepage:65001 /target:winexe /platform:anycpu /define:BACKEND /reference:System.Windows.Forms.dll /reference:System.Drawing.dll "/win32icon:$(Join-Path $PSScriptRoot 'backend.ico')" "/out:$(Join-Path $root '启动后端SQL.exe')" (Join-Path $PSScriptRoot 'Launcher.cs')
    if ($LASTEXITCODE -ne 0) { throw 'Backend compiler failed' }
} finally {
    if (Test-Path -LiteralPath $tempCompiler) { Remove-Item -LiteralPath $tempCompiler }
}
