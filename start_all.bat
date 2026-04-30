@echo off
chcp 65001 >nul
echo ========================================
echo Geqie Monitor + AI Video Clip System
echo Unified Start Script
echo ========================================
echo.
echo This script will start the following services:
echo 1. FastAPI Backend Server (Port 8000)
echo 2. Celery Task Queue
echo 3. Frontend Dev Server (Port 5173)
echo 4. Danmaku Monitor Service (Port 5000)
echo.
echo Note: Four new windows will be opened
echo.

set PROJECT_DIR=%~dp0
set VENV_DIR=%PROJECT_DIR%venv

cd /d "%PROJECT_DIR%"

echo [Check] Virtual environment...
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found
    echo Please run install.bat first to install dependencies
    pause
    exit /b 1
)
echo [OK] Virtual environment is ready
echo.

echo [Check] Redis...
redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Redis is not running or not installed
    echo Celery task queue requires Redis
    echo Please start Redis service first
    echo.
    pause
    exit /b 1
)
echo [OK] Redis is ready
echo.

echo [Check] FFmpeg...
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] FFmpeg not found
    echo Video processing features will be unavailable
    echo Please download FFmpeg and add to system PATH
    echo Download: https://ffmpeg.org/download.html
    echo.
    pause
) else (
    echo [OK] FFmpeg is ready
)
echo.

echo ========================================
echo Starting Services
echo ========================================
echo.

echo [1/4] Starting FastAPI Backend Server...
echo Window: AutoClip - FastAPI Server
start "AutoClip - FastAPI Server" cmd /k "cd /d "%PROJECT_DIR%" ^&^& start_backend.bat"

echo Waiting 5 seconds for service to start...
timeout /t 5 /nobreak >nul
echo.

echo [2/4] Starting Celery Task Queue...
echo Window: AutoClip - Celery Worker
start "AutoClip - Celery Worker" cmd /k "cd /d "%PROJECT_DIR%" ^&^& start_celery.bat"

echo Waiting 3 seconds for service to start...
timeout /t 3 /nobreak >nul
echo.

echo [3/4] Starting Frontend Dev Server...
echo Window: AutoClip - Frontend
start "AutoClip - Frontend" cmd /k "cd /d "%PROJECT_DIR%frontend" ^&^& npm run dev"

echo Waiting 3 seconds for service to start...
timeout /t 3 /nobreak >nul
echo.

echo [4/4] Starting Danmaku Monitor Service...
echo Window: Danmaku Monitor System
start "Danmaku Monitor System" cmd /k "cd /d "%PROJECT_DIR%" ^&^& start_monitor.bat"

echo.
echo ========================================
echo All Services Started!
echo ========================================
echo.
echo Access URLs:
echo - Danmaku Monitor: http://localhost:5000
echo - Clip System Frontend: http://localhost:5173
echo - FastAPI Backend: http://localhost:8000
echo - API Docs: http://localhost:8000/docs
echo - API ReDoc: http://localhost:8000/redoc
echo.
echo Waiting for frontend to be ready...
timeout /t 5 /nobreak >nul

echo Opening browser...
start http://localhost:5173

echo.
echo Browser opened. Close the corresponding windows to stop services.
echo.
echo ========================================
echo Tips:
echo - If services fail to start, check .env and config.yaml
echo - Log files are in logs/ directory
echo - To reinstall dependencies, delete venv folder and run install.bat again
echo ========================================
echo.
pause
