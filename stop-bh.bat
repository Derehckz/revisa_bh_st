@echo off
REM Detiene el stack (puertos 8000 / 5173).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-web.ps1" %*
