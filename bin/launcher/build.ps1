$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$bin = Join-Path $root 'bin'
New-Item -ItemType Directory -Path $bin -Force | Out-Null
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$tempCompiler = Join-Path $env:TEMP ('easyerp-icon-' + [guid]::NewGuid().ToString('N') + '.exe')
try {
    & $compiler /nologo /codepage:65001 /target:exe /reference:System.Drawing.dll "/out:$tempCompiler" (Join-Path $PSScriptRoot 'IconBuilder.cs')
    if ($LASTEXITCODE -ne 0) { throw 'Icon compiler failed' }
    & $tempCompiler $PSScriptRoot
    if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed' }
    $icons = Join-Path $bin 'icons'
    New-Item -ItemType Directory -Path $icons -Force | Out-Null
    foreach ($item in @(@('frontend.ico','dashboard.ico'),@('backend.ico','sqlview.ico'),@('dashboard.png','dashboard.png'),@('sqlview.png','sqlview.png'),@('icon-preview.png','preview.png'))) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $item[0]) -Destination (Join-Path $icons $item[1]) -Force
    }
    & $compiler /nologo /codepage:65001 /target:winexe /platform:anycpu /reference:System.Windows.Forms.dll /reference:System.Drawing.dll "/win32icon:$(Join-Path $PSScriptRoot 'frontend.ico')" "/out:$(Join-Path $bin 'dashboard.exe')" (Join-Path $PSScriptRoot 'Launcher.cs')
    if ($LASTEXITCODE -ne 0) { throw 'Frontend compiler failed' }
    & $compiler /nologo /codepage:65001 /target:winexe /platform:anycpu /define:BACKEND /reference:System.Windows.Forms.dll /reference:System.Drawing.dll "/win32icon:$(Join-Path $PSScriptRoot 'backend.ico')" "/out:$(Join-Path $bin 'sqlview.exe')" (Join-Path $PSScriptRoot 'Launcher.cs')
    if ($LASTEXITCODE -ne 0) { throw 'Backend compiler failed' }
} finally {
    if (Test-Path -LiteralPath $tempCompiler) { Remove-Item -LiteralPath $tempCompiler }
}
