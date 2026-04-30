#!/usr/bin/env python3
"""
数据库连接池 - 复用数据库连接，提升性能
"""
import sqlite3
import threading
import time
from typing import Optional, Callable, Any
from contextlib import contextmanager
import logging


class ConnectionPool:
    """
    SQLite 连接池

    注意：SQLite 的连接池实现与 PostgreSQL 等不同，
    因为 SQLite 的连接不是线程安全的，需要特殊处理
    """

    def __init__(self, database: str, max_connections: int = 5,
                 timeout: float = 30.0, check_same_thread: bool = False):
        self.database = database
        self.max_connections = max_connections
        self.timeout = timeout
        self._check_same_thread = check_same_thread

        # 活跃连接数
        self._active_count = 0
        self._lock = threading.Lock()

        # 统计信息
        self._stats = {
            'acquired': 0,
            'released': 0,
            'created': 0,
            'errors': 0
        }

    def _create_connection(self) -> sqlite3.Connection:
        """创建新连接"""
        conn = sqlite3.connect(
            self.database,
            timeout=self.timeout,
            check_same_thread=self._check_same_thread
        )
        # 启用外键约束
        conn.execute("PRAGMA foreign_keys = ON")
        # 优化性能
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -64000")
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def acquire(self):
        """获取连接（上下文管理器）"""
        conn = None
        acquired = False

        try:
            with self._lock:
                if self._active_count < self.max_connections:
                    self._active_count += 1
                    acquired = True

            if acquired:
                conn = self._create_connection()
                self._stats['acquired'] += 1
                self._stats['created'] += 1

            yield conn

        except Exception as e:
            self._stats['errors'] += 1
            logging.error(f"数据库连接错误: {e}")
            raise

        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

            with self._lock:
                if acquired:
                    self._active_count -= 1
                    self._stats['released'] += 1

    def execute(self, query: str, params: tuple = None) -> list:
        """执行查询并返回结果"""
        with self.acquire() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            if query.strip().upper().startswith('SELECT'):
                return [dict(row) for row in cursor.fetchall()]
            else:
                conn.commit()
                return []

    def executemany(self, query: str, params_list: list) -> int:
        """批量执行"""
        with self.acquire() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()
            return cursor.rowcount

    def get_stats(self) -> dict:
        """获取连接池统计"""
        with self._lock:
            return {
                'active': self._active_count,
                'max': self.max_connections,
                **self._stats
            }


# 全局连接池实例
_db_pool: Optional[ConnectionPool] = None
_pool_lock = threading.Lock()


def init_db_pool(database: str, max_connections: int = 5):
    """初始化数据库连接池"""
    global _db_pool
    with _pool_lock:
        if _db_pool is None:
            _db_pool = ConnectionPool(database, max_connections)
            logging.info(f"数据库连接池已初始化: {database}, 最大连接数: {max_connections}")


def get_db_pool() -> Optional[ConnectionPool]:
    """获取数据库连接池"""
    return _db_pool


@contextmanager
def db_connection():
    """数据库连接上下文管理器"""
    pool = get_db_pool()
    if pool is None:
        raise RuntimeError("数据库连接池未初始化")

    with pool.acquire() as conn:
        yield conn


def db_execute(query: str, params: tuple = None) -> list:
    """快速执行查询"""
    pool = get_db_pool()
    if pool is None:
        raise RuntimeError("数据库连接池未初始化")
    return pool.execute(query, params)


def db_executemany(query: str, params_list: list) -> int:
    """快速批量执行"""
    pool = get_db_pool()
    if pool is None:
        raise RuntimeError("数据库连接池未初始化")
    return pool.executemany(query, params_list)
