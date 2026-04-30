#!/usr/bin/env python3
"""
缓存管理器 - 统一缓存管理，支持多种缓存策略
"""
import time
import threading
import hashlib
from typing import Any, Callable, Optional, Dict
from functools import wraps
import logging


class CacheEntry:
    """缓存条目"""

    def __init__(self, value: Any, ttl: float, max_size: Optional[int] = None):
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
        self.hits = 0
        self.max_size = max_size

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl <= 0:
            return False  # 永不过期
        return time.time() - self.created_at > self.ttl

    def access(self) -> Any:
        """访问缓存并记录命中"""
        self.hits += 1
        return self.value


class MemoryCache:
    """内存缓存实现"""

    def __init__(self, default_ttl: float = 60, max_entries: int = 1000):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._default_ttl = default_ttl
        self._max_entries = max_entries
        self._stats = {'hits': 0, 'misses': 0, 'evictions': 0}

    def get(self, key: str, default: Any = None) -> Any:
        """获取缓存值"""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._stats['misses'] += 1
                return default

            if entry.is_expired():
                del self._cache[key]
                self._stats['misses'] += 1
                return default

            return entry.access()

    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """设置缓存值"""
        with self._lock:
            # 检查是否需要清理
            if len(self._cache) >= self._max_entries:
                self._evict_lru()

            ttl = ttl if ttl is not None else self._default_ttl
            self._cache[key] = CacheEntry(value, ttl)

    def delete(self, key: str) -> bool:
        """删除缓存"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()

    def _evict_lru(self):
        """淘汰最少使用的条目"""
        if not self._cache:
            return

        # 找出最少使用的条目
        min_hits = min(e.hits for e in self._cache.values())
        keys_to_delete = [k for k, e in self._cache.items() if e.hits == min_hits]

        # 删除最老的那个
        key = min(keys_to_delete, key=lambda k: self._cache[k].created_at)
        del self._cache[key]
        self._stats['evictions'] += 1

    def cleanup_expired(self):
        """清理过期条目"""
        with self._lock:
            expired_keys = [k for k, e in self._cache.items() if e.is_expired()]
            for key in expired_keys:
                del self._cache[key]

    def get_stats(self) -> Dict:
        """获取缓存统计"""
        with self._lock:
            total = self._stats['hits'] + self._stats['misses']
            return {
                'entries': len(self._cache),
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'hit_rate': self._stats['hits'] / total if total > 0 else 0,
                'evictions': self._stats['evictions']
            }


class CacheManager:
    """缓存管理器 - 支持命名空间隔离"""

    _instance: Optional['CacheManager'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._caches: Dict[str, MemoryCache] = {}
        self._lock = threading.Lock()
        self._default_ttl = 60
        self._max_entries = 1000
        self._initialized = True

    def get_cache(self, namespace: str = 'default', ttl: Optional[float] = None,
                  max_entries: Optional[int] = None) -> MemoryCache:
        """获取命名空间缓存"""
        with self._lock:
            if namespace not in self._caches:
                self._caches[namespace] = MemoryCache(
                    default_ttl=ttl or self._default_ttl,
                    max_entries=max_entries or self._max_entries
                )
            return self._caches[namespace]

    def clear_all(self):
        """清空所有缓存"""
        for cache in self._caches.values():
            cache.clear()

    def cleanup_all(self):
        """清理所有过期条目"""
        for cache in self._caches.values():
            cache.cleanup_expired()

    def get_stats(self) -> Dict:
        """获取所有缓存统计"""
        return {
            namespace: cache.get_stats()
            for namespace, cache in self._caches.items()
        }


# 创建全局缓存管理器
cache_manager = CacheManager()


def cached(namespace: str = 'default', ttl: Optional[float] = None,
           key_func: Optional[Callable] = None):
    """
    缓存装饰器

    用法:
    @cached('api', ttl=60)
    def fetch_data(param):
        return expensive_operation(param)

    # 自定义缓存键
    @cached('api', key_func=lambda args, kwargs: f"{args[0]}_{kwargs.get('page', 1)}")
    def fetch_page(page_id, page=1):
        return fetch_page_data(page_id, page)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            if key_func:
                cache_key = key_func(args, kwargs)
            else:
                # 默认键生成：函数名 + 参数哈希
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()

            cache = cache_manager.get_cache(namespace, ttl)

            # 尝试获取缓存
            result = cache.get(cache_key)
            if result is not None:
                return result

            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result

        # 添加缓存管理属性
        wrapper.cache_clear = lambda: cache_manager.get_cache(namespace).clear()
        wrapper.cache_stats = lambda: cache_manager.get_cache(namespace).get_stats()

        return wrapper
    return decorator


def invalidate_cache(namespace: str, key_prefix: str = None):
    """
    使缓存失效

    用法:
    invalidate_cache('api')  # 清空整个命名空间
    """
    if key_prefix:
        # 只清空匹配前缀的键（需要遍历）
        cache = cache_manager.get_cache(namespace)
        # 注意：这里简化处理，实际可以使用 trie 等结构优化前缀匹配
        cache.clear()
    else:
        cache_manager.get_cache(namespace).clear()
