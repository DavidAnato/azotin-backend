# Serveur de dev ASGI avec rechargement auto (HTTP + WebSockets).
# Usage : .\run-dev.ps1
# Remplace Daphne en local : plus besoin de redémarrer à chaque changement .py

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:DJANGO_SETTINGS_MODULE = "jobhub_api.settings.development"

$uvicorn = ".\venv\Scripts\uvicorn.exe"
if (-not (Test-Path $uvicorn)) {
    Write-Host "Installation de uvicorn (rechargement auto)..."
    .\venv\Scripts\pip.exe install "uvicorn[standard]"
}

Write-Host "Demarrage sur http://0.0.0.0:8000 (reload actif)..."
& $uvicorn jobhub_api.asgi:application --host 0.0.0.0 --port 8000 --reload
