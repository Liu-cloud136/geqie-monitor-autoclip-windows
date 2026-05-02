"""
项目清理模块
提供项目删除和清理功能
"""

import logging
import shutil
from typing import Dict, Any, Optional
from pathlib import Path

from core.logging_config import get_logger
from models.project import Project
from models.task import Task
from models.clip import Clip
from services.exceptions import FileOperationError

logger = get_logger(__name__)


class ProjectCleanupMixin:
    """
    项目清理混合类
    提供项目删除和清理功能
    """
    
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
