"""断点续传工具类"""
import json
import logging
import time
from typing import List, Dict, Set, Optional, Callable
from pathlib import Path

logger = logging.getLogger(__name__)

class CheckpointManager:
    """断点续传管理器"""

    def __init__(self, metadata_dir: Path, step_name: str, enable_checkpoint: bool = True):
        """
        初始化断点管理器

        Args:
            metadata_dir: 元数据目录
            step_name: 步骤名称 (如 "step1", "step2")
            enable_checkpoint: 是否启用断点续传
        """
        self.metadata_dir = Path(metadata_dir)
        self.step_name = step_name
        self.enable_checkpoint = enable_checkpoint
        self.checkpoint_file = self.metadata_dir / f"{step_name}_checkpoint.json"
        self.completed_items: Set = set()

    def load_checkpoint(self) -> Set:
        """
        加载断点文件

        Returns:
            已完成的项目索引集合
        """
        if not self.enable_checkpoint or not self.checkpoint_file.exists():
            return set()

        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                completed = set(data.get('completed_items', []))
                logger.info(f"[{self.step_name}] 从断点文件加载了 {len(completed)} 个已完成的项目")
                return completed
        except Exception as e:
            logger.warning(f"[{self.step_name}] 加载断点文件失败: {e}，将重新开始")
            return set()

    def save_checkpoint(self, item_index: int, success: bool = True, item_info: Dict = None):
        """
        保存断点

        Args:
            item_index: 项目索引
            success: 是否成功
            item_info: 项目信息（可选）
        """
        if not self.enable_checkpoint:
            return

        try:
            # 加载现有数据
            completed_items = set()
            if self.checkpoint_file.exists():
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    completed_items = set(data.get('completed_items', []))

            # 添加新的完成项目
            if success:
                completed_items.add(item_index)
            # 失败的项目不添加，下次会重试

            # 保存
            data = {
                'completed_items': sorted(list(completed_items)),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'last_item': item_index,
                'item_info': item_info
            }

            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug(f"[{self.step_name}] 断点已保存: 项目 {item_index}")

        except Exception as e:
            logger.warning(f"[{self.step_name}] 保存断点文件失败: {e}")

    def save_intermediate_results(self, results: List[Dict], output_path: Path = None):
        """
        保存中间结果

        Args:
            results: 结果列表
            output_path: 输出路径（可选）
        """
        if not self.enable_checkpoint:
            return

        try:
            if output_path is None:
                output_path = self.metadata_dir / f"{self.step_name}_intermediate.json"

            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            logger.debug(f"[{self.step_name}] 中间结果已保存，共 {len(results)} 个项目")

        except Exception as e:
            logger.warning(f"[{self.step_name}] 保存中间结果失败: {e}")

    def load_intermediate_results(self) -> List[Dict]:
        """
        加载中间结果

        Returns:
            结果列表
        """
        if not self.enable_checkpoint:
            return []

        try:
            output_path = self.metadata_dir / f"{self.step_name}_intermediate.json"
            if output_path.exists():
                with open(output_path, 'r', encoding='utf-8') as f:
                    results = json.load(f)
                logger.info(f"[{self.step_name}] 已加载 {len(results)} 个中间结果")
                return results
        except Exception as e:
            logger.warning(f"[{self.step_name}] 加载中间结果失败: {e}")

        return []

    def cleanup_checkpoint(self):
        """清理断点文件"""
        if not self.enable_checkpoint:
            return

        try:
            if self.checkpoint_file.exists():
                self.checkpoint_file.unlink()
                logger.info(f"[{self.step_name}] 断点文件已清理")

            # 同时清理中间结果
            intermediate_path = self.metadata_dir / f"{self.step_name}_intermediate.json"
            if intermediate_path.exists():
                intermediate_path.unlink()
                logger.info(f"[{self.step_name}] 中间结果文件已清理")

        except Exception as e:
            logger.warning(f"[{self.step_name}] 清理断点文件失败: {e}")

    def reset_checkpoint(self):
        """重置断点（强制重新开始）"""
        try:
            self.cleanup_checkpoint()
            logger.info(f"[{self.step_name}] 断点已重置，下次将重新开始")
        except Exception as e:
            logger.warning(f"[{self.step_name}] 重置断点失败: {e}")


class ProgressTracker:
    """进度跟踪器"""

    def __init__(self, total_items: int, callback: Optional[Callable[[int, str], None]] = None):
        """
        初始化进度跟踪器

        Args:
            total_items: 总项目数
            callback: 进度回调函数
        """
        self.total_items = total_items
        self.callback = callback
        self.completed = 0

    def update(self, message: str = None):
        """
        更新进度

        Args:
            message: 进度消息（可选）
        """
        self.completed += 1
        if self.callback:
            progress = int((self.completed / self.total_items) * 100) if self.total_items > 0 else 100
            default_message = f"已完成 {self.completed}/{self.total_items} 个项目"
            msg = message or default_message
            self.callback(progress, msg)

    def set_progress(self, completed: int, message: str = None):
        """
        设置进度（用于恢复断点后的初始化）

        Args:
            completed: 已完成数量
            message: 进度消息（可选）
        """
        self.completed = completed
        if self.callback:
            progress = int((self.completed / self.total_items) * 100) if self.total_items > 0 else 100
            default_message = f"已恢复进度 {completed}/{self.total_items} 个项目"
            msg = message or default_message
            self.callback(progress, msg)
