#!/usr/bin/env python3
"""
清除缓存脚本
"""
import sys
sys.path.append('/workspace')

# 导入缓存管理器
from cache_manager import cache_manager

print("清除缓存...")

# 清除房间信息缓存
cache_manager.clear_cache('room_info')
print("房间信息缓存已清除")

# 也可以使用更直接的方法
import time
cache_instances = getattr(cache_manager, '_cache_instances', {})
if 'room_info' in cache_instances:
    cache_instances['room_info'].clear()
    print("room_info缓存实例已清除")

print("缓存清除完成")