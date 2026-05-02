"""
项目统计模块
提供项目统计信息功能
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from core.logging_config import get_logger
from models.project import Project
from models.task import Task
from models.clip import Clip

logger = get_logger(__name__)


class ProjectStatisticsMixin:
    """
    项目统计混合类
    提供项目统计信息功能
    """
    
    def get_project_with_stats(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get project with statistics.
        
        Args:
            project_id: 项目ID
            
        Returns:
            包含统计信息的项目数据字典
        """
        project = self.get(project_id)
        if not project:
            return None

        # 使用优化的聚合查询获取统计信息（减少查询次数）
        from repositories.project_repository import ProjectRepository
        project_repo = ProjectRepository(self.db)
        stats = project_repo.get_project_stats_single(project_id)
        total_clips = stats['clips_count']
        total_tasks = stats['tasks_count']
        
        # Get progress data from Redis if available
        progress_data = None
        try:
            from services.simple_progress import get_progress_snapshot
            progress_data = get_progress_snapshot(project_id)
        except Exception as e:
            logger.debug(f"获取进度数据失败: {e}")

        # Create response
        response_data = {
            "id": str(getattr(project, 'id', '')),
            "name": str(getattr(project, 'name', '')),
            "description": str(getattr(project, 'description', '')) if getattr(project, 'description', None) is not None else None,
            "project_type": getattr(project, 'project_type', 'default'),
            "status": getattr(project, 'status', 'pending'),
            "source_url": project.project_metadata.get("source_url") if getattr(project, 'project_metadata', None) else None,
            "source_file": str(getattr(project, 'video_path', '')) if getattr(project, 'video_path', None) is not None else None,
            "video_path": str(getattr(project, 'video_path', '')) if getattr(project, 'video_path', None) is not None else None,
            "thumbnail": getattr(project, 'thumbnail', None),
            "settings": getattr(project, 'processing_config', {}) or {},
            "processing_config": getattr(project, 'processing_config', {}) or {},
            "project_metadata": getattr(project, 'project_metadata', {}) or {},
            "created_at": self._convert_utc_to_local(getattr(project, 'created_at', None)),
            "updated_at": self._convert_utc_to_local(getattr(project, 'updated_at', None)),
            "completed_at": self._convert_utc_to_local(getattr(project, 'completed_at', None)),
            "total_clips": total_clips,
            "total_tasks": total_tasks
        }
        
        # Add progress data if available
        if progress_data:
            response_data['processing_config'] = response_data.get('settings', {})
            response_data['processing_config']['progress'] = {
                "stage": progress_data.get('stage', ''),
                "percent": progress_data.get('percent', 0),
                "message": progress_data.get('message', ''),
                "ts": progress_data.get('ts', 0),
                "estimated_remaining": progress_data.get('estimated_remaining')
            }

        return response_data
    
    def get_projects_paginated(
        self, 
        pagination, 
        filters: Optional[dict] = None
    ) -> Dict[str, Any]:
        """
        Get paginated projects with filtering.
        
        优化版本：使用批量查询消除N+1问题，将2N+1次查询减少为3次查询。
        
        Args:
            pagination: 分页参数（可以是 PaginationParams 对象或包含 page/size 的字典）
            filters: 过滤条件字典
            
        Returns:
            包含项目列表和分页信息的字典
        """
        filter_dict = filters or {}
        
        # 从 pagination 参数中提取 page 和 size
        if hasattr(pagination, 'page'):
            page = pagination.page
            size = pagination.size
        else:
            page = pagination.get('page', 1)
            size = pagination.get('size', 20)
        
        items, pagination_response = self.get_paginated(
            pagination, 
            filter_dict
        )
        
        if not items:
            return {"items": [], "pagination": pagination_response}
        
        # 批量获取所有项目的统计信息（优化：2次聚合查询替代2N次独立查询）
        project_ids = [str(project.id) for project in items]
        from repositories.project_repository import ProjectRepository
        project_repo = ProjectRepository(self.db)
        stats_map = project_repo.get_projects_stats_batch(project_ids)
        
        # Convert to response schemas
        project_responses = []
        for project in items:
            project_id = str(project.id)
            stats = stats_map.get(project_id, {'clips_count': 0, 'tasks_count': 0})
            total_clips = stats['clips_count']
            total_tasks = stats['tasks_count']
            
            project_responses.append({
                "id": str(getattr(project, 'id', '')),
                "name": str(getattr(project, 'name', '')),
                "description": str(getattr(project, 'description', '')) if getattr(project, 'description', None) is not None else None,
                "project_type": getattr(project, 'project_type', 'default'),
                "status": getattr(project, 'status', 'pending'),
                "source_url": project.project_metadata.get("source_url") if getattr(project, 'project_metadata', None) else None,
                "source_file": str(getattr(project, 'video_path', '')) if getattr(project, 'video_path', None) is not None else None,
                "video_path": str(getattr(project, 'video_path', '')) if getattr(project, 'video_path', None) is not None else None,
                "thumbnail": getattr(project, 'thumbnail', None),
                "settings": getattr(project, 'processing_config', {}) or {},
                "created_at": self._convert_utc_to_local(getattr(project, 'created_at', None)),
                "updated_at": self._convert_utc_to_local(getattr(project, 'updated_at', None)),
                "completed_at": self._convert_utc_to_local(getattr(project, 'completed_at', None)),
                "total_clips": total_clips,
                "total_tasks": total_tasks
            })
        
        return {
            "items": project_responses,
            "pagination": pagination_response
        }
    
    def _convert_utc_to_local(self, dt: Optional[datetime]) -> Optional[datetime]:
        """
        将UTC时间转换为本地时间（SQLite存储时丢失了时区信息）
        
        Args:
            dt: 要转换的时间
            
        Returns:
            转换后的本地时间
        """
        if dt is None:
            return None
        
        from datetime import timezone
        
        # 尝试使用 zoneinfo 模块（Python 3.9+ 标准库）
        try:
            from zoneinfo import ZoneInfo
            local_tz = ZoneInfo('Asia/Shanghai')
            utc_time = dt.replace(tzinfo=timezone.utc)
            local_time = utc_time.astimezone(local_tz)
            return local_time
        except (ImportError, Exception):
            # zoneinfo 不可用，尝试使用 pytz
            try:
                import pytz
                local_tz = pytz.timezone('Asia/Shanghai')
                utc_time = dt.replace(tzinfo=timezone.utc)
                local_time = utc_time.astimezone(local_tz)
                return local_time
            except (ImportError, Exception):
                # 如果都不可用，返回原始时间（不带时区）
                logger.warning("无法进行时区转换，zoneinfo 和 pytz 都不可用")
                return dt
