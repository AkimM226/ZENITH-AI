@echo off
title CERBERUS // ZENITH AI - Application Desktop
cd /d "%~dp0"

echo ========================================================
echo   Lancement de l'Orbe Desktop CERBERUS (ZENITH AI)...
echo ========================================================

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m cerberus app
) else (
    python -m cerberus app
)

pause
