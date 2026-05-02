"""
处理编排器
负责协调流水线执行和Task状态管理
使用依赖注入和事件驱动架构

重构说明：
- 核心逻辑已拆分到 services/processing/ 目录下的多个模块中
- 本文件保持向后兼容，作为统一入口点
"""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from sqlalchemy.orm import Session

from models.task import Task, TaskStatus, TaskType
from repositories.task_repository import TaskRepository
from services.config_manager import ProjectConfigManager, ProcessingStep
from services.unified_progress_service import unified_progress_service, ProgressStage
from services.unified_websocket_service import unified_websocket_service
from services.exceptions import ProcessingError, TaskError, SystemError
from core.event_bus import EventBus, EventType, Event, get_event_bus
from core.unified_config import get_project_root
from core.logging_config import get_logger

# 导入拆分后的模块
from .processing.async_utils import run_async_in_sync_context
from .processing.step_adapters import StepAdaptersMixin
from .processing.pipeline_executor import PipelineExecutorMixin
from .processing.status_manager import StatusManagerMixin

logger = get_logger(__name__)

# 导入流水线步骤
PIPELINE_MODULES_AVAILABLE = False

try:
    from pipeline.step1_outline import run_step1_outline
    from pipeline.step2_timeline import run_step2_timeline
    from pipeline.step3_scoring import run_step3_scoring
    from pipeline.step3_scoring_only import run_step3_scoring_only
    from pipeline.step4_recommendation import run_step4_recommendation
    from pipeline.step4_title import run_step4_title
    from pipeline.step5_video import run_step5_video
    PIPELINE_MODULES_AVAILABLE = True
    logger.info("流水线模块导入成功")
except ImportError as e:
    logger.error(f"无法导入流水线模块: {e}")
    raise ImportError(
        "Pipeline modules not found. Please ensure all pipeline steps are properly installed "
        "and the pipeline directory structure is correct.\n"
        f"Error details: {e}"
    )


class ProcessingOrchestrator(StepAdaptersMixin, PipelineExecutorMixin, StatusManagerMixin):
    """
    处理编排器，负责协调流水线执行和Task状态管理
    
    重构说明：
    - 使用混合类（Mixin）模式组织代码
    - StepAdaptersMixin: 提供步骤参数适配功能
    - PipelineExecutorMixin: 提供流水线执行核心功能
    - StatusManagerMixin: 提供状态管理功能
    """

    def __init__(self, project_id: str, task_id: str, db: Session,
                 progress_service=None, websocket_service=None, event_bus=None):
        if not PIPELINE_MODULES_AVAILABLE:
            raise RuntimeError(
                "Pipeline modules are not available. Cannot process video. "
                "Please ensure all pipeline steps are properly installed."
            )

        self.project_id = project_id
        self.task_id = task_id
        self.db = db
        
        self._progress_service = progress_service or unified_progress_service
        self._websocket_service = websocket_service or unified_websocket_service
        self._event_bus = event_bus

        self.config_manager = ProjectConfigManager(project_id)
        self.adapter = self._create_simple_adapter()
        self.task_repo = TaskRepository(db)

        # 步骤映射
        self.step_functions = {
            ProcessingStep.STEP1_OUTLINE: run_step1_outline,
            ProcessingStep.STEP2_TIMELINE: run_step2_timeline,
            ProcessingStep.STEP3_SCORING: run_step3_scoring,
            ProcessingStep.STEP3_SCORING_ONLY: run_step3_scoring_only,
            ProcessingStep.STEP4_RECOMMENDATION: run_step4_recommendation,
            ProcessingStep.STEP5_TITLE: run_step4_title,
            ProcessingStep.STEP6_CLUSTERING: run_step5_video,
        }

        # 步骤适配器映射
        self.step_adapters = {
            ProcessingStep.STEP1_OUTLINE: self._adapt_step1_outline,
            ProcessingStep.STEP2_TIMELINE: self._adapt_step2_timeline,
            ProcessingStep.STEP3_SCORING: self._adapt_step3_scoring,
            ProcessingStep.STEP3_SCORING_ONLY: self._adapt_step3_scoring_only,
            ProcessingStep.STEP4_RECOMMENDATION: self._adapt_step4_recommendation,
            ProcessingStep.STEP5_TITLE: self._adapt_step4_title,
            ProcessingStep.STEP6_CLUSTERING: self._adapt_step6_clustering
        }
        
        # 初始化状态管理
        self._init_status_management()
    
    def _create_simple_adapter(self):
        """创建一个简单的适配器替代实现"""
        class SimpleAdapter:
            def __init__(self, project_id):
                self.project_id = project_id
                from pathlib import Path
                from core.config import get_project_root
                project_root = get_project_root()
                self.data_dir = project_root / "data"
            
            def prepare_step_environment(self, step_name):
                """准备步骤环境"""
                pass
            
            def validate_pipeline_prerequisites(self):
                """验证流水线前置条件"""
                return []
            
            def get_step_output_path(self, step_name):
                """获取步骤输出路径"""
                from pathlib import Path
                step_file_map = {
                    "step1_outline": ("metadata", "step1_outline.json"),
                    "step2_timeline": ("metadata", "step2_timeline.json"),
                    "step3_scoring": ("metadata", "step3_only_high_score_clips.json"),
                    "step3_scoring_only": ("metadata", "step3_only_high_score_clips.json"),
                    "step4_recommendation": ("metadata", "step4_with_recommendations.json"),
                    "step5_title": ("metadata", "step4_titles.json"),
                    "step6_clustering": ("output", "step5_video_output.json")
                }
                if step_name in step_file_map:
                    dir_name, file_name = step_file_map[step_name]
                else:
                    dir_name, file_name = "metadata", f"{step_name}.json"
                return self.data_dir / "projects" / self.project_id / dir_name / file_name
            
            def cleanup_intermediate_files(self, step_name):
                """清理中间文件"""
                pass
            
            def get_step_result(self, step_name):
                """获取步骤结果"""
                return {}
        
        return SimpleAdapter(self.project_id)
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """获取流水线状态"""
        task = self.task_repo.get_by_id(self.task_id)
        if not task:
            return {"error": "任务不存在"}
        
        return {
            "task_id": self.task_id,
            "project_id": self.project_id,
            "task_status": task.status.value,
            "task_progress": task.progress,
            "error_message": task.error_message,
            "step_status": self.step_status,
            "step_timings": self.step_timings,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None
        }
    
    def retry_step(self, step: ProcessingStep, **kwargs) -> Dict[str, Any]:
        """重试特定步骤"""
        logger.info(f"重试步骤: {step.value}")
        
        # 清理步骤的中间文件
        self.adapter.cleanup_intermediate_files(step.value)
        
        # 重新执行步骤
        return self.execute_step(step, **kwargs)
    
    def get_step_result(self, step: ProcessingStep) -> Any:
        """获取步骤结果"""
        return self.adapter.get_step_result(step.value)
    
    def resume_from_step(self, start_step: ProcessingStep, srt_path: Optional[Path] = None) -> Dict[str, Any]:
        """从指定步骤恢复执行"""
        logger.info(f"从步骤 {start_step.value} 恢复执行")
        
        # 获取从指定步骤开始的所有步骤
        all_steps = [
            ProcessingStep.STEP1_OUTLINE,
            ProcessingStep.STEP2_TIMELINE,
            ProcessingStep.STEP3_SCORING_ONLY,
            ProcessingStep.STEP4_RECOMMENDATION,
            ProcessingStep.STEP5_TITLE,
            ProcessingStep.STEP6_CLUSTERING
        ]
        
        try:
            start_index = all_steps.index(start_step)
            
            # 只执行未完成的步骤
            steps_to_execute = []
            for step in all_steps[start_index:]:
                step_output = self.adapter.get_step_output_path(step.value)
                if not step_output.exists():
                    steps_to_execute.append(step)
                else:
                    logger.info(f"步骤 {step.value} 已完成，跳过")
            
            if not steps_to_execute:
                logger.info("所有步骤都已完成，无需执行")
                return {"message": "所有步骤都已完成"}
            
            logger.info(f"将执行步骤: {[step.value for step in steps_to_execute]}")
            
            if start_step == ProcessingStep.STEP1_OUTLINE:
                if not srt_path:
                    raise ValueError("从Step1恢复需要提供SRT文件路径")
                return self.execute_pipeline(srt_path, steps_to_execute)
            else:
                # 验证前置步骤是否已完成
                for step in all_steps[:start_index]:
                    step_output = self.adapter.get_step_output_path(step.value)
                    if not step_output.exists():
                        raise ValueError(f"前置步骤 {step.value} 未完成，无法从 {start_step.value} 恢复")
                
                return self.execute_pipeline(Path("dummy.srt"), steps_to_execute)
                
        except ValueError as e:
            logger.error(f"恢复执行失败: {e}")
            raise


# 导出向后兼容的函数和类
__all__ = [
    'ProcessingOrchestrator',
    'run_async_in_sync_context',
    'PIPELINE_MODULES_AVAILABLE',
]
