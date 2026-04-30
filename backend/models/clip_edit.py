"""
切片编辑模型
定义切片编辑会话和编辑片段的数据模型
"""

import enum
from typing import Optional, List
from sqlalchemy import Column, String, Integer, Float, ForeignKey, Enum, JSON, Text, Index
from sqlalchemy.orm import relationship
from .base import BaseModel


class EditSessionStatus(str, enum.Enum):
    """编辑会话状态枚举"""
    DRAFT = "draft"               # 草稿状态
    PROCESSING = "processing"     # 处理中（正在生成合并视频）
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"            # 失败


class EditSegmentType(str, enum.Enum):
    """编辑片段类型枚举"""
    ORIGINAL = "original"         # 原始切片
    CROPPED = "cropped"           # 裁剪后的片段


class ClipEditSession(BaseModel):
    """切片编辑会话模型"""
    
    __tablename__ = "clip_edit_sessions"
    
    # 基本信息
    name = Column(
        String(255), 
        nullable=False, 
        comment="编辑会话名称"
    )
    description = Column(
        Text, 
        nullable=True, 
        comment="编辑会话描述"
    )
    
    # 状态信息
    status = Column(
        Enum(EditSessionStatus), 
        default=EditSessionStatus.DRAFT,
        nullable=False,
        index=True,
        comment="编辑会话状态"
    )
    
    # 输出信息
    output_video_path = Column(
        String(500), 
        nullable=True, 
        comment="输出视频文件路径"
    )
    output_duration = Column(
        Float, 
        nullable=True, 
        comment="输出视频时长（秒）"
    )
    
    # 元数据
    edit_metadata = Column(
        JSON, 
        nullable=True, 
        comment="编辑元数据（包括原始视频时长等信息）"
    )
    
    # 外键关联
    project_id = Column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目ID"
    )
    
    # 关联关系
    project = relationship(
        "Project",
        backref="edit_sessions"
    )
    segments = relationship(
        "EditSegment",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="EditSegment.order_index"
    )
    
    def __repr__(self):
        return f"<ClipEditSession(id={self.id}, name='{self.name}', status={self.status})>"
    
    @property
    def total_duration(self) -> float:
        """计算所有片段的总时长"""
        if not self.segments:
            return 0.0
        return sum(seg.duration for seg in self.segments if seg.duration)
    
    @property
    def segments_count(self) -> int:
        """获取片段数量"""
        return len(self.segments) if self.segments else 0


class EditSegment(BaseModel):
    """编辑片段模型"""
    
    __tablename__ = "edit_segments"
    
    # 基本信息
    segment_type = Column(
        Enum(EditSegmentType), 
        default=EditSegmentType.ORIGINAL,
        nullable=False,
        comment="片段类型"
    )
    
    # 时间信息（相对于原始视频）
    original_start_time = Column(
        Float, 
        nullable=False, 
        comment="原始开始时间（秒）"
    )
    original_end_time = Column(
        Float, 
        nullable=False, 
        comment="原始结束时间（秒）"
    )
    
    # 时间信息（在输出视频中的时间）
    output_start_time = Column(
        Float, 
        nullable=True, 
        comment="在输出视频中的开始时间（秒）"
    )
    
    # 时长
    duration = Column(
        Float, 
        nullable=False, 
        comment="片段时长（秒）"
    )
    
    # 排序
    order_index = Column(
        Integer, 
        nullable=False, 
        default=0,
        comment="排序索引"
    )
    
    # 元数据
    segment_metadata = Column(
        JSON, 
        nullable=True, 
        comment="片段元数据"
    )
    
    # 外键关联
    session_id = Column(
        String(36),
        ForeignKey("clip_edit_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属编辑会话ID"
    )
    original_clip_id = Column(
        String(36),
        ForeignKey("clips.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联的原始切片ID（可为空，如手动创建的片段）"
    )
    
    # 关联关系
    session = relationship(
        "ClipEditSession",
        back_populates="segments"
    )
    original_clip = relationship(
        "Clip",
        backref="edit_segments"
    )
    
    def __repr__(self):
        return f"<EditSegment(id={self.id}, type={self.segment_type}, order={self.order_index}, duration={self.duration}s)>"
    
    def calculate_duration(self):
        """计算并更新时长"""
        self.duration = self.original_end_time - self.original_start_time
        return self.duration


# 复合索引
Index('idx_edit_session_project_status', ClipEditSession.project_id, ClipEditSession.status)
Index('idx_edit_segment_session_order', EditSegment.session_id, EditSegment.order_index)
