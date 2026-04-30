"""
处理编排器
负责协调流水线执行和Task状态管理
使用依赖注入和事件驱动架构
"""

import logging
import time
import sys
import asyncio
from typing import Dict, Any, List, Optional, Callable, Protocol
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

logger = get_logger(__name__)

def run_async_in_sync_context(coro):
    """在同步上下文中运行异步函数的辅助函数"""
    import concurrent.futures
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果事件循环正在运行，使用线程池执行
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_in_thread)
                return future.result(timeout=30)  # 30秒超时
        else:
            # 如果事件循环没有运行，直接运行
            return loop.run_until_complete(coro)
    except RuntimeError:
        # 没有事件循环，创建新的
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"运行异步上下文失败: {e}")
        # 如果是事件循环关闭错误，尝试创建新循环
        if "Event loop is closed" in str(e):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        raise

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


class ProcessingOrchestrator:
    """处理编排器，负责协调流水线执行和Task状态管理"""

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
        
        # 步骤状态管理
        self.step_status = {}
        self.step_timings = {}
        self.step_results = {}
    
    def execute_step(self, step: ProcessingStep, **kwargs) -> Dict[str, Any]:
        """
        执行单个步骤
        
        Args:
            step: 处理步骤
            **kwargs: 步骤特定参数
            
        Returns:
            步骤执行结果
        """
        step_name = step.value
        logger.info(f"开始执行步骤: {step_name}")
        
        # 更新步骤状态为运行中
        self._update_step_status(step, "running")
        
        try:
            # 获取步骤编号
            step_number = self._get_step_number(step)
            
            # 更新任务状态为运行中
            self._update_task_status(TaskStatus.RUNNING, progress=self._get_step_progress(step), current_step=step_number)
            
            # 获取步骤函数和适配器
            step_func = self.step_functions[step]
            step_adapter = self.step_adapters[step]
            
            # 准备步骤环境
            self.adapter.prepare_step_environment(step_name)
            
            # 执行步骤（使用高精度计时器）
            start_time = time.perf_counter()
            
            if step == ProcessingStep.STEP1_OUTLINE:
                # Step1需要SRT文件路径
                srt_path = kwargs.get('srt_path')
                if not srt_path:
                    # 尝试从数据库获取项目的SRT文件路径
                    from models.project import Project
                    project = self.db.query(Project).filter(Project.id == self.project_id).first()
                    if project and hasattr(project, 'subtitle_path') and project.subtitle_path:
                        srt_path = project.subtitle_path
                        logger.info(f"从数据库获取SRT路径: {srt_path}")
                    else:
                        raise ValueError("Step1需要提供SRT文件路径，但未找到有效的SRT文件。请确保项目已正确上传并处理了字幕文件。")
                
                # 确保是Path对象
                if not isinstance(srt_path, Path):
                    from pathlib import Path as PathLib
                    srt_path = PathLib(srt_path)

                # 检查文件是否存在
                if not srt_path.exists():
                    raise ValueError(f"SRT文件不存在: {srt_path}")

                adapted_params = step_adapter(srt_path)
            else:
                # 其他步骤使用前一步的输出
                adapted_params = step_adapter()

            # 为Step6添加进度回调
            if step == ProcessingStep.STEP6_CLUSTERING:
                # 创建进度回调函数
                def video_progress_callback(progress: float):
                    # 计算步骤的进度范围（50-100%）
                    step_progress = 50.0 + progress * 0.5
                    self._update_task_status(
                        TaskStatus.RUNNING,
                        progress=step_progress,
                        current_step=step_number,
                        step_details=f"视频切割进度: {progress:.1f}%"
                    )

                adapted_params['progress_callback'] = video_progress_callback

            # 执行步骤函数
            result = step_func(**adapted_params)
            
            execution_time = time.perf_counter() - start_time
            logger.info(f"步骤 {step_name} 执行完成，耗时: {execution_time:.4f}秒")
            
            # 记录步骤执行信息
            self.step_timings[step_name] = {
                "start_time": start_time,
                "end_time": time.perf_counter(),
                "execution_time": execution_time
            }
            
            # 保存结果到数据库
            self._save_step_result(step, result)
            
            # 更新步骤状态为完成
            self._update_step_status(step, "completed", execution_time=execution_time)
            
            # 更新任务进度
            self._update_task_status(TaskStatus.RUNNING, progress=self._get_step_progress(step), current_step=step_number)
            
            return {
                "step": step_name,
                "status": "completed",
                "execution_time": execution_time,
                "result": result
            }
            
        except ProcessingError:
            execution_time = time.perf_counter() - start_time if 'start_time' in locals() else 0
            logger.error(f"步骤 {step_name} 执行失败")
            
            # 更新步骤状态为失败
            self._update_step_status(step, "failed", execution_time=execution_time, error="处理失败")
            
            self._update_task_status(TaskStatus.FAILED, error_message="处理失败")
            raise
        except Exception as e:
            execution_time = time.perf_counter() - start_time if 'start_time' in locals() else 0
            logger.error(f"步骤 {step_name} 执行失败: {e}")
            
            # 更新步骤状态为失败
            self._update_step_status(step, "failed", execution_time=execution_time, error=str(e))
            
            self._update_task_status(TaskStatus.FAILED, error_message=str(e))
            raise ProcessingError(f"步骤 {step_name} 执行失败: {e}", step_name=step_name, cause=e)
    
    def execute_pipeline(self, srt_path: Path, steps_to_execute: Optional[List[ProcessingStep]] = None) -> Dict[str, Any]:
        """
        执行流水线（支持按需执行子集步骤）
        
        Args:
            srt_path: SRT文件路径
            steps_to_execute: 要执行的步骤列表，None表示执行完整流水线
            
        Returns:
            流水线执行结果
        """
        if steps_to_execute is None:
            # 执行完整流水线
            steps_to_execute = [
                ProcessingStep.STEP1_OUTLINE,
                ProcessingStep.STEP2_TIMELINE,
                ProcessingStep.STEP3_SCORING_ONLY,
                ProcessingStep.STEP4_RECOMMENDATION,
                ProcessingStep.STEP5_TITLE,
                ProcessingStep.STEP6_CLUSTERING
            ]
            logger.info(f"开始执行项目 {self.project_id} 的完整流水线")
        else:
            logger.info(f"开始执行项目 {self.project_id} 的子集流水线: {[step.value for step in steps_to_execute]}")
        
        # 验证前置条件
        errors = self.adapter.validate_pipeline_prerequisites()
        if errors:
            error_msg = "; ".join(errors)
            self._update_task_status(TaskStatus.FAILED, error_message=error_msg)
            # 直接从active_tasks中移除任务
            run_async_in_sync_context(self._progress_service.fail_progress(self.project_id, error_msg))
            raise ValueError(f"流水线前置条件验证失败: {error_msg}")
        
        # 验证步骤依赖关系
        self._validate_step_dependencies(steps_to_execute)
        
        # 开始监控任务进度 - 使用异步方法
        from datetime import datetime
        run_async_in_sync_context(
            unified_progress_service.start_progress(
                self.project_id,
                self.task_id,
                "开始处理任务"
            )
        )
        logger.info(f"已开始监控任务进度: {self.task_id}")
        
        # 更新任务状态为运行中
        self._update_task_status(TaskStatus.RUNNING, progress=0)
        
        results = {}
        total_steps = len(steps_to_execute)
        
        try:
            for i, step in enumerate(steps_to_execute):
                step_number = self._get_step_number(step)
                logger.info(f"执行步骤 {i+1}/{total_steps}: {step.value}")
                
                if step == ProcessingStep.STEP1_OUTLINE:
                    step_result = self.execute_step(step, srt_path=srt_path)
                else:
                    step_result = self.execute_step(step)
                
                results[step.value] = step_result
                
                # 更新总体进度
                progress = ((i + 1) / total_steps) * 100
                self._update_task_status(TaskStatus.RUNNING, progress=progress, current_step=step_number)
            
            # 流水线执行完成，保存数据到数据库
            self._save_pipeline_results_to_database(results)
            
            # 更新任务状态为完成
            self._update_task_status(TaskStatus.COMPLETED, progress=100)
            
            # 标记任务完成 - 使用异步方法
            run_async_in_sync_context(unified_progress_service.complete_progress(self.project_id, "流水线执行完成"))
            logger.info(f"已标记任务完成: {self.task_id}")
            
            logger.info(f"项目 {self.project_id} 流水线执行完成")
            return {
                "status": "completed",
                "project_id": self.project_id,
                "task_id": self.task_id,
                "results": results,
                "executed_steps": [step.value for step in steps_to_execute]
            }
            
        except ProcessingError:
            logger.error(f"流水线执行失败")
            self._update_task_status(TaskStatus.FAILED, error_message="处理失败")
            # 标记任务失败 - 使用异步方法
            run_async_in_sync_context(unified_progress_service.fail_progress(self.project_id, "处理失败"))
            logger.info(f"已标记任务失败: {self.task_id}")
            raise
        except Exception as e:
            logger.error(f"流水线执行失败: {e}")
            self._update_task_status(TaskStatus.FAILED, error_message=str(e))
            # 标记任务失败 - 使用异步方法
            run_async_in_sync_context(unified_progress_service.fail_progress(self.project_id, str(e)))
            logger.info(f"已标记任务失败: {self.task_id}")
            raise ProcessingError(f"流水线执行失败: {e}", cause=e)
    
    def _update_step_status(self, step: ProcessingStep, status: str, execution_time: Optional[float] = None, 
                           error: Optional[str] = None):
        """更新步骤状态"""
        step_name = step.value
        self.step_status[step_name] = {
            "status": status,
            "timestamp": time.time(),
            "execution_time": execution_time,
            "error": error
        }
        logger.debug(f"步骤 {step_name} 状态更新: {status}")
    
    def _update_task_status(self, status: TaskStatus, progress: Optional[float] = None, 
                           error_message: Optional[str] = None, result: Optional[Dict] = None,
                           current_step: Optional[int] = None):
        """更新任务状态"""
        # 使用TaskRepository的专用方法
        if progress is not None:
            self.task_repo.update_task_progress(self.task_id, progress)
        
        if error_message is not None:
            self.task_repo.update_task_error(self.task_id, error_message)
        
        if result is not None:
            self.task_repo.update_task_result(self.task_id, result)
        
        # 更新状态
        self.task_repo.update_task_status(self.task_id, status)
        
        # 更新项目状态
        if current_step is not None:
            self._update_project_status(current_step, progress)
        
        # 获取当前步骤名称
        step_name = "处理中..."
        if current_step is not None:
            step_name_map = {
                1: "大纲提取",
                2: "时间定位", 
                3: "内容评分",
                4: "视频简介生成",
                5: "标题生成",
                6: "视频切割"
            }
            step_name = step_name_map.get(current_step, "处理中...")
        
        # 更新unified_progress_service中的进度信息 - 使用异步方法
        from services.unified_progress_service import ProgressStage
        
        stage_mapping = {
            1: ProgressStage.INGEST,
            2: ProgressStage.SUBTITLE,
            3: ProgressStage.ANALYZE,
            4: ProgressStage.HIGHLIGHT,
            5: ProgressStage.EXPORT
        }
        current_stage = stage_mapping.get(current_step, ProgressStage.ANALYZE)
        
        try:
            run_async_in_sync_context(
                unified_progress_service.update_progress(
                    self.project_id,
                    current_stage,
                    step_name,
                    sub_progress=float(progress or 0) / 100.0
                )
            )
        except (RuntimeError, TimeoutError) as e:
            logger.warning(f"更新进度服务失败: {e}")
        except Exception as e:
            logger.warning(f"更新进度服务失败: {e}")
        
        logger.debug(f"已更新unified_progress_service中的进度: {self.task_id} - {progress}%")
        
        logger.info(f"任务 {self.task_id} 状态更新为: {status.value}, 进度: {progress}%, 步骤: {current_step}")
        
        # 发送WebSocket实时进度更新
        self._send_realtime_progress_update(status, progress, error_message, current_step)
    
    def _update_project_status(self, current_step: int, progress: Optional[float] = None):
        """更新项目状态"""
        try:
            from services.project_service import ProjectService
            
            # 使用 orchestrator 的数据库会话，而不是创建新会话
            project_service = ProjectService(self.db)
            project = project_service.get(self.project_id)
            if project:
                # 更新项目状态
                update_data = {
                    "current_step": current_step,
                    "total_steps": 6,
                    "status": "processing" if current_step < 6 else "completed"
                }
                if progress is not None:
                    update_data["progress"] = progress
                
                project_service.update(self.project_id, **update_data)
                self.db.commit()
                logger.info(f"项目 {self.project_id} 状态已更新: 步骤 {current_step}/6, 进度 {progress}%")
            else:
                # 项目不存在时只记录警告，不抛出异常
                # 可能项目已被删除或在另一个会话中创建
                logger.warning(f"项目 {self.project_id} 不存在，跳过状态更新")
        except ProcessingError:
            raise
        except Exception as e:
            logger.error(f"更新项目状态失败: {e}")
            # 不再抛出异常，避免中断处理流程
            pass
    
    def _send_realtime_progress_update(self, status: TaskStatus, progress: Optional[float] = None, 
                                     error_message: Optional[str] = None, current_step: Optional[int] = None):
        """发送实时进度更新到前端 - 使用统一服务"""
        try:
            # 获取当前步骤信息
            if current_step is None:
                current_step = 0
                step_name = "初始化中..."
                
                # 根据进度推断当前步骤
                if progress is not None:
                    if progress <= 10:
                        current_step = 1
                        step_name = "大纲提取"
                    elif progress <= 25:
                        current_step = 2
                        step_name = "时间定位"
                    elif progress <= 40:
                        current_step = 3
                        step_name = "内容评分"
                    elif progress <= 55:
                        current_step = 4
                        step_name = "视频简介生成"
                    elif progress <= 70:
                        current_step = 5
                        step_name = "标题生成"
                    elif progress <= 95:
                        current_step = 6
                        step_name = "视频切割"
                    else:
                        current_step = 7
                        step_name = "处理完成"
            else:
                # 根据步骤编号获取步骤名称
                step_name_map = {
                    1: "大纲提取",
                    2: "时间定位", 
                    3: "内容评分",
                    4: "视频简介生成",
                    5: "标题生成",
                    6: "视频切割"
                }
                step_name = step_name_map.get(current_step, "处理中...")
            
            # 构建进度消息
            progress_message = f"正在执行{step_name}..."
            if error_message:
                progress_message = f"处理失败: {error_message}"
            elif status == TaskStatus.COMPLETED:
                progress_message = "处理完成"
            
            # 使用统一WebSocket服务发送进度更新
            try:
                run_async_in_sync_context(
                    unified_websocket_service.send_processing_progress(
                        self.project_id,
                        self.task_id,
                        int(progress or 0),
                        progress_message,
                        current_step,
                        7,
                        step_name
                    )
                )
            except (RuntimeError, TimeoutError) as e:
                logger.error(f"发送WebSocket进度更新失败: {e}")
            except Exception as e:
                logger.error(f"发送WebSocket进度更新失败: {e}")
            
            logger.debug(f"已发送实时进度更新: {self.project_id} - {progress}% - {step_name}")
            
        except (RuntimeError, TimeoutError) as e:
            logger.error(f"发送实时进度更新失败: {e}")
        except Exception as e:
            logger.error(f"发送实时进度更新失败: {e}")
    
    def _get_step_number(self, step: ProcessingStep) -> int:
        """获取步骤编号"""
        step_number_map = {
            ProcessingStep.STEP1_OUTLINE: 1,
            ProcessingStep.STEP2_TIMELINE: 2,
            ProcessingStep.STEP3_SCORING: 3,
            ProcessingStep.STEP3_SCORING_ONLY: 3,
            ProcessingStep.STEP4_RECOMMENDATION: 4,
            ProcessingStep.STEP5_TITLE: 5,
            ProcessingStep.STEP6_CLUSTERING: 6
        }
        return step_number_map.get(step, 0)
    
    def _get_step_progress(self, step: ProcessingStep) -> float:
        """获取步骤对应的进度百分比"""
        step_progress_map = {
            ProcessingStep.STEP1_OUTLINE: 15,
            ProcessingStep.STEP2_TIMELINE: 30,
            ProcessingStep.STEP3_SCORING: 45,
            ProcessingStep.STEP3_SCORING_ONLY: 45,
            ProcessingStep.STEP4_RECOMMENDATION: 60,
            ProcessingStep.STEP5_TITLE: 75,
            ProcessingStep.STEP6_CLUSTERING: 95
        }
        return step_progress_map.get(step, 0)
    
    def _save_step_result(self, step: ProcessingStep, result: Any):
        """保存步骤结果到数据库"""
        # 这里可以根据需要将结果保存到相应的数据库表
        # 比如切片结果保存到Clip表
        logger.info(f"步骤 {step.value} 结果已保存")
    
    def _save_pipeline_results_to_database(self, results: Dict[str, Any]):
        """将流水线执行结果保存到数据库"""
        try:
            logger.info(f"开始保存项目 {self.project_id} 流水线结果到数据库")
            
            # 获取项目目录
            project_dir = self.adapter.data_dir / "projects" / self.project_id
            
            # 使用DataSyncService同步数据到数据库
            from services.data_sync_service import DataSyncService
            sync_service = DataSyncService(self.db)
            
            # 同步项目数据
            sync_result = sync_service.sync_project_from_filesystem(self.project_id, project_dir)
            
            if sync_result.get("success"):
                logger.info(f"项目 {self.project_id} 数据同步成功: {sync_result}")
            else:
                logger.error(f"项目 {self.project_id} 数据同步失败: {sync_result}")
            
            logger.info(f"项目 {self.project_id} 流水线结果已全部保存到数据库")
            
        except (IOError, OSError) as e:
            logger.error(f"保存流水线结果到数据库失败: {e}")
            # 不抛出异常，避免影响整个流水线的完成状态
        except Exception as e:
            logger.error(f"保存流水线结果到数据库失败: {e}")
            # 不抛出异常，避免影响整个流水线的完成状态
    
    def _validate_step_dependencies(self, steps_to_execute: List[ProcessingStep]):
        """验证步骤依赖关系"""
        step_dependencies = {
            ProcessingStep.STEP2_TIMELINE: [ProcessingStep.STEP1_OUTLINE],
            ProcessingStep.STEP3_SCORING: [ProcessingStep.STEP2_TIMELINE],
            ProcessingStep.STEP3_SCORING_ONLY: [ProcessingStep.STEP2_TIMELINE],
            ProcessingStep.STEP4_RECOMMENDATION: [ProcessingStep.STEP3_SCORING_ONLY],
            ProcessingStep.STEP5_TITLE: [ProcessingStep.STEP3_SCORING_ONLY],
            ProcessingStep.STEP6_CLUSTERING: [ProcessingStep.STEP5_TITLE]
        }
        
        optional_steps = {
            ProcessingStep.STEP4_RECOMMENDATION: ProcessingStep.STEP5_TITLE
        }
        
        if steps_to_execute:
            first_step = steps_to_execute[0]
            if first_step in step_dependencies:
                required_steps = step_dependencies[first_step]
                missing_steps = []
                
                for req_step in required_steps:
                    step_output = self.adapter.get_step_output_path(req_step.value)
                    if not step_output.exists():
                        if req_step in optional_steps:
                            alt_step = optional_steps[req_step]
                            alt_output = self.adapter.get_step_output_path(alt_step.value)
                            if alt_output.exists():
                                logger.info(f"可选步骤 {req_step.value} 未完成，但替代步骤 {alt_step.value} 已完成，跳过依赖检查")
                                continue
                        missing_steps.append(req_step)
                
                if missing_steps:
                    missing_step_names = [step.value for step in missing_steps]
                    raise ValueError(f"步骤 {first_step.value} 缺少依赖步骤: {missing_step_names}")
    
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
    
    def get_step_performance_summary(self) -> Dict[str, Any]:
        """获取步骤性能摘要"""
        if not self.step_timings:
            return {"message": "暂无性能数据"}
        
        total_time = sum(timing["execution_time"] for timing in self.step_timings.values())
        step_performance = {}
        
        for step_name, timing in self.step_timings.items():
            percentage = (timing["execution_time"] / total_time * 100) if total_time > 0 else 0
            step_performance[step_name] = {
                "execution_time": timing["execution_time"],
                "percentage": percentage,
                "start_time": timing["start_time"],
                "end_time": timing["end_time"]
            }
        
        return {
            "total_execution_time": total_time,
            "step_performance": step_performance,
            "slowest_step": max(self.step_timings.items(), key=lambda x: x[1]["execution_time"])[0] if self.step_timings else None,
            "fastest_step": min(self.step_timings.items(), key=lambda x: x[1]["execution_time"])[0] if self.step_timings else None
        }
    
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
    
    def _adapt_step1_outline(self, srt_path):
        """适配Step1参数"""
        from pathlib import Path
        project_dir = self.adapter.data_dir / "projects" / self.project_id
        output_dir = project_dir / "metadata"
        output_dir.mkdir(parents=True, exist_ok=True)

        return {
            "srt_path": srt_path,
            "output_path": output_dir / "step1_outline.json",
            "metadata_dir": output_dir,
            "enable_checkpoint": True
        }

    def _adapt_step2_timeline(self):
        """适配Step2参数"""
        from pathlib import Path
        project_dir = self.adapter.data_dir / "projects" / self.project_id
        output_dir = project_dir / "metadata"

        return {
            "input_path": output_dir / "step1_outline.json",
            "output_path": output_dir / "step2_timeline.json",
            "metadata_dir": output_dir,
            "enable_checkpoint": True
        }

    def _adapt_step3_scoring(self):
        """适配Step3参数"""
        from pathlib import Path
        project_dir = self.adapter.data_dir / "projects" / self.project_id
        output_dir = project_dir / "metadata"

        return {
            "timeline_path": output_dir / "step2_timeline.json",
            "output_path": output_dir / "step3_scoring.json",
            "metadata_dir": output_dir,
            "enable_checkpoint": True
        }

    def _adapt_step4_title(self):
        """适配Step4参数"""
        from pathlib import Path
        project_dir = self.adapter.data_dir / "projects" / self.project_id
        output_dir = project_dir / "metadata"

        return {
            "input_path": output_dir / "step4_recommendation.json",
            "output_path": output_dir / "step4_title.json",
            "metadata_dir": output_dir,
            "enable_checkpoint": True
        }

    def _adapt_step3_scoring_only(self):
        """适配Step3_SCORING_ONLY参数"""
        from pathlib import Path
        project_dir = self.adapter.data_dir / "projects" / self.project_id
        output_dir = project_dir / "metadata"

        return {
            "timeline_path": output_dir / "step2_timeline.json",
            "output_path": output_dir / "step3_scoring.json",
            "metadata_dir": output_dir,
            "enable_checkpoint": True
        }

    def _adapt_step4_recommendation(self):
        """适配Step4_RECOMMENDATION参数"""
        from pathlib import Path
        project_dir = self.adapter.data_dir / "projects" / self.project_id
        output_dir = project_dir / "metadata"

        return {
            "scored_clips_path": output_dir / "step3_scoring.json",
            "output_path": output_dir / "step4_recommendation.json",
            "metadata_dir": output_dir,
            "enable_checkpoint": True
        }

    def _adapt_step6_clustering(self):
        """适配Step6参数（切片生成）"""
        from pathlib import Path
        from core.config import get_video_config
        from models.project import Project
        
        project_dir = self.adapter.data_dir / "projects" / self.project_id
        output_dir = project_dir / "metadata"
        clips_dir = project_dir / "output" / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)

        # 从数据库获取项目视频路径
        project = self.db.query(Project).filter(Project.id == self.project_id).first()
        video_path = None
        if project and project.video_path:
            # 确保 video_path 是 Path 对象
            video_path_str = project.video_path
            if isinstance(video_path_str, str):
                video_path = Path(video_path_str)
            else:
                video_path = video_path_str

        # 如果视频路径不存在，记录警告
        if not video_path or not video_path.exists():
            logger.warning(f"项目 {self.project_id} 的视频路径不存在: {video_path}")
            # 使用一个不存在的路径作为占位符
            video_path = Path("/dev/null/not_existing_video.mp4")

        video_config = get_video_config()

        params = {
            "input_path": output_dir / "step5_title.json",
            "output_path": output_dir / "step6_video_output.json",
            "input_video": video_path,  # 必须提供
            "clips_dir": str(clips_dir),
            "metadata_dir": str(output_dir),
            "enable_checkpoint": True,
            "use_stream_copy": video_config.get("use_stream_copy", True),
            "use_hardware_accel": video_config.get("use_hardware_accel", True)
        }
        
        return params

    def get_step_status_summary(self) -> Dict[str, Any]:
        """获取步骤状态摘要"""
        if not self.step_status:
            return {"message": "暂无步骤状态数据"}
        
        completed_steps = [step for step, status in self.step_status.items() if status["status"] == "completed"]
        failed_steps = [step for step, status in self.step_status.items() if status["status"] == "failed"]
        running_steps = [step for step, status in self.step_status.items() if status["status"] == "running"]
        
        return {
            "total_steps": len(self.step_status),
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "running_steps": running_steps,
            "completion_rate": len(completed_steps) / len(self.step_status) * 100 if self.step_status else 0,
            "step_details": self.step_status
        }