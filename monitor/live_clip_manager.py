#!/usr/bin/env python3
"""
直播切片管理器
- 弹幕监控与录制系统的深度集成
- 关键词触发自动切片
- 切片报告生成
- 多房间协调管理
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


class ClipTriggerType(Enum):
    """切片触发类型"""
    KEYWORD = "keyword"
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    HIGHLIGHT = "highlight"


class ClipStatus(Enum):
    """切片状态"""
    PENDING = "pending"
    RECORDING = "recording"
    EXTRACTING = "extracting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class LiveClipRequest:
    """直播切片请求"""
    clip_id: str
    room_id: int
    trigger_type: ClipTriggerType
    trigger_time: float
    
    start_time: float
    end_time: float
    
    keyword: Optional[str] = None
    username: Optional[str] = None
    danmaku_content: Optional[str] = None
    
    status: ClipStatus = ClipStatus.PENDING
    output_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    
    duration_seconds: float = 0.0
    file_size: int = 0
    
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


@dataclass
class ClipReport:
    """切片报告"""
    report_id: str
    room_id: int
    room_title: str
    clip_count: int
    generated_at: float
    
    clips: List[Dict] = field(default_factory=list)
    total_duration: float = 0.0
    total_size: int = 0
    
    keyword_stats: Dict[str, int] = field(default_factory=dict)
    user_stats: Dict[str, int] = field(default_factory=dict)
    
    html_content: str = ""
    summary: str = ""


class LiveClipManager:
    """
    直播切片管理器
    连接弹幕监控、直播录制和自动切片系统
    """
    
    def __init__(self,
                 pre_buffer_seconds: float = 30.0,
                 post_buffer_seconds: float = 30.0,
                 max_concurrent_clips: int = 3,
                 enable_clip_notification: bool = True):
        """
        初始化切片管理器
        
        Args:
            pre_buffer_seconds: 前置缓冲秒数
            post_buffer_seconds: 后置缓冲秒数
            max_concurrent_clips: 最大并发切片数
            enable_clip_notification: 是否启用通知
        """
        self.pre_buffer = pre_buffer_seconds
        self.post_buffer = post_buffer_seconds
        self.max_concurrent = max_concurrent_clips
        self.enable_notification = enable_clip_notification
        
        self._clips: Dict[str, LiveClipRequest] = {}
        self._room_clips: Dict[int, List[LiveClipRequest]] = defaultdict(list)
        
        self._callbacks: Dict[str, List[Callable]] = {
            'clip_created': [],
            'clip_completed': [],
            'clip_failed': [],
            'report_generated': []
        }
        
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._is_running: bool = False
        self._worker_task: Optional[asyncio.Task] = None
        
        self._lock = threading.RLock()
        
        logging.info("=" * 60)
        logging.info("🎬 直播切片管理器初始化")
        logging.info(f"   - 前置缓冲: {pre_buffer_seconds}秒")
        logging.info(f"   - 后置缓冲: {post_buffer_seconds}秒")
        logging.info(f"   - 最大并发: {max_concurrent_clips}")
        logging.info("=" * 60)
    
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
    
    def create_clip_request(self,
                            room_id: int,
                            trigger_type: ClipTriggerType,
                            trigger_time: float,
                            keyword: str = None,
                            username: str = None,
                            danmaku_content: str = None,
                            metadata: Dict = None) -> LiveClipRequest:
        """
        创建切片请求
        
        Args:
            room_id: 直播间ID
            trigger_type: 触发类型
            trigger_time: 触发时间戳
            keyword: 触发关键词
            username: 触发用户
            danmaku_content: 弹幕内容
            metadata: 额外元数据
            
        Returns:
            LiveClipRequest 对象
        """
        import uuid
        
        clip_id = str(uuid.uuid4())[:12]
        
        start_time = trigger_time - self.pre_buffer
        end_time = trigger_time + self.post_buffer
        
        request = LiveClipRequest(
            clip_id=clip_id,
            room_id=room_id,
            trigger_type=trigger_type,
            trigger_time=trigger_time,
            start_time=start_time,
            end_time=end_time,
            keyword=keyword,
            username=username,
            danmaku_content=danmaku_content,
            status=ClipStatus.PENDING,
            duration_seconds=self.pre_buffer + self.post_buffer,
            metadata=metadata or {}
        )
        
        with self._lock:
            self._clips[clip_id] = request
            self._room_clips[room_id].append(request)
        
        logging.info(f"📋 切片请求已创建:")
        logging.info(f"   - 房间: {room_id}")
        logging.info(f"   - 类型: {trigger_type.value}")
        logging.info(f"   - 关键词: {keyword}")
        logging.info(f"   - 时间范围: {start_time:.1f} - {end_time:.1f}")
        
        asyncio.create_task(self._notify('clip_created', self._clip_to_dict(request)))
        
        return request
    
    def _clip_to_dict(self, clip: LiveClipRequest) -> Dict:
        """转换为字典"""
        return {
            'clip_id': clip.clip_id,
            'room_id': clip.room_id,
            'trigger_type': clip.trigger_type.value,
            'trigger_time': clip.trigger_time,
            'start_time': clip.start_time,
            'end_time': clip.end_time,
            'keyword': clip.keyword,
            'username': clip.username,
            'danmaku_content': clip.danmaku_content,
            'status': clip.status.value,
            'output_path': clip.output_path,
            'thumbnail_path': clip.thumbnail_path,
            'duration_seconds': clip.duration_seconds,
            'file_size': clip.file_size,
            'error_message': clip.error_message,
            'created_at': clip.created_at,
            'completed_at': clip.completed_at
        }
    
    async def process_clip(self, clip: LiveClipRequest, recorder=None) -> bool:
        """
        处理单个切片请求
        
        Args:
            clip: 切片请求
            recorder: 录制器实例（可选）
            
        Returns:
            是否成功
        """
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async with self._semaphore:
            try:
                clip.status = ClipStatus.EXTRACTING
                logging.info(f"🎬 开始处理切片: {clip.clip_id}")
                
                if recorder:
                    output_path = await recorder.extract_clip(
                        start_time=clip.start_time,
                        end_time=clip.end_time
                    )
                    
                    if output_path:
                        clip.output_path = output_path
                        clip.status = ClipStatus.COMPLETED
                        clip.completed_at = time.time()
                        
                        if os.path.exists(output_path):
                            clip.file_size = os.path.getsize(output_path)
                        
                        logging.info(f"✅ 切片完成: {output_path}")
                        
                        await self._generate_thumbnail(clip)
                        
                        await self._notify('clip_completed', self._clip_to_dict(clip))
                        return True
                    else:
                        clip.status = ClipStatus.FAILED
                        clip.error_message = "切片提取失败"
                        logging.error(f"❌ 切片失败: {clip.clip_id}")
                        await self._notify('clip_failed', self._clip_to_dict(clip))
                        return False
                else:
                    clip.status = ClipStatus.FAILED
                    clip.error_message = "没有可用的录制器"
                    logging.error(f"❌ 切片失败: 没有录制器实例")
                    await self._notify('clip_failed', self._clip_to_dict(clip))
                    return False
                    
            except Exception as e:
                clip.status = ClipStatus.FAILED
                clip.error_message = str(e)
                logging.error(f"❌ 处理切片异常: {e}")
                await self._notify('clip_failed', self._clip_to_dict(clip))
                return False
    
    async def _generate_thumbnail(self, clip: LiveClipRequest):
        """
        生成切片缩略图
        
        Args:
            clip: 切片请求
        """
        if not clip.output_path or not os.path.exists(clip.output_path):
            return
        
        import subprocess
        
        try:
            video_path = Path(clip.output_path)
            thumbnail_path = video_path.parent / f"{video_path.stem}_thumb.jpg"
            
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-ss', '3',
                '-vframes', '1',
                '-q:v', '2',
                '-y',
                str(thumbnail_path)
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            process.wait(timeout=30)
            
            if process.returncode == 0 and thumbnail_path.exists():
                clip.thumbnail_path = str(thumbnail_path)
                logging.info(f"🖼️ 缩略图已生成: {thumbnail_path}")
            else:
                logging.warning(f"缩略图生成失败: {process.returncode}")
                
        except Exception as e:
            logging.warning(f"生成缩略图异常: {e}")
    
    async def generate_report(self,
                               room_id: int,
                               clips: List[LiveClipRequest] = None,
                               room_title: str = "") -> Optional[ClipReport]:
        """
        生成切片报告
        
        Args:
            room_id: 直播间ID
            clips: 切片列表（可选，默认使用房间的所有切片）
            room_title: 房间标题
            
        Returns:
            ClipReport 对象或 None
        """
        import uuid
        
        if clips is None:
            with self._lock:
                clips = [c for c in self._room_clips.get(room_id, [])
                        if c.status == ClipStatus.COMPLETED]
        
        if not clips:
            logging.warning(f"房间 {room_id} 没有可报告的切片")
            return None
        
        report_id = str(uuid.uuid4())[:12]
        
        keyword_stats = defaultdict(int)
        user_stats = defaultdict(int)
        total_duration = 0.0
        total_size = 0
        
        clip_dicts = []
        for clip in clips:
            clip_dicts.append(self._clip_to_dict(clip))
            total_duration += clip.duration_seconds
            total_size += clip.file_size
            
            if clip.keyword:
                keyword_stats[clip.keyword] += 1
            if clip.username:
                user_stats[clip.username] += 1
        
        html_content = self._generate_html_report(
            room_id, room_title, clips, dict(keyword_stats), dict(user_stats)
        )
        
        summary = self._generate_summary(
            len(clips), total_duration, total_size, dict(keyword_stats)
        )
        
        report = ClipReport(
            report_id=report_id,
            room_id=room_id,
            room_title=room_title,
            clip_count=len(clips),
            generated_at=time.time(),
            clips=clip_dicts,
            total_duration=total_duration,
            total_size=total_size,
            keyword_stats=dict(keyword_stats),
            user_stats=dict(user_stats),
            html_content=html_content,
            summary=summary
        )
        
        logging.info(f"📊 切片报告已生成: 房间 {room_id}, {len(clips)} 个切片")
        
        await self._notify('report_generated', {
            'report_id': report_id,
            'room_id': room_id,
            'clip_count': len(clips),
            'summary': summary
        })
        
        return report
    
    def _generate_html_report(self,
                               room_id: int,
                               room_title: str,
                               clips: List[LiveClipRequest],
                               keyword_stats: Dict[str, int],
                               user_stats: Dict[str, int]) -> str:
        """
        生成HTML报告内容
        
        Args:
            room_id: 房间ID
            room_title: 房间标题
            clips: 切片列表
            keyword_stats: 关键词统计
            user_stats: 用户统计
            
        Returns:
            HTML字符串
        """
        total_duration = sum(c.duration_seconds for c in clips)
        total_size = sum(c.file_size for c in clips)
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>直播切片报告 - {room_title or f'房间 {room_id}'}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; }}
        .header h1 {{ font-size: 24px; margin-bottom: 10px; }}
        .header .meta {{ opacity: 0.9; font-size: 14px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }}
        .stat-card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .stat-card .value {{ font-size: 28px; font-weight: bold; color: #667eea; }}
        .stat-card .label {{ font-size: 14px; color: #666; margin-top: 5px; }}
        .section {{ background: white; padding: 25px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .section h2 {{ font-size: 18px; color: #333; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #eee; }}
        .keyword-list, .user-list {{ display: flex; flex-wrap: wrap; gap: 10px; }}
        .tag {{ background: #f0f2ff; color: #667eea; padding: 8px 16px; border-radius: 20px; font-size: 14px; }}
        .tag .count {{ font-weight: bold; margin-left: 5px; }}
        .clip-list {{ display: flex; flex-direction: column; gap: 15px; }}
        .clip-item {{ display: flex; gap: 15px; padding: 15px; background: #f9f9f9; border-radius: 8px; }}
        .clip-thumb {{ width: 160px; height: 90px; background: #ddd; border-radius: 6px; display: flex; align-items: center; justify-content: center; color: #999; flex-shrink: 0; }}
        .clip-info {{ flex: 1; }}
        .clip-info .title {{ font-weight: bold; color: #333; margin-bottom: 5px; }}
        .clip-info .meta {{ font-size: 13px; color: #666; }}
        .clip-info .meta span {{ margin-right: 15px; }}
        .footer {{ text-align: center; color: #999; font-size: 13px; padding: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎬 直播切片报告</h1>
            <div class="meta">
                房间: {room_title or f'房间 {room_id}'} | 
                生成时间: {datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')}
            </div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="value">{len(clips)}</div>
                <div class="label">切片数量</div>
            </div>
            <div class="stat-card">
                <div class="value">{self._format_duration(total_duration)}</div>
                <div class="label">总时长</div>
            </div>
            <div class="stat-card">
                <div class="value">{self._format_size(total_size)}</div>
                <div class="label">总大小</div>
            </div>
            <div class="stat-card">
                <div class="value">{len(keyword_stats)}</div>
                <div class="label">关键词类型</div>
            </div>
        </div>
"""
        
        if keyword_stats:
            html += f"""
        <div class="section">
            <h2>📊 关键词统计</h2>
            <div class="keyword-list">
"""
            for keyword, count in sorted(keyword_stats.items(), key=lambda x: -x[1]):
                html += f'                <div class="tag">{keyword}<span class="count">×{count}</span></div>\n'
            html += """            </div>
        </div>
"""
        
        if user_stats:
            html += f"""
        <div class="section">
            <h2>👥 用户统计</h2>
            <div class="user-list">
"""
            for user, count in sorted(user_stats.items(), key=lambda x: -x[1])[:10]:
                html += f'                <div class="tag">{user}<span class="count">×{count}</span></div>\n'
            html += """            </div>
        </div>
"""
        
        html += f"""
        <div class="section">
            <h2>🎥 切片列表</h2>
            <div class="clip-list">
"""
        
        for i, clip in enumerate(clips, 1):
            trigger_info = ""
            if clip.keyword:
                trigger_info = f"关键词: {clip.keyword}"
            elif clip.username:
                trigger_info = f"用户: {clip.username}"
            
            html += f"""
                <div class="clip-item">
                    <div class="clip-thumb">
                        {f'<img src="{clip.thumbnail_path}" style="width:100%;height:100%;object-fit:cover;border-radius:6px;">' if clip.thumbnail_path and os.path.exists(clip.thumbnail_path) else '🎬'}
                    </div>
                    <div class="clip-info">
                        <div class="title">切片 #{i} - {clip.trigger_type.value}</div>
                        <div class="meta">
                            <span>🕐 {self._format_duration(clip.duration_seconds)}</span>
                            <span>💾 {self._format_size(clip.file_size)}</span>
                            {f'<span>🏷️ {trigger_info}</span>' if trigger_info else ''}
                        </div>
                        <div class="meta" style="margin-top:5px;">
                            <span>📁 {clip.output_path or '未生成'}</span>
                        </div>
                    </div>
                </div>
"""
        
        html += """
            </div>
        </div>
        
        <div class="footer">
            由鸽切监控系统自动生成 | 报告 ID: {report_id}
        </div>
    </div>
</body>
</html>
"""
        
        return html
    
    def _generate_summary(self,
                          clip_count: int,
                          total_duration: float,
                          total_size: int,
                          keyword_stats: Dict[str, int]) -> str:
        """
        生成简短摘要
        
        Args:
            clip_count: 切片数量
            total_duration: 总时长
            total_size: 总大小
            keyword_stats: 关键词统计
            
        Returns:
            摘要字符串
        """
        parts = [f"共生成 {clip_count} 个切片"]
        parts.append(f"总时长 {self._format_duration(total_duration)}")
        parts.append(f"总大小 {self._format_size(total_size)}")
        
        if keyword_stats:
            top_keywords = sorted(keyword_stats.items(), key=lambda x: -x[1])[:3]
            keyword_str = ", ".join([f"{k}({v}次)" for k, v in top_keywords])
            parts.append(f"主要关键词: {keyword_str}")
        
        return " | ".join(parts)
    
    def _format_duration(self, seconds: float) -> str:
        """格式化时长"""
        if seconds < 60:
            return f"{int(seconds)}秒"
        elif seconds < 3600:
            return f"{int(seconds // 60)}分{int(seconds % 60)}秒"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            return f"{hours}时{mins}分{secs}秒"
    
    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f}KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / 1024 / 1024:.1f}MB"
        else:
            return f"{size / 1024 / 1024 / 1024:.1f}GB"
    
    def get_clip(self, clip_id: str) -> Optional[LiveClipRequest]:
        """获取切片请求"""
        with self._lock:
            return self._clips.get(clip_id)
    
    def get_room_clips(self, room_id: int, status: ClipStatus = None) -> List[LiveClipRequest]:
        """
        获取房间的切片列表
        
        Args:
            room_id: 房间ID
            status: 过滤状态（可选）
            
        Returns:
            切片列表
        """
        with self._lock:
            clips = self._room_clips.get(room_id, [])
            
            if status:
                clips = [c for c in clips if c.status == status]
            
            return clips.copy()
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            total_clips = len(self._clips)
            completed = sum(1 for c in self._clips.values() if c.status == ClipStatus.COMPLETED)
            failed = sum(1 for c in self._clips.values() if c.status == ClipStatus.FAILED)
            pending = sum(1 for c in self._clips.values() if c.status == ClipStatus.PENDING)
            
            active_rooms = len([rid for rid, clips in self._room_clips.items() if clips])
        
        return {
            'total_clips': total_clips,
            'completed': completed,
            'failed': failed,
            'pending': pending,
            'active_rooms': active_rooms,
            'config': {
                'pre_buffer_seconds': self.pre_buffer,
                'post_buffer_seconds': self.post_buffer,
                'max_concurrent_clips': self.max_concurrent
            }
        }


_clip_manager_instance: Optional[LiveClipManager] = None
_clip_manager_lock = threading.Lock()


def get_clip_manager(pre_buffer_seconds: float = 30.0,
                     post_buffer_seconds: float = 30.0,
                     max_concurrent_clips: int = 3) -> LiveClipManager:
    """
    获取全局切片管理器实例
    
    Args:
        pre_buffer_seconds: 前置缓冲
        post_buffer_seconds: 后置缓冲
        max_concurrent_clips: 最大并发
        
    Returns:
        LiveClipManager 实例
    """
    global _clip_manager_instance
    
    with _clip_manager_lock:
        if _clip_manager_instance is None:
            _clip_manager_instance = LiveClipManager(
                pre_buffer_seconds=pre_buffer_seconds,
                post_buffer_seconds=post_buffer_seconds,
                max_concurrent_clips=max_concurrent_clips
            )
        return _clip_manager_instance
