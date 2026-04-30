"""
统一配置管理系统（向后兼容层）
整合所有配置源，提供统一的配置访问接口
配置优先级：环境变量 > 配置文件 > 默认值

注意：此文件保留用于向后兼容，新代码应直接从 config 模块导入
"""

from typing import Dict, Any, Optional
from pathlib import Path
from functools import lru_cache

from config import (
    AppConfig,
    DatabaseConfig,
    RedisConfig,
    CeleryConfig,
    LLMConfig,
    ProcessingConfig,
    VideoConfig,
    LoggingConfig,
    PathConfig,
    get_config,
    reload_config
)

# 导出所有配置类和枚举，保持向后兼容
__all__ = [
    'AppConfig',
    'DatabaseConfig',
    'RedisConfig',
    'CeleryConfig',
    'LLMConfig',
    'ProcessingConfig',
    'VideoConfig',
    'LoggingConfig',
    'PathConfig',
    'get_config',
    'reload_config',
    'get_default_prompt_files',
    'get_processing_config',
    'get_prompt_files',
    'get_redis_url',
    'get_database_url',
    'get_project_root',
    'get_data_directory',
    'get_logging_config'
]


@lru_cache(maxsize=1)
def get_default_prompt_files() -> Dict[str, str]:
    """获取默认提示词文件路径"""
    config = get_config()
    return {
        "outline": str(config.paths.prompt_dir / "大纲.txt"),
        "topic_extraction": str(config.paths.prompt_dir / "大纲.txt"),
        "timeline": str(config.paths.prompt_dir / "时间点.txt"),
        "recommendation": str(config.paths.prompt_dir / "推荐理由.txt"),
        "clip_selection": str(config.paths.prompt_dir / "推荐理由.txt"),
        "scoring": str(config.paths.prompt_dir / "评分.txt"),
        "title": str(config.paths.prompt_dir / "标题生成.txt"),
        "collection_title": str(config.paths.prompt_dir / "标题生成.txt"),
        "clip_title": str(config.paths.prompt_dir / "标题生成.txt")
    }


def get_processing_config() -> ProcessingConfig:
    """获取处理配置（向后兼容）"""
    config = get_config()
    return config.processing


def get_prompt_files() -> Dict[str, str]:
    """获取提示词文件路径（向后兼容）"""
    return get_default_prompt_files()


def get_redis_url() -> str:
    """获取Redis URL（向后兼容）"""
    config = get_config()
    return config.redis.url


def get_database_url() -> str:
    """获取数据库URL（向后兼容）"""
    config = get_config()
    return config.database.url


def get_project_root() -> Path:
    """获取项目根目录（向后兼容）"""
    config = get_config()
    return config.paths.project_root


def get_data_directory() -> Path:
    """获取数据目录（向后兼容）"""
    config = get_config()
    return config.paths.data_dir


def get_logging_config() -> LoggingConfig:
    """获取日志配置（向后兼容）"""
    config = get_config()
    return config.logging
