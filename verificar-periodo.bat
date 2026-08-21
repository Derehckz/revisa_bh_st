@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Verificar periodo Boletas Honorarios

if "%~1"=="" goto :ask_year
set "YEAR=%~1"
goto :have_year

:ask_year
set /p YEAR=Anio (ej 2026): 

:have_year
if "%~2"=="" goto :ask_month
set "MONTH=%~2"
goto :have_month

:ask_month
set /p MONTH=Mes (ej Julio): 

:have_month
set "XLSX=%~3"
if "%XLSX%"=="" set "XLSX=%YEAR%\%MONTH%\Solicitud.xlsx"

echo.
echo === Verificacion de periodo ===
echo Periodo: %MONTH% %YEAR%
echo Excel:   %XLSX%
echo.

if not exist "%XLSX%" (
  echo ERROR: No existe el archivo "%XLSX%"
  echo Uso: verificar-periodo.bat 2026 Julio "2026\Julio\Solicitud.xlsx"
  pause
  exit /b 1
)

echo [1/6] Aplicando migraciones DB...
python -m alembic upgrade head
if errorlevel 1 goto :fail

echo [2/6] Importando snapshot del periodo a PostgreSQL...
python db/import_excel_snapshot.py --file "%XLSX%" --year %YEAR% --month-name "%MONTH%"
if errorlevel 1 goto :fail

echo [3/6] Comparando Excel vs DB (sombra)...
python db/compare_excel_db.py --year %YEAR% --month "%MONTH%"
if errorlevel 1 goto :fail

echo [4/6] Check del periodo en DB...
python db/check_period.py --year %YEAR% --month "%MONTH%"
if errorlevel 1 goto :fail

echo [5/6] Check de consistencia global (muestra corta)...
python db/check_consistency.py --limit 20
if errorlevel 1 goto :fail

echo [6/6] Recomendacion:
echo - Si Diferencias=0 en comparacion, puedes activar BH_READ_FROM_DB=1 en .env
echo - Luego ejecuta reiniciar-bh.bat
echo.
echo OK: verificacion completada.
pause
exit /b 0

:fail
echo.
echo ERROR: Fallo un paso de verificacion. Revisa el mensaje anterior.
pause
exit /b 1
