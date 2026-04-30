import json
import logging
import os
from pathlib import Path
from typing import Dict, Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.database import DatabaseConfig, RedisConfig, CeleryConfig
from config.llm import LLMConfig
from config.app import (
    ProcessingConfig,
    VideoConfig,
    LoggingConfig,
    PathConfig
)

logger = logging.getLogger(__name__)


class AppConfig(BaseSettings):
    """应用主配置"""
    
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding='utf-8',
        extra='ignore'
    )
    
    # 基础配置
    environment: str = Field(default="development", description="运行环境")
    debug: bool = Field(default=True, description="调试模式")
    encryption_key: str = Field(default="", description="加密密钥")
    
    # 子配置
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    celery: CeleryConfig = Field(default_factory=CeleryConfig)
    paths: PathConfig = Field(default_factory=PathConfig)
    
    def __init__(self, **data):
        super().__init__(**data)
        self._load_from_config_file()
        self._load_from_environment()
    
    def _load_from_environment(self):
        """从环境变量加载配置"""
        # LLM 配置
        if os.getenv("API_DASHSCOPE_API_KEY"):
            self.llm.dashscope_api_key = os.getenv("API_DASHSCOPE_API_KEY")
        if os.getenv("DASHSCOPE_API_KEY"):
            self.llm.dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        if os.getenv("OPENAI_API_KEY"):
            self.llm.openai_api_key = os.getenv("OPENAI_API_KEY")
        if os.getenv("GEMINI_API_KEY"):
            self.llm.gemini_api_key = os.getenv("GEMINI_API_KEY")
        if os.getenv("SILICONFLOW_API_KEY"):
            self.llm.siliconflow_api_key = os.getenv("SILICONFLOW_API_KEY")
        if os.getenv("LLM_PROVIDER"):
            self.llm.provider = os.getenv("LLM_PROVIDER")
        
        # 模型配置
        if os.getenv("API_MODEL_NAME"):
            self.llm.model_name = os.getenv("API_MODEL_NAME")
        if os.getenv("API_MAX_TOKENS"):
            self.llm.max_tokens = int(os.getenv("API_MAX_TOKENS"))
        if os.getenv("API_TIMEOUT"):
            self.llm.timeout = int(os.getenv("API_TIMEOUT"))
        if os.getenv("TEMPERATURE"):
            self.llm.temperature = float(os.getenv("TEMPERATURE"))
        if os.getenv("TOP_P"):
            self.llm.top_p = float(os.getenv("TOP_P"))
        if os.getenv("PROXY_URL"):
            self.llm.proxy_url = os.getenv("PROXY_URL")
        
        # 数据库配置
        if os.getenv("DATABASE_URL"):
            self.database.url = os.getenv("DATABASE_URL")
        
        # Redis 配置
        if os.getenv("REDIS_URL"):
            self.redis.url = os.getenv("REDIS_URL")
        
        # 处理配置
        if os.getenv("PROCESSING_CHUNK_SIZE"):
            self.processing.chunk_size = int(os.getenv("PROCESSING_CHUNK_SIZE"))
        if os.getenv("PROCESSING_MIN_SCORE_THRESHOLD"):
            self.processing.min_score_threshold = float(os.getenv("PROCESSING_MIN_SCORE_THRESHOLD"))
        
        # 视频配置
        if os.getenv("VIDEO_USE_STREAM_COPY"):
            self.video.use_stream_copy = os.getenv("VIDEO_USE_STREAM_COPY").lower() == "true"
        if os.getenv("VIDEO_USE_HARDWARE_ACCEL"):
            self.video.use_hardware_accel = os.getenv("VIDEO_USE_HARDWARE_ACCEL").lower() == "true"
        if os.getenv("VIDEO_ENCODER_PRESET"):
            self.video.encoder_preset = os.getenv("VIDEO_ENCODER_PRESET")
        if os.getenv("VIDEO_CRF"):
            self.video.crf = int(os.getenv("VIDEO_CRF"))
        
        # 日志配置
        if os.getenv("LOG_LEVEL"):
            self.logging.level = os.getenv("LOG_LEVEL")
        if os.getenv("LOG_FILE"):
            self.logging.file = os.getenv("LOG_FILE")
    
    def _load_from_config_file(self):
        """从配置文件加载配置"""
        config_file = self.paths.data_dir / "settings.json"
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    
                    # 更新 LLM 配置
                    if "llm" in config_data:
                        llm_data = config_data["llm"]
                        if "provider" in llm_data:
                            self.llm.provider = llm_data["provider"]
                        if "model_name" in llm_data:
                            self.llm.model_name = llm_data["model_name"]
                        if "max_tokens" in llm_data:
                            self.llm.max_tokens = llm_data["max_tokens"]
                        if "temperature" in llm_data:
                            self.llm.temperature = llm_data["temperature"]
                        if "top_p" in llm_data:
                            self.llm.top_p = llm_data["top_p"]
                        if "timeout" in llm_data:
                            self.llm.timeout = llm_data["timeout"]
                        if "proxy_url" in llm_data:
                            self.llm.proxy_url = llm_data["proxy_url"]
                        
                        # API 密钥
                        if "provider_configs" in llm_data:
                            provider_configs = llm_data["provider_configs"]
                            if "dashscope" in provider_configs:
                                self.llm.dashscope_api_key = provider_configs["dashscope"].get("api_key", "")
                            if "openai" in provider_configs:
                                self.llm.openai_api_key = provider_configs["openai"].get("api_key", "")
                            if "gemini" in provider_configs:
                                self.llm.gemini_api_key = provider_configs["gemini"].get("api_key", "")
                            if "siliconflow" in provider_configs:
                                self.llm.siliconflow_api_key = provider_configs["siliconflow"].get("api_key", "")
                    
                    # 更新处理配置
                    if "processing" in config_data:
                        proc_data = config_data["processing"]
                        if "chunk_size" in proc_data:
                            self.processing.chunk_size = proc_data["chunk_size"]
                        if "min_score_threshold" in proc_data:
                            self.processing.min_score_threshold = proc_data["min_score_threshold"]
                    
                    logger.info(f"已加载配置文件: {config_file}")
            except Exception as e:
                logger.warning(f"加载配置文件失败: {e}")
    
    def save_to_file(self):
        """保存配置到文件"""
        config_file = self.paths.data_dir / "settings.json"
        config_file.parent.mkdir(exist_ok=True)
        
        try:
            config_data = {
                "environment": self.environment.value,
                "debug": self.debug,
                "llm": {
                    "provider": self.llm.provider.value,
                    "model_name": self.llm.model_name,
                    "max_tokens": self.llm.max_tokens,
                    "temperature": self.llm.temperature,
                    "top_p": self.llm.top_p,
                    "timeout": self.llm.timeout,
                    "proxy_url": self.llm.proxy_url,
                    "provider_configs": {
                        "dashscope": {
                            "api_key": self.llm.dashscope_api_key,
                            "base_url": self.llm.dashscope_base_url
                        },
                        "openai": {
                            "api_key": self.llm.openai_api_key,
                            "base_url": self.llm.openai_base_url
                        },
                        "gemini": {
                            "api_key": self.llm.gemini_api_key
                        },
                        "siliconflow": {
                            "api_key": self.llm.siliconflow_api_key,
                            "base_url": self.llm.siliconflow_base_url
                        }
                    }
                },
                "processing": {
                    "chunk_size": self.processing.chunk_size,
                    "min_score_threshold": self.processing.min_score_threshold,
                    "max_clips_per_collection": self.processing.max_clips_per_collection,
                    "max_retries": self.processing.max_retries,
                    "timeout_seconds": self.processing.timeout_seconds
                },
                "video": {
                    "use_stream_copy": self.video.use_stream_copy,
                    "use_hardware_accel": self.video.use_hardware_accel,
                    "encoder_preset": self.video.encoder_preset,
                    "crf": self.video.crf
                }
            }
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"配置已保存到: {config_file}")
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            raise
    
    def export_config(self) -> Dict[str, Any]:
        """导出配置（隐藏敏感信息）"""
        return {
            "environment": self.environment.value,
            "debug": self.debug,
            "database": {
                "url": self.database.url,
                "echo": self.database.echo,
                "pool_size": self.database.pool_size,
                "max_overflow": self.database.max_overflow
            },
            "redis": {
                "url": self.redis.url,
                "max_connections": self.redis.max_connections,
                "socket_timeout": self.redis.socket_timeout
            },
            "llm": {
                "provider": self.llm.provider.value,
                "model_name": self.llm.model_name,
                "max_tokens": self.llm.max_tokens,
                "temperature": self.llm.temperature,
                "top_p": self.llm.top_p,
                "timeout": self.llm.timeout,
                "proxy_url": self.llm.proxy_url,
                "api_key": "***REDACTED***" if self.llm.get_api_key() else ""
            },
            "processing": {
                "chunk_size": self.processing.chunk_size,
                "min_score_threshold": self.processing.min_score_threshold,
                "max_clips_per_collection": self.processing.max_clips_per_collection,
                "max_retries": self.processing.max_retries,
                "timeout_seconds": self.processing.timeout_seconds
            },
            "video": {
                "use_stream_copy": self.video.use_stream_copy,
                "use_hardware_accel": self.video.use_hardware_accel,
                "encoder_preset": self.video.encoder_preset,
                "crf": self.video.crf
            },
            "logging": {
                "level": self.logging.level,
                "file": self.logging.file,
                "json_logs": self.logging.json_logs
            }
        }


# 全局配置实例
_config: AppConfig = None


def get_config() -> AppConfig:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


def reload_config() -> AppConfig:
    """重新加载配置"""
    global _config
    _config = AppConfig()
    return _config
