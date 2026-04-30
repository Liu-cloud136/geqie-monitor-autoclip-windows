"""
统一配置管理
集中管理应用的所有配置项
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, AliasChoices, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _detect_project_root() -> Path:
    """自动检测项目根目录"""
    current_path = Path(__file__).parent
    
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


def _ensure_absolute_database_url(url: str) -> str:
    """确保数据库URL使用绝对路径"""
    if url.startswith("sqlite:///"):
        db_path_str = url[len("sqlite:///"):]
        db_path = Path(db_path_str)
        
        if not db_path.is_absolute():
            project_root = _detect_project_root()
            absolute_db_path = project_root / db_path_str
            return f"sqlite:///{absolute_db_path}"
    
    return url


class APISettings(BaseModel):
    """API配置"""
    dashscope_api_key: str = Field(default='', validation_alias=AliasChoices('API_DASHSCOPE_API_KEY'))
    model_name: str = Field(default='qwen-plus', validation_alias=AliasChoices('API_MODEL_NAME'))
    max_tokens: int = Field(default=4096, validation_alias=AliasChoices('API_MAX_TOKENS'))
    timeout: int = Field(default=30, validation_alias=AliasChoices('API_TIMEOUT'))


class DatabaseSettings(BaseModel):
    """数据库配置"""
    url: str = Field(default_factory=_get_default_database_url, validation_alias=AliasChoices('DATABASE_URL'))
    
    @model_validator(mode='after')
    def ensure_absolute_path(self) -> 'DatabaseSettings':
        """确保数据库URL使用绝对路径"""
        self.url = _ensure_absolute_database_url(self.url)
        return self

class RedisSettings(BaseModel):
    """Redis配置"""
    url: str = Field(default='redis://localhost:6379/0', validation_alias=AliasChoices('REDIS_URL'))

class ProcessingSettings(BaseModel):
    """处理配置"""
    chunk_size: int = Field(default=5000, validation_alias=AliasChoices('PROCESSING_CHUNK_SIZE'))
    min_score_threshold: float = Field(default=70, validation_alias=AliasChoices('PROCESSING_MIN_SCORE_THRESHOLD'))  # 100分制
    max_clips_per_collection: int = Field(default=5, validation_alias=AliasChoices('PROCESSING_MAX_CLIPS_PER_COLLECTION'))
    max_retries: int = Field(default=3, validation_alias=AliasChoices('PROCESSING_MAX_RETRIES'))

class LoggingSettings(BaseModel):
    """日志配置"""
    level: str = Field(default='INFO', validation_alias=AliasChoices('LOG_LEVEL'))
    fmt: str = Field(default='%(asctime)s - %(name)s - %(levelname)s - %(message)s', validation_alias=AliasChoices('LOG_FORMAT'))
    file: str = Field(default='backend.log', validation_alias=AliasChoices('LOG_FILE'))

class Settings(BaseSettings):
    """应用设置"""
    # 允许 .env + 忽略未声明的键，避免"Extra inputs are not permitted"
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent.parent / '.env'),
        env_file_encoding='utf-8',
        extra='ignore'
    )

    environment: str = Field(default='development', validation_alias=AliasChoices('ENVIRONMENT'))
    debug: bool = Field(default=True, validation_alias=AliasChoices('DEBUG'))
    encryption_key: str = Field(default='', validation_alias=AliasChoices('ENCRYPTION_KEY'))

    # 直接定义字段，不使用嵌套的BaseModel
    database_url: str = Field(default_factory=_get_default_database_url, validation_alias=AliasChoices('DATABASE_URL'))
    
    @model_validator(mode='after')
    def ensure_absolute_paths(self) -> 'Settings':
        """确保所有路径都是绝对路径"""
        self.database_url = _ensure_absolute_database_url(self.database_url)
        return self

    redis_url: str = Field(default='redis://localhost:6379/0', validation_alias=AliasChoices('REDIS_URL'))
    api_dashscope_api_key: str = Field(default='', validation_alias=AliasChoices('API_DASHSCOPE_API_KEY'))
    api_model_name: str = Field(default='qwen-plus', validation_alias=AliasChoices('API_MODEL_NAME'))
    api_max_tokens: int = Field(default=4096, validation_alias=AliasChoices('API_MAX_TOKENS'))
    api_timeout: int = Field(default=30, validation_alias=AliasChoices('API_TIMEOUT'))
    processing_chunk_size: int = Field(default=5000, validation_alias=AliasChoices('PROCESSING_CHUNK_SIZE'))
    processing_min_score_threshold: float = Field(default=70, validation_alias=AliasChoices('PROCESSING_MIN_SCORE_THRESHOLD'))
    processing_max_clips_per_collection: int = Field(default=5, validation_alias=AliasChoices('PROCESSING_MAX_CLIPS_PER_COLLECTION'))
    processing_max_retries: int = Field(default=3, validation_alias=AliasChoices('PROCESSING_MAX_RETRIES'))
    video_use_stream_copy: bool = Field(default=True, validation_alias=AliasChoices('VIDEO_USE_STREAM_COPY'))
    video_use_hardware_accel: bool = Field(default=True, validation_alias=AliasChoices('VIDEO_USE_HARDWARE_ACCEL'))
    video_encoder_preset: str = Field(default='p6', validation_alias=AliasChoices('VIDEO_ENCODER_PRESET'))
    video_crf: int = Field(default=23, validation_alias=AliasChoices('VIDEO_CRF'))
    log_level: str = Field(default='INFO', validation_alias=AliasChoices('LOG_LEVEL'))
    log_format: str = Field(default='%(asctime)s - %(name)s - %(levelname)s - %(message)s', validation_alias=AliasChoices('LOG_FORMAT'))
    log_file: str = Field(default='logs/backend.log', validation_alias=AliasChoices('LOG_FILE'))

# 全局配置实例
settings = Settings()

def get_project_root() -> Path:
    """获取项目根目录"""
    # 使用新的路径工具
    from core.path_utils import get_project_root as get_root
    return get_root()

def get_data_directory() -> Path:
    """获取数据目录"""
    project_root = get_project_root()
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir

def get_uploads_directory() -> Path:
    """获取上传文件目录"""
    data_dir = get_data_directory()
    uploads_dir = data_dir / "uploads"
    uploads_dir.mkdir(exist_ok=True)
    return uploads_dir

def get_temp_directory() -> Path:
    """获取临时文件目录"""
    data_dir = get_data_directory()
    temp_dir = data_dir / "temp"
    temp_dir.mkdir(exist_ok=True)
    return temp_dir

def get_output_directory() -> Path:
    """获取输出文件目录"""
    data_dir = get_data_directory()
    output_dir = data_dir / "output"
    output_dir.mkdir(exist_ok=True)
    return output_dir

def get_database_url() -> str:
    """获取数据库URL"""
    # 使用绝对路径避免相对路径导致的问题
    project_root = get_project_root()
    db_path = project_root / "data" / "autoclip.db"
    return f"sqlite:///{db_path}"

def get_redis_url() -> str:
    """获取Redis URL"""
    return settings.redis_url

def get_api_key() -> Optional[str]:
    """获取API密钥"""
    return settings.api_dashscope_api_key if settings.api_dashscope_api_key else None

def get_model_config() -> Dict[str, Any]:
    """获取模型配置"""
    return {
        "model_name": settings.api_model_name,
        "max_tokens": settings.api_max_tokens,
        "timeout": settings.api_timeout
    }

def get_processing_config() -> Dict[str, Any]:
    """获取处理配置"""
    return {
        "chunk_size": settings.processing_chunk_size,
        "min_score_threshold": settings.processing_min_score_threshold,
        "max_clips_per_collection": settings.processing_max_clips_per_collection,
        "max_retries": settings.processing_max_retries
    }

def get_video_config() -> Dict[str, Any]:
    """获取视频处理配置"""
    return {
        "use_stream_copy": settings.video_use_stream_copy,
        "use_hardware_accel": settings.video_use_hardware_accel,
        "encoder_preset": settings.video_encoder_preset,
        "crf": settings.video_crf
    }

def get_logging_config() -> Dict[str, Any]:
    """获取日志配置"""
    project_root = get_project_root()
    log_file_path = project_root / settings.log_file
    return {
        "level": settings.log_level,
        "format": settings.log_format,
        "file": str(log_file_path)
    }

# 初始化路径配置
def init_paths():
    """初始化路径配置"""
    project_root = get_project_root()
    data_dir = get_data_directory()
    uploads_dir = get_uploads_directory()
    temp_dir = get_temp_directory()
    output_dir = get_output_directory()
    
    print(f"项目根目录: {project_root}")
    print(f"数据目录: {data_dir}")
    print(f"上传目录: {uploads_dir}")
    print(f"临时目录: {temp_dir}")
    print(f"输出目录: {output_dir}")

if __name__ == "__main__":
    # 测试配置加载
    init_paths()
    print(f"数据库URL: {get_database_url()}")
    print(f"Redis URL: {get_redis_url()}")
    print(f"API配置: {get_model_config()}")
    print(f"处理配置: {get_processing_config()}")