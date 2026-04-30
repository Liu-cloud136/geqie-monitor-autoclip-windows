"""
统一进度服务
整合所有进度相关功能，提供统一的进度管理接口
使用事件驱动架构解耦服务间通信
"""

import time
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from functools import wraps
import redis.asyncio as redis
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.event_bus import EventBus, EventType, Event, get_event_bus
from models.project import Project, ProjectStatus
from models.task import Task, TaskStatus
from services.exceptions import ServiceError, ProcessingError, TaskError, ErrorCode
from core.logging_config import get_logger

logger = get_logger(__name__)


class ProgressStage(Enum):
    INGEST = "INGEST"
    SUBTITLE = "SUBTITLE"
    ANALYZE = "ANALYZE"
    HIGHLIGHT = "HIGHLIGHT"
    EXPORT = "EXPORT"
    DONE = "DONE"
    ERROR = "ERROR"


class ProgressStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class ProgressInfo:
    project_id: str
    task_id: Optional[str] = None
    stage: ProgressStage = ProgressStage.INGEST
    status: ProgressStatus = ProgressStatus.PENDING
    progress: int = 0
    message: str = ""
    error_message: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    estimated_remaining: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['stage'] = self.stage.value
        data['status'] = self.status.value
        if self.start_time:
            data['start_time'] = self.start_time.isoformat()
        if self.end_time:
            data['end_time'] = self.end_time.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProgressInfo':
        if 'stage' in data and isinstance(data['stage'], str):
            data['stage'] = ProgressStage(data['stage'])
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = ProgressStatus(data['status'])
        if 'start_time' in data and isinstance(data['start_time'], str):
            data['start_time'] = datetime.fromisoformat(data['start_time'])
        if 'end_time' in data and isinstance(data['end_time'], str):
            data['end_time'] = datetime.fromisoformat(data['end_time'])
        return cls(**data)


class ProgressRepository:
    """进度数据存储抽象"""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_client: Optional[redis.Redis] = None
        self._redis_initialized = False
        self._redis_url = redis_url or "redis://127.0.0.1:6379/0"
        self._redis_lock = asyncio.Lock()
    
    async def init_redis(self):
        if self._redis_initialized:
            return
        try:
            self.redis_client = redis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            await self.redis_client.ping()
            self._redis_initialized = True
            logger.info("ProgressRepository Redis连接成功")
        except Exception as e:
            logger.warning(f"ProgressRepository Redis连接失败: {e}")
    
    async def save(self, project_id: str, progress_info: ProgressInfo) -> bool:
        if not self.redis_client:
            return False
        try:
            async with self._redis_lock:
                await self.redis_client.setex(
                    f"progress:{project_id}",
                    3600,
                    json.dumps(progress_info.to_dict())
                )
            return True
        except Exception as e:
            logger.warning(f"保存进度到Redis失败: {e}")
            return False
    
    async def load(self, project_id: str) -> Optional[ProgressInfo]:
        if not self.redis_client:
            return None
        try:
            async with self._redis_lock:
                data = await self.redis_client.get(f"progress:{project_id}")
            if data:
                return ProgressInfo.from_dict(json.loads(data))
        except Exception as e:
            logger.warning(f"从Redis加载进度失败: {e}")
        return None
    
    async def delete(self, project_id: str) -> bool:
        if not self.redis_client:
            return False
        try:
            async with self._redis_lock:
                await self.redis_client.delete(f"progress:{project_id}")
            return True
        except Exception as e:
            logger.warning(f"删除Redis进度失败: {e}")
            return False


class UnifiedProgressService:
    """统一进度服务 - 使用事件驱动架构"""
    
    STAGE_WEIGHTS = {
        ProgressStage.INGEST: 0,
        ProgressStage.SUBTITLE: 1,
        ProgressStage.ANALYZE: 2,
        ProgressStage.HIGHLIGHT: 3,
        ProgressStage.EXPORT: 4,
        ProgressStage.DONE: 5,
        ProgressStage.ERROR: -1,
    }
    
    def __init__(self, event_bus=None, repository=None):
        self._event_bus = event_bus
        self._repository = repository or ProgressRepository()
        self._cache: Dict[str, ProgressInfo] = {}
        self._callbacks: list = []
    
    def set_event_bus(self, event_bus):
        self._event_bus = event_bus
    
    async def start(self, project_id: str, task_id: Optional[str] = None,
                    initial_message: str = "开始处理") -> ProgressInfo:
        await self._repository.init_redis()
        
        progress_info = ProgressInfo(
            project_id=project_id,
            task_id=task_id,
            status=ProgressStatus.RUNNING,
            message=initial_message,
            start_time=datetime.utcnow()
        )
        
        self._cache[project_id] = progress_info
        await self._repository.save(project_id, progress_info)
        
        self._emit_event('progress_started', progress_info)
        return progress_info
    
    async def update(self, project_id: str, stage: ProgressStage,
                     message: str = "", sub_progress: float = 0.0,
                     metadata: Optional[Dict[str, Any]] = None) -> ProgressInfo:
        progress_info = self._cache.get(project_id)
        if not progress_info:
            progress_info = await self._repository.load(project_id)
        
        if not progress_info:
            raise ValueError(f"Progress not found for project: {project_id}")
        
        progress_info.stage = stage
        progress_info.message = message
        progress_info.progress = self._calculate_progress(stage, sub_progress)
        if metadata:
            progress_info.metadata = {**(progress_info.metadata or {}), **metadata}
        
        self._cache[project_id] = progress_info
        await self._repository.save(project_id, progress_info)
        
        self._emit_event('progress_updated', progress_info)
        return progress_info
    
    async def complete(self, project_id: str, message: str = "处理完成") -> ProgressInfo:
        progress_info = self._cache.get(project_id)
        if not progress_info:
            progress_info = await self._repository.load(project_id)
        
        if not progress_info:
            raise ValueError(f"Progress not found for project: {project_id}")
        
        progress_info.status = ProgressStatus.COMPLETED
        progress_info.message = message
        progress_info.progress = 100
        progress_info.end_time = datetime.utcnow()
        
        self._cache[project_id] = progress_info
        await self._repository.save(project_id, progress_info)
        
        self._emit_event('progress_completed', progress_info)
        return progress_info
    
    async def fail(self, project_id: str, error_message: str) -> ProgressInfo:
        progress_info = self._cache.get(project_id)
        if not progress_info:
            progress_info = await self._repository.load(project_id)
        
        if not progress_info:
            raise ValueError(f"Progress not found for project: {project_id}")
        
        progress_info.status = ProgressStatus.FAILED
        progress_info.error_message = error_message
        progress_info.end_time = datetime.utcnow()
        
        self._cache[project_id] = progress_info
        await self._repository.save(project_id, progress_info)
        
        self._emit_event('progress_failed', progress_info)
        return progress_info
    
    async def get(self, project_id: str) -> Optional[ProgressInfo]:
        if project_id in self._cache:
            return self._cache[project_id]
        return await self._repository.load(project_id)
    
    def _calculate_progress(self, stage: ProgressStage, sub_progress: float) -> int:
        stage_weight = self.STAGE_WEIGHTS.get(stage, 0)
        if stage == ProgressStage.DONE:
            return 100
        if stage == ProgressStage.ERROR:
            return 0
        base = (stage_weight / 5) * 100
        return min(99, int(base + sub_progress * 20))
    
    def _emit_event(self, event_type: str, progress_info: ProgressInfo):
        if self._event_bus:
            from core.event_types import ProgressEvent
            self._event_bus.emit(ProgressEvent(
                type=event_type,
                data=progress_info.to_dict()
            ))
        
        for callback in self._callbacks:
            try:
                callback(progress_info)
            except Exception as e:
                logger.error(f"进度回调执行失败: {e}")
    
    def add_callback(self, callback):
        self._callbacks.append(callback)
    
    def remove_callback(self, callback):
        if callback in self._callbacks:
            self._callbacks.remove(callback)


class _LegacyProgressService:
    """兼容旧接口的包装器"""
    
    def __init__(self):
        self._service = UnifiedProgressService()
        self._initialized = False
    
    async def _ensure_init(self):
        if not self._initialized:
            await self._service._repository.init_redis()
            self._initialized = True
    
    async def start_progress(self, project_id: str, task_id: Optional[str] = None,
                             initial_message: str = "开始处理") -> ProgressInfo:
        await self._ensure_init()
        return await self._service.start(project_id, task_id, initial_message)
    
    async def update_progress(self, project_id: str, stage: ProgressStage,
                              message: str = "", sub_progress: float = 0.0,
                              metadata: Optional[Dict[str, Any]] = None) -> ProgressInfo:
        await self._ensure_init()
        return await self._service.update(project_id, stage, message, sub_progress, metadata)
    
    async def complete_progress(self, project_id: str, message: str = "处理完成") -> ProgressInfo:
        await self._ensure_init()
        progress_info = self._service._cache.get(project_id)
        if progress_info:
            progress_info.status = ProgressStatus.COMPLETED
            progress_info.message = message
            progress_info.end_time = datetime.utcnow()
            await self._service._repository.save(project_id, progress_info)
            self._service._emit_event('progress_completed', progress_info)
        return progress_info
    
    async def fail_progress(self, project_id: str, error_message: str) -> ProgressInfo:
        await self._ensure_init()
        progress_info = self._service._cache.get(project_id)
        if progress_info:
            progress_info.status = ProgressStatus.FAILED
            progress_info.error_message = error_message
            progress_info.end_time = datetime.utcnow()
            await self._service._repository.save(project_id, progress_info)
            self._service._emit_event('progress_failed', progress_info)
        return progress_info
    
    async def get_progress(self, project_id: str) -> Optional[ProgressInfo]:
        await self._ensure_init()
        return await self._service.get(project_id)
    
    def add_progress_callback(self, callback):
        self._service.add_callback(callback)
    
    def remove_progress_callback(self, callback):
        self._service.remove_callback(callback)


unified_progress_service = _LegacyProgressService()


async def start_progress(project_id: str, task_id: Optional[str] = None,
                         initial_message: str = "开始处理") -> ProgressInfo:
    return await unified_progress_service.start_progress(project_id, task_id, initial_message)


async def update_progress(project_id: str, stage: ProgressStage,
                          message: str = "", sub_progress: float = 0.0,
                          metadata: Optional[Dict[str, Any]] = None) -> ProgressInfo:
    return await unified_progress_service.update_progress(project_id, stage, message, sub_progress, metadata)


async def complete_progress(project_id: str, message: str = "处理完成") -> ProgressInfo:
    return await unified_progress_service.complete_progress(project_id, message)


async def fail_progress(project_id: str, error_message: str) -> ProgressInfo:
    return await unified_progress_service.fail_progress(project_id, error_message)


async def get_progress(project_id: str) -> Optional[ProgressInfo]:
    return await unified_progress_service.get_progress(project_id)