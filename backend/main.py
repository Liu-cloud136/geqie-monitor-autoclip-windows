"""FastAPI应用入口点"""

import logging
import traceback
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import mimetypes

# 加载环境变量
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# 导入配置管理
from core.config import settings, get_logging_config, get_api_key

# 配置日志
import os

logging_config = get_logging_config()

# 确保日志目录存在
log_file = logging_config["file"]
log_dir = os.path.dirname(log_file)
if log_dir and not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

# 使用统一的日志配置系统
from core.logging_config import configure_logging, get_logger



# 配置结构化日志 - 同时输出到控制台和文件
configure_logging(
    level=logging_config["level"],
    log_file=log_file,
    json_logs=False,
    enable_console=True
)

logger = get_logger(__name__)

# 使用统一的API路由注册
from api.v1 import router as api_router
from core.database import engine
from models.base import Base

# Create FastAPI app
app = FastAPI(
    title="AutoClip API",
    description="AI视频切片处理API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 增加请求体大小限制（用于大文件上传）
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# 添加 GZip 压缩中间件
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 修改 CORS 中间件配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
@app.on_event("startup")
async def startup_event():
    logger.info("启动AutoClip API服务...")
    
    # 配置 MIME 类型
    mimetypes.init()
    mimetypes.add_type('application/javascript', '.js')
    mimetypes.add_type('text/css', '.css')
    
    # 创建数据库表
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表创建完成")
    
    # 加载API密钥到环境变量
    api_key = get_api_key()
    if api_key:
        import os
        os.environ["DASHSCOPE_API_KEY"] = api_key
        logger.info("API密钥已加载到环境变量")
    else:
        logger.warning("未找到API密钥配置")
    
    # 启动WebSocket网关服务
    from services.websocket_gateway_service import websocket_gateway_service
    await websocket_gateway_service.start()
    logger.info("WebSocket网关服务已启动")
    
    # 启动统一WebSocket服务
    from services.unified_websocket_service import unified_websocket_service
    await unified_websocket_service.start()
    logger.info("统一WebSocket服务已启动")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("正在关闭AutoClip API服务...")
    # 停止WebSocket网关服务
    from services.websocket_gateway_service import websocket_gateway_service
    await websocket_gateway_service.stop()
    logger.info("WebSocket网关服务已停止")
    # 停止统一WebSocket服务
    from services.unified_websocket_service import unified_websocket_service
    await unified_websocket_service.stop()
    logger.info("统一WebSocket服务已停止")

# Include unified API routes
app.include_router(api_router, prefix="/api/v1")



# 添加独立的video-categories端点
@app.get("/api/v1/video-categories")
async def get_video_categories():
    """获取视频分类配置."""
    return {
        "categories": [
            {
                "value": "default",
                "name": "默认",
                "description": "通用视频内容处理",
                "icon": "🎬",
                "color": "#4facfe"
            },
            {
                "value": "knowledge",
                "name": "知识科普",
                "description": "科学、技术、历史、文化等知识类内容",
                "icon": "📚",
                "color": "#52c41a"
            },
            {
                "value": "entertainment",
                "name": "娱乐",
                "description": "游戏、音乐、电影等娱乐内容",
                "icon": "🎮",
                "color": "#722ed1"
            },
            {
                "value": "business",
                "name": "商业",
                "description": "商业、创业、投资等商业内容",
                "icon": "💼",
                "color": "#fa8c16"
            },
            {
                "value": "experience",
                "name": "经验分享",
                "description": "个人经历、生活感悟等经验内容",
                "icon": "🌟",
                "color": "#eb2f96"
            },
            {
                "value": "opinion",
                "name": "观点评论",
                "description": "时事评论、观点分析等评论内容",
                "icon": "💭",
                "color": "#13c2c2"
            },
            {
                "value": "speech",
                "name": "演讲",
                "description": "公开演讲、讲座等演讲内容",
                "icon": "🎤",
                "color": "#f5222d"
            }
        ],
        "default_category": "default"
    }

# 导入统一错误处理中间件
from core.error_middleware import global_exception_handler

# 注册全局异常处理器
app.add_exception_handler(Exception, global_exception_handler)

if __name__ == "__main__":
    import uvicorn
    import sys
    
    # 默认端口
    port = 8000
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        for i, arg in enumerate(sys.argv):
            if arg == "--port" and i + 1 < len(sys.argv):
                try:
                    port = int(sys.argv[i + 1])
                except ValueError:
                    logger.error(f"无效的端口号: {sys.argv[i + 1]}")
                    port = 8000
    
    logger.info(f"启动服务器，端口: {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
