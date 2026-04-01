$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Resolve-JdkHome {
    $candidates = @(
        $env:JAVA_HOME,
        "C:\Program Files\Java\jdk-20",
        "C:\Program Files\Java\latest"
    ) | Where-Object { $_ -and (Test-Path $_) }
    foreach ($candidate in $candidates) {
        $jlink = Join-Path $candidate "bin\jlink.exe"
        if (Test-Path $jlink) {
            return (Get-Item $candidate).FullName
        }
    }
    throw "No se encontro un JDK con jlink para generar el runtime portable."
}

function Build-JavaRuntime {
    $jdkHome = Resolve-JdkHome
    $jlink = Join-Path $jdkHome "bin\jlink.exe"
    $runtimeRoot = Join-Path $root "build\poda-runtime"
    $runtimeDest = Join-Path $root "dist\PODA\jre"
    Remove-Item -Recurse -Force $runtimeRoot -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $runtimeDest -ErrorAction SilentlyContinue

    & $jlink `
        --add-modules java.base,java.sql,java.naming,java.management,java.security.jgss,java.security.sasl,jdk.zipfs `
        --strip-debug `
        --no-man-pages `
        --no-header-files `
        --compress=2 `
        --output $runtimeRoot

    if (-not (Test-Path (Join-Path $runtimeRoot "bin\server\jvm.dll"))) {
        throw "El runtime Java portable no se genero correctamente."
    }

    New-Item -ItemType Directory -Force -Path (Split-Path $runtimeDest -Parent) | Out-Null
    Copy-Item -Recurse -Force $runtimeRoot $runtimeDest
}

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
Build-JavaRuntime
Write-Host "Runtime Java portable generado en dist\PODA\jre"

$iscc = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
if (Test-Path $iscc) {
    & $iscc .\installer\PODA.iss
    Write-Host "Instalador generado en installer_output\PODA_Setup.exe"
} else {
    Write-Host "ISCC.exe no encontrado; se omite el instalador."
}
