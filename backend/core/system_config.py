"""
系统配置管理器
管理所有可通过前端界面配置的系统级参数
"""
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ConfigCategory(str, Enum):
    """配置分类枚举"""
    PROCESSING = "processing"
    VIDEO = "video"
    TOPIC = "topic"
    LOGGING = "logging"
    ADVANCED = "advanced"


@dataclass
class ProcessingConfig:
    """处理参数配置"""
    chunk_size: int = 5000
    min_score_threshold: float = 70.0
    max_clips_per_collection: int = 5
    max_retries: int = 3
    api_timeout: int = 600


@dataclass
class VideoConfig:
    """视频处理配置"""
    use_stream_copy: bool = True
    use_hardware_accel: bool = True
    encoder_preset: str = "p6"
    crf: int = 23


@dataclass
class TopicConfig:
    """话题提取配置"""
    min_topic_duration_minutes: int = 2
    max_topic_duration_minutes: int = 12
    target_topic_duration_minutes: int = 5
    min_topics_per_chunk: int = 3
    max_topics_per_chunk: int = 8


@dataclass
class LoggingConfig:
    """日志配置"""
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class AdvancedConfig:
    """高级配置"""
    proxy_url: str = ""
    encryption_key: str = ""
    bilibili_cookie: str = ""


@dataclass
class SystemConfig:
    """系统配置容器"""
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    topic: TopicConfig = field(default_factory=TopicConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    advanced: AdvancedConfig = field(default_factory=AdvancedConfig)


class SystemConfigManager:
    """系统配置管理器"""

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or self._get_default_config_file()
        self.config: SystemConfig = SystemConfig()
        self._load_configs()

    def _get_default_config_file(self) -> Path:
        """获取默认配置文件路径"""
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent
        return project_root / "data" / "system_config.json"

    def _load_configs(self):
        """加载配置"""
        default_config = SystemConfig()

        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved_configs = json.load(f)

                for key, value in saved_configs.items():
                    if hasattr(default_config, key) and isinstance(value, dict):
                        config_obj = getattr(default_config, key)
                        for sub_key, sub_value in value.items():
                            if hasattr(config_obj, sub_key):
                                setattr(config_obj, sub_key, sub_value)

                self.config = default_config
                logger.info(f"已加载系统配置文件: {self.config_file}")
            except Exception as e:
                logger.warning(f"加载系统配置失败，使用默认配置: {e}")
                self.config = default_config
        else:
            self.config = default_config
            logger.info(f"使用默认系统配置，配置文件不存在: {self.config_file}")

    def save_configs(self):
        """保存配置"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        config_data = {
            "processing": asdict(self.config.processing),
            "video": asdict(self.config.video),
            "topic": asdict(self.config.topic),
            "logging": asdict(self.config.logging),
            "advanced": asdict(self.config.advanced),
        }

        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            logger.info(f"系统配置已保存: {self.config_file}")
        except Exception as e:
            logger.error(f"保存系统配置失败: {e}")
            raise

    def get_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """获取所有配置"""
        return {
            "processing": asdict(self.config.processing),
            "video": asdict(self.config.video),
            "topic": asdict(self.config.topic),
            "logging": asdict(self.config.logging),
            "advanced": asdict(self.config.advanced),
        }

    def update_config(self, category: str, config_data: Dict[str, Any]):
        """更新指定分类的配置"""
        if not hasattr(self.config, category):
            raise ValueError(f"不支持的配置分类: {category}")

        config_obj = getattr(self.config, category)
        for key, value in config_data.items():
            if hasattr(config_obj, key):
                setattr(config_obj, key, value)

        self.save_configs()

    def get_processing_config(self) -> ProcessingConfig:
        """获取处理配置"""
        return self.config.processing

    def get_video_config(self) -> VideoConfig:
        """获取视频配置"""
        return self.config.video

    def get_topic_config(self) -> TopicConfig:
        """获取话题配置"""
        return self.config.topic

    def get_logging_config(self) -> LoggingConfig:
        """获取日志配置"""
        return self.config.logging

    def get_advanced_config(self) -> AdvancedConfig:
        """获取高级配置"""
        return self.config.advanced

    def reset_all_configs(self):
        """重置所有配置为默认值"""
        self.config = SystemConfig()
        self.save_configs()

    def reset_category_config(self, category: str):
        """重置指定分类的配置为默认值"""
        if category == "processing":
            self.config.processing = ProcessingConfig()
        elif category == "video":
            self.config.video = VideoConfig()
        elif category == "topic":
            self.config.topic = TopicConfig()
        elif category == "logging":
            self.config.logging = LoggingConfig()
        elif category == "advanced":
            self.config.advanced = AdvancedConfig()
        else:
            raise ValueError(f"不支持的配置分类: {category}")

        self.save_configs()


_system_config_manager: Optional[SystemConfigManager] = None


def get_system_config_manager() -> SystemConfigManager:
    """获取全局系统配置管理器实例"""
    global _system_config_manager
    if _system_config_manager is None:
        _system_config_manager = SystemConfigManager()
    return _system_config_manager


def reload_system_configs():
    """重新加载系统配置"""
    global _system_config_manager
    if _system_config_manager is not None:
        _system_config_manager._load_configs()
        logger.info("系统配置已重新加载")


def get_processing_config_dict() -> Dict[str, Any]:
    """获取处理配置字典（用于向后兼容）"""
    manager = get_system_config_manager()
    config = manager.get_processing_config()
    return {
        "chunk_size": config.chunk_size,
        "min_score_threshold": config.min_score_threshold,
        "max_clips_per_collection": config.max_clips_per_collection,
        "max_retries": config.max_retries,
    }


def get_video_config_dict() -> Dict[str, Any]:
    """获取视频配置字典"""
    manager = get_system_config_manager()
    config = manager.get_video_config()
    return {
        "use_stream_copy": config.use_stream_copy,
        "use_hardware_accel": config.use_hardware_accel,
        "encoder_preset": config.encoder_preset,
        "crf": config.crf,
    }


def get_topic_config_dict() -> Dict[str, Any]:
    """获取话题配置字典"""
    manager = get_system_config_manager()
    config = manager.get_topic_config()
    return {
        "min_topic_duration_minutes": config.min_topic_duration_minutes,
        "max_topic_duration_minutes": config.max_topic_duration_minutes,
        "target_topic_duration_minutes": config.target_topic_duration_minutes,
        "min_topics_per_chunk": config.min_topics_per_chunk,
        "max_topics_per_chunk": config.max_topics_per_chunk,
    }
