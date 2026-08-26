@echo off
REM Reinicia Boletas Honorarios (detiene servidor viejo + arranca uno nuevo).
cd /d "%~dp0.."
title Reiniciar Boletas Honorarios
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-bh.ps1" -Restart
if errorlevel 1 (
  echo.
  echo No se pudo reiniciar. Revisa el mensaje de arriba o logs\uvicorn.err
  pause
)
