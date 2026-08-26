@echo off
REM Doble clic: levanta API (:8000) + Vite (:5173) y abre el navegador.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-web.ps1" %*
