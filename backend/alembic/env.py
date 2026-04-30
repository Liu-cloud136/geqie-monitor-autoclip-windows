"""
Alembic 环境配置
用于数据库迁移管理
"""

import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# 导入数据库配置和模型
from core.database import DATABASE_URL
from models.base import Base
from models.project import Project
from models.clip import Clip
from models.task import Task

# Alembic 配置对象
config = context.config

# 设置数据库 URL
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# 解释配置文件中的日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 设置目标元数据
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """
    在'离线'模式下运行迁移
    这将配置上下文，只需一个 URL 而不是 Engine
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    在'在线'模式下运行迁移
    这将创建一个 Engine 并关联一个连接
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# 根据上下文判断运行模式
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()