"""
同步工具函数模块
提供数据同步所需的通用工具函数
"""

import json
import logging
from pathlib import Path
from typing import Optional, List, Any

from core.logging_config import get_logger

logger = get_logger(__name__)


class SyncUtilsMixin:
    """
    同步工具函数混合类
    提供数据同步所需的通用工具函数
    """
    
    def _parse_time(self, time_str: str) -> float:
        """
        解析时间字符串为秒数
        
        Args:
            time_str: 时间字符串，格式如 "00:00:00,120" 或 "00:00:00.120"
            
        Returns:
            秒数
        """
        try:
            if ',' in time_str:
                time_str = time_str.replace(',', '.')
            
            parts = time_str.split(':')
            if len(parts) == 3:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = float(parts[2])
                return hours * 3600 + minutes * 60 + seconds
            else:
                return 0.0
        except Exception:
            return 0.0
    
    def _calculate_duration(self, start_time: str, end_time: str) -> float:
        """
        计算持续时间
        
        Args:
            start_time: 开始时间字符串
            end_time: 结束时间字符串
            
        Returns:
            持续时间（秒）
        """
        start_seconds = self._parse_time(start_time)
        end_seconds = self._parse_time(end_time)
        return end_seconds - start_seconds

    def _convert_time_to_seconds(self, time_str: str) -> int:
        """
        将时间字符串转换为秒数
        
        Args:
            time_str: 时间字符串，格式如 "00:00:00,120" 或 "00:00:00.120"
            
        Returns:
            整数秒数
        """
        try:
            # 处理格式 "00:00:00,120" 或 "00:00:00.120"
            time_str = time_str.replace(',', '.')
            parts = time_str.split(':')
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds_parts = parts[2].split('.')
            seconds = int(seconds_parts[0])
            milliseconds = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0
            
            total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000
            return int(total_seconds)
        except Exception as e:
            logger.error(f"时间转换失败: {time_str}, 错误: {e}")
            return 0
    
    def _read_json_file(self, file_path: Path) -> Optional[List]:
        """
        读取JSON文件
        
        Args:
            file_path: JSON文件路径
            
        Returns:
            解析后的列表数据，如果文件不存在或解析失败则返回None
        """
        if not file_path.exists():
            return None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else None
        except Exception as e:
            logger.warning(f"读取JSON文件失败 {file_path}: {e}")
            return None
    
    def _read_project_metadata(self, project_dir: Path) -> Optional[dict]:
        """
        读取项目元数据
        
        Args:
            project_dir: 项目目录路径
            
        Returns:
            项目元数据字典，如果不存在则返回None
        """
        metadata_files = [
            project_dir / "project.json",
            project_dir / "metadata.json",
            project_dir / "info.json"
        ]
        
        for metadata_file in metadata_files:
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    logger.warning(f"读取元数据文件失败 {metadata_file}: {e}")
        
        return None
