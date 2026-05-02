@echo off
chcp 65001 >nul
echo ========================================
echo Geqie Monitor + AI Video Clip System
echo FastAPI Backend Service
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

cd /d "%SCRIPT_DIR%backend"

echo [Starting] FastAPI Service...
echo URL: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo API ReDoc: http://localhost:8000/redoc
echo.
echo Press Ctrl+C to stop
echo.

"%VENV_DIR%\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1

pause
