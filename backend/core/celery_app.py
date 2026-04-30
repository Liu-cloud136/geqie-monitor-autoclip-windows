"""
Celery应用配置
任务队列配置和初始化
"""

import os
from pathlib import Path

# 加载环境变量
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

from celery import Celery

# 设置默认配置模块
# os.environ.setdefault('CELERY_CONFIG_MODULE', 'backend.core.celery_app')

# 创建Celery应用
celery_app = Celery('autoclip')

# 检测是否在Windows环境
import platform
IS_WINDOWS = platform.system() == 'Windows'

# 配置Celery
class CeleryConfig:
    """Celery配置类"""

    # 任务序列化格式
    task_serializer = 'json'
    accept_content = ['json']
    result_serializer = 'json'
    timezone = 'Asia/Shanghai'
    enable_utc = True

    # Redis配置
    broker_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    result_backend = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    # 任务配置
    task_always_eager = os.getenv('CELERY_ALWAYS_EAGER', 'False').lower() == 'true'  # 生产环境异步执行
    task_eager_propagates = True

    # 工作进程配置 - 优化性能
    if IS_WINDOWS:
        # Windows下使用gevent或eventlet提高并发性能
        try:
            import gevent
            worker_pool = 'gevent'
            worker_concurrency = os.getenv('CELERY_CONCURRENCY', '4')
        except ImportError:
            try:
                import eventlet
                worker_pool = 'eventlet'
                worker_concurrency = os.getenv('CELERY_CONCURRENCY', '4')
            except ImportError:
                worker_pool = 'solo'
                worker_concurrency = 1
    else:
        worker_pool = 'prefork'
        worker_concurrency = os.getenv('CELERY_CONCURRENCY', '4')

    worker_prefetch_multiplier = 4
    worker_max_tasks_per_child = 500
    worker_disable_rate_limits = True
    
    # 任务路由 - 按任务类型分配到不同队列，提高处理效率
    task_routes = {
        'backend.tasks.processing.process_video_pipeline': {'queue': 'processing'},
        'backend.tasks.processing.process_single_step': {'queue': 'processing'},
        'backend.tasks.processing.retry_processing_step': {'queue': 'processing'},
        'backend.tasks.video.*': {'queue': 'video'},
        'backend.tasks.notification.*': {'queue': 'notification'},
        'backend.tasks.upload.*': {'queue': 'upload'},
        'backend.tasks.import_processing.*': {'queue': 'processing'},
        'backend.tasks.maintenance.*': {'queue': 'maintenance'},
        'backend.tasks.data_cleanup.*': {'queue': 'maintenance'},
    }
    
    # 结果配置优化
    result_expires = 1800  # 30分钟，减少内存占用
    task_ignore_result = False
    task_track_started = True  # 跟踪任务开始时间
    
    # 连接池优化
    redis_max_connections = 50
    broker_connection_retry_on_startup = True
    broker_connection_retry = True
    broker_connection_max_retries = 5
    
    # 性能优化
    task_acks_late = True  # 任务完成后再确认，防止任务丢失
    task_reject_on_worker_lost = True  # Worker丢失时拒绝任务
    task_send_sent_event = False  # 禁用发送事件，减少开销
    
    # 日志配置
    worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
    worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] [%(task_name)s(%(task_id)s)] %(message)s'
    
    # 允许Celery劫持根日志记录器，确保日志正确输出
    worker_hijack_root_logger = True

# 应用配置
celery_app.config_from_object(CeleryConfig)

# 配置日志（在类定义之外）
def setup_logging():
    """配置Celery日志"""
    import logging
    from pathlib import Path

    # 创建日志目录
    log_dir = Path(__file__).parent.parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)

    # Worker日志文件
    worker_log_file = log_dir / 'celery_worker.log'

    # 配置日志处理器 - 使用覆盖模式
    worker_log_handler = logging.FileHandler(
        worker_log_file,
        mode='w',  # 覆盖模式，每次启动清空旧日志
        encoding='utf-8'
    )
    worker_log_handler.setFormatter(logging.Formatter(
        '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
    ))
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
    ))
    
    # 配置Celery的日志记录器
    celery_logger = logging.getLogger('celery')
    celery_logger.setLevel(logging.INFO)
    celery_logger.addHandler(worker_log_handler)
    celery_logger.addHandler(console_handler)
    
    # 配置任务日志记录器（避免使用根日志记录器）
    task_logger = logging.getLogger('tasks')
    task_logger.setLevel(logging.INFO)
    task_logger.addHandler(worker_log_handler)
    task_logger.addHandler(console_handler)

# 设置日志
setup_logging()

# 手动导入任务模块以确保任务被注册
# 必须导入所有包含Celery任务的模块
import tasks.processing
import tasks.import_processing
import tasks.thumbnail_task
import tasks.video
import tasks.notification
import tasks.maintenance
import tasks.data_cleanup

if __name__ == '__main__':
    celery_app.start()