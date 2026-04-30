@echo off
chcp 65001 >nul
echo ========================================
echo Geqie Monitor + AI Video Clip System
echo Unified Install Script
echo ========================================
echo.

set PROJECT_DIR=%~dp0
set VENV_DIR=%PROJECT_DIR%venv

echo Project directory: %PROJECT_DIR%
echo Virtual environment: %VENV_DIR%
echo.

echo ========================================
echo Checking Python Environment
echo ========================================
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found, please install Python 3.9+
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python is installed
python --version
echo.

echo ========================================
echo Creating Virtual Environment
echo ========================================
if exist "%VENV_DIR%" (
    echo [INFO] Virtual environment already exists
    echo To reinstall, please delete the venv folder first
) else (
    echo [Creating] Virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created successfully
)
echo.

echo ========================================
echo Activating Virtual Environment
echo ========================================
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)
echo [OK] Virtual environment activated
echo.

echo ========================================
echo Upgrading pip
echo ========================================
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
echo.

echo ========================================
echo Installing Python Dependencies (Tsinghua Mirror)
echo ========================================
echo This may take a few minutes, please wait...
echo.

pip install -r "%PROJECT_DIR%requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo.
    echo [WARNING] Some dependencies failed to install, trying official source...
    pip install -r "%PROJECT_DIR%requirements.txt"
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies, please check network connection
        pause
        exit /b 1
    )
)
echo.
echo [OK] Python dependencies installed
echo.

echo ========================================
echo Installing bcut-asr Speech Recognition
echo ========================================
cd /d "%PROJECT_DIR%backend\bcut-asr"
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [WARNING] bcut-asr installation may have issues, but you can continue
) else (
    echo [OK] bcut-asr installed
)
echo.

echo ========================================
echo Initializing Clip System Database
echo ========================================
cd /d "%PROJECT_DIR%backend"

if not exist "data" (
    mkdir data
    echo [Created] data directory
)

python init_db.py
if errorlevel 1 (
    echo [WARNING] Database initialization may have issues
    echo Please check .env configuration
) else (
    echo [OK] Database initialized
)
echo.

echo ========================================
echo Checking Frontend Environment
echo ========================================
node --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] Node.js not found, frontend features will be unavailable
    echo To use the clip system frontend, please install Node.js 18.x+
    echo Download: https://nodejs.org/
) else (
    echo [OK] Node.js is installed
    node --version
    
    echo.
    echo ========================================
    echo Installing Frontend Dependencies
    echo ========================================
    cd /d "%PROJECT_DIR%frontend"
    
    echo Checking package-lock.json...
    if exist "package-lock.json" (
        echo Installing dependencies (using cache)...
        npm install
    ) else (
        echo Installing dependencies...
        npm install
    )
    
    if errorlevel 1 (
        echo [WARNING] Frontend dependencies installation failed
        echo Please run manually: cd frontend ^&^& npm install
    ) else (
        echo [OK] Frontend dependencies installed
    )
)
echo.

echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo Virtual environment: %VENV_DIR%
echo.
echo Next Steps:
echo 1. Configure environment variables (already configured):
echo    - .env file: LLM API Key and Bilibili Cookie
echo    - monitor/config.yaml: Room ID and admin password
echo.
echo 2. Install external dependencies:
echo    - Redis 5.0+ (for Celery task queue)
echo    - FFmpeg 4.0+ (for video processing)
echo.
echo 3. Start services:
echo    - Run start_all.bat to start all services
echo    - Or run individual start scripts
echo.
echo Access URLs:
echo - Danmaku Monitor: http://localhost:5000
echo - Clip System Frontend: http://localhost:5173
echo - API Docs: http://localhost:8000/docs
echo.
echo ========================================
pause
