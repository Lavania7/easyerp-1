$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$desktop=[Environment]::GetFolderPath('Desktop')
$shell=New-Object -ComObject WScript.Shell
$result=@()
foreach($item in @(
    @('easyERP-前端工作台.lnk','启动前端.exe','打开 easyERP 经营工作台'),
    @('easyERP-后端SQL.lnk','启动后端SQL.exe','打开 easyERP 数据库与 SQL 查询工具')
)) {
    $path=Join-Path $desktop $item[0]
    $target=Join-Path $root $item[1]
    $shortcut=$shell.CreateShortcut($path)
    if((Test-Path -LiteralPath $path) -and $shortcut.TargetPath -ne $target){throw '桌面已存在指向其他程序的同名快捷方式，未覆盖。'}
    $shortcut.TargetPath=$target
    $shortcut.WorkingDirectory=$root
    $shortcut.Description=$item[2]
    $shortcut.IconLocation=$target+',0'
    $shortcut.WindowStyle=1
    $shortcut.Save()
    $verify=$shell.CreateShortcut($path)
    if($verify.TargetPath -ne $target){throw '快捷方式目标验证失败'}
    $result+=[ordered]@{path=$path;target=$target;working_directory=$root}
}
$result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root 'reports\shortcuts.json') -Encoding UTF8
$result | ForEach-Object {Write-Output $_.path}
