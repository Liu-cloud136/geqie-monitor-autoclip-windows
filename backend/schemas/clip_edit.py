"""
切片编辑相关的 Pydantic schemas
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field

from .base import BaseSchema, PaginationResponse


class EditSessionStatus(str, Enum):
    """编辑会话状态枚举"""
    DRAFT = "draft"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class EditSegmentType(str, Enum):
    """编辑片段类型枚举"""
    ORIGINAL = "original"
    CROPPED = "cropped"


# Edit Segment Schemas

class EditSegmentCreate(BaseSchema):
    """创建编辑片段的 schema"""
    segment_type: EditSegmentType = Field(
        default=EditSegmentType.ORIGINAL,
        description="片段类型"
    )
    original_start_time: float = Field(
        ..., 
        ge=0, 
        description="原始开始时间（秒）"
    )
    original_end_time: float = Field(
        ..., 
        ge=0, 
        description="原始结束时间（秒）"
    )
    order_index: int = Field(
        default=0, 
        ge=0, 
        description="排序索引"
    )
    original_clip_id: Optional[str] = Field(
        default=None, 
        description="关联的原始切片ID"
    )
    segment_metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        description="片段元数据"
    )


class EditSegmentUpdate(BaseSchema):
    """更新编辑片段的 schema"""
    original_start_time: Optional[float] = Field(
        default=None, 
        ge=0, 
        description="原始开始时间（秒）"
    )
    original_end_time: Optional[float] = Field(
        default=None, 
        ge=0, 
        description="原始结束时间（秒）"
    )
    order_index: Optional[int] = Field(
        default=None, 
        ge=0, 
        description="排序索引"
    )
    segment_type: Optional[EditSegmentType] = Field(
        default=None, 
        description="片段类型"
    )
    segment_metadata: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="片段元数据"
    )


class EditSegmentResponse(BaseSchema):
    """编辑片段响应 schema"""
    id: str = Field(description="片段ID")
    session_id: str = Field(description="所属编辑会话ID")
    segment_type: EditSegmentType = Field(description="片段类型")
    original_start_time: float = Field(description="原始开始时间（秒）")
    original_end_time: float = Field(description="原始结束时间（秒）")
    output_start_time: Optional[float] = Field(default=None, description="在输出视频中的开始时间（秒）")
    duration: float = Field(description="片段时长（秒）")
    order_index: int = Field(description="排序索引")
    original_clip_id: Optional[str] = Field(default=None, description="关联的原始切片ID")
    segment_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="片段元数据")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
    
    # 前端兼容性字段
    start_time: float = Field(description="开始时间（秒，兼容字段）")
    end_time: float = Field(description="结束时间（秒，兼容字段）")
    segment_order: int = Field(description="排序索引（兼容字段）")
    original_clip_title: Optional[str] = Field(default=None, description="原始切片标题（从元数据中提取）")
    original_clip_thumbnail: Optional[str] = Field(default=None, description="原始切片缩略图路径（从元数据中提取）")
    thumbnail_path: Optional[str] = Field(default=None, description="缩略图路径（兼容字段）")


# Edit Session Schemas

class EditSessionCreate(BaseSchema):
    """创建编辑会话的 schema"""
    name: str = Field(
        ..., 
        min_length=1, 
        max_length=200, 
        description="编辑会话名称"
    )
    description: Optional[str] = Field(
        default=None, 
        description="编辑会话描述"
    )
    project_id: str = Field(
        ..., 
        description="所属项目ID"
    )
    edit_metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        description="编辑元数据"
    )
    segments: Optional[List[EditSegmentCreate]] = Field(
        default_factory=list, 
        description="初始片段列表"
    )


class EditSessionUpdate(BaseSchema):
    """更新编辑会话的 schema"""
    name: Optional[str] = Field(
        default=None, 
        min_length=1, 
        max_length=200, 
        description="编辑会话名称"
    )
    description: Optional[str] = Field(
        default=None, 
        description="编辑会话描述"
    )
    status: Optional[EditSessionStatus] = Field(
        default=None, 
        description="编辑会话状态"
    )
    edit_metadata: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="编辑元数据"
    )


class EditSessionResponse(BaseSchema):
    """编辑会话响应 schema"""
    id: str = Field(description="编辑会话ID")
    name: str = Field(description="编辑会话名称")
    description: Optional[str] = Field(default=None, description="编辑会话描述")
    status: EditSessionStatus = Field(description="编辑会话状态")
    project_id: str = Field(description="所属项目ID")
    output_video_path: Optional[str] = Field(default=None, description="输出视频文件路径")
    output_duration: Optional[float] = Field(default=None, description="输出视频时长（秒）")
    edit_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="编辑元数据")
    segments: List[EditSegmentResponse] = Field(default_factory=list, description="片段列表")
    total_duration: float = Field(default=0.0, description="总时长（秒）")
    segments_count: int = Field(default=0, description="片段数量")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class EditSessionListResponse(BaseSchema):
    """编辑会话列表响应 schema"""
    items: List[EditSessionResponse] = Field(description="编辑会话列表")
    pagination: PaginationResponse = Field(description="分页信息")


# Operation Schemas

class ReorderSegmentsRequest(BaseSchema):
    """重排片段请求 schema"""
    segment_orders: List[Dict[str, int]] = Field(
        ..., 
        description="片段ID和新的排序索引列表，如 [{'segment_id': 'xxx', 'order_index': 0}, ...]"
    )


class AddClipsToSessionRequest(BaseSchema):
    """添加切片到会话请求 schema"""
    clip_ids: List[str] = Field(
        ..., 
        description="要添加的切片ID列表"
    )
    insert_position: Optional[int] = Field(
        default=None, 
        description="插入位置（从0开始，None表示追加到末尾）"
    )


class CropSegmentRequest(BaseSchema):
    """裁剪片段请求 schema"""
    segment_id: str = Field(
        ..., 
        description="要裁剪的片段ID"
    )
    new_start_time: float = Field(
        ..., 
        ge=0, 
        description="新的开始时间（秒）"
    )
    new_end_time: float = Field(
        ..., 
        ge=0, 
        description="新的结束时间（秒）"
    )


class MergeSegmentsRequest(BaseSchema):
    """合并片段请求 schema（用于创建合并视频任务）"""
    session_id: str = Field(
        ..., 
        description="编辑会话ID"
    )
    output_name: Optional[str] = Field(
        default=None, 
        description="输出视频名称"
    )


class GenerateVideoResponse(BaseSchema):
    """生成视频响应 schema"""
    success: bool = Field(description="是否成功启动任务")
    session_id: str = Field(description="编辑会话ID")
    task_id: Optional[str] = Field(default=None, description="任务ID（如果异步处理）")
    message: str = Field(description="状态消息")


class AddClipsToSessionResponse(BaseSchema):
    """添加切片到会话响应 schema"""
    success: bool = Field(description="是否成功")
    segments: List[EditSegmentResponse] = Field(default_factory=list, description="添加的片段列表")
    added_count: int = Field(description="实际添加的片段数量")


class GetSessionResponse(BaseSchema):
    """获取编辑会话响应 schema"""
    success: bool = Field(description="是否成功")
    session: EditSessionResponse = Field(description="编辑会话信息")


class GetOrCreateDefaultSessionResponse(BaseSchema):
    """获取或创建默认编辑会话响应 schema"""
    success: bool = Field(description="是否成功")
    session: EditSessionResponse = Field(description="编辑会话信息")
    is_new: bool = Field(description="是否是新创建的会话")


class SplitSegmentRequest(BaseSchema):
    """分割片段请求 schema"""
    segment_id: str = Field(
        ..., 
        description="要分割的片段ID"
    )
    split_time: float = Field(
        ..., 
        ge=0, 
        description="分割时间点（秒，相对于原始视频）"
    )
