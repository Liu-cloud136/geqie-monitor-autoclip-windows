@echo off
chcp 65001 >nul
echo ========================================
echo AutoClip FastAPI Server
echo ========================================
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
echo Starting FastAPI server...
echo URL: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server
echo.

uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4 --timeout-keep-alive 300 --limit-concurrency 1000

pause
