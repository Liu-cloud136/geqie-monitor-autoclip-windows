@echo off
chcp 65001 >nul
title 鸽切弹幕监控 + 自动切片系统 - 一键启动

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║     鸽切弹幕监控 + 自动切片系统                                ║
echo ║     Geqie Danmaku Monitor + Auto Clip System                  ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

set PROJECT_DIR=%~dp0
set VENV_DIR=%PROJECT_DIR%venv

echo [信息] 项目目录: %PROJECT_DIR%
echo [信息] 虚拟环境: %VENV_DIR%
echo.

:: ========================================
:: 步骤 1: 检查并创建虚拟环境
:: ========================================
echo [步骤 1/7] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.9+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python 版本:
python --version
echo.

:: ========================================
:: 步骤 2: 检查虚拟环境
:: ========================================
echo [步骤 2/7] 检查虚拟环境...
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [信息] 虚拟环境不存在，正在创建...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [错误] 虚拟环境创建失败
        pause
        exit /b 1
    )
    echo [OK] 虚拟环境创建成功
) else (
    echo [OK] 虚拟环境已存在
)
echo.

:: ========================================
:: 步骤 3: 激活虚拟环境并安装/更新依赖
:: ========================================
echo [步骤 3/7] 检查 Python 依赖...
call "%VENV_DIR%\Scripts\activate.bat"

:: 升级 pip
echo [信息] 升级 pip...
python -m pip install --upgrade pip -q -i https://pypi.tuna.tsinghua.edu.cn/simple 2>nul

:: 检查并安装 NLP 依赖 (SnowNLP, jieba, wordcloud)
echo [信息] 检查 NLP 依赖...

pip show snownlp >nul 2>&1
if errorlevel 1 (
    echo [安装] SnowNLP (情感分析)...
    pip install snownlp -q -i https://pypi.tuna.tsinghua.edu.cn/simple
) else (
    echo [OK] SnowNLP 已安装
)

pip show jieba >nul 2>&1
if errorlevel 1 (
    echo [安装] jieba (中文分词)...
    pip install jieba -q -i https://pypi.tuna.tsinghua.edu.cn/simple
) else (
    echo [OK] jieba 已安装
)

pip show wordcloud >nul 2>&1
if errorlevel 1 (
    echo [安装] wordcloud (词云生成)...
    pip install wordcloud -q -i https://pypi.tuna.tsinghua.edu.cn/simple
) else (
    echo [OK] wordcloud 已安装
)

echo.

:: ========================================
:: 步骤 4: 检查外部依赖
:: ========================================
echo [步骤 4/7] 检查外部依赖...

:: 检查 FFmpeg (视频处理)
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [警告] 未找到 FFmpeg，视频切片功能将不可用
    echo        下载地址: https://ffmpeg.org/download.html
    echo        下载后将 bin 目录添加到系统 PATH
) else (
    echo [OK] FFmpeg 已安装
)

echo.

:: ========================================
:: 步骤 5: 检查配置文件
:: ========================================
echo [步骤 5/7] 检查配置文件...

if not exist "%PROJECT_DIR%monitor\config.yaml" (
    echo [警告] 未找到 config.yaml
    if exist "%PROJECT_DIR%monitor\config.yaml.example" (
        echo [信息] 从 config.yaml.example 复制配置...
        copy "%PROJECT_DIR%monitor\config.yaml.example" "%PROJECT_DIR%monitor\config.yaml" >nul
        echo [OK] 配置文件已创建
    ) else (
        echo [错误] 配置文件缺失
        pause
        exit /b 1
    )
) else (
    echo [OK] 配置文件已存在
)

echo.

:: ========================================
:: 步骤 6: 启动服务
:: ========================================
echo [步骤 6/7] 启动服务...
echo.

cd /d "%PROJECT_DIR%"

:: 启动弹幕监控服务 (主服务)
echo [1/2] 启动弹幕监控服务...
echo       URL: http://localhost:5000
start "弹幕监控系统 - 端口 5000" cmd /k "%VENV_DIR%\Scripts\python.exe" monitor\jk.py

:: 等待服务启动
echo       等待 3 秒...
timeout /t 3 /nobreak >nul
echo.

:: ========================================
:: 步骤 7: 完成
:: ========================================
echo [步骤 7/7] 服务启动完成!
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                        🎉 启动成功!                            ║
echo ╠══════════════════════════════════════════════════════════════╣
echo ║                                                                  ║
echo ║  访问地址:                                                      ║
echo ║  ──────────────────────────────────────────────────────────── ║
echo ║  弹幕监控界面: http://localhost:5000                           ║
echo ║                   (包含弹幕列表、关键词监控、聊天室等)         ║
echo ║                                                                  ║
echo ║  自动切片配置:                                                   ║
echo ║  ──────────────────────────────────────────────────────────── ║
echo ║  - 配置文件: monitor/config.yaml                                ║
echo ║  - 关键词: 鸽切 (可在 monitor 配置节修改)                       ║
echo ║  - 切片缓冲: 前置 30秒 + 后置 30秒 = 60秒/每段                ║
echo ║  - 视频源: 配置 auto_clip.video_source_path                    ║
echo ║                                                                  ║
echo ║  使用说明:                                                       ║
echo ║  ──────────────────────────────────────────────────────────── ║
echo ║  1. 当有人发送包含"鸽切"的弹幕时，系统会自动:                  ║
echo ║     - 记录弹幕到数据库                                           ║
echo ║     - 发送邮件通知                                               ║
echo ║     - 触发自动视频切片 (需配置视频源)                           ║
echo ║                                                                  ║
echo ║  2. 视频切片配置:                                                ║
echo ║     - 在 config.yaml 的 auto_clip.video_source_path            ║
echo ║       填入直播录制的视频文件路径                                 ║
echo ║     - 示例: D:/recordings/live.mp4                              ║
echo ║                                                                  ║
echo ║  3. 如需前端管理界面:                                            ║
echo ║     - 安装 Node.js 18.x+                                        ║
echo ║     - 运行 install.bat 安装前端依赖                              ║
echo ║     - 运行 start_frontend.bat 启动前端                          ║
echo ║                                                                  ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: 打开浏览器
echo [信息] 正在打开浏览器...
start http://localhost:5000
echo.

echo [提示] 关闭窗口可停止对应服务
echo.
echo 按任意键查看当前服务状态...
pause >nul

echo.
echo ========================================
echo 当前运行的服务:
echo ========================================
echo.
tasklist /fi "WINDOWTITLE eq 弹幕监控系统*" 2>nul | find /i "python" >nul
if errorlevel 1 (
    echo [警告] 弹幕监控服务可能未运行
) else (
    echo [OK] 弹幕监控服务 (端口 5000) - 运行中
)
echo.

echo ========================================
echo 日志提示:
echo ========================================
echo - 关键词匹配时会显示: "保存鸽切数据"
echo - 自动切片触发时会显示: "自动切片请求已创建"
echo - 查看更多日志请打开弹幕监控系统窗口
echo.

pause
