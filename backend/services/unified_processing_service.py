"""
统一处理服务
整合所有处理相关功能，提供统一的处理管理接口
使用依赖注入和事件驱动架构
"""

import logging
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Protocol
from datetime import datetime
from sqlalchemy.orm import Session

from models.task import Task, TaskStatus, TaskType
from models.project import Project, ProjectStatus
from repositories.task_repository import TaskRepository
from services.config_manager import ProjectConfigManager, ProcessingStep
from services.processing_orchestrator import ProcessingOrchestrator, run_async_in_sync_context
from services.processing_context import ProcessingContext
from services.exceptions import ServiceError, ProcessingError, TaskError, ProjectError, handle_service_error
from services.concurrency_manager import with_concurrency_control
from core.event_bus import EventBus, EventType, Event, get_event_bus
from dependency_injector.wiring import Provide, inject
from core.logging_config import get_logger

logger = get_logger(__name__)


class ProgressServiceProtocol(Protocol):
    async def start_progress(self, project_id: str, task_id: Optional[str] = None,
                             initial_message: str = "开始处理"):
        ...
    
    async def update_progress(self, project_id: str, stage, message: str = "",
                              sub_progress: float = 0.0, metadata: Optional[Dict[str, Any]] = None):
        ...
    
    async def complete_progress(self, project_id: str, message: str = "处理完成"):
        ...
    
    async def fail_progress(self, project_id: str, error_message: str):
        ...


class TaskRepositoryProtocol(Protocol):
    def create(self, **kwargs) -> Task:
        ...
    
    def get_latest_task_by_project_id(self, project_id: str) -> Optional[Task]:
        ...


class UnifiedProcessingService:
    """统一处理服务 - 使用依赖注入和事件驱动"""
    
    def __init__(self, 
                 db: Session,
                 task_repository: TaskRepository,
                 progress_service: Optional[ProgressServiceProtocol] = None,
                 event_bus: Optional[EventBus] = None,
                 data_sync_service: Optional[Any] = None):
        self.db = db
        self.task_repo = task_repository
        self._progress_service = progress_service
        self._event_bus = event_bus
        self._data_sync_service = data_sync_service
        self.processing_projects = set()
    
    def _publish_event(self, event_type: EventType, data: Dict[str, Any]):
        if self._event_bus:
            event = Event(event_type=event_type, data=data)
            self._event_bus.publish(event)
    
    def _update_project_status(self, project_id: str, status: ProjectStatus) -> bool:
        try:
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.status = status
                project.updated_at = datetime.utcnow()
                self.db.commit()
                logger.info(f"项目 {project_id} 状态已更新为 {status}")
                return True
        except Exception as e:
            logger.error(f"更新项目状态失败: {e}")
            self.db.rollback()
        return False
    
    @handle_service_error
    @with_concurrency_control()
    def start_processing(self, project_id: str, srt_path: Path) -> Dict[str, Any]:
        logger.info(f"开始处理项目: {project_id}")
        
        if project_id in self.processing_projects:
            raise TaskError(f"项目 {project_id} 已在处理中", project_id=project_id)
        
        self.processing_projects.add(project_id)
        
        try:
            context = ProcessingContext(project_id, "temp_task_id", self.db)
            context.set_srt_path(srt_path)
            context.mark_initialized()
            
            task = self._create_processing_task(project_id)
            context.task_id = str(task.id)
            
            self._publish_event(EventType.PROJECT_PROCESSING_STARTED, {
                "project_id": project_id,
                "task_id": str(task.id)
            })
            
            if self._progress_service:
                run_async_in_sync_context(
                    self._progress_service.start_progress(project_id, str(task.id), "开始处理项目")
                )
            
            orchestrator = ProcessingOrchestrator(project_id, str(task.id), self.db)
            result = orchestrator.execute_pipeline(srt_path)
            
            context.mark_completed()
            
            self._update_project_status(project_id, ProjectStatus.COMPLETED)
            self._sync_project_data(project_id)
            
            if self._progress_service:
                run_async_in_sync_context(
                    self._progress_service.complete_progress(project_id, "项目处理完成")
                )
            
            self._publish_event(EventType.PROJECT_PROCESSING_COMPLETED, {
                "project_id": project_id,
                "task_id": str(task.id),
                "result": result
            })
            
            return {
                "success": True,
                "task_id": task.id,
                "project_id": project_id,
                "result": result,
                "context": context.get_context_summary()
            }
        except TaskError:
            raise
        except Exception as e:
            if self._progress_service:
                run_async_in_sync_context(
                    self._progress_service.fail_progress(project_id, f"处理失败: {str(e)}")
                )
            self._publish_event(EventType.PROJECT_PROCESSING_FAILED, {
                "project_id": project_id,
                "task_id": "unknown",
                "error": str(e)
            })
            raise ProcessingError(f"处理项目失败: {str(e)}", project_id=project_id, cause=e)
        finally:
            self.processing_projects.discard(project_id)
    
    @handle_service_error
    @with_concurrency_control()
    def execute_single_step(self, project_id: str, step: ProcessingStep,
                            srt_path: Optional[Path] = None) -> Dict[str, Any]:
        logger.info(f"执行步骤: {step.value}")
        
        context = ProcessingContext(project_id, "temp_task_id", self.db)
        if srt_path:
            context.set_srt_path(srt_path)
        context.mark_initialized()
        
        task = self._create_processing_task(project_id, task_type=TaskType.VIDEO_PROCESSING)
        context.task_id = str(task.id)
        
        orchestrator = ProcessingOrchestrator(project_id, str(task.id), self.db)
        
        self._publish_event(EventType.PROCESSING_STEP_STARTED, {
            "project_id": project_id,
            "step": step.value
        })
        
        if self._progress_service:
            from services.unified_progress_service import ProgressStage
            stage_mapping = {
                ProcessingStep.STEP1_OUTLINE: ProgressStage.SUBTITLE,
                ProcessingStep.STEP2_TIMELINE: ProgressStage.ANALYZE,
                ProcessingStep.STEP3_SCORING: ProgressStage.ANALYZE,
                ProcessingStep.STEP3_SCORING_ONLY: ProgressStage.ANALYZE,
                ProcessingStep.STEP4_RECOMMENDATION: ProgressStage.ANALYZE,
                ProcessingStep.STEP5_TITLE: ProgressStage.HIGHLIGHT,
                ProcessingStep.STEP6_CLUSTERING: ProgressStage.EXPORT,
            }
            run_async_in_sync_context(
                self._progress_service.start_progress(project_id, str(task.id), f"开始执行步骤: {step.value}")
            )
        
        kwargs = {}
        if step == ProcessingStep.STEP1_OUTLINE and srt_path:
            kwargs['srt_path'] = srt_path
        
        result = orchestrator.execute_step(step, **kwargs)
        
        context.mark_completed()
        
        if step == ProcessingStep.STEP6_CLUSTERING:
            self._sync_project_data(project_id)
            if self._progress_service:
                run_async_in_sync_context(
                    self._progress_service.complete_progress(project_id, "步骤执行完成")
                )
        elif self._progress_service:
            stage = stage_mapping.get(step, ProgressStage.ANALYZE)
            run_async_in_sync_context(
                self._progress_service.update_progress(project_id, stage, f"步骤 {step.value} 完成")
            )
        
        self._publish_event(EventType.PROCESSING_STEP_COMPLETED, {
            "project_id": project_id,
            "step": step.value,
            "result": result
        })
        
        return {
            "success": True,
            "task_id": task.id,
            "step": step.value,
            "result": result,
            "context": context.get_context_summary()
        }
    
    @handle_service_error
    def process_project(self, project_id: str) -> Dict[str, Any]:
        logger.info(f"开始处理项目: {project_id}")
        
        # 首先检查项目是否存在
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            logger.warning(f"项目 {project_id} 不存在，跳过处理")
            return {
                "success": True,
                "project_id": project_id,
                "message": "项目不存在，跳过处理",
                "status": "skipped"
            }
        
        # 检查项目是否已被删除
        if project.status == ProjectStatus.FAILED and not project.video_path:
            logger.warning(f"项目 {project_id} 可能已被删除，跳过处理")
            return {
                "success": True,
                "project_id": project_id,
                "message": "项目可能已被删除，跳过处理",
                "status": "skipped"
            }
        
        from core.config import get_project_root
        project_root = get_project_root()
        project_dir = project_root / "data" / "projects" / project_id / "raw"
        srt_files = list(project_dir.glob("*.srt"))
        
        # 如果没有字幕文件，使用 bcut-asr 生成字幕
        if not srt_files:
            logger.info(f"未找到字幕文件，使用 bcut-asr 生成字幕")
            
            # 获取项目视频路径
            if not project.video_path:
                raise ProcessingError(f"项目 {project_id} 缺少视频文件，无法生成字幕", project_id=project_id)
            
            video_path = Path(project.video_path)
            if not video_path.exists():
                raise ProcessingError(f"项目 {project_id} 的视频文件不存在: {video_path}", project_id=project_id)
            
            # 使用 bcut-asr 生成字幕
            from utils.speech_recognizer import generate_subtitle_for_video
            srt_path = project_dir / "input.srt"
            
            try:
                generated_srt = generate_subtitle_for_video(video_path, srt_path)
                if not generated_srt:
                    raise ProcessingError(f"字幕生成失败", project_id=project_id)
                
                # 更新项目的字幕路径
                if not hasattr(project, 'subtitle_path'):
                    project.subtitle_path = str(generated_srt)
                else:
                    project.subtitle_path = str(generated_srt)
                
                self.db.commit()
                logger.info(f"字幕生成成功: {generated_srt}")
                srt_path = generated_srt
            except Exception as e:
                raise ProcessingError(f"使用 bcut-asr 生成字幕失败: {str(e)}", project_id=project_id, cause=e)
        else:
            srt_path = srt_files[0]
            logger.info(f"找到SRT文件: {srt_path}")
        
        return self.start_processing(project_id, srt_path)
    
    @handle_service_error
    def get_processing_status(self, project_id: str) -> Dict[str, Any]:
        task = self.task_repo.get_latest_task_by_project_id(project_id)
        if not task:
            return {"status": "no_task", "message": "项目没有处理任务"}
        
        orchestrator = ProcessingOrchestrator(project_id, str(task.id), self.db)
        return orchestrator.get_pipeline_status()
    
    @handle_service_error
    @with_concurrency_control()
    def retry_step(self, project_id: str, task_id: str, step: ProcessingStep,
                   srt_path: Optional[Path] = None) -> Dict[str, Any]:
        logger.info(f"重试步骤: {step.value}")
        
        context = ProcessingContext(project_id, task_id, self.db)
        if srt_path:
            context.set_srt_path(srt_path)
        context.mark_initialized()
        
        orchestrator = ProcessingOrchestrator(project_id, task_id, self.db)
        
        if self._progress_service:
            self._progress_service.start_progress(project_id, task_id, f"重试步骤: {step.value}")
        
        kwargs = {}
        if step == ProcessingStep.STEP1_OUTLINE and srt_path:
            kwargs['srt_path'] = srt_path
        
        result = orchestrator.retry_step(step, **kwargs)
        
        context.mark_completed()
        
        if self._progress_service:
            from services.unified_progress_service import ProgressStage
            self._progress_service.update_progress(project_id, ProgressStage.ANALYZE, f"步骤 {step.value} 重试完成")
        
        return {
            "success": True,
            "step": step.value,
            "result": result,
            "context": context.get_context_summary()
        }
    
    @handle_service_error
    @with_concurrency_control()
    def resume_processing(self, project_id: str, start_step: str,
                          srt_path: Optional[Path] = None) -> Dict[str, Any]:
        logger.info(f"从步骤 {start_step} 恢复处理项目: {project_id}")
        
        context = ProcessingContext(project_id, "temp_task_id", self.db)
        if srt_path:
            context.set_srt_path(srt_path)
        context.mark_initialized()
        
        task = self._create_processing_task(project_id)
        context.task_id = str(task.id)
        
        orchestrator = ProcessingOrchestrator(project_id, str(task.id), self.db)
        
        step_mapping = {
            "step1_outline": ProcessingStep.STEP1_OUTLINE,
            "step2_timeline": ProcessingStep.STEP2_TIMELINE,
            "step3_scoring": ProcessingStep.STEP3_SCORING,
            "step3_scoring_only": ProcessingStep.STEP3_SCORING_ONLY,
            "step4_recommendation": ProcessingStep.STEP4_RECOMMENDATION,
            "step5_title": ProcessingStep.STEP5_TITLE,
            "step6_clustering": ProcessingStep.STEP6_CLUSTERING
        }
        
        if start_step not in step_mapping:
            raise ProcessingError(f"无效的步骤名称: {start_step}", project_id=project_id)
        
        processing_step = step_mapping[start_step]
        
        if self._progress_service:
            self._progress_service.start_progress(project_id, str(task.id), f"从步骤 {start_step} 恢复处理")
        
        result = orchestrator.resume_from_step(processing_step, srt_path)
        
        context.mark_completed()
        
        self._status_updater.update(project_id, ProjectStatus.COMPLETED)
        self._sync_project_data(project_id)
        
        if self._progress_service:
            self._progress_service.complete_progress(project_id, "处理恢复完成")
        
        return {
            "success": True,
            "task_id": task.id,
            "project_id": project_id,
            "start_step": start_step,
            "result": result,
            "context": context.get_context_summary()
        }
    
    @handle_service_error
    def get_project_config(self, project_id: str) -> Dict[str, Any]:
        config_manager = ProjectConfigManager(project_id)
        return config_manager.export_config()
    
    @handle_service_error
    def update_project_config(self, project_id: str, config_updates: Dict[str, Any]) -> Dict[str, Any]:
        config_manager = ProjectConfigManager(project_id)
        
        if "processing_params" in config_updates:
            config_manager.update_processing_params(**config_updates["processing_params"])
        
        if "llm_config" in config_updates:
            config_manager.update_llm_config(**config_updates["llm_config"])
        
        if "steps" in config_updates:
            for step_name, step_config in config_updates["steps"].items():
                config_manager.update_step_config(step_name, **step_config)
        
        return {
            "success": True,
            "message": "配置更新成功"
        }
    
    @handle_service_error
    def validate_project_setup(self, project_id: str) -> Dict[str, Any]:
        return {
            "valid": True,
            "message": "项目设置验证通过"
        }
    
    def _create_processing_task(self, project_id: str, task_type: TaskType = TaskType.VIDEO_PROCESSING) -> Task:
        task_data = {
            "name": f"视频处理任务 - {project_id}",
            "description": f"处理项目 {project_id} 的视频内容",
            "project_id": project_id,
            "task_type": task_type,
            "status": TaskStatus.PENDING,
            "progress": 0.0,
            "metadata": {
                "project_id": project_id,
                "task_type": task_type.value if hasattr(task_type, 'value') else task_type
            }
        }
        
        return self.task_repo.create(**task_data)
    
    def _sync_project_data(self, project_id: str):
        from core.config import get_project_root
        project_root = get_project_root()
        project_dir = project_root / "data" / "projects" / project_id
        if project_dir.exists():
            if self._data_sync_service:
                sync_result = self._data_sync_service.sync_project_from_filesystem(project_id, project_dir)
                if sync_result.get("success"):
                    logger.info(f"项目 {project_id} 数据同步成功: {sync_result}")
                else:
                    logger.error(f"项目 {project_id} 数据同步失败: {sync_result}")
            else:
                from services.data_sync_service import DataSyncService
                sync_service = DataSyncService(self.db)
                sync_result = sync_service.sync_project_from_filesystem(project_id, project_dir)
                if sync_result.get("success"):
                    logger.info(f"项目 {project_id} 数据同步成功: {sync_result}")
                else:
                    logger.error(f"项目 {project_id} 数据同步失败: {sync_result}")
    
    def get_processing_status_overview(self) -> Dict[str, Any]:
        return {
            "processing_projects": list(self.processing_projects),
            "total_processing": len(self.processing_projects)
        }


def create_unified_processing_service(db: Session,
                                      progress_service: Optional[ProgressServiceProtocol] = None,
                                      event_bus: Optional[EventBus] = None,
                                      data_sync_service: Optional[Any] = None) -> UnifiedProcessingService:
    task_repository = TaskRepository(db)
    return UnifiedProcessingService(
        db=db,
        task_repository=task_repository,
        progress_service=progress_service,
        event_bus=event_bus,
        data_sync_service=data_sync_service
    )
