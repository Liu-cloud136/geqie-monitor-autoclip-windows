"""
事件总线
用于服务间解耦通信的事件驱动架构
"""

import logging
import asyncio
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import defaultdict
import inspect
from core.logging_config import get_logger

logger = get_logger(__name__)


class EventType(Enum):
    PROGRESS_STARTED = "progress_started"
    PROGRESS_UPDATED = "progress_updated"
    PROGRESS_COMPLETED = "progress_completed"
    PROGRESS_FAILED = "progress_failed"
    
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    
    PROJECT_CREATED = "project_created"
    PROJECT_UPDATED = "project_updated"
    PROJECT_PROCESSING_STARTED = "project_processing_started"
    PROJECT_PROCESSING_COMPLETED = "project_processing_completed"
    PROJECT_PROCESSING_FAILED = "project_processing_failed"
    
    WEBSOCKET_MESSAGE = "websocket_message"
    WEBSOCKET_BROADCAST = "websocket_broadcast"
    
    PROCESSING_STEP_STARTED = "processing_step_started"
    PROCESSING_STEP_COMPLETED = "processing_step_completed"
    PROCESSING_STEP_FAILED = "processing_step_failed"
    
    SYSTEM_NOTIFICATION = "system_notification"
    ERROR_NOTIFICATION = "error_notification"


@dataclass
class Event:
    event_type: EventType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: Optional[str] = None
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "correlation_id": self.correlation_id
        }


EventHandler = Callable[[Event], None]
AsyncEventHandler = Callable[[Event], Any]


class EventBus:
    """事件总线实现"""
    
    def __init__(self):
        self._sync_handlers: Dict[EventType, List[EventHandler]] = defaultdict(list)
        self._async_handlers: Dict[EventType, List[AsyncEventHandler]] = defaultdict(list)
        self._global_handlers: List[EventHandler] = []
        self._global_async_handlers: List[AsyncEventHandler] = []
        self._event_history: List[Event] = []
        self._max_history_size = 1000
        self._lock = asyncio.Lock()
    
    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """订阅同步事件处理器"""
        self._sync_handlers[event_type].append(handler)
        logger.debug(f"订阅事件: {event_type.value} -> {handler.__name__}")
    
    def subscribe_async(self, event_type: EventType, handler: AsyncEventHandler) -> None:
        """订阅异步事件处理器"""
        self._async_handlers[event_type].append(handler)
        logger.debug(f"订阅异步事件: {event_type.value} -> {handler.__name__}")
    
    def subscribe_all(self, handler: EventHandler) -> None:
        """订阅所有事件（同步）"""
        self._global_handlers.append(handler)
        logger.debug(f"订阅所有事件: {handler.__name__}")
    
    def subscribe_all_async(self, handler: AsyncEventHandler) -> None:
        """订阅所有事件（异步）"""
        self._global_async_handlers.append(handler)
        logger.debug(f"订阅所有异步事件: {handler.__name__}")
    
    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> bool:
        """取消订阅"""
        if handler in self._sync_handlers[event_type]:
            self._sync_handlers[event_type].remove(handler)
            return True
        if handler in self._async_handlers[event_type]:
            self._async_handlers[event_type].remove(handler)
            return True
        return False
    
    def publish(self, event: Event) -> None:
        """发布事件（同步）"""
        self._event_history.append(event)
        if len(self._event_history) > self._max_history_size:
            self._event_history = self._event_history[-self._max_history_size:]
        
        for handler in self._sync_handlers[event.event_type]:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"事件处理器执行失败: {handler.__name__}, 错误: {e}")
        
        for handler in self._global_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"全局事件处理器执行失败: {handler.__name__}, 错误: {e}")
        
        logger.debug(f"事件已发布: {event.event_type.value}")
    
    async def publish_async(self, event: Event) -> None:
        """发布事件（异步）"""
        async with self._lock:
            self._event_history.append(event)
            if len(self._event_history) > self._max_history_size:
                self._event_history = self._event_history[-self._max_history_size:]
        
        tasks = []
        
        for handler in self._async_handlers[event.event_type]:
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    tasks.append(self._safe_execute_async(handler, event))
            except Exception as e:
                logger.error(f"异步事件处理器执行失败: {handler.__name__}, 错误: {e}")
        
        for handler in self._sync_handlers[event.event_type]:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"事件处理器执行失败: {handler.__name__}, 错误: {e}")
        
        for handler in self._global_async_handlers:
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    tasks.append(self._safe_execute_async(handler, event))
            except Exception as e:
                logger.error(f"全局异步事件处理器执行失败: {handler.__name__}, 错误: {e}")
        
        for handler in self._global_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"全局事件处理器执行失败: {handler.__name__}, 错误: {e}")
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.debug(f"异步事件已发布: {event.event_type.value}")
    
    async def _safe_execute_async(self, handler: AsyncEventHandler, event: Event) -> None:
        """安全执行异步处理器"""
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"异步事件处理器执行失败: {handler.__name__}, 错误: {e}")
    
    def get_history(self, event_type: Optional[EventType] = None, 
                   limit: int = 100) -> List[Event]:
        """获取事件历史"""
        if event_type:
            return [e for e in self._event_history if e.event_type == event_type][-limit:]
        return self._event_history[-limit:]
    
    def clear_history(self) -> None:
        """清除事件历史"""
        self._event_history.clear()


event_bus = EventBus()


def get_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    return event_bus


def on_event(event_type: EventType):
    """事件处理器装饰器"""
    def decorator(func):
        if inspect.iscoroutinefunction(func):
            event_bus.subscribe_async(event_type, func)
        else:
            event_bus.subscribe(event_type, func)
        return func
    return decorator


def create_event(event_type: EventType, data: Dict[str, Any], 
                source: Optional[str] = None, 
                correlation_id: Optional[str] = None) -> Event:
    """创建事件的便捷函数"""
    return Event(
        event_type=event_type,
        data=data,
        source=source,
        correlation_id=correlation_id
    )
