param([switch]$UseCurrentProject,[string]$BackupDirectory)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$desktop=[Environment]::GetFolderPath('Desktop')
if(-not $desktop){throw 'Desktop path unavailable'}
if(-not $BackupDirectory){$BackupDirectory=Join-Path $root ('backups\icon-shortcuts-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))}
New-Item -ItemType Directory -Path $BackupDirectory -Force | Out-Null
$shell=New-Object -ComObject WScript.Shell
if(-not ('EasyErpShellIconRefresh' -as [type])) {
    Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class EasyErpShellIconRefresh { [DllImport("shell32.dll", CharSet=CharSet.Unicode)] public static extern void SHChangeNotify(uint e, uint f, string a, IntPtr b); }'
}
$result=@()
foreach($item in @(@('easyERP-Dashboard.lnk','dashboard.exe','dashboard.ico'),@('easyERP-SQLview.lnk','sqlview.exe','sqlview.ico'))) {
    $path=Join-Path $desktop $item[0]
    $exe=Join-Path (Join-Path $root 'bin') $item[1]
    $icon=Join-Path $root ('bin\icons\'+$item[2])
    if(-not (Test-Path -LiteralPath $exe)){throw ('Missing EXE: '+$exe)}
    if(-not (Test-Path -LiteralPath $icon)){throw ('Missing icon: '+$icon)}
    $exists=Test-Path -LiteralPath $path
    $shortcut=$shell.CreateShortcut($path)
    $legacyTarget=Join-Path $root $item[1]
    if($exists -and -not $UseCurrentProject -and $shortcut.TargetPath -notin @($exe,$legacyTarget)){throw '同名快捷方式指向其他项目，请核对后明确选择 -UseCurrentProject。'}
    if($exists){Copy-Item -LiteralPath $path -Destination (Join-Path $BackupDirectory $item[0]) -Force}
    if($UseCurrentProject -or -not $exists -or $shortcut.TargetPath -eq $legacyTarget) {
        $shortcut.TargetPath=$exe
        $shortcut.WorkingDirectory=$root
    }
    $shortcut.IconLocation=$icon+',0'
    $shortcut.Save()
    $verify=$shell.CreateShortcut($path)
    if($verify.IconLocation -ne $icon+',0'){throw 'Shortcut icon verification failed'}
    if($UseCurrentProject -and ($verify.TargetPath -ne $exe -or $verify.WorkingDirectory -ne $root)){throw 'Shortcut target verification failed'}
    foreach($changed in @($path,$exe,$icon)){[EasyErpShellIconRefresh]::SHChangeNotify(0x2000,0x1005,$changed,[IntPtr]::Zero)}
    $result+=[ordered]@{path=$path;target=$verify.TargetPath;working_directory=$verify.WorkingDirectory;icon=$verify.IconLocation;status='PASS'}
}
foreach($directory in @($root,(Join-Path $root 'bin\icons'),$desktop)) {
    [EasyErpShellIconRefresh]::SHChangeNotify(0x1000,0x1005,$directory,[IntPtr]::Zero)
}
$result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $root 'reports\icon-shortcuts.json') -Encoding UTF8
$result | ConvertTo-Json -Depth 4
