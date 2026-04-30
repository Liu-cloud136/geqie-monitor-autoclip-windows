#!/usr/bin/env python3
"""
测试数据生成脚本 - 用于生成鸽切弹幕测试数据
"""
import random
import time
from datetime import datetime, timedelta
import sqlite3
import os

# 配置
DB_PATH = "geqie_data.db"
ROOM_ID = 22391541  # 默认直播间ID
ROOM_TITLE = "鸽切直播间 - 精彩直播中"

# 模拟的B站用户名列表
USERNAMES = [
    "快乐鸽子123", "聪明猫咪456", "勇敢小狗789", "温柔兔子012",
    "活泼熊猫345", "机智海豚678", "帅气老虎901", "美丽蝴蝶234",
    "优雅狐狸567", "可爱松鼠890", "快乐小鸟111", "聪明小熊222",
    "勇敢企鹅333", "温柔蜜蜂444", "活泼蜻蜓555", "机智海豚666",
    "帅气老虎777", "美丽蝴蝶888", "优雅狐狸999", "可爱松鼠000"
]

# 包含"鸽切"关键词的弹幕内容模板
DANMAKU_TEMPLATES = [
    "鸽切！鸽切！太精彩了！",
    "这波操作简直是鸽切本切",
    "鸽切无处不在，快乐随之而来",
    "今天也是鸽切满满的一天",
    "鸽切大军在哪里？让我看到你们的双手！",
    "这才是真正的鸽切操作",
    "鸽切虽迟但到",
    "主播这波操作太鸽切了",
    "鸽切是一种态度，也是一种生活",
    "每次看直播都能感受到鸽切的力量",
    "鸽切不鸽，快乐不缺",
    "这波鸽切操作我给满分",
    "鸽切文化，源远流长",
    "主播的鸽切操作越来越熟练了",
    "今天你鸽切了吗？",
    "鸽切是我们共同的语言",
    "这波操作鸽切到没朋友",
    "鸽切虽小，快乐很大",
    "每天一点鸽切，生活更有滋味",
    "主播的鸽切操作总是让人惊喜"
]

def generate_random_date(days_back=7, force_today=False):
    """生成随机日期（最近几天内）"""
    today = datetime.now()
    
    if force_today:
        # 生成今天的随机时间
        random_hours = random.randint(0, 23)
        random_minutes = random.randint(0, 59)
        random_seconds = random.randint(0, 59)
        random_date = today.replace(
            hour=random_hours,
            minute=random_minutes,
            second=random_seconds,
            microsecond=0
        )
    else:
        # 生成最近几天内的随机时间
        random_days = random.randint(0, days_back)
        random_hours = random.randint(0, 23)
        random_minutes = random.randint(0, 59)
        random_seconds = random.randint(0, 59)
        
        random_date = today - timedelta(
            days=random_days,
            hours=random_hours,
            minutes=random_minutes,
            seconds=random_seconds
        )
    
    return random_date

def init_database():
    """初始化数据库（如果不存在）"""
    conn = sqlite3.connect(DB_PATH)
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
            email_sent_time REAL,
            rating INTEGER DEFAULT 0,
            rating_time REAL,
            rating_comment TEXT,
            rating_email_status TEXT DEFAULT 'none',
            rating_email_time REAL
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON geqie_data(date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON geqie_data(timestamp)')
    
    conn.commit()
    conn.close()

def generate_test_data(count=15, force_today=False):
    """生成测试数据
    
    Args:
        count: 生成的数据条数
        force_today: 是否强制生成今天的数据
    """
    init_database()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    date_desc = "今天" if force_today else "最近7天"
    print(f"正在生成 {count} 条{date_desc}的测试数据...")
    
    for i in range(count):
        # 随机选择用户名
        username = random.choice(USERNAMES)
        
        # 随机选择弹幕内容
        content = random.choice(DANMAKU_TEMPLATES)
        
        # 生成随机时间
        random_datetime = generate_random_date(days_back=7, force_today=force_today)
        timestamp = random_datetime.timestamp()
        date_str = random_datetime.strftime('%Y-%m-%d')
        
        # 随机房间标题
        room_titles = [
            "鸽切直播间 - 精彩直播中",
            "欢乐鸽切时刻",
            "每日鸽切精选",
            "鸽切大作战",
            "快乐鸽切直播间"
        ]
        room_title = random.choice(room_titles)
        
        # 插入数据
        cursor.execute('''
            INSERT INTO geqie_data (
                username, content, timestamp, room_id, room_title, date, email_status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'none')
        ''', (username, content, timestamp, ROOM_ID, room_title, date_str))
        
        # 显示进度
        if (i + 1) % 5 == 0:
            print(f"  已生成 {i + 1}/{count} 条数据...")
    
    conn.commit()
    
    # 查询并显示生成的数据统计
    cursor.execute('SELECT COUNT(*) FROM geqie_data')
    total_count = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT date, COUNT(*) as count 
        FROM geqie_data 
        GROUP BY date 
        ORDER BY date DESC
    ''')
    daily_stats = cursor.fetchall()
    
    conn.close()
    
    print(f"\n测试数据生成完成！")
    print(f"数据库总记录数: {total_count} 条")
    print(f"按日期统计:")
    for date, count in daily_stats:
        print(f"   {date}: {count} 条")
    
    return total_count

if __name__ == "__main__":
    # 生成10条今天的测试数据
    generate_test_data(count=10, force_today=True)
