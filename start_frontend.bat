@echo off
chcp 65001 >nul
echo ========================================
echo Geqie Monitor + AI Video Clip System
echo Frontend Dev Server
echo ========================================
echo.

set SCRIPT_DIR=%~dp0

echo Script directory: %SCRIPT_DIR%
echo.

cd /d "%SCRIPT_DIR%frontend"

echo [Check] Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found
    echo Please install Node.js 18.x+ from https://nodejs.org/
    pause
    exit /b 1
)
echo [OK] Node.js is installed
node --version
echo.

echo [Check] node_modules...
if not exist "node_modules" (
    echo [WARNING] node_modules not found
    echo Installing dependencies...
    npm install
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
) else (
    echo [OK] node_modules found
)
echo.

echo [Starting] Frontend Dev Server...
echo URL: http://localhost:5173
echo.
echo Press Ctrl+C to stop
echo.

npm run dev

pause
