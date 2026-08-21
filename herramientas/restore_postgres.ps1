# Restore PostgreSQL — USO CON CUIDADO (sobrescribe la BD)
# powershell -ExecutionPolicy Bypass -File .\herramientas\restore_postgres.ps1 -DumpPath .\.backups\postgres\bh_YYYYMMDD_HHMMSS.dump

param(
  [Parameter(Mandatory = $true)]
  [string]$DumpPath,
  [switch]$Yes
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path $DumpPath)) {
  throw "No existe dump: $DumpPath"
}
if (-not $Yes) {
  $confirm = Read-Host "Esto RESTAURA la base. Escribe SI para continuar"
  if ($confirm -ne "SI") { throw "Cancelado" }
}

$envFile = Join-Path $Root ".env"
if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*#') { return }
    if ($_ -match '^\s*([A-Za-z0-9_]+)\s*=\s*(.*)\s*$') {
      $k = $Matches[1]
      $v = $Matches[2].Trim().Trim('"').Trim("'")
      if ($k -like "BH_DB_*") {
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

$env:PGPASSWORD = $Password
& pg_restore -h $HostName -p $Port -U $User -d $Name --clean --if-exists $DumpPath
if ($LASTEXITCODE -ne 0) {
  Write-Warning "pg_restore terminó con código $LASTEXITCODE (revisa warnings)."
} else {
  Write-Host "OK restore desde $DumpPath"
}
