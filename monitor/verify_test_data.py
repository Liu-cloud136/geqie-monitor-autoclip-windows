#!/usr/bin/env python3
"""
验证测试数据脚本 - 用于检查数据库中的测试数据
"""
import sqlite3
from datetime import datetime

DB_PATH = "geqie_data.db"

def verify_test_data():
    """验证数据库中的测试数据"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查总记录数
    cursor.execute('SELECT COUNT(*) FROM geqie_data')
    total_count = cursor.fetchone()[0]
    print(f"数据库总记录数: {total_count} 条")
    
    # 检查按日期统计
    print("\n按日期统计:")
    cursor.execute('''
        SELECT date, COUNT(*) as count 
        FROM geqie_data 
        GROUP BY date 
        ORDER BY date DESC
    ''')
    daily_stats = cursor.fetchall()
    for date, count in daily_stats:
        print(f"  {date}: {count} 条")
    
    # 显示最近的10条记录
    print("\n最近10条记录:")
    cursor.execute('''
        SELECT id, username, content, timestamp, room_title, date 
        FROM geqie_data 
        ORDER BY timestamp DESC 
        LIMIT 10
    ''')
    recent_records = cursor.fetchall()
    
    for record in recent_records:
        record_id, username, content, timestamp, room_title, date = record
        # 转换时间戳为可读格式
        time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n  ID: {record_id}")
        print(f"  用户名: {username}")
        print(f"  内容: {content[:50]}{'...' if len(content) > 50 else ''}")
        print(f"  时间: {time_str}")
        print(f"  房间标题: {room_title}")
        print(f"  日期: {date}")
    
    # 检查数据分布
    print("\n用户分布（前5名）:")
    cursor.execute('''
        SELECT username, COUNT(*) as count 
        FROM geqie_data 
        GROUP BY username 
        ORDER BY count DESC 
        LIMIT 5
    ''')
    user_stats = cursor.fetchall()
    for username, count in user_stats:
        print(f"  {username}: {count} 条")
    
    conn.close()
    
    return total_count

if __name__ == "__main__":
    verify_test_data()
