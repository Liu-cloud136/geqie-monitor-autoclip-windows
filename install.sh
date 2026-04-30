#!/bin/bash

set -e

echo "========================================"
echo "鸽切监控 + AI 视频切片系统"
echo "统一安装脚本 (Linux/Mac)"
echo "========================================"
echo ""

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"

echo "项目目录: $PROJECT_DIR"
echo "虚拟环境目录: $VENV_DIR"
echo ""

echo "========================================"
echo "检查 Python 环境"
echo "========================================"
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "[错误] 未找到 Python，请先安装 Python 3.9+"
        echo "下载地址: https://www.python.org/downloads/"
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

echo "[OK] Python 已安装"
$PYTHON_CMD --version
echo ""

echo "========================================"
echo "创建虚拟环境"
echo "========================================"
if [ -d "$VENV_DIR" ]; then
    echo "[提示] 虚拟环境已存在"
    echo "如需重新安装，请先删除 venv 目录"
else
    echo "[正在创建] 虚拟环境..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "[错误] 虚拟环境创建失败"
        exit 1
    fi
    echo "[OK] 虚拟环境创建成功"
fi
echo ""

echo "========================================"
echo "激活虚拟环境"
echo "========================================"
source "$VENV_DIR/bin/activate"
echo "[OK] 虚拟环境已激活"
echo ""

echo "========================================"
echo "升级 pip"
echo "========================================"
pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
echo ""

echo "========================================"
echo "安装 Python 依赖（使用清华镜像）"
echo "========================================"
echo "这可能需要几分钟时间，请耐心等待..."
echo ""

pip install -r "$PROJECT_DIR/requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple || {
    echo ""
    echo "[警告] 部分依赖安装失败，尝试使用官方源..."
    pip install -r "$PROJECT_DIR/requirements.txt" || {
        echo "[错误] 依赖安装失败，请检查网络连接"
        exit 1
    }
}
echo ""
echo "[OK] Python 依赖安装完成"
echo ""

echo "========================================"
echo "安装 bcut-asr 语音识别组件"
echo "========================================"
cd "$PROJECT_DIR/backend/bcut-asr"
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple || {
    echo "[警告] bcut-asr 安装可能有问题，但可以继续"
}
echo "[OK] bcut-asr 安装完成"
echo ""

echo "========================================"
echo "初始化切片系统数据库"
echo "========================================"
cd "$PROJECT_DIR/backend"

if [ ! -d "data" ]; then
    mkdir -p data
    echo "[已创建] data 目录"
fi

python init_db.py || {
    echo "[警告] 数据库初始化可能有问题"
    echo "请检查 .env 配置"
}
echo "[OK] 数据库初始化完成"
echo ""

echo "========================================"
echo "检查前端环境"
echo "========================================"
if ! command -v node &> /dev/null; then
    echo "[提示] 未找到 Node.js，前端功能将不可用"
    echo "如需使用切片系统前端，请安装 Node.js 18.x+"
    echo "下载地址: https://nodejs.org/"
else
    echo "[OK] Node.js 已安装"
    node --version
    
    echo ""
    echo "========================================"
    echo "安装前端依赖"
    echo "========================================"
    cd "$PROJECT_DIR/frontend"
    
    echo "正在安装依赖..."
    npm install || {
        echo "[警告] 前端依赖安装失败"
        echo "请手动执行: cd frontend && npm install"
    }
    echo "[OK] 前端依赖安装完成"
fi
echo ""

echo "========================================"
echo "安装完成！"
echo "========================================"
echo ""
echo "虚拟环境位置: $VENV_DIR"
echo ""
echo "下一步操作:"
echo "1. 配置环境变量:"
echo "   - 复制 .env.example 为 .env"
echo "   - 填写 LLM API Key 和 B站 Cookie"
echo ""
echo "2. 配置弹幕监控系统:"
echo "   - 复制 monitor/config.yaml.example 为 monitor/config.yaml"
echo "   - 填写直播间 ID 和管理员密码"
echo ""
echo "3. 安装外部依赖:"
echo "   - Redis 5.0+ (用于 Celery 任务队列)"
echo "   - FFmpeg 4.0+ (用于视频处理)"
echo ""
echo "4. 启动服务:"
echo "   - 激活虚拟环境: source venv/bin/activate"
echo "   - 启动监控系统: cd monitor && python jk.py"
echo "   - 启动后端 API: cd backend && python main.py"
echo "   - 启动 Celery: cd backend && celery -A tasks worker --loglevel=info"
echo "   - 启动前端: cd frontend && npm run dev"
echo ""
echo "访问地址:"
echo "- 弹幕监控系统: http://localhost:5000"
echo "- 切片系统前端: http://localhost:5173"
echo "- API 文档: http://localhost:8000/docs"
echo ""
echo "========================================"
