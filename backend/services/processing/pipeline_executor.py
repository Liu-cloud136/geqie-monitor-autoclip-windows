"""
流水线执行器模块
提供流水线执行、步骤执行、进度更新等核心功能
"""

import time
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from core.logging_config import get_logger
from services.config_manager import ProcessingStep
from services.exceptions import ProcessingError
from services.unified_progress_service import unified_progress_service, ProgressStage
from services.unified_websocket_service import unified_websocket_service
from models.task import TaskStatus

logger = get_logger(__name__)


class PipelineExecutorMixin:
    """
    流水线执行器混合类
    提供流水线执行、步骤执行、进度更新等核心功能
    """
    
    def _update_task_status(self, status: TaskStatus, progress: Optional[float] = None, 
                           error_message: Optional[str] = None, result: Optional[Dict] = None,
                           current_step: Optional[int] = None):
        """
        更新任务状态
        
        Args:
            status: 任务状态
            progress: 进度百分比
            error_message: 错误信息
            result: 结果数据
            current_step: 当前步骤编号
        """
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
        
        # 更新unified_progress_service中的进度信息
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
            from .async_utils import run_async_in_sync_context
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
        """
        更新项目状态
        
        Args:
            current_step: 当前步骤编号
            progress: 进度百分比
        """
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
        """
        发送实时进度更新到前端
        
        Args:
            status: 任务状态
            progress: 进度百分比
            error_message: 错误信息
            current_step: 当前步骤编号
        """
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
                from .async_utils import run_async_in_sync_context
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
            from .async_utils import run_async_in_sync_context
            run_async_in_sync_context(self._progress_service.fail_progress(self.project_id, error_msg))
            raise ValueError(f"流水线前置条件验证失败: {error_msg}")
        
        # 验证步骤依赖关系
        self._validate_step_dependencies(steps_to_execute)
        
        # 开始监控任务进度 - 使用异步方法
        from datetime import datetime
        from .async_utils import run_async_in_sync_context
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
            from .async_utils import run_async_in_sync_context
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
            from .async_utils import run_async_in_sync_context
            run_async_in_sync_context(unified_progress_service.fail_progress(self.project_id, "处理失败"))
            logger.info(f"已标记任务失败: {self.task_id}")
            raise
        except Exception as e:
            logger.error(f"流水线执行失败: {e}")
            self._update_task_status(TaskStatus.FAILED, error_message=str(e))
            # 标记任务失败 - 使用异步方法
            from .async_utils import run_async_in_sync_context
            run_async_in_sync_context(unified_progress_service.fail_progress(self.project_id, str(e)))
            logger.info(f"已标记任务失败: {self.task_id}")
            raise ProcessingError(f"流水线执行失败: {e}", cause=e)
    
    def _validate_step_dependencies(self, steps_to_execute: List[ProcessingStep]):
        """
        验证步骤依赖关系
        
        Args:
            steps_to_execute: 要执行的步骤列表
        """
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
    
    def _save_pipeline_results_to_database(self, results: Dict[str, Any]):
        """
        将流水线执行结果保存到数据库
        
        Args:
            results: 流水线执行结果
        """
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
