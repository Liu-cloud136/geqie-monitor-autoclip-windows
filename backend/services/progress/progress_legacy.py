"""
进度服务遗留兼容层
保持与原有代码的向后兼容性
"""

from typing import Optional
from datetime import datetime
from .progress_models import ProgressInfo, ProgressStage, ProgressStatus
from .progress_service import UnifiedProgressService


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
                              metadata: Optional[dict] = None) -> ProgressInfo:
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
                          metadata: Optional[dict] = None) -> ProgressInfo:
    return await unified_progress_service.update_progress(project_id, stage, message, sub_progress, metadata)


async def complete_progress(project_id: str, message: str = "处理完成") -> ProgressInfo:
    return await unified_progress_service.complete_progress(project_id, message)


async def fail_progress(project_id: str, error_message: str) -> ProgressInfo:
    return await unified_progress_service.fail_progress(project_id, error_message)


async def get_progress(project_id: str) -> Optional[ProgressInfo]:
    return await unified_progress_service.get_progress(project_id)
