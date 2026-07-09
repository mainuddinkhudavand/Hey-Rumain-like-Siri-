@echo off
title Rumain 3D Desktop Assistant
echo ============================================================
echo   RUMAIN 3D Desktop Assistant Launcher
echo ============================================================

cd /d "%~dp0"

:: Check for .env file
if not exist .env (
    echo [.env] configuration file not found. Copying template from .env.example...
    copy .env.example .env
    echo Please open the newly created .env file in Notepad and configure your Anthropic Claude API keys.
)

echo Starting voice assistant pipeline and PyQt5 UI...
python main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Rumain closed with code %errorlevel%.
    echo Please verify that dependencies are installed: pip install -r requirements.txt
    pause
)
