"""
消息广播器
负责将消息广播到WebSocket连接和事件总线
"""

import asyncio
import time
from typing import Dict, Any, Optional
from datetime import datetime
from core.websocket_manager import manager
from core.event_bus import EventBus, EventType, Event
from core.logging_config import get_logger

logger = get_logger(__name__)


class MessageBroadcaster:
    """消息广播器"""
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        self._event_bus = event_bus
        self._throttle_cache: Dict[str, Dict[str, Any]] = {}
        self.throttle_interval = 0.2
    
    def set_event_bus(self, event_bus: EventBus):
        self._event_bus = event_bus
    
    async def broadcast(self, message: Dict[str, Any], topic: Optional[str] = None):
        await manager.broadcast(message)
        
        if topic:
            await manager.broadcast_to_topic(message, topic)
        
        if self._event_bus:
            event = Event(
                event_type=EventType.WEBSOCKET_BROADCAST,
                data={"message": message, "topic": topic}
            )
            await self._event_bus.publish_async(event)
    
    async def send_to_user(self, user_id: str, message: Dict[str, Any]):
        await manager.send_personal_message(message, user_id)
    
    def _should_throttle(self, key: str) -> bool:
        now = time.time()
        if key in self._throttle_cache:
            if now - self._throttle_cache[key]['timestamp'] < self.throttle_interval:
                return True
        self._throttle_cache[key] = {'timestamp': now}
        return False
