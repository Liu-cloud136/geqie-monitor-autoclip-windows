"""
统一进度服务 - 主服务类
使用事件驱动架构解耦服务间通信
"""

import asyncio
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from core.event_bus import EventBus, EventType, Event, get_event_bus
from core.logging_config import get_logger
from .progress_models import ProgressInfo, ProgressStage, ProgressStatus
from .progress_repository import ProgressRepository

logger = get_logger(__name__)


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
