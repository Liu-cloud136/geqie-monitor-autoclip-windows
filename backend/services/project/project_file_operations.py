"""
项目文件操作模块
提供项目文件相关的操作功能
"""

import logging
from typing import Dict, Any
from pathlib import Path

from core.logging_config import get_logger

logger = get_logger(__name__)


class ProjectFileOperationsMixin:
    """
    项目文件操作混合类
    提供项目文件相关的操作功能
    """
    
    def get_project_paths(self, project_id: str) -> Dict[str, Path]:
        """
        获取项目相关路径
        
        Args:
            project_id: 项目ID
            
        Returns:
            包含项目相关路径的字典
        """
        from core.path_utils import get_project_directory
        
        project_dir = get_project_directory(project_id)
        
        return {
            "project_dir": project_dir,
            "metadata_dir": project_dir / "metadata",
            "raw_dir": project_dir / "raw",
            "outputs_dir": project_dir / "outputs",
            "logs_dir": project_dir / "logs"
        }
    
    def ensure_project_directories(self, project_id: str):
        """
        确保项目目录结构存在
        
        Args:
            project_id: 项目ID
        """
        paths = self.get_project_paths(project_id)
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
        logger.info(f"已确保项目 {project_id} 的目录结构存在")
