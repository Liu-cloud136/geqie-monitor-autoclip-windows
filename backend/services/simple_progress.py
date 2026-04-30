"""
简化的进度服务 - 固定阶段 + 固定权重
基于你提出的"做笨做稳"方案
"""

import time
import json
import logging
import os
from typing import List, Tuple, Optional, Dict, Any
import redis

logger = logging.getLogger(__name__)

# 固定阶段定义 - 根据你的项目实际调整
STAGES: List[Tuple[str, int]] = [
    ("INGEST", 10),        # 下载/就绪
    ("SUBTITLE", 15),      # 字幕/对齐
    ("ANALYZE", 20),       # 语义分析/大纲
    ("HIGHLIGHT", 25),     # 片段定位/打分
    ("EXPORT", 20),        # 导出/封装
    ("DONE", 10),          # 校验/归档
]

# 阶段权重映射
WEIGHTS = {name: w for name, w in STAGES}
# 阶段顺序
ORDER = [name for name, _ in STAGES]

# Redis连接 - 使用项目现有的Redis配置
try:
    # 从环境变量获取Redis URL，默认为本地地址
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    r = redis.Redis.from_url(redis_url, decode_responses=True)
    # 测试连接
    r.ping()
    logger.info("Redis连接成功")
except Exception as e:
    logger.error(f"Redis连接失败: {e}")
    r = None


def compute_percent(stage: str, subpercent: Optional[float] = None) -> int:
    """
    计算阶段对应的百分比
    
    Args:
        stage: 当前阶段名称
        subpercent: 子进度百分比 (0-100)，可选
        
    Returns:
        总进度百分比 (0-100)
    """
    # 累加之前阶段权重
    done = 0
    for s in ORDER:
        if s == stage:
            break
        done += WEIGHTS[s]
    
    # 当前阶段
    cur = WEIGHTS.get(stage, 0)
    
    if subpercent is None:
        # 阶段切换时，显示到当前阶段的起点
        # 对于 DONE 阶段显示 100%，其他阶段显示当前阶段开始的百分比
        return min(100, done + cur)
    else:
        # 带子进度，按权重线性换算
        subpercent = max(0, min(100, subpercent))
        return min(99, done + int(cur * subpercent / 100))


def emit_progress(project_id: str, stage: str, message: str = "", subpercent: Optional[float] = None, task_id: Optional[str] = None, estimated_remaining: Optional[int] = None):
    """
    发送进度事件
    
    Args:
        project_id: 项目ID
        stage: 当前阶段
        message: 进度消息
        subpercent: 子进度百分比，可选
        task_id: 任务ID，可选（用于更新数据库任务进度）
        estimated_remaining: 预计剩余时间（秒），可选
    """
    if not r:
        logger.warning("Redis未连接，跳过进度发送")
        return
        
    percent = compute_percent(stage, subpercent)
    payload = {
        "type": "progress",  # 添加消息类型，确保能被识别为进度消息
        "project_id": project_id,
        "stage": stage,
        "percent": percent,
        "message": message,
        "ts": int(time.time())
    }
    
    # 添加预计剩余时间（如果有）
    if estimated_remaining is not None:
        payload["estimated_remaining"] = estimated_remaining
    
    try:
        # 1) 持久化最新快照（给轮询/刷新用）
        mapping = {
            "stage": stage, 
            "percent": str(percent), 
            "message": message, 
            "ts": str(payload["ts"])
        }
        if estimated_remaining is not None:
            mapping["estimated_remaining"] = str(estimated_remaining)
        
        r.hset(f"progress:project:{project_id}", mapping=mapping)
        
        # 2) 即时广播（可选，用于WebSocket）
        r.publish(f"progress:project:{project_id}", json.dumps(payload))
        
        # 3) 更新数据库任务进度（如果提供了task_id）
        if task_id:
            _update_task_progress_in_db(task_id, percent, stage, message)
        
        logger.info(f"进度事件已发送: {project_id} - {stage} ({percent}%) - {message}" + (f" - 预计剩余: {estimated_remaining}秒" if estimated_remaining else ""))
        
    except Exception as e:
        logger.error(f"发送进度事件失败: {e}")

def _update_task_progress_in_db(task_id: str, progress: int, stage: str, message: str):
    """
    更新数据库中的任务进度
    
    Args:
        task_id: 任务ID
        progress: 进度百分比
        stage: 当前阶段
        message: 进度消息
    """
    try:
        from core.database import SessionLocal
        from models.task import Task, TaskStatus
        
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.progress = float(progress)
                task.current_step = stage
                
                # 根据进度更新任务状态
                if progress >= 100:
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = None  # 将由处理任务设置
                elif progress > 0:
                    task.status = TaskStatus.RUNNING
                    if not task.started_at:
                        from datetime import datetime
                        task.started_at = datetime.utcnow()
                
                db.commit()
                logger.debug(f"数据库任务进度已更新: {task_id} - {progress}%")
            else:
                logger.debug(f"未找到任务: {task_id}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"更新数据库任务进度失败: {e}")

def get_progress_snapshot(project_id: str) -> Optional[Dict[str, Any]]:
    """
    获取项目进度快照
    
    Args:
        project_id: 项目ID
        
    Returns:
        进度快照数据，如果不存在返回None
    """
    if not r:
        return None
        
    try:
        h = r.hgetall(f"progress:project:{project_id}")
        if not h:
            return None
        
        # 解析预计剩余时间
        estimated_remaining = None
        if "estimated_remaining" in h:
            try:
                estimated_remaining = int(h["estimated_remaining"])
            except (ValueError, TypeError):
                estimated_remaining = None
            
        return {
            "project_id": project_id,
            "stage": h.get("stage", ""),
            "percent": int(h.get("percent", 0)),
            "message": h.get("message", ""),
            "ts": int(h.get("ts", 0)),
            "estimated_remaining": estimated_remaining
        }
    except Exception as e:
        logger.error(f"获取进度快照失败: {e}")
        return None


def get_multiple_progress_snapshots(project_ids: List[str]) -> List[Dict[str, Any]]:
    """
    批量获取多个项目的进度快照
    
    Args:
        project_ids: 项目ID列表
        
    Returns:
        进度快照列表
    """
    if not r:
        return []
        
    results = []
    for project_id in project_ids:
        snapshot = get_progress_snapshot(project_id)
        if snapshot:
            results.append(snapshot)
    
    return results


def clear_progress(project_id: str):
    """
    清除项目进度数据
    
    Args:
        project_id: 项目ID
    """
    if not r:
        return
        
    try:
        r.delete(f"progress:project:{project_id}")
        logger.info(f"已清除项目进度数据: {project_id}")
    except Exception as e:
        logger.error(f"清除进度数据失败: {e}")

# 阶段名称映射（用于显示）
STAGE_NAMES = {
    "INGEST": "素材准备",
    "SUBTITLE": "字幕处理", 
    "ANALYZE": "内容分析",
    "HIGHLIGHT": "片段定位",
    "EXPORT": "视频导出",
    "DONE": "处理完成"
}

def get_stage_display_name(stage: str) -> str:
    """获取阶段的显示名称"""
    return STAGE_NAMES.get(stage, stage)