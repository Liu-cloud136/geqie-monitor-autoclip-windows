"""
Business logic services layer.
Separates business logic from API controllers and data access.
"""
from .base import BaseService
from .exceptions import ServiceError

# 统一服务
from .unified_progress_service import (
    UnifiedProgressService,
    ProgressStage,
    ProgressStatus,
    ProgressInfo,
    unified_progress_service,
    start_progress,
    update_progress,
    complete_progress,
    fail_progress,
    get_progress
)

from .unified_processing_service import (
    UnifiedProcessingService,
    create_unified_processing_service
)

from .unified_storage_service import (
    UnifiedStorageService,
    create_unified_storage_service
)

from .unified_websocket_service import (
    UnifiedWebSocketService,
    unified_websocket_service,
    send_task_update,
    send_project_update,
    send_processing_progress
)

__all__ = [
    # 基础服务
    "BaseService",
    "ServiceError",
    
    # 统一进度服务
    "UnifiedProgressService",
    "ProgressStage",
    "ProgressStatus",
    "ProgressInfo",
    "unified_progress_service",
    "start_progress",
    "update_progress",
    "complete_progress",
    "fail_progress",
    "get_progress",
    
    # 统一处理服务
    "UnifiedProcessingService",
    "create_unified_processing_service",
    
    # 统一存储服务
    "UnifiedStorageService",
    "create_unified_storage_service",
    
    # 统一WebSocket服务
    "UnifiedWebSocketService",
    "unified_websocket_service",
    "send_task_update",
    "send_project_update",
    "send_processing_progress"
]