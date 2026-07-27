@echo off
REM Boletas Honorarios — un solo puerto (API + interfaz).
cd /d "%~dp0"
title Boletas Honorarios
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-bh.ps1" %*
if errorlevel 1 (
  echo.
  echo Arranque fallido. Revisa el mensaje de arriba o logs\uvicorn.err
  pause
)
