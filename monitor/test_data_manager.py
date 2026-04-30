#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库层单元测试 - 测试评分相关功能
测试文件: data_manager.py
"""

import sys
import os
import tempfile
import shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

TEST_RESULTS = []

def log_test_result(test_name, passed, message=""):
    """记录测试结果"""
    result = {
        "name": test_name,
        "passed": passed,
        "message": message,
        "timestamp": datetime.now().isoformat()
    }
    TEST_RESULTS.append(result)
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {test_name}")
    if message:
        print(f"       {message}")

def test_data_manager():
    """测试数据管理器"""
    
    print("\n" + "=" * 60)
    print("测试: 数据管理器 (data_manager.py)")
    print("=" * 60)
    
    # 1. 测试导入
    print("\n1. 测试模块导入...")
    try:
        from data_manager import data_manager, DataManager
        log_test_result("模块导入", True, "成功导入 data_manager 模块")
    except ImportError as e:
        log_test_result("模块导入", False, f"导入失败: {e}")
        return
    
    # 2. 测试数据库迁移功能
    print("\n2. 测试数据库迁移功能...")
    try:
        test_db_dir = tempfile.mkdtemp()
        test_db_path = os.path.join(test_db_dir, "test_geqie_data.db")
        
        import sqlite3
        
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()
        
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
                email_sent_time REAL
            )
        ''')
        
        conn.commit()
        conn.close()
        
        from data_manager import DataManager
        
        class TestDataManager(DataManager):
            def __init__(self, db_path):
                self._db_path = db_path
                self._cache = type('obj', (object,), {
                    'get': lambda self, k: None,
                    'set': lambda self, k, v, ttl=0: None,
                    'delete': lambda self, k: None
                })()
        
        test_manager = TestDataManager(test_db_path)
        
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(geqie_data)")
        columns = [row[1] for row in cursor.fetchall()]
        
        rating_columns = ['rating', 'rating_time', 'rating_comment', 'rating_email_status', 'rating_email_time']
        missing_columns = [col for col in rating_columns if col not in columns]
        
        if missing_columns:
            test_manager._migrate_database(cursor)
            conn.commit()
            
            cursor.execute("PRAGMA table_info(geqie_data)")
            columns = [row[1] for row in cursor.fetchall()]
            
            missing_after = [col for col in rating_columns if col not in columns]
            
            if missing_after:
                log_test_result("数据库迁移", False, f"迁移后仍缺少字段: {missing_after}")
            else:
                log_test_result("数据库迁移", True, "成功添加所有评分数段")
        else:
            log_test_result("数据库迁移", True, "所有评分数段已存在")
        
        conn.close()
        
        shutil.rmtree(test_db_dir)
        
    except Exception as e:
        log_test_result("数据库迁移", False, f"测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. 测试评分更新功能
    print("\n3. 测试评分更新功能...")
    try:
        test_db_dir = tempfile.mkdtemp()
        test_db_path = os.path.join(test_db_dir, "test_geqie_data.db")
        
        import sqlite3
        
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE geqie_data (
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
        
        cursor.execute('''
            INSERT INTO geqie_data (username, content, timestamp, room_id, room_title, date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ("测试用户", "测试内容", datetime.now().timestamp(), 12345, "测试直播间", "2026-04-30"))
        
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        class TestDataManager(DataManager):
            def __init__(self, db_path):
                self._db_path = db_path
                self._cache = type('obj', (object,), {
                    'get': lambda self, k: None,
                    'set': lambda self, k, v, ttl=0: None,
                    'delete': lambda self, k: None
                })()
            
            def _get_connection(self):
                return sqlite3.connect(self._db_path)
        
        test_manager = TestDataManager(test_db_path)
        
        test_manager.update_rating(record_id, 5, "非常好的内容！")
        
        conn = sqlite3.connect(test_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM geqie_data WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        
        if row['rating'] == 5:
            log_test_result("更新评分", True, f"成功将记录 {record_id} 评分设为 5 星")
        else:
            log_test_result("更新评分", False, f"评分未正确更新: 期望 5, 实际 {row['rating']}")
        
        if row['rating_comment'] == "非常好的内容！":
            log_test_result("更新评论文字", True, "成功更新评论文字")
        else:
            log_test_result("更新评论文字", False, f"评论文字未正确更新: {row['rating_comment']}")
        
        if row['rating_time'] is not None:
            log_test_result("更新评分时间", True, "成功更新评分时间戳")
        else:
            log_test_result("更新评分时间", False, "评分时间戳为空")
        
        conn.close()
        shutil.rmtree(test_db_dir)
        
    except Exception as e:
        log_test_result("评分更新", False, f"测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. 测试评分边界值
    print("\n4. 测试评分边界值验证...")
    try:
        test_db_dir = tempfile.mkdtemp()
        test_db_path = os.path.join(test_db_dir, "test_geqie_data.db")
        
        import sqlite3
        
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE geqie_data (
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
        
        cursor.execute('''
            INSERT INTO geqie_data (username, content, timestamp, room_id, room_title, date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ("测试用户", "测试内容", datetime.now().timestamp(), 12345, "测试直播间", "2026-04-30"))
        
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        class TestDataManager(DataManager):
            def __init__(self, db_path):
                self._db_path = db_path
                self._cache = type('obj', (object,), {
                    'get': lambda self, k: None,
                    'set': lambda self, k, v, ttl=0: None,
                    'delete': lambda self, k: None
                })()
            
            def _get_connection(self):
                return sqlite3.connect(self._db_path)
        
        test_manager = TestDataManager(test_db_path)
        
        try:
            test_manager.update_rating(record_id, 0)
            log_test_result("边界值测试 - 0星", False, "应该拒绝0星评分但没有拒绝")
        except ValueError:
            log_test_result("边界值测试 - 0星", True, "正确拒绝0星评分")
        
        try:
            test_manager.update_rating(record_id, 6)
            log_test_result("边界值测试 - 6星", False, "应该拒绝6星评分但没有拒绝")
        except ValueError:
            log_test_result("边界值测试 - 6星", True, "正确拒绝6星评分")
        
        test_manager.update_rating(record_id, 1)
        log_test_result("边界值测试 - 1星", True, "成功设置1星评分")
        
        test_manager.update_rating(record_id, 5)
        log_test_result("边界值测试 - 5星", True, "成功设置5星评分")
        
        shutil.rmtree(test_db_dir)
        
    except Exception as e:
        log_test_result("边界值验证", False, f"测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. 测试评分邮件状态更新
    print("\n5. 测试评分邮件状态更新...")
    try:
        test_db_dir = tempfile.mkdtemp()
        test_db_path = os.path.join(test_db_dir, "test_geqie_data.db")
        
        import sqlite3
        
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE geqie_data (
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
        
        cursor.execute('''
            INSERT INTO geqie_data (username, content, timestamp, room_id, room_title, date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ("测试用户", "测试内容", datetime.now().timestamp(), 12345, "测试直播间", "2026-04-30"))
        
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        class TestDataManager(DataManager):
            def __init__(self, db_path):
                self._db_path = db_path
                self._cache = type('obj', (object,), {
                    'get': lambda self, k: None,
                    'set': lambda self, k, v, ttl=0: None,
                    'delete': lambda self, k: None
                })()
            
            def _get_connection(self):
                return sqlite3.connect(self._db_path)
        
        test_manager = TestDataManager(test_db_path)
        
        test_manager.update_rating_email_status(record_id, 'success')
        
        conn = sqlite3.connect(test_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM geqie_data WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        
        if row['rating_email_status'] == 'success':
            log_test_result("评分邮件状态更新", True, "成功更新邮件状态为 'success'")
        else:
            log_test_result("评分邮件状态更新", False, f"状态未正确更新: {row['rating_email_status']}")
        
        if row['rating_email_time'] is not None:
            log_test_result("评分邮件时间更新", True, "成功更新邮件发送时间戳")
        else:
            log_test_result("评分邮件时间更新", False, "邮件发送时间戳为空")
        
        conn.close()
        shutil.rmtree(test_db_dir)
        
    except Exception as e:
        log_test_result("评分邮件状态", False, f"测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 输出测试汇总
    print("\n" + "=" * 60)
    print("数据管理器测试汇总")
    print("=" * 60)
    
    passed = sum(1 for r in TEST_RESULTS if r['passed'])
    failed = sum(1 for r in TEST_RESULTS if not r['passed'])
    
    print(f"\n通过: {passed}, 失败: {failed}")
    
    if failed > 0:
        print("\n失败的测试:")
        for r in TEST_RESULTS:
            if not r['passed']:
                print(f"  - {r['name']}: {r['message']}")
    
    return TEST_RESULTS

if __name__ == "__main__":
    test_data_manager()
