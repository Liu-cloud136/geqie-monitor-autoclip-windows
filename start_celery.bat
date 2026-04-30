@echo off
chcp 65001 >nul
echo ========================================
echo 鸽切监控 + AI 视频切片系统
echo Celery 任务队列
echo ========================================
echo.

set PROJECT_DIR=%~dp0
set VENV_DIR=%PROJECT_DIR%venv

cd /d "%PROJECT_DIR%backend"

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [错误] 虚拟环境未找到
    echo 请先运行 install.bat 安装依赖
    pause
    exit /b 1
)

echo [正在激活] 虚拟环境...
call "%VENV_DIR%\Scripts\activate.bat"

echo.
echo [正在创建] 日志目录...
if not exist "%PROJECT_DIR%logs" (
    mkdir "%PROJECT_DIR%logs"
    echo [OK] 日志目录已创建
)

echo.
echo [正在启动] Celery Worker...
echo 任务队列: processing, celery
echo 并发数: 4
echo.
echo 按 Ctrl+C 停止服务
echo.
echo ========================================
echo 日志文件: %PROJECT_DIR%logs\celery_worker.log
echo ========================================
echo.

set PYTHONPATH=%CD%
set PYTHONUNBUFFERED=1

python -u -m celery -A core.celery_app worker --loglevel=info --concurrency=4 -Q processing,celery --include=tasks.import_processing,tasks.processing,tasks.video,tasks.thumbnail_task,tasks.notification,tasks.maintenance,tasks.data_cleanup 2>&1 | tee "%PROJECT_DIR%logs\celery_worker.log"

pause
