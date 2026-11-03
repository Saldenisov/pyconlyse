param(
    [string]$Python = 'C:\Users\elyse\miniconda3\envs\pyconlyse312\pythonw.exe',
    [string]$Directory = 'F:\ELYSE_Telemetry_Server\cooling_alert'
)
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'elyse_cooling_alert.py'
if (!(Test-Path -LiteralPath $source) -or !(Test-Path -LiteralPath $Python)) { throw 'Alarm source or Python missing' }
$helpers = @(
    @{ Source = (Join-Path $PSScriptRoot 'elyse_cooling_temperature.py'); Name = 'elyse_cooling_temperature.py' },
    @{ Source = (Join-Path (Split-Path $PSScriptRoot) 'web\frontend\src\coolingTemperaturePolicy.json'); Name = 'coolingTemperaturePolicy.json' }
)
foreach ($item in $helpers) {
    if (!(Test-Path -LiteralPath $item.Source)) { throw ('Missing alarm helper: ' + $item.Source) }
}
New-Item -ItemType Directory -Path $Directory -Force | Out-Null
$target = Join-Path $Directory 'elyse_cooling_alert.py'
if (Test-Path -LiteralPath $target) {
    $stamp = Get-Date -Format 'yyyyMMddTHHmmss'
    Copy-Item -LiteralPath $target -Destination ($target + '.' + $stamp + '.backup')
}
Copy-Item -LiteralPath $source -Destination $target
foreach ($item in $helpers) {
    $destination = Join-Path $Directory $item.Name
    if (Test-Path -LiteralPath $destination) { Copy-Item -LiteralPath $destination -Destination ($destination + '.' + (Get-Date -Format 'yyyyMMddTHHmmss') + '.backup') }
    Copy-Item -LiteralPath $item.Source -Destination $destination
}
$shell = New-Object -ComObject WScript.Shell
foreach ($folder in @([Environment]::GetFolderPath('Startup'), [Environment]::GetFolderPath('Desktop'))) {
    $linkPath = Join-Path $folder 'ELYSE Cooling Alert.lnk'
    if (Test-Path -LiteralPath $linkPath) { Copy-Item -LiteralPath $linkPath -Destination ($linkPath + '.backup') }
    $shortcut = $shell.CreateShortcut($linkPath)
    $shortcut.TargetPath = $Python
    $shortcut.Arguments = '"' + $target + '" --directory "' + $Directory + '"' + $(if ($folder -eq [Environment]::GetFolderPath('Desktop')) { ' --show' } else { '' })
    $shortcut.WorkingDirectory = $Directory
    $shortcut.Description = 'Read-only Tango cooling alarm; sound and Windows window, independent of browser'
    $shortcut.Save()
}
Start-Process -FilePath $Python -ArgumentList @('"' + $target + '"', '--directory', '"' + $Directory + '"', '--show') -WorkingDirectory $Directory -WindowStyle Hidden
Write-Output ('Installed read-only operator alarm: ' + $target)
