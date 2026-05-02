#!/usr/bin/env python3
"""
直播录制和切片 API 接口
- 提供直播录制控制 API
- 提供切片管理 API
- 提供状态查询 API
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from flask import Blueprint, jsonify, request, Response, send_file, send_from_directory

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

try:
    from live_integration import (
        LiveIntegrationManager, IntegrationStatus, RoomIntegrationState,
        get_integration_manager
    )
    LIVE_INTEGRATION_AVAILABLE = True
except ImportError:
    LIVE_INTEGRATION_AVAILABLE = False
    logging.warning("live_integration 模块不可用")


live_bp = Blueprint('live', __name__, url_prefix='/api/live')


def _get_integration_manager():
    """获取集成管理器实例"""
    if not LIVE_INTEGRATION_AVAILABLE:
        return None
    return get_integration_manager()


def _get_clip_manager():
    """获取切片管理器实例"""
    if not LIVE_CLIP_MANAGER_AVAILABLE:
        return None
    return get_clip_manager()


def _format_timestamp(ts: float) -> str:
    """格式化时间戳"""
    if ts <= 0:
        return ""
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')


def _format_duration(seconds: float) -> str:
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


def _format_size(size: int) -> str:
    """格式化文件大小"""
    if size < 1024:
        return f"{size}B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / 1024 / 1024:.1f}MB"
    else:
        return f"{size / 1024 / 1024 / 1024:.1f}GB"


@live_bp.route('/status', methods=['GET'])
def get_system_status():
    """
    获取直播系统整体状态
    
    Returns:
        JSON 包含系统状态信息
    """
    status = {
        'success': True,
        'timestamp': time.time(),
        'modules': {
            'live_stream_api': LIVE_STREAM_API_AVAILABLE,
            'live_recorder': LIVE_RECORDER_AVAILABLE,
            'live_clip_manager': LIVE_CLIP_MANAGER_AVAILABLE,
            'live_integration': LIVE_INTEGRATION_AVAILABLE
        }
    }
    
    if LIVE_INTEGRATION_AVAILABLE:
        manager = _get_integration_manager()
        if manager:
            stats = manager.get_stats()
            status['integration'] = stats
    
    if LIVE_CLIP_MANAGER_AVAILABLE:
        clip_manager = _get_clip_manager()
        if clip_manager:
            status['clip_manager'] = clip_manager.get_stats()
    
    return jsonify(status)


@live_bp.route('/rooms', methods=['GET'])
def get_all_rooms():
    """
    获取所有已添加的房间列表
    
    Returns:
        JSON 包含房间列表
    """
    if not LIVE_INTEGRATION_AVAILABLE:
        return jsonify({
            'success': False,
            'error': '集成管理器不可用'
        }), 500
    
    manager = _get_integration_manager()
    rooms = manager.get_all_rooms()
    
    result = []
    for room in rooms:
        recorder_status = 'idle'
        recorder = None
        if LIVE_RECORDER_AVAILABLE:
            recorders = get_all_recorders()
            if room['room_id'] in recorders:
                recorder = recorders[room['room_id']]
                stats = recorder.get_stats()
                recorder_status = stats.status.value if hasattr(stats.status, 'value') else str(stats.status)
        
        result.append({
            'room_id': room['room_id'],
            'nickname': room['nickname'],
            'monitor_enabled': room['monitor_enabled'],
            'recorder_enabled': room['recorder_enabled'],
            'auto_clip_enabled': room['auto_clip_enabled'],
            'recorder_status': recorder_status,
            'keyword_count': room.get('keyword_count', 0),
            'clip_count': room.get('clip_count', 0),
            'recording_elapsed_seconds': room.get('recording_elapsed_seconds', 0),
            'recording_elapsed_display': _format_duration(room.get('recording_elapsed_seconds', 0))
        })
    
    return jsonify({
        'success': True,
        'rooms': result,
        'count': len(result)
    })


@live_bp.route('/room/<int:room_id>', methods=['GET'])
def get_room_info(room_id: int):
    """
    获取指定房间的详细信息
    
    Args:
        room_id: 直播间ID
    
    Returns:
        JSON 包含房间详细信息
    """
    if not LIVE_INTEGRATION_AVAILABLE:
        return jsonify({
            'success': False,
            'error': '集成管理器不可用'
        }), 500
    
    manager = _get_integration_manager()
    state = manager.get_room_state(room_id)
    
    if not state:
        return jsonify({
            'success': False,
            'error': f'房间 {room_id} 未注册'
        }), 404
    
    recorder_info = {}
    if LIVE_RECORDER_AVAILABLE:
        recorders = get_all_recorders()
        if room_id in recorders:
            recorder = recorders[room_id]
            stats = recorder.get_stats()
            recorder_info = {
                'status': stats.status.value if hasattr(stats.status, 'value') else str(stats.status),
                'start_time': stats.start_time,
                'start_time_display': _format_timestamp(stats.start_time),
                'elapsed_seconds': stats.elapsed_seconds,
                'elapsed_display': _format_duration(stats.elapsed_seconds),
                'file_size': stats.file_size,
                'file_size_display': _format_size(stats.file_size),
                'segment_count': stats.segment_count,
                'error_count': stats.error_count
            }
            
            markers = recorder.get_time_markers(marker_type='keyword')
            recorder_info['time_markers'] = [{
                'marker_id': m.marker_id,
                'timestamp': m.timestamp,
                'relative_time': m.relative_time,
                'marker_type': m.marker_type,
                'description': m.description
            } for m in markers]
    
    clips_info = {}
    if LIVE_CLIP_MANAGER_AVAILABLE:
        clip_manager = _get_clip_manager()
        if clip_manager:
            clips = clip_manager.get_room_clips(room_id)
            clips_info = {
                'total': len(clips),
                'clips': [{
                    'clip_id': c.clip_id,
                    'trigger_type': c.trigger_type.value,
                    'trigger_time': c.trigger_time,
                    'status': c.status.value,
                    'keyword': c.keyword,
                    'username': c.username,
                    'output_path': c.output_path,
                    'duration_seconds': c.duration_seconds,
                    'file_size': c.file_size,
                    'created_at': c.created_at,
                    'completed_at': c.completed_at
                } for c in clips[-20:]]
            }
    
    return jsonify({
        'success': True,
        'room': {
            'room_id': room_id,
            'nickname': state.nickname,
            'monitor_enabled': state.monitor_enabled,
            'recorder_enabled': state.recorder_enabled,
            'auto_clip_enabled': state.auto_clip_enabled,
            'monitor_status': state.monitor_status,
            'recorder_status': state.recorder_status,
            'last_keyword_time': state.last_keyword_time,
            'last_clip_time': state.last_clip_time,
            'keyword_count': state.keyword_count,
            'clip_count': state.clip_count,
            'recording_start_time': state.recording_start_time,
            'recording_elapsed_seconds': state.recording_elapsed_seconds
        },
        'recorder': recorder_info,
        'clips': clips_info
    })


@live_bp.route('/room/<int:room_id>/add', methods=['POST'])
def add_room(room_id: int):
    """
    添加房间进行监控和录制
    
    Args:
        room_id: 直播间ID
    
    Request Body (JSON):
        nickname: 房间昵称（可选）
        enable_monitor: 是否启用弹幕监控（默认 true）
        enable_recorder: 是否启用直播录制（默认 true）
        enable_auto_clip: 是否启用自动切片（默认 true）
    
    Returns:
        JSON 操作结果
    """
    if not LIVE_INTEGRATION_AVAILABLE:
        return jsonify({
            'success': False,
            'error': '集成管理器不可用'
        }), 500
    
    data = request.get_json() or {}
    nickname = data.get('nickname', '')
    enable_monitor = data.get('enable_monitor', True)
    enable_recorder = data.get('enable_recorder', True)
    enable_auto_clip = data.get('enable_auto_clip', True)
    
    manager = _get_integration_manager()
    state = manager.add_room(
        room_id=room_id,
        nickname=nickname,
        enable_monitor=enable_monitor,
        enable_recorder=enable_recorder,
        enable_auto_clip=enable_auto_clip
    )
    
    return jsonify({
        'success': True,
        'room_id': room_id,
        'nickname': state.nickname,
        'monitor_enabled': state.monitor_enabled,
        'recorder_enabled': state.recorder_enabled,
        'auto_clip_enabled': state.auto_clip_enabled
    })


@live_bp.route('/room/<int:room_id>/remove', methods=['POST'])
def remove_room(room_id: int):
    """
    移除房间
    
    Args:
        room_id: 直播间ID
    
    Returns:
        JSON 操作结果
    """
    if not LIVE_INTEGRATION_AVAILABLE:
        return jsonify({
            'success': False,
            'error': '集成管理器不可用'
        }), 500
    
    manager = _get_integration_manager()
    success = manager.remove_room(room_id)
    
    if LIVE_RECORDER_AVAILABLE:
        remove_recorder(room_id)
    
    if success:
        return jsonify({
            'success': True,
            'message': f'房间 {room_id} 已移除'
        })
    else:
        return jsonify({
            'success': False,
            'error': f'房间 {room_id} 不存在'
        }), 404


@live_bp.route('/room/<int:room_id>/record/start', methods=['POST'])
def start_recording(room_id: int):
    """
    启动房间录制
    
    Args:
        room_id: 直播间ID
    
    Request Body (JSON):
        quality: 画质（可选，默认 "原画"）
        buffer_duration_seconds: 缓冲时长（可选，默认 300）
        segment_duration_seconds: 片段时长（可选，默认 60）
    
    Returns:
        JSON 操作结果
    """
    if not LIVE_INTEGRATION_AVAILABLE:
        return jsonify({
            'success': False,
            'error': '集成管理器不可用'
        }), 500
    
    if not LIVE_RECORDER_AVAILABLE:
        return jsonify({
            'success': False,
            'error': '直播录制模块不可用'
        }), 500
    
    data = request.get_json() or {}
    quality = data.get('quality', '原画')
    buffer_duration = data.get('buffer_duration_seconds', 300)
    segment_duration = data.get('segment_duration_seconds', 60)
    
    manager = _get_integration_manager()
    
    state = manager.get_room_state(room_id)
    if not state:
        manager.add_room(room_id)
    
    async def _start():
        try:
            recorder = get_recorder(
                room_id=room_id,
                output_dir="live_recordings",
                buffer_duration_seconds=buffer_duration,
                segment_duration_seconds=segment_duration,
                quality=quality
            )
            
            success = await recorder.start()
            return success
        except Exception as e:
            logging.error(f"启动录制失败: {e}")
            return False
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    success = loop.run_until_complete(_start())
    loop.close()
    
    if success:
        return jsonify({
            'success': True,
            'message': f'房间 {room_id} 录制已启动',
            'quality': quality
        })
    else:
        return jsonify({
            'success': False,
            'error': f'房间 {room_id} 录制启动失败，可能未开播或无法获取直播流'
        }), 400


@live_bp.route('/room/<int:room_id>/record/stop', methods=['POST'])
def stop_recording(room_id: int):
    """
    停止房间录制
    
    Args:
        room_id: 直播间ID
    
    Returns:
        JSON 操作结果
    """
    if not LIVE_RECORDER_AVAILABLE:
        return jsonify({
            'success': False,
            'error': '直播录制模块不可用'
        }), 500
    
    recorders = get_all_recorders()
    if room_id not in recorders:
        return jsonify({
            'success': True,
            'message': f'房间 {room_id} 没有正在进行的录制'
        })
    
    recorder = recorders[room_id]
    
    async def _stop():
        try:
            await recorder.stop()
            return True
        except Exception as e:
            logging.error(f"停止录制失败: {e}")
            return False
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    success = loop.run_until_complete(_stop())
    loop.close()
    
    return jsonify({
        'success': True,
        'message': f'房间 {room_id} 录制已停止'
    })


@live_bp.route('/room/<int:room_id>/record/status', methods=['GET'])
def get_recording_status(room_id: int):
    """
    获取录制状态
    
    Args:
        room_id: 直播间ID
    
    Returns:
        JSON 包含录制状态信息
    """
    if not LIVE_RECORDER_AVAILABLE:
        return jsonify({
            'success': False,
            'error': '直播录制模块不可用'
        }), 500
    
    recorders = get_all_recorders()
    if room_id not in recorders:
        return jsonify({
            'success': True,
            'status': 'idle',
            'message': '没有正在进行的录制'
        })
    
    recorder = recorders[room_id]
    stats = recorder.get_stats()
    
    return jsonify({
        'success': True,
        'status': stats.status.value if hasattr(stats.status, 'value') else str(stats.status),
        'start_time': stats.start_time,
        'start_time_display': _format_timestamp(stats.start_time),
        'elapsed_seconds': stats.elapsed_seconds,
        'elapsed_display': _format_duration(stats.elapsed_seconds),
        'file_size': stats.file_size,
        'file_size_display': _format_size(stats.file_size),
        'segment_count': stats.segment_count,
        'error_count': stats.error_count
    })


@live_bp.route('/room/<int:room_id>/clip', methods=['POST'])
def create_manual_clip(room_id: int):
    """
    创建手动切片请求
    
    Args:
        room_id: 直播间ID
    
    Request Body (JSON):
        pre_buffer: 前置缓冲秒数（可选，默认 30）
        post_buffer: 后置缓冲秒数（可选，默认 30）
        description: 描述（可选）
    
    Returns:
        JSON 操作结果
    """
    if not LIVE_RECORDER_AVAILABLE:
        return jsonify({
            'success': False,
            'error': '直播录制模块不可用'
        }), 500
    
    if not LIVE_CLIP_MANAGER_AVAILABLE:
        return jsonify({
            'success': False,
            'error': '切片管理器不可用'
        }), 500
    
    recorders = get_all_recorders()
    if room_id not in recorders:
        return jsonify({
            'success': False,
            'error': f'房间 {room_id} 没有正在进行的录制'
        }), 400
    
    recorder = recorders[room_id]
    
    if recorder.get_status() not in [RecordingStatus.RECORDING, RecordingStatus.PAUSED, RecordingStatus.STOPPED]:
        return jsonify({
            'success': False,
            'error': f'房间 {room_id} 录制器状态无效'
        }), 400
    
    data = request.get_json() or {}
    pre_buffer = data.get('pre_buffer', 30)
    post_buffer = data.get('post_buffer', 30)
    description = data.get('description', '手动切片')
    
    current_time = time.time()
    
    async def _process():
        try:
            clip_manager = get_clip_manager(
                pre_buffer_seconds=pre_buffer,
                post_buffer_seconds=post_buffer
            )
            
            clip_request = clip_manager.create_clip_request(
                room_id=room_id,
                trigger_type=ClipTriggerType.MANUAL,
                trigger_time=current_time,
                metadata={'description': description}
            )
            
            success = await clip_manager.process_clip(clip_request, recorder)
            
            return {
                'success': success,
                'clip_id': clip_request.clip_id,
                'output_path': clip_request.output_path,
                'file_size': clip_request.file_size,
                'duration': clip_request.duration_seconds
            }
        except Exception as e:
            logging.error(f"手动切片失败: {e}")
            return {'success': False, 'error': str(e)}
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(_process())
    loop.close()
    
    if result.get('success'):
        return jsonify({
            'success': True,
            'clip_id': result['clip_id'],
            'output_path': result['output_path'],
            'file_size': result['file_size'],
            'file_size_display': _format_size(result['file_size']),
            'duration': result['duration'],
            'duration_display': _format_duration(result['duration'])
        })
    else:
        return jsonify({
            'success': False,
            'error': result.get('error', '切片失败')
        }), 500


@live_bp.route('/room/<int:room_id>/clips', methods=['GET'])
def get_room_clips(room_id: int):
    """
    获取房间的切片列表
    
    Args:
        room_id: 直播间ID
    
    Query Parameters:
        status: 按状态过滤（可选）
        limit: 返回数量限制（默认 50）
    
    Returns:
        JSON 包含切片列表
    """
    if not LIVE_CLIP_MANAGER_AVAILABLE:
        return jsonify({
            'success': False,
            'error': '切片管理器不可用'
        }), 500
    
    clip_manager = _get_clip_manager()
    if not clip_manager:
        return jsonify({
            'success': False,
            'error': '切片管理器未初始化'
        }), 500
    
    status_filter = request.args.get('status')
    limit = request.args.get('limit', 50, type=int)
    
    status_enum = None
    if status_filter:
        try:
            status_enum = ClipStatus(status_filter.lower())
        except ValueError:
            pass
    
    clips = clip_manager.get_room_clips(room_id, status_enum)
    clips = clips[-limit:]
    
    result = []
    for clip in reversed(clips):
        result.append({
            'clip_id': clip.clip_id,
            'trigger_type': clip.trigger_type.value,
            'trigger_time': clip.trigger_time,
            'trigger_time_display': _format_timestamp(clip.trigger_time),
            'keyword': clip.keyword,
            'username': clip.username,
            'danmaku_content': clip.danmaku_content,
            'status': clip.status.value,
            'output_path': clip.output_path,
            'thumbnail_path': clip.thumbnail_path,
            'duration_seconds': clip.duration_seconds,
            'duration_display': _format_duration(clip.duration_seconds),
            'file_size': clip.file_size,
            'file_size_display': _format_size(clip.file_size),
            'error_message': clip.error_message,
            'created_at': clip.created_at,
            'completed_at': clip.completed_at
        })
    
    return jsonify({
        'success': True,
        'room_id': room_id,
        'clips': result,
        'count': len(result)
    })


@live_bp.route('/clip/<clip_id>', methods=['GET'])
def get_clip_detail(clip_id: str):
    """
    获取切片详细信息
    
    Args:
        clip_id: 切片ID
    
    Returns:
        JSON 包含切片详细信息
    """
    if not LIVE_CLIP_MANAGER_AVAILABLE:
        return jsonify({
            'success': False,
            'error': '切片管理器不可用'
        }), 500
    
    clip_manager = _get_clip_manager()
    if not clip_manager:
        return jsonify({
            'success': False,
            'error': '切片管理器未初始化'
        }), 500
    
    clip = clip_manager.get_clip(clip_id)
    if not clip:
        return jsonify({
            'success': False,
            'error': f'切片 {clip_id} 不存在'
        }), 404
    
    return jsonify({
        'success': True,
        'clip': {
            'clip_id': clip.clip_id,
            'room_id': clip.room_id,
            'trigger_type': clip.trigger_type.value,
            'trigger_time': clip.trigger_time,
            'trigger_time_display': _format_timestamp(clip.trigger_time),
            'start_time': clip.start_time,
            'end_time': clip.end_time,
            'keyword': clip.keyword,
            'username': clip.username,
            'danmaku_content': clip.danmaku_content,
            'status': clip.status.value,
            'output_path': clip.output_path,
            'thumbnail_path': clip.thumbnail_path,
            'duration_seconds': clip.duration_seconds,
            'duration_display': _format_duration(clip.duration_seconds),
            'file_size': clip.file_size,
            'file_size_display': _format_size(clip.file_size),
            'error_message': clip.error_message,
            'created_at': clip.created_at,
            'completed_at': clip.completed_at
        }
    })


@live_bp.route('/room/<int:room_id>/report', methods=['POST'])
def generate_room_report(room_id: int):
    """
    生成房间切片报告
    
    Args:
        room_id: 直播间ID
    
    Request Body (JSON):
        room_title: 房间标题（可选）
    
    Returns:
        JSON 包含报告信息
    """
    if not LIVE_CLIP_MANAGER_AVAILABLE:
        return jsonify({
            'success': False,
            'error': '切片管理器不可用'
        }), 500
    
    data = request.get_json() or {}
    room_title = data.get('room_title', '')
    
    clip_manager = _get_clip_manager()
    if not clip_manager:
        return jsonify({
            'success': False,
            'error': '切片管理器未初始化'
        }), 500
    
    async def _generate():
        try:
            report = await clip_manager.generate_report(
                room_id=room_id,
                room_title=room_title
            )
            return report
        except Exception as e:
            logging.error(f"生成报告失败: {e}")
            return None
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    report = loop.run_until_complete(_generate())
    loop.close()
    
    if not report:
        return jsonify({
            'success': False,
            'error': '无法生成报告，可能没有切片数据'
        }), 400
    
    return jsonify({
        'success': True,
        'report': {
            'report_id': report.report_id,
            'room_id': report.room_id,
            'room_title': report.room_title,
            'clip_count': report.clip_count,
            'generated_at': report.generated_at,
            'generated_at_display': _format_timestamp(report.generated_at),
            'total_duration': report.total_duration,
            'total_duration_display': _format_duration(report.total_duration),
            'total_size': report.total_size,
            'total_size_display': _format_size(report.total_size),
            'keyword_stats': report.keyword_stats,
            'user_stats': report.user_stats,
            'summary': report.summary
        }
    })


@live_bp.route('/clips/stats', methods=['GET'])
def get_clips_stats():
    """
    获取全局切片统计
    
    Returns:
        JSON 包含统计信息
    """
    if not LIVE_CLIP_MANAGER_AVAILABLE:
        return jsonify({
            'success': False,
            'error': '切片管理器不可用'
        }), 500
    
    clip_manager = _get_clip_manager()
    if not clip_manager:
        return jsonify({
            'success': False,
            'error': '切片管理器未初始化'
        }), 500
    
    stats = clip_manager.get_stats()
    
    return jsonify({
        'success': True,
        'stats': stats
    })


@live_bp.route('/stream/<int:room_id>/info', methods=['GET'])
def get_stream_info(room_id: int):
    """
    获取直播流信息
    
    Args:
        room_id: 直播间ID
    
    Returns:
        JSON 包含直播流信息
    """
    if not LIVE_STREAM_API_AVAILABLE:
        return jsonify({
            'success': False,
            'error': '直播流API模块不可用'
        }), 500
    
    preferred_quality = request.args.get('quality', '原画')
    
    async def _get_info():
        try:
            api = BilibiliLiveStreamAPI()
            stream_info = await api.get_live_stream_info(room_id, preferred_quality)
            await api.close()
            return stream_info
        except Exception as e:
            logging.error(f"获取直播流信息失败: {e}")
            return None
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    stream_info = loop.run_until_complete(_get_info())
    loop.close()
    
    if not stream_info:
        return jsonify({
            'success': False,
            'error': f'无法获取房间 {room_id} 的直播流信息'
        }), 400
    
    result = {
        'room_id': stream_info.room_id,
        'is_live': stream_info.is_live,
        'title': stream_info.title,
        'liver_name': stream_info.liver_name,
        'area_name': stream_info.area_name,
        'cover_url': stream_info.cover_url,
        'timestamp': stream_info.timestamp
    }
    
    if stream_info.is_live and stream_info.stream_urls:
        best_url = stream_info.get_best_quality_url()
        result['stream_urls'] = [{
            'url': url.url,
            'quality': url.quality,
            'codec': url.codec,
            'format': url.format,
            'priority': url.priority
        } for url in stream_info.stream_urls]
        
        if best_url:
            result['best_quality_url'] = {
                'url': best_url.url,
                'quality': best_url.quality,
                'codec': best_url.codec,
                'format': best_url.format
            }
    
    return jsonify({
        'success': True,
        'stream_info': result
    })


@live_bp.route('/health', methods=['GET'])
def health_check():
    """
    健康检查接口
    
    Returns:
        JSON 健康状态
    """
    return jsonify({
        'success': True,
        'status': 'healthy',
        'timestamp': time.time(),
        'modules': {
            'live_stream_api': LIVE_STREAM_API_AVAILABLE,
            'live_recorder': LIVE_RECORDER_AVAILABLE,
            'live_clip_manager': LIVE_CLIP_MANAGER_AVAILABLE,
            'live_integration': LIVE_INTEGRATION_AVAILABLE
        }
    })
