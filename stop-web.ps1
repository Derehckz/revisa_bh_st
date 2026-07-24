# Detiene procesos que escuchan en los puertos del stack web.
param(
    [int]$ApiPort = 8000,
    [int]$WebPort = 5173
)

$ErrorActionPreference = "SilentlyContinue"

function Stop-Port([int]$Port) {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        $procId = $c.OwningProcess
        if ($procId -and $procId -ne 0) {
            $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
            Write-Host "Deteniendo PID $procId ($($p.ProcessName)) en :$Port" -ForegroundColor Yellow
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
}

Stop-Port $ApiPort
Stop-Port $WebPort
Write-Host "Puertos $ApiPort / $WebPort liberados (si habia listeners)." -ForegroundColor Green
