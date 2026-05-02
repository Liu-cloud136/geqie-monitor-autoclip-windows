"""
Redis发布订阅管理器
管理Redis Pub/Sub连接和消息路由
"""

import json
import logging
import asyncio
from typing import Dict, Set, Any, Optional, Callable
from datetime import datetime
import redis.asyncio as redis
from core.unified_config import get_redis_url
from services.exceptions import ServiceError, ErrorCode, SystemError
from core.logging_config import get_logger

logger = get_logger(__name__)


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
