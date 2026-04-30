"""
批量导入服务
支持并行导入多个视频文件，优化导入性能
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from core.logging_config import get_logger
from services.concurrency_manager import ConcurrencyLimiter
from config.import_config import (
    MAX_CONCURRENT_IMPORTS,
    BATCH_IMPORT_SIZE,
    ENABLE_BATCH_IMPORT_OPTIMIZATION
)

logger = get_logger(__name__)


@dataclass
class ImportTask:
    """导入任务数据类"""
    task_id: str
    video_path: Path
    project_name: str
    project_type: str = "default"
    srt_path: Optional[Path] = None
    danmaku_path: Optional[Path] = None
    status: str = "pending"
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    project_id: Optional[str] = None
    celery_task_id: Optional[str] = None


class BatchImportService:
    """
    批量导入服务
    
    功能：
    1. 并行导入多个视频文件
    2. 限制并发数，避免系统过载
    3. 提供进度跟踪和错误处理
    """
    
    def __init__(self, max_concurrent: int = None):
        """
        初始化批量导入服务
        
        Args:
            max_concurrent: 最大并发导入数，默认使用配置中的 MAX_CONCURRENT_IMPORTS
        """
        self.max_concurrent = max_concurrent or MAX_CONCURRENT_IMPORTS
        self.limiter = ConcurrencyLimiter(max_concurrent=self.max_concurrent)
        self._import_tasks: Dict[str, ImportTask] = {}
        self._lock = threading.RLock()
        self._completed_count = 0
        self._failed_count = 0
        
        logger.info(f"批量导入服务已初始化，最大并发数: {self.max_concurrent}")
    
    def create_import_task(
        self,
        video_path: Path,
        project_name: str,
        project_type: str = "default",
        srt_path: Optional[Path] = None,
        danmaku_path: Optional[Path] = None
    ) -> ImportTask:
        """
        创建导入任务
        
        Args:
            video_path: 视频文件路径
            project_name: 项目名称
            project_type: 项目类型
            srt_path: 字幕文件路径（可选）
            danmaku_path: 弹幕文件路径（可选）
            
        Returns:
            ImportTask 实例
        """
        import uuid
        
        task_id = str(uuid.uuid4())
        task = ImportTask(
            task_id=task_id,
            video_path=video_path,
            project_name=project_name,
            project_type=project_type,
            srt_path=srt_path,
            danmaku_path=danmaku_path
        )
        
        with self._lock:
            self._import_tasks[task_id] = task
        
        logger.info(f"创建导入任务: {task_id} -> {video_path}")
        return task
    
    def _execute_single_import(self, task: ImportTask) -> Dict[str, Any]:
        """
        执行单个导入任务（同步版本）
        
        Args:
            task: 导入任务
            
        Returns:
            执行结果字典
        """
        from sqlalchemy.orm import Session
        from core.database import SessionLocal
        from services.project_service import ProjectService
        from schemas.project import ProjectCreate, ProjectType as SchemaProjectType, ProjectStatus
        from tasks.import_processing import process_import_task
        
        db: Optional[Session] = None
        
        try:
            with self._lock:
                self._import_tasks[task.task_id].status = "processing"
            
            logger.info(f"开始执行导入任务: {task.task_id}")
            
            # 验证视频文件
            if not task.video_path.exists():
                raise ValueError(f"视频文件不存在: {task.video_path}")
            
            # 创建数据库会话
            db = SessionLocal()
            project_service = ProjectService(db)
            
            # 确定项目类型
            try:
                project_type_enum = SchemaProjectType(task.project_type)
            except ValueError:
                project_type_enum = SchemaProjectType.DEFAULT
            
            # 创建项目数据
            project_data = ProjectCreate(
                name=task.project_name,
                description=f"批量导入项目: {task.video_path.name}",
                project_type=project_type_enum,
                status=ProjectStatus.PENDING,
                source_file=str(task.video_path),
                settings={
                    "video_file": task.video_path.name,
                    "subtitle_mode": "ai_generated" if not task.srt_path else "provided",
                    "batch_import": True
                }
            )
            
            # 创建项目
            project = project_service.create_project(project_data)
            project_id = str(project.id)
            
            with self._lock:
                self._import_tasks[task.task_id].project_id = project_id
            
            logger.info(f"项目创建成功: {project_id}")
            
            # 复制视频文件到项目目录（如果需要）
            from core.path_utils import get_project_raw_directory
            raw_dir = get_project_raw_directory(project_id)
            target_video_path = raw_dir / "input.mp4"
            
            if task.video_path != target_video_path:
                import shutil
                logger.info(f"复制视频文件: {task.video_path} -> {target_video_path}")
                shutil.copy2(task.video_path, target_video_path)
            
            # 更新项目的视频路径
            project.video_path = str(target_video_path)
            db.commit()
            
            # 如果有字幕文件，复制到项目目录
            if task.srt_path and task.srt_path.exists():
                target_srt_path = raw_dir / "input.srt"
                if task.srt_path != target_srt_path:
                    shutil.copy2(task.srt_path, target_srt_path)
                logger.info(f"字幕文件已复制: {target_srt_path}")
            else:
                task.srt_path = None
            
            # 提交异步处理任务
            try:
                celery_task = process_import_task.delay(
                    project_id=project_id,
                    video_path=str(target_video_path),
                    srt_file_path=str(task.srt_path) if task.srt_path else None
                )
                
                with self._lock:
                    self._import_tasks[task.task_id].celery_task_id = celery_task.id
                    self._import_tasks[task.task_id].status = "queued"
                
                logger.info(f"异步处理任务已提交: {celery_task.id}")
                
            except Exception as e:
                logger.error(f"提交异步任务失败: {e}")
                # 即使异步任务提交失败，项目也已创建，标记为部分完成
                with self._lock:
                    self._import_tasks[task.task_id].status = "partial"
                    self._import_tasks[task.task_id].error_message = f"异步任务提交失败: {str(e)}"
                
                return {
                    "success": False,
                    "task_id": task.task_id,
                    "project_id": project_id,
                    "error": f"异步任务提交失败: {str(e)}",
                    "partial_success": True
                }
            
            with self._lock:
                self._import_tasks[task.task_id].status = "completed"
                self._completed_count += 1
            
            logger.info(f"导入任务完成: {task.task_id}")
            
            return {
                "success": True,
                "task_id": task.task_id,
                "project_id": project_id,
                "celery_task_id": celery_task.id,
                "video_path": str(target_video_path)
            }
            
        except Exception as e:
            logger.error(f"导入任务失败: {task.task_id}, 错误: {e}")
            
            with self._lock:
                self._import_tasks[task.task_id].status = "failed"
                self._import_tasks[task.task_id].error_message = str(e)
                self._failed_count += 1
            
            return {
                "success": False,
                "task_id": task.task_id,
                "error": str(e)
            }
            
        finally:
            if db:
                try:
                    db.close()
                except:
                    pass
    
    def import_videos_parallel(
        self,
        video_files: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        并行导入多个视频文件
        
        Args:
            video_files: 视频文件列表，每个元素包含:
                - video_path: Path 或 str
                - project_name: str (可选，默认使用文件名)
                - project_type: str (可选)
                - srt_path: Path 或 str (可选)
            progress_callback: 进度回调函数，参数为 (完成数, 总数, 当前任务ID)
            
        Returns:
            导入结果列表
        """
        if not ENABLE_BATCH_IMPORT_OPTIMIZATION:
            logger.warning("批量导入优化已禁用，将使用串行导入")
            return self._import_videos_serial(video_files, progress_callback)
        
        # 创建导入任务
        tasks = []
        for video_info in video_files:
            video_path = Path(video_info["video_path"]) if isinstance(video_info["video_path"], str) else video_info["video_path"]
            project_name = video_info.get("project_name", video_path.stem)
            project_type = video_info.get("project_type", "default")
            srt_path = video_info.get("srt_path")
            if srt_path and isinstance(srt_path, str):
                srt_path = Path(srt_path)
            
            task = self.create_import_task(
                video_path=video_path,
                project_name=project_name,
                project_type=project_type,
                srt_path=srt_path
            )
            tasks.append(task)
        
        total = len(tasks)
        completed = 0
        results = []
        
        logger.info(f"开始并行导入 {total} 个视频，最大并发数: {self.max_concurrent}")
        
        # 使用线程池执行导入任务
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # 提交所有任务
            future_to_task = {
                executor.submit(self._execute_single_import, task): task
                for task in tasks
            }
            
            # 处理完成的任务
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"任务执行异常: {task.task_id}, 错误: {e}")
                    results.append({
                        "success": False,
                        "task_id": task.task_id,
                        "error": str(e)
                    })
                
                completed += 1
                
                if progress_callback:
                    try:
                        progress_callback(completed, total, task.task_id)
                    except Exception as e:
                        logger.error(f"进度回调失败: {e}")
        
        logger.info(f"并行导入完成: 成功 {self._completed_count}, 失败 {self._failed_count}")
        
        return results
    
    def _import_videos_serial(
        self,
        video_files: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        串行导入视频文件（备用方案）
        """
        results = []
        total = len(video_files)
        
        for i, video_info in enumerate(video_files):
            video_path = Path(video_info["video_path"]) if isinstance(video_info["video_path"], str) else video_info["video_path"]
            project_name = video_info.get("project_name", video_path.stem)
            project_type = video_info.get("project_type", "default")
            srt_path = video_info.get("srt_path")
            if srt_path and isinstance(srt_path, str):
                srt_path = Path(srt_path)
            
            task = self.create_import_task(
                video_path=video_path,
                project_name=project_name,
                project_type=project_type,
                srt_path=srt_path
            )
            
            result = self._execute_single_import(task)
            results.append(result)
            
            if progress_callback:
                try:
                    progress_callback(i + 1, total, task.task_id)
                except Exception as e:
                    logger.error(f"进度回调失败: {e}")
        
        return results
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取导入任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态字典或 None
        """
        with self._lock:
            task = self._import_tasks.get(task_id)
            if not task:
                return None
            
            return {
                "task_id": task.task_id,
                "video_path": str(task.video_path),
                "project_name": task.project_name,
                "project_type": task.project_type,
                "status": task.status,
                "error_message": task.error_message,
                "created_at": task.created_at.isoformat(),
                "project_id": task.project_id,
                "celery_task_id": task.celery_task_id
            }
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """
        获取所有导入任务状态
        
        Returns:
            任务状态列表
        """
        with self._lock:
            return [
                {
                    "task_id": task.task_id,
                    "video_path": str(task.video_path),
                    "project_name": task.project_name,
                    "status": task.status,
                    "error_message": task.error_message,
                    "project_id": task.project_id
                }
                for task in self._import_tasks.values()
            ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取批量导入统计信息
        
        Returns:
            统计信息字典
        """
        with self._lock:
            total = len(self._import_tasks)
            pending = sum(1 for t in self._import_tasks.values() if t.status == "pending")
            processing = sum(1 for t in self._import_tasks.values() if t.status == "processing")
            queued = sum(1 for t in self._import_tasks.values() if t.status == "queued")
            completed = sum(1 for t in self._import_tasks.values() if t.status == "completed")
            failed = sum(1 for t in self._import_tasks.values() if t.status == "failed")
            partial = sum(1 for t in self._import_tasks.values() if t.status == "partial")
            
            return {
                "total": total,
                "pending": pending,
                "processing": processing,
                "queued": queued,
                "completed": completed,
                "failed": failed,
                "partial": partial,
                "max_concurrent": self.max_concurrent,
                "batch_size": BATCH_IMPORT_SIZE
            }


# 全局批量导入服务实例
_batch_import_service: Optional[BatchImportService] = None
_service_lock = threading.Lock()


def get_batch_import_service() -> BatchImportService:
    """
    获取全局批量导入服务实例
    
    Returns:
        BatchImportService 实例
    """
    global _batch_import_service
    
    if _batch_import_service is None:
        with _service_lock:
            if _batch_import_service is None:
                _batch_import_service = BatchImportService()
    
    return _batch_import_service
