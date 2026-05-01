@echo off
title VRay Texture Map Generator - Installer
echo ============================================
echo   VRay Texture Map Generator - Installer
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo Please install Python 3.10 or later from https://python.org
    echo Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

echo [OK] Python found:
python --version
echo.
echo Installing dependencies...
echo.
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [ERROR] Installation failed. Check your internet connection and try again.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Installation complete!
echo   Run run.bat to start the application.
echo ============================================
pause
