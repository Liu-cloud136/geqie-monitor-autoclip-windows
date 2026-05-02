"""
进度数据存储仓库
负责进度数据的Redis存储和读取
"""

import json
import asyncio
from typing import Optional, Dict, Any
import redis.asyncio as redis
from core.logging_config import get_logger
from .progress_models import ProgressInfo, ProgressStage, ProgressStatus

logger = get_logger(__name__)


class ProgressRepository:
    """进度数据存储抽象"""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_client: Optional[redis.Redis] = None
        self._redis_initialized = False
        self._redis_url = redis_url or "redis://127.0.0.1:6379/0"
        self._redis_lock = asyncio.Lock()
    
    async def init_redis(self):
        if self._redis_initialized:
            return
        try:
            self.redis_client = redis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            await self.redis_client.ping()
            self._redis_initialized = True
            logger.info("ProgressRepository Redis连接成功")
        except Exception as e:
            logger.warning(f"ProgressRepository Redis连接失败: {e}")
    
    async def save(self, project_id: str, progress_info: ProgressInfo) -> bool:
        if not self.redis_client:
            return False
        try:
            async with self._redis_lock:
                await self.redis_client.setex(
                    f"progress:{project_id}",
                    3600,
                    json.dumps(progress_info.to_dict())
                )
            return True
        except Exception as e:
            logger.warning(f"保存进度到Redis失败: {e}")
            return False
    
    async def load(self, project_id: str) -> Optional[ProgressInfo]:
        if not self.redis_client:
            return None
        try:
            async with self._redis_lock:
                data = await self.redis_client.get(f"progress:{project_id}")
            if data:
                return ProgressInfo.from_dict(json.loads(data))
        except Exception as e:
            logger.warning(f"从Redis加载进度失败: {e}")
        return None
    
    async def delete(self, project_id: str) -> bool:
        if not self.redis_client:
            return False
        try:
            async with self._redis_lock:
                await self.redis_client.delete(f"progress:{project_id}")
            return True
        except Exception as e:
            logger.warning(f"删除Redis进度失败: {e}")
            return False
