@echo off
chcp 65001 >nul
title AutoClip 全能系统 - 统一启动脚本

echo.
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║                                                                   ║
echo ║      █████╗ ██╗   ██╗████████╗ ██████╗  ██████╗ ██╗     ║
echo ║     ██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗██╔═══██╗██║     ║
echo ║     ███████║██║   ██║   ██║   ██║   ██║██║   ██║██║     ║
echo ║     ██╔══██║██║   ██║   ██║   ██║   ██║██║   ██║██║     ║
echo ║     ██║  ██║╚██████╔╝   ██║   ╚██████╔╝╚██████╔╝███████╗║
echo ║     ╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝║
echo ║                                                                   ║
echo ║                    全能系统 - 弹幕监控 + AI 视频切片                   ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.

set SCRIPT_DIR=%~dp0
set VENV_DIR=%SCRIPT_DIR%venv

echo [INFO] 脚本目录: %SCRIPT_DIR%
echo [INFO] 虚拟环境目录: %VENV_DIR%
echo.

echo ========================================
echo [步骤 1/6: 环境检查
echo ========================================
echo.

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [ERROR] 虚拟环境未找到
    echo [ERROR] 期望路径: %VENV_DIR%\Scripts\python.exe
    echo.
    echo [提示] 请先运行 install.bat 安装依赖
    pause
    exit /b 1
)
echo [OK] 虚拟环境已就绪
echo.

echo ========================================
echo [步骤 2/6: 检查 Redis]
echo ========================================
echo.

redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Redis 未运行或未安装
    echo [WARNING] Celery 任务队列需要 Redis
    echo [WARNING] 请先启动 Redis 服务
    echo.
    echo [提示] 如果没有 Redis，视频处理功能将不可用
    echo.
    set REDIS_READY=0
) else (
    echo [OK] Redis 已就绪
    echo.
    set REDIS_READY=1
)

echo ========================================
echo [步骤 3/6: 检查 FFmpeg]
echo ========================================
echo.

ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] FFmpeg 未找到
    echo [WARNING] 视频处理功能将不可用
    echo.
    echo [提示] 请下载 FFmpeg 并添加到系统 PATH
    echo [提示] 下载地址: https://ffmpeg.org/download.html
    echo.
    set FFMPEG_READY=0
) else (
    echo [OK] FFmpeg 已就绪
    echo.
    set FFMPEG_READY=1
)

echo ========================================
echo [步骤 4/6: 准备启动
echo ========================================
echo.

echo [INFO] 即将启动以下服务:
echo [INFO] 1. FastAPI 后端服务 (端口 8000)
echo [INFO] 2. Celery 任务队列
echo [INFO] 3. 前端开发服务器 (端口 5173)
echo [INFO] 4. 弹幕监控服务 (端口 5000)
echo.

echo [INFO] 每个服务将在独立的新窗口中启动
echo.

timeout /t 3 /nobreak >nul

echo ========================================
echo [步骤 5/6: 启动服务
echo ========================================
echo.

echo [1/4] 启动 FastAPI 后端服务...
start "AutoClip - FastAPI 后端" cmd /k "cd /d %SCRIPT_DIR% && echo 启动 FastAPI 后端... && echo URL: http://localhost:8000 && echo API 文档: http://localhost:8000/docs && echo 按 Ctrl+C 停止服务 && echo ======================================== && %VENV_DIR%\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1"

echo [OK] FastAPI 后端启动中...
timeout /t 3 /nobreak >nul

if "%REDIS_READY%"=="1" (
    echo [2/4] 启动 Celery 任务队列...
    start "AutoClip - Celery Worker" cmd /k "cd /d %SCRIPT_DIR%\backend && echo 启动 Celery 任务队列... && echo 按 Ctrl+C 停止服务 && echo ======================================== && set PYTHONPATH=%CD% && %VENV_DIR%\Scripts\celery.exe -A core.celery_app worker --loglevel=info --concurrency=4"
    echo [OK] Celery 启动中...
) else (
    echo [2/4] 跳过 Celery (Redis 未就绪，跳过)
)
timeout /t 2 /nobreak >nul

echo [3/4] 启动前端开发服务器...
start "AutoClip - 前端服务" cmd /k "cd /d %SCRIPT_DIR%\frontend && echo 启动前端开发服务器... && echo URL: http://localhost:5173 && echo 按 Ctrl+C 停止服务 && echo ======================================== && npm run dev"
echo [OK] 前端服务启动中...
timeout /t 5 /nobreak >nul

echo [4/4] 启动弹幕监控服务...
start "AutoClip - 弹幕监控" cmd /k "cd /d %SCRIPT_DIR%\monitor && echo 启动弹幕监控服务... && echo URL: http://localhost:5000 && echo 按 Ctrl+C 停止服务 && echo ======================================== && %VENV_DIR%\Scripts\python.exe jk.py"
echo [OK] 弹幕监控服务启动中...
echo.

echo ========================================
echo [步骤 6/6: 服务启动完成
echo ========================================
echo.

echo ╔═══════════════════════════════════════════════════════════════╗
echo ║                                                                   ║
echo ║                        所有服务已启动！                             ║
echo ║                                                                   ║
echo ╠═══════════════════════════════════════════════════════════════╣
echo ║                                                                   ║
echo ║  🌐 统一前端入口:                                                ║
echo ║     http://localhost:5173                                         ║
echo ║                                                                   ║
echo ╠═══════════════════════════════════════════════════════════════╣
echo ║                                                                   ║
echo ║  🔧 各服务地址:                                                  ║
echo ║     FastAPI 后端:    http://localhost:8000                     ║
echo ║     API 文档 (Swagger): http://localhost:8000/docs              ║
echo ║     API ReDoc:         http://localhost:8000/redoc             ║
echo ║     弹幕监控服务:      http://localhost:5000                     ║
echo ║                                                                   ║
echo ╠═══════════════════════════════════════════════════════════════╣
echo ║                                                                   ║
echo ║  🎯 功能模块:                                                    ║
echo ║     - 弹幕监控: 今日数据、多房间监控、弹幕分析、历史数据         ║
echo ║     - AI 切片: 项目管理、视频处理、智能评分、自动切片            ║
echo ║     - 设置: LLM 配置、步骤配置、系统配置                          ║
echo ║                                                                   ║
echo ╠═══════════════════════════════════════════════════════════════╣
echo ║                                                                   ║
echo ║  ⚠️  注意事项:                                                    ║
echo ║     - 关闭对应窗口以停止服务                                         ║
echo ║     - 日志文件位于 logs/ 目录                                     ║
echo ║     - 如需重新安装依赖，请删除 venv 文件夹并运行 install.bat     ║
echo ║                                                                   ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.

echo [INFO] 等待前端服务完全启动...
timeout /t 3 /nobreak >nul

echo [INFO] 正在打开浏览器...
start http://localhost:5173

echo.
echo [INFO] 浏览器已打开。关闭对应窗口以停止服务。
echo.
echo ========================================
echo [提示]
echo ========================================
echo.
echo - 统一前端入口: http://localhost:5173
echo - 导航栏可切换: 弹幕监控 / AI 切片 / 设置
echo - 弹幕监控下拉菜单包含: 今日数据、多房间监控、弹幕分析、历史数据
echo.
echo ========================================
pause