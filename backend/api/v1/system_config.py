"""
系统配置 API 路由
支持前端界面配置所有系统级参数
"""
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
import json
from pathlib import Path

from core.system_config import (
    SystemConfigManager, 
    get_system_config_manager,
    ConfigCategory
)

router = APIRouter()


class ProcessingConfigUpdate(BaseModel):
    """处理参数配置更新请求"""
    chunk_size: Optional[int] = Field(None, ge=100, le=50000)
    min_score_threshold: Optional[float] = Field(None, ge=0, le=100)
    max_clips_per_collection: Optional[int] = Field(None, ge=1, le=20)
    max_retries: Optional[int] = Field(None, ge=0, le=10)
    api_timeout: Optional[int] = Field(None, ge=10, le=3600)


class VideoConfigUpdate(BaseModel):
    """视频处理配置更新请求"""
    use_stream_copy: Optional[bool] = None
    use_hardware_accel: Optional[bool] = None
    encoder_preset: Optional[str] = None
    crf: Optional[int] = Field(None, ge=0, le=51)


class TopicConfigUpdate(BaseModel):
    """话题提取配置更新请求"""
    min_topic_duration_minutes: Optional[int] = Field(None, ge=1, le=60)
    max_topic_duration_minutes: Optional[int] = Field(None, ge=1, le=120)
    target_topic_duration_minutes: Optional[int] = Field(None, ge=1, le=60)
    min_topics_per_chunk: Optional[int] = Field(None, ge=1, le=20)
    max_topics_per_chunk: Optional[int] = Field(None, ge=1, le=30)


class LoggingConfigUpdate(BaseModel):
    """日志配置更新请求"""
    log_level: Optional[str] = None
    log_format: Optional[str] = None


class AdvancedConfigUpdate(BaseModel):
    """高级配置更新请求"""
    proxy_url: Optional[str] = None
    encryption_key: Optional[str] = None
    bilibili_cookie: Optional[str] = None


class ConfigCategoryUpdate(BaseModel):
    """配置分类更新请求"""
    config: Dict[str, Any]


def get_config_manager():
    """获取配置管理器依赖"""
    return get_system_config_manager()


@router.get("/")
async def get_all_system_configs(
    manager: SystemConfigManager = Depends(get_config_manager)
):
    """获取所有系统配置"""
    try:
        configs = manager.get_all_configs()
        return {
            "processing": configs["processing"],
            "video": configs["video"],
            "topic": configs["topic"],
            "logging": configs["logging"],
            "advanced": configs["advanced"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取系统配置失败: {e}")


@router.get("/processing")
async def get_processing_config(
    manager: SystemConfigManager = Depends(get_config_manager)
):
    """获取处理参数配置"""
    try:
        config = manager.get_processing_config()
        return {
            "chunk_size": config.chunk_size,
            "min_score_threshold": config.min_score_threshold,
            "max_clips_per_collection": config.max_clips_per_collection,
            "max_retries": config.max_retries,
            "api_timeout": config.api_timeout,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取处理配置失败: {e}")


@router.put("/processing")
async def update_processing_config(
    request: ProcessingConfigUpdate,
    manager: SystemConfigManager = Depends(get_config_manager)
):
    """更新处理参数配置"""
    try:
        config_data = {}
        for field in ["chunk_size", "min_score_threshold", "max_clips_per_collection", "max_retries", "api_timeout"]:
            value = getattr(request, field)
            if value is not None:
                config_data[field] = value

        if config_data:
            manager.update_config("processing", config_data)

        return {"message": "处理配置已更新", "config": manager.get_all_configs()["processing"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新处理配置失败: {e}")


@router.get("/video")
async def get_video_config(
    manager: SystemConfigManager = Depends(get_config_manager)
):
    """获取视频处理配置"""
    try:
        config = manager.get_video_config()
        return {
            "use_stream_copy": config.use_stream_copy,
            "use_hardware_accel": config.use_hardware_accel,
            "encoder_preset": config.encoder_preset,
            "crf": config.crf,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取视频配置失败: {e}")


@router.put("/video")
async def update_video_config(
    request: VideoConfigUpdate,
    manager: SystemConfigManager = Depends(get_config_manager)
):
    """更新视频处理配置"""
    try:
        config_data = {}
        for field in ["use_stream_copy", "use_hardware_accel", "encoder_preset", "crf"]:
            value = getattr(request, field)
            if value is not None:
                config_data[field] = value

        if config_data:
            manager.update_config("video", config_data)

        return {"message": "视频配置已更新", "config": manager.get_all_configs()["video"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新视频配置失败: {e}")


@router.get("/topic")
async def get_topic_config(
    manager: SystemConfigManager = Depends(get_config_manager)
):
    """获取话题提取配置"""
    try:
        config = manager.get_topic_config()
        return {
            "min_topic_duration_minutes": config.min_topic_duration_minutes,
            "max_topic_duration_minutes": config.max_topic_duration_minutes,
            "target_topic_duration_minutes": config.target_topic_duration_minutes,
            "min_topics_per_chunk": config.min_topics_per_chunk,
            "max_topics_per_chunk": config.max_topics_per_chunk,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取话题配置失败: {e}")


@router.put("/topic")
async def update_topic_config(
    request: TopicConfigUpdate,
    manager: SystemConfigManager = Depends(get_config_manager)
):
    """更新话题提取配置"""
    try:
        config_data = {}
        for field in [
            "min_topic_duration_minutes", "max_topic_duration_minutes",
            "target_topic_duration_minutes", "min_topics_per_chunk", "max_topics_per_chunk"
        ]:
            value = getattr(request, field)
            if value is not None:
                config_data[field] = value

        if config_data:
            manager.update_config("topic", config_data)

        return {"message": "话题配置已更新", "config": manager.get_all_configs()["topic"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新话题配置失败: {e}")


@router.get("/logging")
async def get_logging_config(
    manager: SystemConfigManager = Depends(get_config_manager)
):
    """获取日志配置"""
    try:
        config = manager.get_logging_config()
        return {
            "log_level": config.log_level,
            "log_format": config.log_format,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取日志配置失败: {e}")


@router.put("/logging")
async def update_logging_config(
    request: LoggingConfigUpdate,
    manager: SystemConfigManager = Depends(get_config_manager)
):
    """更新日志配置"""
    try:
        config_data = {}
        for field in ["log_level", "log_format"]:
            value = getattr(request, field)
            if value is not None:
                config_data[field] = value

        if config_data:
            manager.update_config("logging", config_data)

        return {"message": "日志配置已更新", "config": manager.get_all_configs()["logging"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新日志配置失败: {e}")


@router.get("/advanced")
async def get_advanced_config(
    manager: SystemConfigManager = Depends(get_config_manager)
):
    """获取高级配置"""
    try:
        config = manager.get_advanced_config()
        return {
            "proxy_url": config.proxy_url,
            "encryption_key": config.encryption_key,
            "bilibili_cookie": config.bilibili_cookie,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取高级配置失败: {e}")


@router.put("/advanced")
async def update_advanced_config(
    request: AdvancedConfigUpdate,
    manager: SystemConfigManager = Depends(get_config_manager)
):
    """更新高级配置"""
    try:
        config_data = {}
        for field in ["proxy_url", "encryption_key", "bilibili_cookie"]:
            value = getattr(request, field)
            if value is not None:
                config_data[field] = value

        if config_data:
            manager.update_config("advanced", config_data)

        return {"message": "高级配置已更新", "config": manager.get_all_configs()["advanced"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新高级配置失败: {e}")


@router.post("/reset-all")
async def reset_all_system_configs(
    manager: SystemConfigManager = Depends(get_config_manager)
):
    """重置所有系统配置为默认值"""
    try:
        manager.reset_all_configs()
        return {"message": "所有系统配置已重置为默认值", "config": manager.get_all_configs()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置系统配置失败: {e}")


@router.post("/reset/{category}")
async def reset_category_config(
    category: str,
    manager: SystemConfigManager = Depends(get_config_manager)
):
    """重置指定分类的配置为默认值"""
    try:
        valid_categories = ["processing", "video", "topic", "logging", "advanced"]
        if category not in valid_categories:
            raise HTTPException(status_code=400, detail=f"无效的配置分类: {category}")

        manager.reset_category_config(category)
        return {
            "message": f"{category} 配置已重置为默认值",
            "config": manager.get_all_configs()[category]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置配置失败: {e}")


@router.get("/config-info")
async def get_config_info():
    """获取配置说明信息"""
    return {
        "categories": {
            "processing": {
                "name": "处理参数",
                "description": "控制视频处理流程的核心参数",
                "fields": {
                    "chunk_size": "文本分块大小（字符数）",
                    "min_score_threshold": "最小评分阈值（100分制）",
                    "max_clips_per_collection": "每个合集最大切片数",
                    "max_retries": "最大重试次数",
                    "api_timeout": "API超时时间（秒）",
                }
            },
            "video": {
                "name": "视频处理",
                "description": "视频编码和处理相关配置",
                "fields": {
                    "use_stream_copy": "使用流复制（速度最快）",
                    "use_hardware_accel": "使用硬件加速",
                    "encoder_preset": "编码预设（p1-p7）",
                    "crf": "视频质量（18-28，越小越好）",
                }
            },
            "topic": {
                "name": "话题提取",
                "description": "话题检测和提取的控制参数",
                "fields": {
                    "min_topic_duration_minutes": "话题最小时长（分钟）",
                    "max_topic_duration_minutes": "话题最大时长（分钟）",
                    "target_topic_duration_minutes": "话题目标时长（分钟）",
                    "min_topics_per_chunk": "每个文本块最少话题数",
                    "max_topics_per_chunk": "每个文本块最多话题数",
                }
            },
            "logging": {
                "name": "日志配置",
                "description": "日志输出的级别和格式",
                "fields": {
                    "log_level": "日志级别（DEBUG/INFO/WARNING/ERROR）",
                    "log_format": "日志格式",
                }
            },
            "advanced": {
                "name": "高级配置",
                "description": "代理、加密密钥等高级设置",
                "fields": {
                    "proxy_url": "代理服务器URL",
                    "encryption_key": "加密密钥",
                    "bilibili_cookie": "B站Cookie（用于语音识别）",
                }
            }
        }
    }
