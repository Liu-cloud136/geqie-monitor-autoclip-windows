#!/usr/bin/env python3
"""
直播流录制器
- 实时接收 B站 直播流
- 基于 FFmpeg 的高性能录制
- 支持时间点回溯缓冲
- 支持实时切片
- 支持多房间同时录制
"""

import asyncio
import logging
import os
import time
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Deque
from collections import deque

try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False


class RecordingStatus(Enum):
    """录制状态"""
    IDLE = "idle"
    CONNECTING = "connecting"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class RecordingSegment:
    """录制片段信息"""
    segment_id: str
    start_time: float
    end_time: float
    file_path: str
    duration: float
    file_size: int = 0
    is_complete: bool = False


@dataclass
class TimeMarker:
    """时间标记点"""
    marker_id: str
    timestamp: float
    relative_time: float
    marker_type: str
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecordingStats:
    """录制统计信息"""
    status: RecordingStatus
    start_time: float
    elapsed_seconds: float
    file_size: int
    segment_count: int
    error_count: int
    last_heartbeat: float


class CircularTimeBuffer:
    """
    循环时间缓冲器
    用于保存最近一段时间的视频数据，支持回溯切片
    """
    
    def __init__(self, buffer_duration_seconds: int = 300, max_segments: int = 50):
        """
        初始化循环缓冲器
        
        Args:
            buffer_duration_seconds: 缓冲时长（秒）
            max_segments: 最大片段数
        """
        self.buffer_duration = buffer_duration_seconds
        self.max_segments = max_segments
        self._segments: Deque[RecordingSegment] = deque(maxlen=max_segments)
        self._lock = threading.RLock()
        
        logging.info(f"循环缓冲器初始化: 缓冲时长={buffer_duration_seconds}秒, 最大片段数={max_segments}")
    
    def add_segment(self, segment: RecordingSegment):
        """添加片段到缓冲器"""
        with self._lock:
            self._segments.append(segment)
            self._cleanup_old_segments()
    
    def _cleanup_old_segments(self):
        """清理过期片段"""
        if not self._segments:
            return
        
        current_time = time.time()
        cutoff_time = current_time - self.buffer_duration
        
        while self._segments:
            oldest = self._segments[0]
            if oldest.end_time and oldest.end_time < cutoff_time:
                if os.path.exists(oldest.file_path):
                    try:
                        os.remove(oldest.file_path)
                        logging.debug(f"已删除过期缓冲片段: {oldest.file_path}")
                    except Exception as e:
                        logging.warning(f"删除缓冲片段失败: {e}")
                self._segments.popleft()
            else:
                break
    
    def get_segments_for_time_range(self, start_time: float, end_time: float) -> List[RecordingSegment]:
        """
        获取指定时间范围内的所有片段
        
        Args:
            start_time: 开始时间戳
            end_time: 结束时间戳
            
        Returns:
            重叠的片段列表
        """
        with self._lock:
            result = []
            for segment in self._segments:
                seg_start = segment.start_time
                seg_end = segment.end_time or time.time()
                
                if not (seg_end < start_time or seg_start > end_time):
                    result.append(segment)
            
            return result
    
    def get_all_segments(self) -> List[RecordingSegment]:
        """获取所有缓冲片段"""
        with self._lock:
            return list(self._segments)
    
    def clear(self):
        """清空缓冲器"""
        with self._lock:
            for segment in self._segments:
                if os.path.exists(segment.file_path):
                    try:
                        os.remove(segment.file_path)
                    except Exception as e:
                        logging.warning(f"删除文件失败: {e}")
            self._segments.clear()


class BilibiliLiveRecorder:
    """
    B站直播录制器
    基于 FFmpeg 实现高性能录制
    """
    
    def __init__(self,
                 room_id: int,
                 output_dir: str = "live_recordings",
                 buffer_duration_seconds: int = 300,
                 segment_duration_seconds: int = 60,
                 quality: str = "原画",
                 credential: Dict = None,
                 headers: Dict = None):
        """
        初始化直播录制器
        
        Args:
            room_id: 直播间ID
            output_dir: 输出目录
            buffer_duration_seconds: 循环缓冲时长（秒）
            segment_duration_seconds: 单个片段时长（秒）
            quality: 画质
            credential: 登录凭证
            headers: 请求头
        """
        self.room_id = room_id
        self.output_dir = Path(output_dir)
        self.buffer_duration = buffer_duration_seconds
        self.segment_duration = segment_duration_seconds
        self.quality = quality
        self.credential = credential or {}
        self.headers = headers or {}
        
        self.room_output_dir = self.output_dir / f"room_{room_id}"
        self.buffer_dir = self.room_output_dir / "buffer"
        self.recordings_dir = self.room_output_dir / "recordings"
        self.clips_dir = self.room_output_dir / "clips"
        
        for d in [self.buffer_dir, self.recordings_dir, self.clips_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        self._status = RecordingStatus.IDLE
        self._process: Optional[subprocess.Popen] = None
        self._recording_start_time: float = 0
        self._last_heartbeat: float = 0
        self._error_count: int = 0
        self._total_file_size: int = 0
        
        self._segments: List[RecordingSegment] = []
        self._current_segment: Optional[RecordingSegment] = None
        
        self._time_markers: List[TimeMarker] = []
        
        self._callbacks: Dict[str, List[Callable]] = {
            'status_change': [],
            'segment_complete': [],
            'time_marker': [],
            'clip_complete': [],
            'error': []
        }
        
        self._monitor_task: Optional[asyncio.Task] = None
        self._is_running: bool = False
        
        self._buffer = CircularTimeBuffer(
            buffer_duration_seconds=buffer_duration_seconds,
            max_segments=buffer_duration_seconds // segment_duration_seconds + 10
        )
        
        self._lock = threading.RLock()
        
        logging.info(f"直播录制器初始化完成 - 房间: {room_id}, 画质: {quality}")
        logging.info(f"  - 输出目录: {self.room_output_dir.absolute()}")
        logging.info(f"  - 缓冲时长: {buffer_duration_seconds}秒")
        logging.info(f"  - 片段时长: {segment_duration_seconds}秒")
    
    def add_callback(self, event_type: str, callback: Callable):
        """添加事件回调"""
        if event_type in self._callbacks:
            self._callbacks[event_type].append(callback)
            logging.info(f"已添加回调: {event_type}")
    
    def remove_callback(self, event_type: str, callback: Callable):
        """移除事件回调"""
        if event_type in self._callbacks and callback in self._callbacks[event_type]:
            self._callbacks[event_type].remove(callback)
    
    async def _notify_callbacks(self, event_type: str, data: Any):
        """通知回调函数"""
        for callback in self._callbacks.get(event_type, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logging.error(f"回调执行失败 [{event_type}]: {e}")
    
    def _set_status(self, new_status: RecordingStatus):
        """设置状态并通知"""
        old_status = self._status
        if old_status != new_status:
            self._status = new_status
            logging.info(f"录制状态变更: {old_status.value} -> {new_status.value}")
            asyncio.create_task(self._notify_callbacks('status_change', {
                'room_id': self.room_id,
                'old_status': old_status.value,
                'new_status': new_status.value,
                'timestamp': time.time()
            }))
    
    def get_status(self) -> RecordingStatus:
        """获取当前状态"""
        return self._status
    
    def get_stats(self) -> RecordingStats:
        """获取录制统计"""
        elapsed = time.time() - self._recording_start_time if self._recording_start_time > 0 else 0
        
        return RecordingStats(
            status=self._status,
            start_time=self._recording_start_time,
            elapsed_seconds=elapsed,
            file_size=self._total_file_size,
            segment_count=len(self._segments),
            error_count=self._error_count,
            last_heartbeat=self._last_heartbeat
        )
    
    def add_time_marker(self, 
                        marker_type: str, 
                        description: str = "", 
                        metadata: Dict = None) -> TimeMarker:
        """
        添加时间标记点
        
        Args:
            marker_type: 标记类型 (如 'keyword', 'highlight', 'manual')
            description: 描述
            metadata: 额外元数据
            
        Returns:
            TimeMarker 对象
        """
        import uuid
        
        current_time = time.time()
        relative_time = current_time - self._recording_start_time if self._recording_start_time > 0 else 0
        
        marker = TimeMarker(
            marker_id=str(uuid.uuid4())[:12],
            timestamp=current_time,
            relative_time=relative_time,
            marker_type=marker_type,
            description=description,
            metadata=metadata or {}
        )
        
        with self._lock:
            self._time_markers.append(marker)
        
        logging.info(f"[房间 {self.room_id}] 添加时间标记: {marker_type} - {description} @ {relative_time:.1f}s")
        
        asyncio.create_task(self._notify_callbacks('time_marker', {
            'room_id': self.room_id,
            'marker': {
                'marker_id': marker.marker_id,
                'timestamp': marker.timestamp,
                'relative_time': marker.relative_time,
                'marker_type': marker.marker_type,
                'description': marker.description
            }
        }))
        
        return marker
    
    def get_time_markers(self, 
                          marker_type: str = None,
                          start_time: float = None,
                          end_time: float = None) -> List[TimeMarker]:
        """
        获取时间标记
        
        Args:
            marker_type: 过滤标记类型
            start_time: 开始时间戳
            end_time: 结束时间戳
            
        Returns:
            时间标记列表
        """
        with self._lock:
            markers = self._time_markers.copy()
        
        if marker_type:
            markers = [m for m in markers if m.marker_type == marker_type]
        
        if start_time is not None:
            markers = [m for m in markers if m.timestamp >= start_time]
        
        if end_time is not None:
            markers = [m for m in markers if m.timestamp <= end_time]
        
        return markers
    
    async def start(self) -> bool:
        """
        开始录制
        
        Returns:
            是否成功启动
        """
        if self._status == RecordingStatus.RECORDING:
            logging.warning("录制器已经在运行中")
            return True
        
        self._set_status(RecordingStatus.CONNECTING)
        
        try:
            from .live_stream_api import BilibiliLiveStreamAPI
            
            api = BilibiliLiveStreamAPI(
                headers=self.headers,
                credential=self.credential
            )
            
            stream_info = await api.get_live_stream_info(self.room_id, self.quality)
            
            if not stream_info:
                self._set_status(RecordingStatus.ERROR)
                self._error_count += 1
                logging.error(f"无法获取房间 {self.room_id} 的直播流信息")
                await api.close()
                return False
            
            if not stream_info.is_live:
                self._set_status(RecordingStatus.IDLE)
                logging.warning(f"房间 {self.room_id} 未开播")
                await api.close()
                return False
            
            best_url = stream_info.get_best_quality_url()
            if not best_url:
                self._set_status(RecordingStatus.ERROR)
                self._error_count += 1
                logging.error(f"无法获取房间 {self.room_id} 的直播流地址")
                await api.close()
                return False
            
            await api.close()
            
            success = await self._start_ffmpeg_recording(best_url.url)
            
            if success:
                self._recording_start_time = time.time()
                self._is_running = True
                self._set_status(RecordingStatus.RECORDING)
                
                self._monitor_task = asyncio.create_task(self._monitor_recording())
                
                logging.info(f"✅ 开始录制房间 {self.room_id}")
                return True
            else:
                self._set_status(RecordingStatus.ERROR)
                self._error_count += 1
                return False
                
        except Exception as e:
            self._set_status(RecordingStatus.ERROR)
            self._error_count += 1
            logging.error(f"启动录制失败: {e}")
            return False
    
    async def _start_ffmpeg_recording(self, stream_url: str) -> bool:
        """
        启动 FFmpeg 录制进程
        
        Args:
            stream_url: 直播流地址
            
        Returns:
            是否成功
        """
        import uuid
        
        segment_template = str(self.buffer_dir / f"segment_%03d_{int(time.time())}.ts")
        
        cmd = [
            'ffmpeg',
            '-i', stream_url,
            '-c:v', 'copy',
            '-c:a', 'copy',
            '-f', 'segment',
            '-segment_time', str(self.segment_duration),
            '-segment_format', 'mpegts',
            '-segment_list', str(self.buffer_dir / 'playlist.m3u8'),
            '-segment_list_flags', '+live',
            '-reset_timestamps', '1',
            '-y',
            segment_template
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': f'https://live.bilibili.com/{self.room_id}',
            'Origin': 'https://live.bilibili.com'
        }
        
        if self.credential.get('sessdata'):
            cookie = f"SESSDATA={self.credential.get('sessdata', '')}"
            if self.credential.get('bili_jct'):
                cookie += f"; bili_jct={self.credential.get('bili_jct', '')}"
            headers['Cookie'] = cookie
        
        headers_str = '\r\n'.join([f'{k}: {v}' for k, v in headers.items()]) + '\r\n'
        
        cmd = [
            'ffmpeg',
            '-headers', headers_str,
            '-i', stream_url,
            '-c:v', 'copy',
            '-c:a', 'copy',
            '-f', 'segment',
            '-segment_time', str(self.segment_duration),
            '-segment_format', 'mpegts',
            '-reset_timestamps', '1',
            '-y',
            segment_template
        ]
        
        logging.info(f"启动 FFmpeg 录制: {' '.join(cmd)[:200]}...")
        
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            self._last_heartbeat = time.time()
            
            return True
            
        except Exception as e:
            logging.error(f"启动 FFmpeg 失败: {e}")
            return False
    
    async def _monitor_recording(self):
        """监控录制进程"""
        while self._is_running and self._status == RecordingStatus.RECORDING:
            try:
                if self._process:
                    if self._process.poll() is not None:
                        logging.warning(f"FFmpeg 进程已退出，返回码: {self._process.returncode}")
                        
                        stderr_data = self._process.stderr.read() if self._process.stderr else b''
                        if stderr_data:
                            logging.error(f"FFmpeg 错误: {stderr_data.decode('utf-8', errors='ignore')[-500:]}")
                        
                        if self._is_running:
                            logging.info("尝试重新连接...")
                            await self._try_reconnect()
                        break
                    
                    else:
                        self._last_heartbeat = time.time()
                
                await self._check_new_segments()
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logging.error(f"录制监控异常: {e}")
                await asyncio.sleep(5)
    
    async def _check_new_segments(self):
        """检查新的录制片段"""
        segment_files = sorted(self.buffer_dir.glob("segment_*.ts"))
        
        for seg_file in segment_files:
            with self._lock:
                existing = [s for s in self._segments if s.file_path == str(seg_file)]
                if existing:
                    continue
            
            try:
                stat = seg_file.stat()
                file_size = stat.st_size
                
                segment = RecordingSegment(
                    segment_id=seg_file.stem,
                    start_time=stat.st_ctime,
                    end_time=stat.st_mtime,
                    file_path=str(seg_file),
                    duration=self.segment_duration,
                    file_size=file_size,
                    is_complete=True
                )
                
                with self._lock:
                    self._segments.append(segment)
                    self._total_file_size += file_size
                
                self._buffer.add_segment(segment)
                
                await self._notify_callbacks('segment_complete', {
                    'room_id': self.room_id,
                    'segment': {
                        'segment_id': segment.segment_id,
                        'start_time': segment.start_time,
                        'end_time': segment.end_time,
                        'file_path': segment.file_path,
                        'file_size': segment.file_size
                    }
                })
                
                logging.debug(f"新片段: {seg_file.name}, 大小: {file_size/1024/1024:.2f}MB")
                
            except Exception as e:
                logging.warning(f"处理片段失败 {seg_file}: {e}")
    
    async def _try_reconnect(self) -> bool:
        """尝试重新连接"""
        self._set_status(RecordingStatus.CONNECTING)
        
        max_attempts = 5
        for attempt in range(max_attempts):
            logging.info(f"重连尝试 {attempt + 1}/{max_attempts}")
            
            try:
                success = await self.start()
                if success:
                    logging.info("✅ 重新连接成功")
                    return True
            except Exception as e:
                logging.error(f"重连失败: {e}")
            
            await asyncio.sleep(5)
        
        self._set_status(RecordingStatus.ERROR)
        self._error_count += 1
        logging.error("❌ 重连失败次数过多，已停止")
        return False
    
    async def stop(self):
        """停止录制"""
        if self._status not in [RecordingStatus.RECORDING, RecordingStatus.PAUSED]:
            return
        
        logging.info(f"正在停止录制房间 {self.room_id}...")
        
        self._is_running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        if self._process:
            try:
                self._process.terminate()
                try:
                    await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, self._process.wait),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    self._process.kill()
                    logging.warning("FFmpeg 进程被强制终止")
            except Exception as e:
                logging.error(f"停止进程失败: {e}")
        
        self._set_status(RecordingStatus.STOPPED)
        logging.info(f"✅ 已停止录制房间 {self.room_id}")
    
    async def extract_clip(self,
                           start_time: float,
                           end_time: float,
                           output_path: str = None,
                           use_hardware_accel: bool = True) -> Optional[str]:
        """
        从录制内容中提取切片
        
        Args:
            start_time: 开始时间戳（绝对时间）
            end_time: 结束时间戳（绝对时间）
            output_path: 输出路径（可选）
            use_hardware_accel: 是否使用硬件加速
            
        Returns:
            输出文件路径 或 None
        """
        import uuid
        
        if self._status != RecordingStatus.RECORDING and self._status != RecordingStatus.STOPPED:
            logging.error("录制器未运行或已停止，无法提取切片")
            return None
        
        segments = self._buffer.get_segments_for_time_range(start_time, end_time)
        
        if not segments:
            logging.warning(f"没有找到时间范围内的片段: {start_time} - {end_time}")
            return None
        
        logging.info(f"找到 {len(segments)} 个片段用于切片")
        
        if output_path is None:
            safe_time = datetime.fromtimestamp(time.time()).strftime('%Y%m%d_%H%M%S')
            output_path = str(self.clips_dir / f"clip_{self.room_id}_{safe_time}_{uuid.uuid4().hex[:8]}.mp4")
        
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        concat_file = self.clips_dir / f"concat_{uuid.uuid4().hex[:8]}.txt"
        
        try:
            with open(concat_file, 'w', encoding='utf-8') as f:
                for seg in segments:
                    seg_path = Path(seg.file_path)
                    if seg_path.exists():
                        f.write(f"file '{seg_path.absolute()}'\n")
            
            video_encoder = 'h264_nvenc' if use_hardware_accel else 'libx264'
            
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c:v', video_encoder,
                '-c:a', 'aac',
                '-movflags', '+faststart',
                '-y',
                str(output)
            ]
            
            if not use_hardware_accel:
                cmd.insert(-3, '-preset')
                cmd.insert(-3, 'fast')
                cmd.insert(-3, '-crf')
                cmd.insert(-3, '23')
            
            logging.info(f"执行切片命令: {' '.join(cmd)[:200]}...")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            stdout, stderr = process.communicate(timeout=120)
            
            if process.returncode == 0 and output.exists():
                logging.info(f"✅ 切片成功: {output_path}")
                
                await self._notify_callbacks('clip_complete', {
                    'room_id': self.room_id,
                    'output_path': output_path,
                    'start_time': start_time,
                    'end_time': end_time,
                    'file_size': output.stat().st_size
                })
                
                return output_path
            else:
                logging.error(f"切片失败，返回码: {process.returncode}")
                if stderr:
                    logging.error(f"FFmpeg 错误: {stderr.decode('utf-8', errors='ignore')[-500:]}")
                return None
                
        except subprocess.TimeoutExpired:
            logging.error("切片过程超时")
            return None
        except Exception as e:
            logging.error(f"切片异常: {e}")
            return None
        finally:
            if concat_file.exists():
                concat_file.unlink()
    
    async def extract_clip_by_relative_time(self,
                                             start_seconds: float,
                                             end_seconds: float,
                                             output_path: str = None) -> Optional[str]:
        """
        根据相对时间提取切片（从录制开始计算）
        
        Args:
            start_seconds: 开始秒数
            end_seconds: 结束秒数
            output_path: 输出路径
            
        Returns:
            输出文件路径
        """
        if self._recording_start_time <= 0:
            logging.error("录制尚未开始")
            return None
        
        abs_start = self._recording_start_time + start_seconds
        abs_end = self._recording_start_time + end_seconds
        
        return await self.extract_clip(abs_start, abs_end, output_path)
    
    def get_current_relative_time(self) -> float:
        """获取当前相对录制开始的时间（秒）"""
        if self._recording_start_time <= 0:
            return 0
        return time.time() - self._recording_start_time


_recorder_instances: Dict[int, BilibiliLiveRecorder] = {}
_recorder_lock = threading.Lock()


def get_recorder(room_id: int,
                 output_dir: str = "live_recordings",
                 buffer_duration_seconds: int = 300,
                 segment_duration_seconds: int = 60,
                 quality: str = "原画",
                 credential: Dict = None,
                 headers: Dict = None) -> BilibiliLiveRecorder:
    """
    获取或创建房间录制器实例
    
    Args:
        room_id: 直播间ID
        output_dir: 输出目录
        buffer_duration_seconds: 缓冲时长
        segment_duration_seconds: 片段时长
        quality: 画质
        credential: 登录凭证
        headers: 请求头
        
    Returns:
        BilibiliLiveRecorder 实例
    """
    global _recorder_instances
    
    with _recorder_lock:
        if room_id not in _recorder_instances:
            _recorder_instances[room_id] = BilibiliLiveRecorder(
                room_id=room_id,
                output_dir=output_dir,
                buffer_duration_seconds=buffer_duration_seconds,
                segment_duration_seconds=segment_duration_seconds,
                quality=quality,
                credential=credential,
                headers=headers
            )
        return _recorder_instances[room_id]


def get_all_recorders() -> Dict[int, BilibiliLiveRecorder]:
    """获取所有录制器实例"""
    with _recorder_lock:
        return _recorder_instances.copy()


def remove_recorder(room_id: int) -> bool:
    """移除录制器实例"""
    global _recorder_instances
    
    with _recorder_lock:
        if room_id in _recorder_instances:
            del _recorder_instances[room_id]
            return True
        return False
