"""
切片同步模块
提供切片数据同步功能
"""

import json
import logging
import shutil
from typing import Dict, Any, List, Optional
from pathlib import Path

from core.logging_config import get_logger
from models.clip import Clip, ClipStatus
from models.project import Project

logger = get_logger(__name__)


class ClipSyncMixin:
    """
    切片同步混合类
    提供切片数据同步功能
    """
    
    def _sync_clips_from_filesystem(self, project_id: str, project_dir: Path) -> int:
        """
        从文件系统同步切片数据
        
        Args:
            project_id: 项目ID
            project_dir: 项目目录路径
            
        Returns:
            同步的切片数量
        """
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
        """
        同步项目数据到数据库
        
        Args:
            project_id: 项目ID
            project_dir: 项目目录路径
            
        Returns:
            同步结果字典
        """
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
        """
        同步clips数据（旧版方法，保持向后兼容）
        
        Args:
            project_id: 项目ID
            project_dir: 项目目录路径
            
        Returns:
            同步的切片数量
        """
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
        """
        更新项目统计信息
        
        Args:
            project_id: 项目ID
            clips_count: 切片数量
        """
        try:
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.total_clips = clips_count
                self.db.commit()
                logger.info(f"更新项目统计: clips={clips_count}")
        except Exception as e:
            logger.error(f"更新项目统计失败: {str(e)}")
