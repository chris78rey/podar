$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    python -m pip install pyinstaller
}

try {
    python -c "import openpyxl"
} catch {
}
if ($LASTEXITCODE -ne 0) {
    python -m pip install openpyxl
}

Remove-Item -Recurse -Force .\build, .\dist -ErrorAction SilentlyContinue

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name OrganizaPlanillas `
    --paths scripts `
    --collect-submodules openpyxl `
    scripts\organiza_planillas_app.py

Write-Host "Build terminado en dist\OrganizaPlanillas"
