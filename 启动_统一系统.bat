@echo off
chcp 65001 >nul
title AutoClip System - Unified Launcher

echo.
echo ========================================
echo   AutoClip System - All-in-One
echo   Danmaku Monitor + AI Video Clipping
echo ========================================
echo.

set SCRIPT_DIR=%~dp0
set VENV_DIR=%SCRIPT_DIR%venv

echo [INFO] Script Directory: %SCRIPT_DIR%
echo [INFO] Virtual Environment: %VENV_DIR%
echo.

echo ========================================
echo [Step 1/6] Environment Check
echo ========================================
echo.

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found!
    echo [ERROR] Expected: %VENV_DIR%\Scripts\python.exe
    echo.
    echo [Hint] Please run install.bat first to install dependencies.
    pause
    exit /b 1
)
echo [OK] Virtual environment is ready
echo.

echo ========================================
echo [Step 2/6] Check Redis
echo ========================================
echo.

redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Redis is not running or not installed
    echo [WARNING] Celery task queue requires Redis
    echo [WARNING] Video processing features will be unavailable
    echo.
    set REDIS_READY=0
) else (
    echo [OK] Redis is ready
    echo.
    set REDIS_READY=1
)

echo ========================================
echo [Step 3/6] Check FFmpeg
echo ========================================
echo.

ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] FFmpeg not found
    echo [WARNING] Video processing features will be unavailable
    echo [WARNING] Please download FFmpeg and add to system PATH
    echo.
    set FFMPEG_READY=0
) else (
    echo [OK] FFmpeg is ready
    echo.
    set FFMPEG_READY=1
)

echo ========================================
echo [Step 4/6] Prepare to Start
echo ========================================
echo.

echo [INFO] Starting the following services:
echo [INFO] 1. FastAPI Backend (Port 8000)
echo [INFO] 2. Celery Task Queue
echo [INFO] 3. Frontend Dev Server (Port 5173)
echo [INFO] 4. Danmaku Monitor Service (Port 5000)
echo.

echo [INFO] Each service will run in a separate window
echo.

timeout /t 3 /nobreak >nul

echo ========================================
echo [Step 5/6] Starting Services
echo ========================================
echo.

echo [1/4] Starting FastAPI Backend...
start "AutoClip - FastAPI Backend" cmd /k "cd /d %SCRIPT_DIR%\backend && echo Starting FastAPI Backend... && echo URL: http://localhost:8000 && echo API Docs: http://localhost:8000/docs && echo Press Ctrl+C to stop && echo ======================================== && %VENV_DIR%\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1"

echo [OK] FastAPI Backend starting...
timeout /t 3 /nobreak >nul

if "%REDIS_READY%"=="1" (
    echo [2/4] Starting Celery Task Queue...
    start "AutoClip - Celery Worker" cmd /k "cd /d %SCRIPT_DIR%\backend && echo Starting Celery Task Queue... && echo Press Ctrl+C to stop && echo ======================================== && set PYTHONPATH=%CD% && %VENV_DIR%\Scripts\celery.exe -A core.celery_app worker --loglevel=info --concurrency=4"
    echo [OK] Celery starting...
) else (
    echo [2/4] Skipping Celery (Redis not available)
)
timeout /t 2 /nobreak >nul

echo [3/4] Starting Frontend Dev Server...
start "AutoClip - Frontend" cmd /k "cd /d %SCRIPT_DIR%\frontend && echo Starting Frontend Dev Server... && echo URL: http://localhost:5173 && echo Press Ctrl+C to stop && echo ======================================== && npm run dev"
echo [OK] Frontend starting...
timeout /t 5 /nobreak >nul

echo [4/4] Starting Danmaku Monitor Service...
start "AutoClip - Danmaku Monitor" cmd /k "cd /d %SCRIPT_DIR%\monitor && echo Starting Danmaku Monitor Service... && echo URL: http://localhost:5000 && echo Press Ctrl+C to stop && echo ======================================== && %VENV_DIR%\Scripts\python.exe jk.py"
echo [OK] Danmaku Monitor starting...
echo.

echo ========================================
echo [Step 6/6] All Services Started!
echo ========================================
echo.

echo ========================================
echo Access URLs:
echo ========================================
echo.
echo   Unified Frontend: http://localhost:5173
echo.
echo   FastAPI Backend:  http://localhost:8000
echo   API Docs:         http://localhost:8000/docs
echo   API ReDoc:        http://localhost:8000/redoc
echo   Danmaku Monitor:  http://localhost:5000
echo.
echo ========================================
echo Features:
echo ========================================
echo.
echo   - Danmaku Monitor: Today Data, Multi-Room, Analysis, History
echo   - AI Video Clip: Project Management, Video Processing, Smart Scoring
echo   - Settings: LLM Config, Step Config, System Config
echo.
echo ========================================
echo Notes:
echo ========================================
echo.
echo   - Close the corresponding windows to stop services
echo   - Log files are in logs/ directory
echo   - To reinstall dependencies, delete venv folder and run install.bat
echo.

echo [INFO] Waiting for frontend to be ready...
timeout /t 3 /nobreak >nul

echo [INFO] Opening browser...
start http://localhost:5173

echo.
echo [INFO] Browser opened. Close the corresponding windows to stop services.
echo.
echo ========================================
echo Hints:
echo ========================================
echo.
echo - Unified Frontend: http://localhost:5173
echo - Navigation: Danmaku Monitor / AI Clip / Settings
echo - Danmaku Monitor dropdown contains: Today, Multi-Room, Analysis, History
echo.
echo ========================================
pause