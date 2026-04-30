"""
WebSocket连接管理器
管理WebSocket连接和消息广播
支持同一用户多个连接
"""

import json
import logging
import asyncio
import uuid
from typing import Dict, Set, Any, Optional, List
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

logger = logging.getLogger(__name__)

class ConnectionManager:
    """WebSocket连接管理器 - 支持同一用户多个连接"""
    
    def __init__(self):
        # 连接ID到WebSocket的映射
        self.active_connections: Dict[str, WebSocket] = {}
        # 连接ID到用户ID的映射
        self.connection_to_user: Dict[str, str] = {}
        # 用户ID到连接ID集合的映射（支持多连接）
        self.user_connections: Dict[str, Set[str]] = {}
        # 存储每个连接订阅的主题
        self.connection_subscriptions: Dict[str, Set[str]] = {}
        # 存储主题订阅者
        self.topic_subscribers: Dict[str, Set[str]] = {}
        # 发送队列和任务（按连接ID）
        self.send_queues: Dict[str, asyncio.Queue] = {}
        self.send_tasks: Dict[str, asyncio.Task] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str) -> str:
        """建立WebSocket连接，返回连接ID"""
        await websocket.accept()
        
        # 生成唯一的连接ID
        connection_id = f"{user_id}_{uuid.uuid4().hex[:8]}"
        
        # 存储连接
        self.active_connections[connection_id] = websocket
        self.connection_to_user[connection_id] = user_id
        self.connection_subscriptions[connection_id] = set()
        
        # 更新用户的连接集合
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(connection_id)
        
        # 创建发送队列和任务
        self.send_queues[connection_id] = asyncio.Queue()
        self.send_tasks[connection_id] = asyncio.create_task(
            self._send_worker(connection_id)
        )
        
        logger.info(f"用户 {user_id} 已连接 (连接ID: {connection_id}, 总连接数: {len(self.user_connections[user_id])})")
        return connection_id
    
    async def disconnect(self, connection_id: str):
        """断开WebSocket连接"""
        user_id = self.connection_to_user.get(connection_id)
        
        # 停止发送任务
        if connection_id in self.send_tasks:
            task = self.send_tasks[connection_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self.send_tasks[connection_id]
        
        # 清理队列
        if connection_id in self.send_queues:
            del self.send_queues[connection_id]
        
        # 清理连接
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        if connection_id in self.connection_subscriptions:
            del self.connection_subscriptions[connection_id]
        if connection_id in self.connection_to_user:
            del self.connection_to_user[connection_id]
        
        # 从用户的连接集合中移除
        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(connection_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        # 从所有主题中移除连接
        for topic in self.topic_subscribers:
            self.topic_subscribers[topic].discard(connection_id)
        
        logger.info(f"用户 {user_id} 断开连接 (连接ID: {connection_id})")
    
    async def _send_worker(self, connection_id: str):
        """发送工作器 - 从队列中取消息并发送"""
        try:
            while True:
                message = await self.send_queues[connection_id].get()
                if message is None:  # 停止信号
                    break
                
                if connection_id in self.active_connections:
                    try:
                        await self.active_connections[connection_id].send_text(json.dumps(message))
                    except Exception as e:
                        logger.error(f"发送消息到连接 {connection_id} 失败: {e}")
                        break
                
                self.send_queues[connection_id].task_done()
        except asyncio.CancelledError:
            logger.debug(f"连接 {connection_id} 发送工作器已取消")
        except Exception as e:
            logger.error(f"连接 {connection_id} 发送工作器异常: {e}")
    
    async def send_to_connection(self, message: Dict[str, Any], connection_id: str):
        """发送消息到特定连接"""
        if connection_id in self.send_queues:
            try:
                await self.send_queues[connection_id].put(message)
            except Exception as e:
                logger.error(f"将消息加入队列失败 {connection_id}: {e}")
                await self.disconnect(connection_id)
    
    async def send_personal_message(self, message: Dict[str, Any], user_id: str):
        """发送个人消息到用户的所有连接"""
        if user_id not in self.user_connections:
            return
        
        # 发送到用户的所有连接
        disconnected = []
        for connection_id in list(self.user_connections[user_id]):
            try:
                await self.send_to_connection(message, connection_id)
            except Exception as e:
                logger.error(f"发送消息给用户 {user_id} 的连接 {connection_id} 失败: {e}")
                disconnected.append(connection_id)
        
        # 清理断开的连接
        for connection_id in disconnected:
            await self.disconnect(connection_id)
    
    async def broadcast(self, message: Dict[str, Any]):
        """广播消息给所有连接"""
        disconnected = []
        for connection_id in list(self.active_connections.keys()):
            try:
                await self.send_to_connection(message, connection_id)
            except Exception as e:
                logger.error(f"广播消息到连接 {connection_id} 失败: {e}")
                disconnected.append(connection_id)
        
        # 清理断开的连接
        for connection_id in disconnected:
            await self.disconnect(connection_id)
    
    async def broadcast_to_topic(self, message: Dict[str, Any], topic: str):
        """广播消息给特定主题的订阅者"""
        if topic not in self.topic_subscribers:
            return
        
        disconnected = []
        for connection_id in list(self.topic_subscribers[topic]):
            if connection_id in self.active_connections:
                try:
                    await self.send_to_connection(message, connection_id)
                except Exception as e:
                    logger.error(f"发送主题消息到连接 {connection_id} 失败: {e}")
                    disconnected.append(connection_id)
        
        # 清理断开的连接
        for connection_id in disconnected:
            await self.disconnect(connection_id)
    
    def subscribe_to_topic(self, connection_id: str, topic: str):
        """连接订阅主题"""
        if connection_id not in self.connection_subscriptions:
            self.connection_subscriptions[connection_id] = set()
        
        self.connection_subscriptions[connection_id].add(topic)
        
        if topic not in self.topic_subscribers:
            self.topic_subscribers[topic] = set()
        
        self.topic_subscribers[topic].add(connection_id)
        
        user_id = self.connection_to_user.get(connection_id, "unknown")
        logger.info(f"连接 {connection_id} (用户 {user_id}) 订阅主题 {topic}")
    
    def unsubscribe_from_topic(self, connection_id: str, topic: str):
        """连接取消订阅主题"""
        if connection_id in self.connection_subscriptions:
            self.connection_subscriptions[connection_id].discard(topic)
        
        if topic in self.topic_subscribers:
            self.topic_subscribers[topic].discard(connection_id)
        
        user_id = self.connection_to_user.get(connection_id, "unknown")
        logger.info(f"连接 {connection_id} (用户 {user_id}) 取消订阅主题 {topic}")
    
    def get_user_connections(self, user_id: str) -> List[str]:
        """获取用户的所有连接ID"""
        return list(self.user_connections.get(user_id, set()))
    
    def get_connection_count(self) -> int:
        """获取当前连接数"""
        return len(self.active_connections)
    
    def get_user_count(self) -> int:
        """获取当前用户数"""
        return len(self.user_connections)
    
    def get_topic_subscriber_count(self, topic: str) -> int:
        """获取主题订阅者数量"""
        return len(self.topic_subscribers.get(topic, set()))

# 全局连接管理器实例
manager = ConnectionManager()

class WebSocketMessage:
    """WebSocket消息工具类"""
    
    @staticmethod
    def create_task_update(task_id: str, status: str, progress: Optional[int] = None, 
                          message: Optional[str] = None, error: Optional[str] = None) -> Dict[str, Any]:
        """创建任务更新消息"""
        return {
            "type": "task_update",
            "task_id": task_id,
            "status": status,
            "progress": progress,
            "message": message,
            "error": error,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def create_system_notification(notification_type: str, title: str, message: str, 
                                 level: str = "info") -> Dict[str, Any]:
        """创建系统通知消息"""
        return {
            "type": "system_notification",
            "notification_type": notification_type,
            "title": title,
            "message": message,
            "level": level,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def create_project_update(project_id: str, status: str, progress: Optional[int] = None,
                            message: Optional[str] = None) -> Dict[str, Any]:
        """创建项目更新消息"""
        return {
            "type": "project_update",
            "project_id": project_id,
            "status": status,
            "progress": progress,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def create_error_notification(error_type: str, error_message: str, 
                                details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建错误通知消息"""
        return {
            "type": "error_notification",
            "error_type": error_type,
            "error_message": error_message,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        }
