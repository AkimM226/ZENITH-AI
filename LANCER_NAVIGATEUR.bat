@echo off
title CERBERUS // ZENITH AI - Interface Web
cd /d "%~dp0"

echo ========================================================
echo   Demarrage de l'interface CERBERUS dans le navigateur...
echo ========================================================

start http://127.0.0.1:8000/

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m cerberus ui
) else (
    python -m cerberus ui
)

pause
