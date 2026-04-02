$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$exePath = Join-Path $root "dist\OrganizaPlanillas\OrganizaPlanillas.exe"
if (-not (Test-Path $exePath)) {
    Write-Host "No se encontro el exe; generando primero el build portable."
    & powershell -ExecutionPolicy Bypass -File (Join-Path $root "build_organiza_planillas.ps1")
}

$iscc = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) {
    throw "No se encontro ISCC.exe. Instala Inno Setup 6 para generar el instalador."
}

& $iscc .\installer\OrganizaPlanillas.iss
Write-Host "Instalador generado en installer_output\OrganizaPlanillas_Setup.exe"
