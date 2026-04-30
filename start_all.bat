@echo off
chcp 65001 >nul
echo ========================================
echo AutoClip - Start All Services
echo ========================================
echo.
echo This script will:
echo 1. Start FastAPI Server (port 8000)
echo 2. Start Celery Worker (task queue)
echo 3. Start frontend development server
echo.
echo Note: Three new windows will be opened
echo.

cd /d "%~dp0"

echo Starting FastAPI server...
start "AutoClip - FastAPI Server" cmd /k "start_backend.bat"

echo Waiting for FastAPI server to start...
echo Checking if server is ready...
timeout /t 5 /nobreak >nul

echo Starting Celery worker...
start "AutoClip - Celery Worker" cmd /k "start_celery_enhanced.bat"

echo Waiting for services to be ready...
timeout /t 3 /nobreak >nul

echo Starting frontend development server...
echo ========================================
echo Frontend dev server will run in a new window
start "AutoClip - Frontend Dev Server" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ========================================
echo Services Started!
echo ========================================
echo.
echo Frontend Dev Server: http://localhost:5173
echo FastAPI Server: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.
echo Waiting for frontend to be ready...
timeout /t 5 /nobreak >nul

echo Opening browser...
start http://localhost:5173

echo.
echo Browser opened. Close windows to stop services.
echo.
