"""
步骤适配器模块
提供流水线步骤的参数适配功能
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from core.logging_config import get_logger
from core.config import get_video_config
from services.config_manager import ProcessingStep

logger = get_logger(__name__)


class StepAdaptersMixin:
    """
    步骤适配器混合类
    提供流水线步骤的参数适配功能
    """
    
    def _adapt_step1_outline(self, srt_path: Path) -> Dict[str, Any]:
        """
        适配Step1参数
        
        Args:
            srt_path: SRT文件路径
            
        Returns:
            适配后的参数字典
        """
        project_dir = self.adapter.data_dir / "projects" / self.project_id
        output_dir = project_dir / "metadata"
        output_dir.mkdir(parents=True, exist_ok=True)

        return {
            "srt_path": srt_path,
            "output_path": output_dir / "step1_outline.json",
            "metadata_dir": output_dir,
            "enable_checkpoint": True
        }

    def _adapt_step2_timeline(self) -> Dict[str, Any]:
        """
        适配Step2参数
        
        Returns:
            适配后的参数字典
        """
        project_dir = self.adapter.data_dir / "projects" / self.project_id
        output_dir = project_dir / "metadata"

        return {
            "input_path": output_dir / "step1_outline.json",
            "output_path": output_dir / "step2_timeline.json",
            "metadata_dir": output_dir,
            "enable_checkpoint": True
        }

    def _adapt_step3_scoring(self) -> Dict[str, Any]:
        """
        适配Step3参数
        
        Returns:
            适配后的参数字典
        """
        project_dir = self.adapter.data_dir / "projects" / self.project_id
        output_dir = project_dir / "metadata"

        return {
            "timeline_path": output_dir / "step2_timeline.json",
            "output_path": output_dir / "step3_scoring.json",
            "metadata_dir": output_dir,
            "enable_checkpoint": True
        }

    def _adapt_step4_title(self) -> Dict[str, Any]:
        """
        适配Step4参数（标题生成）
        
        Returns:
            适配后的参数字典
        """
        project_dir = self.adapter.data_dir / "projects" / self.project_id
        output_dir = project_dir / "metadata"

        return {
            "input_path": output_dir / "step4_recommendation.json",
            "output_path": output_dir / "step4_title.json",
            "metadata_dir": output_dir,
            "enable_checkpoint": True
        }

    def _adapt_step3_scoring_only(self) -> Dict[str, Any]:
        """
        适配Step3_SCORING_ONLY参数
        
        Returns:
            适配后的参数字典
        """
        project_dir = self.adapter.data_dir / "projects" / self.project_id
        output_dir = project_dir / "metadata"

        return {
            "timeline_path": output_dir / "step2_timeline.json",
            "output_path": output_dir / "step3_scoring.json",
            "metadata_dir": output_dir,
            "enable_checkpoint": True
        }

    def _adapt_step4_recommendation(self) -> Dict[str, Any]:
        """
        适配Step4_RECOMMENDATION参数
        
        Returns:
            适配后的参数字典
        """
        project_dir = self.adapter.data_dir / "projects" / self.project_id
        output_dir = project_dir / "metadata"

        return {
            "scored_clips_path": output_dir / "step3_scoring.json",
            "output_path": output_dir / "step4_recommendation.json",
            "metadata_dir": output_dir,
            "enable_checkpoint": True
        }

    def _adapt_step6_clustering(self) -> Dict[str, Any]:
        """
        适配Step6参数（切片生成）
        
        Returns:
            适配后的参数字典
        """
        from pathlib import Path
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
