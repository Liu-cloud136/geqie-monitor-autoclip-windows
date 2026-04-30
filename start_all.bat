@echo off
chcp 65001 >nul
echo ========================================
echo 鸽切监控 + AI 视频切片系统
echo 统一启动脚本
echo ========================================
echo.
echo 此脚本将启动以下服务:
echo 1. FastAPI 后端服务 (端口 8000)
echo 2. Celery 任务队列
echo 3. 前端开发服务器 (端口 5173)
echo 4. 弹幕监控服务 (端口 5000)
echo.
echo 注意: 四个新窗口将被打开
echo.

set PROJECT_DIR=%~dp0
set VENV_DIR=%PROJECT_DIR%venv

cd /d "%PROJECT_DIR%"

echo [检查] 虚拟环境...
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [错误] 虚拟环境未找到
    echo 请先运行 install.bat 安装依赖
    pause
    exit /b 1
)
echo [OK] 虚拟环境已就绪
echo.

echo [检查] Redis...
redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo [警告] Redis 未运行或未安装
    echo Celery 任务队列需要 Redis
    echo 请先启动 Redis 服务
    echo.
    pause
    exit /b 1
)
echo [OK] Redis 已就绪
echo.

echo [检查] FFmpeg...
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [警告] FFmpeg 未找到
    echo 视频处理功能将不可用
    echo 请下载 FFmpeg 并添加到系统 PATH
    echo 下载地址: https://ffmpeg.org/download.html
    echo.
    pause
) else (
    echo [OK] FFmpeg 已就绪
)
echo.

echo ========================================
echo 开始启动服务
echo ========================================
echo.

echo [1/4] 启动 FastAPI 后端服务...
echo 窗口: AutoClip - FastAPI Server
start "AutoClip - FastAPI Server" cmd /k "cd /d "%PROJECT_DIR%" ^&^& start_backend.bat"

echo 等待 5 秒让服务启动...
timeout /t 5 /nobreak >nul
echo.

echo [2/4] 启动 Celery 任务队列...
echo 窗口: AutoClip - Celery Worker
start "AutoClip - Celery Worker" cmd /k "cd /d "%PROJECT_DIR%" ^&^& start_celery.bat"

echo 等待 3 秒让服务启动...
timeout /t 3 /nobreak >nul
echo.

echo [3/4] 启动前端开发服务器...
echo 窗口: AutoClip - Frontend
start "AutoClip - Frontend" cmd /k "cd /d "%PROJECT_DIR%frontend" ^&^& npm run dev"

echo 等待 3 秒让服务启动...
timeout /t 3 /nobreak >nul
echo.

echo [4/4] 启动弹幕监控服务...
echo 窗口: 弹幕监控系统
start "弹幕监控系统" cmd /k "cd /d "%PROJECT_DIR%" ^&^& start_monitor.bat"

echo.
echo ========================================
echo 所有服务已启动！
echo ========================================
echo.
echo 访问地址:
echo - 弹幕监控系统: http://localhost:5000
echo - 切片系统前端: http://localhost:5173
echo - FastAPI 后端: http://localhost:8000
echo - API 文档: http://localhost:8000/docs
echo - API ReDoc: http://localhost:8000/redoc
echo.
echo 等待前端就绪...
timeout /t 5 /nobreak >nul

echo 正在打开浏览器...
start http://localhost:5173

echo.
echo 浏览器已打开。关闭对应窗口可停止各服务。
echo.
echo ========================================
echo 提示:
echo - 如果服务启动失败，请检查 .env 和 config.yaml 配置
echo - 日志文件位于 logs/ 目录
echo - 如需重新安装依赖，请删除 venv 目录后重新运行 install.bat
echo ========================================
echo.
pause
