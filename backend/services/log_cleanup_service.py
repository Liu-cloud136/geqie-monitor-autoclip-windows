"""日志清理服务 - 定期清理过期和备份日志"""

import logging
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from core.logging_config import get_logger

logger = get_logger(__name__)


class LogCleanupService:
    """日志清理服务"""

    def __init__(self, log_dir: Optional[Path] = None):
        """
        初始化日志清理服务

        Args:
            log_dir: 日志目录路径，默认为 logs/
        """
        if log_dir is None:
            # 获取项目根目录
            project_root = Path(__file__).parent.parent.parent
            log_dir = project_root / 'logs'

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 配置
        self.max_age_days = 7  # 最大保留天数
        self.max_backup_count = 1  # 最大备份数量
        self.max_file_size_mb = 50  # 单个文件最大大小（MB）

        # 要保留的主日志文件
        self.keep_patterns = [
            'backend.log',
            'celery.log',
            'celery_worker.log',
            'frontend.log',
        ]

    def cleanup_all(self) -> Dict[str, int]:
        """
        执行所有清理操作

        Returns:
            清理统计信息
        """
        stats = {
            'backup_files_deleted': 0,
            'backup_size_freed_kb': 0,
            'old_files_deleted': 0,
            'old_size_freed_kb': 0,
            'large_files_rotated': 0,
            'total_deleted': 0,
            'total_size_freed_kb': 0
        }

        # 1. 清理备份日志
        backup_stats = self.cleanup_backup_logs()
        stats.update(backup_stats)

        # 2. 清理过期日志
        old_stats = self.cleanup_old_logs()
        stats['old_files_deleted'] = old_stats['deleted_count']
        stats['old_size_freed_kb'] = old_stats['deleted_size_kb']

        # 3. 检查并轮转大文件
        large_stats = self.cleanup_large_files()
        stats['large_files_rotated'] = large_stats['rotated_count']

        # 统计总计
        stats['total_deleted'] = stats['backup_files_deleted'] + stats['old_files_deleted']
        stats['total_size_freed_kb'] = stats['backup_size_freed_kb'] + stats['old_size_freed_kb']

        logger.info(f"日志清理完成: {stats}")
        return stats

    def cleanup_backup_logs(self) -> Dict[str, int]:
        """
        清理所有备份日志文件（不保留任何备份）

        Returns:
            清理统计信息
        """
        stats = {
            'backup_files_deleted': 0,
            'backup_size_freed_kb': 0
        }

        if not self.log_dir.exists():
            return stats

        # 获取所有备份文件（.log.1, .log.2 等）
        backup_files = list(self.log_dir.glob('*.log.*'))

        for file in backup_files:
            if file.is_file():
                try:
                    size_kb = file.stat().st_size / 1024
                    file.unlink()
                    stats['backup_files_deleted'] += 1
                    stats['backup_size_freed_kb'] += size_kb
                    logger.info(f"删除备份日志: {file.name} ({size_kb:.1f} KB)")
                except Exception as e:
                    logger.error(f"删除备份日志失败 {file.name}: {e}")

        return stats

    def cleanup_old_logs(self, max_age_days: Optional[int] = None) -> Dict[str, int]:
        """
        清理过期的日志文件

        Args:
            max_age_days: 最大保留天数，默认使用配置值

        Returns:
            清理统计信息
        """
        stats = {
            'deleted_count': 0,
            'deleted_size_kb': 0
        }

        if max_age_days is None:
            max_age_days = self.max_age_days

        if not self.log_dir.exists():
            return stats

        # 计算过期时间
        cutoff_time = datetime.now() - timedelta(days=max_age_days)

        # 获取所有日志文件
        all_files = list(self.log_dir.glob('*.log*'))

        for file in all_files:
            # 跳过备份文件（由 cleanup_backup_logs 处理）
            parts = file.name.rsplit('.', 1)
            if len(parts) > 1 and parts[-1].isdigit():
                continue

            # 检查文件修改时间
            mtime = datetime.fromtimestamp(file.stat().st_mtime)
            if mtime < cutoff_time:
                try:
                    size_kb = file.stat().st_size / 1024
                    file.unlink()
                    stats['deleted_count'] += 1
                    stats['deleted_size_kb'] += size_kb
                    logger.info(f"删除过期日志: {file.name} ({size_kb:.1f} KB, {mtime.strftime('%Y-%m-%d')})")
                except Exception as e:
                    logger.error(f"删除过期日志失败 {file.name}: {e}")

        return stats

    def cleanup_large_files(self) -> Dict[str, int]:
        """
        检查并标记过大的日志文件

        Returns:
            轮转统计信息
        """
        stats = {
            'rotated_count': 0
        }

        if not self.log_dir.exists():
            return stats

        # 获取所有主日志文件
        all_files = list(self.log_dir.glob('*.log'))

        for file in all_files:
            # 跳过备份文件
            parts = file.name.rsplit('.', 1)
            if len(parts) > 1 and parts[-1].isdigit():
                continue

            # 检查文件大小
            size_mb = file.stat().st_size / (1024 * 1024)
            if size_mb > self.max_file_size_mb:
                logger.warning(f"日志文件过大: {file.name} ({size_mb:.1f} MB)")
                stats['rotated_count'] += 1

        return stats

    def get_log_info(self) -> Dict[str, any]:
        """
        获取日志文件信息

        Returns:
            日志信息字典
        """
        info = {
            'log_dir': str(self.log_dir),
            'exists': self.log_dir.exists(),
            'total_size_kb': 0,
            'file_count': 0,
            'files': []
        }

        if not self.log_dir.exists():
            return info

        all_files = list(self.log_dir.glob('*.log*'))
        info['file_count'] = len(all_files)

        for file in all_files:
            size_kb = file.stat().st_size / 1024
            mtime = datetime.fromtimestamp(file.stat().st_mtime)

            file_info = {
                'name': file.name,
                'size_kb': round(size_kb, 1),
                'modified': mtime.strftime('%Y-%m-%d %H:%M:%S'),
                'is_backup': file.name.rsplit('.', 1)[-1].isdigit() if '.' in file.name else False
            }

            info['files'].append(file_info)
            info['total_size_kb'] += size_kb

        info['total_size_kb'] = round(info['total_size_kb'], 1)

        return info


# 便捷函数
def cleanup_logs(log_dir: Optional[Path] = None) -> Dict[str, int]:
    """
    便捷函数：清理日志

    Args:
        log_dir: 日志目录路径

    Returns:
        清理统计信息
    """
    service = LogCleanupService(log_dir)
    return service.cleanup_all()


def get_log_info(log_dir: Optional[Path] = None) -> Dict[str, any]:
    """
    便捷函数：获取日志信息

    Args:
        log_dir: 日志目录路径

    Returns:
        日志信息字典
    """
    service = LogCleanupService(log_dir)
    return service.get_log_info()


if __name__ == "__main__":
    # 测试日志清理
    import json

    print("开始清理日志...")
    stats = cleanup_logs()
    print("清理统计:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))

    print("\n日志信息:")
    info = get_log_info()
    print(json.dumps(info, indent=2, ensure_ascii=False))
