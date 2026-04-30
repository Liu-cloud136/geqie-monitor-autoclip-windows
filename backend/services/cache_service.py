"""
缓存服务
提供基于Redis的缓存功能，支持异步操作
"""

import json
import logging
from typing import Optional, Any, Callable
from datetime import timedelta

logger = logging.getLogger(__name__)

DEFAULT_CACHE_TTL = 3600


class CacheService:
    """
    缓存服务类
    
    提供基于Redis的缓存功能，支持异步操作
    
    Attributes:
        redis: Redis客户端实例
        _cache_stats: 缓存统计信息
    """

    def __init__(self, redis_client):
        """
        初始化缓存服务
        
        Args:
            redis_client: Redis客户端实例（支持异步操作）
        """
        self.redis = redis_client
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }

    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存
        
        Args:
            key: 缓存键
            
        Returns:
            缓存的值，如果不存在则返回None
        """
        try:
            data = await self.redis.get(key)
            if data:
                self._cache_stats['hits'] += 1
                logger.debug(f"缓存命中: {key}")
                return json.loads(data)
            else:
                self._cache_stats['misses'] += 1
                logger.debug(f"缓存未命中: {key}")
                return None
        except Exception as e:
            logger.error(f"获取缓存失败 [{key}]: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = DEFAULT_CACHE_TTL):
        """
        设置缓存
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），默认3600秒（1小时）
        """
        try:
            await self.redis.setex(key, ttl, json.dumps(value, ensure_ascii=False))
            self._cache_stats['sets'] += 1
            logger.debug(f"设置缓存: {key}, TTL: {ttl}秒")
        except Exception as e:
            logger.error(f"设置缓存失败 [{key}]: {e}")

    async def delete(self, key: str):
        """
        删除缓存
        
        Args:
            key: 缓存键
        """
        try:
            await self.redis.delete(key)
            self._cache_stats['deletes'] += 1
            logger.debug(f"删除缓存: {key}")
        except Exception as e:
            logger.error(f"删除缓存失败 [{key}]: {e}")

    async def exists(self, key: str) -> bool:
        """
        检查缓存是否存在
        
        Args:
            key: 缓存键
            
        Returns:
            如果存在返回True，否则返回False
        """
        try:
            result = await self.redis.exists(key)
            return bool(result)
        except Exception as e:
            logger.error(f"检查缓存存在性失败 [{key}]: {e}")
            return False

    async def expire(self, key: str, ttl: int):
        """
        设置缓存的过期时间
        
        Args:
            key: 缓存键
            ttl: 过期时间（秒）
        """
        try:
            await self.redis.expire(key, ttl)
            logger.debug(f"设置缓存过期时间: {key}, TTL: {ttl}秒")
        except Exception as e:
            logger.error(f"设置缓存过期时间失败 [{key}]: {e}")

    async def get_ttl(self, key: str) -> Optional[int]:
        """
        获取缓存的剩余过期时间
        
        Args:
            key: 缓存键
            
        Returns:
            剩余秒数，如果不存在或没有过期时间则返回None
        """
        try:
            ttl = await self.redis.ttl(key)
            return ttl if ttl >= 0 else None
        except Exception as e:
            logger.error(f"获取缓存TTL失败 [{key}]: {e}")
            return None

    async def get_or_set(self, key: str, factory: Callable[[], Any], ttl: int = DEFAULT_CACHE_TTL) -> Any:
        """
        获取或设置缓存（缓存穿透保护）
        
        Args:
            key: 缓存键
            factory: 生成值的函数（异步或同步）
            ttl: 过期时间（秒）
            
        Returns:
            缓存的值或新生成的值
        """
        cached = await self.get(key)
        if cached is not None:
            return cached

        # 执行factory函数
        import inspect
        if inspect.iscoroutinefunction(factory):
            # factory是协程函数
            value = await factory()
        else:
            # factory是普通函数
            value = factory()

        if value is not None:
            await self.set(key, value, ttl)
        
        return value

    async def clear_pattern(self, pattern: str):
        """
        清除匹配模式的所有缓存
        
        Args:
            pattern: Redis键模式，如 "project:*"
        """
        try:
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                await self.redis.delete(*keys)
                logger.info(f"清除了 {len(keys)} 个缓存项，模式: {pattern}")
        except Exception as e:
            logger.error(f"清除模式缓存失败 [{pattern}]: {e}")

    async def clear_all(self):
        """清除所有缓存（慎用）"""
        try:
            await self.redis.flushdb()
            logger.warning("清除了所有缓存")
        except Exception as e:
            logger.error(f"清除所有缓存失败: {e}")

    def get_stats(self) -> dict:
        """
        获取缓存统计信息
        
        Returns:
            统计信息字典
        """
        return self._cache_stats.copy()

    def reset_stats(self):
        """重置统计信息"""
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }


# 全局缓存实例（将在应用初始化时设置）
_cache_service: Optional[CacheService] = None


def get_cache_service() -> Optional[CacheService]:
    """
    获取全局缓存服务实例
    
    Returns:
        CacheService实例
    """
    return _cache_service


def set_cache_service(redis_client):
    """
    设置全局缓存服务实例
    
    Args:
        redis_client: Redis客户端实例
    """
    global _cache_service
    _cache_service = CacheService(redis_client)
    logger.info("全局缓存服务已初始化")
