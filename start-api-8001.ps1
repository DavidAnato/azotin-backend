$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:DJANGO_SETTINGS_MODULE = 'jobhub_api.settings.development'
& "$PSScriptRoot\venv\Scripts\python.exe" -m uvicorn jobhub_api.asgi:application --host 0.0.0.0 --port 8001
