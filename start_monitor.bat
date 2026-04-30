@echo off
chcp 65001 >nul
echo ========================================
echo Geqie Monitor + AI Video Clip System
echo Danmaku Monitor Service
echo ========================================
echo.

set PROJECT_DIR=%~dp0
set VENV_DIR=%PROJECT_DIR%venv

cd /d "%PROJECT_DIR%monitor"

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found
    echo Please run install.bat first to install dependencies
    pause
    exit /b 1
)

echo [Activating] Virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

echo.
echo [Check] Config file...
if not exist "config.yaml" (
    echo [WARNING] Config file not found
    echo Please copy config.yaml.example to config.yaml
    echo and fill in room ID and admin password
    echo.
    echo Using default configuration...
    echo.
)

echo [Starting] Danmaku Monitor Service...
echo URL: http://localhost:5000
echo.
echo Press Ctrl+C to stop
echo.

python jk.py

pause
