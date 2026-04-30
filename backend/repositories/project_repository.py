"""
项目Repository
提供项目相关的数据访问操作
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, asc, func
from pathlib import Path
from .base import BaseRepository
from models.project import Project, ProjectStatus, ProjectType
from models.task import Task
from models.clip import Clip

class ProjectRepository(BaseRepository[Project]):
    """项目Repository类"""
    
    def __init__(self, db: Session):
        super().__init__(Project, db)
    
    def get_by_status(self, status: ProjectStatus) -> List[Project]:
        """
        根据状态获取项目列表
        
        Args:
            status: 项目状态
            
        Returns:
            项目列表
        """
        return self.find_by(status=status)
    
    def get_by_category(self, category: ProjectType) -> List[Project]:
        """
        根据项目类型获取项目列表
        
        Args:
            category: 项目类型
            
        Returns:
            项目列表
        """
        return self.find_by(project_type=category)
    
    def get_recent_projects(self, limit: int = 10) -> List[Project]:
        """
        获取最近创建的项目
        
        Args:
            limit: 返回数量限制
            
        Returns:
            最近的项目列表
        """
        return self.db.query(self.model).order_by(
            desc(self.model.created_at)
        ).limit(limit).all()
    
    def create_project(self, project_data: Dict[str, Any]) -> Project:
        """创建项目记录（分离存储模式）"""
        from ..services.storage_service import StorageService
        import uuid
        
        # 生成项目ID（如果没有提供）
        if "id" not in project_data:
            project_data["id"] = str(uuid.uuid4())
        
        # 初始化存储服务
        storage_service = StorageService(project_data["id"])
        
        # 创建项目记录
        project = Project(
            id=project_data["id"],
            name=project_data["name"],
            description=project_data.get("description"),
            project_type=project_data.get("project_type", ProjectType.DEFAULT),
            status=project_data.get("status", ProjectStatus.PENDING),
            processing_config=project_data.get("processing_config", {}),
            project_metadata={
                'project_id': project_data["id"],
                'created_at': project_data.get("created_at"),
                'storage_service_initialized': True
            }
        )
        
        self.db.add(project)
        self.db.commit()
        return project
    
    def get_project_file_paths(self, project_id: str) -> Dict[str, Optional[Path]]:
        """获取项目文件路径"""
        project = self.get_by_id(project_id)
        if not project:
            return {}
        
        return {
            "video_path": Path(project.video_path) if project.video_path else None,
            "subtitle_path": Path(project.subtitle_path) if project.subtitle_path else None
        }
    
    def update_project_file_path(self, project_id: str, file_type: str, file_path: str) -> bool:
        """更新项目文件路径"""
        project = self.get_by_id(project_id)
        if not project:
            return False
        
        if file_type == "video":
            project.video_path = file_path
        elif file_type == "subtitle":
            project.subtitle_path = file_path
        else:
            return False
        
        self.db.commit()
        return True
    
    def get_project_storage_info(self, project_id: str) -> Dict[str, Any]:
        """获取项目存储信息"""
        from ..services.storage_service import StorageService
        
        project = self.get_by_id(project_id)
        if not project:
            return {}
        
        storage_service = StorageService(project_id)
        storage_info = storage_service.get_project_storage_info()
        
        return {
            "project_id": project_id,
            "storage_info": storage_info,
            "file_paths": {
                "video_path": project.video_path,
                "subtitle_path": project.subtitle_path
            }
        }
    
    def get_processing_projects(self) -> List[Project]:
        """
        获取正在处理的项目
        
        Returns:
            正在处理的项目列表
        """
        return self.find_by(status=ProjectStatus.PROCESSING)
    
    def get_completed_projects(self) -> List[Project]:
        """
        获取已完成的项目
        
        Returns:
            已完成的项目列表
        """
        return self.find_by(status=ProjectStatus.COMPLETED)
    
    def get_error_projects(self) -> List[Project]:
        """
        获取出错的项目
        
        Returns:
            出错的项目列表
        """
        return self.find_by(status=ProjectStatus.FAILED)
    
    def search_projects(self, keyword: str) -> List[Project]:
        """
        搜索项目
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            匹配的项目列表
        """
        return self.db.query(self.model).filter(
            self.model.name.contains(keyword) | 
            self.model.description.contains(keyword)
        ).all()
    
    def get_projects_with_clips_count(self, skip: int = 0, limit: int = 100) -> List[Project]:
        """
        获取项目列表，包含切片数量
        
        Args:
            skip: 跳过的记录数
            limit: 返回的记录数限制
            
        Returns:
            项目列表
        """
        return self.db.query(self.model).options(
            # 这里可以添加预加载选项，减少N+1查询问题
        ).offset(skip).limit(limit).all()
    
    def get_project_with_details(self, project_id: str) -> Optional[Project]:
        """
        获取项目详情，包含关联的切片和合集
        
        Args:
            project_id: 项目ID
            
        Returns:
            项目实例或None
        """
        return self.db.query(self.model).filter(
            self.model.id == project_id
        ).first()
    
    def update_project_status(self, project_id: str, status: ProjectStatus) -> Optional[Project]:
        """
        更新项目状态
        
        Args:
            project_id: 项目ID
            status: 新状态
            
        Returns:
            更新后的项目实例或None
        """
        return self.update(project_id, status=status)
    
    def get_projects_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Project]:
        """
        根据日期范围获取项目
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            项目列表
        """
        return self.db.query(self.model).filter(
            self.model.created_at >= start_date,
            self.model.created_at <= end_date
        ).order_by(desc(self.model.created_at)).all()
    
    def get_project_statistics(self) -> dict:
        """
        获取项目统计信息
        
        Returns:
            统计信息字典
        """
        total_projects = self.count()
        processing_projects = len(self.get_processing_projects())
        completed_projects = len(self.get_completed_projects())
        error_projects = len(self.get_error_projects())
        
        return {
            "total": total_projects,
            "processing": processing_projects,
            "completed": completed_projects,
            "error": error_projects,
            "success_rate": (completed_projects / total_projects * 100) if total_projects > 0 else 0
        }
    
    def get_projects_stats_batch(self, project_ids: List[str]) -> Dict[str, Dict[str, int]]:
        """
        批量获取多个项目的统计信息（clips_count, tasks_count）
        
        Args:
            project_ids: 项目ID列表
            
        Returns:
            字典，key为project_id，value为包含统计信息的字典
        """
        if not project_ids:
            return {}
        
        clips_counts = self.db.query(
            Clip.project_id,
            func.count(Clip.id).label('count')
        ).filter(
            Clip.project_id.in_(project_ids)
        ).group_by(Clip.project_id).all()
        
        tasks_counts = self.db.query(
            Task.project_id,
            func.count(Task.id).label('count')
        ).filter(
            Task.project_id.in_(project_ids)
        ).group_by(Task.project_id).all()
        
        result = {pid: {'clips_count': 0, 'tasks_count': 0} for pid in project_ids}
        
        for row in clips_counts:
            result[row.project_id]['clips_count'] = row.count
        
        for row in tasks_counts:
            result[row.project_id]['tasks_count'] = row.count
        
        return result
    
    def get_project_stats_single(self, project_id: str) -> Dict[str, int]:
        """
        获取单个项目的统计信息（优化版，使用聚合查询）
        
        Args:
            project_id: 项目ID
            
        Returns:
            包含clips_count和tasks_count的字典
        """
        clips_count = self.db.query(func.count(Clip.id)).filter(
            Clip.project_id == project_id
        ).scalar() or 0
        
        tasks_count = self.db.query(func.count(Task.id)).filter(
            Task.project_id == project_id
        ).scalar() or 0
        
        return {
            'clips_count': clips_count,
            'tasks_count': tasks_count
        }