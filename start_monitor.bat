@echo off
chcp 65001 >nul
echo ========================================
echo 鸽切监控 + AI 视频切片系统
echo 弹幕监控服务
echo ========================================
echo.

set PROJECT_DIR=%~dp0
set VENV_DIR=%PROJECT_DIR%venv

cd /d "%PROJECT_DIR%monitor"

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [错误] 虚拟环境未找到
    echo 请先运行 install.bat 安装依赖
    pause
    exit /b 1
)

echo [正在激活] 虚拟环境...
call "%VENV_DIR%\Scripts\activate.bat"

echo.
echo [检查] 配置文件...
if not exist "config.yaml" (
    echo [警告] 配置文件未找到
    echo 请复制 config.yaml.example 为 config.yaml
    echo 并填写直播间 ID 和管理员密码
    echo.
    echo 使用默认配置继续运行...
    echo.
)

echo [正在启动] 弹幕监控服务...
echo URL: http://localhost:5000
echo.
echo 按 Ctrl+C 停止服务
echo.

python jk.py

pause
