@echo off
title Yu-Gi-Oh! Forbidden Memories - ROM Suite
cd /d "%~dp0"
python main.py
if errorlevel 1 (
    echo.
    echo Ocurrio un error al ejecutar la aplicacion. Asegurate de tener Python instalado.
    pause
)
