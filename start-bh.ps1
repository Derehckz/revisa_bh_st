# Arranque profesional: un solo puerto (API + UI embebida).
# Uso: doble clic start-bh.bat  |  .\start-bh.ps1
#
# Requiere frontend/dist (se construye solo si falta).
# Desarrollo con hot-reload: usa start-web.bat (API + Vite).

param(
    [switch]$NoBrowser,
    [switch]$Rebuild,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$LogDir = Join-Path $Root "logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$UvicornLog = Join-Path $LogDir "uvicorn.log"
$UvicornErr = Join-Path $LogDir "uvicorn.err"

function Test-PortListen([int]$PortNum) {
    try {
        $c = Get-NetTCPConnection -LocalPort $PortNum -State Listen -ErrorAction SilentlyContinue
        return $null -ne $c
    } catch {
        return $false
    }
}

function Resolve-PythonExe {
    # Prefer real install; WindowsApps stub often fails on double-click.
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Python\bin\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Python\pythoncore-3.14-64\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe")
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    try {
        $py = Get-Command py -ErrorAction SilentlyContinue
        if ($py) {
            $out = & py -3 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $out -and (Test-Path $out.Trim())) {
                return $out.Trim()
            }
        }
    } catch {}
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notmatch "WindowsApps") {
        return $cmd.Source
    }
    if ($cmd) { return $cmd.Source }
    return $null
}

function Wait-Health([int]$PortNum, [int]$TimeoutSec = 45) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:$PortNum/health" -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) { return $true }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    return $false
}

Write-Host ""
Write-Host "=== Boletas Honorarios ===" -ForegroundColor Cyan
Write-Host "Carpeta: $Root"

if (-not (Test-Path (Join-Path $Root ".env"))) {
    Write-Host "AVISO: no hay .env. Copia .env.example y define BH_API_KEY." -ForegroundColor Yellow
}

$distIndex = Join-Path $Root "frontend\dist\index.html"
$needBuild = $Rebuild -or -not (Test-Path $distIndex)

if ($needBuild) {
    if (-not (Test-Path (Join-Path $Root "frontend\node_modules"))) {
        Write-Host "npm install..." -ForegroundColor Cyan
        Push-Location (Join-Path $Root "frontend")
        npm install
        if ($LASTEXITCODE -ne 0) { throw "Fallo npm install" }
        Pop-Location
    }
    Write-Host "Construyendo interfaz (npm run build)..." -ForegroundColor Cyan
    Push-Location (Join-Path $Root "frontend")
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Fallo el build del frontend" }
    Pop-Location
}

$Python = Resolve-PythonExe
if (-not $Python) {
    Write-Host "ERROR: no se encontro Python. Instala Python 3 y reintenta." -ForegroundColor Red
    Write-Host "Pulsa Enter para cerrar..."
    Read-Host | Out-Null
    exit 1
}
Write-Host "Python: $Python" -ForegroundColor DarkGray

$env:PYTHONPATH = "$Root;$Root\lib"

$alreadyUp = $false
if (Test-PortListen $Port) {
    if (Wait-Health $Port 5) {
        Write-Host "Ya hay un servidor listo en :$Port" -ForegroundColor DarkYellow
        $alreadyUp = $true
    } else {
        Write-Host "Puerto :$Port ocupado pero /health no responde. Usa stop-bh.bat" -ForegroundColor Red
        Write-Host "Pulsa Enter para cerrar..."
        Read-Host | Out-Null
        exit 1
    }
}

if (-not $alreadyUp) {
    Write-Host "Iniciando API + UI en http://127.0.0.1:$Port ..." -ForegroundColor Green
    if (Test-Path $UvicornLog) { Remove-Item $UvicornLog -Force -ErrorAction SilentlyContinue }
    if (Test-Path $UvicornErr) { Remove-Item $UvicornErr -Force -ErrorAction SilentlyContinue }

    $proc = Start-Process -FilePath $Python -ArgumentList @(
        "-m", "uvicorn", "api.app:app",
        "--host", "127.0.0.1",
        "--port", "$Port"
    ) -WorkingDirectory $Root -PassThru -WindowStyle Minimized `
      -RedirectStandardOutput $UvicornLog -RedirectStandardError $UvicornErr

    Write-Host "Esperando que el servidor responda (hasta 45s)..." -ForegroundColor DarkGray
    if (-not (Wait-Health $Port 45)) {
        Write-Host ""
        Write-Host "ERROR: el servidor no respondio a tiempo." -ForegroundColor Red
        if ($proc -and -not $proc.HasExited) {
            Write-Host "Proceso uvicorn sigue vivo (PID $($proc.Id)) pero /health fallo." -ForegroundColor Yellow
        } elseif ($proc) {
            Write-Host "uvicorn salio con codigo $($proc.ExitCode)." -ForegroundColor Yellow
        }
        Write-Host ""
        Write-Host "--- logs/uvicorn.err ---" -ForegroundColor Yellow
        if (Test-Path $UvicornErr) { Get-Content $UvicornErr -ErrorAction SilentlyContinue }
        Write-Host "--- logs/uvicorn.log ---" -ForegroundColor Yellow
        if (Test-Path $UvicornLog) { Get-Content $UvicornLog -ErrorAction SilentlyContinue }
        Write-Host ""
        Write-Host "Pulsa Enter para cerrar..."
        Read-Host | Out-Null
        exit 1
    }
}

Write-Host "OK - servidor listo." -ForegroundColor Green

if (-not $NoBrowser) {
    Start-Process "http://127.0.0.1:$Port/"
}

Write-Host ""
Write-Host "URL: http://127.0.0.1:$Port/" -ForegroundColor Cyan
Write-Host "Primera vez: Ajustes -> pega BH_API_KEY del .env" -ForegroundColor Cyan
Write-Host "Detener: stop-bh.bat" -ForegroundColor DarkGray
Write-Host "Logs: logs\uvicorn.log / logs\uvicorn.err" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Puedes cerrar esta ventana; el servidor sigue en segundo plano." -ForegroundColor DarkGray
Start-Sleep -Seconds 4
