@echo off
chcp 65001 >nul
echo ========================================
echo Geqie Monitor + AI Video Clip System
echo FastAPI Backend Service
echo ========================================
echo.

set PROJECT_DIR=%~dp0
set VENV_DIR=%PROJECT_DIR%venv

cd /d "%PROJECT_DIR%backend"

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found
    echo Please run install.bat first to install dependencies
    echo Or run manually: python -m venv venv ^&^& pip install -r requirements.txt
    pause
    exit /b 1
)

echo [Activating] Virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

echo.
echo [Starting] FastAPI Service...
echo URL: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo API ReDoc: http://localhost:8000/redoc
echo.
echo Press Ctrl+C to stop
echo.

uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4 --timeout-keep-alive 300 --limit-concurrency 1000

pause
