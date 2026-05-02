"""
项目同步模块
提供项目数据同步功能
"""

import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from core.logging_config import get_logger
from models.project import Project, ProjectStatus, ProjectType

logger = get_logger(__name__)


class ProjectSyncMixin:
    """
    项目同步混合类
    提供项目数据同步功能
    """
    
    def sync_all_projects_from_filesystem(self, data_dir: Path) -> Dict[str, Any]:
        """
        从文件系统同步所有项目到数据库
        
        Args:
            data_dir: 数据目录路径
            
        Returns:
            同步结果字典
        """
        try:
            logger.info(f"开始从文件系统同步所有项目: {data_dir}")
            
            projects_dir = data_dir / "projects"
            if not projects_dir.exists():
                logger.warning(f"项目目录不存在: {projects_dir}")
                return {"success": False, "error": "项目目录不存在"}
            
            synced_projects = []
            failed_projects = []
            
            # 遍历所有项目目录
            for project_dir in projects_dir.iterdir():
                if project_dir.is_dir() and not project_dir.name.startswith('.'):
                    project_id = project_dir.name
                    try:
                        result = self.sync_project_from_filesystem(project_id, project_dir)
                        if result["success"]:
                            synced_projects.append(project_id)
                        else:
                            failed_projects.append({"project_id": project_id, "error": result.get("error")})
                    except Exception as e:
                        logger.error(f"同步项目 {project_id} 失败: {str(e)}")
                        failed_projects.append({"project_id": project_id, "error": str(e)})
            
            logger.info(f"同步完成: 成功 {len(synced_projects)} 个, 失败 {len(failed_projects)} 个")
            
            return {
                "success": True,
                "synced_projects": synced_projects,
                "failed_projects": failed_projects,
                "total_synced": len(synced_projects),
                "total_failed": len(failed_projects)
            }
            
        except Exception as e:
            logger.error(f"同步所有项目失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def sync_project_from_filesystem(self, project_id: str, project_dir: Path) -> Dict[str, Any]:
        """
        从文件系统同步单个项目到数据库
        
        Args:
            project_id: 项目ID
            project_dir: 项目目录路径
            
        Returns:
            同步结果字典
        """
        try:
            logger.info(f"开始同步项目: {project_id}")
            
            # 检查项目是否已存在于数据库
            existing_project = self.db.query(Project).filter(Project.id == project_id).first()
            if existing_project:
                logger.info(f"项目 {project_id} 已存在于数据库，继续同步切片数据")
            else:
                # 读取项目元数据
                project_metadata = self._read_project_metadata(project_dir)
                if not project_metadata:
                    logger.warning(f"项目 {project_id} 没有元数据文件，创建基础项目记录")
                    project_metadata = {
                        "project_name": f"项目_{project_id[:8]}",
                        "created_at": datetime.now().isoformat(),
                        "status": "pending"
                    }
                
                # 创建项目记录
                project = Project(
                    id=project_id,
                    name=project_metadata.get("project_name", f"项目_{project_id[:8]}"),
                    description=project_metadata.get("description", ""),
                    project_type=ProjectType.KNOWLEDGE,  # 默认类型
                    status=ProjectStatus.PENDING,
                    processing_config=project_metadata.get("processing_config", {}),
                    project_metadata=project_metadata
                )
                
                self.db.add(project)
                self.db.commit()
                self.db.refresh(project)
                
                logger.info(f"项目 {project_id} 同步到数据库成功")
            
            # 同步切片数据
            clips_count = self._sync_clips_from_filesystem(project_id, project_dir)
            
            # 同步AI处理结果到processing_config
            self._sync_ai_processing_results(project_id, project_dir)
            
            # 检查项目是否已完成处理，更新项目状态
            self._update_project_status_if_completed(project_id, project_dir)
            
            return {
                "success": True,
                "project_id": project_id,
                "clips_synced": clips_count
            }
            
        except Exception as e:
            logger.error(f"同步项目 {project_id} 失败: {str(e)}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
    
    def _update_project_status_if_completed(self, project_id: str, project_dir: Path):
        """
        检查项目是否已完成处理，如果是则更新状态为completed
        
        Args:
            project_id: 项目ID
            project_dir: 项目目录路径
        """
        try:
            # 检查是否有step5_video_output.json文件，这是处理完成的标志
            step5_output_file = project_dir / "output" / "step5_video_output.json"
            
            if step5_output_file.exists():
                # 获取项目记录
                project = self.db.query(Project).filter(Project.id == project_id).first()
                if project and project.status != ProjectStatus.COMPLETED:
                    # 读取step5输出文件获取统计信息
                    try:
                        with open(step5_output_file, 'r', encoding='utf-8') as f:
                            step5_output = json.load(f)
                        
                        # 更新项目状态和统计信息
                        project.status = ProjectStatus.COMPLETED
                        project.total_clips = step5_output.get("clips_count", 0)
                        project.completed_at = datetime.now()
                        
                        self.db.commit()
                        logger.info(f"项目 {project_id} 状态已更新为已完成，切片数: {project.total_clips}")
                        
                    except Exception as e:
                        logger.error(f"读取step5输出文件失败: {e}")
                        # 即使读取失败，也标记为已完成
                        project.status = ProjectStatus.COMPLETED
                        project.completed_at = datetime.now()
                        self.db.commit()
                        logger.info(f"项目 {project_id} 状态已更新为已完成（无统计信息）")
                        
        except Exception as e:
            logger.error(f"更新项目状态失败: {e}")
