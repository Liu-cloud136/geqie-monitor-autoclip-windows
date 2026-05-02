#!/usr/bin/env python3
"""
直播系统集成管理器
- 弹幕监控 → 识别关键词 → 记录时间点 → 自动录制 → 触发切片 → 生成报告
- 完整的工作流集成
- 多房间支持
"""

import asyncio
import logging
import os
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from collections import defaultdict

try:
    from live_stream_api import BilibiliLiveStreamAPI, LiveStreamInfo, StreamQuality
    LIVE_STREAM_API_AVAILABLE = True
except ImportError:
    LIVE_STREAM_API_AVAILABLE = False
    logging.warning("live_stream_api 模块不可用")

try:
    from live_recorder import (
        BilibiliLiveRecorder, RecordingStatus, RecordingStats,
        get_recorder, get_all_recorders, remove_recorder
    )
    LIVE_RECORDER_AVAILABLE = True
except ImportError:
    LIVE_RECORDER_AVAILABLE = False
    logging.warning("live_recorder 模块不可用")

try:
    from live_clip_manager import (
        LiveClipManager, ClipTriggerType, ClipStatus,
        LiveClipRequest, ClipReport, get_clip_manager
    )
    LIVE_CLIP_MANAGER_AVAILABLE = True
except ImportError:
    LIVE_CLIP_MANAGER_AVAILABLE = False
    logging.warning("live_clip_manager 模块不可用")


class IntegrationStatus(Enum):
    """集成系统状态"""
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class RoomIntegrationState:
    """房间集成状态"""
    room_id: int
    nickname: str = ""
    
    monitor_enabled: bool = False
    recorder_enabled: bool = False
    auto_clip_enabled: bool = False
    
    monitor_status: str = "idle"
    recorder_status: str = "idle"
    
    last_keyword_time: float = 0
    last_clip_time: float = 0
    
    keyword_count: int = 0
    clip_count: int = 0
    
    recording_start_time: float = 0
    recording_elapsed_seconds: float = 0
    
    metadata: Dict[str, Any] = field(default_factory=dict)


class LiveIntegrationManager:
    """
    直播系统集成管理器
    协调弹幕监控、直播录制和自动切片系统
    """
    
    def __init__(self,
                 output_dir: str = "live_recordings",
                 buffer_duration_seconds: int = 300,
                 segment_duration_seconds: int = 60,
                 pre_buffer_seconds: float = 30.0,
                 post_buffer_seconds: float = 30.0,
                 quality: str = "原画"):
        """
        初始化集成管理器
        
        Args:
            output_dir: 输出目录
            buffer_duration_seconds: 缓冲时长（秒）
            segment_duration_seconds: 片段时长（秒）
            pre_buffer_seconds: 切片前置缓冲
            post_buffer_seconds: 切片后置缓冲
            quality: 录制画质
        """
        self.output_dir = Path(output_dir)
        self.buffer_duration = buffer_duration_seconds
        self.segment_duration = segment_duration_seconds
        self.pre_buffer = pre_buffer_seconds
        self.post_buffer = post_buffer_seconds
        self.quality = quality
        
        self._rooms: Dict[int, RoomIntegrationState] = {}
        self._recorders: Dict[int, Any] = {}
        self._monitors: Dict[int, Any] = {}
        
        self._status = IntegrationStatus.IDLE
        self._is_running: bool = False
        
        self._callbacks: Dict[str, List[Callable]] = {
            'room_added': [],
            'room_removed': [],
            'recording_started': [],
            'recording_stopped': [],
            'keyword_detected': [],
            'clip_created': [],
            'clip_completed': [],
            'report_generated': [],
            'error': []
        }
        
        self._lock = threading.RLock()
        
        self._clip_manager: Optional[Any] = None
        self._init_clip_manager()
        
        logging.info("=" * 60)
        logging.info("🎬 直播系统集成管理器初始化")
        logging.info(f"   - 输出目录: {self.output_dir.absolute()}")
        logging.info(f"   - 缓冲时长: {buffer_duration_seconds}秒")
        logging.info(f"   - 片段时长: {segment_duration_seconds}秒")
        logging.info(f"   - 切片缓冲: 前置{pre_buffer_seconds}秒, 后置{post_buffer_seconds}秒")
        logging.info(f"   - 录制画质: {quality}")
        logging.info("=" * 60)
    
    def _init_clip_manager(self):
        """初始化切片管理器"""
        if LIVE_CLIP_MANAGER_AVAILABLE:
            self._clip_manager = get_clip_manager(
                pre_buffer_seconds=self.pre_buffer,
                post_buffer_seconds=self.post_buffer
            )
    
    def add_callback(self, event_type: str, callback: Callable):
        """添加事件回调"""
        if event_type in self._callbacks:
            self._callbacks[event_type].append(callback)
    
    def remove_callback(self, event_type: str, callback: Callable):
        """移除事件回调"""
        if event_type in self._callbacks and callback in self._callbacks[event_type]:
            self._callbacks[event_type].remove(callback)
    
    async def _notify(self, event_type: str, data: Any):
        """通知回调函数"""
        for callback in self._callbacks.get(event_type, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logging.error(f"回调执行失败 [{event_type}]: {e}")
    
    def add_room(self,
                  room_id: int,
                  nickname: str = "",
                  enable_monitor: bool = True,
                  enable_recorder: bool = True,
                  enable_auto_clip: bool = True,
                  credential: Dict = None,
                  headers: Dict = None) -> RoomIntegrationState:
        """
        添加房间进行监控和录制
        
        Args:
            room_id: 直播间ID
            nickname: 房间昵称
            enable_monitor: 启用弹幕监控
            enable_recorder: 启用直播录制
            enable_auto_clip: 启用自动切片
            credential: 登录凭证
            headers: 请求头
            
        Returns:
            RoomIntegrationState 对象
        """
        with self._lock:
            if room_id in self._rooms:
                logging.warning(f"房间 {room_id} 已存在")
                return self._rooms[room_id]
            
            state = RoomIntegrationState(
                room_id=room_id,
                nickname=nickname or f"直播间 {room_id}",
                monitor_enabled=enable_monitor,
                recorder_enabled=enable_recorder,
                auto_clip_enabled=enable_auto_clip
            )
            
            self._rooms[room_id] = state
            
            logging.info(f"✅ 已添加房间: {room_id} ({state.nickname})")
            logging.info(f"   - 弹幕监控: {'启用' if enable_monitor else '禁用'}")
            logging.info(f"   - 直播录制: {'启用' if enable_recorder else '禁用'}")
            logging.info(f"   - 自动切片: {'启用' if enable_auto_clip else '禁用'}")
            
            asyncio.create_task(self._notify('room_added', {
                'room_id': room_id,
                'nickname': state.nickname,
                'monitor_enabled': enable_monitor,
                'recorder_enabled': enable_recorder,
                'auto_clip_enabled': enable_auto_clip
            }))
            
            return state
    
    def remove_room(self, room_id: int) -> bool:
        """
        移除房间
        
        Args:
            room_id: 直播间ID
            
        Returns:
            是否成功
        """
        with self._lock:
            if room_id not in self._rooms:
                return False
            
            if room_id in self._recorders:
                recorder = self._recorders[room_id]
                try:
                    asyncio.create_task(recorder.stop())
                except Exception as e:
                    logging.warning(f"停止录制器失败: {e}")
                del self._recorders[room_id]
            
            del self._rooms[room_id]
            
            logging.info(f"✅ 已移除房间: {room_id}")
            
            asyncio.create_task(self._notify('room_removed', {
                'room_id': room_id
            }))
            
            return True
    
    async def start_room_recording(self,
                                    room_id: int,
                                    credential: Dict = None,
                                    headers: Dict = None) -> bool:
        """
        启动房间录制
        
        Args:
            room_id: 直播间ID
            credential: 登录凭证
            headers: 请求头
            
        Returns:
            是否成功启动
        """
        with self._lock:
            if room_id not in self._rooms:
                logging.error(f"房间 {room_id} 不存在")
                return False
            
            state = self._rooms[room_id]
            
            if not state.recorder_enabled:
                logging.warning(f"房间 {room_id} 的录制功能未启用")
                return False
        
        if not LIVE_RECORDER_AVAILABLE:
            logging.error("直播录制模块不可用")
            return False
        
        try:
            if room_id in self._recorders:
                recorder = self._recorders[room_id]
                if recorder.get_status() == RecordingStatus.RECORDING:
                    logging.warning(f"房间 {room_id} 已经在录制中")
                    return True
            
            recorder = get_recorder(
                room_id=room_id,
                output_dir=str(self.output_dir),
                buffer_duration_seconds=self.buffer_duration,
                segment_duration_seconds=self.segment_duration,
                quality=self.quality,
                credential=credential,
                headers=headers
            )
            
            self._recorders[room_id] = recorder
            
            success = await recorder.start()
            
            if success:
                with self._lock:
                    if room_id in self._rooms:
                        self._rooms[room_id].recorder_status = "recording"
                        self._rooms[room_id].recording_start_time = time.time()
                
                logging.info(f"✅ 房间 {room_id} 录制已启动")
                
                await self._notify('recording_started', {
                    'room_id': room_id,
                    'start_time': time.time()
                })
                
                return True
            else:
                logging.error(f"❌ 房间 {room_id} 录制启动失败")
                return False
                
        except Exception as e:
            logging.error(f"启动录制失败: {e}")
            return False
    
    async def stop_room_recording(self, room_id: int) -> bool:
        """
        停止房间录制
        
        Args:
            room_id: 直播间ID
            
        Returns:
            是否成功
        """
        if room_id not in self._recorders:
            return True
        
        try:
            recorder = self._recorders[room_id]
            await recorder.stop()
            
            with self._lock:
                if room_id in self._rooms:
                    self._rooms[room_id].recorder_status = "stopped"
            
            logging.info(f"✅ 房间 {room_id} 录制已停止")
            
            await self._notify('recording_stopped', {
                'room_id': room_id,
                'stop_time': time.time()
            })
            
            return True
            
        except Exception as e:
            logging.error(f"停止录制失败: {e}")
            return False
    
    async def on_keyword_detected(self,
                                    room_id: int,
                                    keyword: str,
                                    username: str,
                                    danmaku_content: str,
                                    timestamp: float = None,
                                    metadata: Dict = None) -> Optional[Any]:
        """
        当检测到关键词时触发
        
        Args:
            room_id: 直播间ID
            keyword: 关键词
            username: 用户名
            danmaku_content: 弹幕内容
            timestamp: 时间戳
            metadata: 额外元数据
            
        Returns:
            切片请求对象或 None
        """
        if timestamp is None:
            timestamp = time.time()
        
        with self._lock:
            if room_id not in self._rooms:
                logging.warning(f"关键词检测: 房间 {room_id} 未注册")
                return None
            
            state = self._rooms[room_id]
            state.keyword_count += 1
            state.last_keyword_time = timestamp
        
        logging.info(f"🔍 [房间 {room_id}] 检测到关键词: {keyword} (用户: {username})")
        
        await self._notify('keyword_detected', {
            'room_id': room_id,
            'keyword': keyword,
            'username': username,
            'danmaku_content': danmaku_content,
            'timestamp': timestamp
        })
        
        with self._lock:
            if room_id in self._rooms and not self._rooms[room_id].auto_clip_enabled:
                logging.info(f"房间 {room_id} 的自动切片功能未启用")
                return None
        
        if not LIVE_CLIP_MANAGER_AVAILABLE:
            logging.warning("切片管理器不可用")
            return None
        
        clip_request = self._clip_manager.create_clip_request(
            room_id=room_id,
            trigger_type=ClipTriggerType.KEYWORD,
            trigger_time=timestamp,
            keyword=keyword,
            username=username,
            danmaku_content=danmaku_content,
            metadata=metadata or {}
        )
        
        with self._lock:
            if room_id in self._rooms:
                self._rooms[room_id].last_clip_time = timestamp
                self._rooms[room_id].clip_count += 1
        
        await self._notify('clip_created', {
            'clip_id': clip_request.clip_id,
            'room_id': room_id,
            'keyword': keyword,
            'start_time': clip_request.start_time,
            'end_time': clip_request.end_time
        })
        
        if room_id in self._recorders:
            recorder = self._recorders[room_id]
            
            try:
                success = await self._clip_manager.process_clip(clip_request, recorder)
                
                if success:
                    logging.info(f"✅ [房间 {room_id}] 切片处理完成: {clip_request.clip_id}")
                else:
                    logging.error(f"❌ [房间 {room_id}] 切片处理失败: {clip_request.clip_id}")
                    
            except Exception as e:
                logging.error(f"处理切片异常: {e}")
        
        return clip_request
    
    async def generate_room_report(self,
                                     room_id: int,
                                     room_title: str = "") -> Optional[Any]:
        """
        生成房间切片报告
        
        Args:
            room_id: 直播间ID
            room_title: 房间标题
            
        Returns:
            ClipReport 对象或 None
        """
        if not LIVE_CLIP_MANAGER_AVAILABLE:
            logging.error("切片管理器不可用")
            return None
        
        report = await self._clip_manager.generate_report(
            room_id=room_id,
            room_title=room_title
        )
        
        if report:
            logging.info(f"📊 [房间 {room_id}] 报告已生成: {report.clip_count} 个切片")
            
            await self._notify('report_generated', {
                'room_id': room_id,
                'report_id': report.report_id,
                'clip_count': report.clip_count,
                'summary': report.summary
            })
        
        return report
    
    def get_room_state(self, room_id: int) -> Optional[RoomIntegrationState]:
        """获取房间状态"""
        with self._lock:
            state = self._rooms.get(room_id)
            if state and room_id in self._recorders:
                recorder = self._recorders[room_id]
                stats = recorder.get_stats()
                state.recording_elapsed_seconds = stats.elapsed_seconds
            return state
    
    def get_all_rooms(self) -> List[Dict]:
        """获取所有房间信息"""
        with self._lock:
            result = []
            for room_id, state in self._rooms.items():
                if room_id in self._recorders:
                    recorder = self._recorders[room_id]
                    stats = recorder.get_stats()
                    recorder_status = stats.status.value if hasattr(stats.status, 'value') else str(stats.status)
                else:
                    recorder_status = "idle"
                
                result.append({
                    'room_id': room_id,
                    'nickname': state.nickname,
                    'monitor_enabled': state.monitor_enabled,
                    'recorder_enabled': state.recorder_enabled,
                    'auto_clip_enabled': state.auto_clip_enabled,
                    'recorder_status': recorder_status,
                    'keyword_count': state.keyword_count,
                    'clip_count': state.clip_count,
                    'recording_elapsed_seconds': state.recording_elapsed_seconds
                })
            return result
    
    def get_stats(self) -> Dict:
        """获取系统统计"""
        with self._lock:
            total_keywords = sum(s.keyword_count for s in self._rooms.values())
            total_clips = sum(s.clip_count for s in self._rooms.values())
            recording_rooms = sum(
                1 for rid, s in self._rooms.items()
                if rid in self._recorders and 
                self._recorders[rid].get_status() == RecordingStatus.RECORDING
            )
            
            clip_stats = {}
            if self._clip_manager:
                clip_stats = self._clip_manager.get_stats()
        
        return {
            'status': self._status.value,
            'total_rooms': len(self._rooms),
            'recording_rooms': recording_rooms,
            'total_keywords': total_keywords,
            'total_clips': total_clips,
            'clip_manager_stats': clip_stats,
            'config': {
                'output_dir': str(self.output_dir.absolute()),
                'buffer_duration_seconds': self.buffer_duration,
                'segment_duration_seconds': self.segment_duration,
                'pre_buffer_seconds': self.pre_buffer,
                'post_buffer_seconds': self.post_buffer,
                'quality': self.quality
            }
        }
    
    async def start_all(self) -> int:
        """
        启动所有已配置房间的录制
        
        Returns:
            成功启动的房间数
        """
        self._status = IntegrationStatus.STARTING
        self._is_running = True
        
        success_count = 0
        
        with self._lock:
            room_ids = list(self._rooms.keys())
        
        for room_id in room_ids:
            with self._lock:
                if room_id not in self._rooms:
                    continue
                
                state = self._rooms[room_id]
                
                if not state.recorder_enabled:
                    continue
            
            success = await self.start_room_recording(room_id)
            if success:
                success_count += 1
        
        if success_count > 0:
            self._status = IntegrationStatus.RUNNING
        else:
            self._status = IntegrationStatus.IDLE
        
        logging.info(f"🚀 已启动 {success_count} 个房间的录制")
        return success_count
    
    async def stop_all(self):
        """停止所有房间的录制"""
        self._status = IntegrationStatus.STOPPING
        
        with self._lock:
            room_ids = list(self._rooms.keys())
        
        for room_id in room_ids:
            await self.stop_room_recording(room_id)
        
        self._is_running = False
        self._status = IntegrationStatus.IDLE
        
        logging.info("🛑 所有房间录制已停止")


_integration_manager_instance: Optional[LiveIntegrationManager] = None
_integration_manager_lock = threading.Lock()


def get_integration_manager(output_dir: str = "live_recordings",
                             buffer_duration_seconds: int = 300,
                             segment_duration_seconds: int = 60,
                             pre_buffer_seconds: float = 30.0,
                             post_buffer_seconds: float = 30.0,
                             quality: str = "原画") -> LiveIntegrationManager:
    """
    获取全局集成管理器实例
    
    Args:
        output_dir: 输出目录
        buffer_duration_seconds: 缓冲时长
        segment_duration_seconds: 片段时长
        pre_buffer_seconds: 前置缓冲
        post_buffer_seconds: 后置缓冲
        quality: 画质
        
    Returns:
        LiveIntegrationManager 实例
    """
    global _integration_manager_instance
    
    with _integration_manager_lock:
        if _integration_manager_instance is None:
            _integration_manager_instance = LiveIntegrationManager(
                output_dir=output_dir,
                buffer_duration_seconds=buffer_duration_seconds,
                segment_duration_seconds=segment_duration_seconds,
                pre_buffer_seconds=pre_buffer_seconds,
                post_buffer_seconds=post_buffer_seconds,
                quality=quality
            )
        return _integration_manager_instance
