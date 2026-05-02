"""
进度模型定义
包含进度阶段、状态和数据类
"""

from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum


class ProgressStage(Enum):
    INGEST = "INGEST"
    SUBTITLE = "SUBTITLE"
    ANALYZE = "ANALYZE"
    HIGHLIGHT = "HIGHLIGHT"
    EXPORT = "EXPORT"
    DONE = "DONE"
    ERROR = "ERROR"


class ProgressStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class ProgressInfo:
    project_id: str
    task_id: Optional[str] = None
    stage: ProgressStage = ProgressStage.INGEST
    status: ProgressStatus = ProgressStatus.PENDING
    progress: int = 0
    message: str = ""
    error_message: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    estimated_remaining: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['stage'] = self.stage.value
        data['status'] = self.status.value
        if self.start_time:
            data['start_time'] = self.start_time.isoformat()
        if self.end_time:
            data['end_time'] = self.end_time.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProgressInfo':
        if 'stage' in data and isinstance(data['stage'], str):
            data['stage'] = ProgressStage(data['stage'])
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = ProgressStatus(data['status'])
        if 'start_time' in data and isinstance(data['start_time'], str):
            data['start_time'] = datetime.fromisoformat(data['start_time'])
        if 'end_time' in data and isinstance(data['end_time'], str):
            data['end_time'] = datetime.fromisoformat(data['end_time'])
        return cls(**data)
