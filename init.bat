@echo off
chcp 65001 >nul
echo ========================================
echo AutoClip - Initialize
echo ========================================
echo.

cd /d "%~dp0backend"

if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Error: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created successfully!
) else (
    echo Virtual environment already exists
)

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Installing dependencies...
pip install -r requirements.txt

if errorlevel 1 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo Initializing database...
python init_db.py

if errorlevel 1 (
    echo Warning: Database initialization may have failed, please check configuration
)

echo.
echo ========================================
echo Initialization Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Configure .env file (if needed)
echo 2. Run start_all.bat to start all services
echo.
pause
