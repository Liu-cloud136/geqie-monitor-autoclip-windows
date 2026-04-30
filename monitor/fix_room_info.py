#!/usr/bin/env python3
"""
临时修复脚本：直接使用requests获取直播间信息
"""
import sys
import os
import logging

# 确保可以导入项目模块
sys.path.append('/workspace')

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_room_info_sync():
    """同步获取直播间信息"""
    import requests
    import json
    
    room_id = 22625568
    api_urls = [
        f"https://api.live.bilibili.com/room/v1/Room/get_info?id={room_id}",
        f"https://api.live.bilibili.com/room/v1/Room/room_init?id={room_id}"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': f'https://live.bilibili.com/{room_id}',
        'Origin': 'https://live.bilibili.com'
    }
    
    for url in api_urls:
        try:
            logging.info(f"尝试请求: {url}")
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code', 0) == 0:
                    room_data = data.get('data', {})
                    title = room_data.get('title', '未知标题')
                    live_status = room_data.get('live_status', 0)
                    
                    result = {
                        'room_id': room_data.get('room_id', room_id),
                        'room_title': title,
                        'live_status': live_status,
                        'online': room_data.get('online', 0),
                        'api_source': url.split('/')[-1]
                    }
                    
                    logging.info(f"✅ 成功获取直播间信息: {result}")
                    return result
            else:
                logging.warning(f"HTTP状态码 {response.status_code}: {url}")
                
        except Exception as e:
            logging.warning(f"请求失败 {url}: {e}")
            continue
    
    # 所有尝试都失败
    fallback = {
        'room_id': room_id,
        'room_title': '未知直播间-fallback',
        'live_status': 0,
        'online': 0,
        'api_source': 'all_failed'
    }
    logging.warning(f"❌ 所有API请求失败，返回fallback: {fallback}")
    return fallback

if __name__ == "__main__":
    print("测试同步获取直播间信息...")
    result = get_room_info_sync()
    print(f"结果: {result}")