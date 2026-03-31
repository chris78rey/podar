$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    python -m pip install pyinstaller
}

Remove-Item -Recurse -Force .\build, .\dist -ErrorAction SilentlyContinue

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name PODA `
    --paths scripts `
    --collect-submodules jpype `
    --collect-submodules jaydebeapi `
    --add-data ".env.example;." `
    --add-data "jdbc\ojdbc8.jar;jdbc" `
    scripts\gui_launcher_app.py

Write-Host "Build terminado en dist\PODA"

$iscc = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
if (Test-Path $iscc) {
    & $iscc .\installer\PODA.iss
    Write-Host "Instalador generado en installer_output\PODA_Setup.exe"
} else {
    Write-Host "ISCC.exe no encontrado; se omite el instalador."
}
