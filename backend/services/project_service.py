"""
项目服务
提供项目相关的业务逻辑操作
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

logger = get_logger(__name__)


class ProjectService(BaseService[Project, ProjectCreate, ProjectUpdate, ProjectResponse]):
    """Project service with business logic."""
    
    def __init__(self, db: Session):
        repository = ProjectRepository(db)
        super().__init__(repository)
        self.db = db
    
    def create_project(self, project_data: ProjectCreate) -> Project:
        """Create a new project with business logic."""
        # Convert Pydantic schema to dict for repository
        project_dict = project_data.model_dump()
        
        # Map Pydantic fields to ORM fields
        orm_data = {
            "name": project_dict["name"],
            "description": project_dict.get("description"),
            "project_type": project_dict.get("project_type", "default").value if hasattr(project_dict.get("project_type", "default"), 'value') else project_dict.get("project_type", "default"),  # Map project_type to project_type
            "video_path": project_dict.get("source_file"),  # Map source_file to video_path
            "processing_config": project_dict.get("settings", {}),  # Map settings to processing_config
            "project_metadata": {"source_url": project_dict.get("source_url")}  # Map source_url to metadata
        }
        
        return self.create(**orm_data)
    
    def update_project(self, project_id: str, project_data: ProjectUpdate) -> Optional[Project]:
        """Update a project with business logic."""
        # Filter out None values
        update_data = {k: v for k, v in project_data.model_dump().items() if v is not None}
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
    
    def get_project_with_stats(self, project_id: str) -> Optional[ProjectResponse]:
        """Get project with statistics."""
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
            "project_type": ProjectType(getattr(project, 'project_type').value) if hasattr(project, 'project_type') and getattr(project, 'project_type', None) is not None else ProjectType.DEFAULT,
            "status": getattr(project, 'status', ProjectStatus.PENDING),
            "source_url": project.project_metadata.get("source_url") if getattr(project, 'project_metadata', None) else None,
            "source_file": str(getattr(project, 'video_path', '')) if getattr(project, 'video_path', None) is not None else None,
            "video_path": str(getattr(project, 'video_path', '')) if getattr(project, 'video_path', None) is not None else None,  # 添加video_path字段供前端使用
            "thumbnail": getattr(project, 'thumbnail', None),  # 从数据库获取缩略图
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

        return ProjectResponse(**response_data)
    
    def get_projects_paginated(
        self, 
        pagination: PaginationParams,
        filters: Optional[ProjectFilter] = None
    ) -> ProjectListResponse:
        """Get paginated projects with filtering.
        
        优化版本：使用批量查询消除N+1问题，将2N+1次查询减少为3次查询。
        """
        filter_dict = {}
        if filters:
            filter_data = filters.model_dump()
            filter_dict = {k: v for k, v in filter_data.items() if v is not None}
        
        items, pagination_response = self.get_paginated(pagination, filter_dict)
        
        if not items:
            return ProjectListResponse(items=[], pagination=pagination_response)
        
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
            
            project_responses.append(ProjectResponse(
                id=str(getattr(project, 'id', '')),
                name=str(getattr(project, 'name', '')),
                description=str(getattr(project, 'description', '')) if getattr(project, 'description', None) is not None else None,
                project_type=ProjectType(getattr(project, 'project_type').value) if hasattr(project, 'project_type') and getattr(project, 'project_type', None) is not None else ProjectType.DEFAULT,
                status=ProjectStatus(getattr(project, 'status').value) if hasattr(project, 'status') and getattr(project, 'status', None) is not None else ProjectStatus.PENDING,
                source_url=project.project_metadata.get("source_url") if getattr(project, 'project_metadata', None) else None,
                source_file=str(getattr(project, 'video_path', '')) if getattr(project, 'video_path', None) is not None else None,
                video_path=str(getattr(project, 'video_path', '')) if getattr(project, 'video_path', None) is not None else None,
                thumbnail=getattr(project, 'thumbnail', None),
                settings=getattr(project, 'processing_config', {}) or {},
                created_at=self._convert_utc_to_local(getattr(project, 'created_at', None)),
                updated_at=self._convert_utc_to_local(getattr(project, 'updated_at', None)),
                completed_at=self._convert_utc_to_local(getattr(project, 'completed_at', None)),
                total_clips=total_clips,
                total_tasks=total_tasks
            ))
        
        return ProjectListResponse(
            items=project_responses,
            pagination=pagination_response
        )
    
    def start_project_processing(self, project_id: str) -> bool:
        """Start processing a project."""
        project = self.get(project_id)
        if not project or project.status != "pending":
            return False
        
        # Update status to processing
        self.update(project_id, status="processing")
        return True
    
    def complete_project(self, project_id: str) -> bool:
        """Mark project as completed."""
        project = self.get(project_id)
        if not project:
            return False
        
        # Update status and completion time
        from datetime import datetime
        self.update(project_id, status="completed", completed_at=datetime.utcnow())
        return True
    
    def fail_project(self, project_id: str, error_message: str = None) -> bool:
        """Mark project as failed."""
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
        """Update project status."""
        project = self.get(project_id)
        if not project:
            return False
        
        # Update status
        self.update(project_id, status=status)
        return True
    
    def _convert_utc_to_local(self, dt: Optional[datetime]) -> Optional[datetime]:
        """将UTC时间转换为本地时间（SQLite存储时丢失了时区信息）"""
        if dt is None:
            return None
        
        from datetime import timezone
        import pytz
        
        # 由于SQLite存储时丢失了时区信息，我们假设这些时间是UTC时间
        # 将其转换为本地时间
        local_tz = pytz.timezone('Asia/Shanghai')
        utc_time = dt.replace(tzinfo=timezone.utc)
        local_time = utc_time.astimezone(local_tz)
        
        return local_time
    
    def delete_project_with_files(self, project_id: str) -> bool:
        """
        删除项目及其所有相关数据
        
        Args:
            project_id: 项目ID
            
        Returns:
            是否删除成功
        """
        try:
            project = self.get(project_id)
            if not project:
                logger.warning(f"项目 {project_id} 不存在")
                return False
            
            logger.info(f"开始删除项目 {project_id}: {project.name}")
            
            # Always allow deletion regardless of project status
            running_tasks = self.db.query(Task).filter(
                Task.project_id == project_id,
                Task.status == TaskStatus.RUNNING
            ).count()
            
            if running_tasks > 0:
                logger.info(f"项目 {project_id} 有 {running_tasks} 个正在运行的任务，将强制删除")
            
            try:
                task_count = self.db.query(Task).filter(Task.project_id == project_id).delete()
                logger.info(f"删除项目 {project_id} 的 {task_count} 个任务")
                
                clip_count = self.db.query(Clip).filter(Clip.project_id == project_id).delete()
                logger.info(f"删除项目 {project_id} 的 {clip_count} 个切片")
                
                project_deleted = self.db.query(Project).filter(Project.id == project_id).delete()
                logger.info(f"删除项目 {project_id} 记录: {project_deleted} 条")
                
                self.db.commit()
                logger.info(f"数据库事务已提交")
                
                self._delete_project_files(project_id)
                
                self._cleanup_project_progress(project_id)
                
                logger.info(f"项目 {project_id} 删除成功")
                return True
                
            except Exception as e:
                self.db.rollback()
                logger.error(f"删除项目 {project_id} 数据库操作失败: {str(e)}")
                return False
            
        except Exception as e:
            logger.error(f"删除项目 {project_id} 时发生错误: {str(e)}")
            return False
    
    def _delete_project_files(self, project_id: str):
        """
        删除项目相关的文件

        Args:
            project_id: 项目ID
        """
        try:
            from core.path_utils import get_project_directory, get_data_directory, get_project_root

            # 删除项目目录（可能存在于多个位置）
            deleted_dirs = []

            # 1. 检查正确的项目目录 (data/projects/{project_id})
            project_dir = get_project_directory(project_id)
            if project_dir.exists():
                logger.info(f"删除项目目录: {project_dir}")
                shutil.rmtree(project_dir)
                deleted_dirs.append(str(project_dir))
            else:
                logger.info(f"项目目录不存在: {project_dir}")

            # 2. 检查backend/data/projects/{project_id}（旧数据位置）
            project_root = get_project_root()
            legacy_project_dir = project_root / "backend" / "data" / "projects" / project_id
            if legacy_project_dir.exists():
                logger.info(f"删除旧项目目录: {legacy_project_dir}")
                shutil.rmtree(legacy_project_dir)
                deleted_dirs.append(str(legacy_project_dir))
            else:
                logger.info(f"旧项目目录不存在: {legacy_project_dir}")

            # 3. 删除全局切片和合集文件
            data_dir = get_data_directory()
            global_clips_dir = data_dir / "output" / "clips"
            global_collections_dir = data_dir / "output" / "collections"

            deleted_files = []

            if global_clips_dir.exists():
                for clip_file in global_clips_dir.glob(f"*_{project_id}*"):
                    try:
                        clip_file.unlink()
                        deleted_files.append(str(clip_file))
                        logger.info(f"删除全局切片文件: {clip_file}")
                    except Exception as e:
                        logger.error(f"删除全局切片文件失败 {clip_file}: {e}")
                        raise FileOperationError(f"删除全局切片文件失败: {clip_file}", str(clip_file), cause=e)

            if global_collections_dir.exists():
                for collection_file in global_collections_dir.glob(f"*_{project_id}*"):
                    try:
                        collection_file.unlink()
                        deleted_files.append(str(collection_file))
                        logger.info(f"删除全局合集文件: {collection_file}")
                    except Exception as e:
                        logger.error(f"删除全局合集文件失败 {collection_file}: {e}")
                        raise FileOperationError(f"删除全局合集文件失败: {collection_file}", str(collection_file), cause=e)

            # 汇总日志
            logger.info(f"项目 {project_id} 文件删除完成:")
            if deleted_dirs:
                logger.info(f"  - 删除目录: {', '.join(deleted_dirs)}")
            if deleted_files:
                logger.info(f"  - 删除文件: {len(deleted_files)} 个")
            if not deleted_dirs and not deleted_files:
                logger.info(f"  - 未找到需要删除的文件")

        except FileOperationError:
            raise
        except Exception as e:
            logger.error(f"删除项目文件时发生错误: {str(e)}")
            raise FileOperationError(f"删除项目文件失败: {str(e)}", project_id=project_id, cause=e)
    
    def _cleanup_project_progress(self, project_id: str):
        """
        清理项目相关的进度数据
        
        Args:
            project_id: 项目ID
        """
        try:
            # 清理Redis中的进度数据
            try:
                from services.simple_progress import clear_progress
                clear_progress(project_id)
                logger.info(f"清理项目 {project_id} 的Redis进度数据")
            except Exception as e:
                logger.warning(f"清理Redis进度数据失败: {e}")

            # 清理增强进度服务中的缓存
            try:
                from services.unified_progress_service import unified_progress_service
                if project_id in unified_progress_service._service._cache:
                    del unified_progress_service._service._cache[project_id]
                    logger.info(f"清理项目 {project_id} 的内存进度缓存")
            except Exception as e:
                logger.warning(f"清理内存进度缓存失败: {e}")

            # 清理Redis中的Celery任务元数据
            try:
                self._cleanup_celery_task_metadata(project_id)
            except Exception as e:
                logger.warning(f"清理Celery任务元数据失败: {e}")
            
        except Exception as e:
            logger.error(f"清理项目进度数据失败: {str(e)}")
    
    def _cleanup_celery_task_metadata(self, project_id: str):
        """
        清理Redis中的Celery任务元数据
        
        Args:
            project_id: 项目ID
        """
        try:
            import redis
            import json
            from core.config import get_database_url

            # 从配置中获取 Redis URL
            redis_url = None
            try:
                from core.celery_app import celery_app
                redis_url = celery_app.conf.broker_url or celery_app.conf.result_backend
            except:
                pass

            if not redis_url:
                logger.warning(f"无法获取Redis URL，跳过清理Celery任务元数据")
                return

            # 连接 Redis
            r = redis.from_url(redis_url, decode_responses=True)
            
            # 尝试 ping Redis
            try:
                r.ping()
            except Exception as e:
                logger.warning(f"Redis连接失败，跳过清理Celery任务元数据: {e}")
                return

            # 查找并删除该项目相关的任务元数据
            deleted_count = 0
            
            # 查找所有 celery-task-meta-* 键
            task_meta_keys = r.keys('celery-task-meta-*')
            
            for key in task_meta_keys:
                try:
                    task_data = r.get(key)
                    if task_data:
                        # 解析任务数据，检查是否包含该项目ID
                        try:
                            task_info = json.loads(task_data)
                            # 检查结果中是否包含该项目ID
                            result = task_info.get('result', {})
                            if isinstance(result, dict):
                                result_str = json.dumps(result)
                                if project_id in result_str:
                                    r.delete(key)
                                    deleted_count += 1
                                    logger.info(f"已删除任务元数据: {key}")
                        except json.JSONDecodeError:
                            # 如果无法解析JSON，尝试直接在字符串中查找
                            if project_id in task_data:
                                r.delete(key)
                                deleted_count += 1
                                logger.info(f"已删除任务元数据: {key}")
                except Exception as e:
                    logger.warning(f"检查任务元数据 {key} 失败: {e}")

            if deleted_count > 0:
                logger.info(f"共清理 {deleted_count} 个与项目 {project_id} 相关的Celery任务元数据")
            else:
                logger.debug(f"没有找到与项目 {project_id} 相关的Celery任务元数据")

        except Exception as e:
            logger.error(f"清理Celery任务元数据时发生错误: {str(e)}")
            # 不抛出异常，避免影响删除流程

 