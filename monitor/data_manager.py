#!/usr/bin/env python3
"""
数据管理器 - 用于存储和查询鸽切数据
优化版：集成连接池、批量操作、查询优化
"""
import json
import os
import time
from datetime import datetime, timedelta
import sqlite3
from typing import List, Dict, Optional
from contextlib import contextmanager
import pytz
import yaml
import logging

from cache_manager import cache_manager
from db_pool import init_db_pool, get_db_pool


# 设置中国时区（延迟加载）
_china_tz_cache = None


def load_config():
    """直接加载配置文件"""
    config_path = "config.yaml"
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    return {}


def get_config(section=None, key=None, default=None):
    """获取配置值"""
    config = load_config()
    if section is None:
        return config
    elif key is None:
        return config.get(section, {})
    else:
        return config.get(section, {}).get(key, default)


def get_china_tz():
    """延迟获取中国时区"""
    global _china_tz_cache
    if _china_tz_cache is None:
        _china_tz_cache = pytz.timezone(get_config("app", "timezone", "Asia/Shanghai"))
    return _china_tz_cache


class DataManager:
    """鸽切数据管理器 - 优化版：使用缓存、批量操作和连接池"""

    _pool_initialized = False

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = get_config("app", "database_path")
        self.db_path = db_path

        # 优化：使用统一的缓存管理器
        self._cache = cache_manager.get_cache('data', ttl=60)

        # 初始化数据库连接池（只执行一次）
        if not DataManager._pool_initialized:
            init_db_pool(self.db_path, max_connections=5)
            DataManager._pool_initialized = True

        self.init_database()

    def _get_connection(self):
        """获取数据库连接（优先使用连接池）"""
        pool = get_db_pool()
        if pool:
            return pool.acquire()
        # 回退：直接创建连接
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return contextmanager(lambda: conn).__enter__()

    def init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # 创建鸽切数据表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS geqie_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    room_id INTEGER NOT NULL,
                    room_title TEXT,
                    date TEXT NOT NULL,
                    slice_url TEXT,
                    skip_reason TEXT,
                    email_status TEXT DEFAULT 'none',
                    email_sent_time REAL,
                    rating INTEGER DEFAULT 0,
                    rating_time REAL,
                    rating_comment TEXT,
                    rating_email_status TEXT DEFAULT 'none',
                    rating_email_time REAL
                )
            ''')

            # 迁移现有表结构 - 添加评分相关字段
            self._migrate_database(cursor)

            # 创建日期索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON geqie_data(date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON geqie_data(timestamp)')

            conn.commit()
        finally:
            conn.close()

    def _migrate_database(self, cursor):
        """迁移数据库表结构，添加新字段"""
        try:
            # 检查是否需要添加 rating 字段
            cursor.execute("PRAGMA table_info(geqie_data)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'rating' not in columns:
                cursor.execute('ALTER TABLE geqie_data ADD COLUMN rating INTEGER DEFAULT 0')
            if 'rating_time' not in columns:
                cursor.execute('ALTER TABLE geqie_data ADD COLUMN rating_time REAL')
            if 'rating_comment' not in columns:
                cursor.execute('ALTER TABLE geqie_data ADD COLUMN rating_comment TEXT')
            if 'rating_email_status' not in columns:
                cursor.execute('ALTER TABLE geqie_data ADD COLUMN rating_email_status TEXT DEFAULT "none"')
            if 'rating_email_time' not in columns:
                cursor.execute('ALTER TABLE geqie_data ADD COLUMN rating_email_time REAL')
        except Exception as e:
            logging.warning(f"数据库迁移警告: {e}")

    def add_geqie_record(self, username: str, content: str, room_id: int, room_title: str = None) -> int:
        """添加鸽切记录，返回记录ID"""
        # 使用UTC时间戳以确保一致性
        timestamp = datetime.utcnow().timestamp()
        # 使用中国时区计算日期，确保日期查询的一致性
        china_tz = get_china_tz()
        date = datetime.now(china_tz).strftime('%Y-%m-%d')

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO geqie_data (username, content, timestamp, room_id, room_title, date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, content, timestamp, room_id, room_title, date))
            record_id = cursor.lastrowid
            conn.commit()

        # 清除统计缓存
        self._invalidate_stats_cache()

        return record_id

    def get_today_data(self) -> List[Dict]:
        """获取今天的数据"""
        china_tz = get_china_tz()
        today = datetime.now(china_tz).strftime('%Y-%m-%d')
        return self.get_data_by_date(today)

    def get_data_by_date(self, date: str) -> List[Dict]:
        """获取指定日期的数据 - 优化版：直接使用WHERE条件过滤"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM geqie_data
                WHERE date = ?
                ORDER BY timestamp DESC
            ''', (date,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_record_by_id(self, record_id: int) -> Optional[Dict]:
        """根据ID获取单个记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM geqie_data WHERE id = ?', (record_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_recent_days_data(self, days: int = 7) -> Dict[str, List[Dict]]:
        """获取最近几天的数据 - 优化版：单次查询获取多天数据"""
        china_tz = get_china_tz()
        min_date = (datetime.now(china_tz) - timedelta(days=days - 1)).strftime('%Y-%m-%d')

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM geqie_data
                WHERE date >= ?
                ORDER BY date DESC, timestamp DESC
            ''', (min_date,))
            rows = cursor.fetchall()

            # 按日期分组
            result = {}
            for row in rows:
                date = row['date']
                if date not in result:
                    result[date] = []
                result[date].append(dict(row))

        return result

    def get_daily_stats(self, days: int = 7) -> List[Dict]:
        """获取每日统计 - 使用统一缓存"""
        cache_key = f'daily_stats_{days}'
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        china_tz = get_china_tz()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT date, COUNT(*) as count
                FROM geqie_data
                WHERE date >= ?
                GROUP BY date
                ORDER BY date DESC
            ''', ((datetime.now(china_tz) - timedelta(days=days)).strftime('%Y-%m-%d'),))
            rows = cursor.fetchall()
            result = [{'date': date, 'count': count} for date, count in rows]

        self._cache.set(cache_key, result, ttl=30)
        return result

    def get_total_stats(self) -> Dict:
        """获取总体统计 - 使用统一缓存"""
        cache_key = 'total_stats'
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        china_tz = get_china_tz()
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 优化：单次查询获取多个统计值
            cursor.execute('''
                SELECT
                    (SELECT COUNT(*) FROM geqie_data) as total_count,
                    (SELECT COUNT(*) FROM geqie_data WHERE date = ?) as today_count,
                    (SELECT COUNT(*) FROM geqie_data WHERE date >= ?) as week_count
            ''', (
                datetime.now(china_tz).strftime('%Y-%m-%d'),
                (datetime.now(china_tz) - timedelta(days=7)).strftime('%Y-%m-%d')
            ))
            row = cursor.fetchone()

            cursor.execute('''
                SELECT username, COUNT(*) as count
                FROM geqie_data
                GROUP BY username
                ORDER BY count DESC
                LIMIT 5
            ''')
            top_users = cursor.fetchall()

        result = {
            'total_count': row[0] or 0,
            'today_count': row[1] or 0,
            'week_count': row[2] or 0,
            'top_users': [{'username': user, 'count': count} for user, count in top_users]
        }

        self._cache.set(cache_key, result, ttl=60)
        return result

    def update_record(self, record_id: int, slice_url: str = None, skip_reason: str = None):
        """更新记录的切片地址或跳过原因"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE geqie_data
                SET slice_url = ?, skip_reason = ?
                WHERE id = ?
            ''', (slice_url, skip_reason, record_id))
            conn.commit()

    def update_email_status(self, record_id: int, status: str):
        """更新记录的邮件发送状态"""
        sent_time = datetime.now().timestamp() if status in ('success', 'failed') else None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE geqie_data
                SET email_status = ?, email_sent_time = ?
                WHERE id = ?
            ''', (status, sent_time, record_id))
            conn.commit()

    def update_rating(self, record_id: int, rating: int, rating_comment: str = None):
        """更新记录的评分"""
        if rating < 1 or rating > 5:
            raise ValueError("评分必须在 1-5 之间")
        
        rating_time = datetime.now().timestamp()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE geqie_data
                SET rating = ?, rating_time = ?, rating_comment = ?
                WHERE id = ?
            ''', (rating, rating_time, rating_comment, record_id))
            conn.commit()

    def update_rating_email_status(self, record_id: int, status: str):
        """更新记录的评分邮件发送状态"""
        sent_time = datetime.now().timestamp() if status in ('success', 'failed') else None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE geqie_data
                SET rating_email_status = ?, rating_email_time = ?
                WHERE id = ?
            ''', (status, sent_time, record_id))
            conn.commit()

    def _invalidate_stats_cache(self):
        """清除统计相关的缓存"""
        self._cache.delete('total_stats')
        self._cache.delete('daily_stats_7')
        self._cache.delete('daily_stats_30')
        logging.debug("统计数据缓存已清除")

    def delete_record(self, record_id: int):
        """删除记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM geqie_data WHERE id = ?', (record_id,))
            conn.commit()
        self._invalidate_stats_cache()
    
    # ============================================================================
    # 多房间数据查询方法
    # ============================================================================
    
    def get_data_by_room_and_date(self, room_id: int, date: str = None) -> List[Dict]:
        """
        获取指定房间在指定日期的数据
        如果不指定日期，则获取今天的数据
        """
        if date is None:
            china_tz = get_china_tz()
            date = datetime.now(china_tz).strftime('%Y-%m-%d')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM geqie_data
                WHERE room_id = ? AND date = ?
                ORDER BY timestamp DESC
            ''', (room_id, date))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_data_by_room(self, room_id: int, days: int = 7) -> List[Dict]:
        """
        获取指定房间最近几天的数据
        """
        china_tz = get_china_tz()
        min_date = (datetime.now(china_tz) - timedelta(days=days)).strftime('%Y-%m-%d')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM geqie_data
                WHERE room_id = ? AND date >= ?
                ORDER BY date DESC, timestamp DESC
            ''', (room_id, min_date))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_room_stats(self, room_id: int, days: int = 7) -> Dict:
        """
        获取指定房间的统计数据
        """
        cache_key = f'room_stats_{room_id}_{days}'
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        china_tz = get_china_tz()
        today = datetime.now(china_tz).strftime('%Y-%m-%d')
        week_ago = (datetime.now(china_tz) - timedelta(days=days)).strftime('%Y-%m-%d')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 总体统计
            cursor.execute('''
                SELECT
                    COUNT(*) as total_count,
                    COUNT(CASE WHEN date = ? THEN 1 END) as today_count,
                    COUNT(CASE WHEN date >= ? THEN 1 END) as recent_count
                FROM geqie_data
                WHERE room_id = ?
            ''', (today, week_ago, room_id))
            row = cursor.fetchone()
            
            # 活跃用户
            cursor.execute('''
                SELECT username, COUNT(*) as count
                FROM geqie_data
                WHERE room_id = ? AND date >= ?
                GROUP BY username
                ORDER BY count DESC
                LIMIT 5
            ''', (room_id, week_ago))
            top_users = cursor.fetchall()
            
            # 每日统计
            cursor.execute('''
                SELECT date, COUNT(*) as count
                FROM geqie_data
                WHERE room_id = ? AND date >= ?
                GROUP BY date
                ORDER BY date DESC
            ''', (room_id, week_ago))
            daily_stats = cursor.fetchall()
        
        result = {
            'room_id': room_id,
            'total_count': row[0] or 0,
            'today_count': row[1] or 0,
            'recent_count': row[2] or 0,
            'top_users': [{'username': user, 'count': count} for user, count in top_users],
            'daily_stats': [{'date': date, 'count': count} for date, count in daily_stats]
        }
        
        self._cache.set(cache_key, result, ttl=60)
        return result
    
    def get_all_rooms_stats(self, days: int = 7) -> List[Dict]:
        """
        获取所有房间的统计数据（用于对比分析）
        """
        cache_key = f'all_rooms_stats_{days}'
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        china_tz = get_china_tz()
        today = datetime.now(china_tz).strftime('%Y-%m-%d')
        week_ago = (datetime.now(china_tz) - timedelta(days=days)).strftime('%Y-%m-%d')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取所有有数据的房间列表
            cursor.execute('''
                SELECT DISTINCT room_id, room_title
                FROM geqie_data
                ORDER BY room_id
            ''')
            rooms = cursor.fetchall()
            
            # 为每个房间获取统计数据
            result = []
            for room_id, room_title in rooms:
                # 总体统计
                cursor.execute('''
                    SELECT
                        COUNT(*) as total_count,
                        COUNT(CASE WHEN date = ? THEN 1 END) as today_count,
                        COUNT(CASE WHEN date >= ? THEN 1 END) as week_count
                    FROM geqie_data
                    WHERE room_id = ?
                ''', (today, week_ago, room_id))
                row = cursor.fetchone()
                
                # 获取房间标题（如果没有，使用room_id）
                title = room_title or f"直播间 {room_id}"
                
                result.append({
                    'room_id': room_id,
                    'room_title': title,
                    'total_count': row[0] or 0,
                    'today_count': row[1] or 0,
                    'week_count': row[2] or 0
                })
        
        self._cache.set(cache_key, result, ttl=60)
        return result
    
    def get_room_comparison(self, days: int = 7) -> Dict:
        """
        获取房间对比数据（用于可视化对比）
        """
        china_tz = get_china_tz()
        min_date = (datetime.now(china_tz) - timedelta(days=days)).strftime('%Y-%m-%d')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取每个房间的每日数据
            cursor.execute('''
                SELECT room_id, date, COUNT(*) as count, room_title
                FROM geqie_data
                WHERE date >= ?
                GROUP BY room_id, date
                ORDER BY room_id, date
            ''', (min_date,))
            rows = cursor.fetchall()
            
            # 按房间分组
            room_data = {}
            for room_id, date, count, room_title in rows:
                if room_id not in room_data:
                    room_data[room_id] = {
                        'room_id': room_id,
                        'room_title': room_title or f"直播间 {room_id}",
                        'daily_data': [],
                        'total_count': 0
                    }
                room_data[room_id]['daily_data'].append({'date': date, 'count': count})
                room_data[room_id]['total_count'] += count
            
            # 转换为列表并排序
            result = sorted(
                room_data.values(),
                key=lambda x: x['total_count'],
                reverse=True
            )
        
        return {
            'comparison_data': result,
            'days': days
        }
    
    def get_keyword_frequency_by_room(self, room_id: int = None, days: int = 7) -> Dict:
        """
        获取关键词出现频率统计（按房间）
        如果指定 room_id，则只获取该房间的数据；否则获取所有房间的汇总
        """
        cache_key = f'keyword_freq_{room_id or "all"}_{days}'
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        china_tz = get_china_tz()
        min_date = (datetime.now(china_tz) - timedelta(days=days)).strftime('%Y-%m-%d')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 构建查询条件
            query = '''
                SELECT room_id, room_title, content
                FROM geqie_data
                WHERE date >= ?
            '''
            params = [min_date]
            
            if room_id is not None:
                query += ' AND room_id = ?'
                params.append(room_id)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # 统计关键词频率
            import re
            # 简单的关键词提取（使用空格或标点分割）
            keyword_pattern = re.compile(r'[\u4e00-\u9fa5]+')
            
            # 按房间统计
            room_keywords = {}
            all_keywords = {}
            
            for rid, room_title, content in rows:
                if not content:
                    continue
                
                # 提取中文关键词
                keywords = keyword_pattern.findall(content)
                
                # 初始化房间统计
                if rid not in room_keywords:
                    room_keywords[rid] = {
                        'room_id': rid,
                        'room_title': room_title or f"直播间 {rid}",
                        'keywords': {},
                        'total_danmaku': 0
                    }
                
                room_keywords[rid]['total_danmaku'] += 1
                
                # 统计关键词
                for kw in keywords:
                    if len(kw) >= 2:  # 只统计长度>=2的词
                        # 全房间统计
                        all_keywords[kw] = all_keywords.get(kw, 0) + 1
                        # 按房间统计
                        room_keywords[rid]['keywords'][kw] = room_keywords[rid]['keywords'].get(kw, 0) + 1
            
            # 格式化结果
            result = {
                'all_keywords': sorted(
                    [{'keyword': k, 'count': v} for k, v in all_keywords.items()],
                    key=lambda x: x['count'],
                    reverse=True
                )[:50],  # 只返回前50个
                'room_keywords': []
            }
            
            # 格式化每个房间的关键词
            for rid, data in room_keywords.items():
                sorted_keywords = sorted(
                    [{'keyword': k, 'count': v} for k, v in data['keywords'].items()],
                    key=lambda x: x['count'],
                    reverse=True
                )[:20]  # 每个房间返回前20个
                
                result['room_keywords'].append({
                    'room_id': rid,
                    'room_title': data['room_title'],
                    'total_danmaku': data['total_danmaku'],
                    'keywords': sorted_keywords
                })
        
        self._cache.set(cache_key, result, ttl=300)  # 缓存5分钟
        return result
    
    def get_rooms_with_data(self) -> List[Dict]:
        """
        获取所有有数据记录的房间列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT room_id, room_title,
                       (SELECT COUNT(*) FROM geqie_data g2 WHERE g2.room_id = g1.room_id) as total_count,
                       (SELECT MAX(date) FROM geqie_data g2 WHERE g2.room_id = g1.room_id) as last_date
                FROM geqie_data g1
                ORDER BY total_count DESC
            ''')
            rows = cursor.fetchall()
            
            return [
                {
                    'room_id': row[0],
                    'room_title': row[1] or f"直播间 {row[0]}",
                    'total_count': row[2],
                    'last_date': row[3]
                }
                for row in rows
            ]

    def test_connection(self):
        """测试数据库连接"""
        try:
            pool = get_db_pool()
            if pool:
                pool_stats = pool.get_stats()
                return {
                    'status': 'connected',
                    'database_path': self.db_path,
                    'pool': pool_stats
                }

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM sqlite_master WHERE type="table"')
            table_count = cursor.fetchone()[0]
            conn.close()
            return {
                'status': 'connected',
                'tables': table_count,
                'database_path': self.db_path
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }

# 全局数据管理器实例（延迟初始化）
_data_manager_instance = None

def get_data_manager():
    """获取全局数据管理器实例（延迟初始化）"""
    global _data_manager_instance
    if _data_manager_instance is None:
        _data_manager_instance = DataManager()
    return _data_manager_instance

# 延迟初始化：只在第一次访问时创建实例
class DataManagerProxy:
    """数据管理器代理，延迟初始化"""
    
    def __init__(self):
        self._instance = None
    
    def __getattr__(self, name):
        if self._instance is None:
            self._instance = DataManager()
        return getattr(self._instance, name)

# 创建代理实例
data_manager = DataManagerProxy()