"""
统一存储服务
整合所有存储相关功能，提供统一的存储管理接口
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.unified_config import get_data_directory
from models.project import Project
from models.clip import Clip
from services.exceptions import ServiceError, FileOperationError, ErrorCode

logger = logging.getLogger(__name__)


class UnifiedStorageService:
    """统一存储服务 - 整合所有存储相关功能"""
    
    def __init__(self, db: Session, project_id: str):
        self.db = db
        self.project_id = project_id
        self.data_dir = get_data_directory()
        self.project_dir = self.data_dir / "projects" / project_id
        
        self._ensure_project_structure()
    
    def _ensure_project_structure(self):
        """确保项目目录结构存在"""
        directories = [
            self.project_dir / "raw",
            self.project_dir / "processing",
            self.project_dir / "output" / "clips"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_project_dir(self) -> Path:
        """获取项目目录"""
        return self.project_dir
    
    def get_raw_dir(self) -> Path:
        """获取原始文件目录"""
        return self.project_dir / "raw"
    
    def get_processing_dir(self) -> Path:
        """获取处理中间文件目录"""
        return self.project_dir / "processing"
    
    def get_output_dir(self) -> Path:
        """获取输出文件目录"""
        return self.project_dir / "output"
    
    def get_clips_dir(self) -> Path:
        """获取切片文件目录"""
        return self.project_dir / "output" / "clips"
    
    
    def save_project_file(self, file_path: Path, file_type: str = "video") -> str:
        """
        保存项目文件到文件系统
        
        Args:
            file_path: 源文件路径
            file_type: 文件类型 (video, subtitle, other)
            
        Returns:
            相对路径
        """
        try:
            if file_type == "video":
                target_dir = self.project_dir / "raw"
                target_name = f"input_video{file_path.suffix}"
            elif file_type == "subtitle":
                target_dir = self.project_dir / "raw"
                target_name = f"input_subtitle{file_path.suffix}"
            else:
                target_dir = self.project_dir / "raw"
                target_name = file_path.name
            
            target_path = target_dir / target_name
            shutil.copy2(file_path, target_path)
            
            relative_path = f"projects/{self.project_id}/raw/{target_name}"
            logger.info(f"项目文件已保存: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"保存项目文件失败: {e}")
            raise FileOperationError(f"保存项目文件失败: {str(e)}", str(file_path))
    
    def get_project_file_path(self, relative_path: str) -> Path:
        """根据相对路径获取完整文件路径"""
        return self.data_dir / relative_path
    
    def save_clip_file(self, clip_data: Dict[str, Any], clip_id: str) -> str:
        """
        保存切片文件到文件系统
        
        Args:
            clip_data: 切片数据
            clip_id: 切片ID
            
        Returns:
            相对路径
        """
        try:
            clip_file = f"clip_{clip_id}.mp4"
            target_path = self.project_dir / "output" / "clips" / clip_file
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            target_path.touch()
            
            relative_path = f"projects/{self.project_id}/output/clips/{clip_file}"
            logger.info(f"切片文件已保存: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"保存切片文件失败: {e}")
            raise FileOperationError(f"保存切片文件失败: {str(e)}")
    
    def save_clip_metadata(self, clip_data: Dict[str, Any], clip_id: str) -> Clip:
        """
        保存切片元数据到数据库
        
        Args:
            clip_data: 切片数据
            clip_id: 切片ID
            
        Returns:
            切片记录
        """
        try:
            clip = Clip(
                id=clip_id,
                project_id=self.project_id,
                title=clip_data.get('title', ''),
                description=clip_data.get('description', ''),
                start_time=clip_data.get('start_time', 0),
                end_time=clip_data.get('end_time', 0),
                duration=clip_data.get('duration', 0),
                score=clip_data.get('score', 0.0),
                recommendation_reason=clip_data.get('recommendation_reason', ''),
                video_path=self.save_clip_file(clip_data, clip_id),
                thumbnail_path=clip_data.get('thumbnail_path', ''),
                processing_step=clip_data.get('processing_step', 6),
                tags=clip_data.get('tags', []),
                clip_metadata=clip_data.get('metadata', {})
            )
            
            self.db.add(clip)
            self.db.commit()
            self.db.refresh(clip)
            
            logger.info(f"切片元数据已保存到数据库: {clip_id}")
            return clip
            
        except Exception as e:
            logger.error(f"保存切片元数据失败: {e}")
            self.db.rollback()
            raise FileOperationError(f"保存切片元数据失败: {str(e)}")
    
    def save_processing_metadata(self, metadata: Dict[str, Any], step: str) -> str:
        """
        保存处理中间元数据到文件系统
        
        Args:
            metadata: 元数据
            step: 步骤名称
            
        Returns:
            文件路径
        """
        try:
            metadata_file = self.project_dir / "processing" / f"{step}.json"
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            logger.info(f"处理元数据已保存: {metadata_file}")
            return str(metadata_file)
            
        except Exception as e:
            logger.error(f"保存处理元数据失败: {e}")
            raise FileOperationError(f"保存处理元数据失败: {str(e)}")
    
    def get_processing_metadata(self, step: str) -> Optional[Dict[str, Any]]:
        """
        获取处理中间元数据
        
        Args:
            step: 步骤名称
            
        Returns:
            元数据或None
        """
        try:
            metadata_file = self.project_dir / "processing" / f"{step}.json"
            
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
            
        except Exception as e:
            logger.error(f"获取处理元数据失败: {e}")
            return None
    
    def get_project_clips(self) -> List[Clip]:
        """获取项目的所有切片（从数据库）"""
        return self.db.query(Clip).filter(Clip.project_id == self.project_id).all()
    
    def get_clip_file_path(self, clip: Clip) -> Path:
        """获取切片的完整文件路径"""
        if clip.video_path:
            return self.data_dir / clip.video_path
        return None
    
    def get_file_content(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        获取文件内容
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件内容或None
        """
        try:
            file_path_obj = Path(file_path)
            if file_path_obj.exists() and file_path_obj.suffix == '.json':
                with open(file_path_obj, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            logger.error(f"读取文件内容失败: {e}")
            return None
    
    def get_file_path(self, file_type: str, file_name: str) -> Optional[Path]:
        """
        获取文件路径
        
        Args:
            file_type: 文件类型 (raw, clip, processing, output)
            file_name: 文件名
            
        Returns:
            文件路径或None
        """
        if file_type == "raw":
            return self.project_dir / "raw" / file_name
        elif file_type == "clip":
            return self.project_dir / "output" / "clips" / file_name
        elif file_type == "processing":
            return self.project_dir / "processing" / file_name
        elif file_type == "output":
            return self.project_dir / "output" / file_name
        else:
            return None
    
    def cleanup_temp_files(self):
        """清理临时文件"""
        temp_dir = self.data_dir / "temp"
        if temp_dir.exists():
            for temp_file in temp_dir.iterdir():
                if temp_file.is_file():
                    temp_file.unlink()
                    logger.info(f"清理临时文件: {temp_file}")
    
    def cleanup_old_files(self, keep_days: int = 30):
        """
        清理旧文件
        
        Args:
            keep_days: 保留天数
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=keep_days)
            
            temp_dir = self.data_dir / "temp"
            if temp_dir.exists():
                for temp_file in temp_dir.iterdir():
                    if temp_file.is_file() and temp_file.stat().st_mtime < cutoff_date.timestamp():
                        temp_file.unlink()
                        logger.info(f"清理旧临时文件: {temp_file}")
            
            logger.info(f"清理完成，保留 {keep_days} 天内的文件")
            
        except Exception as e:
            logger.error(f"清理旧文件失败: {e}")
    
    def get_project_storage_info(self) -> Dict[str, Any]:
        """
        获取项目存储信息
        
        Returns:
            存储信息字典
        """
        try:
            total_size = 0
            file_count = 0
            
            for file_path in self.project_dir.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
                    file_count += 1
            
            return {
                "project_id": self.project_id,
                "total_size": total_size,
                "file_count": file_count,
                "project_dir": str(self.project_dir)
            }
            
        except Exception as e:
            logger.error(f"获取存储信息失败: {e}")
            return {}
    
    def migrate_from_old_storage(self, old_project_dir: Path) -> Dict[str, Any]:
        """
        从旧存储格式迁移数据
        
        Args:
            old_project_dir: 旧项目目录
            
        Returns:
            迁移结果
        """
        try:
            logger.info(f"开始迁移项目数据: {self.project_id}")
            
            migrated_files = []
            migrated_metadata = []
            
            if (old_project_dir / "raw").exists():
                for file_path in (old_project_dir / "raw").iterdir():
                    if file_path.is_file():
                        relative_path = self.save_project_file(file_path)
                        migrated_files.append(relative_path)
            
            if (old_project_dir / "processing").exists():
                for metadata_file in (old_project_dir / "processing").iterdir():
                    if metadata_file.suffix == '.json':
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        
                        step_name = metadata_file.stem
                        self.save_processing_metadata(metadata, step_name)
                        migrated_metadata.append(step_name)
            
            if (old_project_dir / "output").exists():
                clips_dir = old_project_dir / "output" / "clips"
                if clips_dir.exists():
                    for clip_file in clips_dir.iterdir():
                        if clip_file.is_file():
                            target_path = self.project_dir / "output" / "clips" / clip_file.name
                            target_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(clip_file, target_path)
                            migrated_files.append(f"projects/{self.project_id}/output/clips/{clip_file.name}")
            
            logger.info(f"数据迁移完成: {len(migrated_files)} 个文件, {len(migrated_metadata)} 个元数据")
            
            return {
                "success": True,
                "migrated_files": migrated_files,
                "migrated_metadata": migrated_metadata
            }
            
        except Exception as e:
            logger.error(f"数据迁移失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def delete_project_files(self) -> bool:
        """
        删除项目所有文件
        
        Returns:
            是否删除成功
        """
        try:
            if self.project_dir.exists():
                shutil.rmtree(self.project_dir)
                logger.info(f"项目文件已删除: {self.project_dir}")
                return True
            return False
        except Exception as e:
            logger.error(f"删除项目文件失败: {e}")
            return False


# 全局统一存储服务实例工厂函数
def create_unified_storage_service(db: Session, project_id: str) -> UnifiedStorageService:
    """
    创建统一存储服务实例
    
    Args:
        db: 数据库会话
        project_id: 项目ID
        
    Returns:
        统一存储服务实例
    """
    return UnifiedStorageService(db, project_id)