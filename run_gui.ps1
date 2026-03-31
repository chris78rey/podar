$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw = $null

try {
    $pythonw = (Get-Command pythonw.exe -ErrorAction Stop).Source
} catch {
    $pythonw = "C:\Program Files\Python310\pythonw.exe"
}

if (-not (Test-Path $pythonw)) {
    throw "No se encontro pythonw.exe. Revisa la instalacion de Python."
}

Start-Process -FilePath $pythonw -ArgumentList @("scripts\gui_launcher_app.py") -WorkingDirectory $root | Out-Null
