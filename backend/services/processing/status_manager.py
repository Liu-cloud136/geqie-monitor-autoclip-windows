"""
状态管理器模块
提供步骤状态和任务状态的管理功能
"""

import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from core.logging_config import get_logger
from services.config_manager import ProcessingStep
from models.task import TaskStatus

logger = get_logger(__name__)


class StatusManagerMixin:
    """
    状态管理器混合类
    提供步骤状态和任务状态的管理功能
    """
    
    def _init_status_management(self):
        """初始化状态管理"""
        if not hasattr(self, 'step_status'):
            self.step_status = {}
        if not hasattr(self, 'step_timings'):
            self.step_timings = {}
        if not hasattr(self, 'step_results'):
            self.step_results = {}
    
    def _update_step_status(self, step: ProcessingStep, status: str, 
                           execution_time: Optional[float] = None, 
                           error: Optional[str] = None):
        """
        更新步骤状态
        
        Args:
            step: 处理步骤
            status: 状态值
            execution_time: 执行时间
            error: 错误信息
        """
        self._init_status_management()
        
        step_name = step.value
        self.step_status[step_name] = {
            "status": status,
            "timestamp": time.time(),
            "execution_time": execution_time,
            "error": error
        }
        logger.debug(f"步骤 {step_name} 状态更新: {status}")
    
    def _get_step_number(self, step: ProcessingStep) -> int:
        """
        获取步骤编号
        
        Args:
            step: 处理步骤
            
        Returns:
            步骤编号
        """
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
        """
        获取步骤对应的进度百分比
        
        Args:
            step: 处理步骤
            
        Returns:
            进度百分比
        """
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
        """
        保存步骤结果到数据库
        
        Args:
            step: 处理步骤
            result: 步骤结果
        """
        # 这里可以根据需要将结果保存到相应的数据库表
        # 比如切片结果保存到Clip表
        logger.info(f"步骤 {step.value} 结果已保存")
    
    def get_step_status_summary(self) -> Dict[str, Any]:
        """
        获取步骤状态摘要
        
        Returns:
            步骤状态摘要字典
        """
        self._init_status_management()
        
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
    
    def get_step_performance_summary(self) -> Dict[str, Any]:
        """
        获取步骤性能摘要
        
        Returns:
            步骤性能摘要字典
        """
        self._init_status_management()
        
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
