#!/usr/bin/env python3
"""
自动切片触发服务
- 弹幕监控识别关键词时自动触发视频切片
- 支持配置切片时间窗口
- 支持切片队列管理
- 支持切片状态跟踪
"""

import asyncio
import logging
import os
import time
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from pathlib import Path
from collections import deque
import threading

try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False


class ClipTriggerStatus(Enum):
    """切片触发状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ClipTriggerRequest:
    """切片触发请求"""
    request_id: str
    room_id: int
    room_title: str
    keyword: str
    username: str
    danmaku_content: str
    danmaku_timestamp: float
    trigger_time: float
    
    start_offset_seconds: float = 0.0
    duration_seconds: float = 60.0
    
    video_source: Optional[str] = None
    status: ClipTriggerStatus = ClipTriggerStatus.PENDING
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    live_duration: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'request_id': self.request_id,
            'room_id': self.room_id,
            'room_title': self.room_title,
            'keyword': self.keyword,
            'username': self.username,
            'danmaku_content': self.danmaku_content,
            'danmaku_timestamp': self.danmaku_timestamp,
            'trigger_time': self.trigger_time,
            'start_offset_seconds': self.start_offset_seconds,
            'duration_seconds': self.duration_seconds,
            'video_source': self.video_source,
            'status': self.status.value,
            'output_path': self.output_path,
            'error_message': self.error_message,
            'metadata': self.metadata,
            'live_duration': self.live_duration
        }


@dataclass
class AutoClipConfig:
    """自动切片配置"""
    enable_auto_clip: bool = True
    pre_buffer_seconds: float = 30.0
    post_buffer_seconds: float = 30.0
    max_concurrent_clips: int = 3
    clip_queue_size: int = 100
    video_output_dir: str = "auto_clips"
    enable_clip_notification: bool = True
    clip_cooldown_seconds: float = 60.0
    deduplication_window_seconds: float = 120.0
    enable_deduplication: bool = True


class AutoClipTrigger:
    """自动切片触发器 - 连接弹幕监控和视频切片"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config: Optional[AutoClipConfig] = None):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self.config = config or AutoClipConfig()
        
        self._clip_queue: deque = deque(maxlen=self.config.clip_queue_size)
        self._processing_tasks: Dict[str, asyncio.Task] = {}
        self._completed_clips: List[ClipTriggerRequest] = []
        self._failed_clips: List[ClipTriggerRequest] = []
        
        self._last_clip_time: Dict[int, float] = {}
        self._recent_clip_positions: Dict[int, List[float]] = {}
        
        self._is_running = False
        self._worker_task: Optional[asyncio.Task] = None
        
        self._notification_callbacks: List[callable] = []
        
        self._semaphore: Optional[asyncio.Semaphore] = None
        
        self._output_dir = Path(self.config.video_output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        
        logging.info("=" * 60)
        logging.info("🎬 自动切片触发器初始化完成")
        logging.info(f"   - 自动切片: {'启用' if self.config.enable_auto_clip else '禁用'}")
        logging.info(f"   - 前置缓冲: {self.config.pre_buffer_seconds}秒")
        logging.info(f"   - 后置缓冲: {self.config.post_buffer_seconds}秒")
        logging.info(f"   - 最大并发: {self.config.max_concurrent_clips}")
        logging.info(f"   - 输出目录: {self._output_dir.absolute()}")
        logging.info(f"   - 切片冷却: {self.config.clip_cooldown_seconds}秒")
        logging.info(f"   - 去重窗口: {self.config.deduplication_window_seconds}秒")
        logging.info("=" * 60)
    
    def _get_china_tz(self):
        """获取中国时区"""
        if PYTZ_AVAILABLE:
            return pytz.timezone("Asia/Shanghai")
        return None
    
    def _get_china_timestamp(self) -> float:
        """获取当前中国时间戳"""
        if PYTZ_AVAILABLE:
            china_tz = self._get_china_tz()
            return datetime.now(china_tz).timestamp()
        return time.time()
    
    def _get_china_time_str(self) -> str:
        """获取当前中国时间字符串"""
        if PYTZ_AVAILABLE:
            china_tz = self._get_china_tz()
            china_time = datetime.now(china_tz)
            return china_time.strftime('%Y-%m-%d %H:%M:%S')
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def add_notification_callback(self, callback: callable):
        """添加通知回调"""
        if callback not in self._notification_callbacks:
            self._notification_callbacks.append(callback)
            logging.info(f"已添加通知回调")
    
    def remove_notification_callback(self, callback: callable):
        """移除通知回调"""
        if callback in self._notification_callbacks:
            self._notification_callbacks.remove(callback)
            logging.info(f"已移除通知回调")
    
    async def _notify(self, event_type: str, data: Dict[str, Any]):
        """发送通知"""
        for callback in self._notification_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_type, data)
                else:
                    callback(event_type, data)
            except Exception as e:
                logging.error(f"通知回调执行失败: {e}")
    
    def _should_deduplicate(self, room_id: int, danmaku_timestamp: float) -> bool:
        """检查是否应该去重"""
        if not self.config.enable_deduplication:
            return False
        
        if room_id not in self._recent_clip_positions:
            self._recent_clip_positions[room_id] = []
            return False
        
        recent_positions = self._recent_clip_positions[room_id]
        current_time = self._get_china_timestamp()
        cutoff_time = current_time - self.config.deduplication_window_seconds
        
        recent_positions = [t for t in recent_positions if t > cutoff_time]
        self._recent_clip_positions[room_id] = recent_positions
        
        for pos in recent_positions:
            if abs(danmaku_timestamp - pos) < self.config.deduplication_window_seconds:
                logging.info(f"检测到重复切片请求，跳过 (时间差: {abs(danmaku_timestamp - pos):.1f}秒")
                return True
        
        return False
    
    def _check_cooldown(self, room_id: int) -> bool:
        """检查冷却时间"""
        if room_id not in self._last_clip_time:
            return True
        
        current_time = self._get_china_timestamp()
        elapsed = current_time - self._last_clip_time[room_id]
        
        if elapsed < self.config.clip_cooldown_seconds:
            remaining = self.config.clip_cooldown_seconds - elapsed
            logging.info(f"切片冷却中，还需等待 {remaining:.1f} 秒")
            return False
        
        return True
    
    def trigger_clip(
        self,
        room_id: int,
        room_title: str,
        keyword: str,
        username: str,
        danmaku_content: str,
        danmaku_timestamp: float,
        video_source: Optional[str] = None,
        live_duration: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ClipTriggerRequest]:
        """
        触发切片请求
        
        Args:
            room_id: 直播间ID
            room_title: 直播间标题
            keyword: 匹配到的关键词
            username: 发送弹幕的用户名
            danmaku_content: 弹幕内容
            danmaku_timestamp: 弹幕发送时间戳
            video_source: 视频源路径（可选）
            live_duration: 直播经过时间（可选）
            metadata: 额外元数据（可选）
        
        Returns:
            ClipTriggerRequest 或 None（如果被冷却/去重跳过）
        """
        if not self.config.enable_auto_clip:
            logging.debug("自动切片功能已禁用")
            return None
        
        if not self._check_cooldown(room_id):
            logging.debug("切片冷却中，跳过")
            return None
        
        if self._should_deduplicate(room_id, danmaku_timestamp):
            logging.debug("重复切片请求，跳过")
            return None
        
        import uuid
        request_id = str(uuid.uuid4())[:12]
        
        request = ClipTriggerRequest(
            request_id=request_id,
            room_id=room_id,
            room_title=room_title,
            keyword=keyword,
            username=username,
            danmaku_content=danmaku_content,
            danmaku_timestamp=danmaku_timestamp,
            trigger_time=self._get_china_timestamp(),
            start_offset_seconds=danmaku_timestamp - self.config.pre_buffer_seconds,
            duration_seconds=self.config.pre_buffer_seconds + self.config.post_buffer_seconds,
            video_source=video_source,
            live_duration=live_duration,
            metadata=metadata or {}
        )
        
        self._clip_queue.append(request)
        
        if room_id not in self._recent_clip_positions:
            self._recent_clip_positions[room_id] = []
        self._recent_clip_positions[room_id].append(danmaku_timestamp)
        self._last_clip_time[room_id] = self._get_china_timestamp()
        
        logging.info(f"📋 切片请求已入队:")
        logging.info(f"   - 请求ID: {request_id}")
        logging.info(f"   - 直播间: {room_title} ({room_id})")
        logging.info(f"   - 关键词: {keyword}")
        logging.info(f"   - 发送者: {username}")
        logging.info(f"   - 弹幕内容: {danmaku_content[:50]}...")
        logging.info(f"   - 切片范围: {request.start_offset_seconds:.1f}s 开始，时长 {request.duration_seconds:.1f}s")
        logging.info(f"   - 队列当前大小: {len(self._clip_queue)}")
        
        asyncio.create_task(self._notify('clip_queued', request.to_dict()))
        
        return request
    
    async def _process_clip_request(self, request: ClipTriggerRequest):
        """处理单个切片请求"""
        request.status = ClipTriggerStatus.PROCESSING
        
        try:
            logging.info(f"🎬 开始处理切片请求: {request.request_id}")
            
            output_filename = self._generate_output_filename(request)
            output_path = self._output_dir / output_filename
            
            request.output_path = str(output_path)
            
            success = await self._extract_video_clip(request)
            
            if success:
                request.status = ClipTriggerStatus.SUCCESS
                self._completed_clips.append(request)
                
                logging.info(f"✅ 切片成功: {output_path}")
                
                await self._notify('clip_completed', request.to_dict())
            else:
                request.status = ClipTriggerStatus.FAILED
                request.error_message = "视频提取失败"
                self._failed_clips.append(request)
                
                logging.error(f"❌ 切片失败: {request.request_id}")
                
                await self._notify('clip_failed', request.to_dict())
                
        except Exception as e:
            request.status = ClipTriggerStatus.FAILED
            request.error_message = str(e)
            self._failed_clips.append(request)
            
            logging.error(f"❌ 处理切片请求时出错: {e}")
            
            await self._notify('clip_failed', request.to_dict())
        
        finally:
            if request.request_id in self._processing_tasks:
                del self._processing_tasks[request.request_id]
    
    def _generate_output_filename(self, request: ClipTriggerRequest) -> str:
        """生成输出文件名"""
        safe_room_title = "".join(
            c for c in request.room_title if c.isalnum() or c in (' ', '-', '_')
        ).strip()[:30]
        
        china_time = self._get_china_time_str()
        safe_time = china_time.replace(':', '-').replace(' ', '_')
        
        return (
            f"clip_{request.room_id}_{safe_time}_"
            f"{request.request_id}_"
            f"{safe_room_title}.mp4"
        )
    
    async def _extract_video_clip(self, request: ClipTriggerRequest) -> bool:
        """
        提取视频片段
        
        这里需要根据实际情况实现视频提取逻辑。
        目前是一个占位实现，需要根据实际的视频源进行集成。
        
        可能的视频源:
        1. 直播录制文件（需要从录制服务获取）
        2. 直播流（需要实时录制）
        3. 已存在的视频文件（来自后端的项目视频
        """
        try:
            if request.video_source and os.path.exists(request.video_source):
                return await self._extract_from_existing_video(request)
            else:
                return await self._extract_from_live_recording(request)
                
        except Exception as e:
            logging.error(f"视频提取异常: {e}")
            return False
    
    async def _extract_from_existing_video(self, request: ClipTriggerRequest) -> bool:
        """从现有视频文件提取片段"""
        try:
            from pathlib import Path
            
            video_path = Path(request.video_source)
            output_path = Path(request.output_path)
            
            if not video_path.exists():
                logging.error(f"视频文件不存在: {video_path}")
                return False
            
            try:
                import sys
                backend_path = str(Path(__file__).parent.parent / 'backend')
                if backend_path not in sys.path:
                    sys.path.insert(0, backend_path)
                from utils.video_processor import VideoProcessor
                
                start_time = request.start_offset_seconds
                end_time = request.start_offset_seconds + request.duration_seconds
                
                ffmpeg_start = VideoProcessor.convert_seconds_to_ffmpeg_time(start_time)
                ffmpeg_end = VideoProcessor.convert_seconds_to_ffmpeg_time(end_time)
                
                success = VideoProcessor.extract_clip(
                    video_path,
                    output_path,
                    ffmpeg_start,
                    ffmpeg_end,
                    use_stream_copy=True
                )
                
                return success
                
            except ImportError as e:
                logging.warning(f"无法导入 VideoProcessor: {e}")
                return self._dummy_extract(request)
            
        except Exception as e:
            logging.error(f"从现有视频提取失败: {e}")
            return False
    
    async def _extract_from_live_recording(self, request: ClipTriggerRequest) -> bool:
        """从直播录制中提取片段"""
        logging.warning("从直播录制提取需要集成录制服务")
        
        return self._dummy_extract(request)
    
    def _dummy_extract(self, request: ClipTriggerRequest) -> bool:
        """模拟提取（用于测试）"""
        output_path = Path(request.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(json.dumps(request.to_dict(), ensure_ascii=False, indent=2))
        
        logging.info(f"模拟切片文件已创建: {output_path}")
        return True
    
    async def _worker_loop(self):
        """工作循环 - 处理切片队列"""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.config.max_concurrent_clips)
        
        while self._is_running:
            try:
                if len(self._processing_tasks) < self.config.max_concurrent_clips and self._clip_queue:
                    request = self._clip_queue.popleft()
                    
                    if request.status == ClipTriggerStatus.PENDING:
                        task = asyncio.create_task(self._process_clip_request(request))
                        self._processing_tasks[request.request_id] = task
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logging.error(f"工作循环异常: {e}")
                await asyncio.sleep(1)
    
    async def start(self):
        """启动自动切片触发器"""
        if self._is_running:
            logging.warning("自动切片触发器已经在运行")
            return
        
        self._is_running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        
        logging.info("🚀 自动切片触发器已启动")
        
        await self._notify('service_started', {
            'timestamp': self._get_china_timestamp(),
            'config': {
                'enable_auto_clip': self.config.enable_auto_clip,
                'pre_buffer_seconds': self.config.pre_buffer_seconds,
                'post_buffer_seconds': self.config.post_buffer_seconds,
                'max_concurrent_clips': self.config.max_concurrent_clips,
                'clip_queue_size': self.config.clip_queue_size
            }
        })
    
    async def stop(self):
        """停止自动切片触发器"""
        if not self._is_running:
            logging.warning("自动切片触发器已经停止")
            return
        
        self._is_running = False
        
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        for request_id, task in list(self._processing_tasks.items()):
            if not task.done():
                task.cancel()
        
        logging.info("🛑 自动切片触发器已停止")
        
        await self._notify('service_stopped', {
            'timestamp': self._get_china_timestamp(),
            'completed_count': len(self._completed_clips),
            'failed_count': len(self._failed_clips)
        })
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'is_running': self._is_running,
            'queue_size': len(self._clip_queue),
            'processing_count': len(self._processing_tasks),
            'completed_count': len(self._completed_clips),
            'failed_count': len(self._failed_clips),
            'config': {
                'enable_auto_clip': self.config.enable_auto_clip,
                'pre_buffer_seconds': self.config.pre_buffer_seconds,
                'post_buffer_seconds': self.config.post_buffer_seconds,
                'max_concurrent_clips': self.config.max_concurrent_clips,
                'clip_cooldown_seconds': self.config.clip_cooldown_seconds,
                'deduplication_window_seconds': self.config.deduplication_window_seconds,
                'enable_deduplication': self.config.enable_deduplication
            },
            'recent_clips': [
                clip.to_dict() for clip in self._completed_clips[-10:]
            ] if self._completed_clips else []
        }
    
    def get_pending_requests(self) -> List[Dict[str, Any]]:
        """获取待处理的请求列表"""
        return [request.to_dict() for request in list(self._clip_queue)]
    
    def get_completed_requests(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取已完成的请求列表"""
        return [request.to_dict() for request in self._completed_clips[-limit:]]
    
    def update_config(self, **kwargs):
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                old_value = getattr(self.config, key)
                setattr(self.config, key, value)
                logging.info(f"配置更新: {key} = {old_value} -> {value}")
        
        if 'max_concurrent_clips' in kwargs:
            self._semaphore = asyncio.Semaphore(self.config.max_concurrent_clips)
            logging.info(f"已重新创建信号量，并发数: {self.config.max_concurrent_clips}")


_auto_clip_trigger_instance: Optional[AutoClipTrigger] = None


def get_auto_clip_trigger(config: Optional[AutoClipConfig] = None) -> AutoClipTrigger:
    """获取全局自动切片触发器实例"""
    global _auto_clip_trigger_instance
    if _auto_clip_trigger_instance is None:
        _auto_clip_trigger_instance = AutoClipTrigger(config)
    return _auto_clip_trigger_instance


def load_auto_clip_config_from_yaml(config_manager) -> AutoClipConfig:
    """从YAML配置加载自动切片配置"""
    config = AutoClipConfig()
    
    auto_clip_config = config_manager.get("auto_clip") or {}
    
    config.enable_auto_clip = auto_clip_config.get("enable", True)
    config.pre_buffer_seconds = auto_clip_config.get("pre_buffer_seconds", 30.0)
    config.post_buffer_seconds = auto_clip_config.get("post_buffer_seconds", 30.0)
    config.max_concurrent_clips = auto_clip_config.get("max_concurrent_clips", 3)
    config.clip_queue_size = auto_clip_config.get("clip_queue_size", 100)
    config.video_output_dir = auto_clip_config.get("output_dir", "auto_clips")
    config.enable_clip_notification = auto_clip_config.get("enable_notification", True)
    config.clip_cooldown_seconds = auto_clip_config.get("clip_cooldown_seconds", 60.0)
    config.deduplication_window_seconds = auto_clip_config.get("deduplication_window_seconds", 120.0)
    config.enable_deduplication = auto_clip_config.get("enable_deduplication", True)
    
    return config
