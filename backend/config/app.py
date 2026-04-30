from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ProcessingConfig(BaseModel):
    """处理配置"""
    chunk_size: int = Field(default=5000, gt=0, description="文本分块大小")
    min_score_threshold: float = Field(default=80.0, ge=0.0, le=100.0, description="最小评分阈值（100分制）")
    max_retries: int = Field(default=3, gt=0, description="最大重试次数")
    timeout_seconds: int = Field(default=120, gt=0, description="处理超时时间（秒）")
    
    # 话题提取控制参数
    min_topic_duration_minutes: int = Field(default=2, gt=0, description="话题最小时长（分钟）")
    max_topic_duration_minutes: int = Field(default=12, gt=0, description="话题最大时长（分钟）")
    target_topic_duration_minutes: int = Field(default=5, gt=0, description="话题目标时长（分钟）")
    min_topics_per_chunk: int = Field(default=3, gt=0, description="每个分块最小话题数")
    max_topics_per_chunk: int = Field(default=8, gt=0, description="每个分块最大话题数")
    
    @field_validator('chunk_size')
    @classmethod
    def validate_chunk_size(cls, v):
        if v < 100:
            raise ValueError('分块大小不能少于100')
        if v > 50000:
            raise ValueError('分块大小不能超过50000')
        return v
    
    @field_validator('min_score_threshold')
    @classmethod
    def validate_min_score_threshold(cls, v):
        if not (0.0 <= v <= 100.0):
            raise ValueError('最小评分阈值必须在0到100之间')
        return v
    
    @field_validator('timeout_seconds')
    @classmethod
    def validate_timeout_seconds(cls, v):
        if v < 10:
            raise ValueError('超时时间不能少于10秒')
        if v > 600:
            raise ValueError('超时时间不能超过600秒')
        return v


class VideoConfig(BaseModel):
    """视频处理配置"""
    use_stream_copy: bool = Field(default=True, description="是否使用流复制（快速模式）")
    use_hardware_accel: bool = Field(default=True, description="是否使用硬件加速")
    encoder_preset: str = Field(default="p6", description="编码预设（p1-p7）")
    crf: int = Field(default=23, ge=18, le=28, description="视频质量（18-28，越小质量越好）")
    
    @field_validator('encoder_preset')
    @classmethod
    def validate_preset(cls, v):
        if v not in [f'p{i}' for i in range(1, 8)]:
            raise ValueError('encoder_preset必须是p1-p7之间的值')
        return v


class LoggingConfig(BaseModel):
    """日志配置"""
    level: str = Field(default="INFO", description="日志级别")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="日志格式")
    file: str = Field(default="logs/backend.log", description="日志文件路径")
    max_size: int = Field(default=10 * 1024 * 1024, description="日志文件最大大小（字节）")
    backup_count: int = Field(default=5, description="日志文件备份数量")
    json_logs: bool = Field(default=False, description="是否输出JSON格式日志")
    enable_console: bool = Field(default=True, description="是否启用控制台输出")
    
    @field_validator('level')
    @classmethod
    def validate_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'日志级别必须是以下之一: {", ".join(valid_levels)}')
        return v.upper()
    
    @field_validator('max_size')
    @classmethod
    def validate_max_size(cls, v):
        if v < 1024:
            raise ValueError('日志文件最大大小不能少于1KB')
        if v > 1024 * 1024 * 1024:
            raise ValueError('日志文件最大大小不能超过1GB')
        return v


class PathConfig(BaseModel):
    """路径配置"""
    project_root: Optional[Path] = Field(default=None, description="项目根目录")
    data_dir: Optional[Path] = Field(default=None, description="数据目录")
    uploads_dir: Optional[Path] = Field(default=None, description="上传目录")
    output_dir: Optional[Path] = Field(default=None, description="输出目录")
    temp_dir: Optional[Path] = Field(default=None, description="临时目录")
    prompt_dir: Optional[Path] = Field(default=None, description="提示词目录")
    logs_dir: Optional[Path] = Field(default=None, description="日志目录")
    
    def __init__(self, **data):
        super().__init__(**data)
        self._initialize_paths()
    
    def _initialize_paths(self):
        """初始化路径"""
        if self.project_root is None:
            self.project_root = self._detect_project_root()
        
        if self.data_dir is None:
            self.data_dir = self.project_root / "data"
        
        if self.uploads_dir is None:
            self.uploads_dir = self.data_dir / "uploads"
        
        if self.output_dir is None:
            self.output_dir = self.data_dir / "output"
        
        if self.temp_dir is None:
            self.temp_dir = self.data_dir / "temp"
        
        if self.prompt_dir is None:
            self.prompt_dir = self.project_root / "backend" / "prompt"
        
        if self.logs_dir is None:
            self.logs_dir = self.project_root / "logs"
        
        # 确保目录存在
        self._ensure_directories()
    
    def _detect_project_root(self) -> Path:
        """自动检测项目根目录"""
        current_path = Path(__file__).parent.parent
        
        # 向上查找项目根目录
        while current_path.parent != current_path:
            if (current_path.parent / "frontend").exists() and (current_path.parent / "backend").exists():
                return current_path.parent
            current_path = current_path.parent
        
        # 如果没找到，使用默认路径
        return Path(__file__).parent.parent.parent
    
    def _ensure_directories(self):
        """确保关键目录存在"""
        directories = [
            self.data_dir,
            self.uploads_dir,
            self.output_dir,
            self.temp_dir,
            self.logs_dir,
            self.output_dir / "clips",
            self.output_dir / "metadata",
            self.data_dir / "projects",
            self.data_dir / "backups"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_project_directory(self, project_id: str) -> Path:
        """获取项目目录"""
        project_dir = self.data_dir / "projects" / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir
    
    def get_project_raw_directory(self, project_id: str) -> Path:
        """获取项目原始文件目录"""
        raw_dir = self.get_project_directory(project_id) / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        return raw_dir
    
    def get_project_output_directory(self, project_id: str) -> Path:
        """获取项目输出目录"""
        output_dir = self.get_project_directory(project_id) / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
