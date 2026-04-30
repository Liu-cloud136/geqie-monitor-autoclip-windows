#!/usr/bin/env python3
"""
数据库索引迁移脚本
用于添加优化后的数据库索引
执行此脚本以应用新的索引到现有数据库
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text, inspect
from core.database import engine, SessionLocal
from models.project import Project
from models.task import Task
from models.clip import Clip
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_existing_indexes(table_name: str) -> set:
    """获取表中已存在的索引名称"""
    inspector = inspect(engine)
    indexes = inspector.get_indexes(table_name)
    return {idx['name'] for idx in indexes}


def index_exists(table_name: str, index_name: str) -> bool:
    """检查索引是否已存在"""
    existing = get_existing_indexes(table_name)
    return index_name in existing


def create_index_if_not_exists(table_name: str, index_name: str, columns: list, unique: bool = False):
    """如果索引不存在则创建"""
    if index_exists(table_name, index_name):
        logger.info(f"✅ 索引 {index_name} 已存在，跳过")
        return False
    
    columns_str = ", ".join(columns)
    unique_str = "UNIQUE " if unique else ""
    
    create_sql = f"CREATE {unique_str}INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_str})"
    
    try:
        with engine.connect() as conn:
            conn.execute(text(create_sql))
            conn.commit()
        logger.info(f"✅ 成功创建索引: {index_name} ON {table_name}({columns_str})")
        return True
    except Exception as e:
        logger.error(f"❌ 创建索引 {index_name} 失败: {e}")
        return False


def add_task_indexes():
    """为 tasks 表添加索引"""
    logger.info("\n=== 为 tasks 表添加索引 ===")
    
    indexes = [
        ("idx_task_project_id", ["project_id"]),
        ("idx_task_status", ["status"]),
        ("idx_task_task_type", ["task_type"]),
        ("idx_task_created_at", ["created_at"]),
        ("idx_task_celery_task_id", ["celery_task_id"]),
        ("idx_task_project_status", ["project_id", "status"]),
        ("idx_task_project_created", ["project_id", "created_at"]),
        ("idx_task_status_created", ["status", "created_at"]),
    ]
    
    created = 0
    for name, columns in indexes:
        if create_index_if_not_exists("tasks", name, columns):
            created += 1
    
    logger.info(f"tasks 表索引完成: 新增 {created} 个索引")
    return created


def add_project_indexes():
    """为 projects 表添加索引"""
    logger.info("\n=== 为 projects 表添加索引 ===")
    
    indexes = [
        ("idx_project_created_at", ["created_at"]),
        ("idx_project_status", ["status"]),
    ]
    
    created = 0
    for name, columns in indexes:
        if create_index_if_not_exists("projects", name, columns):
            created += 1
    
    logger.info(f"projects 表索引完成: 新增 {created} 个索引")
    return created


def add_clip_indexes():
    """为 clips 表添加额外索引（如果需要）"""
    logger.info("\n=== 检查 clips 表索引 ===")
    
    existing = get_existing_indexes("clips")
    logger.info(f"clips 表现有索引: {existing}")
    
    return 0


def verify_indexes():
    """验证所有索引是否已创建"""
    logger.info("\n=== 验证索引状态 ===")
    
    tables = ["projects", "tasks", "clips"]
    
    for table in tables:
        indexes = get_existing_indexes(table)
        logger.info(f"\n{table} 表索引:")
        for idx in sorted(indexes):
            logger.info(f"  - {idx}")


def main():
    """主函数"""
    logger.info("🚀 开始执行数据库索引迁移...")
    
    total_created = 0
    
    total_created += add_project_indexes()
    total_created += add_task_indexes()
    total_created += add_clip_indexes()
    
    verify_indexes()
    
    logger.info(f"\n🎉 索引迁移完成！共新增 {total_created} 个索引")
    
    if total_created > 0:
        logger.info("""
📋 索引优化说明：

1. Project 表新增索引：
   - idx_project_created_at: 加速按创建时间排序查询
   - idx_project_status: 加速按状态过滤查询

2. Task 表新增索引：
   - idx_task_project_id: 加速按项目查询任务
   - idx_task_status: 加速按状态过滤
   - idx_task_task_type: 加速按任务类型过滤
   - idx_task_created_at: 加速按时间排序
   - idx_task_celery_task_id: 加速通过 Celery ID 查找
   - idx_task_project_status: 复合索引，加速查询项目特定状态的任务
   - idx_task_project_created: 复合索引，加速查询项目任务并按时间排序
   - idx_task_status_created: 复合索引，加速查询特定状态任务并按时间排序

这些索引将显著提升：
- 项目列表查询性能（消除 N+1 查询）
- 任务状态查询性能
- 批量数据操作性能
""")


if __name__ == "__main__":
    main()
