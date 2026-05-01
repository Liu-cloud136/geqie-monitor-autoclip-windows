@echo off
chcp 65001 >nul
echo ========================================
echo Geqie Monitor + AI Video Clip System
echo Danmaku Monitor Service
echo ========================================
echo.

set SCRIPT_DIR=%~dp0
set VENV_DIR=%SCRIPT_DIR%venv

echo Script directory: %SCRIPT_DIR%
echo Virtual environment: %VENV_DIR%
echo.

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found
    echo Expected: %VENV_DIR%\Scripts\python.exe
    echo.
    echo Please run install.bat first to install dependencies
    pause
    exit /b 1
)

echo [OK] Virtual environment found
echo.

cd /d "%SCRIPT_DIR%monitor"

echo [Check] Config file...
if not exist "config.yaml" (
    echo [WARNING] Config file not found
    echo Please copy config.yaml.example to config.yaml
    echo and fill in room ID and admin password
    echo.
    echo Using default configuration...
    echo.
) else (
    echo [OK] Config file found
    echo.
)

echo [Starting] Danmaku Monitor Service...
echo URL: http://localhost:5000
echo.
echo Press Ctrl+C to stop
echo.

"%VENV_DIR%\Scripts\python.exe" jk.py

pause
