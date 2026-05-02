"""
WebSocket连接管理器
管理用户与连接的映射关系
"""

import asyncio
from typing import Dict, Set
from core.logging_config import get_logger

logger = get_logger(__name__)


class WebSocketConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.user_connections: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()
    
    async def register_connection(self, user_id: str, connection_id: str):
        async with self._lock:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)
        logger.debug(f"连接注册: {user_id} -> {connection_id}")
    
    async def unregister_connection(self, user_id: str, connection_id: str):
        async with self._lock:
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(connection_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
        logger.debug(f"连接注销: {user_id} -> {connection_id}")
    
    async def get_user_connections(self, user_id: str) -> Set[str]:
        return self.user_connections.get(user_id, set()).copy()
    
    async def get_all_users(self) -> Set[str]:
        async with self._lock:
            return set(self.user_connections.keys())
