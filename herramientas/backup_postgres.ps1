# Backup PostgreSQL — Boletas Honorarios
# Uso: powershell -ExecutionPolicy Bypass -File .\herramientas\backup_postgres.ps1
# Programar diario en el Programador de tareas de Windows.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# Carga BH_DB_* desde .env si existen
$envFile = Join-Path $Root ".env"
if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*#') { return }
    if ($_ -match '^\s*([A-Za-z0-9_]+)\s*=\s*(.*)\s*$') {
      $k = $Matches[1]
      $v = $Matches[2].Trim().Trim('"').Trim("'")
      if ($k -like "BH_DB_*" -or $k -eq "BH_DB_PASSWORD") {
        [Environment]::SetEnvironmentVariable($k, $v, "Process")
      }
    }
  }
}

$HostName = if ($env:BH_DB_HOST) { $env:BH_DB_HOST } else { "localhost" }
$Port = if ($env:BH_DB_PORT) { $env:BH_DB_PORT } else { "5432" }
$Name = if ($env:BH_DB_NAME) { $env:BH_DB_NAME } else { "boletas_honorarios" }
$User = if ($env:BH_DB_USER) { $env:BH_DB_USER } else { "boletas_app" }
$Password = if ($env:BH_DB_PASSWORD) { $env:BH_DB_PASSWORD } else { "" }

$OutDir = Join-Path $Root ".backups\postgres"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutFile = Join-Path $OutDir "bh_$Stamp.dump"

$env:PGPASSWORD = $Password
& pg_dump -h $HostName -p $Port -U $User -d $Name -Fc -f $OutFile
if ($LASTEXITCODE -ne 0) {
  throw "pg_dump falló con código $LASTEXITCODE"
}

# Retención: últimos 14
Get-ChildItem $OutDir -Filter "*.dump" |
  Sort-Object LastWriteTime -Descending |
  Select-Object -Skip 14 |
  Remove-Item -Force

Write-Host "OK backup: $OutFile"
