"""
异步工具函数
提供在同步上下文中运行异步函数的能力
"""

import asyncio
import logging
from typing import Any, Coroutine

from core.logging_config import get_logger

logger = get_logger(__name__)


def run_async_in_sync_context(coro: Coroutine[Any, Any, Any]) -> Any:
    """
    在同步上下文中运行异步函数的辅助函数
    
    Args:
        coro: 要运行的异步协程
        
    Returns:
        异步函数的返回值
        
    Raises:
        异步函数中抛出的任何异常
    """
    import concurrent.futures
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果事件循环正在运行，使用线程池执行
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_in_thread)
                return future.result(timeout=30)  # 30秒超时
        else:
            # 如果事件循环没有运行，直接运行
            return loop.run_until_complete(coro)
    except RuntimeError:
        # 没有事件循环，创建新的
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"运行异步上下文失败: {e}")
        # 如果是事件循环关闭错误，尝试创建新循环
        if "Event loop is closed" in str(e):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        raise
