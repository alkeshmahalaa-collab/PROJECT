@echo off
title VRay Texture Map Generator
cd /d "%~dp0"
python main.py
if errorlevel 1 (
    echo.
    echo [ERROR] The application crashed. Make sure you ran install.bat first.
    pause
)
