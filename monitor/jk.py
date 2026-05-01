#!/usr/bin/env python3
"""
B站直播弹幕监控与数据展示系统 - 集成鸽切关键词监控和Web展示
使用bilibili_api的LIVE事件检测开播，同时提供Web API和SSE实时推送
时区设置为中国时区（东八区）
"""

import asyncio
import logging
import json
import os
import glob
import re
import threading
import time
import queue
import hashlib
import secrets
import traceback
import smtplib
import requests
from email.mime.text import MIMEText
from email.header import Header
from functools import wraps
from datetime import datetime, timedelta
from collections import deque
import uuid
import time
from typing import Dict, Optional, List, Tuple, Any
from enum import Enum
from contextlib import contextmanager

import pytz
from bilibili_api.live import LiveDanmaku
from bilibili_api import Credential

# 优化：导入新模块
from config_manager import (
    config_manager, load_config, get_config, 
    get_api_urls, get_bilibili_headers,
    is_multi_room_enabled, get_multi_room_config, get_enabled_rooms
)
from cache_manager import cache_manager, cached, invalidate_cache
from http_client import http_client
from data_manager import data_manager

# 导入独立的在线聊天室模块
import live_chatroom

# 导入弹幕分析模块
from danmaku_analyzer import get_danmaku_analyzer, DanmakuAnalyzer, SentimentType

# 导入自动切片触发模块
try:
    from auto_clip_trigger import (
        get_auto_clip_trigger, load_auto_clip_config_from_yaml,
        AutoClipConfig, AutoClipTrigger, ClipTriggerRequest, ClipTriggerStatus
    )
    AUTO_CLIP_AVAILABLE = True
except ImportError as e:
    logging.warning(f"自动切片模块导入失败: {e}")
    AUTO_CLIP_AVAILABLE = False

# 导入数据导出模块
try:
    from export_manager import ExportManager, ExportFormat, ExportTemplate
    EXPORT_MANAGER_AVAILABLE = True
except ImportError:
    EXPORT_MANAGER_AVAILABLE = False

from flask import Flask, render_template, jsonify, Response, send_file, send_from_directory, session, request
import flask
from flask_compress import Compress
from flask_socketio import SocketIO, emit, join_room, leave_room
import yaml


# ============================================================================
# 自定义异常类 - 统一错误类型
# ============================================================================

class GQMonitorError(Exception):
    """鸽切监控基础异常"""
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code or 'UNKNOWN_ERROR'
        super().__init__(self.message)

class APIError(GQMonitorError):
    """API调用异常"""
    pass

class ConfigError(GQMonitorError):
    """配置错误"""
    pass

class DatabaseError(GQMonitorError):
    """数据库操作异常"""
    pass

class EmailError(GQMonitorError):
    """邮件发送异常"""
    pass

class AuthenticationError(GQMonitorError):
    """认证异常"""
    pass

class CircuitBreakerOpenError(Exception):
    """熔断器开启异常"""
    pass


# ============================================================================
# 统一错误响应格式 - API错误处理装饰器
# ============================================================================

def api_error_handler(f):
    """API错误处理装饰器 - 统一错误响应格式"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            logging.warning(f"数据格式错误 [{f.__name__}]: {e}")
            return jsonify({
                'success': False,
                'error': '数据格式错误',
                'error_code': 'INVALID_DATA',
                'detail': str(e)
            }), 400
        except PermissionError as e:
            logging.warning(f"权限不足 [{f.__name__}]: {e}")
            return jsonify({
                'success': False,
                'error': '权限不足',
                'error_code': 'PERMISSION_DENIED'
            }), 403
        except FileNotFoundError as e:
            logging.warning(f"文件不存在 [{f.__name__}]: {e}")
            return jsonify({
                'success': False,
                'error': '文件不存在',
                'error_code': 'FILE_NOT_FOUND'
            }), 404
        except ConnectionError as e:
            logging.error(f"网络连接失败 [{f.__name__}]: {e}")
            return jsonify({
                'success': False,
                'error': '网络连接失败',
                'error_code': 'CONNECTION_ERROR'
            }), 503
        except GQMonitorError as e:
            logging.error(f"业务异常 [{f.__name__}] [{e.error_code}]: {e.message}")
            return jsonify({
                'success': False,
                'error': e.message,
                'error_code': e.error_code
            }), 400
        except Exception as e:
            logging.error(f"未处理的API异常 [{f.__name__}]: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': '服务器内部错误',
                'error_code': 'INTERNAL_ERROR'
            }), 500
    return wrapper


# ============================================================================
# API速率限制器 - 防止滥用
# ============================================================================

class RateLimiter:
    """滑动窗口速率限制器"""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests = deque()
        self._lock = threading.Lock()

    def is_allowed(self, key: str = 'default') -> Tuple[bool, int]:
        """
        检查是否允许请求

        Returns:
            (是否允许, 剩余请求数)
        """
        current_time = time.time()
        cache_key = f'rate_limit_{key}'

        with self._lock:
            cache = cache_manager.get_cache('rate_limit', ttl=self.window_seconds)
            request_times = cache.get(cache_key)

            if request_times is None:
                request_times = deque()

            # 清理过期请求
            cutoff_time = current_time - self.window_seconds
            while request_times and request_times[0] < cutoff_time:
                request_times.popleft()

            if len(request_times) < self.max_requests:
                request_times.append(current_time)
                cache.set(cache_key, request_times, ttl=self.window_seconds)
                remaining = self.max_requests - len(request_times)
                return True, remaining
            else:
                return False, 0

    def get_wait_time(self, key: str = 'default') -> float:
        """获取需要等待的时间（秒）"""
        cache_key = f'rate_limit_{key}'
        cache = cache_manager.get_cache('rate_limit', ttl=self.window_seconds)
        request_times = cache.get(cache_key)

        if request_times and len(request_times) >= self.max_requests:
            oldest = request_times[0]
            return max(0, self.window_seconds - (time.time() - oldest))
        return 0


# 全局速率限制器
api_rate_limiter = RateLimiter(max_requests=100, window_seconds=60)


def rate_limit(max_per_minute: int = 100):
    """速率限制装饰器"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # 使用IP作为限制键
            client_ip = request.remote_addr
            allowed, remaining = api_rate_limiter.is_allowed(client_ip)

            if not allowed:
                wait_time = api_rate_limiter.get_wait_time(client_ip)
                return jsonify({
                    'success': False,
                    'error': '请求过于频繁',
                    'error_code': 'RATE_LIMITED',
                    'retry_after': int(wait_time) + 1
                }), 429

            response = f(*args, **kwargs)

            # 添加速率限制响应头
            if isinstance(response, tuple):
                json_response, status_code = response
            else:
                json_response = response
                status_code = 200

            if hasattr(json_response, 'headers'):
                json_response.headers['X-RateLimit-Remaining'] = str(remaining)
                json_response.headers['X-RateLimit-Limit'] = str(max_per_minute)

            return json_response, status_code
        return wrapper
    return decorator


# ============================================================================
# API性能监控装饰器
# ============================================================================

def performance_monitor(f):
    """API性能监控装饰器"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = f(*args, **kwargs)
            duration = time.time() - start_time

            # 记录慢查询（超过500ms）
            if duration > 0.5:
                logging.warning(f"慢API [{f.__name__}]: {duration*1000:.1f}ms")

            return result
        except Exception as e:
            duration = time.time() - start_time
            logging.error(f"API [{f.__name__}] 异常: {e}, 耗时: {duration*1000:.1f}ms")
            raise
    return wrapper


# ============================================================================
# 重试装饰器 - 指数退避重试机制
# ============================================================================

def async_retry(max_attempts: int = 3,
                base_delay: float = 1.0,
                max_delay: float = 60.0,
                exponential_base: float = 2.0,
                retriable_exceptions: tuple = (ConnectionError, TimeoutError, Exception)):
    """异步重试装饰器（指数退避）"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except retriable_exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        delay = min(base_delay * (exponential_base ** attempt), max_delay)
                        logging.warning(
                            f"Retry {func.__name__} attempt {attempt + 1}/{max_attempts} "
                            f"failed, waiting {delay:.1f}s: {e}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logging.error(f"{func.__name__} 最终失败 after {max_attempts} attempts: {e}")
            raise last_exception
        return wrapper
    return decorator


def sync_retry(max_attempts: int = 3,
               base_delay: float = 1.0,
               retriable_exceptions: tuple = (ConnectionError, TimeoutError, OSError)):
    """同步重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except retriable_exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        delay = base_delay * (2 ** attempt)
                        logging.warning(f"{func.__name__} retry {attempt + 1}/{max_attempts}, waiting {delay}s: {e}")
                        time.sleep(delay)
            if last_exception:
                raise last_exception
        return wrapper
    return decorator


# ============================================================================
# 熔断器模式 - 防止级联故障
# ============================================================================

class CircuitState(Enum):
    CLOSED = "closed"      # 正常状态
    OPEN = "open"          # 熔断状态
    HALF_OPEN = "half_open"  # 半开状态

class CircuitBreaker:
    """熔断器实现"""

    def __init__(self, name: str, failure_threshold: int = 5,
                 recovery_timeout: int = 60, half_open_max_calls: int = 3):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.failure_count = 0
        self.success_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = None
        self.half_open_calls = 0
        self.lock = threading.Lock()

    def _can_attempt(self) -> bool:
        """检查是否可以尝试调用"""
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and \
               time.time() - self.last_failure_time >= self.recovery_timeout:
                return True
            return False
        if self.state == CircuitState.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls
        return False

    def record_success(self):
        """记录成功调用"""
        with self.lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.half_open_max_calls:
                    logging.info(f"熔断器 [{self.name}] 恢复为关闭状态")
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    def record_failure(self):
        """记录失败调用"""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == CircuitState.HALF_OPEN:
                logging.warning(f"熔断器 [{self.name}] 在半开状态失败，重新开启")
                self.state = CircuitState.OPEN
                self.success_count = 0
            elif self.failure_count >= self.failure_threshold:
                logging.warning(f"熔断器 [{self.name}] 达到失败阈值({self.failure_count}/{self.failure_threshold})，开启熔断")
                self.state = CircuitState.OPEN

    def get_state(self) -> CircuitState:
        """获取当前状态"""
        with self.lock:
            # 检查是否需要从OPEN转为HALF_OPEN
            if self.state == CircuitState.OPEN and self.last_failure_time:
                if time.time() - self.last_failure_time >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                    logging.info(f"熔断器 [{self.name}] 进入半开状态")
            return self.state

    def get_stats(self) -> Dict:
        """获取熔断器统计信息"""
        with self.lock:
            return {
                'name': self.name,
                'state': self.state.value,
                'failure_count': self.failure_count,
                'success_count': self.success_count,
                'failure_threshold': self.failure_threshold,
                'recovery_timeout': self.recovery_timeout,
                'last_failure_time': self.last_failure_time
            }

    async def call_async(self, func, *args, **kwargs):
        """执行带熔断保护的异步函数"""
        if not self._can_attempt():
            raise CircuitBreakerOpenError(f"熔断器 [{self.name}] 已开启，拒绝调用")

        with self.lock:
            if self.state == CircuitState.HALF_OPEN:
                self.half_open_calls += 1

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise

    def call_sync(self, func, *args, **kwargs):
        """执行带熔断保护的同步函数"""
        if not self._can_attempt():
            raise CircuitBreakerOpenError(f"熔断器 [{self.name}] 已开启，拒绝调用")

        with self.lock:
            if self.state == CircuitState.HALF_OPEN:
                self.half_open_calls += 1

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise

# 创建熔断器实例
email_circuit_breaker = CircuitBreaker(
    name="email_sender",
    failure_threshold=3,
    recovery_timeout=300,
    half_open_max_calls=1
)

bilibili_api_breaker = CircuitBreaker(
    name="bilibili_api",
    failure_threshold=5,
    recovery_timeout=60,
    half_open_max_calls=2
)


# ============================================================================
# 错误处理辅助函数
# ============================================================================

def log_error_with_context(context: str, error: Exception, exc_info: bool = True):
    """记录错误日志，包含上下文信息"""
    error_type = type(error).__name__
    error_msg = str(error)

    # 根据异常类型选择日志级别和消息
    if isinstance(error, (ConnectionError, TimeoutError)):
        log_level = logging.WARNING
        prefix = "连接/超时"
    elif isinstance(error, (ValueError, FileNotFoundError)):
        log_level = logging.WARNING
        prefix = "数据/文件"
    elif isinstance(error, GQMonitorError):
        log_level = logging.ERROR
        prefix = f"业务异常[{error.error_code}]"
    else:
        log_level = logging.ERROR
        prefix = "系统异常"

    logging.log(log_level, f"[{context}] {prefix} - {error_type}: {error_msg}", exc_info=exc_info)

def safe_get_dict(data: Dict, *keys, default=None) -> Any:
    """安全获取嵌套字典的值"""
    try:
        result = data
        for key in keys:
            result = result[key]
        return result
    except (KeyError, TypeError, IndexError):
        return default


# 配置缓存变量（兼容旧代码，使用config_manager）
_config_cache = None
_config_last_modified = 0

# 弹幕监控实例（用于获取直播状态）
_danmaku_monitor = None

def get_live_duration():
    """获取当前直播经过时间（用于显示在记录中）"""
    if _danmaku_monitor and _danmaku_monitor.live_start_time:
        current = get_china_timestamp()
        duration_seconds = current - _danmaku_monitor.live_start_time
        hours = int(duration_seconds // 3600)
        minutes = int((duration_seconds % 3600) // 60)
        seconds = int(duration_seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return None

# Flask应用实例
app = Flask(__name__)

# 静态文件哈希缓存 - 存储格式: {路径: (修改时间, 哈希值)}
_static_file_hashes = {}

def _precompute_static_hashes():
    """应用启动时预计算所有静态文件哈希（支持文件变更检测）"""
    import glob
    global _static_file_hashes
    static_dir = app.static_folder
    if not static_dir or not os.path.exists(static_dir):
        return
    
    patterns = ['**/*.css', '**/*.js', '**/*.woff', '**/*.woff2', '**/*.ttf', '**/*.png', '**/*.jpg', '**/*.ico']
    count = 0
    for pattern in patterns:
        for filepath in glob.glob(os.path.join(static_dir, pattern), recursive=True):
            if os.path.isfile(filepath):
                rel_path = os.path.relpath(filepath, static_dir)
                try:
                    mtime = os.path.getmtime(filepath)
                    file_hash = generate_file_hash(filepath)
                    _static_file_hashes[rel_path] = (mtime, file_hash)
                    count += 1
                except Exception:
                    pass
    logging.info(f"静态文件哈希预计算完成: {count} 个文件")

def get_static_file_hash(filename):
    """获取静态文件的哈希值（支持文件变更检测）"""
    global _static_file_hashes
    filepath = os.path.join(app.static_folder, filename)
    
    try:
        if not os.path.exists(filepath):
            return ''
        
        current_mtime = os.path.getmtime(filepath)
        
        # 检查缓存是否存在且有效
        if filename in _static_file_hashes:
            cached_mtime, cached_hash = _static_file_hashes[filename]
            # 如果文件修改时间没有变化，直接返回缓存的哈希
            if abs(current_mtime - cached_mtime) < 0.001:  # 浮点比较容差
                return cached_hash
        
        # 文件已修改或无缓存，重新计算哈希
        file_hash = generate_file_hash(filepath)
        _static_file_hashes[filename] = (current_mtime, file_hash)
        
        # 记录日志以便调试
        logging.debug(f"[Static Hash] 文件已更新，重新计算哈希: {filename}")
        
        return file_hash
    except Exception as e:
        logging.warning(f"获取文件哈希失败 {filename}: {e}")
        return ''

@app.template_filter('static_hashed')
def static_hashed_filter(filename):
    """模板过滤器：为静态文件添加哈希参数"""
    if filename.startswith('/static/'):
        relative_path = filename[8:]
    else:
        relative_path = filename

    file_hash = get_static_file_hash(relative_path)
    if file_hash:
        return f"{filename}?v={file_hash}"
    return filename

# 并发管理器
class ConcurrencyManager:
    """并发连接管理器 - 限制最大并发数和排队机制"""
    def __init__(self, max_concurrent=50):
        self.max_concurrent = max_concurrent
        self.active_connections = set()  # 当前活跃连接 sid
        self.active_users = {}  # 当前活跃用户 {sid: ip}
        self.waiting_queue = queue.Queue()  # 等待队列 (sid, start_time, ip)
        self.lock = threading.Lock()

    def add_connection(self, sid, ip=None):
        """添加连接，返回是否立即进入等待"""
        with self.lock:
            if len(self.active_connections) < self.max_concurrent:
                self.active_connections.add(sid)
                if ip:
                    self.active_users[sid] = ip
                user_count = len(set(self.active_users.values()))
                logging.info(f"✅ 连接 {sid[:8]}... 已加入活跃池 ({len(self.active_connections)}/{self.max_concurrent}, 用户: {user_count})")
                return True, False
            else:
                # 加入等待队列
                self.waiting_queue.put((sid, time.time(), ip))
                position = self.waiting_queue.qsize()
                logging.info(f"⏳ 连接 {sid[:8]}... 进入等待队列 (位置: {position})")
                return False, position

    def remove_connection(self, sid):
        """移除连接"""
        with self.lock:
            user_count = None
            if sid in self.active_connections:
                self.active_connections.remove(sid)
                if sid in self.active_users:
                    del self.active_users[sid]
                user_count = len(set(self.active_users.values()))
                logging.info(f"❌ 连接 {sid[:8]}... 已移除 ({len(self.active_connections)}/{self.max_concurrent}, 用户: {user_count})")

            # 检查等待队列，唤醒下一个
            if not self.waiting_queue.empty() and len(self.active_connections) < self.max_concurrent:
                next_sid, wait_start, ip = self.waiting_queue.get()
                wait_time = time.time() - wait_start
                self.active_connections.add(next_sid)
                if ip:
                    self.active_users[next_sid] = ip
                logging.info(f"🚀 连接 {next_sid[:8]}... 已从等待队列唤醒 (等待时间: {wait_time:.1f}秒)")
                # 通知该连接可以开始
                return next_sid
        return None

    def get_queue_position(self, sid):
        """获取队列位置"""
        with self.lock:
            if sid in self.active_connections:
                return 0  # 已连接
            position = 1
            queue_list = list(self.waiting_queue.queue)
            for item in queue_list:
                if item[0] == sid:
                    return position
                position += 1
            return -1  # 不在队列中

    def get_stats(self):
        """获取统计信息"""
        with self.lock:
            # 计算实际用户数（去重 IP）
            user_count = len(set(self.active_users.values()))
            return {
                'active': user_count,  # 返回实际用户数而不是连接数
                'connections': len(self.active_connections),  # 保留连接数信息
                'waiting': self.waiting_queue.qsize(),
                'max_concurrent': self.max_concurrent
            }

# 初始化并发管理器
MAX_CONCURRENT = get_config("app", "max_concurrent", default=50)
concurrency_manager = ConcurrencyManager(MAX_CONCURRENT)

# 留言板功能配置
CHAT_CONFIG = get_config("chat") or {}
logging.info(f"📋 CHAT_CONFIG loaded: {CHAT_CONFIG}")
CHAT_ENABLE = CHAT_CONFIG.get("enable", True)
MAX_CHAT_MESSAGES = CHAT_CONFIG.get("max_messages", 100)
MAX_MESSAGE_LENGTH = CHAT_CONFIG.get("max_message_length", 500)
MAX_USERNAME_LENGTH = CHAT_CONFIG.get("max_username_length", 20)

# 随机用户名配置
USERNAME_CONFIG = CHAT_CONFIG.get("username", {})
USERNAME_ADJECTIVES = USERNAME_CONFIG.get("adjectives", ["快乐", "开心", "可爱"])
USERNAME_NOUNS = USERNAME_CONFIG.get("nouns", ["鸽子", "小鸟", "猫咪"])

# 敏感词过滤配置
FILTER_CONFIG = CHAT_CONFIG.get("filter", {})
logging.info(f"📋 FILTER_CONFIG loaded: {FILTER_CONFIG}")
FILTER_ENABLE = FILTER_CONFIG.get("enable", True)
SENSITIVE_WORDS = FILTER_CONFIG.get("sensitive_words", [])
FILTER_ACTION = FILTER_CONFIG.get("filter_action", "replace")

# 禁言功能配置
MUTE_CONFIG = CHAT_CONFIG.get("mute", {})
MUTE_ENABLE = MUTE_CONFIG.get("enable", True)
MUTE_DURATION = MUTE_CONFIG.get("mute_duration", 3600)  # 默认1小时

# 输出聊天配置信息
logging.info("=" * 50)
logging.info("📝 留言板功能配置:")
logging.info(f"  - 聊天启用: {CHAT_ENABLE}")
logging.info(f"  - 最大消息数: {MAX_CHAT_MESSAGES}")
logging.info(f"  - 最大消息长度: {MAX_MESSAGE_LENGTH}")
logging.info(f"  - 最大用户名长度: {MAX_USERNAME_LENGTH}")
logging.info(f"  - 敏感词过滤启用: {FILTER_ENABLE}")
logging.info(f"  - 敏感词数量: {len(SENSITIVE_WORDS)}")
logging.info(f"  - 过滤动作: {FILTER_ACTION}")
logging.info(f"  - 禁言功能启用: {MUTE_ENABLE}")
logging.info(f"  - 默认禁言时长: {MUTE_DURATION}秒")
if SENSITIVE_WORDS:
    logging.info(f"  - 前5个敏感词: {SENSITIVE_WORDS[:5]}")
logging.info("=" * 50)

# 初始化WebSocket（使用Flask-SocketIO）- 配置心跳参数防止连接断开
# 注意: 使用 'threading' 模式，Werkzeug 的 write() before start_response 错误可以安全忽略
# 这个错误只发生在 WebSocket 正常断开时，不影响功能
socketio = SocketIO(app,
                    cors_allowed_origins="*",
                    async_mode='threading',
                    ping_timeout=60,  # 客户端等待服务器响应的时间（秒）
                    ping_interval=25,  # 服务器ping客户端的间隔（秒）
                    engineio_logger=False,  # 禁用Engine.IO日志
                    socketio_logger=False,  # 禁用Socket.IO日志
                    always_connect=False,  # 避免在握手失败时自动重连
                    cookie=False,  # 不使用cookie
                    http_compression=False  # 禁用HTTP压缩，避免与Compress冲突
                   )







# WebSocket事件广播函数
def send_websocket_event(event_type, data):
    """向所有WebSocket客户端发送事件"""
    try:
        socketio.emit(event_type, {
            'type': event_type,
            'data': data,
            'timestamp': time.time()
        })
        logging.debug(f"WebSocket广播事件: {event_type}")
    except Exception as e:
        logging.error(f"WebSocket广播失败: {e}")

# 统一事件广播函数（使用SocketIO）
def broadcast_event(event_type, data):
    """向所有连接的客户端广播事件"""
    socketio.emit(event_type, data, namespace='/')

    logging.debug(f"广播事件: {event_type} (WebSocket)")



def broadcast_room_info_update(room_info):
    """广播房间信息更新事件"""
    
    # 检查room_info是否为None或不是字典，如果是则提供默认值
    if room_info is None or not isinstance(room_info, dict):
        room_info = {
            'room_title': '未知直播间',
            'room_id': get_config("bilibili", "room_id", default=22391541),
            'live_status': 0,
            'online': 0,
            'api_source': '获取失败'
        }
    
    # 直接通过WebSocket发送房间信息更新
    broadcast_event('room_info_update', room_info)

# SSE事件队列 - 用于SSE端点
class SSEEventQueue:
    """SSE事件队列 - 支持多客户端订阅"""
    def __init__(self):
        self.clients = []  # 存储响应对象
    
    def add_client(self, response):
        """添加客户端"""
        self.clients.append(response)
        logging.debug(f"SSE客户端连接，当前连接数: {len(self.clients)}")
    
    def remove_client(self, response):
        """移除客户端"""
        if response in self.clients:
            self.clients.remove(response)
        logging.debug(f"SSE客户端断开，当前连接数: {len(self.clients)}")
    
    def broadcast(self, event_type, data):
        """广播事件到所有客户端"""
        for client in self.clients[:]:  # 使用切片避免迭代时修改
            try:
                client.write(f"event: {event_type}\ndata: {json.dumps(data)}\n\n")
                client.flush()
            except Exception as e:
                # 客户端可能已断开，移除它
                logging.debug(f"SSE广播到客户端失败，移除: {e}")
                self.clients.remove(client)

# 全局SSE事件队列
sse_event_queue = SSEEventQueue()

# 设置中国时区（延迟加载）
def get_china_tz():
    """延迟获取中国时区"""
    import pytz
    return pytz.timezone(get_config("app", "timezone", default="Asia/Shanghai"))

def get_china_time() -> str:
    """获取当前中国时间字符串"""
    china_tz = get_china_tz()
    china_time = datetime.now(china_tz)
    return china_time.strftime('%Y-%m-%d %H:%M:%S')

def get_china_timestamp() -> float:
    """获取当前中国时间戳"""
    china_tz = get_china_tz()
    return datetime.now(china_tz).timestamp()

# 配置日志
def setup_logging():
    """配置日志系统 - 按日期分割日志文件"""
    # 创建日志目录
    log_dir = "log"
    os.makedirs(log_dir, exist_ok=True)

    # 获取当前日期作为日志文件名
    china_tz = pytz.timezone(get_config("app", "timezone", default="Asia/Shanghai"))
    current_date = datetime.now(china_tz).strftime('%Y-%m-%d')
    log_file = os.path.join(log_dir, f"geqie-monitor-{current_date}.log")

    # 创建日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 文件处理器 - 记录到文件
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # 控制台处理器 - 输出到控制台
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # 配置根日志记录器
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logging.info(f"📝 日志系统初始化完成")
    logging.info(f"   日志目录: {os.path.abspath(log_dir)}")
    logging.info(f"   当前日志文件: {log_file}")
    logging.info(f"   日志级别: INFO")

    # 返回文件处理器和当前日期用于后续的日志轮换
    return file_handler, current_date

# 初始化日志系统
_file_handler = None

# 配置缓存策略
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 3600  # 静态文件缓存1小时

# 启用 HTTP 压缩（仅压缩文本文件，排除 WebSocket 流量）
compress = Compress()
compress.init_app(app)

# 配置压缩选项：仅压缩文本文件
app.config['COMPRESS_MIMETYPES'] = [
    'text/html',
    'text/css',
    'text/xml',
    'text/plain',
    'application/json',
    'application/javascript',
    'application/x-javascript',
    'text/javascript',
    'application/xhtml+xml',
    'application/xml',
    'font/woff',
    'font/woff2',
    'font/ttf',
    'font/eot'
]

# 优先使用 Brotli 压缩（如果服务器支持），备选 gzip
app.config['COMPRESS_ALGORITHM'] = ['br', 'gzip']
# Brotli 压缩级别 (0-11，推荐 4-5 作为平衡点)
app.config['COMPRESS_BR_LEVEL'] = 4
# gzip 压缩级别 (1-9，越高压缩率越高但CPU消耗越大)
app.config['COMPRESS_LEVEL'] = 6
# 设置最小压缩大小（字节），小于此大小的文件不压缩
app.config['COMPRESS_MIN_SIZE'] = 500
# 设置压缩后的最小大小（字节），如果压缩后文件反而变大则不压缩
app.config['COMPRESS_MIN_SIZE_AFTER_COMPRESSION'] = 200

# 常量定义
CACHE_DURATION = 300  # API缓存时长（秒）
MAX_RECONNECT_ATTEMPTS = 10
RECONNECT_DELAY = 30
HEARTBEAT_TIMEOUT = 300

# 直播间信息缓存
room_info_cache = {
    'data': None,
    'timestamp': 0,
    'cache_duration': CACHE_DURATION  # 使用常量
}

# Flask路由定义
@app.route('/')
def index():
    """主页 - 展示今日鸽切数据"""
    # 从B站API获取实时直播间信息（使用缓存，提升首屏加载速度）
    room_info = get_live_room_info(use_cache=True)

    # 构建streamer_info，与API返回格式保持一致（不包含主播昵称）
    streamer_info = {
        'room_title': room_info.get('room_title', '未知直播间'),
        'room_id': room_info.get('room_id', get_config("bilibili", "room_id", default=22391541))
    }

    # 获取当前日期（YYYY-MM-DD格式）
    current_date = datetime.now(get_china_tz()).strftime('%Y-%m-%d')

    return render_template('index.html',
                          streamer_info=streamer_info,
                          current_date=current_date)

@app.route('/queue_demo')
def queue_demo():
    """并发队列测试页面"""
    return render_template('queue_demo.html')


@app.route('/analysis')
def danmaku_analysis():
    """弹幕分析页面"""
    room_info = get_live_room_info(use_cache=True)
    streamer_info = {
        'room_title': room_info.get('room_title', '未知直播间'),
        'room_id': room_info.get('room_id', get_config("bilibili", "room_id", default=22391541))
    }
    current_date = datetime.now(get_china_tz()).strftime('%Y-%m-%d')
    return render_template('danmaku_analysis.html',
                          streamer_info=streamer_info,
                          current_date=current_date)


@app.route('/api/today')
@api_error_handler
def get_today_data():
    """获取今日数据API"""
    today_data = data_manager.get_today_data()

    # 获取直播经过时间
    live_duration = get_live_duration()
    
    # 格式化时间显示
    china_tz = get_china_tz()
    for item in today_data:
        dt = datetime.fromtimestamp(item['timestamp'], china_tz)
        item['time_display'] = dt.strftime('%H:%M:%S')
        item['datetime_display'] = dt.strftime('%Y-%m-%d %H:%M:%S')
        # 添加直播经过时间
        item['live_duration'] = live_duration if live_duration else dt.strftime('%H:%M:%S')
        if 'email_status' not in item:
            item['email_status'] = 'none'
        if 'email_sent_time' not in item:
            item['email_sent_time'] = None

    return jsonify({
        'success': True,
        'data': today_data,
        'count': len(today_data)
    })

@app.route('/api/stats')
@api_error_handler
def get_stats():
    """获取统计数据API"""
    days = request.args.get('days', 7, type=int)

    # 获取总体统计
    total_stats = data_manager.get_total_stats()

    # 获取每日统计
    daily_stats = data_manager.get_daily_stats(days)

    # 获取最近几天的数据
    recent_data = data_manager.get_recent_days_data(days)

    return jsonify({
        'success': True,
        'total_stats': total_stats,
        'daily_stats': daily_stats,
        'recent_data': recent_data
    })


@app.route('/api/date/<date_str>')
@api_error_handler
def get_date_data(date_str):
    """获取指定日期的数据"""
    date_data = data_manager.get_data_by_date(date_str)

    # 获取直播经过时间
    live_duration = get_live_duration()
    
    # 格式化时间显示
    china_tz = get_china_tz()
    for item in date_data:
        dt = datetime.fromtimestamp(item['timestamp'], china_tz)
        item['time_display'] = dt.strftime('%H:%M:%S')
        item['datetime_display'] = dt.strftime('%Y-%m-%d %H:%M:%S')
        # 添加直播经过时间
        item['live_duration'] = live_duration if live_duration else dt.strftime('%H:%M:%S')

    return jsonify({
        'success': True,
        'data': date_data,
        'count': len(date_data)
    })


@app.route('/api/history')
@api_error_handler
def get_history_data():
    """获取历史数据"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date or not end_date:
        raise ValueError("请提供开始日期和结束日期")

    # 获取日期范围内的所有数据
    all_data = []
    current_date = datetime.strptime(start_date, '%Y-%m-%d')
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')

    while current_date <= end_date_obj:
        date_str = current_date.strftime('%Y-%m-%d')
        date_data = data_manager.get_data_by_date(date_str)

        # 获取直播经过时间
        live_duration = get_live_duration()
        
        # 格式化时间显示并添加日期信息
        china_tz = get_china_tz()
        for item in date_data:
            dt = datetime.fromtimestamp(item['timestamp'], china_tz)
            item['time_display'] = dt.strftime('%H:%M:%S')
            item['datetime_display'] = dt.strftime('%Y-%m-%d %H:%M:%S')
            item['date'] = date_str
            # 添加直播经过时间
            item['live_duration'] = live_duration if live_duration else dt.strftime('%H:%M:%S')

        all_data.extend(date_data)
        current_date += timedelta(days=1)

    # 按时间倒序排列（最新的在前）
    all_data.sort(key=lambda x: x['timestamp'], reverse=True)

    return jsonify({
        'success': True,
        'data': all_data,
        'count': len(all_data)
    })


async def get_live_room_info_async(room_id: int = None) -> dict:
    """异步获取直播间信息 - 使用新HTTP客户端"""
    if room_id is None:
        room_id = get_config("bilibili", "room_id", default=22391541)

    # 使用缓存
    cache = cache_manager.get_cache('room_info', ttl=300)
    cached_data = cache.get(f'room_{room_id}')
    if cached_data:
        return cached_data

    api_urls = get_api_urls(room_id)
    headers = get_bilibili_headers(room_id)

    # 先尝试异步HTTP客户端
    for url in api_urls:
        try:
            data = await http_client.get(url, headers=headers, timeout=15)

            if data is None:
                continue

            if data.get('code', 0) != 0:
                continue

            room_data = data.get('data', {})
            if not room_data or not isinstance(room_data, dict):
                continue

            title = None
            live_status = 0
            api_name = url.split('/')[-1]

            if 'getInfoByRoom' in api_name:
                room_info = room_data.get('room_info')
                if room_info and isinstance(room_info, dict):
                    title = room_info.get('title', '未知标题')
                    live_status = room_info.get('live_status', 0)
            elif 'get_info' in api_name:
                title = room_data.get('title', '未知标题')
                live_status = room_data.get('live_status', 0)
            elif 'room_init' in api_name:
                room_info = room_data.get('room_info')
                if room_info and isinstance(room_info, dict):
                    title = room_info.get('title', '未知标题')
                    live_status = room_info.get('live_status', 0)

            logging.debug(f"get_live_room_info_async异步处理结果: title={title}, room_data={room_data}")
            result = {
                'room_id': room_data.get('room_id', room_id),
                'room_title': title or '未知标题',
                'live_status': live_status,
                'online': room_data.get('online', 0),
                'api_source': f'async_{api_name}'
            }

            cache.set(f'room_{room_id}', result, ttl=300)
            return result

        except Exception as e:
            logging.warning(f"异步API请求失败: {url} - {e}")
    
    # 异步请求全部失败，尝试同步请求
    logging.info("异步HTTP请求失败，尝试同步请求...")
    
    for url in api_urls:
        try:
            response = requests.get(url, headers=dict(headers), timeout=15)
            
            if response.status_code != 200:
                logging.warning(f"同步API状态码 {response.status_code}: {url}")
                continue
                
            data = response.json()
            
            if data.get('code', 0) != 0:
                logging.warning(f"同步API返回错误码 {data.get('code')}: {url}")
                continue

            room_data = data.get('data', {})
            if not room_data or not isinstance(room_data, dict):
                continue

            title = None
            live_status = 0
            api_name = url.split('/')[-1]

            if 'getInfoByRoom' in api_name:
                room_info = room_data.get('room_info')
                if room_info and isinstance(room_info, dict):
                    title = room_info.get('title', '未知标题')
                    live_status = room_info.get('live_status', 0)
            elif 'get_info' in api_name:
                title = room_data.get('title', '未知标题')
                live_status = room_data.get('live_status', 0)
            elif 'room_init' in api_name:
                room_info = room_data.get('room_info')
                if room_info and isinstance(room_info, dict):
                    title = room_info.get('title', '未知标题')
                    live_status = room_info.get('live_status', 0)

            logging.info(f"同步请求成功: title={title}, url={url}")
            result = {
                'room_id': room_data.get('room_id', room_id),
                'room_title': title or '未知标题',
                'live_status': live_status,
                'online': room_data.get('online', 0),
                'api_source': f'sync_{api_name}'
            }

            cache.set(f'room_{room_id}', result, ttl=300)
            return result

        except Exception as e:
            logging.warning(f"同步API请求失败: {url} - {e}")
            continue
    
    # 所有方法都失败，返回fallback
    fallback_data = {
        'room_title': '未知直播间',
        'room_id': room_id,
        'live_status': 0,
        'online': 0,
        'api_source': 'fallback'
    }

    cache.set(f'room_{room_id}', fallback_data, ttl=60)
    return fallback_data


def get_live_room_info(room_id: int = None, use_cache: bool = True) -> dict:
    """从B站API获取实时直播间信息 - 同步版本（使用http_client）"""
    import asyncio

    if room_id is None:
        room_id = get_config("bilibili", "room_id", default=22391541)

    # 检查缓存
    if use_cache:
        cache = cache_manager.get_cache('room_info', ttl=300)
        cached_data = cache.get(f'room_{room_id}')
        if cached_data:
            return cached_data

    # 创建新的事件循环来运行异步函数
    try:
        # 优先使用现有事件循环
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 没有运行中的事件循环，创建一个新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            should_close = True
        else:
            should_close = False

        try:
            result = loop.run_until_complete(get_live_room_info_async(room_id))
            logging.debug(f"get_live_room_info返回结果: {result}")
            return result
        finally:
            # 只在是我们创建的新循环时才关闭
            if should_close and not loop.is_closed():
                loop.close()
    except RuntimeError as e:
        logging.warning(f"获取直播间信息时事件循环错误: {e}")
        # 返回默认值
        return {
            'room_title': '未知直播间',
            'room_id': room_id,
            'live_status': 0,
            'online': 0,
            'api_source': 'error_fallback'
        }

@app.route('/api/config')
@api_error_handler
def get_config_api():
    """获取配置文件API"""
    config = load_config()

    # 过滤敏感信息
    safe_config = {}
    for section, content in config.items():
        if section == 'email':
            # 只保留邮箱配置的基本信息，隐藏密码等敏感信息
            safe_email = {}
            if 'smtp_server' in content:
                safe_email['smtp_server'] = content['smtp_server']
            if 'smtp_port' in content:
                safe_email['smtp_port'] = content['smtp_port']
            if 'sender' in content:
                safe_email['sender'] = content['sender']
            if 'receiver' in content:
                safe_email['receiver'] = content['receiver']
            safe_config[section] = safe_email
        elif section == 'credential':
            # 隐藏登录凭证的敏感信息
            safe_credential = {'enable': content.get('enable', False)}
            safe_config[section] = safe_credential
        elif section == 'app':
            # 过滤管理员密码
            safe_app = {}
            for key, value in content.items():
                if key != 'admin_password':
                    safe_app[key] = value
            safe_config[section] = safe_app
        else:
            safe_config[section] = content

    return jsonify({
        'success': True,
        'config': safe_config,
        'timestamp': time.time()
    })


@app.route('/api/verify_password', methods=['POST'])
@api_error_handler
def verify_password():
    """验证管理员密码"""
    data = request.json
    password = data.get('password')

    if not password:
        raise ValueError('密码不能为空')

    # 验证密码
    admin_password = get_config("app", "admin_password")
    if password == admin_password:
        return jsonify({
            'success': True, 'message': '密码验证成功'
        })
    else:
        raise AuthenticationError('密码错误', error_code='INVALID_PASSWORD')

@app.route('/api/room_info')
@api_error_handler
def get_room_info():
    """获取实时直播间信息（使用缓存）"""
    # 检查是否有强制刷新参数
    force_refresh = flask.request.args.get('force_refresh', '').lower() == 'true'
    
    # 从B站API获取实时直播间信息（使用缓存或强制刷新）
    room_info = get_live_room_info(use_cache=not force_refresh)

    return jsonify({
        'success': True,
        'room_info': room_info,
        'from_cache': not force_refresh,
        'force_refresh_used': force_refresh
    })

@app.route('/api/room_info/refresh')
@api_error_handler
def refresh_room_info():
    """强制刷新直播间信息（不使用缓存）"""
    # 强制从B站API获取最新直播间信息
    room_info = get_live_room_info(use_cache=False)

    return jsonify({
        'success': True,
        'room_info': room_info,
        'from_cache': False,
        'message': '已从B站API获取最新数据'
    })


# ============================================================================
# 多房间监控 API 接口
# ============================================================================

@app.route('/api/multi-room/config')
@api_error_handler
def get_multi_room_config_api():
    """获取多房间监控配置"""
    config = {
        'enabled': is_multi_room_enabled(),
        'rooms': get_multi_room_config()
    }
    
    return jsonify({
        'success': True,
        'config': config
    })


@app.route('/api/multi-room/status')
@api_error_handler
def get_multi_room_status():
    """获取所有监控房间的实时状态"""
    manager = get_multi_room_manager()
    
    # 获取实时监控状态
    live_status = manager.get_all_rooms_info()
    
    # 获取数据库中的历史统计
    db_stats = data_manager.get_all_rooms_stats()
    
    # 合并数据
    result = {
        'global_stats': manager.get_global_stats(),
        'rooms': [],
        'is_multi_room_enabled': is_multi_room_enabled()
    }
    
    # 创建数据库统计的字典以便快速查找
    db_stats_dict = {s['room_id']: s for s in db_stats}
    
    # 处理所有房间（包括配置中但可能没有数据的房间）
    config_rooms = get_multi_room_config()
    
    for room_config in config_rooms:
        room_id = room_config['room_id']
        
        # 获取实时状态
        live_info = None
        for info in live_status:
            if info['room_id'] == room_id:
                live_info = info
                break
        
        # 获取数据库统计
        db_stat = db_stats_dict.get(room_id, {})
        
        # 构建房间信息
        room_info = {
            'room_id': room_id,
            'nickname': room_config.get('nickname', f"直播间 {room_id}"),
            'enabled': room_config.get('enabled', True),
            'live_status': live_info.get('live_status', 0) if live_info else 0,
            'is_live': live_info.get('is_live', False) if live_info else False,
            'is_monitoring': live_info.get('is_monitoring', False) if live_info else False,
            'online': live_info.get('online', 0) if live_info else 0,
            'room_title': live_info.get('title') if live_info else db_stat.get('room_title'),
            'keyword_count': live_info.get('keyword_count', 0) if live_info else 0,
            'total_danmaku': live_info.get('total_danmaku', 0) if live_info else 0,
            'db_total_count': db_stat.get('total_count', 0),
            'db_today_count': db_stat.get('today_count', 0),
            'db_week_count': db_stat.get('week_count', 0)
        }
        
        result['rooms'].append(room_info)
    
    return jsonify({
        'success': True,
        'data': result
    })


@app.route('/api/multi-room/comparison')
@api_error_handler
def get_room_comparison_data():
    """获取房间对比数据（用于可视化对比）"""
    days = request.args.get('days', 7, type=int)
    
    # 获取对比数据
    comparison_data = data_manager.get_room_comparison(days=days)
    
    # 获取关键词频率
    keyword_freq = data_manager.get_keyword_frequency_by_room(days=days)
    
    return jsonify({
        'success': True,
        'comparison_data': comparison_data,
        'keyword_frequency': keyword_freq,
        'days': days
    })


@app.route('/api/multi-room/<int:room_id>/stats')
@api_error_handler
def get_room_detail_stats(room_id):
    """获取指定房间的详细统计数据"""
    days = request.args.get('days', 7, type=int)
    
    # 获取房间统计
    room_stats = data_manager.get_room_stats(room_id, days=days)
    
    # 获取房间数据
    room_data = data_manager.get_data_by_room(room_id, days=days)
    
    # 获取该房间的关键词频率
    keyword_freq = data_manager.get_keyword_frequency_by_room(room_id=room_id, days=days)
    
    return jsonify({
        'success': True,
        'room_stats': room_stats,
        'room_data': room_data,
        'keyword_frequency': keyword_freq,
        'days': days
    })


@app.route('/api/multi-room/<int:room_id>/today')
@api_error_handler
def get_room_today_data(room_id):
    """获取指定房间的今日数据"""
    today_data = data_manager.get_data_by_room_and_date(room_id)
    
    # 格式化时间显示
    china_tz = get_china_tz()
    for item in today_data:
        dt = datetime.fromtimestamp(item['timestamp'], china_tz)
        item['time_display'] = dt.strftime('%H:%M:%S')
        item['datetime_display'] = dt.strftime('%Y-%m-%d %H:%M:%S')
    
    return jsonify({
        'success': True,
        'data': today_data,
        'count': len(today_data)
    })


@app.route('/api/multi-room/rooms-with-data')
@api_error_handler
def get_rooms_with_data_api():
    """获取所有有数据记录的房间列表"""
    rooms = data_manager.get_rooms_with_data()
    
    return jsonify({
        'success': True,
        'rooms': rooms
    })


@app.route('/api/multi-room/keyword-frequency')
@api_error_handler
def get_keyword_frequency_api():
    """获取关键词频率统计（全局或按房间）"""
    room_id = request.args.get('room_id', None, type=int)
    days = request.args.get('days', 7, type=int)
    
    result = data_manager.get_keyword_frequency_by_room(room_id=room_id, days=days)
    
    return jsonify({
        'success': True,
        'data': result,
        'room_id': room_id,
        'days': days
    })


@app.route('/api/announcement')
@api_error_handler
def get_announcement():
    """获取公告信息"""
    config = load_config()
    logging.debug(f"Loaded config: {type(config)}")
    announcement_config = config.get('announcement', {})
    logging.debug(f"Announcement config: {announcement_config}")
    return jsonify({
        'success': True,
        'announcement': {
            'enable': announcement_config.get('enable', False),
            'title': announcement_config.get('title', ''),
            'content': announcement_config.get('content', ''),
            'show_once': announcement_config.get('show_once', True)
        }
    })


@app.route('/api/record/update', methods=['POST'])
@api_error_handler
def update_record():
    """更新记录的切片地址或跳过原因"""
    data = request.json
    record_id = data.get('id')
    slice_url = data.get('slice_url')
    skip_reason = data.get('skip_reason')
    password = data.get('password')

    if not record_id:
        raise ValueError('记录ID不能为空')

    # 验证管理员密码
    admin_password = get_config("app", "admin_password")
    if not password or password != admin_password:
        raise AuthenticationError('密码错误', error_code='INVALID_PASSWORD')

    data_manager.update_record(record_id, slice_url, skip_reason)

    return jsonify({
        'success': True,
        'message': '更新成功'
    })

@app.route('/api/record/update_email_status', methods=['POST'])
@api_error_handler
def update_email_status():
    """更新记录的邮件发送状态"""
    data = request.json
    record_id = data.get('id')
    status = data.get('status')  # 'success' 或 'failed'

    if not record_id:
        raise ValueError('记录ID不能为空')

    if status not in ('success', 'failed'):
        raise ValueError('状态值无效，必须是 success 或 failed')

    data_manager.update_email_status(record_id, status)

    return jsonify({
        'success': True,
        'message': '邮件状态更新成功'
    })


@app.route('/api/record/<int:record_id>')
@api_error_handler
def get_record(record_id):
    """获取单个记录"""
    record = data_manager.get_record_by_id(record_id)

    if not record:
        raise FileNotFoundError(f"记录 {record_id} 不存在")

    # 获取直播经过时间
    live_duration = get_live_duration()
    
    # 格式化时间显示
    china_tz = get_china_tz()
    dt = datetime.fromtimestamp(record['timestamp'], china_tz)
    record['time_display'] = dt.strftime('%H:%M:%S')
    record['datetime_display'] = dt.strftime('%Y-%m-%d %H:%M:%S')
    # 添加直播经过时间
    record['live_duration'] = live_duration if live_duration else dt.strftime('%H:%M:%S')

    # 确保有邮件状态字段
    if 'email_status' not in record:
        record['email_status'] = 'none'
    if 'email_sent_time' not in record:
        record['email_sent_time'] = None

    return jsonify({
        'success': True,
        'record': record
    })

@app.route('/api/record/delete', methods=['POST'])
@api_error_handler
def delete_record():
    """删除记录"""
    data = request.json
    record_id = data.get('id')
    password = data.get('password')

    if not record_id:
        raise ValueError('记录ID不能为空')

    # 验证管理员密码
    admin_password = get_config("app", "admin_password")
    if not password or password != admin_password:
        raise AuthenticationError('密码错误', error_code='INVALID_PASSWORD')

    data_manager.delete_record(record_id)

    return jsonify({
        'success': True,
        'message': '删除成功'
    })

@app.route('/api/record/rate', methods=['POST'])
@api_error_handler
def rate_record():
    """对记录进行评分"""
    data = request.json
    record_id = data.get('id')
    rating = data.get('rating')
    rating_comment = data.get('comment', '')

    if not record_id:
        raise ValueError('记录ID不能为空')
    
    if rating is None:
        raise ValueError('评分为空')
    
    rating = int(rating)
    if rating < 1 or rating > 5:
        raise ValueError('评分必须在 1-5 之间')

    record = data_manager.get_record_by_id(record_id)
    if not record:
        raise FileNotFoundError(f"记录 {record_id} 不存在")

    data_manager.update_rating(record_id, rating, rating_comment)
    logging.info(f"⭐ 记录 {record_id} 已被评分: {rating} 星")

    def send_rating_email_async():
        """异步发送评分邮件通知"""
        try:
            email_config = get_config("email")
            if not email_config or not email_config.get('sender'):
                logging.warning("⚠️ 邮件配置不完整，跳过评分邮件发送")
                return
            
            email_notifier = EmailNotifier(email_config)
            china_time = get_china_time()
            
            username = record.get('username', '未知用户')
            content = record.get('content', '无内容')
            room_title = record.get('room_title', '未知直播间')
            
            stars = '⭐' * rating + '☆' * (5 - rating)
            
            subject = f"【评分通知】记录 {record_id} 收到新评分"
            
            email_content = f"""收到新的评分通知！

记录ID: {record_id}
用户: {username}
直播间: {room_title}
弹幕内容: {content}

评分: {stars} ({rating}/5 星)
{"评论: " + rating_comment if rating_comment else ""}
评分时间: {china_time}
"""
            
            if email_notifier.send_email(subject, email_content):
                data_manager.update_rating_email_status(record_id, 'success')
                logging.info(f"📧 评分邮件发送成功: 记录 {record_id}")
            else:
                data_manager.update_rating_email_status(record_id, 'failed')
                logging.warning(f"⚠️ 评分邮件发送失败: 记录 {record_id}")
                
        except Exception as e:
            logging.error(f"❌ 发送评分邮件时出错: {e}")
            data_manager.update_rating_email_status(record_id, 'failed')

    email_thread = threading.Thread(target=send_rating_email_async)
    email_thread.start()

    return jsonify({
        'success': True,
        'message': f'评分成功: {rating} 星'
    })


# ============================================================================
# 数据导出 API
# ============================================================================

@app.route('/api/export/data')
@api_error_handler
def export_data():
    """数据导出 API - 支持 Excel、CSV、PDF 格式"""
    
    if not EXPORT_MANAGER_AVAILABLE:
        raise GQMonitorError(
            "数据导出功能未启用，请安装依赖: pip install openpyxl reportlab",
            error_code='EXPORT_NOT_AVAILABLE'
        )
    
    # 获取参数
    format_type = request.args.get('format', 'excel').lower()
    rooms_param = request.args.get('rooms', '')
    date_range = request.args.get('date_range', 'all')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    template = request.args.get('template', 'standard')
    
    # 解析房间列表
    rooms = []
    if rooms_param:
        try:
            rooms = [int(r.strip()) for r in rooms_param.split(',') if r.strip()]
        except ValueError:
            raise ValueError('房间ID格式无效')
    
    if not rooms:
        # 如果没有指定房间，使用配置中的默认房间或所有启用的房间
        if is_multi_room_enabled():
            enabled_rooms = get_enabled_rooms()
            rooms = [r['room_id'] for r in enabled_rooms]
        else:
            default_room = get_config("bilibili", "room_id", default=22391541)
            rooms = [default_room]
    
    # 确定格式枚举
    try:
        export_format = ExportFormat(format_type)
    except ValueError:
        export_format = ExportFormat.EXCEL
    
    # 确定模板枚举
    try:
        export_template = ExportTemplate(template)
    except ValueError:
        export_template = ExportTemplate.STANDARD
    
    # 确定指标
    metrics = {
        'basic': request.args.get('metric_basic', 'true') == 'true',
        'rating': request.args.get('metric_rating', 'true') == 'true',
        'room': request.args.get('metric_room', 'true') == 'true',
        'charts': request.args.get('metric_charts', 'true') == 'true',
        'stats': request.args.get('metric_stats', 'true') == 'true'
    }
    
    # 创建导出管理器
    export_mgr = ExportManager(data_manager)
    
    # 获取要导出的数据
    export_data_list = export_mgr.get_export_data(
        rooms=rooms,
        date_range=date_range,
        start_date=start_date,
        end_date=end_date,
        metrics=metrics
    )
    
    # 生成文件名
    filename = export_mgr.generate_filename(export_format, rooms)
    
    # 根据格式导出
    if export_format == ExportFormat.CSV:
        data_bytes = export_mgr.export_to_csv(export_data_list)
        mimetype = 'text/csv; charset=utf-8-sig'
    elif export_format == ExportFormat.EXCEL:
        data_bytes = export_mgr.export_to_excel(export_data_list, sheet_name="鸽切监控数据")
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    elif export_format == ExportFormat.PDF:
        # 准备统计数据
        stats_data = {
            'total_count': len(export_data_list),
            'date_range': date_range,
            'room_count': len(rooms)
        }
        
        # 准备图表数据（简单示例）
        chart_data = None
        if metrics.get('charts'):
            try:
                # 尝试获取房间对比数据作为图表数据
                if is_multi_room_enabled():
                    manager = get_multi_room_manager()
                    comparison = manager.get_room_comparison()
                    if comparison:
                        chart_data = {
                            'bar_data': {
                                'values': [c.get('keyword_count', 0) for c in comparison],
                                'labels': [c.get('nickname', str(c.get('room_id'))) for c in comparison]
                            }
                        }
            except Exception as e:
                logging.warning(f"生成图表数据时出错: {e}")
        
        data_bytes = export_mgr.export_to_pdf(
            data=export_data_list,
            template=export_template,
            report_title="鸽切监控数据导出报告",
            stats_data=stats_data,
            chart_data=chart_data
        )
        mimetype = 'application/pdf'
    else:
        # 默认使用 Excel
        data_bytes = export_mgr.export_to_excel(export_data_list)
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    if not data_bytes:
        raise GQMonitorError("没有数据可导出", error_code='NO_DATA_TO_EXPORT')
    
    # 创建 BytesIO 并返回文件
    from io import BytesIO
    output = BytesIO(data_bytes)
    output.seek(0)
    
    return send_file(
        output,
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename
    )


# ============================================================================
# 多房间监控页面路由
# ============================================================================

@app.route('/multi-room')
def multi_room_page():
    """多房间监控页面"""
    return render_template('multi_room.html')


@app.route('/api/music/list')
@api_error_handler
def get_music_list():
    """获取音乐文件列表"""
    # 使用相对于项目目录的song文件夹作为默认路径
    default_music_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'song')
    music_dir = get_config("app", "music_dir", default=default_music_dir)

    # 如果路径不存在，尝试使用默认路径
    if not os.path.exists(music_dir):
        music_dir = default_music_dir

    # 添加调试日志
    logging.info(f"[Music API] music_dir: {music_dir}")
    logging.info(f"[Music API] exists: {os.path.exists(music_dir)}")

    # 确保目录存在
    os.makedirs(music_dir, exist_ok=True)

    # 支持的音乐文件格式
    music_extensions = ['*.mp3', '*.wav', '*.ogg', '*.m4a', '*.flac', '*.aac', '*.wma']
    music_files = []

    for ext in music_extensions:
        pattern = os.path.join(music_dir, ext)
        files = glob.glob(pattern)
        music_files.extend(files)

    # 只返回文件名，去掉路径
    music_files = [os.path.basename(f) for f in music_files]

    logging.info(f"[Music API] total: {len(music_files)} files")

    return jsonify({
        'success': True,
        'music_files': music_files
    })

@app.route('/api/music/play/<filename>')
@api_error_handler
def play_music(filename):
    """播放音乐文件 - 安全版本"""
    # 验证文件名安全性
    if not filename or '..' in filename or filename.startswith('/'):
        raise ValueError('无效的文件名')

    # 使用相对于项目目录的song文件夹作为默认路径
    default_music_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'song')
    music_dir = get_config("app", "music_dir", default=default_music_dir)

    # 如果路径不存在，尝试使用默认路径
    if not os.path.exists(music_dir):
        music_dir = default_music_dir

    # 使用安全的路径拼接
    file_path = os.path.join(music_dir, filename)

    # 规范路径并验证是否在允许的目录内
    file_path = os.path.normpath(file_path)
    if not file_path.startswith(os.path.abspath(music_dir)):
        raise PermissionError('文件路径无效')

    # 检查文件是否存在且是普通文件
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        raise FileNotFoundError(f'文件不存在: {filename}')

    # 检查文件扩展名
    allowed_extensions = {'.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac', '.wma'}
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise ValueError('不支持的文件格式')

    # 安全发送文件
    return send_file(
        file_path,
        as_attachment=False,
        conditional=True  # 支持条件请求
    )

# SSE事件端点 - 支持EventSource
@app.route('/api/events')
def sse_events():
    """SSE事件流端点 - 用于实时推送房间信息和直播状态"""
    import flask
    from flask import Response, stream_with_context
    
    def generate():
        # 生成初始连接确认
        yield f"event: connected\ndata: {{'status': 'connected', 'timestamp': {int(time.time())}}}\n\n"
        
        # 定期发送心跳
        while True:
            try:
                yield f"event: heartbeat\ndata: {{'timestamp': {int(time.time())}}}\n\n"
                time.sleep(30)  # 每30秒心跳
            except GeneratorExit:
                break
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'  # 禁用nginx缓冲
        }
    )


# 健康检查端点 - 增强版
@app.route('/health')
def health_check():
    """详细健康检查端点，用于Docker健康检查和监控"""
    health_status = {
        'status': 'healthy',
        'timestamp': time.time(),
        'checks': {}
    }

    # 1. 数据库检查
    try:
        db_result = data_manager.test_connection()
        health_status['checks']['database'] = {
            'status': 'healthy' if db_result.get('status') == 'connected' else 'unhealthy',
            'details': db_result
        }
        if db_result.get('status') != 'connected':
            health_status['status'] = 'degraded'
    except Exception as e:
        health_status['checks']['database'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_status['status'] = 'unhealthy'

    # 2. 邮件服务配置检查
    try:
        email_config = get_config("email")
        if email_config.get('sender'):
            health_status['checks']['email'] = {
                'status': 'configured', 'sender': email_config.get('sender')[:3] + '***'  # 脱敏
            }
        else:
            health_status['checks']['email'] = {
                'status': 'not_configured'
            }
    except Exception as e:
        health_status['checks']['email'] = {
            'status': 'error', 'error': str(e)
        }

    # 3. 熔断器状态检查
    try:
        email_stats = email_circuit_breaker.get_stats()
        api_stats = bilibili_api_breaker.get_stats()
        
        # 判断是否有熔断器处于开启状态
        breakers_healthy = email_stats.get('state') != 'open' and api_stats.get('state') != 'open'
        
        health_status['checks']['circuit_breakers'] = {
            'status': 'healthy' if breakers_healthy else 'open',  # 只有熔断器开启才是不健康
            'email': email_stats,
            'bilibili_api': api_stats
        }
    except Exception as e:
        health_status['checks']['circuit_breakers'] = {
            'status': 'error',
            'error': str(e)
        }

    # 4. 磁盘空间检查
    try:
        import shutil
        disk_usage = shutil.disk_usage('/')
        disk_percent = (disk_usage.used / disk_usage.total) * 100
        health_status['checks']['disk'] = {
            'status': 'healthy' if disk_percent < 90 else 'low',
            'usage_percent': round(disk_percent, 1),
            'free_gb': round(disk_usage.free / (1024**3), 2)
        }
        if disk_percent >= 90:
            health_status['status'] = 'degraded'
    except Exception as e:
        health_status['checks']['disk'] = {
            'status': 'unknown',
            'error': str(e)
        }

    # 5. 配置文件检查
    try:
        config = load_config()
        health_status['checks']['config'] = {
            'status': 'loaded',
            'sections': list(config.keys())
        }
    except Exception as e:
        health_status['checks']['config'] = {
            'status': 'error',
            'error': str(e)
        }
        health_status['status'] = 'degraded'

    # 6. 缓存系统检查
    try:
        cache_stats = cache_manager.get_stats()
        total_hits = sum(s.get('hits', 0) for s in cache_stats.values())
        total_misses = sum(s.get('misses', 0) for s in cache_stats.values())
        total = total_hits + total_misses
        health_status['checks']['cache'] = {
            'status': 'healthy',
            'namespaces': len(cache_stats),
            'total_hits': total_hits,
            'total_misses': total_misses,
            'hit_rate': round(total_hits / total, 2) if total > 0 else 0
        }
    except Exception as e:
        health_status['checks']['cache'] = {
            'status': 'error',
            'error': str(e)
        }

    # 7. HTTP客户端检查
    try:
        http_stats = http_client.get_stats()
        health_status['checks']['http_client'] = {
            'status': 'healthy' if http_stats.get('session_active') else 'inactive',
            'session_active': http_stats.get('session_active'),
            'error_count': http_stats.get('error_count', 0)
        }
    except Exception as e:
        health_status['checks']['http_client'] = {
            'status': 'error',
            'error': str(e)
        }

    # 确定整体状态
    unhealthy_checks = [
        k for k, v in health_status['checks'].items()
        if v.get('status') not in ['healthy', 'configured', 'loaded', 'not_configured']
    ]

    if unhealthy_checks:
        health_status['unhealthy_components'] = unhealthy_checks
        if health_status['status'] == 'healthy':
            health_status['status'] = 'degraded'

    return jsonify(health_status), 200 if health_status['status'] != 'unhealthy' else 503


import hashlib
import os

def generate_file_hash(filepath):
    """生成文件内容的 SHA256 哈希值 - 分块读取优化大文件"""
    sha256 = hashlib.sha256()
    chunk_size = 65536  # 64KB 分块读取

    try:
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()[:8]  # 取前8位作为文件版本
    except Exception as e:
        logging.warning(f"计算文件哈希失败: {filepath} - {e}")
        # 失败时返回基于mtime的哈希
        try:
            mtime = int(os.path.getmtime(filepath))
            return hashlib.md5(str(mtime).encode()).hexdigest()[:8]
        except Exception:
            return str(int(time.time()))[:8]

# 自定义静态文件处理器，添加缓存头（使用预计算的哈希）
@app.route('/static/<path:filename>')
def static_files(filename):
    response = send_from_directory(app.static_folder, filename)

    # 使用预计算的哈希（从缓存获取，不重复计算）
    file_hash = get_static_file_hash(filename)
    if file_hash:
        response.headers['ETag'] = f'"{file_hash}"'
    response.headers['Vary'] = 'Accept-Encoding'

    # 根据文件类型设置缓存策略
    if filename.endswith('.css'):
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    elif filename.endswith('.js'):
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    elif filename.endswith(('.woff', '.woff2', '.ttf', '.otf')):
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    elif filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.ico', '.webp', '.svg')):
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    else:
        response.headers['Cache-Control'] = 'public, max-age=86400'

    return response

# 新增API：获取服务器并发状态
@app.route('/api/concurrency/status')
@api_error_handler
def get_concurrency_status():
    """获取当前并发状态"""
    stats = concurrency_manager.get_stats()
    return jsonify({
        'success': True,
        'stats': stats,
        'message': f'当前 {stats["active"]}/{stats["max_concurrent"]} 人在线，{stats["waiting"]} 人在等待'
    })

# 新增API：获取缓存系统状态
@app.route('/api/cache/stats')
@api_error_handler
def get_cache_stats():
    """获取缓存系统统计"""
    cache_stats = cache_manager.get_stats()
    http_stats = http_client.get_stats()

    return jsonify({
        'success': True,
        'cache': cache_stats,
        'http_client': http_stats
    })

# 新增API：清空缓存（需管理员密码）
@app.route('/api/cache/clear', methods=['POST'])
@api_error_handler
def clear_cache():
    """清空所有缓存"""
    data = request.json
    password = data.get('password')

    # 验证管理员密码
    admin_password = get_config("app", "admin_password")
    if not password or password != admin_password:
        raise AuthenticationError('密码错误', error_code='INVALID_PASSWORD')

    cache_manager.clear_all()
    logging.info("管理员清空了所有缓存")

    return jsonify({
        'success': True,
        'message': '缓存已清空'
    })

# 聊天配置API - 注意：敏感词列表不应暴露给客户端
@app.route('/api/chat/config')
@api_error_handler
def get_chat_config():
    """获取聊天配置"""
    return jsonify({
        'success': True,
        'config': {
            'enable': CHAT_ENABLE,
            'max_messages': MAX_CHAT_MESSAGES,
            'max_message_length': MAX_MESSAGE_LENGTH,
            'max_username_length': MAX_USERNAME_LENGTH,
            'username': {
                'adjectives': USERNAME_ADJECTIVES,
                'nouns': USERNAME_NOUNS
            },
            'filter': {
                'enable': FILTER_ENABLE,
                # 敏感词列表不返回，保护数据安全
                'sensitive_words_count': len(SENSITIVE_WORDS),
                'filter_action': FILTER_ACTION
            },
            'mute': {
                'enable': MUTE_ENABLE,
                'mute_duration': MUTE_DURATION
            }
        }
    })

@app.route('/api/music/config')
@api_error_handler
def get_music_config():
    """获取音乐播放器配置"""
    config = load_config()
    music_config = config.get('app', {}).get('music', {})
    return jsonify({
        'success': True,
        'config': {
            'preload_count': music_config.get('preload_count', 3)
        }
    })


@app.route('/api/music/import', methods=['POST'])
@api_error_handler
def import_music_playlist():
    """导入歌单 - 从QQ音乐、网易云音乐等平台导入歌单"""
    data = request.get_json()
    
    if not data:
        raise ValueError('请求数据为空')
    
    platform = data.get('platform')
    url_or_id = data.get('url_or_id')
    
    if not platform:
        raise ValueError('请选择平台')
    if not url_or_id:
        raise ValueError('请输入歌单链接或ID')
    
    # 支持的平台
    supported_platforms = ['qqmusic', 'netease']
    if platform not in supported_platforms:
        raise ValueError(f'不支持的平台: {platform}')
    
    # 解析歌单ID
    playlist_id = parse_playlist_id(platform, url_or_id)
    
    if not playlist_id:
        raise ValueError('无法解析歌单ID，请检查链接格式')
    
    try:
        # 获取歌单信息
        playlist_info = get_playlist_info(platform, playlist_id)
        
        if not playlist_info or not playlist_info.get('songs'):
            raise ValueError('无法获取歌单信息')
        
        # 返回歌单信息，实际下载需要额外处理
        # 这里我们只返回歌单信息，不进行实际下载
        # 实际下载可以在后续版本中实现
        songs = playlist_info.get('songs', [])
        
        return jsonify({
            'success': True,
            'playlist_name': playlist_info.get('name', '未知歌单'),
            'songs': songs,
            'total': len(songs),
            'message': f'成功获取歌单信息，共 {len(songs)} 首歌曲'
        })
        
    except Exception as e:
        logging.error(f'[Music Import] 导入歌单失败: {e}')
        logging.error(traceback.format_exc())
        raise ValueError(f'导入歌单失败: {str(e)}')


def parse_playlist_id(platform: str, url_or_id: str) -> Optional[str]:
    """
    从链接或ID中解析歌单ID
    
    Args:
        platform: 平台名称 (qqmusic, netease)
        url_or_id: 歌单链接或ID
    
    Returns:
        歌单ID，如果无法解析返回None
    """
    # 如果已经是纯数字ID，直接返回
    if url_or_id.isdigit():
        return url_or_id
    
    # QQ音乐链接格式示例:
    # https://y.qq.com/n/ryqq/playlist/1234567890
    # https://y.qq.com/n/portal/playlist_detail.html?id=1234567890
    if platform == 'qqmusic':
        # 匹配数字ID
        patterns = [
            r'playlist/(\d+)',
            r'id=(\d+)',
            r'disstid=(\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)
        
        return url_or_id if url_or_id.isdigit() else None
    
    # 网易云音乐链接格式示例:
    # https://music.163.com/#/playlist?id=1234567890
    # https://music.163.com/playlist?id=1234567890
    elif platform == 'netease':
        patterns = [
            r'playlist\?id=(\d+)',
            r'playlist/(\d+)',
            r'id=(\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)
        
        return url_or_id if url_or_id.isdigit() else None
    
    return None


def get_playlist_info(platform: str, playlist_id: str) -> Optional[Dict]:
    """
    获取歌单信息（简化版 - 演示用途）
    
    注意：此函数是简化版本，实际生产环境需要：
    1. 处理复杂的API调用和签名
    2. 处理反爬机制
    3. 可能需要付费API
    
    Args:
        platform: 平台名称
        playlist_id: 歌单ID
    
    Returns:
        歌单信息字典
    """
    logging.info(f'[Music Import] 获取歌单信息: platform={platform}, id={playlist_id}')
    
    # 由于真实的QQ音乐和网易云音乐API需要复杂的签名和认证
    # 这里提供一个简化的框架，实际实现需要处理：
    # 1. QQ音乐: 需要处理sign、g_tk等参数
    # 2. 网易云音乐: 需要处理加密的API参数
    
    # 返回示例数据（演示用途）
    # 实际项目中应该调用真实的API
    
    # 由于实际的音乐平台API实现比较复杂，这里返回一个示例
    # 生产环境建议使用专门的音乐API服务或者第三方库
    # 如: pyncm (网易云音乐), qq-music-api (QQ音乐)
    
    logging.warning(f'[Music Import] 注意：当前版本仅返回示例数据，实际音乐平台API需要完整实现')
    
    # 返回一个简化的示例结构
    return {
        'name': f'{platform} 歌单示例',
        'id': playlist_id,
        'songs': [
            {
                'id': '1',
                'name': '示例歌曲1',
                'artist': '艺术家1',
                'album': '专辑1',
                'duration': 240
            },
            {
                'id': '2',
                'name': '示例歌曲2',
                'artist': '艺术家2',
                'album': '专辑2',
                'duration': 180
            }
        ]
    }


def download_song(platform: str, song_id: str, save_path: str) -> bool:
    """
    下载歌曲（框架函数）
    
    实际实现需要：
    1. 获取歌曲的播放URL
    2. 下载音频文件
    3. 保存到指定路径
    
    Args:
        platform: 平台名称
        song_id: 歌曲ID
        save_path: 保存路径
    
    Returns:
        是否下载成功
    """
    # 这是一个框架函数，实际实现需要处理具体的音乐平台API
    logging.info(f'[Music Import] 下载歌曲: platform={platform}, id={song_id}')
    
    # 实际实现示例:
    # 1. 调用API获取歌曲播放链接
    # 2. 使用requests下载文件
    # 3. 保存到save_path
    
    return False


# ============================================================================
# 弹幕分析API
# ============================================================================

@app.route('/api/danmaku/analysis/realtime')
@api_error_handler
def get_danmaku_realtime_analysis():
    """获取弹幕实时分析概览"""
    danmaku_analyzer = get_danmaku_analyzer()
    stats = danmaku_analyzer.get_realtime_stats()
    
    return jsonify({
        'success': True,
        'data': stats
    })


@app.route('/api/danmaku/analysis/sentiment')
@api_error_handler
def get_danmaku_sentiment_analysis():
    """获取情感分析统计"""
    time_window = request.args.get('time_window', 3600, type=int)
    
    danmaku_analyzer = get_danmaku_analyzer()
    sentiment_stats = danmaku_analyzer.get_sentiment_stats(time_window=time_window)
    
    return jsonify({
        'success': True,
        'data': sentiment_stats
    })


@app.route('/api/danmaku/analysis/wordcloud')
@api_error_handler
def get_danmaku_wordcloud():
    """获取词云数据"""
    time_window = request.args.get('time_window', 3600, type=int)
    max_words = request.args.get('max_words', 100, type=int)
    
    danmaku_analyzer = get_danmaku_analyzer()
    wordcloud_data = danmaku_analyzer.generate_wordcloud_data(
        time_window=time_window,
        max_words=max_words
    )
    
    return jsonify({
        'success': True,
        'data': wordcloud_data
    })


@app.route('/api/danmaku/analysis/hot_topics')
@api_error_handler
def get_danmaku_hot_topics():
    """获取热门话题"""
    time_window = request.args.get('time_window', 3600, type=int)
    top_n = request.args.get('top_n', 10, type=int)
    
    danmaku_analyzer = get_danmaku_analyzer()
    hot_topics = danmaku_analyzer.get_hot_topics(
        time_window=time_window,
        top_n=top_n
    )
    
    result = []
    for topic in hot_topics:
        result.append({
            'keyword': topic.keyword,
            'count': topic.count,
            'trend_score': topic.trend_score,
            'related_danmaku': topic.related_danmaku
        })
    
    return jsonify({
        'success': True,
        'data': result
    })


@app.route('/api/danmaku/analysis/duplicates')
@api_error_handler
def get_danmaku_duplicates():
    """获取重复弹幕统计"""
    top_n = request.args.get('top_n', 20, type=int)
    
    danmaku_analyzer = get_danmaku_analyzer()
    duplicate_stats = danmaku_analyzer.get_duplicate_stats(top_n=top_n)
    
    return jsonify({
        'success': True,
        'data': duplicate_stats
    })


@app.route('/api/danmaku/analysis/active_users')
@api_error_handler
def get_danmaku_active_users():
    """获取活跃用户统计"""
    time_window = request.args.get('time_window', 3600, type=int)
    top_n = request.args.get('top_n', 20, type=int)
    
    danmaku_analyzer = get_danmaku_analyzer()
    active_users = danmaku_analyzer.get_active_users(
        time_window=time_window,
        top_n=top_n
    )
    
    return jsonify({
        'success': True,
        'data': active_users
    })


@app.route('/api/danmaku/analysis/suspicious_users')
@api_error_handler
def get_danmaku_suspicious_users():
    """获取可疑用户（潜在带节奏者）"""
    time_window = request.args.get('time_window', 3600, type=int)
    
    danmaku_analyzer = get_danmaku_analyzer()
    suspicious_users = danmaku_analyzer.get_suspicious_users(time_window=time_window)
    
    return jsonify({
        'success': True,
        'data': suspicious_users
    })


@app.route('/api/danmaku/analysis/word_frequency')
@api_error_handler
def get_danmaku_word_frequency():
    """获取词频统计"""
    time_window = request.args.get('time_window', 3600, type=int)
    top_n = request.args.get('top_n', 100, type=int)
    
    danmaku_analyzer = get_danmaku_analyzer()
    word_freq = danmaku_analyzer.get_word_frequency(
        time_window=time_window if time_window > 0 else None,
        top_n=top_n
    )
    
    return jsonify({
        'success': True,
        'data': [{'word': w, 'count': c} for w, c in word_freq.items()]
    })


@app.route('/api/danmaku/analysis/clear', methods=['POST'])
@api_error_handler
def clear_danmaku_analysis():
    """清空弹幕分析历史数据（需要管理员密码）"""
    data = request.json
    password = data.get('password') if data else None
    
    admin_password = get_config("app", "admin_password")
    if not password or password != admin_password:
        raise AuthenticationError('密码错误', error_code='INVALID_PASSWORD')
    
    danmaku_analyzer = get_danmaku_analyzer()
    danmaku_analyzer.clear_history()
    
    return jsonify({
        'success': True,
        'message': '弹幕分析历史数据已清空'
    })


# WebSocket事件处理器
@socketio.on('connect')
def handle_connect():
    """处理WebSocket连接"""
    try:
        # 在 Flask-SocketIO 中使用 flask.request.sid 获取 session ID
        sid = flask.request.sid
        # 获取客户端 IP 地址
        client_ip = flask.request.remote_addr
        is_active, queue_position = concurrency_manager.add_connection(sid, client_ip)

        if is_active:
            # 立即进入，发送连接成功事件
            emit('connection_status', {
                'status': 'connected',
                'message': '连接成功',
                'queue_position': 0
            })
            # 广播统计更新
            broadcast_queue_stats()
        else:
            # 进入等待队列，发送等待状态
            emit('connection_status', {
                'status': 'waiting',
                'message': f'当前服务器繁忙，您在第 {queue_position} 位等待',
                'queue_position': queue_position,
                'estimated_wait': queue_position * 2  # 估计等待时间（秒）
            })
            # 广播统计更新
            broadcast_queue_stats()
    except Exception as e:
        logging.error(f"WebSocket连接错误: {e}")
        return False

@socketio.on('disconnect')
def handle_disconnect():
    """处理WebSocket断开连接"""
    try:
        # 在 Flask-SocketIO 中使用 flask.request.sid 获取 session ID
        sid = flask.request.sid
        next_sid = concurrency_manager.remove_connection(sid)

        # 如果有用户被唤醒，通知该用户
        if next_sid:
            socketio.emit('connection_status', {
                'status': 'connected',
                'message': '您的位置已到，连接成功',
                'queue_position': 0
            }, room=next_sid)

        # 广播统计更新
        broadcast_queue_stats()
    except Exception as e:
        logging.error(f"WebSocket断开连接错误: {e}")

@socketio.on('check_queue')
def handle_check_queue():
    """检查队列位置"""
    # 在 Flask-SocketIO 中使用 flask.request.sid 获取 session ID
    sid = flask.request.sid
    position = concurrency_manager.get_queue_position(sid)

    if position == 0:
        emit('queue_status', {
            'status': 'connected',
            'queue_position': 0,
            'message': '您已连接'
        })
    else:
        emit('queue_status', {
            'status': 'waiting',
            'queue_position': position,
            'estimated_wait': position * 2,
            'message': f'您在第 {position} 位等待'
        })

def broadcast_queue_stats():
    """广播队列统计信息到所有连接"""
    stats = concurrency_manager.get_stats()
    socketio.emit('queue_stats', {
        'active': stats['active'],
        'waiting': stats['waiting'],
        'max_concurrent': stats['max_concurrent']
    })

# 留言板管理 - 使用 deque 优化消息存储
chat_messages = deque(maxlen=MAX_CHAT_MESSAGES)  # 自动限制最大消息数
muted_users = {}  # 存储禁言用户 {ip: {'until': timestamp, 'reason': str}}
ADMIN_PASSWORD = get_config("app", "admin_password", default="changeme")  # 管理员密码，请通过config.yaml设置

def filter_sensitive_words(text):
    """过滤敏感词"""
    if not FILTER_ENABLE or not SENSITIVE_WORDS:
        logging.info("✓ 敏感词过滤未启用或词列表为空")
        return text, True  # 不过滤，返回成功

    filtered_text = text
    has_sensitive = False

    # 按长度从长到短排序，优先匹配长词
    sorted_words = sorted(SENSITIVE_WORDS, key=len, reverse=True)

    for word in sorted_words:
        if word in filtered_text:
            has_sensitive = True
            logging.warning(f"⚠️ 检测到敏感词: '{word}' 在消息: '{text}'")
            if FILTER_ACTION == "replace":
                # 替换为 *
                filtered_text = filtered_text.replace(word, "*" * len(word))
                logging.info(f"  → 已替换为: '{filtered_text}'")
            elif FILTER_ACTION == "reject" or FILTER_ACTION == "warn":
                # 拒绝或警告方式
                logging.info(f"  → 消息被拒绝（动作: {FILTER_ACTION}）")
                return text, False

    if has_sensitive:
        logging.warning(f"🚫 消息包含敏感词，结果: 有效={not has_sensitive}")
    else:
        logging.info(f"✓ 消息通过敏感词检查")

    return filtered_text, not has_sensitive

@socketio.on('chat_message')
def handle_chat_message(data):
    """处理聊天消息"""
    try:
        # 检查是否启用聊天功能
        if not CHAT_ENABLE:
            emit('chat_error', {'message': '聊天功能未启用'})
            return

        username = data.get('username', '匿名用户')
        message = data.get('message', '').strip()

        if not message:
            return

        # 检查是否被禁言
        if MUTE_ENABLE:
            client_ip = flask.request.remote_addr
            if client_ip in muted_users:
                mute_info = muted_users[client_ip]
                remaining = int(mute_info['until'] - time.time())
                if remaining > 0:
                    emit('chat_error', {
                        'message': f'您已被禁言，剩余时间: {remaining // 60}分{remaining % 60}秒',
                        'is_muted': True,
                        'remaining_time': remaining
                    })
                    return
                else:
                    # 禁言过期，自动解除
                    del muted_users[client_ip]
                    logging.info(f"🔓 [{client_ip}] 禁言已自动解除")

        # 敏感词过滤
        filtered_message, is_valid = filter_sensitive_words(message)
        if not is_valid:
            if FILTER_ACTION == "reject":
                emit('chat_error', {'message': '消息包含敏感词，已被拒绝'})
                logging.warning(f"🚫 [{username}] 敏感词拒绝: {message}")
                return
            elif FILTER_ACTION == "warn":
                emit('chat_warning', {'message': '消息包含敏感词，已被替换'})
                logging.warning(f"⚠️ [{username}] 敏感词警告: {message}")

        # 限制消息长度
        if len(filtered_message) > MAX_MESSAGE_LENGTH:
            filtered_message = filtered_message[:MAX_MESSAGE_LENGTH] + '...'

        # 限制用户名长度
        username = username[:MAX_USERNAME_LENGTH]

        # 获取客户端 IP
        client_ip = flask.request.remote_addr

        # 构建消息对象
        chat_message = {
            'username': username,
            'message': filtered_message,
            'timestamp': time.time(),
            'type': 'user_message',
            'ip': client_ip
        }

        # 添加到消息列表（deque自动限制最大长度）
        chat_messages.append(chat_message)

        # 广播消息给所有客户端
        socketio.emit('chat_message', chat_message)

        logging.info(f"💬 聊天消息 [{username} ({client_ip})]: {filtered_message}")

    except Exception as e:
        logging.error(f"处理聊天消息错误: {e}")

@socketio.on('get_chat_history')
def handle_get_chat_history():
    """获取聊天历史"""
    try:
        emit('chat_history', chat_messages)
    except Exception as e:
        logging.error(f"获取聊天历史错误: {e}")

@socketio.on('admin_login')
def handle_admin_login(data):
    """管理员登录"""
    try:
        password = data.get('password', '')

        if password == ADMIN_PASSWORD:
            emit('admin_login_success', {'message': '登录成功'})
            logging.info(f"🔑 管理员登录成功")
        else:
            emit('admin_login_failed', {'message': '密码错误'})
            logging.warning(f"⚠️ 管理员登录失败: 密码错误")
    except Exception as e:
        logging.error(f"管理员登录错误: {e}")

@socketio.on('admin_mute_user')
def handle_admin_mute_user(data):
    """管理员禁言用户"""
    try:
        password = data.get('password', '')
        target_ip = data.get('ip', '')
        reason = data.get('reason', '违规行为')
        duration = data.get('duration', MUTE_DURATION)

        # 验证管理员密码
        if password != ADMIN_PASSWORD:
            emit('admin_operation_failed', {'message': '权限验证失败'})
            logging.warning(f"⚠️ 禁言操作失败: 密码错误")
            return

        if not target_ip:
            emit('admin_operation_failed', {'message': '缺少目标IP'})
            return

        # 执行禁言
        muted_users[target_ip] = {
            'until': time.time() + duration,
            'reason': reason
        }

        # 广播禁言通知
        socketio.emit('user_muted', {
            'ip': target_ip,
            'until': time.time() + duration,
            'remaining': duration,
            'reason': reason
        })

        emit('admin_operation_success', {'message': f'已禁言用户 {target_ip}'})
        logging.info(f"🔒 管理员禁言用户: {target_ip}, 原因: {reason}, 时长: {duration}秒")

    except Exception as e:
        logging.error(f"禁言用户错误: {e}")
        emit('admin_operation_failed', {'message': '操作失败'})

@socketio.on('admin_unmute_user')
def handle_admin_unmute_user(data):
    """管理员解禁用户"""
    try:
        password = data.get('password', '')
        target_ip = data.get('ip', '')

        # 验证管理员密码
        if password != ADMIN_PASSWORD:
            emit('admin_operation_failed', {'message': '权限验证失败'})
            logging.warning(f"⚠️ 解禁操作失败: 密码错误")
            return

        if not target_ip:
            emit('admin_operation_failed', {'message': '缺少目标IP'})
            return

        # 执行解禁
        if target_ip in muted_users:
            del muted_users[target_ip]

            # 广播解禁通知
            socketio.emit('user_unmuted', {'ip': target_ip})

            emit('admin_operation_success', {'message': f'已解禁用户 {target_ip}'})
            logging.info(f"🔓 管理员解禁用户: {target_ip}")
        else:
            emit('admin_operation_failed', {'message': '该用户未被禁言'})

    except Exception as e:
        logging.error(f"解禁用户错误: {e}")
        emit('admin_operation_failed', {'message': '操作失败'})

@socketio.on('get_muted_list')
def handle_get_muted_list():
    """获取禁言用户列表"""
    try:
        muted_list = []
        current_time = time.time()

        for ip, info in muted_users.items():
            remaining = int(info['until'] - current_time)
            if remaining > 0:
                muted_list.append({
                    'ip': ip,
                    'remaining': remaining,
                    'reason': info['reason']
                })

        emit('muted_list', muted_list)
    except Exception as e:
        logging.error(f"获取禁言列表错误: {e}")


# ==================== 独立在线聊天室 WebSocket 事件 ====================
# 完全独立于现有聊天/留言板系统

@socketio.on('live_chat_join')
def handle_live_chat_join(data):
    """处理用户加入聊天室"""
    try:
        sid = flask.request.sid
        client_ip = flask.request.remote_addr

        if not live_chatroom.LIVE_CHATROOM_ENABLE:
            emit('live_chat_error', {'message': '聊天室功能未启用'})
            return

        username = data.get('username', '')
        if not username:
            import random
            adjectives = live_chatroom.USERNAME_ADJECTIVES
            nouns = live_chatroom.USERNAME_NOUNS
            adj = random.choice(adjectives)
            noun = random.choice(nouns)
            random_num = random.randint(100, 999)
            username = f"{adj}{noun}{random_num}"

        live_chatroom.add_online_user(sid, client_ip, username)

        emit('live_chat_joined', {
            'username': username,
            'online_count': live_chatroom.get_online_count()
        })

        recent_messages = live_chatroom.get_recent_messages(50)
        emit('live_chat_history', {'messages': recent_messages})

        socketio.emit('live_chat_user_online', {
            'username': username,
            'online_count': live_chatroom.get_online_count()
        })

        logging.info(f"💬 [聊天室] 用户 {username} ({client_ip}) 加入聊天室")

    except Exception as e:
        logging.error(f"处理聊天室加入错误: {e}")
        emit('live_chat_error', {'message': '加入聊天室失败'})


@socketio.on('live_chat_message')
def handle_live_chat_message(data):
    """处理聊天室消息"""
    try:
        sid = flask.request.sid
        client_ip = flask.request.remote_addr

        if not live_chatroom.LIVE_CHATROOM_ENABLE:
            emit('live_chat_error', {'message': '聊天室功能未启用'})
            return

        user_info = live_chatroom.online_users.get(sid)
        if not user_info:
            emit('live_chat_error', {'message': '请先加入聊天室'})
            return

        username = user_info['username']
        content = data.get('content', '').strip()

        if not content:
            emit('live_chat_error', {'message': '消息内容不能为空'})
            return

        if len(content) > live_chatroom.MAX_MESSAGE_LENGTH:
            emit('live_chat_error', {'message': f'消息长度不能超过 {live_chatroom.MAX_MESSAGE_LENGTH} 字符'})
            return

        mute_info = live_chatroom.check_muted(client_ip)
        if mute_info:
            remaining = mute_info['remaining']
            emit('live_chat_error', {
                'message': f'您已被禁言，剩余时间: {remaining // 60}分{remaining % 60}秒',
                'is_muted': True,
                'remaining_time': remaining
            })
            return

        filtered_content, is_valid = live_chatroom.filter_room_sensitive_words(content)
        if not is_valid:
            emit('live_chat_error', {'message': '消息包含敏感词，已被拒绝'})
            logging.warning(f"🚫 [聊天室] 消息被拒绝: {username} - {content}")
            return

        chat_message = live_chatroom.create_message(username, filtered_content, client_ip)
        live_chatroom.add_message(chat_message)

        socketio.emit('live_chat_message', chat_message)

        logging.info(f"💬 [聊天室] 消息广播: {username} - {filtered_content[:50]}...")

    except Exception as e:
        logging.error(f"处理聊天室消息错误: {e}")
        emit('live_chat_error', {'message': '发送消息失败'})


@socketio.on('live_chat_admin_login')
def handle_live_chat_admin_login(data):
    """聊天室管理员登录"""
    try:
        password = data.get('password', '')
        admin_password = get_config("app", "admin_password", default="changeme")

        if password == admin_password:
            emit('live_chat_admin_login_success', {
                'message': '登录成功',
                'muted_list': live_chatroom.get_muted_list(),
                'online_users': live_chatroom.get_online_users()
            })
            logging.info(f"🔑 [聊天室] 管理员登录成功")
        else:
            emit('live_chat_admin_login_failed', {'message': '密码错误'})
            logging.warning(f"⚠️ [聊天室] 管理员登录失败: 密码错误")

    except Exception as e:
        logging.error(f"聊天室管理员登录错误: {e}")
        emit('live_chat_error', {'message': '登录失败'})


@socketio.on('live_chat_admin_mute')
def handle_live_chat_admin_mute(data):
    """聊天室管理员禁言用户"""
    try:
        sid = flask.request.sid
        user_info = live_chatroom.online_users.get(sid)

        password = data.get('password', '')
        admin_password = get_config("app", "admin_password", default="changeme")

        if password != admin_password:
            emit('live_chat_admin_operation_failed', {'message': '权限验证失败'})
            logging.warning(f"⚠️ [聊天室] 禁言操作失败: 密码错误")
            return

        target_ip = data.get('ip', '')
        reason = data.get('reason', '违规行为')
        duration = data.get('duration', live_chatroom.DEFAULT_MUTE_DURATION)

        if not target_ip:
            emit('live_chat_admin_operation_failed', {'message': '缺少目标IP'})
            return

        mute_info = live_chatroom.mute_user(target_ip, reason, duration)

        socketio.emit('live_chat_user_muted', {
            'ip': target_ip,
            'until': mute_info['until'],
            'remaining': mute_info['remaining'],
            'reason': reason
        })

        emit('live_chat_admin_operation_success', {
            'message': f'已禁言用户 {target_ip}',
            'muted_list': live_chatroom.get_muted_list()
        })

    except Exception as e:
        logging.error(f"聊天室禁言用户错误: {e}")
        emit('live_chat_admin_operation_failed', {'message': '操作失败'})


@socketio.on('live_chat_admin_unmute')
def handle_live_chat_admin_unmute(data):
    """聊天室管理员解禁用户"""
    try:
        password = data.get('password', '')
        admin_password = get_config("app", "admin_password", default="changeme")

        if password != admin_password:
            emit('live_chat_admin_operation_failed', {'message': '权限验证失败'})
            logging.warning(f"⚠️ [聊天室] 解禁操作失败: 密码错误")
            return

        target_ip = data.get('ip', '')

        if not target_ip:
            emit('live_chat_admin_operation_failed', {'message': '缺少目标IP'})
            return

        if live_chatroom.unmute_user(target_ip):
            socketio.emit('live_chat_user_unmuted', {'ip': target_ip})

            emit('live_chat_admin_operation_success', {
                'message': f'已解禁用户 {target_ip}',
                'muted_list': live_chatroom.get_muted_list()
            })
        else:
            emit('live_chat_admin_operation_failed', {'message': '该用户未被禁言'})

    except Exception as e:
        logging.error(f"聊天室解禁用户错误: {e}")
        emit('live_chat_admin_operation_failed', {'message': '操作失败'})


@socketio.on('live_chat_get_muted_list')
def handle_live_chat_get_muted_list():
    """获取聊天室禁言用户列表"""
    try:
        muted_list = live_chatroom.get_muted_list()
        emit('live_chat_muted_list', {'list': muted_list})
    except Exception as e:
        logging.error(f"获取聊天室禁言列表错误: {e}")


@socketio.on('live_chat_leave')
def handle_live_chat_leave():
    """处理用户离开聊天室"""
    try:
        sid = flask.request.sid
        user_info = live_chatroom.remove_online_user(sid)

        if user_info:
            socketio.emit('live_chat_user_offline', {
                'username': user_info['username'],
                'online_count': live_chatroom.get_online_count()
            })
            logging.info(f"👋 [聊天室] 用户 {user_info['username']} 离开聊天室")

    except Exception as e:
        logging.error(f"处理聊天室离开错误: {e}")


# ==================== 独立在线聊天室 REST API ====================

@app.route('/api/live-chat/config')
@api_error_handler
def get_live_chat_config():
    """获取聊天室配置"""
    return jsonify({
        'success': True,
        'config': {
            'enable': live_chatroom.LIVE_CHATROOM_ENABLE,
            'max_messages': live_chatroom.MAX_ROOM_MESSAGES,
            'max_message_length': live_chatroom.MAX_MESSAGE_LENGTH,
            'max_username_length': live_chatroom.MAX_USERNAME_LENGTH,
            'username': {
                'adjectives': live_chatroom.USERNAME_ADJECTIVES,
                'nouns': live_chatroom.USERNAME_NOUNS
            },
            'filter': {
                'enable': live_chatroom.FILTER_ENABLE,
                'sensitive_words_count': len(live_chatroom.SENSITIVE_WORDS),
                'filter_action': live_chatroom.FILTER_ACTION
            },
            'mute': {
                'enable': live_chatroom.MUTE_ENABLE,
                'mute_duration': live_chatroom.DEFAULT_MUTE_DURATION
            }
        }
    })


@app.route('/api/live-chat/messages')
@api_error_handler
def get_live_chat_messages():
    """获取聊天室历史消息"""
    limit = request.args.get('limit', 100, type=int)
    messages = live_chatroom.get_recent_messages(limit)
    return jsonify({
        'success': True,
        'messages': messages,
        'count': len(messages)
    })


@app.route('/api/live-chat/online')
@api_error_handler
def get_live_chat_online():
    """获取在线用户数"""
    return jsonify({
        'success': True,
        'online_count': live_chatroom.get_online_count(),
        'online_users': live_chatroom.get_online_users()
    })


# ==================== 留言板 REST API ====================

# 留言板消息存储（JSON文件持久化）
GUESTBOOK_FILE = "guestbook_messages.json"
guestbook_messages = []

def load_guestbook_messages():
    """从JSON文件加载留言"""
    global guestbook_messages
    try:
        if os.path.exists(GUESTBOOK_FILE):
            with open(GUESTBOOK_FILE, 'r', encoding='utf-8') as f:
                guestbook_messages = json.load(f)
            logging.info(f"📝 已加载 {len(guestbook_messages)} 条留言")
        else:
            guestbook_messages = []
            logging.info("📝 留言板文件不存在，创建新文件")
    except Exception as e:
        logging.error(f"加载留言板失败: {e}")
        guestbook_messages = []

def save_guestbook_messages():
    """保存留言到JSON文件"""
    try:
        with open(GUESTBOOK_FILE, 'w', encoding='utf-8') as f:
            json.dump(guestbook_messages, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"保存留言板失败: {e}")

# 启动时加载留言
load_guestbook_messages()

@app.route('/api/guestbook/config')
@api_error_handler
def get_guestbook_config():
    """获取留言板配置"""
    return jsonify({
        'success': True,
        'config': {
            'enable': CHAT_ENABLE,
            'max_messages': MAX_CHAT_MESSAGES,
            'max_message_length': MAX_MESSAGE_LENGTH,
            'max_title_length': 50,
            'max_username_length': MAX_USERNAME_LENGTH,
            'username': {
                'adjectives': USERNAME_ADJECTIVES,
                'nouns': USERNAME_NOUNS
            },
            'filter': {
                'enable': FILTER_ENABLE,
                'sensitive_words_count': len(SENSITIVE_WORDS),
                'filter_action': FILTER_ACTION
            },
            'mute': {
                'enable': MUTE_ENABLE,
                'mute_duration': MUTE_DURATION
            }
        }
    })

@app.route('/api/guestbook/messages')
@api_error_handler
def get_guestbook_messages():
    """获取留言列表（支持轮询）"""
    since = request.args.get('since', type=float, default=0)

    # 过滤指定时间之后的留言
    messages = [msg for msg in guestbook_messages if msg['timestamp'] > since]

    return jsonify({
        'success': True,
        'messages': list(guestbook_messages)
    })

@app.route('/api/guestbook/message', methods=['POST'])
@api_error_handler
def post_guestbook_message():
    """发布留言"""
    # 检查是否启用留言功能
    if not CHAT_ENABLE:
        return jsonify({
            'success': False,
            'message': '留言功能未启用'
        }), 400

    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'message': '无效的请求数据'
        }), 400

    username = data.get('username', '匿名用户')
    title = data.get('title', '').strip()
    message = data.get('message', '').strip()

    if not message:
        return jsonify({
            'success': False,
            'message': '留言内容不能为空'
        }), 400

    # 检查是否被禁言
    if MUTE_ENABLE:
        client_ip = request.remote_addr
        if client_ip in muted_users:
            mute_info = muted_users[client_ip]
            remaining = int(mute_info['until'] - time.time())
            if remaining > 0:
                return jsonify({
                    'success': False,
                    'message': f'您已被禁言，剩余时间: {remaining // 60}分{remaining % 60}秒',
                    'is_muted': True,
                    'remaining_time': remaining
                }), 403
            else:
                # 禁言过期，自动解除
                del muted_users[client_ip]
                logging.info(f"🔓 [{client_ip}] 禁言已自动解除")

    # 敏感词过滤
    filtered_message, is_valid = filter_sensitive_words(message)
    if not is_valid:
        if FILTER_ACTION == "reject":
            return jsonify({
                'success': False,
                'message': '留言包含敏感词，已被拒绝'
            }), 400
        elif FILTER_ACTION == "warn":
            logging.warning(f"⚠️ [{username}] 敏感词警告: {message}")

    # 过滤标题敏感词
    filtered_title = title
    if title:
        filtered_title, title_valid = filter_sensitive_words(title)
        if not title_valid and FILTER_ACTION == "reject":
            return jsonify({
                'success': False,
                'message': '标题包含敏感词，已被拒绝'
            }), 400

    # 限制长度
    if len(filtered_message) > MAX_MESSAGE_LENGTH:
        filtered_message = filtered_message[:MAX_MESSAGE_LENGTH] + '...'
    if len(filtered_title) > 50:
        filtered_title = filtered_title[:50]

    username = username[:MAX_USERNAME_LENGTH]

    # 获取客户端 IP
    client_ip = request.remote_addr

    # 构建留言对象
    guestbook_message = {
        'id': str(uuid.uuid4())[:8],
        'username': username,
        'title': filtered_title,
        'message': filtered_message,
        'timestamp': time.time(),
        'type': 'user_message',
        'ip': client_ip
    }

    # 添加到留言列表
    guestbook_messages.append(guestbook_message)

    # 限制最大条数（保留最近的1000条）
    if len(guestbook_messages) > 1000:
        guestbook_messages[:] = guestbook_messages[-1000:]

    # 保存到文件
    save_guestbook_messages()

    logging.info(f"📝 留言 [{username} ({client_ip})]: {filtered_title or '(无标题)'} - {filtered_message[:50]}...")

    return jsonify({
        'success': True,
        'message': guestbook_message
    })

@app.route('/api/guestbook/admin/login', methods=['POST'])
@api_error_handler
def guestbook_admin_login():
    """留言板管理员登录"""
    data = request.get_json()
    password = data.get('password', '') if data else ''

    if password == ADMIN_PASSWORD:
        return jsonify({
            'success': True,
            'message': '登录成功'
        })
    else:
        return jsonify({
            'success': False,
            'message': '密码错误'
        }), 401

@app.route('/api/guestbook/admin/mute', methods=['POST'])
@api_error_handler
def guestbook_admin_mute():
    """留言板管理员禁言"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '无效的请求'}), 400

    password = data.get('password', '')
    target_ip = data.get('ip', '')
    reason = data.get('reason', '违规行为')
    duration = data.get('duration', MUTE_DURATION)

    # 验证管理员密码
    if password != ADMIN_PASSWORD:
        return jsonify({'success': False, 'message': '权限验证失败'}), 403

    if not target_ip:
        return jsonify({'success': False, 'message': '缺少目标IP'}), 400

    # 执行禁言
    muted_users[target_ip] = {
        'until': time.time() + duration,
        'reason': reason
    }

    logging.info(f"🔒 留言板管理员禁言用户: {target_ip}, 原因: {reason}, 时长: {duration}秒")

    return jsonify({
        'success': True,
        'message': f'已禁言用户 {target_ip}'
    })

@app.route('/api/guestbook/admin/unmute', methods=['POST'])
@api_error_handler
def guestbook_admin_unmute():
    """留言板管理员解禁"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '无效的请求'}), 400

    password = data.get('password', '')
    target_ip = data.get('ip', '')

    # 验证管理员密码
    if password != ADMIN_PASSWORD:
        return jsonify({'success': False, 'message': '权限验证失败'}), 403

    if not target_ip:
        return jsonify({'success': False, 'message': '缺少目标IP'}), 400

    # 执行解禁
    if target_ip in muted_users:
        del muted_users[target_ip]
        logging.info(f"🔓 留言板管理员解禁用户: {target_ip}")
        return jsonify({
            'success': True,
            'message': f'已解禁用户 {target_ip}'
        })
    else:
        return jsonify({'success': False, 'message': '该用户未被禁言'}), 400

@app.route('/api/guestbook/admin/muted-list')
@api_error_handler
def guestbook_admin_muted_list():
    """获取留言板禁言用户列表"""
    muted_list = []
    current_time = time.time()

    for ip, info in muted_users.items():
        remaining = int(info['until'] - current_time)
        if remaining > 0:
            muted_list.append({
                'ip': ip,
                'remaining': remaining,
                'reason': info['reason']
            })

    return jsonify({
        'success': True,
        'list': muted_list
    })







class EmailNotifier:
    """QQ邮箱通知器 - 带熔断器保护"""

    def __init__(self, email_config: Dict):
        self.smtp_server = email_config.get('smtp_server', 'smtp.qq.com')
        self.smtp_port = email_config.get('smtp_port', 587)
        self.sender = email_config.get('sender', '')
        self.password = email_config.get('password', '')  # QQ邮箱授权码
        # 支持多个邮箱，用逗号分隔
        receiver_str = email_config.get('receiver', '')
        self.receivers = [r.strip() for r in receiver_str.split(',') if r.strip()]

        # 验证配置
        if not all([self.sender, self.password]) or not self.receivers:
            logging.warning("⚠️ 邮箱配置不完整，邮件通知功能可能无法正常工作")

    def _do_send_email(self, subject: str, content: str) -> bool:
        """执行实际的邮件发送逻辑"""
        # 创建邮件内容
        message = MIMEText(content, 'plain', 'utf-8')
        message['From'] = f'"{self.sender}" <{self.sender}>'
        message['To'] = ', '.join(self.receivers)  # 显示所有收件人
        message['Subject'] = Header(subject, 'utf-8')

        # 根据端口选择连接方式
        if self.smtp_port == 587:
            # 使用STARTTLS
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.sender, self.password)
                result = server.sendmail(self.sender, self.receivers, message.as_string())
        else:
            # 使用SSL
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=10) as server:
                server.login(self.sender, self.password)
                result = server.sendmail(self.sender, self.receivers, message.as_string())

        return True

    @sync_retry(max_attempts=2, base_delay=1.0,
                retriable_exceptions=(smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected))
    def send_email(self, subject: str, content: str) -> bool:
        """发送邮件通知 - 带熔断器保护"""
        try:
            # 通过熔断器执行邮件发送
            result = email_circuit_breaker.call_sync(self._do_send_email, subject, content)
            logging.info(f"📧 邮件发送成功: {subject}")
            return True

        except CircuitBreakerOpenError:
            logging.warning(f"⚠️ 邮件发送被熔断器阻止: {subject}")
            return False
        except smtplib.SMTPAuthenticationError as e:
            logging.error(f"❌ SMTP认证失败: {e}")
            logging.error("💡 请检查QQ邮箱授权码是否正确，或是否开启了SMTP服务")
            return False
        except smtplib.SMTPConnectError as e:
            logging.error(f"❌ SMTP连接失败: {e}")
            logging.error("💡 请检查网络连接和SMTP服务器地址")
            return False
        except smtplib.SMTPResponseException as e:
            # 检查是否是连接关闭时的协议错误（邮件已发送成功）
            if hasattr(e, 'smtp_error') and isinstance(e.smtp_error, bytes) and e.smtp_error == b'\x00\x00\x00':
                logging.info("📧 邮件发送成功")
                return True
            else:
                logging.error(f"❌ 邮件发送失败: {e}")
                return False
        except Exception as e:
            logging.error(f"❌ 邮件发送失败: {e}")
            return False

class FuzzyKeywordMatcher:
    """模糊关键词匹配器"""
    
    def __init__(self):
        """
        初始化关键词匹配器
        只匹配包含"鸽切"的弹幕
        """
        # 延迟初始化，避免模块加载时的配置问题
        self.pattern = None
        self.keyword = None
        
    def _ensure_initialized(self):
        """确保匹配器已初始化"""
        if self.pattern is None:
            try:
                self.keyword = get_config("monitor", "keyword", default="鸽切")
                # 创建简单的包含匹配
                self.pattern = re.compile(self.keyword)
                logging.info(f"🔍 关键词: {self.keyword}（包含匹配）")
            except Exception as e:
                logging.error(f"❌ 关键词匹配器初始化失败: {e}")
                # 设置一个默认模式，避免后续崩溃
                self.keyword = "鸽切"
                self.pattern = re.compile(self.keyword)
                logging.warning(f"⚠️ 使用默认关键词: {self.keyword}")
    
    def contains_keyword(self, text: str) -> bool:
        """检查文本是否包含关键词（模糊匹配）"""
        self._ensure_initialized()
        if not text:
            return False
        
        # 防御性检查：确保pattern不为None
        if self.pattern is None:
            logging.error("❌ 关键词匹配器pattern为None，尝试重新初始化")
            try:
                self.keyword = get_config("monitor", "keyword", default="鸽切")
                self.pattern = re.compile(self.keyword)
                logging.info(f"🔍 重新初始化关键词: {self.keyword}")
            except Exception as e:
                logging.error(f"❌ 重新初始化失败: {e}")
                return False
        
        # 使用正则表达式进行模糊匹配
        match = self.pattern.search(text)
        return match is not None
    
    def find_keyword_matches(self, text: str) -> List[str]:
        """查找文本中所有匹配的关键词"""
        self._ensure_initialized()
        if not text:
            return []
        
        # 防御性检查：确保pattern不为None
        if self.pattern is None:
            logging.error("❌ 关键词匹配器pattern为None，尝试重新初始化")
            try:
                self.keyword = get_config("monitor", "keyword", default="鸽切")
                self.pattern = re.compile(self.keyword)
                logging.info(f"🔍 重新初始化关键词: {self.keyword}")
            except Exception as e:
                logging.error(f"❌ 重新初始化失败: {e}")
                return []
        
        matches = self.pattern.findall(text)
        return list(set(matches))  # 去重
    
    def get_matched_keyword(self, text: str) -> Optional[str]:
        """获取匹配到的关键词（返回第一个匹配）"""
        self._ensure_initialized()
        matches = self.find_keyword_matches(text)
        return matches[0] if matches else None

class BilibiliDanmakuMonitor:
    """B站弹幕监控 - 使用LIVE事件检测开播"""
    
    def __init__(self, room_id: int, email_config: Dict, credential_config: Dict = None):
        self.room_id = room_id
        self.email_notifier = EmailNotifier(email_config)
        
        # 初始化模糊关键词匹配器
        self.keyword_matcher = FuzzyKeywordMatcher()
        
        # 状态标志
        self.is_live = False  # 是否正在直播
        self.is_monitoring = False  # 是否正在监控弹幕
        self.live_start_time = None  # 开播时间（中国时区时间戳）
        self.monitor_start_time = None  # 监控开始时间（作为邮件中经过时间的备用）
        
        # 频率控制（避免重复发送邮件）
        self.last_email_time = 0
        self.email_cooldown = None  # 延迟加载
        
        # 统计信息
        self.keyword_count = 0
        self.total_danmaku = 0
        
        # 直播间信息缓存（避免重复获取）
        self.room_info_cache = None
        
        # 重连机制
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = None  # 延迟加载
        self.reconnect_delay = None  # 延迟加载
        self.last_heartbeat_time = None  # 延迟初始化
        self.heartbeat_timeout = None  # 延迟加载
        
        # 登录凭证
        self.credential = None
        if credential_config and credential_config.get('enable', False):
            self.credential = Credential(
                sessdata=credential_config.get('sessdata', ''),
                bili_jct=credential_config.get('bili_jct', ''),
                buvid3=credential_config.get('buvid3', '')
            )
            logging.info("🔐 使用登录凭证")
        else:
            logging.info("🔓 匿名模式")
        
        # 自动切片触发相关
        self.auto_clip_trigger = None
        self.auto_clip_config = None
        self.video_source_path = None  # 视频源路径（用于切片）
        
        # 弹幕监听器
        self.danmaku = LiveDanmaku(self.room_id, credential=self.credential)
        
        # 延迟日志输出，避免在初始化时调用get_config
        self._log_initialization(room_id)
    
    def _ensure_config_initialized(self):
        """确保配置已初始化"""
        if self.email_cooldown is None:
            self.email_cooldown = get_config("monitor", "email_cooldown", default=1)
            self.max_reconnect_attempts = get_config("monitor", "max_reconnect_attempts", default=MAX_RECONNECT_ATTEMPTS)
            self.reconnect_delay = get_config("monitor", "reconnect_delay", default=RECONNECT_DELAY)
            self.heartbeat_timeout = get_config("monitor", "heartbeat_timeout", default=HEARTBEAT_TIMEOUT)
            # 初始化心跳时间
            if self.last_heartbeat_time is None:
                self.last_heartbeat_time = get_china_timestamp()
    
    def _log_initialization(self, room_id):
        """延迟输出初始化日志"""
        self._ensure_config_initialized()
        logging.info(f"🎯 B站弹幕监控初始化 - 房间: {room_id}")
        logging.info(f"🔍 监控关键词: 鸽切（包含匹配）")
        logging.info(f"📧 邮件通知: {self.email_notifier.sender} → {', '.join(self.email_notifier.receivers)}")
        timezone = get_config('app', 'timezone', default='Asia/Shanghai')
        logging.info(f"⏰ 系统时区: 中国时区（{timezone}）")
        logging.info(f"🔄 自动重连机制: 最大重试{self.max_reconnect_attempts}次，延迟{self.reconnect_delay}秒")
        
        # 初始化自动切片配置
        if AUTO_CLIP_AVAILABLE:
            try:
                self.auto_clip_config = load_auto_clip_config_from_yaml(config_manager)
                self.auto_clip_trigger = get_auto_clip_trigger(self.auto_clip_config)
                
                # 从配置中获取视频源路径
                self.video_source_path = get_config("auto_clip", "video_source_path", default=None)
                
                logging.info("=" * 60)
                logging.info("🎬 自动切片配置:")
                logging.info(f"   - 自动切片: {'启用' if self.auto_clip_config.enable_auto_clip else '禁用'}")
                logging.info(f"   - 前置缓冲: {self.auto_clip_config.pre_buffer_seconds}秒")
                logging.info(f"   - 后置缓冲: {self.auto_clip_config.post_buffer_seconds}秒")
                logging.info(f"   - 最大并发: {self.auto_clip_config.max_concurrent_clips}")
                logging.info(f"   - 切片冷却: {self.auto_clip_config.clip_cooldown_seconds}秒")
                logging.info(f"   - 去重窗口: {self.auto_clip_config.deduplication_window_seconds}秒")
                if self.video_source_path:
                    logging.info(f"   - 视频源路径: {self.video_source_path}")
                else:
                    logging.info(f"   - 视频源路径: 未配置（将使用模拟模式）")
                logging.info("=" * 60)
            except Exception as e:
                logging.warning(f"自动切片初始化失败: {e}")
        else:
            logging.info("🎬 自动切片模块未启用")

    async def get_room_info(self) -> Optional[Dict]:
        """获取直播间信息 - 只获取标题和直播状态"""
        
        # 使用配置中的API接口
        api_urls = get_api_urls(self.room_id)
        
        # 使用配置中的请求头
        headers = get_bilibili_headers(self.room_id)
        
        # 构建Cookie（如果启用了凭证）
        if self.credential:
            cookie_parts = []
            if hasattr(self.credential, 'sessdata') and self.credential.sessdata:
                cookie_parts.append(f'SESSDATA={self.credential.sessdata}')
            if hasattr(self.credential, 'bili_jct') and self.credential.bili_jct:
                cookie_parts.append(f'bili_jct={self.credential.bili_jct}')
            if hasattr(self.credential, 'buvid3') and self.credential.buvid3:
                cookie_parts.append(f'buvid3={self.credential.buvid3}')
            
            if cookie_parts:
                headers['Cookie'] = '; '.join(cookie_parts)
        
        for url in api_urls:
            try:
                logging.info(f"🔍 尝试API接口: {url.split('/')[-1]}")
                
                # 使用全局 http_client 而不是直接创建 ClientSession
                data = await http_client.get(url, headers=headers, timeout=15)
                
                if data is None:
                    continue
                
                # 解析不同API的响应格式
                room_data = None
                if 'data' in data:
                    room_data = data['data']
                
                if room_data:
                    title = None
                    live_status = 0
                    
                    # 根据API来源使用不同的解析逻辑
                    api_name = url.split('/')[-1]
                    
                    if 'get_info' in api_name:
                        title = room_data.get('title', '未知标题')
                        live_status = room_data.get('live_status', 0)
                        
                    elif 'getInfoByRoom' in api_name:
                        if 'room_info' in room_data:
                            title = room_data['room_info'].get('title', '未知标题')
                            live_status = room_data['room_info'].get('live_status', 0)
                        
                    elif 'room_init' in api_name:
                        if 'room_info' in room_data:
                            title = room_data['room_info'].get('title', '未知标题')
                            live_status = room_data['room_info'].get('live_status', 0)
                    
                    # 构建简化数据（只保留标题和状态）
                    formatted_data = {
                        'room_id': room_data.get('room_id', self.room_id),
                        'title': title or '未知标题',
                        'live_status': live_status,
                        'online': room_data.get('online', 0),
                        'api_source': api_name  # 记录使用的API
                    }
                    
                    logging.info(f"✅ API {url.split('/')[-1]} 获取成功: {formatted_data['title']}")
                    return formatted_data
                else:
                    logging.warning(f"API {url.split('/')[-1]} 返回数据格式异常")
                            
            except Exception as e:
                logging.warning(f"API {url.split('/')[-1]} 请求失败: {e}")
                continue
        
        logging.error("❌ 所有API接口均无法获取直播间信息")
        return None



    def format_duration(self, seconds: float) -> str:
        """格式化时间间隔"""
        if not seconds:
            return "0秒"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}小时{minutes}分钟{secs}秒"
        elif minutes > 0:
            return f"{minutes}分钟{secs}秒"
        else:
            return f"{secs}秒"

    async def send_notification(self, notification_type: str, **kwargs) -> bool:
        """发送邮件通知 - 根据不同类型"""
        current_time = get_china_timestamp()
        record_id = kwargs.get('record_id')

        # 检查是否启用对应类型的通知
        enable_live_start = get_config("email", "enable_live_start", default=True)
        enable_live_end = get_config("email", "enable_live_end", default=True)
        enable_monitor_start = get_config("email", "enable_monitor_start", default=True)

        # 开播/关播/监控开始通知检查开关
        if notification_type == "live_start" and not enable_live_start:
            logging.info(f"⏭️ 开播邮件提醒已关闭")
            return False
        if notification_type == "live_end" and not enable_live_end:
            logging.info(f"⏭️ 关播邮件提醒已关闭")
            return False
        if notification_type == "monitor_start" and not enable_monitor_start:
            logging.info(f"⏭️ 监控开始邮件提醒已关闭")
            return False

        # 关键词通知检查开关（默认开启）
        if notification_type == "keyword":
            # 关键词通知默认开启
            pass

        # 关键词通知保持原有冷却逻辑
        if notification_type == "keyword" and current_time - self.last_email_time < self.email_cooldown:
            remaining = self.email_cooldown - (current_time - self.last_email_time)
            logging.info(f"⏰ 关键词通知冷却中，还需{int(remaining)}秒")
            # 冷却期间不发送邮件，但更新状态为冷却中（可视为成功的一种）
            if record_id:
                data_manager.update_email_status(record_id, 'success')
                logging.info(f"💾 更新记录 {record_id} 邮件状态为成功（冷却期间）")
            return False

        try:
            room_info = kwargs.get('room_info', {})
            china_time = get_china_time()
            room_title = room_info.get('title', '未知标题') if room_info else '未知标题'

            if notification_type == "keyword":
                subject = f"【鸽切监控】检测到切片需求关键词！"
                username = kwargs.get('username', '未知用户')
                matched_keyword = kwargs.get('matched_keyword', '鸽切')

                # 计算直播经过时间
                live_duration = "未知"
                # 优先使用开播时间，如果没有则使用监控开始时间
                reference_time = self.live_start_time if self.live_start_time and self.live_start_time > 0 else self.monitor_start_time
                if reference_time and reference_time > 0:
                    duration_seconds = current_time - reference_time
                    hours = int(duration_seconds // 3600)
                    minutes = int((duration_seconds % 3600) // 60)
                    seconds = int(duration_seconds % 60)
                    live_duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                content = f"""检测到切片需求关键词！

直播间：{room_title}
发送人：{username}
直播经过时间：{live_duration}
检测时间：{china_time}

关键词：{matched_keyword}
请检查相关直播片段
"""

            elif notification_type == "live_start":
                subject = f"【开播提醒】{room_title} 开播啦！"
                online = room_info.get('online', 0) if room_info else 0

                content = f"""直播间已开播！

直播间：{room_title}
开播时间：{china_time}
当前在线：{online} 人

请准备开始监控~
"""

            elif notification_type == "live_end":
                subject = f"【关播提醒】{room_title} 已关播"
                # 计算直播时长
                live_duration = "未知"
                if self.live_start_time and self.live_start_time > 0:
                    duration_seconds = current_time - self.live_start_time
                    hours = int(duration_seconds // 3600)
                    minutes = int((duration_seconds % 3600) // 60)
                    seconds = int(duration_seconds % 60)
                    live_duration = f"{hours}小时{minutes}分钟"

                content = f"""直播间已关播！

直播间：{room_title}
关播时间：{china_time}
直播时长：{live_duration}

本场统计：弹幕 {self.total_danmaku} 条，关键词匹配 {self.keyword_count} 次
"""

            elif notification_type == "monitor_start":
                subject = f"【监控开始】{room_title} 鸽切监控系统已启动"
                live_status_text = "直播中" if room_info.get('live_status') == 1 else "未开播"
                online = room_info.get('online', 0) if room_info else 0

                content = f"""鸽切监控系统已启动！

直播间：{room_title}
直播状态：{live_status_text}
当前在线：{online} 人
启动时间：{china_time}

正在监控弹幕中的关键词...
"""

            else:
                logging.error(f"未知的通知类型: {notification_type}")
                return False

            # 发送邮件
            if self.email_notifier.send_email(subject, content):
                if notification_type == "keyword":
                    self.last_email_time = current_time
                # 更新数据库中的邮件状态为成功
                if record_id:
                    data_manager.update_email_status(record_id, 'success')
                    logging.info(f"💾 更新记录 {record_id} 邮件状态为成功")
                return True
            else:
                # 更新数据库中的邮件状态为失败
                if record_id:
                    data_manager.update_email_status(record_id, 'failed')
                    logging.info(f"💾 更新记录 {record_id} 邮件状态为失败")
            return False

        except Exception as e:
            logging.error(f"❌ 构建邮件内容失败: {e}")
            # 发生异常时也更新为失败状态
            if record_id:
                data_manager.update_email_status(record_id, 'failed')
            return False
    


    async def on_danmaku(self, event):
        """处理弹幕消息 - 只要连接成功就处理,不依赖直播状态"""
        # 移除直播状态检查,确保即使没有收到直播开始事件也能监控弹幕
        if not self.is_monitoring:
            logging.warning("监控未启动,跳过弹幕处理")
            return
        
        try:
            # 更新心跳时间（每次收到弹幕都视为活跃连接）
            self.last_heartbeat_time = get_china_timestamp()
            
            # 提取弹幕信息
            info = event['data']['info']
            message_content = info[1]  # 弹幕内容
            user_info = info[2]  # 用户信息
            user_name = user_info[1]  # 用户名
            timestamp = get_china_timestamp()
            
            self.total_danmaku += 1
            
            # 弹幕分析 - 对所有弹幕进行分析
            danmaku_analyzer = get_danmaku_analyzer()
            analysis = danmaku_analyzer.analyze_danmaku(
                username=user_name,
                content=message_content,
                timestamp=timestamp,
                room_id=self.room_id
            )
            
            # 构建分析事件数据
            analysis_event_data = {
                'danmaku_id': analysis.danmaku_id,
                'username': analysis.username,
                'content': analysis.content,
                'timestamp': analysis.timestamp,
                'sentiment_score': analysis.sentiment_score,
                'sentiment_type': analysis.sentiment_type.value,
                'keywords': analysis.keywords,
                'word_count': analysis.word_count,
                'is_duplicate': analysis.is_duplicate,
                'duplicate_count': analysis.duplicate_count,
                'duplicate_group_id': analysis.duplicate_group_id,
                'is_suspicious': analysis.is_suspicious,
                'suspicious_reason': analysis.suspicious_reason
            }
            
            # 广播弹幕分析事件
            broadcast_event('danmaku_analysis', analysis_event_data)
            
            # 如果是可疑行为，记录日志并广播警告事件
            if analysis.is_suspicious:
                logging.warning(f"⚠️ 检测到可疑弹幕行为: 用户{user_name} - 原因: {analysis.suspicious_reason}")
                suspicious_event_data = {
                    'username': user_name,
                    'content': message_content,
                    'reason': analysis.suspicious_reason,
                    'timestamp': timestamp,
                    'sentiment_score': analysis.sentiment_score,
                    'duplicate_count': analysis.duplicate_count
                }
                broadcast_event('suspicious_behavior', suspicious_event_data)
            
            # 使用包含匹配检查是否包含目标关键词
            if self.keyword_matcher.contains_keyword(message_content):
                self.keyword_count += 1

                # 获取匹配的具体关键词
                matched_keyword = self.keyword_matcher.get_matched_keyword(message_content)

                # 保存数据到数据库
                room_title = self.room_info_cache.get('title', '未知标题') if self.room_info_cache else '未知标题'
                record_id = data_manager.add_geqie_record(user_name, message_content, self.room_id, room_title)
                # 安全记录日志，避免泄露敏感信息
                safe_message = message_content
                if len(safe_message) > 50:
                    safe_message = safe_message[:47] + "..."

                logging.info(f"保存鸽切数据: 用户{user_name[:10]}... - '{safe_message}', 记录ID: {record_id}")

                # 计算直播经过时间
                live_duration = None
                reference_time = self.live_start_time if self.live_start_time and self.live_start_time > 0 else self.monitor_start_time
                if reference_time and reference_time > 0:
                    duration_seconds = get_china_timestamp() - reference_time
                    hours = int(duration_seconds // 3600)
                    minutes = int((duration_seconds % 3600) // 60)
                    seconds = int(duration_seconds % 60)
                    live_duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                # 触发自动切片
                if AUTO_CLIP_AVAILABLE and self.auto_clip_trigger:
                    try:
                        clip_request = self.auto_clip_trigger.trigger_clip(
                            room_id=self.room_id,
                            room_title=room_title,
                            keyword=matched_keyword,
                            username=user_name,
                            danmaku_content=message_content,
                            danmaku_timestamp=timestamp,
                            video_source=self.video_source_path,
                            live_duration=live_duration,
                            metadata={
                                'record_id': record_id,
                                'room_info': self.room_info_cache
                            }
                        )
                        
                        if clip_request:
                            logging.info(f"🎬 自动切片请求已创建: {clip_request.request_id}")
                            # 将切片请求信息添加到事件数据中
                            keyword_event_data = {
                                'user_name': user_name,
                                'message_content': message_content,
                                'matched_keyword': matched_keyword,
                                'room_info': self.room_info_cache,
                                'record_id': record_id,
                                'timestamp': get_china_timestamp(),
                                'live_duration': live_duration,
                                'clip_request': {
                                    'request_id': clip_request.request_id,
                                    'status': clip_request.status.value,
                                    'start_offset_seconds': clip_request.start_offset_seconds,
                                    'duration_seconds': clip_request.duration_seconds
                                }
                            }
                        else:
                            # 切片被冷却或去重跳过
                            keyword_event_data = {
                                'user_name': user_name,
                                'message_content': message_content,
                                'matched_keyword': matched_keyword,
                                'room_info': self.room_info_cache,
                                'record_id': record_id,
                                'timestamp': get_china_timestamp(),
                                'live_duration': live_duration,
                                'clip_skipped': True,
                                'clip_skip_reason': '冷却或去重'
                            }
                    except Exception as e:
                        logging.error(f"触发自动切片失败: {e}")
                        keyword_event_data = {
                            'user_name': user_name,
                            'message_content': message_content,
                            'matched_keyword': matched_keyword,
                            'room_info': self.room_info_cache,
                            'record_id': record_id,
                            'timestamp': get_china_timestamp(),
                            'live_duration': live_duration,
                            'clip_error': str(e)
                        }
                else:
                    # 自动切片不可用时
                    keyword_event_data = {
                        'user_name': user_name,
                        'message_content': message_content,
                        'matched_keyword': matched_keyword,
                        'room_info': self.room_info_cache,
                        'record_id': record_id,
                        'timestamp': get_china_timestamp(),
                        'live_duration': live_duration
                    }

                # 发送事件通知前端（WebSocket）
                broadcast_event('keyword_match', keyword_event_data)
                logging.info(f"发送关键词匹配事件: {user_name} - {message_content} (WebSocket)")

                # 使用缓存的直播间信息发送通知
                if self.room_info_cache:
                    email_success = await self.send_notification("keyword",
                                         username=user_name,
                                         content=message_content,
                                         matched_keyword=matched_keyword,
                                         room_info=self.room_info_cache,
                                         record_id=record_id)
                else:
                    logging.warning("无法获取直播间信息，邮件通知可能不完整")
                    # 如果缓存为空，尝试重新获取一次
                    self.room_info_cache = await self.get_room_info()
                    if self.room_info_cache:
                        email_success = await self.send_notification("keyword",
                                             username=user_name,
                                             content=message_content,
                                             matched_keyword=matched_keyword,
                                             room_info=self.room_info_cache,
                                             record_id=record_id)
                    else:
                        # 如果仍然无法获取，发送默认信息
                        email_success = await self.send_notification("keyword",
                                             username=user_name,
                                             content=message_content,
                                             matched_keyword=matched_keyword,
                                             room_info={},
                                             record_id=record_id)
                    
        except (KeyError, IndexError) as e:
            logging.warning(f"弹幕数据结构异常: {e}")
        except Exception as e:
            logging.error(f"❌ 处理弹幕时出错: {e}")
            # 记录更详细的错误信息用于调试
            import traceback
            logging.debug(f"详细错误堆栈: {traceback.format_exc()}")

    async def on_live_start(self, event):
        """处理直播开始事件"""
        logging.info("检测到直播开始事件")
        self.is_live = True
        self.is_monitoring = True

        # 记录开播时间（中国时区时间戳）
        self.live_start_time = get_china_timestamp()

        # 重置统计
        self.keyword_count = 0
        self.total_danmaku = 0

        # 使用已缓存的直播间信息
        if self.room_info_cache:
            logging.info(f"直播已开始: {self.room_info_cache.get('title', '未知标题')}")
            logging.info(f"开播时间: {get_china_time()}")

            # 发送直播开始事件
            broadcast_event('live_start', self.room_info_cache)
            logging.info("发送直播开始事件")

            # 发送开播邮件通知
            await self.send_notification("live_start", room_info=self.room_info_cache)
        else:
            logging.warning("无法获取直播间信息，但仍将开始监控")

        logging.info("开始监控弹幕中的关键词（包含匹配）...")

    async def on_live_end(self, event):
        """处理直播结束事件"""
        logging.info("检测到直播结束事件")

        # 停止监控
        self.is_live = False
        self.is_monitoring = False

        # 停止自动切片触发器
        if AUTO_CLIP_AVAILABLE and self.auto_clip_trigger:
            try:
                await self.auto_clip_trigger.stop()
                logging.info("🛑 自动切片触发器已停止")
            except Exception as e:
                logging.error(f"自动切片触发器停止失败: {e}")

        # 输出最终统计
        if self.live_start_time:
            duration = get_china_timestamp() - self.live_start_time
            logging.info(f"直播时长: {self.format_duration(duration)}")

        # 发送直播结束事件
        if self.room_info_cache:
            broadcast_event('live_end', self.room_info_cache)
            logging.info("发送直播结束事件")

            # 发送关播邮件通知
            await self.send_notification("live_end", room_info=self.room_info_cache)

        logging.info(f"最终统计: 弹幕{self.total_danmaku}条, 关键词匹配{self.keyword_count}次")
        logging.info("停止监控弹幕，等待下次开播...")

    async def on_connect(self):
        """处理连接成功事件"""
        logging.info("弹幕服务器连接成功")

        # 连接成功后立即获取并缓存直播间信息
        logging.info("正在获取直播间信息...")
        self.room_info_cache = await self.get_room_info()

        # 详细调试信息
        if self.room_info_cache:
            title = self.room_info_cache.get('title', '未知标题')
            live_status = self.room_info_cache.get('live_status', 0)
            api_source = self.room_info_cache.get('api_source', '未知API')

            logging.info(f"直播间信息已缓存 (来源: {api_source})")
            logging.info(f"   标题: {title}")
            logging.info(f"   直播状态: {'直播中' if live_status == 1 else '未开播'}")
            logging.info(f"   在线人数: {self.room_info_cache.get('online', 0)}")

            # 【重要修改】无论直播状态如何,立即开始监控弹幕
            # 确保即使错过直播开始事件,也能捕获到弹幕中的关键词
            logging.info("🎯 立即开始监控弹幕中的关键词（包含匹配）...")
            self.is_monitoring = True
            self.is_live = True  # 标记为活跃状态,确保弹幕能被处理

            # 启动自动切片触发器
            if AUTO_CLIP_AVAILABLE and self.auto_clip_trigger:
                try:
                    await self.auto_clip_trigger.start()
                    logging.info("✅ 自动切片触发器已启动")
                except Exception as e:
                    logging.error(f"自动切片触发器启动失败: {e}")

            # 发送监控开始邮件提醒
            await self.send_notification("monitor_start", room_info=self.room_info_cache)

            if live_status == 1:
                logging.info("检测到当前正在直播中")
                # 记录开播时间（中国时区时间戳）
                if self.live_start_time is None:
                    self.live_start_time = get_china_timestamp()
                # 开播状态下发送监控开始邮件提醒
                await self.send_notification("monitor_start", room_info=self.room_info_cache)
            else:
                logging.info("直播间当前未开播,但仍开始监控弹幕...")
            
            # 记录监控开始时间（用于邮件通知中计算经过时间的备用）
            if self.monitor_start_time is None:
                self.monitor_start_time = get_china_timestamp()
        else:
            logging.error("无法获取直播间信息")
            logging.info("可能的原因:")
            logging.info("   1. 直播间ID不正确")
            logging.info("   2. 网络连接问题")
            logging.info("   3. B站API接口变更")
            logging.info("   4. Cookie认证信息过期")
            logging.info("建议:")
            logging.info("   1. 检查房间ID是否正确")
            logging.info("   2. 尝试在浏览器中访问直播间确认存在")
            logging.info("   3. 更新Cookie认证信息")
            # 提供一个默认的直播间信息缓存，避免后续调用.get()方法出错
            self.room_info_cache = {
                'title': '未知标题',
                'live_status': 0,
                'online': 0,
                'room_id': self.room_id,
                'api_source': '连接时获取失败'
            }
            # 即使获取失败也开始监控
            self.is_monitoring = True
            self.is_live = True
            
            # 启动自动切片触发器（即使没有房间信息也启动）
            if AUTO_CLIP_AVAILABLE and self.auto_clip_trigger:
                try:
                    await self.auto_clip_trigger.start()
                    logging.info("✅ 自动切片触发器已启动")
                except Exception as e:
                    logging.error(f"自动切片触发器启动失败: {e}")
            
            logging.warning("虽然获取直播间信息失败,但仍然开始监控弹幕")

    async def on_disconnect(self):
        """处理断开连接事件"""
        logging.warning("弹幕服务器断开连接")
        self.is_monitoring = False

        # 触发重连机制
        await self.handle_reconnect()

    async def on_error(self, e):
        """处理错误事件"""
        logging.error(f"弹幕服务器错误: {e}")

        # 如果是心跳超时错误，触发重连
        if "心跳响应超时" in str(e):
            logging.warning("检测到心跳响应超时，触发重连机制")
            await self.handle_reconnect()

    async def connect_danmaku(self):
        """连接B站弹幕服务器并注册事件处理器"""
        logging.info("正在连接B站弹幕服务器...")

        try:
            # 【重要修改】连接前立即开始监控,确保不依赖CONNECT事件
            # 这样即使CONNECT事件没有触发,也能正常监控弹幕
            logging.info("🎯 预设监控状态为启用,确保弹幕能被处理...")
            self.is_monitoring = True
            self.is_live = True

            # 注册事件处理器
            # 弹幕消息
            self.danmaku.add_event_listener('DANMU_MSG', self.on_danmaku)
            # 直播开始事件
            self.danmaku.add_event_listener('LIVE', self.on_live_start)
            # 直播结束事件（PREPARING状态）
            self.danmaku.add_event_listener('PREPARING', self.on_live_end)
            # 连接状态
            self.danmaku.add_event_listener('CONNECT', self.on_connect)
            self.danmaku.add_event_listener('DISCONNECT', self.on_disconnect)
            self.danmaku.add_event_listener('ERROR', self.on_error)

            logging.info("事件处理器注册完成")

            # 连接弹幕服务器
            logging.info("开始监听弹幕和直播状态...")
            await self.danmaku.connect()
            
            # 连接成功后启动心跳检查任务
            if not hasattr(self, '_heartbeat_task') or self._heartbeat_task is None or self._heartbeat_task.done():
                self._heartbeat_task = asyncio.create_task(self.check_heartbeat())
                logging.info("✅ 心跳检查任务已启动")

        except Exception as e:
            logging.error(f"弹幕连接失败: {e}")

    async def handle_reconnect(self):
        """处理重连逻辑"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logging.error(f"已达到最大重连次数({self.max_reconnect_attempts})，停止重连")
            return

        self.reconnect_attempts += 1
        delay = self.reconnect_delay * self.reconnect_attempts  # 指数退避

        logging.info(f"尝试第{self.reconnect_attempts}次重连，等待{delay}秒...")
        await asyncio.sleep(delay)

        try:
            # 清理现有连接
            await self.cleanup()

            # 重新连接
            logging.info("正在重新连接弹幕服务器...")
            await self.connect_danmaku()

            # 重置重连计数器
            self.reconnect_attempts = 0
            logging.info("重连成功")

        except Exception as e:
            logging.error(f"重连失败: {e}")
            # 继续重连
            await self.handle_reconnect()
    
    async def check_heartbeat(self):
        """检查心跳状态"""
        while True:
            current_time = get_china_timestamp()
            time_since_last_heartbeat = current_time - self.last_heartbeat_time
            
            if time_since_last_heartbeat > self.heartbeat_timeout:
                logging.warning(f"💓 心跳超时({int(time_since_last_heartbeat)}秒)，触发重连")
                await self.handle_reconnect()
                break
                
            # 每30秒检查一次
            await asyncio.sleep(30)
    
    async def cleanup(self):
        """清理资源"""
        try:
            # 取消心跳检查任务
            if hasattr(self, '_heartbeat_task') and self._heartbeat_task and not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass
                logging.info("心跳检查任务已取消")
            
            if hasattr(self, 'danmaku'):
                # 取消所有事件监听器
                try:
                    self.danmaku.remove_event_listener('DANMU_MSG', self.on_danmaku)
                    self.danmaku.remove_event_listener('LIVE', self.on_live_start)
                    self.danmaku.remove_event_listener('PREPARING', self.on_live_end)
                    self.danmaku.remove_event_listener('CONNECT', self.on_connect)
                    self.danmaku.remove_event_listener('DISCONNECT', self.on_disconnect)
                    self.danmaku.remove_event_listener('ERROR', self.on_error)
                    logging.info("已移除所有事件监听器")
                except Exception as e:
                    logging.warning(f"移除事件监听器时出错: {e}")

                # 停止监控状态
                self.is_monitoring = False
                self.is_live = False

                # 断开弹幕连接
                try:
                    await self.danmaku.disconnect()
                    logging.info("已断开弹幕连接")
                except Exception as e:
                    # 忽略断开连接时的网络错误（如DNS解析失败）
                    if "name resolution" in str(e).lower() or "dns" in str(e).lower():
                        logging.info(f"断开连接时遇到网络问题（可忽略）: {e}")
                    else:
                        logging.error(f"断开弹幕连接时出错: {e}")
        except Exception as e:
            logging.error(f"清理资源时出错: {e}")


# ============================================================================
# 多房间监控管理器
# ============================================================================

class MultiRoomMonitorManager:
    """多房间监控管理器 - 同时管理多个B站直播间的弹幕监控"""
    
    def __init__(self):
        self.monitors: Dict[int, BilibiliDanmakuMonitor] = {}
        self.room_nicknames: Dict[int, str] = {}
        self.room_tasks: Dict[int, asyncio.Task] = {}
        self._started = False
        self._lock = threading.Lock()
        
        # 全局统计信息
        self._global_stats = {
            'total_danmaku': 0,
            'total_keyword_matches': 0,
            'active_rooms': 0
        }
    
    def get_monitor(self, room_id: int) -> Optional[BilibiliDanmakuMonitor]:
        """获取指定房间的监控实例"""
        return self.monitors.get(room_id)
    
    def get_all_monitors(self) -> Dict[int, BilibiliDanmakuMonitor]:
        """获取所有监控实例"""
        return self.monitors.copy()
    
    def get_room_info(self, room_id: int) -> Optional[Dict]:
        """获取指定房间的信息"""
        monitor = self.get_monitor(room_id)
        if monitor and monitor.room_info_cache:
            return {
                'room_id': room_id,
                'nickname': self.room_nicknames.get(room_id, f"直播间 {room_id}"),
                'title': monitor.room_info_cache.get('title', '未知标题'),
                'live_status': monitor.room_info_cache.get('live_status', 0),
                'online': monitor.room_info_cache.get('online', 0),
                'is_live': monitor.is_live,
                'is_monitoring': monitor.is_monitoring,
                'keyword_count': monitor.keyword_count,
                'total_danmaku': monitor.total_danmaku,
                'live_start_time': monitor.live_start_time
            }
        return None
    
    def get_all_rooms_info(self) -> List[Dict]:
        """获取所有房间的信息列表"""
        rooms_info = []
        for room_id in self.monitors:
            info = self.get_room_info(room_id)
            if info:
                rooms_info.append(info)
        return rooms_info
    
    def get_global_stats(self) -> Dict:
        """获取全局统计信息"""
        total_danmaku = 0
        total_keyword = 0
        active_rooms = 0
        
        for monitor in self.monitors.values():
            total_danmaku += monitor.total_danmaku
            total_keyword += monitor.keyword_count
            if monitor.is_live:
                active_rooms += 1
        
        return {
            'total_danmaku': total_danmaku,
            'total_keyword_matches': total_keyword,
            'active_rooms': active_rooms,
            'total_rooms': len(self.monitors)
        }
    
    def get_room_comparison(self) -> List[Dict]:
        """获取房间对比数据（用于对比分析）"""
        comparison = []
        for room_id, monitor in self.monitors.items():
            comparison.append({
                'room_id': room_id,
                'nickname': self.room_nicknames.get(room_id, f"直播间 {room_id}"),
                'is_live': monitor.is_live,
                'keyword_count': monitor.keyword_count,
                'total_danmaku': monitor.total_danmaku,
                'keyword_ratio': (
                    monitor.keyword_count / monitor.total_danmaku 
                    if monitor.total_danmaku > 0 else 0
                )
            })
        return comparison
    
    async def add_room(self, room_id: int, nickname: str = None, 
                       email_config: Dict = None, 
                       credential_config: Dict = None) -> bool:
        """添加一个新房间进行监控"""
        with self._lock:
            if room_id in self.monitors:
                logging.warning(f"房间 {room_id} 已在监控中")
                return False
            
            if email_config is None:
                email_config = get_config("email")
            if credential_config is None:
                credential_config = get_config("credential")
            
            # 创建监控实例
            monitor = BilibiliDanmakuMonitor(room_id, email_config, credential_config)
            self.monitors[room_id] = monitor
            self.room_nicknames[room_id] = nickname or f"直播间 {room_id}"
            
            logging.info(f"✅ 已添加房间监控: {room_id} ({self.room_nicknames[room_id]})")
            return True
    
    async def remove_room(self, room_id: int) -> bool:
        """移除一个房间的监控"""
        with self._lock:
            if room_id not in self.monitors:
                return False
            
            # 取消任务
            if room_id in self.room_tasks and not self.room_tasks[room_id].done():
                self.room_tasks[room_id].cancel()
            
            # 清理资源
            monitor = self.monitors[room_id]
            await monitor.cleanup()
            
            # 移除实例
            del self.monitors[room_id]
            del self.room_nicknames[room_id]
            if room_id in self.room_tasks:
                del self.room_tasks[room_id]
            
            logging.info(f"✅ 已移除房间监控: {room_id}")
            return True
    
    async def start_monitor_for_room(self, room_id: int):
        """启动指定房间的监控"""
        monitor = self.get_monitor(room_id)
        if not monitor:
            logging.error(f"房间 {room_id} 不存在")
            return
        
        try:
            # 获取直播间信息
            logging.info(f"正在初始化房间 {room_id} 的直播间信息...")
            monitor.room_info_cache = await monitor.get_room_info()
            if not monitor.room_info_cache:
                monitor.room_info_cache = {
                    'title': '未知标题',
                    'live_status': 0,
                    'online': 0,
                    'room_id': room_id,
                    'api_source': '初始化失败'
                }
            
            # 连接弹幕服务器
            await monitor.connect_danmaku()
            
            # 保持监控运行
            while not shutdown_requested:
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            logging.info(f"房间 {room_id} 的监控任务被取消")
        except Exception as e:
            logging.error(f"房间 {room_id} 监控异常: {e}")
        finally:
            await monitor.cleanup()
    
    async def start_all(self):
        """启动所有已配置房间的监控"""
        if self._started:
            return
        
        # 从配置获取启用的房间
        enabled_rooms = get_enabled_rooms() if is_multi_room_enabled() else []
        
        # 如果没有启用多房间或没有配置房间，使用默认房间
        if not enabled_rooms:
            default_room_id = get_config("bilibili", "room_id", default=22391541)
            enabled_rooms = [{
                'room_id': default_room_id,
                'nickname': '默认直播间',
                'enabled': True
            }]
        
        # 添加所有房间
        for room_config in enabled_rooms:
            await self.add_room(
                room_id=room_config['room_id'],
                nickname=room_config.get('nickname')
            )
        
        # 为每个房间创建监控任务
        for room_id in self.monitors:
            task = asyncio.create_task(self.start_monitor_for_room(room_id))
            self.room_tasks[room_id] = task
        
        self._started = True
        logging.info(f"✅ 多房间监控已启动，共 {len(self.monitors)} 个房间")
    
    async def stop_all(self):
        """停止所有房间的监控"""
        # 取消所有任务
        for room_id, task in self.room_tasks.items():
            if not task.done():
                task.cancel()
        
        # 等待所有任务完成
        for task in self.room_tasks.values():
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # 清理所有监控实例
        for monitor in self.monitors.values():
            await monitor.cleanup()
        
        self.monitors.clear()
        self.room_nicknames.clear()
        self.room_tasks.clear()
        self._started = False
        
        logging.info("✅ 多房间监控已停止")


# 全局多房间监控管理器实例
_multi_room_manager: Optional[MultiRoomMonitorManager] = None

def get_multi_room_manager() -> MultiRoomMonitorManager:
    """获取全局多房间监控管理器实例"""
    global _multi_room_manager
    if _multi_room_manager is None:
        _multi_room_manager = MultiRoomMonitorManager()
    return _multi_room_manager


async def start_multi_room_monitor():
    """启动多房间监控系统"""
    manager = get_multi_room_manager()
    await manager.start_all()
    
    # 保持监控运行
    future = asyncio.Future()
    if not hasattr(start_multi_room_monitor, '_active_task'):
        start_multi_room_monitor._active_task = future
    
    try:
        await future
    except asyncio.CancelledError:
        logging.info("多房间监控任务被取消")
        await manager.stop_all()


async def start_danmaku_monitor():
    """启动弹幕监控系统"""
    monitor = None
    try:
        # 从配置文件中获取参数
        room_id = get_config("bilibili", "room_id", default=22391541)
        email_config = get_config("email")
        credential_config = get_config("credential")

        logging.info("启动B站弹幕监控系统（鸽切关键词版）")
        logging.info("=" * 50)

        # 创建监控实例（会在构造函数中输出详细的初始化信息）
        monitor = BilibiliDanmakuMonitor(room_id, email_config, credential_config)
        
        # 保存到全局变量，供 API 使用
        global _danmaku_monitor
        _danmaku_monitor = monitor

        # 在连接弹幕服务器前先获取一次直播间信息
        logging.info("正在初始化获取直播间信息...")
        monitor.room_info_cache = await monitor.get_room_info()
        if monitor.room_info_cache:
            title = monitor.room_info_cache.get('title', '未知标题')
            live_status = monitor.room_info_cache.get('live_status', 0)
            logging.info(f"初始化直播间信息已缓存: {title}")
            logging.info(f"当前直播状态: {'直播中' if live_status == 1 else '未开播'}")
        else:
            logging.warning("初始化获取直播间信息失败")
            # 提供一个默认的直播间信息缓存，避免后续调用.get()方法出错
            monitor.room_info_cache = {
                'title': '未知标题',
                'live_status': 0,
                'online': 0,
                'room_id': room_id,
                'api_source': '初始化失败'
            }

        # 连接弹幕服务器（会自动检测开播状态）
        await monitor.connect_danmaku()

        # 保持监控运行，使用一个可取消的任务
        future = asyncio.Future()
        # 将future添加到全局任务列表，方便取消
        if not hasattr(start_danmaku_monitor, '_active_task'):
            start_danmaku_monitor._active_task = future
        await future

    except asyncio.CancelledError:
        logging.info("弹幕监控任务被取消")
    except Exception as e:
        logging.error(f"弹幕监控初始化失败: {e}")
    finally:
        # 清理资源
        if monitor:
            await monitor.cleanup()

def start_web_app():
    """启动Web应用（支持WebSocket）"""
    logging.info("启动Web应用服务（支持WebSocket实时通信）")
    
    # 初始化独立在线聊天室模块
    live_chatroom.init_live_chatroom()
    
    # 使用SocketIO启动应用，支持WebSocket
    try:
        # 检查全局退出标志
        def should_stop():
            return getattr(start_web_app, '_stop_requested', False) or getattr(signal_handler, '_already_called', False)
        
        # 在单独的线程中运行Web服务，以便可以检查退出标志
        import threading
        import time
        
        def run_web_server():
            # 配置Werkzeug日志，抑制无用的断言错误
            import logging
            werkzeug_log = logging.getLogger('werkzeug')

            # 创建自定义过滤器，抑制 write() before start_response 错误
            class WerkzeugErrorFilter(logging.Filter):
                def filter(self, record):
                    # 过滤掉 write() before start_response 错误
                    if 'write() before start_response' in str(record.getMessage()):
                        return False
                    return True

            werkzeug_log.addFilter(WerkzeugErrorFilter())
            werkzeug_log.setLevel(logging.WARNING)

            socketio.run(
                app,
                host=get_config("app", "host", default="0.0.0.0"),
                port=get_config("app", "port", default=5000),
                debug=get_config("app", "debug", default=False),
                use_reloader=False,  # 禁用自动重载，避免与asyncio冲突
                allow_unsafe_werkzeug=True,
                log_output=False  # 禁用Werkzeug的日志输出
            )
        
        web_thread = threading.Thread(target=run_web_server, daemon=True)
        web_thread.start()
        
        # 主线程等待Web线程或退出信号
        while web_thread.is_alive():
            if should_stop():
                logging.info("收到退出信号，正在关闭Web服务...")
                # 这里无法直接停止Flask服务器，需要等待线程自然结束
                break
            time.sleep(0.1)

    except KeyboardInterrupt:
        logging.info("Web服务收到中断信号，正在关闭...")
        # 设置停止标志
        start_web_app._stop_requested = True

import signal
import concurrent.futures

def global_exception_handler(loop, context):
    """全局异常处理器 - 抑制 bilibili_api 内部的心跳任务异常"""
    message = context.get('message', '')
    exception = context.get('exception')

    # 忽略 bilibili_api 内部的心跳任务异常（DNS 解析失败等）
    if 'Task exception was never retrieved' in message:
        if exception and ('dns' in str(exception).lower() or
                          'name resolution' in str(exception).lower() or
                          'ClientConnector' in str(exception) or
                          'Timeout context manager' in str(exception)):
            logging.debug(f"忽略 bilibili_api 内部心跳任务异常: {exception}")
            return

    # 其他异常正常记录
    if exception:
        logging.error(f"未处理的异步异常: {exception}")
    else:
        logging.error(f"未处理的异步错误: {message}")

async def main():
    """主函数 - 同时启动弹幕监控和Web应用"""
    # 设置全局异常处理器
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(global_exception_handler)

    # 创建任务列表用于追踪所有异步任务
    active_tasks = []
    try:
        logging.info("启动集成系统 - 弹幕监控 + Web展示")
        logging.info("=" * 60)

        # 启动日志轮换任务
        log_rotation = asyncio.create_task(log_rotation_task())
        active_tasks.append(log_rotation)

        # 创建弹幕监控任务（根据配置选择单房间或多房间）
        if is_multi_room_enabled():
            logging.info("📌 启用多房间监控模式")
            danmaku_task = asyncio.create_task(start_multi_room_monitor())
        else:
            logging.info("📌 使用单房间监控模式（向后兼容）")
            danmaku_task = asyncio.create_task(start_danmaku_monitor())
        active_tasks.append(danmaku_task)

        # 在单独的线程中运行 Web 应用（不同步等待）
        import threading
        web_thread = threading.Thread(target=start_web_app, daemon=True)
        web_thread.start()
        logging.info("Web服务已在后台线程启动")

        # 等待弹幕监控任务完成或收到退出信号
        try:
            # 使用 gather 等待弹幕监控任务
            # 注意：不等待 web_thread，因为它应该一直运行
            await danmaku_task
        except asyncio.CancelledError:
            logging.info("弹幕监控任务被取消")
        except Exception as e:
            logging.error(f"弹幕监控任务异常: {e}")

    except KeyboardInterrupt:
        logging.info("用户中断程序")
        # 取消所有任务
        for task in active_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
    except Exception as e:
        logging.error(f"程序异常退出: {e}")
        # 取消所有任务
        for task in active_tasks:
            if not task.done():
                task.cancel()

def signal_handler(signum, frame):
    """信号处理函数 - 优雅关闭程序"""
    logging.info("收到中断信号，正在优雅关闭...")

    # 设置全局退出标志
    global shutdown_requested
    shutdown_requested = True

    # 如果这是第一次收到信号，触发KeyboardInterrupt
    if not hasattr(signal_handler, '_already_called'):
        signal_handler._already_called = True
        raise KeyboardInterrupt
    else:
        # 第二次收到信号，强制退出
        logging.warning("强制退出程序")
        import os
        os._exit(1)

# 全局关闭标志
shutdown_requested = False

# 全局日志处理器和当前日志日期
_file_handler = None
_current_log_date = None

def rotate_log_file():
    """切换日志文件 - 当日期变化时自动切换"""
    global _file_handler, _current_log_date

    # 获取当前日期
    china_tz = pytz.timezone(get_config("app", "timezone", default="Asia/Shanghai"))
    current_date = datetime.now(china_tz).strftime('%Y-%m-%d')

    # 如果日期没有变化,无需切换
    if _current_log_date == current_date:
        return

    logging.info(f"📅 日期变更,切换日志文件: {_current_log_date} -> {current_date}")

    # 移除旧的文件处理器
    if _file_handler:
        logging.getLogger().removeHandler(_file_handler)
        _file_handler.close()
        logging.info(f"✓ 已关闭旧日志文件: geqie-monitor-{_current_log_date}.log")

    # 创建新的日志文件
    log_dir = "log"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"geqie-monitor-{current_date}.log")

    # 创建新的文件处理器
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    _file_handler = logging.FileHandler(log_file, encoding='utf-8')
    _file_handler.setLevel(logging.INFO)
    _file_handler.setFormatter(formatter)

    # 添加到日志记录器
    logging.getLogger().addHandler(_file_handler)

    # 更新当前日期
    _current_log_date = current_date

    logging.info(f"✓ 已创建新日志文件: geqie-monitor-{current_date}.log")
    logging.info(f"📝 日志文件路径: {os.path.abspath(log_file)}")

async def log_rotation_task():
    """日志轮换任务 - 每分钟检查一次日期变化"""
    while not shutdown_requested:
        try:
            rotate_log_file()
            await asyncio.sleep(60)  # 每分钟检查一次
        except Exception as e:
            logging.error(f"日志轮换任务出错: {e}")
            await asyncio.sleep(60)  # 出错后继续

if __name__ == "__main__":
    # 初始化日志系统
    _file_handler, _current_log_date = setup_logging()

    # 预计算所有静态文件哈希（永久缓存，加速渲染）
    _precompute_static_hashes()

    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # 创建日志轮换任务
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("用户中断程序")
    except Exception as e:
        logging.error(f"程序异常退出: {e}")
    finally:
        # 关闭日志文件处理器
        if _file_handler:
            _file_handler.close()
            logging.info("📝 日志文件已关闭")
        logging.info("程序已完全退出")