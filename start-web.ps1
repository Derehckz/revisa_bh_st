# Arranque rápido del stack web (API + Vite).
# Uso:
#   powershell -ExecutionPolicy Bypass -File .\start-web.ps1
#   o doble clic en start-web.bat

param(
    [switch]$NoBrowser,
    [int]$ApiPort = 8000,
    [int]$WebPort = 5173
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Test-PortListen([int]$Port) {
    try {
        $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        return $null -ne $c
    } catch {
        return $false
    }
}

if (-not (Test-Path (Join-Path $Root ".env"))) {
    Write-Host "AVISO: no hay .env en la raiz. Copia .env.example y ajusta BH_API_KEY." -ForegroundColor Yellow
}

if (-not (Test-Path (Join-Path $Root "frontend\node_modules"))) {
    Write-Host "Instalando dependencias frontend (npm install)..." -ForegroundColor Cyan
    Push-Location (Join-Path $Root "frontend")
    npm install
    Pop-Location
}

$env:PYTHONPATH = "$Root;$Root\lib"

if (Test-PortListen $ApiPort) {
    Write-Host "API ya escucha en :$ApiPort (no se abre otra ventana)." -ForegroundColor DarkYellow
} else {
    Write-Host "Iniciando API en http://127.0.0.1:$ApiPort ..." -ForegroundColor Green
    Start-Process -FilePath "python" -ArgumentList @(
        "-m", "uvicorn", "api.app:app",
        "--host", "127.0.0.1",
        "--port", "$ApiPort"
    ) -WorkingDirectory $Root -WindowStyle Normal
}

if (Test-PortListen $WebPort) {
    Write-Host "Vite ya escucha en :$WebPort (no se abre otra ventana)." -ForegroundColor DarkYellow
} else {
    Write-Host "Iniciando frontend en http://127.0.0.1:$WebPort ..." -ForegroundColor Green
    Start-Process -FilePath "npm" -ArgumentList @(
        "run", "dev", "--", "--host", "127.0.0.1", "--port", "$WebPort"
    ) -WorkingDirectory (Join-Path $Root "frontend") -WindowStyle Normal
}

Start-Sleep -Seconds 2

if (-not $NoBrowser) {
    $url = "http://127.0.0.1:$WebPort"
    Write-Host "Abriendo $url" -ForegroundColor Cyan
    Start-Process $url
}

Write-Host ""
Write-Host "Listo. En la web: Ajustes -> pega BH_API_KEY de tu .env (solo la 1a vez)." -ForegroundColor Cyan
Write-Host "Para detener: .\stop-web.bat  o cierra las ventanas de API/Vite." -ForegroundColor DarkGray
