"""
公共工具函数模块
包含项目中常用的工具函数，避免代码重复
"""
import json
import re
import logging
from typing import Any, Dict, Optional, Callable

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，移除或替换不合法的字符
    
    Args:
        filename: 原始文件名
        
    Returns:
        清理后的文件名
    """
    # 移除或替换不合法的字符
    # Windows和Unix系统都不允许的字符: < > : " | ? * \ /
    # 替换为下划线
    sanitized = re.sub(r'[<>:"|?*\\/]', '_', filename)
    
    # 移除前后空格和点
    sanitized = sanitized.strip(' .')
    
    # 限制长度，避免文件名过长
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    
    # 确保文件名不为空
    if not sanitized:
        sanitized = "untitled"
    
    return sanitized


def parse_json_safely(response: str, default: Optional[Any] = None) -> Optional[Any]:
    """
    安全解析 JSON，避免异常导致程序崩溃
    
    Args:
        response: 要解析的 JSON 字符串
        default: 解析失败时返回的默认值
        
    Returns:
        解析后的对象，失败时返回默认值或 None
    """
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON解析失败: {e}")
        return default


def format_duration(seconds: float) -> str:
    """
    格式化时长为 HH:MM:SS 格式
    
    Args:
        seconds: 秒数
        
    Returns:
        格式化后的时间字符串
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_duration_with_ms(seconds: float, separator: str = '.') -> str:
    """
    格式化时长为 HH:MM:SS.mmm 格式（带毫秒）
    
    Args:
        seconds: 秒数
        separator: 秒和毫秒之间的分隔符（默认是'.'，SRT格式用','）
        
    Returns:
        格式化后的时间字符串，包含毫秒
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{milliseconds:03d}"


def time_str_to_seconds(time_str: str) -> float:
    """
    将时间字符串转换为秒数
    支持格式: HH:MM:SS, HH:MM:SS.mmm, HH:MM:SS,mmm
    
    Args:
        time_str: 时间字符串
        
    Returns:
        秒数
        
    Raises:
        ValueError: 如果时间格式无效
    """
    time_str = time_str.replace(',', '.')
    parts = time_str.split(':')
    
    if len(parts) == 3:
        h = int(parts[0])
        m = int(parts[1])
        s_parts = parts[2].split('.')
        s = int(s_parts[0])
        ms = int(s_parts[1]) if len(s_parts) > 1 else 0
        return h * 3600 + m * 60 + s + ms / 1000.0
    
    raise ValueError(f"无效的时间格式: {time_str}")


def remove_bom(text: str) -> str:
    """
    移除文本中的 BOM (Byte Order Mark)
    
    Args:
        text: 输入文本
        
    Returns:
        移除 BOM 后的文本
    """
    return text.lstrip('\ufeff')


def clean_whitespace(text: str) -> str:
    """
    清理文本中的空白字符
    
    Args:
        text: 输入文本
        
    Returns:
        清理后的文本
    """
    # 替换多个空白为单个空格
    text = re.sub(r'\s+', ' ', text)
    # 移除首尾空白
    return text.strip()
