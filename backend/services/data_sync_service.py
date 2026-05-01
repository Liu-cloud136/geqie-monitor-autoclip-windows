"""
数据同步服务
将处理结果同步到数据库

重构说明：
- 核心逻辑已拆分到 services/sync/ 目录下的多个模块中
- 本文件保持向后兼容，作为统一入口点
"""

import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from sqlalchemy.orm import Session

from models.clip import Clip, ClipStatus
from models.project import Project, ProjectStatus, ProjectType
from models.task import Task, TaskStatus
from datetime import datetime
from core.logging_config import get_logger

# 导入拆分后的模块
from .sync.sync_utils import SyncUtilsMixin
from .sync.project_sync import ProjectSyncMixin
from .sync.clip_sync import ClipSyncMixin
from .sync.ai_result_sync import AIResultSyncMixin

logger = get_logger(__name__)


class DataSyncService(SyncUtilsMixin, ProjectSyncMixin, ClipSyncMixin, AIResultSyncMixin):
    """
    数据同步服务
    
    重构说明：
    - 使用混合类（Mixin）模式组织代码
    - SyncUtilsMixin: 提供同步工具函数
    - ProjectSyncMixin: 提供项目同步功能
    - ClipSyncMixin: 提供切片同步功能
    - AIResultSyncMixin: 提供AI结果同步功能
    """
    
    def __init__(self, db: Session):
        """
        初始化数据同步服务
        
        Args:
            db: 数据库会话
        """
        self.db = db


# 导出向后兼容的类
__all__ = [
    'DataSyncService',
]
