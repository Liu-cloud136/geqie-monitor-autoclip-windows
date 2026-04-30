@echo off
chcp 65001 >nul
echo ========================================
echo Geqie Monitor + AI Video Clip System
echo Celery Task Queue
echo ========================================
echo.

set PROJECT_DIR=%~dp0
set VENV_DIR=%PROJECT_DIR%venv

cd /d "%PROJECT_DIR%backend"

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found
    echo Please run install.bat first to install dependencies
    pause
    exit /b 1
)

echo [Activating] Virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

echo.
echo [Creating] Logs directory...
if not exist "%PROJECT_DIR%logs" (
    mkdir "%PROJECT_DIR%logs"
    echo [OK] Logs directory created
)

echo.
echo [Starting] Celery Worker...
echo Task Queues: processing, celery
echo Concurrency: 4
echo.
echo Press Ctrl+C to stop
echo.
echo ========================================
echo Log file: %PROJECT_DIR%logs\celery_worker.log
echo ========================================
echo.

set PYTHONPATH=%CD%
set PYTHONUNBUFFERED=1

python -u -m celery -A core.celery_app worker --loglevel=info --concurrency=4 -Q processing,celery --include=tasks.import_processing,tasks.processing,tasks.video,tasks.thumbnail_task,tasks.notification,tasks.maintenance,tasks.data_cleanup 2>&1 | tee "%PROJECT_DIR%logs\celery_worker.log"

pause
