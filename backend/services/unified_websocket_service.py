"""
统一WebSocket服务
整合所有WebSocket相关功能，提供统一的WebSocket管理接口
使用事件驱动架构解耦服务间通信
"""

import json
import logging
import asyncio
from typing import Dict, Set, Any, Optional, Callable
from datetime import datetime
import redis.asyncio as redis
from core.unified_config import get_redis_url
from core.websocket_manager import manager
from core.event_bus import EventBus, EventType, Event, get_event_bus
from services.exceptions import ServiceError, ErrorCode, SystemError
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


class RedisPubSubManager:
    """Redis发布订阅管理器"""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or get_redis_url()
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.channels_ref: Dict[str, int] = {}
        self.router: Dict[str, Set[Callable]] = {}
        self._lock = asyncio.Lock()
        self._initialized = False
    
    async def init(self):
        if self._initialized:
            return
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            self.pubsub = self.redis_client.pubsub(ignore_subscribe_messages=True)
            self._initialized = True
            logger.info("RedisPubSubManager 初始化成功")
        except (ConnectionError, OSError) as e:
            logger.error(f"RedisPubSubManager 初始化失败: {e}")
            raise SystemError(f"Redis连接失败: {e}", cause=e)
        except Exception as e:
            logger.error(f"RedisPubSubManager 初始化失败: {e}")
            raise SystemError(f"RedisPubSubManager 初始化失败: {e}", cause=e)
    
    async def close(self):
        if self.pubsub:
            await self.pubsub.aclose()
        if self.redis_client:
            await self.redis_client.aclose()
        self._initialized = False
        logger.info("RedisPubSubManager 已关闭")
    
    async def subscribe(self, channel: str, handler: Callable):
        async with self._lock:
            if channel not in self.router:
                self.router[channel] = set()
            if handler in self.router[channel]:
                return
            
            need_sub = channel not in self.channels_ref
            self.channels_ref[channel] = self.channels_ref.get(channel, 0) + 1
            self.router[channel].add(handler)
            
            if need_sub and self.pubsub:
                await self.pubsub.subscribe(channel)
                logger.info(f"订阅频道: {channel}")
    
    async def unsubscribe(self, channel: str, handler: Callable):
        async with self._lock:
            if channel in self.router:
                self.router[channel].discard(handler)
            
            if channel in self.channels_ref:
                self.channels_ref[channel] -= 1
                if self.channels_ref[channel] <= 0:
                    del self.channels_ref[channel]
                    self.router.pop(channel, None)
                    if self.pubsub:
                        await self.pubsub.unsubscribe(channel)
                    logger.info(f"取消订阅频道: {channel}")
    
    async def publish(self, channel: str, message: Dict[str, Any]):
        if not self.redis_client:
            return
        try:
            await self.redis_client.publish(channel, json.dumps(message))
        except (ConnectionError, OSError) as e:
            logger.error(f"发布消息失败: {e}")
        except Exception as e:
            logger.error(f"发布消息失败: {e}")
    
    async def get_message(self, timeout: float = 0.1) -> Optional[Dict]:
        if not self.pubsub:
            return None
        try:
            return await self.pubsub.get_message(timeout=timeout)
        except (ConnectionError, OSError) as e:
            logger.error(f"获取消息失败: {e}")
            return None
        except Exception as e:
            logger.error(f"获取消息失败: {e}")
            return None


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
        import time
        now = time.time()
        if key in self._throttle_cache:
            if now - self._throttle_cache[key]['timestamp'] < self.throttle_interval:
                return True
        self._throttle_cache[key] = {'timestamp': now}
        return False


class UnifiedWebSocketService:
    """统一WebSocket服务 - 使用事件驱动架构"""
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        self._event_bus = event_bus
        self._connection_manager = WebSocketConnectionManager()
        self._pubsub_manager = RedisPubSubManager()
        self._broadcaster = MessageBroadcaster(event_bus)
        self.user_subscriptions: Dict[str, Set[str]] = {}
        self.listen_task: Optional[asyncio.Task] = None
        self.is_running = False
    
    def set_event_bus(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._broadcaster.set_event_bus(event_bus)
    
    async def start(self):
        if self.is_running:
            return
        
        try:
            await self._pubsub_manager.init()
            self.is_running = True
            self.listen_task = asyncio.create_task(self._listen_loop())
            
            if self._event_bus:
                self._event_bus.subscribe_async(EventType.PROGRESS_UPDATED, self._on_progress_event)
                self._event_bus.subscribe_async(EventType.PROGRESS_COMPLETED, self._on_progress_event)
                self._event_bus.subscribe_async(EventType.PROGRESS_FAILED, self._on_progress_event)
            
            logger.info("统一WebSocket服务已启动")
            
        except Exception as e:
            logger.error(f"启动统一WebSocket服务失败: {e}")
            self.is_running = False
            raise ServiceError(f"启动WebSocket服务失败: {str(e)}", ErrorCode.SYSTEM_ERROR, cause=e)
    
    async def stop(self):
        self.is_running = False
        
        if self.listen_task:
            self.listen_task.cancel()
            try:
                await self.listen_task
            except asyncio.CancelledError:
                pass
        
        await self._pubsub_manager.close()
        logger.info("统一WebSocket服务已停止")
    
    async def _on_progress_event(self, event: Event):
        progress_data = event.data
        project_id = progress_data.get('project_id')
        if not project_id:
            return
        
        message = {
            'type': 'progress',
            'project_id': project_id,
            'stage': progress_data.get('stage', ''),
            'percent': progress_data.get('progress', 0),
            'message': progress_data.get('message', ''),
            'ts': int(datetime.utcnow().timestamp() * 1000)
        }
        
        # 添加预计剩余时间字段
        if 'estimated_remaining' in progress_data:
            message['estimated_remaining'] = progress_data['estimated_remaining']
        
        await self._broadcaster.broadcast(message, topic=f"progress:project:{project_id}")
    
    async def _listen_loop(self):
        backoff = 0.05
        
        while self.is_running:
            try:
                has_channels = bool(self._pubsub_manager.channels_ref)
                
                if not has_channels:
                    await asyncio.sleep(0.2)
                    continue
                
                msg = await self._pubsub_manager.get_message(timeout=0.1)
                
                if not msg or msg.get("type") != "message":
                    await asyncio.sleep(0.05)
                    continue
                
                channel = msg["channel"]
                data = msg["data"]
                
                try:
                    message_data = json.loads(data) if isinstance(data, str) else data
                except json.JSONDecodeError as e:
                    logger.error(f"解析消息失败: {e}")
                    continue
                
                handlers = self._pubsub_manager.router.get(channel, set())
                for handler in handlers:
                    try:
                        result = handler(json.dumps(message_data))
                        if asyncio.iscoroutine(result):
                            await result
                    except (RuntimeError, TimeoutError) as e:
                        logger.error(f"处理器执行失败: {e}")
                    except Exception as e:
                        logger.error(f"处理器执行失败: {e}")
                
                backoff = 0.05
                
            except (RuntimeError, TimeoutError) as e:
                logger.error(f"处理Redis消息失败: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 1.0)
            except Exception as e:
                logger.error(f"处理Redis消息失败: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 1.0)
    
    async def send_task_update(self, task_id: str, status: str, progress: Optional[int] = None,
                               message: Optional[str] = None, error: Optional[str] = None):
        notification = {
            "type": "task_update",
            "task_id": task_id,
            "status": status,
            "progress": progress,
            "message": message,
            "error": error,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self._broadcaster.broadcast(notification, topic=f"task_{task_id}")
        logger.info(f"任务更新通知已发送: {task_id} - {status}")
    
    async def send_project_update(self, project_id: str, status: str, progress: Optional[int] = None,
                                  message: Optional[str] = None):
        notification = {
            "type": "project_update",
            "project_id": project_id,
            "status": status,
            "progress": progress,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self._broadcaster.broadcast(notification, topic=f"progress:project:{project_id}")
        logger.info(f"项目更新通知已发送: {project_id} - {status}")
    
    async def broadcast_to_project(self, project_id: str, message: dict):
        """
        广播消息到指定项目的所有订阅者
        
        Args:
            project_id: 项目ID
            message: 要广播的消息字典
        """
        await self._broadcaster.broadcast(message, topic=f"progress:project:{project_id}")
        logger.debug(f"已广播消息到项目 {project_id}: {message.get('type', 'unknown')}")
    
    async def send_system_notification(self, notification_type: str, title: str, message: str,
                                       level: str = "info"):
        notification = {
            "type": "system_notification",
            "notification_type": notification_type,
            "title": title,
            "message": message,
            "level": level,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self._broadcaster.broadcast(notification)
        logger.info(f"系统通知已发送: {title} - {message}")
    
    async def send_error_notification(self, error_type: str, error_message: str,
                                      details: Optional[Dict[str, Any]] = None):
        notification = {
            "type": "error_notification",
            "error_type": error_type,
            "error_message": error_message,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self._broadcaster.broadcast(notification)
        logger.error(f"错误通知已发送: {error_type} - {error_message}")
    
    async def send_processing_start(self, project_id: str, task_id: str):
        notification = {
            'type': 'task_update',
            'task_id': task_id,
            'status': 'running',
            'progress': 0,
            'message': '开始处理',
            'project_id': project_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        await self._broadcaster.broadcast(notification, topic=f"progress:project:{project_id}")
        logger.info(f"处理开始通知已发送: {project_id} - {task_id}")
    
    async def send_processing_progress(self, project_id: str, task_id: str, progress: int, message: str,
                                       current_step: int = 0, total_steps: int = 6, step_name: str = "",
                                       estimated_remaining: Optional[int] = None):
        notification = {
            'type': 'progress',
            'project_id': project_id,
            'stage': step_name,
            'percent': progress,
            'message': message,
            'ts': int(datetime.utcnow().timestamp() * 1000),
            'estimated_remaining': estimated_remaining
        }
        
        await self._broadcaster.broadcast(notification, topic=f"progress:project:{project_id}")
        logger.info(f"处理进度通知已发送: {project_id} - {task_id} - {progress}% - {step_name}")
    
    async def send_processing_complete(self, project_id: str, task_id: str, result: dict):
        notification = {
            "type": "task_update",
            "task_id": task_id,
            "project_id": project_id,  # 添加项目ID
            "status": "completed",
            "progress": 100,
            "message": "项目处理完成",
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self._broadcaster.broadcast(notification, topic=f"progress:project:{project_id}")
        logger.info(f"处理完成通知已发送: {project_id} - {task_id}")
    
    async def send_processing_error(self, project_id: str, task_id: str, error_message: str):
        notification = {
            "type": "task_update",
            "task_id": task_id,
            "status": "failed",
            "progress": 0,
            "error": error_message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self._broadcaster.broadcast(notification, topic=f"progress:project:{project_id}")
        logger.info(f"处理错误通知已发送: {project_id} - {task_id} - {error_message}")
    
    async def subscribe_user_to_task(self, user_id: str, task_id: str) -> bool:
        try:
            # 支持订阅项目进度频道和任务进度频道
            # 如果task_id看起来像项目ID（UUID格式），订阅项目进度频道
            # 否则订阅任务进度频道
            if "-" in task_id and len(task_id) == 36:  # UUID格式，可能是项目ID
                channel = f"progress:project:{task_id}"
            else:
                channel = f"progress:{task_id}"
            
            if user_id not in self.user_subscriptions:
                self.user_subscriptions[user_id] = set()
            self.user_subscriptions[user_id].add(channel)
            
            async def sender(data: str):
                try:
                    message_data = json.loads(data)
                    ws_message = {
                        "type": "task_progress_update",
                        **message_data,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    await self._broadcaster.send_to_user(user_id, ws_message)
                except (RuntimeError, TimeoutError) as e:
                    logger.error(f"发送消息给用户 {user_id} 失败: {e}")
                except Exception as e:
                    logger.error(f"发送消息给用户 {user_id} 失败: {e}")
            
            await self._pubsub_manager.subscribe(channel, sender)
            
            await self._broadcaster.send_to_user(user_id, {
                "type": "subscription_confirmed",
                "task_id": task_id,
                "message": f"已订阅任务 {task_id} 的进度更新",
                "timestamp": datetime.utcnow().isoformat()
            })
            
            logger.debug(f"用户 {user_id} 已订阅任务 {task_id}，频道: {channel}")
            return True
            
        except Exception as e:
            logger.error(f"用户订阅任务失败: {e}")
            return False
    
    async def subscribe_user_to_many_tasks(self, user_id: str, task_ids: list) -> Dict[str, Any]:
        """
        批量订阅用户对多个任务的进度更新
        
        Args:
            user_id: 用户ID
            task_ids: 要订阅的任务ID列表（支持完整频道名称或纯ID）
            
        Returns:
            包含 added 和 already_subscribed 的字典
        """
        added = []
        already_subscribed = []
        
        for task_id in task_ids:
            # 支持两种格式: 完整频道名称 (progress:project:{id} 或 progress:{id}) 或纯ID
            if task_id.startswith("progress:"):
                channel = task_id
                # 提取纯ID用于调用subscribe_user_to_task
                if task_id.startswith("progress:project:"):
                    pure_id = task_id.replace("progress:project:", "")
                else:
                    pure_id = task_id.replace("progress:", "")
            else:
                channel = f"progress:{task_id}"
                pure_id = task_id
            
            if user_id in self.user_subscriptions and channel in self.user_subscriptions[user_id]:
                already_subscribed.append(pure_id)
            else:
                success = await self.subscribe_user_to_task(user_id, pure_id)
                if success:
                    added.append(pure_id)
        
        return {
            "added": added,
            "already_subscribed": already_subscribed
        }
    
    async def unsubscribe_user_from_task(self, user_id: str, task_id: str) -> bool:
        try:
            # 支持订阅项目进度频道和任务进度频道
            # 如果task_id看起来像项目ID（UUID格式），订阅项目进度频道
            # 否则订阅任务进度频道
            if "-" in task_id and len(task_id) == 36:  # UUID格式，可能是项目ID
                channel = f"progress:project:{task_id}"
            else:
                channel = f"progress:{task_id}"
            
            async def sender(data: str):
                pass
            
            await self._pubsub_manager.unsubscribe(channel, sender)
            
            if user_id in self.user_subscriptions:
                self.user_subscriptions[user_id].discard(channel)
            
            await self._broadcaster.send_to_user(user_id, {
                "type": "unsubscription_confirmed",
                "task_id": task_id,
                "message": f"已取消订阅任务 {task_id} 的进度更新",
                "timestamp": datetime.utcnow().isoformat()
            })
            
            logger.debug(f"用户 {user_id} 已取消订阅任务 {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"用户取消订阅任务失败: {e}")
            return False
    
    async def unsubscribe_user_from_all_tasks(self, user_id: str):
        if user_id in self.user_subscriptions:
            task_ids = list(self.user_subscriptions[user_id])
            for task_id in task_ids:
                await self.unsubscribe_user_from_task(user_id, task_id)
            logger.info(f"用户 {user_id} 已取消所有任务订阅")
    
    async def unsubscribe_user_from_many_tasks(self, user_id: str, task_ids: list) -> Dict[str, Any]:
        """
        批量取消用户对多个任务的订阅
        
        Args:
            user_id: 用户ID
            task_ids: 要取消订阅的任务ID列表（支持完整频道名称或纯ID）
            
        Returns:
            包含 removed 和 not_subscribed 的字典
        """
        removed = []
        not_subscribed = []
        
        for task_id in task_ids:
            # 支持两种格式: 完整频道名称 (progress:project:{id} 或 progress:{id}) 或纯ID
            if task_id.startswith("progress:"):
                channel = task_id
                # 提取纯ID用于调用unsubscribe_user_from_task
                if task_id.startswith("progress:project:"):
                    pure_id = task_id.replace("progress:project:", "")
                else:
                    pure_id = task_id.replace("progress:", "")
            else:
                channel = f"progress:{task_id}"
                pure_id = task_id
            
            if user_id in self.user_subscriptions and channel in self.user_subscriptions[user_id]:
                success = await self.unsubscribe_user_from_task(user_id, pure_id)
                if success:
                    removed.append(pure_id)
            else:
                not_subscribed.append(pure_id)
        
        return {
            "removed": removed,
            "not_subscribed": not_subscribed
        }
    
    async def get_subscription_status(self, user_id: str) -> Dict[str, Any]:
        return {
            "user_id": user_id,
            "subscribed_tasks": list(self.user_subscriptions.get(user_id, set())),
            "total_subscriptions": len(self.user_subscriptions.get(user_id, set())),
            "active_channels": len(self._pubsub_manager.channels_ref)
        }
    
    async def sync_user_subscriptions(self, user_id: str, channels: Set[str]) -> Dict[str, Any]:
        """
        同步用户的订阅频道
        
        Args:
            user_id: 用户ID
            channels: 要订阅的频道集合（项目ID或任务ID）
            
        Returns:
            包含 added, removed, unchanged 的字典
        """
        try:
            current_subscriptions = self.user_subscriptions.get(user_id, set()).copy()
            new_channels = set(channels)
            
            # 计算需要新增、移除和保持不变的频道
            added = new_channels - current_subscriptions
            removed = current_subscriptions - new_channels
            unchanged = current_subscriptions & new_channels
            
            # 取消需要移除的订阅
            for channel in removed:
                # 支持两种频道格式: progress:project:{id} 和 progress:{id}
                if channel.startswith("progress:project:"):
                    task_id = channel.replace("progress:project:", "")
                else:
                    task_id = channel.replace("progress:", "")
                await self.unsubscribe_user_from_task(user_id, task_id)
            
            # 订阅新的频道
            for channel in added:
                # 支持两种频道格式: progress:project:{id} 和 progress:{id}
                if channel.startswith("progress:project:"):
                    task_id = channel.replace("progress:project:", "")
                else:
                    task_id = channel.replace("progress:", "")
                success = await self.subscribe_user_to_task(user_id, task_id)
                if not success:
                    logger.warning(f"订阅频道 {task_id} 失败")
            
            logger.info(f"用户 {user_id} 已同步订阅: 新增 {len(added)}, 移除 {len(removed)}, 不变 {len(unchanged)}")
            
            return {
                "added": list(added),
                "removed": list(removed),
                "unchanged": list(unchanged)
            }
            
        except Exception as e:
            logger.error(f"同步用户订阅失败: {e}")
            return {
                "added": [],
                "removed": [],
                "unchanged": []
            }


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
