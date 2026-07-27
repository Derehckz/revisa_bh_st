# Solo reconstruye frontend/dist (sin levantar servidor).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $Root "frontend")
if (-not (Test-Path "node_modules")) { npm install }
npm run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "OK: frontend/dist listo. Usa start-bh.bat para abrir." -ForegroundColor Green
