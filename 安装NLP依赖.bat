@echo off
chcp 65001 >nul
title 安装 NLP 依赖 - SnowNLP / jieba / wordcloud

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║         安装 NLP 依赖包                                        ║
echo ║         SnowNLP (情感分析)                                     ║
echo ║         jieba (中文分词)                                       ║
echo ║         wordcloud (词云生成)                                   ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

set PROJECT_DIR=%~dp0
set VENV_DIR=%PROJECT_DIR%venv

echo [信息] 项目目录: %PROJECT_DIR%
echo.

:: 检查虚拟环境
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [错误] 虚拟环境不存在，请先运行 install.bat
    pause
    exit /b 1
)

:: 激活虚拟环境
call "%VENV_DIR%\Scripts\activate.bat"
echo [OK] 虚拟环境已激活
echo.

:: 升级 pip
echo [步骤 1/4] 升级 pip...
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
echo.

:: 安装 SnowNLP
echo [步骤 2/4] 安装 SnowNLP (情感分析)...
pip install snownlp -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [警告] SnowNLP 安装失败，尝试官方源...
    pip install snownlp
)
echo.

:: 安装 jieba
echo [步骤 3/4] 安装 jieba (中文分词)...
pip install jieba -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [警告] jieba 安装失败，尝试官方源...
    pip install jieba
)
echo.

:: 安装 wordcloud (注意: wordcloud 需要 Visual C++ 或预编译版本)
echo [步骤 4/4] 安装 wordcloud (词云生成)...
pip install wordcloud -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo.
    echo [警告] wordcloud 安装失败
    echo.
    echo 可能的原因:
    echo 1. 需要 Visual C++ 14.0 或更高版本
    echo 2. 或者可以尝试安装预编译版本
    echo.
    echo 解决方法:
    echo 方法 1: 安装 Microsoft C++ Build Tools
    echo         https://visualstudio.microsoft.com/visual-cpp-build-tools/
    echo.
    echo 方法 2: 从非官方 wheel 安装
    echo         访问: https://www.lfd.uci.edu/~gohlke/pythonlibs/#wordcloud
    echo         下载对应版本的 .whl 文件，然后运行:
    echo         pip install 下载的文件名.whl
    echo.
    echo 方法 3: 使用 conda (如果你用 Anaconda)
    echo         conda install -c conda-forge wordcloud
    echo.
    echo 注意: wordcloud 是可选依赖，不影响核心功能
    echo.
)
echo.

:: 验证安装
echo ========================================
echo 验证安装结果:
echo ========================================
echo.

echo 检查 SnowNLP...
pip show snownlp >nul 2>&1
if errorlevel 1 (
    echo [失败] SnowNLP 未安装
) else (
    echo [成功] SnowNLP 已安装
    pip show snownlp | findstr /i "Version Location"
)
echo.

echo 检查 jieba...
pip show jieba >nul 2>&1
if errorlevel 1 (
    echo [失败] jieba 未安装
) else (
    echo [成功] jieba 已安装
    pip show jieba | findstr /i "Version Location"
)
echo.

echo 检查 wordcloud...
pip show wordcloud >nul 2>&1
if errorlevel 1 (
    echo [可选] wordcloud 未安装 (不影响核心功能)
) else (
    echo [成功] wordcloud 已安装
    pip show wordcloud | findstr /i "Version Location"
)
echo.

echo ========================================
echo 安装完成!
echo ========================================
echo.
echo 现在可以运行 "一键启动弹幕监控.bat" 启动系统
echo.

pause
