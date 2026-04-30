"""
切片API路由
提供切片相关的HTTP接口
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from core.database import get_db
from services.clip_service import ClipService
from schemas.clip import ClipCreate, ClipUpdate, ClipResponse, ClipListResponse, ClipStatus, ClipFilter
from schemas.base import PaginationParams
from models.clip import Clip
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_TITLE_LENGTH = 200
DEFAULT_PAGE_SIZE = 20
MIN_PAGE_SIZE = 1
MAX_PAGE_SIZE = 100


def get_clip_service(db: Session = Depends(get_db)) -> ClipService:
    """
    获取切片服务实例
    
    Args:
        db: 数据库会话
        
    Returns:
        切片服务实例
    """
    return ClipService(db)


@router.patch("/{clip_id}/title", response_model=ClipResponse)
async def update_clip_title(
    clip_id: str,
    title_data: dict,
    clip_service: ClipService = Depends(get_clip_service)
):
    """
    更新切片标题
    
    Args:
        clip_id: 切片ID
        title_data: 包含新标题的字典
        clip_service: 切片服务实例
        
    Returns:
        更新后的切片信息
        
    Raises:
        HTTPException: 标题为空或过长时返回400错误
        HTTPException: 切片不存在时返回404错误
        HTTPException: 更新失败时返回500错误
    """
    try:
        new_title = title_data.get("title", "").strip()
        if not new_title:
            raise HTTPException(status_code=400, detail="标题不能为空")
        
        if len(new_title) > MAX_TITLE_LENGTH:
            raise HTTPException(status_code=400, detail=f"标题长度不能超过{MAX_TITLE_LENGTH}个字符")
        
        clip = clip_service.update_clip(clip_id, ClipUpdate(title=new_title))
        if not clip:
            raise HTTPException(status_code=404, detail="切片不存在")
        
        return ClipResponse(
            id=str(clip.id),
            project_id=str(clip.project_id),
            title=str(clip.title),
            description=str(clip.description) if clip.description else None,
            start_time=getattr(clip, 'start_time', 0),
            end_time=getattr(clip, 'end_time', 0),
            duration=int(getattr(clip, 'duration', 0)),
            score=getattr(clip, 'score', None),
            status=getattr(clip, 'status', 'pending'),
            video_path=getattr(clip, 'video_path', None),
            tags=getattr(clip, 'tags', []) or [],
            clip_metadata=getattr(clip, 'clip_metadata', {}) or {},
            created_at=getattr(clip, 'created_at', None),
            updated_at=getattr(clip, 'updated_at', None),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新切片标题失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新切片标题失败: {str(e)}")


@router.post("/{clip_id}/generate-title", response_model=dict)
async def generate_clip_title(
    clip_id: str,
    clip_service: ClipService = Depends(get_clip_service)
):
    """
    使用LLM生成切片标题
    
    Args:
        clip_id: 切片ID
        clip_service: 切片服务实例
        
    Returns:
        包含生成标题的字典
        
    Raises:
        HTTPException: 切片不存在时返回404错误
        HTTPException: LLM调用失败时返回500错误
    """
    try:
        clip = clip_service.get(clip_id)
        if not clip:
            raise HTTPException(status_code=404, detail="切片不存在")
        
        clip_metadata = getattr(clip, 'clip_metadata', {}) or {}
        
        if not clip_metadata:
            raise HTTPException(status_code=404, detail="切片元数据不存在")
        
        llm_input = [{
            "id": clip_id,
            "title": clip_metadata.get('outline', '') or getattr(clip, 'title', ''),
            "content": clip_metadata.get('content', []),
            "recommend_reason": clip_metadata.get('recommend_reason', '')
        }]
        
        from ...utils.llm_client import LLMClient
        from ...core.shared_config import PROMPT_FILES
        
        llm_client = LLMClient()
        
        with open(PROMPT_FILES['title'], 'r', encoding='utf-8') as f:
            title_prompt = f.read()
        
        raw_response = llm_client.call_with_retry(title_prompt, llm_input)
        
        if not raw_response:
            raise HTTPException(status_code=500, detail="LLM调用失败")
        
        titles_map = llm_client.parse_json_response(raw_response)
        
        if not isinstance(titles_map, dict) or clip_id not in titles_map:
            raise HTTPException(status_code=500, detail="LLM返回格式错误")
        
        generated_title = titles_map[clip_id]
        
        return {
            "clip_id": clip_id,
            "generated_title": generated_title,
            "success": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成切片标题失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成切片标题失败: {str(e)}")


@router.post("/", response_model=ClipResponse)
async def create_clip(
    clip_data: ClipCreate,
    clip_service: ClipService = Depends(get_clip_service)
):
    """
    创建新切片
    
    Args:
        clip_data: 切片创建数据
        clip_service: 切片服务实例
        
    Returns:
        创建的切片信息
        
    Raises:
        HTTPException: 创建失败时返回400错误
    """
    try:
        clip = clip_service.create_clip(clip_data)
        status_obj = getattr(clip, 'status', None)
        status_value = status_obj.value if hasattr(status_obj, 'value') else 'pending'
        
        return ClipResponse(
            id=str(getattr(clip, 'id', '')),
            project_id=str(getattr(clip, 'project_id', '')),
            title=str(getattr(clip, 'title', '')),
            description=str(getattr(clip, 'description', '')) if getattr(clip, 'description', None) else None,
            start_time=getattr(clip, 'start_time', 0),
            end_time=getattr(clip, 'end_time', 0),
            duration=getattr(clip, 'duration', 0),
            score=getattr(clip, 'score', None),
            status=status_value,
            video_path=getattr(clip, 'video_path', None),
            tags=getattr(clip, 'tags', []) or [],
            clip_metadata=getattr(clip, 'clip_metadata', {}) or {},
            created_at=getattr(clip, 'created_at', None) if isinstance(getattr(clip, 'created_at', None), (type(None), __import__('datetime').datetime)) else None,
            updated_at=getattr(clip, 'updated_at', None) if isinstance(getattr(clip, 'updated_at', None), (type(None), __import__('datetime').datetime)) else None
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=ClipListResponse)
async def get_clips(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(DEFAULT_PAGE_SIZE, ge=MIN_PAGE_SIZE, le=MAX_PAGE_SIZE, description="每页数量"),
    project_id: Optional[str] = Query(None, description="按项目ID过滤"),
    status: Optional[ClipStatus] = Query(None, description="按状态过滤"),
    clip_service: ClipService = Depends(get_clip_service)
):
    """
    获取分页切片列表（支持过滤）
    
    Args:
        page: 页码，从1开始
        size: 每页数量
        project_id: 项目ID（可选）
        status: 切片状态（可选）
        clip_service: 切片服务实例
        
    Returns:
        分页切片列表
        
    Raises:
        HTTPException: 查询失败时返回400错误
    """
    try:
        pagination = PaginationParams(page=page, size=size)
        
        filters = None
        if project_id or status:
            filters = ClipFilter(
                project_id=project_id,
                status=status
            )
        
        return clip_service.get_clips_paginated(pagination, filters)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{clip_id}", response_model=ClipResponse)
async def get_clip(
    clip_id: str,
    clip_service: ClipService = Depends(get_clip_service)
):
    """
    根据ID获取切片
    
    Args:
        clip_id: 切片ID
        clip_service: 切片服务实例
        
    Returns:
        切片信息
        
    Raises:
        HTTPException: 切片不存在时返回404错误
        HTTPException: 查询失败时返回400错误
    """
    try:
        clip = clip_service.get(clip_id)
        if not clip:
            raise HTTPException(status_code=404, detail="Clip not found")
        return clip
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{clip_id}", response_model=ClipResponse)
async def update_clip(
    clip_id: str,
    clip_data: ClipUpdate,
    clip_service: ClipService = Depends(get_clip_service)
):
    """
    更新切片信息
    
    Args:
        clip_id: 切片ID
        clip_data: 切片更新数据
        clip_service: 切片服务实例
        
    Returns:
        更新后的切片信息
        
    Raises:
        HTTPException: 切片不存在时返回404错误
        HTTPException: 更新失败时返回400错误
    """
    try:
        clip = clip_service.update_clip(clip_id, clip_data)
        if not clip:
            raise HTTPException(status_code=404, detail="Clip not found")
        return clip
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{clip_id}")
async def delete_clip(
    clip_id: str,
    clip_service: ClipService = Depends(get_clip_service)
):
    """
    删除切片
    
    Args:
        clip_id: 切片ID
        clip_service: 切片服务实例
        
    Returns:
        删除成功消息
        
    Raises:
        HTTPException: 切片不存在时返回404错误
        HTTPException: 删除失败时返回400错误
    """
    try:
        success = clip_service.delete(clip_id)
        if not success:
            raise HTTPException(status_code=404, detail="Clip not found")
        return {"message": "Clip deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cleanup-duplicates")
async def cleanup_duplicate_clips(
    project_id: str,
    db: Session = Depends(get_db)
):
    """
    清理项目中的重复切片数据
    
    Args:
        project_id: 项目ID
        db: 数据库会话
        
    Returns:
        清理结果统计信息
        
    Raises:
        HTTPException: 项目不存在时返回404错误
        HTTPException: 元数据文件不存在时返回404错误
        HTTPException: 清理失败时返回500错误
    """
    try:
        from ...models.project import Project
        import json
        from pathlib import Path
        from ...core.config import get_data_directory
        
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        db_clips = db.query(Clip).filter(Clip.project_id == project_id).all()
        logger.info(f"数据库中有 {len(db_clips)} 个切片")
        
        data_dir = get_data_directory()
        project_dir = data_dir / "projects" / project_id
        clips_metadata_file = project_dir / "clips_metadata.json"
        
        if not clips_metadata_file.exists():
            raise HTTPException(status_code=404, detail="切片元数据文件不存在")
        
        with open(clips_metadata_file, 'r', encoding='utf-8') as f:
            original_clips = json.load(f)
        
        logger.info(f"文件系统中有 {len(original_clips)} 个切片")
        
        original_clip_ids = {clip['id']: clip for clip in original_clips}
        
        deleted_count = 0
        kept_count = 0
        
        for db_clip in db_clips:
            metadata = db_clip.clip_metadata or {}
            original_id = metadata.get('id')
            
            if original_id and original_id in original_clip_ids:
                kept_count += 1
                logger.info(f"保留切片: {db_clip.title} (ID: {original_id})")
            else:
                logger.info(f"删除重复切片: {db_clip.title} (DB ID: {db_clip.id})")
                db.delete(db_clip)
                deleted_count += 1
        
        db.commit()
        
        return {
            "project_id": project_id,
            "project_name": project.name,
            "original_count": len(original_clips),
            "db_before_count": len(db_clips),
            "kept_count": kept_count,
            "deleted_count": deleted_count,
            "message": f"清理完成：保留 {kept_count} 个，删除 {deleted_count} 个重复切片"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"清理重复切片失败: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")


@router.post("/resync-project")
async def resync_project_clips(
    project_id: str,
    db: Session = Depends(get_db)
):
    """
    重新同步项目的切片数据
    
    Args:
        project_id: 项目ID
        db: 数据库会话
        
    Returns:
        同步结果统计信息
        
    Raises:
        HTTPException: 项目不存在时返回404错误
        HTTPException: 同步失败时返回500错误
    """
    try:
        from ...models.project import Project
        from ...services.data_sync_service import DataSyncService
        from pathlib import Path
        from ...core.config import get_data_directory
        
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        existing_clips = db.query(Clip).filter(Clip.project_id == project_id).all()
        deleted_count = len(existing_clips)
        for clip in existing_clips:
            db.delete(clip)
        db.commit()
        logger.info(f"删除了 {deleted_count} 个现有切片")
        
        data_dir = get_data_directory()
        project_dir = data_dir / "projects" / project_id
        
        sync_service = DataSyncService(db)
        synced_count = sync_service._sync_clips_from_filesystem(project_id, project_dir)
        
        return {
            "project_id": project_id,
            "project_name": project.name,
            "deleted_count": deleted_count,
            "synced_count": synced_count,
            "message": f"重新同步完成：删除 {deleted_count} 个，同步 {synced_count} 个切片"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重新同步切片失败: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"重新同步失败: {str(e)}")