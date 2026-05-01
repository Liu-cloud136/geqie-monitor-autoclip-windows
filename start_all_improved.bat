@echo off
chcp 65001 >nul
title AutoClip + Danmaku Monitor - 一键启动

echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║              AutoClip + Danmaku Monitor  一键启动                ║
echo ║                      视频切片 + 弹幕监控一体化系统                ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

set SCRIPT_DIR=%~dp0
set VENV_DIR=%SCRIPT_DIR%venv
set FRONTEND_DIR=%SCRIPT_DIR%frontend
set BACKEND_DIR=%SCRIPT_DIR%backend
set MONITOR_DIR=%SCRIPT_DIR%monitor

echo [信息] 项目目录: %SCRIPT_DIR%
echo [信息] 虚拟环境: %VENV_DIR%
echo.

cd /d "%SCRIPT_DIR%"

echo [1/6] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.9+
    echo        下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python 已安装
echo.

echo [2/6] 检查虚拟环境...
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [错误] 虚拟环境不存在
    echo        请先运行 install.bat 安装依赖
    pause
    exit /b 1
)
echo [OK] 虚拟环境已就绪
echo.

echo [3/6] 检查 Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo [警告] Node.js 未安装
    echo        前端开发服务器需要 Node.js 18.x+
    echo        下载地址: https://nodejs.org/
    echo.
    set NODE_MISSING=1
) else (
    echo [OK] Node.js 已安装
    set NODE_MISSING=0
)
echo.

echo [4/6] 检查前端依赖...
if not exist "%FRONTEND_DIR%\node_modules" (
    if %NODE_MISSING%==0 (
        echo [信息] node_modules 不存在，正在安装...
        cd /d "%FRONTEND_DIR%"
        call npm install
        if errorlevel 1 (
            echo [警告] 前端依赖安装失败
        )
        cd /d "%SCRIPT_DIR%"
    )
) else (
    echo [OK] 前端依赖已就绪
)
echo.

echo [5/6] 检查 FFmpeg...
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [警告] FFmpeg 未安装或未添加到 PATH
    echo        视频处理功能将不可用
    echo        下载地址: https://ffmpeg.org/download.html
) else (
    echo [OK] FFmpeg 已就绪
)
echo.

echo [6/6] 检查 Redis (可选)...
redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo [警告] Redis 未运行
    echo        Celery 任务队列需要 Redis
    echo        如需要后台任务处理，请启动 Redis
) else (
    echo [OK] Redis 已就绪
)
echo.

echo ═════════════════════════════════════════════════════════════════════
echo                              启动服务
echo ═════════════════════════════════════════════════════════════════════
echo.

echo [1/4] 启动弹幕监控服务 (Flask, 端口 5000)...
echo       URL: http://localhost:5000
start "弹幕监控系统 - Port 5000" cmd /k "%SCRIPT_DIR%start_monitor.bat"
echo       已启动，等待 3 秒...
timeout /t 3 /nobreak >nul
echo.

echo [2/4] 启动 FastAPI 后端 (端口 8000)...
echo       URL: http://localhost:8000
echo       API Docs: http://localhost:8000/docs
start "AutoClip - FastAPI Server" cmd /k "%SCRIPT_DIR%start_backend.bat"
echo       已启动，等待 3 秒...
timeout /t 3 /nobreak >nul
echo.

echo [3/4] 启动 Celery 任务队列...
echo       (需要 Redis 服务运行)
start "AutoClip - Celery Worker" cmd /k "%SCRIPT_DIR%start_celery.bat"
echo       已启动
echo.

if %NODE_MISSING%==0 (
    echo [4/4] 启动前端开发服务器 (Vite, 端口 5173)...
    echo       URL: http://localhost:5173
    start "AutoClip - Frontend" cmd /k "%SCRIPT_DIR%start_frontend.bat"
    echo       已启动，等待 5 秒让前端准备好...
    timeout /t 5 /nobreak >nul
    echo.
) else (
    echo [4/4] 跳过前端启动 (Node.js 未安装)
    echo.
)

echo ═════════════════════════════════════════════════════════════════════
echo                              启动完成!
echo ═════════════════════════════════════════════════════════════════════
echo.
echo [访问地址]
echo   ├─ 弹幕监控界面:     http://localhost:5000
echo   ├─ AI切片前端:       http://localhost:5173
echo   ├─ FastAPI 后端:    http://localhost:8000
echo   ├─ API 文档:         http://localhost:8000/docs
echo   └─ API ReDoc:        http://localhost:8000/redoc
echo.
echo [功能说明]
echo   ├─ 弹幕监控: 监控B站直播弹幕，关键词匹配，邮件通知
echo   ├─ AI切片: 自动视频切片，AI分析，剪辑导出
echo   └─ 一体化: 前端可以快速切换两个系统
echo.
echo [提示]
echo   ├─ 关闭对应窗口可停止服务
echo   ├─ 首次运行可能需要较长时间启动
echo   ├─ 如遇到问题，请检查对应窗口的错误信息
echo   └─ 配置文件: .env (AI切片), monitor/config.yaml (弹幕监控)
echo.

if %NODE_MISSING%==0 (
    echo [信息] 正在打开前端界面...
    start http://localhost:5173
    echo.
)

echo 按任意键查看服务状态...
pause >nul

echo.
echo ═════════════════════════════════════════════════════════════════════
echo                              当前服务状态
echo ═════════════════════════════════════════════════════════════════════
echo.

tasklist /fi "WINDOWTITLE eq 弹幕监控系统*" 2>nul | find /i "python" >nul
if errorlevel 1 (
    echo [警告] 弹幕监控服务可能未运行
) else (
    echo [OK] 弹幕监控服务 (Port 5000) - 运行中
)

tasklist /fi "WINDOWTITLE eq AutoClip - FastAPI*" 2>nul | find /i "python" >nul
if errorlevel 1 (
    echo [警告] FastAPI 后端可能未运行
) else (
    echo [OK] FastAPI 后端 (Port 8000) - 运行中
)

tasklist /fi "WINDOWTITLE eq AutoClip - Celery*" 2>nul | find /i "python" >nul
if errorlevel 1 (
    echo [警告] Celery 任务队列可能未运行
) else (
    echo [OK] Celery 任务队列 - 运行中
)

echo.
echo 按任意键退出...
pause >nul
