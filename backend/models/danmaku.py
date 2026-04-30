"""
弹幕文件模型
定义弹幕文件的基本信息和状态
"""

import enum
from typing import Optional, List
from sqlalchemy import Column, String, Text, JSON, Enum, Integer, Float, ForeignKey, Index
from sqlalchemy.orm import relationship
from .base import BaseModel


class DanmakuSourceType(str, enum.Enum):
    """弹幕来源类型枚举"""
    BILIBILI = "bilibili"
    YOUTUBE = "youtube"
    DOUYU = "douyu"
    Huya = "huya"
    CUSTOM = "custom"


class DanmakuFileStatus(str, enum.Enum):
    """弹幕文件状态枚举"""
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    FAILED = "failed"


class DanmakuFile(BaseModel):
    """弹幕文件模型"""
    
    __tablename__ = "danmaku_files"
    
    file_name = Column(
        String(255),
        nullable=False,
        comment="原始文件名"
    )
    
    file_path = Column(
        String(500),
        nullable=False,
        comment="文件存储路径"
    )
    
    file_size = Column(
        Integer,
        nullable=True,
        comment="文件大小（字节）"
    )
    
    source_type = Column(
        Enum(DanmakuSourceType),
        default=DanmakuSourceType.BILIBILI,
        nullable=False,
        comment="弹幕来源类型"
    )
    
    status = Column(
        Enum(DanmakuFileStatus),
        default=DanmakuFileStatus.UPLOADED,
        nullable=False,
        index=True,
        comment="处理状态"
    )
    
    danmaku_count = Column(
        Integer,
        nullable=True,
        comment="弹幕数量"
    )
    
    video_duration = Column(
        Integer,
        nullable=True,
        comment="视频时长（秒），用于弹幕时间轴校准"
    )
    
    analysis_metadata = Column(
        JSON,
        nullable=True,
        comment="分析元数据（精简版，完整数据存储在文件系统）"
    )
    
    error_message = Column(
        Text,
        nullable=True,
        comment="错误信息（如果处理失败）"
    )
    
    project_id = Column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="关联项目ID（可选，弹幕文件可以独立于项目存在）"
    )
    
    project = relationship(
        "Project",
        back_populates="danmaku_files"
    )
    
    @property
    def is_parsed(self) -> bool:
        """是否已解析"""
        return self.status == DanmakuFileStatus.PARSED or self.status == DanmakuFileStatus.ANALYZED
    
    @property
    def is_analyzed(self) -> bool:
        """是否已分析"""
        return self.status == DanmakuFileStatus.ANALYZED
    
    @property
    def has_error(self) -> bool:
        """是否有错误"""
        return self.status == DanmakuFileStatus.FAILED
    
    def get_metadata_file_path(self) -> Optional[str]:
        """获取完整元数据文件路径"""
        if self.analysis_metadata and 'metadata_file' in self.analysis_metadata:
            return self.analysis_metadata['metadata_file']
        return None


Index('idx_danmaku_file_project_status', DanmakuFile.project_id, DanmakuFile.status)
Index('idx_danmaku_file_source_type', DanmakuFile.source_type)
