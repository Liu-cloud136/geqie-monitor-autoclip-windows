"""
数据库配置
包含数据库连接、会话管理和依赖注入
支持 SQLite 和 PostgreSQL
"""

import os
import logging
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool, QueuePool
from typing import Generator
from models.base import Base

logger = logging.getLogger(__name__)

def _get_project_root_from_file() -> Path:
    """从当前文件位置确定项目根目录（最可靠的方式）"""
    # 当前文件: backend/core/database.py
    # 向上两级到达项目根目录
    current_path = Path(__file__).resolve().parent  # backend/core/
    project_root = current_path.parent.parent  # autoclip-windows/
    
    # 验证这确实是项目根目录
    if (project_root / "frontend").exists() and (project_root / "backend").exists():
        return project_root
    
    # 如果验证失败，使用遍历查找
    current_path = Path(__file__).resolve().parent
    while current_path.parent != current_path:
        if (current_path / "frontend").exists() and (current_path / "backend").exists():
            return current_path
        current_path = current_path.parent
    
    # 最后的回退
    return Path(__file__).resolve().parent.parent.parent

def _ensure_data_directory():
    """确保数据目录存在"""
    try:
        # 优先使用 path_utils.py 中的逻辑
        from .path_utils import get_data_directory
        data_dir = get_data_directory()
        return data_dir
    except ImportError:
        # 如果导入失败，使用当前文件路径确定项目根目录
        project_root = _get_project_root_from_file()
        data_dir = project_root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

def _get_absolute_database_url() -> str:
    """获取绝对路径的数据库URL（最可靠的方式）"""
    project_root = _get_project_root_from_file()
    db_path = project_root / "data" / "autoclip.db"
    return f"sqlite:///{db_path}"

def _ensure_absolute_url(url: str) -> str:
    """确保数据库URL是绝对路径"""
    if url.startswith("sqlite:///"):
        db_path_str = url[len("sqlite:///"):]
        db_path = Path(db_path_str)
        
        if not db_path.is_absolute():
            # 转换为绝对路径
            project_root = _get_project_root_from_file()
            absolute_db_path = project_root / db_path_str
            new_url = f"sqlite:///{absolute_db_path}"
            logger.warning(f"将相对路径数据库URL转换为绝对路径: {url} -> {new_url}")
            return new_url
    
    return url

# 数据库配置
# 优先使用环境变量，但确保是绝对路径
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # 确保环境变量中的URL是绝对路径
    DATABASE_URL = _ensure_absolute_url(DATABASE_URL)
else:
    # 使用最可靠的路径检测方式
    DATABASE_URL = _get_absolute_database_url()

logger.info(f"数据库URL: {DATABASE_URL}")

# 在创建引擎之前确保数据库目录存在
if "sqlite" in DATABASE_URL:
    # 解析 SQLite 路径并确保目录存在
    sqlite_prefix = "sqlite:///"
    if DATABASE_URL.startswith(sqlite_prefix):
        db_path_str = DATABASE_URL[len(sqlite_prefix):]
        db_path = Path(db_path_str)
        db_path.parent.mkdir(parents=True, exist_ok=True)

def _enable_sqlite_wal(dbapi_connection, connection_record):
    """启用SQLite的WAL模式以支持更好的并发"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()

# 创建数据库引擎
if "sqlite" in DATABASE_URL:
    # SQLite配置 - 优化连接池和并发
    # 启用WAL模式以支持更好的多进程并发
    engine = create_engine(
        DATABASE_URL,
        connect_args={
            "check_same_thread": False,  # 允许跨线程访问
            "timeout": 30,                # 增加超时时间到30秒
            "isolation_level": None       # 自动提交模式
        },
        poolclass=StaticPool,             # SQLite使用静态池
        pool_pre_ping=True,              # 连接健康检查，避免使用失效的连接
        echo=False
    )
    
    # 注册事件监听器以在每个连接上启用WAL模式
    from sqlalchemy import event
    event.listen(engine, "connect", _enable_sqlite_wal)
elif "postgresql" in DATABASE_URL or "postgres" in DATABASE_URL:
    # PostgreSQL配置 - 生产环境优化
    # 使用QueuePool进行连接池管理，适合高并发场景
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=20,           # 增加连接池基础大小
        max_overflow=30,        # 增加最大溢出连接数（总共最多50个连接）
        pool_pre_ping=True,     # 连接前检测，避免使用失效的连接
        pool_recycle=3600,      # 连接回收时间（1小时），避免长时间连接失效
        echo=False
    )
else:
    # 其他数据库（MySQL等）的默认配置
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,      # 5分钟回收连接
        echo=False
    )

# 创建会话工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_db() -> Generator[Session, None, None]:
    """
    数据库会话依赖注入
    用于FastAPI的依赖注入系统
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """创建所有数据库表"""
    Base.metadata.create_all(bind=engine)

def drop_tables():
    """删除所有数据库表"""
    Base.metadata.drop_all(bind=engine)

def reset_database():
    """重置数据库"""
    drop_tables()
    create_tables()

from sqlalchemy import text

def test_connection() -> bool:
    """测试数据库连接"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1")).fetchone()
        return True
    except Exception as e:
        print(f"数据库连接测试失败: {e}")
        return False

def get_database_url() -> str:
    """获取数据库URL（与 config.py 保持一致）"""
    from .config import get_database_url as _get_database_url
    return _get_database_url()

# 数据库初始化
def init_database():
    """初始化数据库"""
    print("正在初始化数据库...")
    
    # 测试连接
    if not test_connection():
        print("❌ 数据库连接失败")
        return False
    
    # 创建表
    try:
        create_tables()
        print("✅ 数据库表创建成功")
        return True
    except Exception as e:
        print(f"❌ 数据库表创建失败: {e}")
        return False

if __name__ == "__main__":
    # 直接运行此文件时初始化数据库
    init_database()