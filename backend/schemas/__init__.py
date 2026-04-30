"""
Pydantic schemas for data validation and serialization.
Separate from SQLAlchemy models to avoid type annotation conflicts.
"""

from .base import BaseSchema
from .project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse
from .clip import ClipCreate, ClipUpdate, ClipResponse, ClipListResponse
from .task import TaskCreate, TaskUpdate, TaskResponse, TaskListResponse
from .clip_edit import (
    EditSessionStatus,
    EditSegmentType,
    EditSegmentCreate,
    EditSegmentUpdate,
    EditSegmentResponse,
    EditSessionCreate,
    EditSessionUpdate,
    EditSessionResponse,
    EditSessionListResponse,
    ReorderSegmentsRequest,
    AddClipsToSessionRequest,
    CropSegmentRequest,
    MergeSegmentsRequest,
    GenerateVideoResponse,
    SplitSegmentRequest,
)

__all__ = [
    "BaseSchema",
    "ProjectCreate", "ProjectUpdate", "ProjectResponse", "ProjectListResponse",
    "ClipCreate", "ClipUpdate", "ClipResponse", "ClipListResponse", 
    "TaskCreate", "TaskUpdate", "TaskResponse", "TaskListResponse",
    "EditSessionStatus",
    "EditSegmentType",
    "EditSegmentCreate",
    "EditSegmentUpdate",
    "EditSegmentResponse",
    "EditSessionCreate",
    "EditSessionUpdate",
    "EditSessionResponse",
    "EditSessionListResponse",
    "ReorderSegmentsRequest",
    "AddClipsToSessionRequest",
    "CropSegmentRequest",
    "MergeSegmentsRequest",
    "GenerateVideoResponse",
    "SplitSegmentRequest",
]