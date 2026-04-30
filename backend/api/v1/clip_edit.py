"""
切片编辑API路由
提供切片编辑会话管理、片段操作、视频合并等HTTP接口
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_
from core.database import get_db
from services.clip_edit_service import ClipEditService
from services.unified_websocket_service import get_ws_service
from models.clip_edit import EditSessionStatus, EditSegmentType
from schemas.clip_edit import (
    EditSessionCreate,
    EditSessionUpdate,
    EditSessionResponse,
    EditSessionListResponse,
    EditSegmentCreate,
    EditSegmentUpdate,
    EditSegmentResponse,
    ReorderSegmentsRequest,
    AddClipsToSessionRequest,
    AddClipsToSessionResponse,
    GetSessionResponse,
    GetOrCreateDefaultSessionResponse,
    CropSegmentRequest,
    SplitSegmentRequest,
    MergeSegmentsRequest,
    GenerateVideoResponse,
)
from schemas.base import PaginationParams, PaginationResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_NAME_LENGTH = 200
DEFAULT_PAGE_SIZE = 20
MIN_PAGE_SIZE = 1
MAX_PAGE_SIZE = 100


def get_edit_service(db: Session = Depends(get_db)) -> ClipEditService:
    """
    获取编辑服务实例
    
    Args:
        db: 数据库会话
        
    Returns:
        编辑服务实例
    """
    return ClipEditService(db)


# Edit Session Endpoints

@router.post("/sessions/", response_model=EditSessionResponse)
async def create_edit_session(
    session_data: EditSessionCreate,
    edit_service: ClipEditService = Depends(get_edit_service)
):
    """
    创建新的编辑会话
    
    Args:
        session_data: 会话创建数据
        edit_service: 编辑服务实例
        
    Returns:
        创建的编辑会话信息
        
    Raises:
        HTTPException: 创建失败时返回400错误
    """
    try:
        if len(session_data.name) > MAX_NAME_LENGTH:
            raise HTTPException(
                status_code=400, 
                detail=f"名称长度不能超过{MAX_NAME_LENGTH}个字符"
            )
        
        session = edit_service.create_session(session_data)
        return edit_service.convert_to_response(session)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建编辑会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建编辑会话失败: {str(e)}")


@router.get("/sessions/{session_id}", response_model=GetSessionResponse)
async def get_edit_session(
    session_id: str,
    edit_service: ClipEditService = Depends(get_edit_service)
):
    """
    获取编辑会话详情
    
    Args:
        session_id: 会话ID
        edit_service: 编辑服务实例
        
    Returns:
        编辑会话信息
        
    Raises:
        HTTPException: 会话不存在时返回404错误
    """
    try:
        session = edit_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="编辑会话不存在")
        
        session_response = edit_service.convert_to_response(session)
        
        return GetSessionResponse(
            success=True,
            session=session_response,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取编辑会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取编辑会话失败: {str(e)}")


@router.get("/projects/{project_id}/sessions/", response_model=EditSessionListResponse)
async def get_project_sessions(
    project_id: str,
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(DEFAULT_PAGE_SIZE, ge=MIN_PAGE_SIZE, le=MAX_PAGE_SIZE, description="每页数量"),
    edit_service: ClipEditService = Depends(get_edit_service)
):
    """
    获取项目的所有编辑会话
    
    Args:
        project_id: 项目ID
        page: 页码
        size: 每页数量
        edit_service: 编辑服务实例
        
    Returns:
        分页的编辑会话列表
    """
    try:
        sessions = edit_service.get_sessions_by_project(project_id)
        
        skip = (page - 1) * size
        limit = size
        paginated_sessions = sessions[skip:skip + limit]
        
        total = len(sessions)
        pages = (total + size - 1) // size
        has_next = page < pages
        has_prev = page > 1
        
        session_responses = [edit_service.convert_to_response(s) for s in paginated_sessions]
        
        pagination = PaginationResponse(
            page=page,
            size=size,
            total=total,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )
        
        return EditSessionListResponse(
            items=session_responses,
            pagination=pagination
        )
        
    except Exception as e:
        logger.error(f"获取项目编辑会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取项目编辑会话失败: {str(e)}")


@router.post("/projects/{project_id}/default-session/", response_model=GetOrCreateDefaultSessionResponse)
async def get_or_create_default_session(
    project_id: str,
    edit_service: ClipEditService = Depends(get_edit_service)
):
    """
    获取或创建项目的默认编辑会话
    
    Args:
        project_id: 项目ID
        edit_service: 编辑服务实例
        
    Returns:
        默认编辑会话信息
    """
    try:
        session, is_new = edit_service.create_or_get_default_session(project_id)
        session_response = edit_service.convert_to_response(session)
        
        return GetOrCreateDefaultSessionResponse(
            success=True,
            session=session_response,
            is_new=is_new,
        )
        
    except Exception as e:
        logger.error(f"获取或创建默认会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取或创建默认会话失败: {str(e)}")


@router.put("/sessions/{session_id}", response_model=EditSessionResponse)
async def update_edit_session(
    session_id: str,
    session_data: EditSessionUpdate,
    edit_service: ClipEditService = Depends(get_edit_service)
):
    """
    更新编辑会话
    
    Args:
        session_id: 会话ID
        session_data: 更新数据
        edit_service: 编辑服务实例
        
    Returns:
        更新后的会话信息
        
    Raises:
        HTTPException: 会话不存在时返回404错误
    """
    try:
        if session_data.name and len(session_data.name) > MAX_NAME_LENGTH:
            raise HTTPException(
                status_code=400, 
                detail=f"名称长度不能超过{MAX_NAME_LENGTH}个字符"
            )
        
        session = edit_service.update_session(session_id, session_data)
        if not session:
            raise HTTPException(status_code=404, detail="编辑会话不存在")
        
        return edit_service.convert_to_response(session)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新编辑会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新编辑会话失败: {str(e)}")


@router.delete("/sessions/{session_id}")
async def delete_edit_session(
    session_id: str,
    edit_service: ClipEditService = Depends(get_edit_service)
):
    """
    删除编辑会话
    
    Args:
        session_id: 会话ID
        edit_service: 编辑服务实例
        
    Returns:
        删除成功消息
        
    Raises:
        HTTPException: 会话不存在时返回404错误
    """
    try:
        success = edit_service.delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="编辑会话不存在")
        
        return {"message": "编辑会话删除成功", "session_id": session_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除编辑会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除编辑会话失败: {str(e)}")


# Segment Endpoints

@router.post("/sessions/{session_id}/segments/", response_model=EditSegmentResponse)
async def add_segment(
    session_id: str,
    segment_data: EditSegmentCreate,
    edit_service: ClipEditService = Depends(get_edit_service)
):
    """
    添加片段到编辑会话
    
    Args:
        session_id: 会话ID
        segment_data: 片段创建数据
        edit_service: 编辑服务实例
        
    Returns:
        创建的片段信息
        
    Raises:
        HTTPException: 会话不存在时返回404错误
    """
    try:
        segment = edit_service.add_segment(session_id, segment_data)
        if not segment:
            raise HTTPException(status_code=404, detail="编辑会话不存在")
        
        return EditSegmentResponse(
            id=segment.id,
            session_id=segment.session_id,
            segment_type=segment.segment_type,
            original_start_time=segment.original_start_time,
            original_end_time=segment.original_end_time,
            output_start_time=segment.output_start_time,
            duration=segment.duration,
            order_index=segment.order_index,
            original_clip_id=segment.original_clip_id,
            segment_metadata=segment.segment_metadata or {},
            created_at=segment.created_at,
            updated_at=segment.updated_at,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加片段失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加片段失败: {str(e)}")


@router.post("/sessions/{session_id}/add-clips/", response_model=AddClipsToSessionResponse)
async def add_clips_to_session(
    session_id: str,
    request: AddClipsToSessionRequest,
    edit_service: ClipEditService = Depends(get_edit_service)
):
    """
    将现有切片添加到编辑会话
    
    Args:
        session_id: 会话ID
        request: 添加请求数据
        edit_service: 编辑服务实例
        
    Returns:
        添加结果
    """
    try:
        segments = edit_service.add_clips_to_session(
            session_id, 
            request.clip_ids, 
            request.insert_position
        )
        
        segment_responses = [edit_service._convert_segment_to_response(s) for s in segments]
        
        return AddClipsToSessionResponse(
            success=True,
            segments=segment_responses,
            added_count=len(segment_responses),
        )
        
    except Exception as e:
        logger.error(f"添加切片到会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加切片到会话失败: {str(e)}")


@router.get("/sessions/{session_id}/segments/", response_model=List[EditSegmentResponse])
async def get_session_segments(
    session_id: str,
    edit_service: ClipEditService = Depends(get_edit_service)
):
    """
    获取会话的所有片段（按顺序）
    
    Args:
        session_id: 会话ID
        edit_service: 编辑服务实例
        
    Returns:
        片段列表
    """
    try:
        segments = edit_service.get_session_segments(session_id)
        
        return [
            EditSegmentResponse(
                id=s.id,
                session_id=s.session_id,
                segment_type=s.segment_type,
                original_start_time=s.original_start_time,
                original_end_time=s.original_end_time,
                output_start_time=s.output_start_time,
                duration=s.duration,
                order_index=s.order_index,
                original_clip_id=s.original_clip_id,
                segment_metadata=s.segment_metadata or {},
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in segments
        ]
        
    except Exception as e:
        logger.error(f"获取会话片段失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取会话片段失败: {str(e)}")


@router.get("/segments/{segment_id}", response_model=EditSegmentResponse)
async def get_segment(
    segment_id: str,
    edit_service: ClipEditService = Depends(get_edit_service)
):
    """
    获取片段详情
    
    Args:
        segment_id: 片段ID
        edit_service: 编辑服务实例
        
    Returns:
        片段信息
        
    Raises:
        HTTPException: 片段不存在时返回404错误
    """
    try:
        segment = edit_service.get_segment(segment_id)
        if not segment:
            raise HTTPException(status_code=404, detail="片段不存在")
        
        return EditSegmentResponse(
            id=segment.id,
            session_id=segment.session_id,
            segment_type=segment.segment_type,
            original_start_time=segment.original_start_time,
            original_end_time=segment.original_end_time,
            output_start_time=segment.output_start_time,
            duration=segment.duration,
            order_index=segment.order_index,
            original_clip_id=segment.original_clip_id,
            segment_metadata=segment.segment_metadata or {},
            created_at=segment.created_at,
            updated_at=segment.updated_at,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取片段失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取片段失败: {str(e)}")


@router.put("/segments/{segment_id}", response_model=EditSegmentResponse)
async def update_segment(
    segment_id: str,
    segment_data: EditSegmentUpdate,
    edit_service: ClipEditService = Depends(get_edit_service)
):
    """
    更新片段
    
    Args:
        segment_id: 片段ID
        segment_data: 更新数据
        edit_service: 编辑服务实例
        
    Returns:
        更新后的片段信息
        
    Raises:
        HTTPException: 片段不存在时返回404错误
    """
    try:
        segment = edit_service.update_segment(segment_id, segment_data)
        if not segment:
            raise HTTPException(status_code=404, detail="片段不存在")
        
        return EditSegmentResponse(
            id=segment.id,
            session_id=segment.session_id,
            segment_type=segment.segment_type,
            original_start_time=segment.original_start_time,
            original_end_time=segment.original_end_time,
            output_start_time=segment.output_start_time,
            duration=segment.duration,
            order_index=segment.order_index,
            original_clip_id=segment.original_clip_id,
            segment_metadata=segment.segment_metadata or {},
            created_at=segment.created_at,
            updated_at=segment.updated_at,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新片段失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新片段失败: {str(e)}")


@router.delete("/segments/{segment_id}")
async def delete_segment(
    segment_id: str,
    edit_service: ClipEditService = Depends(get_edit_service)
):
    """
    删除片段
    
    Args:
        segment_id: 片段ID
        edit_service: 编辑服务实例
        
    Returns:
        删除成功消息
        
    Raises:
        HTTPException: 片段不存在时返回404错误
    """
    try:
        success = edit_service.delete_segment(segment_id)
        if not success:
            raise HTTPException(status_code=404, detail="片段不存在")
        
        return {"message": "片段删除成功", "segment_id": segment_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除片段失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除片段失败: {str(e)}")


# Operation Endpoints

@router.post("/sessions/{session_id}/reorder/")
async def reorder_segments(
    session_id: str,
    request: ReorderSegmentsRequest,
    edit_service: ClipEditService = Depends(get_edit_service)
):
    """
    重排片段顺序
    
    Args:
        session_id: 会话ID
        request: 重排请求数据
        edit_service: 编辑服务实例
        
    Returns:
        重排结果
    """
    try:
        updated_count = edit_service.reorder_segments(session_id, request.segment_orders)
        
        return {
            "success": True,
            "session_id": session_id,
            "updated_count": updated_count,
            "message": f"成功重排 {updated_count} 个片段"
        }
        
    except Exception as e:
        logger.error(f"重排片段失败: {e}")
        raise HTTPException(status_code=500, detail=f"重排片段失败: {str(e)}")


@router.post("/segments/{segment_id}/crop/", response_model=EditSegmentResponse)
async def crop_segment(
    segment_id: str,
    request: CropSegmentRequest,
    edit_service: ClipEditService = Depends(get_edit_service)
):
    """
    裁剪片段（调整开始和结束时间）
    
    Args:
        segment_id: 片段ID
        request: 裁剪请求数据
        edit_service: 编辑服务实例
        
    Returns:
        更新后的片段信息
        
    Raises:
        HTTPException: 片段不存在或时间无效时返回错误
    """
    try:
        if request.new_start_time >= request.new_end_time:
            raise HTTPException(
                status_code=400, 
                detail="开始时间必须小于结束时间"
            )
        
        segment = edit_service.crop_segment(
            segment_id, 
            request.new_start_time, 
            request.new_end_time
        )
        
        if not segment:
            raise HTTPException(status_code=404, detail="片段不存在")
        
        return EditSegmentResponse(
            id=segment.id,
            session_id=segment.session_id,
            segment_type=segment.segment_type,
            original_start_time=segment.original_start_time,
            original_end_time=segment.original_end_time,
            output_start_time=segment.output_start_time,
            duration=segment.duration,
            order_index=segment.order_index,
            original_clip_id=segment.original_clip_id,
            segment_metadata=segment.segment_metadata or {},
            created_at=segment.created_at,
            updated_at=segment.updated_at,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"裁剪片段失败: {e}")
        raise HTTPException(status_code=500, detail=f"裁剪片段失败: {str(e)}")


@router.post("/segments/{segment_id}/split/", response_model=List[EditSegmentResponse])
async def split_segment(
    segment_id: str,
    request: SplitSegmentRequest,
    edit_service: ClipEditService = Depends(get_edit_service)
):
    """
    分割片段
    
    Args:
        segment_id: 片段ID
        request: 分割请求数据
        edit_service: 编辑服务实例
        
    Returns:
        分割后的两个片段列表
        
    Raises:
        HTTPException: 片段不存在或时间无效时返回错误
    """
    try:
        segments = edit_service.split_segment(segment_id, request.split_time)
        
        if not segments:
            raise HTTPException(
                status_code=400, 
                detail="分割失败，请检查分割时间点是否在片段范围内"
            )
        
        return [
            EditSegmentResponse(
                id=s.id,
                session_id=s.session_id,
                segment_type=s.segment_type,
                original_start_time=s.original_start_time,
                original_end_time=s.original_end_time,
                output_start_time=s.output_start_time,
                duration=s.duration,
                order_index=s.order_index,
                original_clip_id=s.original_clip_id,
                segment_metadata=s.segment_metadata or {},
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in segments
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分割片段失败: {e}")
        raise HTTPException(status_code=500, detail=f"分割片段失败: {str(e)}")


async def generate_video_background(
    session_id: str,
    output_name: Optional[str],
    project_id: str,
    edit_service: ClipEditService
):
    """
    后台生成视频任务
    
    Args:
        session_id: 会话ID
        output_name: 输出文件名
        project_id: 项目ID
        edit_service: 编辑服务实例
    """
    try:
        ws_service = get_ws_service()
        
        result = await edit_service.generate_merged_video(
            session_id=session_id,
            output_name=output_name,
            progress_callback=lambda p: ws_service.broadcast_to_project(
                project_id,
                {
                    "type": "edit_progress",
                    "session_id": session_id,
                    "progress": p
                }
            )
        )
        
        if ws_service:
            ws_service.broadcast_to_project(
                project_id,
                {
                    "type": "edit_complete",
                    "session_id": session_id,
                    "success": result.get('success', False),
                    "output_path": result.get('output_path'),
                    "output_duration": result.get('output_duration'),
                    "message": result.get('message')
                }
            )
        
        logger.info(f"后台视频生成完成: {session_id}, 结果: {result}")
        
    except Exception as e:
        logger.error(f"后台视频生成失败: {e}")
        try:
            ws_service = get_ws_service()
            if ws_service:
                ws_service.broadcast_to_project(
                    project_id,
                    {
                        "type": "edit_error",
                        "session_id": session_id,
                        "error": str(e)
                    }
                )
        except Exception as ws_error:
            logger.error(f"发送WebSocket通知失败: {ws_error}")


@router.post("/sessions/{session_id}/generate-video/", response_model=GenerateVideoResponse)
async def generate_merged_video(
    session_id: str,
    request: MergeSegmentsRequest,
    background_tasks: BackgroundTasks,
    edit_service: ClipEditService = Depends(get_edit_service)
):
    """
    生成合并视频
    
    Args:
        session_id: 会话ID
        request: 合并请求数据
        background_tasks: 后台任务
        edit_service: 编辑服务实例
        
    Returns:
        生成响应
    """
    try:
        session = edit_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="编辑会话不存在")
        
        segments = edit_service.get_session_segments(session_id)
        if not segments:
            raise HTTPException(status_code=400, detail="会话中没有片段")
        
        project_id = session.project_id
        
        background_tasks.add_task(
            generate_video_background,
            session_id,
            request.output_name,
            project_id,
            edit_service
        )
        
        return GenerateVideoResponse(
            success=True,
            session_id=session_id,
            task_id=None,
            message="视频生成任务已启动，请等待完成"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动视频生成任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动视频生成任务失败: {str(e)}")


@router.post("/sessions/{session_id}/generate-video-sync/", response_model=GenerateVideoResponse)
async def generate_merged_video_sync(
    session_id: str,
    request: MergeSegmentsRequest,
    edit_service: ClipEditService = Depends(get_edit_service)
):
    """
    同步生成合并视频（阻塞调用）
    
    Args:
        session_id: 会话ID
        request: 合并请求数据
        edit_service: 编辑服务实例
        
    Returns:
        生成响应
    """
    try:
        result = await edit_service.generate_merged_video(
            session_id=session_id,
            output_name=request.output_name
        )
        
        return GenerateVideoResponse(
            success=result.get('success', False),
            session_id=session_id,
            task_id=None,
            message=result.get('message', '完成')
        )
        
    except Exception as e:
        logger.error(f"同步生成视频失败: {e}")
        raise HTTPException(status_code=500, detail=f"同步生成视频失败: {str(e)}")
