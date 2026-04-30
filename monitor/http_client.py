#!/usr/bin/env python3
"""
异步HTTP客户端 - 替换同步requests，提升网络请求性能
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from functools import wraps
import aiohttp
import hashlib
import time

from cache_manager import cache_manager


class AsyncHTTPClient:
    """异步HTTP客户端单例 - 支持连接复用和自动重试"""

    _instance: Optional['AsyncHTTPClient'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
        self._last_error: Optional[str] = None
        self._error_count: int = 0
        self._initialized = True

    async def get_session(self) -> aiohttp.ClientSession:
        """获取或创建Session"""
        if self._session is None or self._session.closed:
            async with self._lock:
                if self._session is None or self._session.closed:
                    # 不设置默认超时，让每个请求自己控制超时
                    connector = aiohttp.TCPConnector(
                        limit=100,
                        limit_per_host=10,
                        ttl_dns_cache=300,
                        use_dns_cache=True
                    )
                    self._session = aiohttp.ClientSession(
                        connector=connector
                    )
                    logging.info("HTTP客户端Session已创建")
        return self._session

    async def close(self):
        """关闭Session"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logging.info("HTTP客户端Session已关闭")

    async def get(self, url: str, headers: Dict = None,
                  timeout: int = 15, retry: int = 3,
                  retry_delay: float = 1.0) -> Optional[Dict]:
        """
        异步GET请求

        Args:
            url: 请求URL
            headers: 请求头
            timeout: 超时时间（秒）
            retry: 重试次数
            retry_delay: 重试延迟（秒）

        Returns:
            响应JSON数据，失败返回None
        """
        session = await self.get_session()
        last_error = None

        for attempt in range(retry):
            try:
                # 使用 aiohttp 的超时机制
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status == 200:
                        self._error_count = 0
                        return await response.json()
                    elif response.status == 429:
                        logging.warning(f"API请求频率限制: {url}")
                        await asyncio.sleep(2)
                        continue
                    else:
                        logging.warning(f"API返回状态码 {response.status}: {url}")
                        last_error = f"HTTP {response.status}"
                        continue

            except asyncio.TimeoutError:
                last_error = "Timeout"
                logging.warning(f"请求超时 (尝试 {attempt + 1}/{retry}): {url}")
            except TimeoutError:
                last_error = "Timeout"
                logging.warning(f"请求超时 (尝试 {attempt + 1}/{retry}): {url}")
            except aiohttp.ClientError as e:
                last_error = str(e)
                logging.warning(f"HTTP请求失败 (尝试 {attempt + 1}/{retry}): {url} - {e}")
            except Exception as e:
                last_error = str(e)
                # 忽略 "Timeout context manager" 相关错误
                if "Timeout context manager" not in str(e):
                    logging.error(f"未知请求错误: {url} - {e}")

            if attempt < retry - 1:
                await asyncio.sleep(retry_delay * (2 ** attempt))

        self._error_count += 1
        self._last_error = last_error
        return None

    async def post(self, url: str, headers: Dict = None,
                   json_data: Dict = None,
                   timeout: int = 15, retry: int = 3) -> Optional[Dict]:
        """异步POST请求"""
        session = await self.get_session()

        for attempt in range(retry):
            try:
                async with session.post(
                    url,
                    headers=headers,
                    json=json_data,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status == 200:
                        self._error_count = 0
                        return await response.json()
                    else:
                        logging.warning(f"POST返回状态码 {response.status}: {url}")
                        continue

            except Exception as e:
                logging.warning(f"POST请求失败 (尝试 {attempt + 1}/{retry}): {url} - {e}")
                if attempt < retry - 1:
                    await asyncio.sleep(1 * (2 ** attempt))
                continue

        return None

    def get_stats(self) -> Dict:
        """获取客户端统计"""
        return {
            'error_count': self._error_count,
            'last_error': self._last_error,
            'session_active': self._session is not None and not self._session.closed
        }


# 全局HTTP客户端实例
http_client = AsyncHTTPClient()


# 缓存装饰器版本的网络请求
def cached_request(ttl: float = 300, key_prefix: str = 'http'):
    """
    带缓存的HTTP请求装饰器

    用法:
    @cached_request(ttl=60)
    async def fetch_room_info(room_id):
        return await http_client.get(f"https://api.example.com/room/{room_id}")
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()

            cache = cache_manager.get_cache('http', ttl=ttl)

            # 尝试从缓存获取
            result = cache.get(cache_key)
            if result is not None:
                logging.debug(f"缓存命中: {cache_key[:16]}...")
                return result

            # 执行请求
            result = await func(*args, **kwargs)

            # 缓存结果
            if result is not None:
                cache.set(cache_key, result, ttl)

            return result

        return wrapper
    return decorator


# 便捷函数
async def fetch_json(url: str, headers: Dict = None, **kwargs) -> Optional[Dict]:
    """快速获取JSON数据"""
    return await http_client.get(url, headers=headers, **kwargs)


async def post_json(url: str, json_data: Dict, headers: Dict = None, **kwargs) -> Optional[Dict]:
    """快速提交JSON数据"""
    return await http_client.post(url, headers=headers, json_data=json_data, **kwargs)
