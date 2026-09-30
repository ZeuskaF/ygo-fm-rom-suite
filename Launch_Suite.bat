@echo off
title Yu-Gi-Oh! Forbidden Memories - ROM Suite
cd /d "%~dp0"
python main.py %*
if errorlevel 1 (
    echo.
    echo An error occurred while running the application.
    echo Please make sure Python 3.10+ and required dependencies are installed:
    echo     pip install -r requirements.txt
    echo.
    pause
)
