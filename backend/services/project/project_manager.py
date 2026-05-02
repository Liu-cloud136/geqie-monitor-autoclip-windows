"""
项目管理模块
提供项目基本管理功能
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

from core.logging_config import get_logger
from models.project import Project
from models.task import Task
from models.clip import Clip

logger = get_logger(__name__)


class ProjectManagerMixin:
    """
    项目管理混合类
    提供项目基本管理功能
    """
    
    def create_project(self, project_data: Dict[str, Any]) -> Project:
        """
        Create a new project with business logic.
        
        Args:
            project_data: 项目数据字典
            
        Returns:
            创建的项目实例
        """
        # Map Pydantic fields to ORM fields
        orm_data = {
            "name": project_data["name"],
            "description": project_data.get("description"),
            "project_type": project_data.get("project_type", "default"),
            "video_path": project_data.get("source_file"),
            "processing_config": project_data.get("settings", {}),
            "project_metadata": {"source_url": project_data.get("source_url")}
        }
        
        return self.create(**orm_data)
    
    def update_project(self, project_id: str, project_data: Dict[str, Any]) -> Optional[Project]:
        """
        Update a project with business logic.
        
        Args:
            project_id: 项目ID
            project_data: 要更新的项目数据
            
        Returns:
            更新后的项目实例，如果不存在则返回None
        """
        # Filter out None values
        update_data = {k: v for k, v in project_data.items() if v is not None}
        if not update_data:
            return self.get(project_id)
        
        # Map schema fields to ORM fields
        orm_data = {}
        for key, value in update_data.items():
            if key == "settings":
                orm_data["processing_config"] = value
            elif key == "processing_config":
                orm_data["processing_config"] = value
            else:
                orm_data[key] = value
        
        return self.update(project_id, **orm_data)
    
    def start_project_processing(self, project_id: str) -> bool:
        """
        Start processing a project.
        
        Args:
            project_id: 项目ID
            
        Returns:
            是否成功启动处理
        """
        project = self.get(project_id)
        if not project or project.status != "pending":
            return False
        
        # Update status to processing
        self.update(project_id, status="processing")
        return True
    
    def complete_project(self, project_id: str) -> bool:
        """
        Mark project as completed.
        
        Args:
            project_id: 项目ID
            
        Returns:
            是否成功标记为完成
        """
        project = self.get(project_id)
        if not project:
            return False
        
        # Update status and completion time
        self.update(project_id, status="completed", completed_at=datetime.utcnow())
        return True
    
    def fail_project(self, project_id: str, error_message: str = None) -> bool:
        """
        Mark project as failed.
        
        Args:
            project_id: 项目ID
            error_message: 错误信息
            
        Returns:
            是否成功标记为失败
        """
        project = self.get(project_id)
        if not project:
            return False
        
        # Update status and add error message to settings
        settings = project.settings or {}
        if error_message:
            settings["error_message"] = error_message
        
        self.update(project_id, status="failed", settings=settings)
        return True
    
    def update_project_status(self, project_id: str, status: str) -> bool:
        """
        Update project status.
        
        Args:
            project_id: 项目ID
            status: 新状态
            
        Returns:
            是否成功更新状态
        """
        project = self.get(project_id)
        if not project:
            return False
        
        # Update status
        self.update(project_id, status=status)
        return True
