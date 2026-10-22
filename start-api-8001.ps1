$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:DJANGO_SETTINGS_MODULE = 'azobatin_api.settings.development'
& "$PSScriptRoot\venv\Scripts\python.exe" -m uvicorn azobatin_api.asgi:application --host 0.0.0.0 --port 8001
