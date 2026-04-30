"""
数据同步服务 - 将处理结果同步到数据库
"""

import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from sqlalchemy.orm import Session
from models.clip import Clip, ClipStatus
from models.project import Project, ProjectStatus, ProjectType
from models.task import Task, TaskStatus, TaskType
from datetime import datetime
from core.logging_config import get_logger

logger = get_logger(__name__)


class DataSyncService:
    """数据同步服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def sync_all_projects_from_filesystem(self, data_dir: Path) -> Dict[str, Any]:
        """从文件系统同步所有项目到数据库"""
        try:
            logger.info(f"开始从文件系统同步所有项目: {data_dir}")
            
            projects_dir = data_dir / "projects"
            if not projects_dir.exists():
                logger.warning(f"项目目录不存在: {projects_dir}")
                return {"success": False, "error": "项目目录不存在"}
            
            synced_projects = []
            failed_projects = []
            
            # 遍历所有项目目录
            for project_dir in projects_dir.iterdir():
                if project_dir.is_dir() and not project_dir.name.startswith('.'):
                    project_id = project_dir.name
                    try:
                        result = self.sync_project_from_filesystem(project_id, project_dir)
                        if result["success"]:
                            synced_projects.append(project_id)
                        else:
                            failed_projects.append({"project_id": project_id, "error": result.get("error")})
                    except Exception as e:
                        logger.error(f"同步项目 {project_id} 失败: {str(e)}")
                        failed_projects.append({"project_id": project_id, "error": str(e)})
            
            logger.info(f"同步完成: 成功 {len(synced_projects)} 个, 失败 {len(failed_projects)} 个")
            
            return {
                "success": True,
                "synced_projects": synced_projects,
                "failed_projects": failed_projects,
                "total_synced": len(synced_projects),
                "total_failed": len(failed_projects)
            }
            
        except Exception as e:
            logger.error(f"同步所有项目失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def sync_project_from_filesystem(self, project_id: str, project_dir: Path) -> Dict[str, Any]:
        """从文件系统同步单个项目到数据库"""
        try:
            logger.info(f"开始同步项目: {project_id}")
            
            # 检查项目是否已存在于数据库
            existing_project = self.db.query(Project).filter(Project.id == project_id).first()
            if existing_project:
                logger.info(f"项目 {project_id} 已存在于数据库，继续同步切片数据")
            else:
                # 读取项目元数据
                project_metadata = self._read_project_metadata(project_dir)
                if not project_metadata:
                    logger.warning(f"项目 {project_id} 没有元数据文件，创建基础项目记录")
                    project_metadata = {
                        "project_name": f"项目_{project_id[:8]}",
                        "created_at": datetime.now().isoformat(),
                        "status": "pending"
                    }
                
                # 创建项目记录
                project = Project(
                    id=project_id,
                    name=project_metadata.get("project_name", f"项目_{project_id[:8]}"),
                    description=project_metadata.get("description", ""),
                    project_type=ProjectType.KNOWLEDGE,  # 默认类型
                    status=ProjectStatus.PENDING,
                    processing_config=project_metadata.get("processing_config", {}),
                    project_metadata=project_metadata
                )
                
                self.db.add(project)
                self.db.commit()
                self.db.refresh(project)
                
                logger.info(f"项目 {project_id} 同步到数据库成功")
            

            
            # 同步切片数据
            clips_count = self._sync_clips_from_filesystem(project_id, project_dir)
            
            # 同步AI处理结果到processing_config
            self._sync_ai_processing_results(project_id, project_dir)
            
            # 检查项目是否已完成处理，更新项目状态
            self._update_project_status_if_completed(project_id, project_dir)
            
            return {
                "success": True,
                "project_id": project_id,
                "clips_synced": clips_count
            }
            
        except Exception as e:
            logger.error(f"同步项目 {project_id} 失败: {str(e)}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
    
    def _read_project_metadata(self, project_dir: Path) -> Optional[Dict[str, Any]]:
        """读取项目元数据"""
        metadata_files = [
            project_dir / "project.json",
            project_dir / "metadata.json",
            project_dir / "info.json"
        ]
        
        for metadata_file in metadata_files:
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    logger.warning(f"读取元数据文件失败 {metadata_file}: {e}")
        
        return None
    
    def _sync_clips_from_filesystem(self, project_id: str, project_dir: Path) -> int:
        """从文件系统同步切片数据"""
        try:
            # 查找切片数据文件
            clips_files = [
                project_dir / "metadata" / "step4_titles.json",  # 最完整的数据源（带标题）
                project_dir / "metadata" / "step3_all_scored.json",  # 评分后的数据
                project_dir / "metadata" / "clips_metadata.json",  # 元数据目录
                project_dir / "step5_video" / "clips_metadata.json",  # 旧版路径
                project_dir / "step3_all_scored.json",  # 旧版路径
                project_dir / "step4_title" / "step4_title.json",  # 旧版路径
                project_dir / "step4_titles.json",  # 旧版路径
                project_dir / "clips_metadata.json"  # 旧版路径
            ]
            
            clips_data = None
            for clips_file in clips_files:
                logger.info(f"检查切片文件: {clips_file}")
                if clips_file.exists():
                    try:
                        with open(clips_file, 'r', encoding='utf-8') as f:
                            clips_data = json.load(f)
                        logger.info(f"成功读取切片文件: {clips_file}, 数据长度: {len(clips_data) if isinstance(clips_data, list) else 'not list'}")
                        break
                    except Exception as e:
                        logger.warning(f"读取切片文件失败 {clips_file}: {e}")
                else:
                    logger.info(f"切片文件不存在: {clips_file}")
            
            if not clips_data:
                logger.info(f"项目 {project_id} 没有找到切片数据")
                return 0
            
            # 确保clips_data是列表
            if isinstance(clips_data, dict) and "clips" in clips_data:
                clips_data = clips_data["clips"]
            elif not isinstance(clips_data, list):
                logger.warning(f"项目 {project_id} 切片数据格式不正确")
                return 0
            
            synced_count = 0
            updated_count = 0
            for clip_data in clips_data:
                try:
                    # 检查切片是否已存在
                    existing_clip = self.db.query(Clip).filter(
                        Clip.project_id == project_id,
                        Clip.title == clip_data.get("generated_title", clip_data.get("title", ""))
                    ).first()
                    
                    if existing_clip:
                        # 更新现有切片的video_path和tags，强制使用项目内输出目录
                        clip_id = clip_data.get('id', str(synced_count + 1))
                        # 强制使用项目内标准路径
                        from core.path_utils import get_project_directory
                        project_dir = get_project_directory(project_id)
                        project_clips_dir = project_dir / "output" / "clips"
                        project_clips_dir.mkdir(parents=True, exist_ok=True)
                        project_video_path = project_clips_dir / f"clip_{clip_id}.mp4"
                        
                        # 兼容旧的全局输出目录，如果存在则迁移到项目目录
                        from core.path_utils import get_data_directory
                        legacy_video_path = get_data_directory() / "output" / "clips" / f"clip_{clip_id}.mp4"
                        try:
                            if legacy_video_path.exists() and not project_video_path.exists():
                                import shutil
                                shutil.copy2(legacy_video_path, project_video_path)
                                logger.info(f"迁移旧切片文件到项目目录: {legacy_video_path} -> {project_video_path}")
                        except Exception as _e:
                            logger.warning(f"迁移旧切片文件失败: {legacy_video_path} -> {project_video_path}: {_e}")
                        
                        # 始终使用项目内路径
                        video_path = str(project_video_path)
                        logger.info(f"更新切片 {existing_clip.id} 的video_path: {video_path}")
                        existing_clip.video_path = video_path
                        if existing_clip.tags is None:
                            existing_clip.tags = []  # 确保tags是空列表而不是null
                        updated_count += 1
                        continue
                    
                    # 转换时间格式
                    start_time = self._convert_time_to_seconds(clip_data.get('start_time', '00:00:00'))
                    end_time = self._convert_time_to_seconds(clip_data.get('end_time', '00:00:00'))
                    duration = end_time - start_time
                    
                    # 构建视频文件路径，强制使用项目内目录
                    clip_id = clip_data.get('id', str(synced_count + 1))
                    title = clip_data.get('generated_title', clip_data.get('title', clip_data.get('outline', '')))
                    
                    # 强制使用项目内路径
                    from core.path_utils import get_project_directory, get_data_directory
                    project_dir = get_project_directory(project_id)
                    project_clips_dir = project_dir / "output" / "clips"
                    project_clips_dir.mkdir(parents=True, exist_ok=True)
                    
                    # 查找实际的文件名（兼容旧格式）
                    actual_filename = None
                    for file_path in project_clips_dir.glob(f"clip_{clip_id}.mp4"):
                        actual_filename = file_path.name
                        break
                    
                    # 如果没找到新格式，尝试查找旧格式 {clip_id}_*.mp4
                    if not actual_filename:
                        for file_path in project_clips_dir.glob(f"{clip_id}_*.mp4"):
                            actual_filename = file_path.name
                            break
                    
                    if actual_filename:
                        project_video_path = project_clips_dir / actual_filename
                    else:
                        # 如果找不到实际文件，使用标准格式
                        project_video_path = project_clips_dir / f"clip_{clip_id}.mp4"
                    
                    # 兼容旧的全局输出目录，如果存在则迁移到项目目录
                    global_clips_dir = get_data_directory() / "output" / "clips"
                    if actual_filename:
                        global_video_path = global_clips_dir / actual_filename
                    else:
                        global_video_path = global_clips_dir / f"clip_{clip_id}.mp4"
                    
                    if global_video_path.exists() and not project_video_path.exists():
                        import shutil
                        shutil.copy2(global_video_path, project_video_path)
                        logger.info(f"将切片文件从全局目录迁移到项目目录: {global_video_path} -> {project_video_path}")
                    
                    # 始终使用项目内路径
                    video_path = str(project_video_path)
                    
                    # 创建切片记录
                    clip = Clip(
                        project_id=project_id,
                        title=clip_data.get('generated_title', clip_data.get('title', clip_data.get('outline', ''))),
                        description=clip_data.get('recommend_reason', ''),
                        start_time=start_time,
                        end_time=end_time,
                        duration=duration,
                        score=clip_data.get('final_score', 0.0),
                        video_path=video_path,
                        tags=[],  # 确保tags是空列表而不是null
                        clip_metadata=clip_data,
                        status=ClipStatus.COMPLETED
                    )
                    
                    self.db.add(clip)
                    synced_count += 1
                    
                except Exception as e:
                    logger.error(f"同步切片失败: {e}")
                    continue
            
            self.db.commit()
            logger.info(f"项目 {project_id} 同步了 {synced_count} 个切片，更新了 {updated_count} 个切片")
            return synced_count
            
        except Exception as e:
            logger.error(f"同步切片数据失败: {str(e)}")
            return 0
    

    
    def sync_project_data(self, project_id: str, project_dir: Path) -> Dict[str, Any]:
        """同步项目数据到数据库"""
        try:
            logger.info(f"开始同步项目数据: {project_id}")
            
            # 同步clips数据
            clips_count = self._sync_clips(project_id, project_dir)
            
            # 更新项目统计信息
            self._update_project_stats(project_id, clips_count)
            
            logger.info(f"项目数据同步完成: {project_id}, clips: {clips_count}")
            
            return {
                "success": True,
                "clips_synced": clips_count
            }
            
        except Exception as e:
            logger.error(f"同步项目数据失败: {str(e)}")
            raise
    
    def _sync_clips(self, project_id: str, project_dir: Path) -> int:
        """同步clips数据"""
        clips_file = project_dir / "step4_titles.json"
        if not clips_file.exists():
            logger.warning(f"Clips文件不存在: {clips_file}")
            return 0
        
        try:
            with open(clips_file, 'r', encoding='utf-8') as f:
                clips_data = json.load(f)
            
            clips_count = 0
            for clip_data in clips_data:
                # 检查是否已存在
                existing_clip = self.db.query(Clip).filter(
                    Clip.project_id == project_id,
                    Clip.title == clip_data.get("generated_title")
                ).first()
                
                if existing_clip:
                    logger.info(f"Clip已存在，跳过: {clip_data.get('generated_title')}")
                    continue
                
                # 创建新的clip记录
                clip = Clip(
                    project_id=project_id,
                    title=clip_data.get("generated_title", ""),
                    description=clip_data.get("outline", ""),
                    start_time=self._parse_time(clip_data.get("start_time", "00:00:00")),
                    end_time=self._parse_time(clip_data.get("end_time", "00:00:00")),
                    duration=self._calculate_duration(
                        clip_data.get("start_time", "00:00:00"),
                        clip_data.get("end_time", "00:00:00")
                    ),
                    score=clip_data.get("final_score", 0.0),
                    status=ClipStatus.COMPLETED,
                    tags=[],
                    clip_metadata={
                        "outline": clip_data.get("outline"),
                        "content": clip_data.get("content", []),
                        "recommend_reason": clip_data.get("recommend_reason"),
                        "chunk_index": clip_data.get("chunk_index"),
                        "original_id": clip_data.get("id")
                    }
                )
                
                self.db.add(clip)
                clips_count += 1
                logger.info(f"创建clip: {clip.title}")
            
            self.db.commit()
            logger.info(f"同步了 {clips_count} 个clips")
            return clips_count
            
        except Exception as e:
            logger.error(f"同步clips失败: {str(e)}")
            self.db.rollback()
            raise
    

    
    def _update_project_stats(self, project_id: str, clips_count: int):
        """更新项目统计信息"""
        try:
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.total_clips = clips_count
                self.db.commit()
                logger.info(f"更新项目统计: clips={clips_count}")
        except Exception as e:
            logger.error(f"更新项目统计失败: {str(e)}")
    
    def _parse_time(self, time_str: str) -> float:
        """解析时间字符串为秒数"""
        try:
            if ',' in time_str:
                time_str = time_str.replace(',', '.')
            
            parts = time_str.split(':')
            if len(parts) == 3:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = float(parts[2])
                return hours * 3600 + minutes * 60 + seconds
            else:
                return 0.0
        except Exception:
            return 0.0
    
    def _calculate_duration(self, start_time: str, end_time: str) -> float:
        """计算持续时间"""
        start_seconds = self._parse_time(start_time)
        end_seconds = self._parse_time(end_time)
        return end_seconds - start_seconds

    def _convert_time_to_seconds(self, time_str: str) -> int:
        """将时间字符串转换为秒数"""
        try:
            # 处理格式 "00:00:00,120" 或 "00:00:00.120"
            time_str = time_str.replace(',', '.')
            parts = time_str.split(':')
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds_parts = parts[2].split('.')
            seconds = int(seconds_parts[0])
            milliseconds = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0
            
            total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000
            return int(total_seconds)
        except Exception as e:
            logger.error(f"时间转换失败: {time_str}, 错误: {e}")
            return 0
    
    def _sync_ai_processing_results(self, project_id: str, project_dir: Path):
        """同步AI处理结果到processing_config字段"""
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
    
    def _read_json_file(self, file_path: Path) -> Optional[List]:
        """读取JSON文件"""
        if not file_path.exists():
            return None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else None
        except Exception as e:
            logger.warning(f"读取JSON文件失败 {file_path}: {e}")
            return None
    
    def _update_project_status_if_completed(self, project_id: str, project_dir: Path):
        """检查项目是否已完成处理，如果是则更新状态为completed"""
        try:
            # 检查是否有step5_video_output.json文件，这是处理完成的标志
            step5_output_file = project_dir / "output" / "step5_video_output.json"
            
            if step5_output_file.exists():
                # 获取项目记录
                project = self.db.query(Project).filter(Project.id == project_id).first()
                if project and project.status != ProjectStatus.COMPLETED:
                    # 读取step5输出文件获取统计信息
                    try:
                        with open(step5_output_file, 'r', encoding='utf-8') as f:
                            step5_output = json.load(f)
                        
                        # 更新项目状态和统计信息
                        project.status = ProjectStatus.COMPLETED
                        project.total_clips = step5_output.get("clips_count", 0)
                        project.completed_at = datetime.now()
                        
                        self.db.commit()
                        logger.info(f"项目 {project_id} 状态已更新为已完成，切片数: {project.total_clips}")
                        
                    except Exception as e:
                        logger.error(f"读取step5输出文件失败: {e}")
                        # 即使读取失败，也标记为已完成
                        project.status = ProjectStatus.COMPLETED
                        project.completed_at = datetime.now()
                        self.db.commit()
                        logger.info(f"项目 {project_id} 状态已更新为已完成（无统计信息）")
                        
        except Exception as e:
            logger.error(f"更新项目状态失败: {e}")
