#!/usr/bin/env python3
"""
配置管理器 - 统一配置加载和缓存
"""
import os
import sys
import time
import yaml
from typing import Any, Dict, Optional, List
import logging


class ConfigManager:
    """配置管理器 - 单例模式，支持配置热更新"""

    _instance: Optional['ConfigManager'] = None
    _config: Optional[Dict] = None
    _last_modified: float = 0
    _cache_duration: float = 1.0  # 配置缓存时间（秒）

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_config_path'):
            self._config_path = self._find_config_file()
            self._watchers: list = []
            logging.info(f"📁 配置文件路径: {self._config_path}")

    def _find_config_file(self) -> str:
        """
        查找配置文件
        搜索顺序：
        1. 环境变量 CONFIG_PATH
        2. 当前目录 config.yaml
        3. 脚本所在目录 config.yaml
        4. 当前目录 config.yml
        5. 脚本所在目录 config.yml
        """
        # 1. 环境变量
        env_path = os.environ.get('CONFIG_PATH')
        if env_path and os.path.exists(env_path):
            return env_path

        # 搜索目录列表
        search_dirs = [
            os.getcwd(),
            os.path.dirname(os.path.abspath(__file__)),
        ]

        # 搜索文件名列表
        config_names = ['config.yaml', 'config.yml']

        for search_dir in search_dirs:
            for config_name in config_names:
                config_path = os.path.join(search_dir, config_name)
                if os.path.exists(config_path):
                    return config_path

        # 如果都没找到，返回默认路径（当前目录的 config.yaml）
        default_path = os.path.join(os.getcwd(), 'config.yaml')
        logging.warning(f"⚠️ 未找到配置文件，将使用默认路径: {default_path}")
        return default_path

    def _should_reload(self) -> bool:
        """检查是否需要重新加载配置"""
        if self._config is None:
            return True

        if not os.path.exists(self._config_path):
            return False

        try:
            current_mtime = os.path.getmtime(self._config_path)
            return current_mtime > self._last_modified
        except OSError:
            return False

    def _load_config(self) -> Dict:
        """从文件加载配置"""
        if not os.path.exists(self._config_path):
            logging.warning(f"配置文件不存在: {os.path.abspath(self._config_path)}")
            return {}

        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
                self._last_modified = os.path.getmtime(self._config_path)
                logging.info(f"✓ 配置文件已加载: {os.path.abspath(self._config_path)}")

                # 通知观察者
                for watcher in self._watchers:
                    try:
                        watcher(self._config)
                    except Exception as e:
                        logging.error(f"配置观察者执行失败: {e}")

                return self._config
        except yaml.YAMLError as e:
            logging.error(f"配置文件解析失败: {e}")
            return self._config or {}
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            return self._config or {}

    def get_config(self) -> Dict:
        """获取完整配置（带缓存）"""
        current_time = time.time()

        if self._config is None or current_time - self._last_modified > self._cache_duration:
            if self._should_reload():
                self._load_config()

        return self._config or {}

    def get(self, *keys: str, default: Any = None) -> Any:
        """
        安全获取嵌套配置值
        用法: config.get("app", "port", default=8080)
        """
        config = self.get_config()
        result = config

        for key in keys:
            if isinstance(result, dict):
                result = result.get(key)
                if result is None:
                    return default
            else:
                return default

        return result if result is not None else default

    def get_section(self, section: str) -> Dict:
        """获取配置节"""
        return self.get_config().get(section, {})

    def reload(self) -> Dict:
        """强制重新加载配置"""
        self._last_modified = 0
        return self._load_config()

    def save_config(self, config: Dict) -> bool:
        """保存配置到文件"""
        try:
            with open(self._config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False, indent=2)
            self._config = config
            self._last_modified = os.path.getmtime(self._config_path)
            logging.info(f"✓ 配置文件已保存: {os.path.abspath(self._config_path)}")
            
            for watcher in self._watchers:
                try:
                    watcher(self._config)
                except Exception as e:
                    logging.error(f"配置观察者执行失败: {e}")
            
            return True
        except Exception as e:
            logging.error(f"❌ 保存配置文件失败: {e}")
            return False

    def update_room_config(self, room_id: int, updates: Dict) -> bool:
        """更新指定房间的配置"""
        config = self.get_config()
        
        if 'multi_room' not in config:
            config['multi_room'] = {'enable': True, 'rooms': []}
        
        if 'rooms' not in config['multi_room']:
            config['multi_room']['rooms'] = []
        
        rooms = config['multi_room']['rooms']
        found = False
        
        for i, room in enumerate(rooms):
            if isinstance(room, dict) and int(room.get('room_id', 0)) == room_id:
                rooms[i].update(updates)
                found = True
                break
        
        if not found:
            logging.warning(f"⚠️ 未找到房间 {room_id}，无法更新配置")
            return False
        
        return self.save_config(config)

    def add_room_config(self, room_data: Dict) -> bool:
        """添加新房间配置"""
        config = self.get_config()
        
        if 'multi_room' not in config:
            config['multi_room'] = {'enable': True, 'rooms': []}
        
        if 'rooms' not in config['multi_room']:
            config['multi_room']['rooms'] = []
        
        room_id = room_data.get('room_id')
        if not room_id:
            logging.error("❌ 房间ID不能为空")
            return False
        
        for room in config['multi_room']['rooms']:
            if isinstance(room, dict) and int(room.get('room_id', 0)) == int(room_id):
                logging.warning(f"⚠️ 房间 {room_id} 已存在")
                return False
        
        new_room = {
            'room_id': int(room_id),
            'nickname': room_data.get('nickname', f"直播间 {room_id}"),
            'enabled': room_data.get('enabled', True),
            'auto_clip_enabled': room_data.get('auto_clip_enabled', True),
            'record_folder': room_data.get('record_folder', '')
        }
        
        config['multi_room']['rooms'].append(new_room)
        
        return self.save_config(config)

    def remove_room_config(self, room_id: int) -> bool:
        """删除房间配置"""
        config = self.get_config()
        
        if 'multi_room' not in config or 'rooms' not in config['multi_room']:
            return False
        
        rooms = config['multi_room']['rooms']
        original_length = len(rooms)
        
        config['multi_room']['rooms'] = [
            room for room in rooms
            if not (isinstance(room, dict) and int(room.get('room_id', 0)) == room_id)
        ]
        
        if len(config['multi_room']['rooms']) == original_length:
            logging.warning(f"⚠️ 未找到房间 {room_id}")
            return False
        
        return self.save_config(config)

    def add_watcher(self, watcher: callable):
        """添加配置变更观察者"""
        if watcher not in self._watchers:
            self._watchers.append(watcher)

    def remove_watcher(self, watcher: callable):
        """移除配置变更观察者"""
        if watcher in self._watchers:
            self._watchers.remove(watcher)


# 创建全局配置管理器实例
config_manager = ConfigManager()


# 兼容旧接口
def load_config() -> Dict:
    """兼容旧接口"""
    return config_manager.get_config()


def get_config(*keys, default=None) -> Any:
    """兼容旧接口
    
    用法:
        get_config() -> 完整配置
        get_config("app") -> app 节
        get_config("app", "port") -> app.port
        get_config("app", "port", default=8080) -> app.port，默认 8080
    """
    if len(keys) == 0:
        return config_manager.get_config()
    elif len(keys) == 1:
        return config_manager.get_section(keys[0])
    elif len(keys) >= 2:
        return config_manager.get(*keys, default=default)


def get_api_urls(room_id: int) -> list:
    """获取B站API URL列表"""
    urls = config_manager.get("bilibili", "api_urls", default=[])
    return [url.format(room_id=room_id) for url in urls]


def get_bilibili_headers(room_id: int) -> Dict:
    """获取B站请求头"""
    headers = config_manager.get("bilibili", "headers", default={})
    return {
        k: v.format(room_id=room_id) if '{room_id}' in v else v
        for k, v in headers.items()
    }


def is_multi_room_enabled() -> bool:
    """检查是否启用多房间监控"""
    return config_manager.get("multi_room", "enable", default=False)


def get_multi_room_config() -> List[Dict]:
    """
    获取多房间配置列表
    返回格式: [{'room_id': int, 'nickname': str, 'enabled': bool}, ...]
    """
    # 先检查是否启用多房间
    multi_room_enabled = config_manager.get("multi_room", "enable", default=False)
    logging.info(f"📊 多房间配置读取: enable={multi_room_enabled}")
    
    # 获取 rooms 配置
    rooms = config_manager.get("multi_room", "rooms", default=[])
    logging.info(f"📊 多房间配置原始数据: rooms={rooms}")
    
    if not isinstance(rooms, list):
        rooms = []
        logging.warning("⚠️ multi_room.rooms 不是列表类型，将使用空列表")
    
    # 处理每个房间配置
    processed_rooms = []
    for idx, room in enumerate(rooms):
        if isinstance(room, dict):
            room_id = room.get("room_id")
            if room_id:
                try:
                    room_id = int(room_id)
                    nickname = room.get("nickname", f"直播间 {room_id}")
                    enabled = room.get("enabled", True)
                    auto_clip_enabled = room.get("auto_clip_enabled", True)
                    record_folder = room.get("record_folder", "")
                    processed_rooms.append({
                        "room_id": room_id,
                        "nickname": nickname,
                        "enabled": enabled,
                        "auto_clip_enabled": auto_clip_enabled,
                        "record_folder": record_folder
                    })
                    logging.info(f"📊 房间配置 [{idx}]: room_id={room_id}, nickname={nickname}, enabled={enabled}, auto_clip={auto_clip_enabled}")
                except (ValueError, TypeError):
                    logging.error(f"❌ 房间ID格式错误: {room_id}")
                    continue
            else:
                logging.warning(f"⚠️ 房间配置缺少 room_id: {room}")
        else:
            logging.warning(f"⚠️ 房间配置不是字典类型: {room}")
    
    logging.info(f"📊 处理后的房间列表: {processed_rooms}")
    
    # 如果没有配置多房间但启用了多房间功能，回退到默认房间
    if multi_room_enabled and not processed_rooms:
        default_room_id = config_manager.get("bilibili", "room_id", default=22391541)
        logging.warning(f"⚠️ 启用了多房间但未配置房间，回退到默认房间: {default_room_id}")
        processed_rooms.append({
            "room_id": default_room_id,
            "nickname": "默认直播间",
            "enabled": True,
            "auto_clip_enabled": True,
            "record_folder": ""
        })
    
    return processed_rooms


def get_enabled_rooms() -> List[Dict]:
    """获取所有启用的房间列表"""
    rooms = get_multi_room_config()
    return [room for room in rooms if room.get("enabled", True)]
