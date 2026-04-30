@echo off
chcp 65001 >nul
echo ========================================
echo AutoClip Celery Worker (Enhanced)
echo ========================================
echo.
echo.

cd /d "%~dp0backend"

if not exist "venv\Scripts\activate.bat" (
    echo Error: Virtual environment not found
    echo Please run: python -m venv venv
    pause
    exit /b 1
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Starting Celery Worker...
echo Queues: processing, celery
echo Concurrency: 4
echo.
echo Press Ctrl+C to stop the worker
echo.
echo ========================================
echo Logs will be written to: ..\logs\celery_worker.log
echo ========================================
echo.

set PYTHONPATH=%CD%
set PYTHONUNBUFFERED=1
python -u -m celery -A core.celery_app worker --loglevel=info --concurrency=4 -Q processing,celery --include=tasks.import_processing,tasks.processing,tasks.video,tasks.thumbnail_task,tasks.notification,tasks.maintenance,tasks.data_cleanup

pause
