$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = $null

try {
    $python = (Get-Command pythonw.exe -ErrorAction Stop).Source
} catch {
    try {
        $python = (Get-Command python.exe -ErrorAction Stop).Source
    } catch {
        $python = "python"
    }
}

Start-Process -FilePath $python -ArgumentList @("scripts\organiza_planillas_app.py") -WorkingDirectory $root | Out-Null
