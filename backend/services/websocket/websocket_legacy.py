"""
WebSocket服务遗留兼容层
保持与原有代码的向后兼容性
"""

from typing import Optional
from .websocket_service import UnifiedWebSocketService

unified_websocket_service = UnifiedWebSocketService()


def get_ws_service() -> UnifiedWebSocketService:
    """
    获取统一WebSocket服务单例
    
    Returns:
        UnifiedWebSocketService 实例
    """
    return unified_websocket_service


async def send_task_update(task_id: str, status: str, progress: Optional[int] = None,
                           message: Optional[str] = None, error: Optional[str] = None):
    return await unified_websocket_service.send_task_update(task_id, status, progress, message, error)


async def send_project_update(project_id: str, status: str, progress: Optional[int] = None,
                              message: Optional[str] = None):
    return await unified_websocket_service.send_project_update(project_id, status, progress, message)


async def send_processing_progress(project_id: str, task_id: str, progress: int, message: str,
                                   current_step: int = 0, total_steps: int = 6, step_name: str = "",
                                   estimated_remaining: Optional[int] = None):
    return await unified_websocket_service.send_processing_progress(
        project_id, task_id, progress, message, current_step, total_steps, step_name, estimated_remaining
    )
