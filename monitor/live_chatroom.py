#!/usr/bin/env python3
"""
在线聊天室模块 - 独立于现有聊天/留言板系统
功能：
- 实时消息通信（WebSocket）
- 关键词过滤
- 禁言/封禁用户
- 随机用户名生成
- 显示IP和发送时间
- 中国时区支持
"""

import json
import os
import time
import logging
import uuid
from datetime import datetime
from collections import deque
from typing import Dict, List, Optional, Any

import pytz
import yaml


LIVE_CHATROOM_CONFIG = {}
LIVE_CHATROOM_ENABLE = True
MAX_ROOM_MESSAGES = 200
MAX_MESSAGE_LENGTH = 500
MAX_USERNAME_LENGTH = 20

USERNAME_ADJECTIVES = ["快乐", "开心", "可爱", "聪明", "勇敢", "温柔", "活泼", "机智", "帅气", "美丽", "优雅", "活泼", "聪明", "伶俐", "善良"]
USERNAME_NOUNS = ["鸽子", "小鸟", "猫咪", "狗狗", "兔子", "熊猫", "老虎", "海豚", "企鹅", "蝴蝶", "蜜蜂", "蜻蜓", "松鼠", "狐狸", "小熊"]

FILTER_ENABLE = True
SENSITIVE_WORDS = []
FILTER_ACTION = "replace"

MUTE_ENABLE = True
DEFAULT_MUTE_DURATION = 3600

room_messages = deque(maxlen=MAX_ROOM_MESSAGES)
muted_users = {}
online_users = {}
MESSAGES_FILE = "live_chatroom_messages.json"


def load_live_chatroom_config():
    """加载聊天室配置"""
    global LIVE_CHATROOM_CONFIG, LIVE_CHATROOM_ENABLE, MAX_ROOM_MESSAGES
    global MAX_MESSAGE_LENGTH, MAX_USERNAME_LENGTH
    global USERNAME_ADJECTIVES, USERNAME_NOUNS
    global FILTER_ENABLE, SENSITIVE_WORDS, FILTER_ACTION
    global MUTE_ENABLE, DEFAULT_MUTE_DURATION

    config_path = "config.yaml"
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            config = {}
    else:
        config = {}

    LIVE_CHATROOM_CONFIG = config.get("live_chatroom", {})
    logging.info(f"📋 LIVE_CHATROOM_CONFIG loaded: {LIVE_CHATROOM_CONFIG}")

    LIVE_CHATROOM_ENABLE = LIVE_CHATROOM_CONFIG.get("enable", True)
    MAX_ROOM_MESSAGES = LIVE_CHATROOM_CONFIG.get("max_messages", 200)
    MAX_MESSAGE_LENGTH = LIVE_CHATROOM_CONFIG.get("max_message_length", 500)
    MAX_USERNAME_LENGTH = LIVE_CHATROOM_CONFIG.get("max_username_length", 20)

    username_config = LIVE_CHATROOM_CONFIG.get("username", {})
    USERNAME_ADJECTIVES = username_config.get("adjectives", USERNAME_ADJECTIVES)
    USERNAME_NOUNS = username_config.get("nouns", USERNAME_NOUNS)

    filter_config = LIVE_CHATROOM_CONFIG.get("filter", {})
    FILTER_ENABLE = filter_config.get("enable", True)
    SENSITIVE_WORDS = filter_config.get("sensitive_words", [])
    FILTER_ACTION = filter_config.get("filter_action", "replace")

    mute_config = LIVE_CHATROOM_CONFIG.get("mute", {})
    MUTE_ENABLE = mute_config.get("enable", True)
    DEFAULT_MUTE_DURATION = mute_config.get("mute_duration", 3600)

    logging.info("=" * 50)
    logging.info("💬 在线聊天室配置:")
    logging.info(f"  - 启用: {LIVE_CHATROOM_ENABLE}")
    logging.info(f"  - 最大消息数: {MAX_ROOM_MESSAGES}")
    logging.info(f"  - 最大消息长度: {MAX_MESSAGE_LENGTH}")
    logging.info(f"  - 敏感词过滤: {FILTER_ENABLE} ({len(SENSITIVE_WORDS)}个词)")
    logging.info(f"  - 过滤动作: {FILTER_ACTION}")
    logging.info(f"  - 禁言功能: {MUTE_ENABLE}")
    logging.info(f"  - 默认禁言时长: {DEFAULT_MUTE_DURATION}秒")
    logging.info("=" * 50)


def get_china_tz():
    """获取中国时区"""
    return pytz.timezone("Asia/Shanghai")


def get_china_timestamp() -> float:
    """获取当前中国时间戳"""
    china_tz = get_china_tz()
    return datetime.now(china_tz).timestamp()


def load_messages():
    """从文件加载历史消息"""
    global room_messages
    try:
        if os.path.exists(MESSAGES_FILE):
            with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
                messages = json.load(f)
                room_messages = deque(messages, maxlen=MAX_ROOM_MESSAGES)
            logging.info(f"📝 已加载 {len(room_messages)} 条聊天室历史消息")
        else:
            room_messages = deque(maxlen=MAX_ROOM_MESSAGES)
            logging.info("📝 聊天室消息文件不存在，创建新文件")
    except Exception as e:
        logging.error(f"加载聊天室消息失败: {e}")
        room_messages = deque(maxlen=MAX_ROOM_MESSAGES)


def save_messages():
    """保存消息到文件"""
    try:
        with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(room_messages), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"保存聊天室消息失败: {e}")


def filter_room_sensitive_words(text: str) -> tuple:
    """
    过滤敏感词
    返回: (过滤后的文本, 是否通过检查)
    """
    if not FILTER_ENABLE or not SENSITIVE_WORDS:
        return text, True

    filtered_text = text
    has_sensitive = False

    sorted_words = sorted(SENSITIVE_WORDS, key=len, reverse=True)

    for word in sorted_words:
        if word in filtered_text:
            has_sensitive = True
            logging.warning(f"⚠️ [聊天室] 检测到敏感词: '{word}' 在消息: '{text}'")
            if FILTER_ACTION == "replace":
                filtered_text = filtered_text.replace(word, "*" * len(word))
                logging.info(f"  → 已替换为: '{filtered_text}'")
            elif FILTER_ACTION == "reject" or FILTER_ACTION == "warn":
                pass

    if has_sensitive:
        logging.warning(f"🚫 [聊天室] 消息包含敏感词，结果: 有效={not has_sensitive}")
    else:
        logging.info(f"✓ [聊天室] 消息通过敏感词检查")

    if FILTER_ACTION == "reject" and has_sensitive:
        return text, False

    return filtered_text, True


def check_muted(ip: str) -> Optional[Dict]:
    """检查用户是否被禁言"""
    if not MUTE_ENABLE:
        return None

    if ip in muted_users:
        mute_info = muted_users[ip]
        current_time = get_china_timestamp()
        remaining = int(mute_info['until'] - current_time)
        if remaining > 0:
            return {
                'remaining': remaining,
                'reason': mute_info.get('reason', '违规行为')
            }
        else:
            del muted_users[ip]
            logging.info(f"🔓 [聊天室] 用户 {ip} 禁言已自动解除")

    return None


def mute_user(ip: str, reason: str = "违规行为", duration: int = None) -> Dict:
    """禁言用户"""
    if duration is None:
        duration = DEFAULT_MUTE_DURATION

    current_time = get_china_timestamp()
    muted_users[ip] = {
        'until': current_time + duration,
        'reason': reason,
        'duration': duration
    }

    logging.info(f"🔒 [聊天室] 禁言用户: {ip}, 原因: {reason}, 时长: {duration}秒")
    return {
        'ip': ip,
        'until': current_time + duration,
        'remaining': duration,
        'reason': reason
    }


def unmute_user(ip: str) -> bool:
    """解禁用户"""
    if ip in muted_users:
        del muted_users[ip]
        logging.info(f"🔓 [聊天室] 解禁用户: {ip}")
        return True
    return False


def get_muted_list() -> List[Dict]:
    """获取禁言用户列表"""
    muted_list = []
    current_time = get_china_timestamp()

    for ip, info in list(muted_users.items()):
        remaining = int(info['until'] - current_time)
        if remaining > 0:
            muted_list.append({
                'ip': ip,
                'remaining': remaining,
                'reason': info.get('reason', '违规行为')
            })
        else:
            del muted_users[ip]

    return muted_list


def add_online_user(sid: str, ip: str, username: str):
    """添加在线用户"""
    online_users[sid] = {
        'ip': ip,
        'username': username,
        'join_time': get_china_timestamp()
    }
    logging.info(f"👤 [聊天室] 用户加入: {username} ({ip}), SID: {sid[:8]}...")


def remove_online_user(sid: str) -> Optional[Dict]:
    """移除在线用户"""
    if sid in online_users:
        user_info = online_users.pop(sid)
        logging.info(f"👋 [聊天室] 用户离开: {user_info['username']} ({user_info['ip']})")
        return user_info
    return None


def get_online_users() -> List[Dict]:
    """获取在线用户列表"""
    return list(online_users.values())


def get_online_count() -> int:
    """获取在线用户数（按IP去重）"""
    unique_ips = set(user['ip'] for user in online_users.values())
    return len(unique_ips)


def create_message(username: str, content: str, ip: str, msg_type: str = "user") -> Dict:
    """创建消息对象"""
    return {
        'id': str(uuid.uuid4())[:12],
        'username': username[:MAX_USERNAME_LENGTH],
        'content': content[:MAX_MESSAGE_LENGTH],
        'timestamp': get_china_timestamp(),
        'type': msg_type,
        'ip': ip
    }


def add_message(message: Dict):
    """添加消息到历史记录"""
    room_messages.append(message)
    save_messages()
    logging.info(f"💬 [聊天室] 新消息: {message['username']} - {message['content'][:50]}...")


def get_recent_messages(limit: int = 100) -> List[Dict]:
    """获取最近的消息"""
    return list(room_messages)[-limit:]


def init_live_chatroom():
    """初始化聊天室"""
    load_live_chatroom_config()
    load_messages()
    logging.info("✅ 在线聊天室模块初始化完成")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_live_chatroom()
