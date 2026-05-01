"""
AI结果同步模块
提供AI处理结果同步功能
"""

import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from core.logging_config import get_logger
from models.project import Project

logger = get_logger(__name__)


class AIResultSyncMixin:
    """
    AI结果同步混合类
    提供AI处理结果同步功能
    """
    
    def _sync_ai_processing_results(self, project_id: str, project_dir: Path):
        """
        同步AI处理结果到processing_config字段
        
        Args:
            project_id: 项目ID
            project_dir: 项目目录路径
        """
        try:
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if not project:
                logger.warning(f"项目 {project_id} 不存在，无法同步AI处理结果")
                return
            
            metadata_dir = project_dir / "metadata"
            if not metadata_dir.exists():
                metadata_dir = project_dir
            
            processing_config = project.processing_config or {}
            
            outline_data = self._read_json_file(metadata_dir / "step1_outline.json")
            if outline_data:
                processing_config["outline"] = {"topics": outline_data}
                logger.info(f"同步大纲数据: {len(outline_data)} 个话题")
            
            timeline_data = self._read_json_file(metadata_dir / "step2_timeline.json")
            if timeline_data:
                processing_config["timeline"] = {"segments": timeline_data}
                logger.info(f"同步时间线数据: {len(timeline_data)} 个片段")
            
            # 尝试读取单独评分的文件，如果不存在则尝试读取标准评分文件
            scoring_file_path = metadata_dir / "step3_only_high_score_clips.json"
            logger.info(f"检查评分文件: {scoring_file_path}")
            scoring_data = self._read_json_file(scoring_file_path)
            logger.info(f"读取评分数据结果: {scoring_data}")
            if not scoring_data:
                logger.info("尝试读取标准评分文件")
                scoring_data = self._read_json_file(metadata_dir / "step3_high_score_clips.json")
                logger.info(f"读取标准评分数据结果: {scoring_data}")
            if scoring_data:
                processing_config["scoring"] = {"high_score_clips": scoring_data}
                logger.info(f"同步评分数据: {len(scoring_data)} 个高分片段")
            else:
                logger.warning("未找到评分数据")
            
            titles_data = self._read_json_file(metadata_dir / "step4_titles.json")
            if titles_data:
                generated_titles = [item.get("generated_title") for item in titles_data if item.get("generated_title")]
                processing_config["titles"] = {"generated_titles": generated_titles}
                logger.info(f"同步标题数据: {len(generated_titles)} 个标题")
            
            raw_outputs = {}
            for step_name, file_name in [
                ("step1_outline_raw", "step1_llm_raw_output"),
                ("step2_timeline_raw", "step2_llm_raw_output"),
                ("step3_scoring_raw", "step3_llm_raw_output"),
                ("step3_scoring_only_raw", "step3_only_llm_raw_output"),
                ("step4_title_raw", "step4_llm_raw_output")
            ]:
                raw_dir = metadata_dir / file_name
                if raw_dir.exists() and raw_dir.is_dir():
                    raw_contents = []
                    for raw_file in sorted(raw_dir.glob("*.txt")):
                        try:
                            with open(raw_file, 'r', encoding='utf-8') as f:
                                raw_contents.append({
                                    "file": raw_file.name,
                                    "content": f.read()[:5000]
                                })
                        except Exception as e:
                            logger.warning(f"读取原始输出文件失败 {raw_file}: {e}")
                    if raw_contents:
                        raw_outputs[step_name] = raw_contents
            
            if raw_outputs:
                processing_config["raw_outputs"] = raw_outputs
                logger.info(f"同步原始输出数据: {len(raw_outputs)} 个步骤")
            
            project.processing_config = processing_config
            # 标记processing_config字段已被修改，确保SQLAlchemy能检测到JSON字段的变化
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(project, "processing_config")
            self.db.commit()
            logger.info(f"项目 {project_id} AI处理结果同步完成")
            
        except Exception as e:
            logger.error(f"同步AI处理结果失败: {str(e)}")
