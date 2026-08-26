@echo off
REM Alias: detiene el stack (puertos 8000 / 5173).
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-web.ps1" %*
