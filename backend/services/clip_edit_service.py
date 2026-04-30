"""
切片编辑服务
提供切片编辑会话的管理、片段操作、视频合并等功能
"""

from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from pathlib import Path
import logging

from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from services.base import BaseService
from repositories.base import BaseRepository
from models.clip_edit import (
    ClipEditSession, 
    EditSegment, 
    EditSessionStatus, 
    EditSegmentType
)
from models.clip import Clip
from models.project import Project
from schemas.clip_edit import (
    EditSessionCreate,
    EditSessionUpdate,
    EditSegmentCreate,
    EditSegmentUpdate,
    EditSessionResponse,
    EditSegmentResponse,
    ReorderSegmentsRequest,
    AddClipsToSessionRequest,
    CropSegmentRequest,
    SplitSegmentRequest,
)
from utils.video_processor import VideoProcessor
from core.config import get_data_directory, get_video_config
from services.exceptions import VideoProcessingError

logger = logging.getLogger(__name__)


class EditSessionRepository(BaseRepository[ClipEditSession]):
    """编辑会话Repository"""
    
    def __init__(self, db: Session):
        super().__init__(ClipEditSession, db)
    
    def get_by_project(self, project_id: str) -> List[ClipEditSession]:
        """获取项目的所有编辑会话"""
        return self.db.query(self.model).filter(
            self.model.project_id == project_id
        ).order_by(desc(self.model.updated_at)).all()
    
    def get_latest_by_project(self, project_id: str) -> Optional[ClipEditSession]:
        """获取项目的最新编辑会话"""
        return self.db.query(self.model).filter(
            self.model.project_id == project_id
        ).order_by(desc(self.model.updated_at)).first()


class EditSegmentRepository(BaseRepository[EditSegment]):
    """编辑片段Repository"""
    
    def __init__(self, db: Session):
        super().__init__(EditSegment, db)
    
    def get_by_session(self, session_id: str) -> List[EditSegment]:
        """获取会话的所有片段（按顺序）"""
        return self.db.query(self.model).filter(
            self.model.session_id == session_id
        ).order_by(asc(self.model.order_index)).all()
    
    def get_max_order_index(self, session_id: str) -> int:
        """获取会话中的最大排序索引"""
        from sqlalchemy import func
        result = self.db.query(func.max(self.model.order_index)).filter(
            self.model.session_id == session_id
        ).scalar()
        return result if result is not None else -1
    
    def reorder_segments(self, session_id: str, segment_orders: List[Dict[str, int]]) -> int:
        """
        重排片段顺序
        
        Args:
            session_id: 会话ID
            segment_orders: 片段ID和新排序索引的列表，如 [{'segment_id': 'xxx', 'order_index': 0}, ...]
            
        Returns:
            更新的片段数量
        """
        updated_count = 0
        for order_info in segment_orders:
            segment_id = order_info.get('segment_id')
            new_order = order_info.get('order_index')
            if segment_id and new_order is not None:
                segment = self.get_by_id(segment_id)
                if segment and segment.session_id == session_id:
                    segment.order_index = new_order
                    updated_count += 1
        
        if updated_count > 0:
            self.db.commit()
        
        return updated_count


class ClipEditService:
    """
    切片编辑服务类
    
    提供编辑会话的创建、管理，片段的添加、删除、重排、裁剪、分割，
    以及视频合并生成等功能。
    """
    
    def __init__(self, db: Session):
        """
        初始化编辑服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.session_repo = EditSessionRepository(db)
        self.segment_repo = EditSegmentRepository(db)
        self.clip_repo = BaseRepository(Clip, db)
        self.project_repo = BaseRepository(Project, db)
        self.video_config = get_video_config()
    
    def create_session(self, session_data: EditSessionCreate) -> ClipEditSession:
        """
        创建新的编辑会话
        
        Args:
            session_data: 会话创建数据
            
        Returns:
            创建的编辑会话
        """
        session = self.session_repo.create(
            name=session_data.name,
            description=session_data.description,
            project_id=session_data.project_id,
            status=EditSessionStatus.DRAFT,
            edit_metadata=session_data.edit_metadata or {}
        )
        
        if session_data.segments:
            for segment_data in session_data.segments:
                self._create_segment_internal(session.id, segment_data)
        
        logger.info(f"创建编辑会话: {session.id}, 项目: {session.project_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[ClipEditSession]:
        """
        获取编辑会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            编辑会话，如果不存在则返回None
        """
        return self.session_repo.get_by_id(session_id)
    
    def get_sessions_by_project(self, project_id: str) -> List[ClipEditSession]:
        """
        获取项目的所有编辑会话
        
        Args:
            project_id: 项目ID
            
        Returns:
            编辑会话列表
        """
        return self.session_repo.get_by_project(project_id)
    
    def update_session(self, session_id: str, session_data: EditSessionUpdate) -> Optional[ClipEditSession]:
        """
        更新编辑会话
        
        Args:
            session_id: 会话ID
            session_data: 更新数据
            
        Returns:
            更新后的会话，如果不存在则返回None
        """
        update_dict = session_data.model_dump(exclude_unset=True)
        if not update_dict:
            return self.get_session(session_id)
        
        session = self.session_repo.update(session_id, **update_dict)
        logger.info(f"更新编辑会话: {session_id}")
        return session
    
    def delete_session(self, session_id: str) -> bool:
        """
        删除编辑会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否删除成功
        """
        success = self.session_repo.delete(session_id)
        if success:
            logger.info(f"删除编辑会话: {session_id}")
        return success
    
    def add_segment(self, session_id: str, segment_data: EditSegmentCreate) -> Optional[EditSegment]:
        """
        添加片段到编辑会话
        
        Args:
            session_id: 会话ID
            segment_data: 片段创建数据
            
        Returns:
            创建的片段，如果会话不存在则返回None
        """
        session = self.get_session(session_id)
        if not session:
            logger.warning(f"会话不存在: {session_id}")
            return None
        
        return self._create_segment_internal(session_id, segment_data)
    
    def _create_segment_internal(self, session_id: str, segment_data: EditSegmentCreate) -> EditSegment:
        """
        内部创建片段方法
        
        Args:
            session_id: 会话ID
            segment_data: 片段创建数据
            
        Returns:
            创建的片段
        """
        max_order = self.segment_repo.get_max_order_index(session_id)
        order_index = segment_data.order_index if segment_data.order_index is not None else (max_order + 1)
        
        duration = segment_data.original_end_time - segment_data.original_start_time
        
        segment = self.segment_repo.create(
            session_id=session_id,
            segment_type=segment_data.segment_type,
            original_start_time=segment_data.original_start_time,
            original_end_time=segment_data.original_end_time,
            duration=duration,
            order_index=order_index,
            original_clip_id=segment_data.original_clip_id,
            segment_metadata=segment_data.segment_metadata or {}
        )
        
        logger.info(f"添加片段到会话: {session_id}, 片段: {segment.id}")
        return segment
    
    def add_clips_to_session(
        self, 
        session_id: str, 
        clip_ids: List[str], 
        insert_position: Optional[int] = None
    ) -> List[EditSegment]:
        """
        将现有切片添加到编辑会话
        
        Args:
            session_id: 会话ID
            clip_ids: 切片ID列表
            insert_position: 插入位置（None表示追加到末尾）
            
        Returns:
            创建的片段列表
        """
        session = self.get_session(session_id)
        if not session:
            logger.warning(f"会话不存在: {session_id}")
            return []
        
        existing_segments = self.segment_repo.get_by_session(session_id)
        max_order = max((s.order_index for s in existing_segments), default=-1)
        
        start_order = insert_position if insert_position is not None else (max_order + 1)
        
        created_segments = []
        
        for i, clip_id in enumerate(clip_ids):
            clip = self.clip_repo.get_by_id(clip_id)
            if not clip:
                logger.warning(f"切片不存在: {clip_id}")
                continue
            
            segment_data = EditSegmentCreate(
                segment_type=EditSegmentType.ORIGINAL,
                original_start_time=float(clip.start_time),
                original_end_time=float(clip.end_time),
                order_index=start_order + i,
                original_clip_id=clip_id,
                segment_metadata={
                    'original_clip_title': clip.title,
                    'original_clip_score': clip.score,
                    'original_clip_description': clip.description,
                    'original_clip_thumbnail': clip.thumbnail_path,
                }
            )
            
            segment = self._create_segment_internal(session_id, segment_data)
            created_segments.append(segment)
        
        if insert_position is not None and created_segments:
            self._adjust_order_indices_after_insert(session_id, insert_position, len(created_segments))
        
        logger.info(f"添加 {len(created_segments)} 个切片到会话: {session_id}")
        return created_segments
    
    def _adjust_order_indices_after_insert(
        self, 
        session_id: str, 
        insert_position: int, 
        count: int
    ) -> None:
        """
        插入后调整后续片段的排序索引
        
        Args:
            session_id: 会话ID
            insert_position: 插入位置
            count: 插入的片段数量
        """
        segments = self.segment_repo.get_by_session(session_id)
        for segment in segments:
            if segment.order_index >= insert_position:
                segment.order_index += count
        
        self.db.commit()
    
    def get_segment(self, segment_id: str) -> Optional[EditSegment]:
        """
        获取片段
        
        Args:
            segment_id: 片段ID
            
        Returns:
            片段，如果不存在则返回None
        """
        return self.segment_repo.get_by_id(segment_id)
    
    def update_segment(self, segment_id: str, segment_data: EditSegmentUpdate) -> Optional[EditSegment]:
        """
        更新片段
        
        Args:
            segment_id: 片段ID
            segment_data: 更新数据
            
        Returns:
            更新后的片段，如果不存在则返回None
        """
        update_dict = segment_data.model_dump(exclude_unset=True)
        if not update_dict:
            return self.get_segment(segment_id)
        
        if 'original_start_time' in update_dict or 'original_end_time' in update_dict:
            segment = self.get_segment(segment_id)
            if segment:
                start = update_dict.get('original_start_time', segment.original_start_time)
                end = update_dict.get('original_end_time', segment.original_end_time)
                update_dict['duration'] = end - start
                update_dict['segment_type'] = EditSegmentType.CROPPED
        
        segment = self.segment_repo.update(segment_id, **update_dict)
        logger.info(f"更新片段: {segment_id}")
        return segment
    
    def delete_segment(self, segment_id: str) -> bool:
        """
        删除片段
        
        Args:
            segment_id: 片段ID
            
        Returns:
            是否删除成功
        """
        segment = self.get_segment(segment_id)
        if segment:
            session_id = segment.session_id
            deleted_order = segment.order_index
            
            success = self.segment_repo.delete(segment_id)
            
            if success:
                self._adjust_order_indices_after_delete(session_id, deleted_order)
                logger.info(f"删除片段: {segment_id}")
            
            return success
        
        return False
    
    def _adjust_order_indices_after_delete(self, session_id: str, deleted_order: int) -> None:
        """
        删除后调整后续片段的排序索引
        
        Args:
            session_id: 会话ID
            deleted_order: 被删除的片段的排序索引
        """
        segments = self.segment_repo.get_by_session(session_id)
        for segment in segments:
            if segment.order_index > deleted_order:
                segment.order_index -= 1
        
        self.db.commit()
    
    def reorder_segments(self, session_id: str, segment_orders: List[Dict[str, int]]) -> int:
        """
        重排片段顺序
        
        Args:
            session_id: 会话ID
            segment_orders: 片段ID和新排序索引的列表
            
        Returns:
            更新的片段数量
        """
        updated_count = self.segment_repo.reorder_segments(session_id, segment_orders)
        logger.info(f"重排会话 {session_id} 中的 {updated_count} 个片段")
        return updated_count
    
    def crop_segment(self, segment_id: str, new_start_time: float, new_end_time: float) -> Optional[EditSegment]:
        """
        裁剪片段（调整开始和结束时间）
        
        Args:
            segment_id: 片段ID
            new_start_time: 新的开始时间
            new_end_time: 新的结束时间
            
        Returns:
            更新后的片段，如果不存在或时间无效则返回None
        """
        segment = self.get_segment(segment_id)
        if not segment:
            return None
        
        if new_start_time >= new_end_time:
            logger.warning(f"裁剪时间无效: start={new_start_time}, end={new_end_time}")
            return None
        
        if new_start_time < segment.original_start_time:
            logger.warning(f"裁剪开始时间早于原始开始时间: {new_start_time} < {segment.original_start_time}")
            new_start_time = segment.original_start_time
        
        if new_end_time > segment.original_end_time:
            logger.warning(f"裁剪结束时间晚于原始结束时间: {new_end_time} > {segment.original_end_time}")
            new_end_time = segment.original_end_time
        
        update_data = EditSegmentUpdate(
            original_start_time=new_start_time,
            original_end_time=new_end_time,
            segment_type=EditSegmentType.CROPPED
        )
        
        updated_segment = self.update_segment(segment_id, update_data)
        logger.info(f"裁剪片段: {segment_id}, 新时间范围: {new_start_time} - {new_end_time}")
        return updated_segment
    
    def split_segment(self, segment_id: str, split_time: float) -> Optional[List[EditSegment]]:
        """
        分割片段
        
        Args:
            segment_id: 片段ID
            split_time: 分割时间点（相对于原始视频）
            
        Returns:
            分割后的两个片段列表，如果失败则返回None
        """
        segment = self.get_segment(segment_id)
        if not segment:
            return None
        
        if split_time <= segment.original_start_time or split_time >= segment.original_end_time:
            logger.warning(f"分割时间点不在片段范围内: {split_time} 不在 {segment.original_start_time} - {segment.original_end_time}")
            return None
        
        session_id = segment.session_id
        original_order = segment.order_index
        
        first_segment_data = EditSegmentUpdate(
            original_end_time=split_time,
            segment_type=EditSegmentType.CROPPED
        )
        first_segment = self.update_segment(segment_id, first_segment_data)
        
        if not first_segment:
            return None
        
        second_segment_data = EditSegmentCreate(
            segment_type=EditSegmentType.CROPPED,
            original_start_time=split_time,
            original_end_time=segment.original_end_time,
            order_index=original_order + 1,
            original_clip_id=segment.original_clip_id,
            segment_metadata={
                'split_from': segment_id,
                'split_time': split_time,
                **(segment.segment_metadata or {})
            }
        )
        
        second_segment = self._create_segment_internal(session_id, second_segment_data)
        
        segments = self.segment_repo.get_by_session(session_id)
        for s in segments:
            if s.order_index > original_order and s.id != second_segment.id:
                s.order_index += 1
        
        self.db.commit()
        
        logger.info(f"分割片段: {segment_id} 在时间点 {split_time}")
        return [first_segment, second_segment]
    
    def get_session_segments(self, session_id: str) -> List[EditSegment]:
        """
        获取会话的所有片段（按顺序）
        
        Args:
            session_id: 会话ID
            
        Returns:
            片段列表
        """
        return self.segment_repo.get_by_session(session_id)
    
    def convert_to_response(self, session: ClipEditSession) -> EditSessionResponse:
        """
        将编辑会话转换为响应格式
        
        Args:
            session: 编辑会话模型
            
        Returns:
            编辑会话响应
        """
        segments = self.get_session_segments(session.id)
        segment_responses = [self._convert_segment_to_response(s) for s in segments]
        
        total_duration = sum(s.duration for s in segments) if segments else 0.0
        
        return EditSessionResponse(
            id=session.id,
            name=session.name,
            description=session.description,
            status=session.status,
            project_id=session.project_id,
            output_video_path=session.output_video_path,
            output_duration=session.output_duration,
            edit_metadata=session.edit_metadata or {},
            segments=segment_responses,
            total_duration=total_duration,
            segments_count=len(segments),
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
    
    def _convert_segment_to_response(self, segment: EditSegment) -> EditSegmentResponse:
        """
        将片段转换为响应格式
        
        Args:
            segment: 片段模型
            
        Returns:
            片段响应
        """
        metadata = segment.segment_metadata or {}
        original_clip_title = metadata.get('original_clip_title')
        original_clip_thumbnail = metadata.get('original_clip_thumbnail')
        
        return EditSegmentResponse(
            id=segment.id,
            session_id=segment.session_id,
            segment_type=segment.segment_type,
            original_start_time=segment.original_start_time,
            original_end_time=segment.original_end_time,
            output_start_time=segment.output_start_time,
            duration=segment.duration,
            order_index=segment.order_index,
            original_clip_id=segment.original_clip_id,
            segment_metadata=segment.segment_metadata or {},
            created_at=segment.created_at,
            updated_at=segment.updated_at,
            # 前端兼容性字段
            start_time=segment.original_start_time,
            end_time=segment.original_end_time,
            segment_order=segment.order_index,
            original_clip_title=original_clip_title,
            original_clip_thumbnail=original_clip_thumbnail,
            thumbnail_path=original_clip_thumbnail,
        )
    
    async def generate_merged_video(
        self,
        session_id: str,
        output_name: Optional[str] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
        use_stream_copy: Optional[bool] = None,
        use_hardware_accel: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        生成合并视频
        
        Args:
            session_id: 会话ID
            output_name: 输出文件名（可选）
            progress_callback: 进度回调函数
            use_stream_copy: 是否使用流复制（默认使用配置）
            use_hardware_accel: 是否使用硬件加速（默认使用配置）
            
        Returns:
            包含生成结果的字典
        """
        session = self.get_session(session_id)
        if not session:
            return {
                'success': False,
                'message': '编辑会话不存在',
                'session_id': session_id
            }
        
        segments = self.get_session_segments(session_id)
        if not segments:
            return {
                'success': False,
                'message': '会话中没有片段',
                'session_id': session_id
            }
        
        self.update_session(session_id, EditSessionUpdate(status=EditSessionStatus.PROCESSING))
        
        try:
            project = self.project_repo.get_by_id(session.project_id)
            if not project:
                raise ValueError(f"项目不存在: {session.project_id}")
            
            data_dir = get_data_directory()
            project_dir = data_dir / "projects" / session.project_id
            edits_dir = project_dir / "edits"
            edits_dir.mkdir(parents=True, exist_ok=True)
            
            if output_name:
                from utils.common import sanitize_filename
                safe_name = sanitize_filename(output_name)
                output_path = edits_dir / f"{safe_name}.mp4"
            else:
                output_path = edits_dir / f"merged_{session.id}.mp4"
            
            video_segments = [
                {
                    'start_time': s.original_start_time,
                    'end_time': s.original_end_time,
                }
                for s in segments
            ]
            
            input_video = None
            if project.video_path:
                input_video = Path(project.video_path)
                if not input_video.exists():
                    input_video = None
            
            if use_stream_copy is None:
                use_stream_copy = self.video_config.get('use_stream_copy', True)
            if use_hardware_accel is None:
                use_hardware_accel = self.video_config.get('use_hardware_accel', True)
            
            success = await VideoProcessor.merge_videos_async(
                video_segments=video_segments,
                output_path=output_path,
                input_video=input_video,
                progress_callback=progress_callback,
                use_stream_copy=use_stream_copy,
                use_hardware_accel=use_hardware_accel
            )
            
            if success and output_path.exists():
                video_info = VideoProcessor.get_video_info(output_path)
                output_duration = video_info.get('duration', 0.0)
                
                self.update_session(
                    session_id, 
                    EditSessionUpdate(
                        status=EditSessionStatus.COMPLETED,
                        output_video_path=str(output_path),
                        output_duration=output_duration
                    )
                )
                
                logger.info(f"成功生成合并视频: {output_path}")
                
                return {
                    'success': True,
                    'session_id': session_id,
                    'output_path': str(output_path),
                    'output_duration': output_duration,
                    'segments_count': len(segments),
                    'message': '视频合并成功'
                }
            else:
                self.update_session(session_id, EditSessionUpdate(status=EditSessionStatus.FAILED))
                return {
                    'success': False,
                    'session_id': session_id,
                    'message': '视频合并失败'
                }
        
        except VideoProcessingError as e:
            logger.error(f"视频处理错误: {e}")
            self.update_session(session_id, EditSessionUpdate(status=EditSessionStatus.FAILED))
            return {
                'success': False,
                'session_id': session_id,
                'message': f'视频处理错误: {str(e)}'
            }
        except Exception as e:
            logger.error(f"生成合并视频异常: {e}")
            self.update_session(session_id, EditSessionUpdate(status=EditSessionStatus.FAILED))
            return {
                'success': False,
                'session_id': session_id,
                'message': f'生成视频失败: {str(e)}'
            }
    
    def create_or_get_default_session(self, project_id: str) -> tuple[ClipEditSession, bool]:
        """
        创建或获取项目的默认编辑会话
        
        Args:
            project_id: 项目ID
            
        Returns:
            (编辑会话, 是否是新创建的)
        """
        existing_session = self.session_repo.get_latest_by_project(project_id)
        if existing_session:
            return existing_session, False
        
        session_data = EditSessionCreate(
            name="默认编辑会话",
            project_id=project_id,
            description="自动创建的默认编辑会话"
        )
        return self.create_session(session_data), True
