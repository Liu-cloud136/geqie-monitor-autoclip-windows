from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


def _detect_project_root() -> Path:
    """自动检测项目根目录"""
    current_path = Path(__file__).parent.parent
    
    while current_path.parent != current_path:
        if (current_path.parent / "frontend").exists() and (current_path.parent / "backend").exists():
            return current_path.parent
        current_path = current_path.parent
    
    return Path(__file__).parent.parent.parent


def _get_default_database_url() -> str:
    """获取默认的数据库URL（绝对路径）"""
    project_root = _detect_project_root()
    db_path = project_root / "data" / "autoclip.db"
    return f"sqlite:///{db_path}"


class DatabaseConfig(BaseModel):
    """数据库配置"""
    url: str = Field(default_factory=_get_default_database_url, description="数据库连接URL")
    echo: bool = Field(default=False, description="是否打印SQL语句")
    pool_size: int = Field(default=20, description="连接池大小")
    max_overflow: int = Field(default=30, description="最大溢出连接数")
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        if not v:
            raise ValueError('数据库URL不能为空')
        return v
    
    @model_validator(mode='after')
    def ensure_absolute_path(self) -> 'DatabaseConfig':
        """确保数据库URL使用绝对路径"""
        url = self.url
        
        if url.startswith("sqlite:///"):
            db_path_str = url[len("sqlite:///"):]
            db_path = Path(db_path_str)
            
            if not db_path.is_absolute():
                project_root = _detect_project_root()
                absolute_db_path = project_root / db_path_str
                self.url = f"sqlite:///{absolute_db_path}"
        
        return self
    
    @field_validator('pool_size')
    @classmethod
    def validate_pool_size(cls, v):
        if v < 1:
            raise ValueError('连接池大小必须大于0')
        if v > 100:
            raise ValueError('连接池大小不能超过100')
        return v
    
    @field_validator('max_overflow')
    @classmethod
    def validate_max_overflow(cls, v):
        if v < 0:
            raise ValueError('最大溢出连接数不能为负数')
        return v


class RedisConfig(BaseModel):
    """Redis 配置"""
    url: str = Field(default="redis://localhost:6379/0", description="Redis连接URL")
    max_connections: int = Field(default=10, description="最大连接数")
    socket_timeout: int = Field(default=5, description="Socket超时时间（秒）")
    decode_responses: bool = Field(default=True, description="是否解码响应")
    
    @field_validator('max_connections')
    @classmethod
    def validate_max_connections(cls, v):
        if v < 1:
            raise ValueError('最大连接数必须大于0')
        return v
    
    @field_validator('socket_timeout')
    @classmethod
    def validate_socket_timeout(cls, v):
        if v < 1:
            raise ValueError('Socket超时时间必须大于0秒')
        if v > 300:
            raise ValueError('Socket超时时间不能超过300秒')
        return v


class CeleryConfig(BaseModel):
    """Celery 配置"""
    broker_url: str = Field(default="redis://localhost:6379/1", description="Celery broker URL")
    result_backend: str = Field(default="redis://localhost:6379/2", description="Celery结果存储URL")
    always_eager: bool = Field(default=False, description="是否同步执行任务（调试模式）")
    concurrency: int = Field(default=4, gt=0, description="Worker并发数")
    
    @field_validator('concurrency')
    @classmethod
    def validate_concurrency(cls, v):
        if v < 1:
            raise ValueError('Worker并发数必须大于0')
        if v > 50:
            raise ValueError('Worker并发数不能超过50')
        return v
