"""
项目服务
提供项目相关的业务逻辑操作

重构说明：
- 核心逻辑已拆分到 services/project/ 目录下的多个模块中
- 本文件保持向后兼容，作为统一入口点
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
import shutil
import logging
from pathlib import Path

from services.base import BaseService
from repositories.project_repository import ProjectRepository
from models.project import Project
from models.task import Task
from models.clip import Clip
from services.exceptions import FileOperationError

from schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse, ProjectFilter
from schemas.base import PaginationParams, PaginationResponse
from schemas.project import ProjectType, ProjectStatus
from schemas.task import TaskStatus
from core.logging_config import get_logger

# 导入拆分后的模块
from .project.project_manager import ProjectManagerMixin
from .project.project_statistics import ProjectStatisticsMixin
from .project.project_cleanup import ProjectCleanupMixin
from .project.project_file_operations import ProjectFileOperationsMixin

logger = get_logger(__name__)


class ProjectService(BaseService[Project, ProjectCreate, ProjectUpdate, ProjectResponse], 
                      ProjectManagerMixin, ProjectStatisticsMixin, ProjectCleanupMixin, ProjectFileOperationsMixin):
    """
    Project service with business logic.
    
    重构说明：
    - 使用混合类（Mixin）模式组织代码
    - ProjectManagerMixin: 提供项目基本管理功能
    - ProjectStatisticsMixin: 提供项目统计信息功能
    - ProjectCleanupMixin: 提供项目删除和清理功能
    - ProjectFileOperationsMixin: 提供项目文件相关操作功能
    """
    
    def __init__(self, db: Session):
        """
        初始化项目服务
        
        Args:
            db: 数据库会话
        """
        repository = ProjectRepository(db)
        super().__init__(repository)
        self.db = db


# 导出向后兼容的类
__all__ = [
    'ProjectService',
]
