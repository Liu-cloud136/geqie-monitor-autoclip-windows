@echo off
chcp 65001 >nul
echo ========================================
echo Geqie Monitor + AI Video Clip System
echo Celery Task Queue
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

echo [Creating] Logs directory...
if not exist "%SCRIPT_DIR%logs" (
    mkdir "%SCRIPT_DIR%logs"
    echo [OK] Logs directory created
) else (
    echo [OK] Logs directory exists
)
echo.

echo [Starting] Celery Worker...
echo Task Queues: processing, celery
echo Concurrency: 4
echo.
echo Press Ctrl+C to stop
echo.
echo ========================================
echo Log file: %SCRIPT_DIR%logs\celery_worker.log
echo ========================================
echo.

set PYTHONPATH=%CD%
set PYTHONUNBUFFERED=1

"%VENV_DIR%\Scripts\python.exe" -m celery -A core.celery_app worker --loglevel=info --concurrency=4 -Q processing,celery

pause
