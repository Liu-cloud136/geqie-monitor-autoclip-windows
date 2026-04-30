"""
Backend utilities package.
"""

from .common import (
    sanitize_filename,
    time_str_to_seconds,
    format_duration,
    format_duration_with_ms,
)

__all__ = [
    'sanitize_filename',
    'time_str_to_seconds',
    'format_duration',
    'format_duration_with_ms',
    'LLMClient',
    'TextProcessor',
    'VideoProcessor',
]

def __getattr__(name):
    """延迟导入以避免循环依赖"""
    if name == 'LLMClient':
        from .llm_client import LLMClient
        return LLMClient
    elif name == 'TextProcessor':
        from .text_processor import TextProcessor
        return TextProcessor
    elif name == 'VideoProcessor':
        from .video_processor import VideoProcessor
        return VideoProcessor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
