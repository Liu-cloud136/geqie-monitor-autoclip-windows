"""
切片服务
提供切片相关的业务逻辑操作
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from services.base import BaseService
from repositories.clip_repository import ClipRepository
from models.clip import Clip
from schemas.clip import ClipCreate, ClipUpdate, ClipResponse, ClipListResponse, ClipFilter
from schemas.base import PaginationParams, PaginationResponse
from services.cache_service import get_cache_service


DEFAULT_CACHE_TTL = 3600
DEFAULT_PAGE_SKIP = 0
DEFAULT_PAGE_LIMIT = 100
MIN_SCORE_THRESHOLD = 0.8


class ClipService(BaseService[Clip, ClipCreate, ClipUpdate, ClipResponse]):
    """
    切片服务类
    
    提供切片的创建、更新、查询、缓存等业务逻辑操作
    
    Attributes:
        CACHE_TTL: 缓存过期时间（秒）
        db: 数据库会话
        cache_service: 缓存服务实例
    """
    
    CACHE_TTL = DEFAULT_CACHE_TTL
    
    def __init__(self, db: Session) -> None:
        """
        初始化切片服务
        
        Args:
            db: 数据库会话
        """
        repository = ClipRepository(db)
        super().__init__(repository)
        self.db = db
        self.cache_service = get_cache_service()
    
    def create_clip(self, clip_data: ClipCreate) -> Clip:
        """
        创建新的切片
        
        Args:
            clip_data: 切片创建数据
            
        Returns:
            创建的切片对象
            
        Raises:
            Exception: 创建失败时抛出异常
        """
        data = clip_data.model_dump()
        orm_data = {
            "project_id": data["project_id"],
            "title": data["title"],
            "description": data["description"],
            "start_time": int(data["start_time"]) if data["start_time"] is not None else 0,
            "end_time": int(data["end_time"]) if data["end_time"] is not None else 0,
            "duration": int(data["duration"]) if data["duration"] is not None else 0,
            "score": data.get("score"),
            "clip_metadata": data.get("clip_metadata", {}),
            "tags": data.get("tags", [])
        }
        clip = self.create(**orm_data)
        self._invalidate_clip_cache(clip.id, data["project_id"])
        return clip
    
    def update_clip(self, clip_id: str, clip_data: ClipUpdate) -> Optional[Clip]:
        """
        更新切片信息
        
        Args:
            clip_id: 切片ID
            clip_data: 切片更新数据
            
        Returns:
            更新后的切片对象，如果不存在则返回None
        """
        update_data = {k: v for k, v in clip_data.model_dump().items() if v is not None}
        if not update_data:
            return self.get(clip_id)
        
        clip = self.get(clip_id)
        if clip:
            self._invalidate_clip_cache(clip_id, clip.project_id)
        
        return self.update(clip_id, **update_data)
    
    async def get_clip_cached(self, clip_id: str) -> Optional[Clip]:
        """
        获取切片（带缓存）
        
        Args:
            clip_id: 切片ID
            
        Returns:
            切片对象，如果不存在则返回None
        """
        cache_key = f"clip:{clip_id}"
        
        if self.cache_service:
            cached = await self.cache_service.get(cache_key)
            if cached:
                return Clip(**cached)
        
        clip = self.get(clip_id)
        if clip and self.cache_service:
            await self.cache_service.set(cache_key, clip.__dict__, self.CACHE_TTL)
        
        return clip
    
    async def get_clips_by_project_cached(self, project_id: str, skip: int = DEFAULT_PAGE_SKIP, limit: int = DEFAULT_PAGE_LIMIT) -> List[Clip]:
        """
        获取项目的切片列表（带缓存）
        
        Args:
            project_id: 项目ID
            skip: 跳过的记录数
            limit: 返回的记录数限制
            
        Returns:
            切片对象列表
        """
        cache_key = f"project_clips:{project_id}:{skip}:{limit}"
        
        if self.cache_service:
            cached = await self.cache_service.get(cache_key)
            if cached:
                return [Clip(**item) for item in cached]
        
        clips = self.get_clips_by_project(project_id, skip, limit)
        if self.cache_service and clips:
            await self.cache_service.set(cache_key, [clip.__dict__ for clip in clips], self.CACHE_TTL)
        
        return clips
    
    def _invalidate_clip_cache(self, clip_id: str, project_id: str):
        """
        使切片相关缓存失效
        
        Args:
            clip_id: 切片ID
            project_id: 项目ID
        """
        if self.cache_service:
            import asyncio
            asyncio.create_task(self._clear_clip_cache_async(clip_id, project_id))
    
    async def _clear_clip_cache_async(self, clip_id: str, project_id: str):
        """
        异步清除切片缓存
        
        Args:
            clip_id: 切片ID
            project_id: 项目ID
        """
        if self.cache_service:
            await self.cache_service.delete(f"clip:{clip_id}")
            await self.cache_service.clear_pattern(f"project_clips:{project_id}:*")
    
    def bulk_create_clips(self, clips_data: List[ClipCreate]) -> List[Clip]:
        """
        批量创建切片（优化性能）
        
        Args:
            clips_data: 切片创建数据列表
            
        Returns:
            创建的切片对象列表
        """
        clips_data_dicts = []
        project_id = None
        
        for clip_data in clips_data:
            data = clip_data.model_dump()
            if project_id is None:
                project_id = data["project_id"]
            
            orm_data = {
                "project_id": data["project_id"],
                "title": data["title"],
                "description": data["description"],
                "start_time": int(data["start_time"]) if data["start_time"] is not None else 0,
                "end_time": int(data["end_time"]) if data["end_time"] is not None else 0,
                "duration": int(data["duration"]) if data["duration"] is not None else 0,
                "score": data.get("score"),
                "clip_metadata": data.get("clip_metadata", {}),
                "tags": data.get("tags", [])
            }
            clips_data_dicts.append(orm_data)
        
        clips = self.repository.bulk_create_clips(clips_data_dicts)
        
        if project_id:
            self._invalidate_clip_cache("", project_id)
        
        return clips
    
    def get_clips_by_project(self, project_id: str, skip: int = DEFAULT_PAGE_SKIP, limit: int = DEFAULT_PAGE_LIMIT) -> List[Clip]:
        """
        根据项目ID获取切片列表
        
        Args:
            project_id: 项目ID
            skip: 跳过的记录数
            limit: 返回的记录数限制
            
        Returns:
            切片对象列表
        """
        return self.repository.find_by(project_id=project_id)
    
    def get_clips_paginated(
        self, 
        pagination: PaginationParams,
        filters: Optional[ClipFilter] = None
    ) -> ClipListResponse:
        """
        获取分页切片列表（支持过滤）
        
        Args:
            pagination: 分页参数
            filters: 过滤条件
            
        Returns:
            分页切片列表响应
        """
        filter_dict = {}
        if filters:
            filter_data = filters.model_dump()
            filter_dict = {k: v for k, v in filter_data.items() if v is not None}
        
        items, pagination_response = self.get_paginated(pagination, filter_dict)
        
        clip_responses = []
        for clip in items:
            status_obj = getattr(clip, 'status', None)
            status_value = status_obj.value if hasattr(status_obj, 'value') else 'pending'
            
            clip_responses.append(ClipResponse(
                id=str(clip.id),
                project_id=str(clip.project_id),
                title=str(clip.title),
                description=str(clip.description) if clip.description else None,
                start_time=getattr(clip, 'start_time', 0),
                end_time=getattr(clip, 'end_time', 0),
                duration=int(getattr(clip, 'duration', 0)),
                score=getattr(clip, 'score', None),
                status=status_value,
                video_path=getattr(clip, 'video_path', None),
                tags=getattr(clip, 'tags', []) or [],
                clip_metadata=getattr(clip, 'clip_metadata', {}) or {},
                created_at=getattr(clip, 'created_at', None) if isinstance(getattr(clip, 'created_at', None), (type(None), __import__('datetime').datetime)) else None,
                updated_at=getattr(clip, 'updated_at', None) if isinstance(getattr(clip, 'updated_at', None), (type(None), __import__('datetime').datetime)) else None
            ))
        
        return ClipListResponse(
            items=clip_responses,
            pagination=pagination_response
        ) 