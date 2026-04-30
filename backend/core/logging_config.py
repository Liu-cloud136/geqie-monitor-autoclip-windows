"""
结构化日志配置模块
使用 structlog 实现统一的、结构化的日志系统
"""

import sys
import logging
import logging.handlers
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

import structlog
from structlog.types import EventDict, Processor


def add_timestamp(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """添加时间戳到日志"""
    event_dict["timestamp"] = datetime.utcnow().isoformat()
    return event_dict


def add_app_info(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """添加应用信息"""
    event_dict["app"] = "autoclip"
    return event_dict


def drop_color_message_key(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """移除颜色消息键"""
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    json_logs: bool = False,
    enable_console: bool = True
) -> None:
    """
    配置结构化日志
    
    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径
        json_logs: 是否输出 JSON 格式日志
        enable_console: 是否启用控制台输出
    """
    shared_processors = [
        add_timestamp,
        add_app_info,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_logs:
        processors = shared_processors + [
            structlog.processors.JSONRenderer()
        ]
    else:
        processors = shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    timestamper = structlog.processors.TimeStamper(fmt="iso")

    if json_logs:
        console_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=False),
        )
        file_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=False),
        )
    else:
        console_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True),
        )
        file_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=False),
        )

    handlers = []

    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        handlers.append(console_handler)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 使用覆盖模式，每次启动清空旧日志
        file_handler = logging.FileHandler(
            log_file,
            mode='w',  # 覆盖模式
            encoding="utf-8"
        )
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    for handler in handlers:
        root_logger.addHandler(handler)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    获取结构化日志记录器
    
    Args:
        name: 日志记录器名称，通常使用 __name__
        
    Returns:
        BoundLogger 实例
    """
    return structlog.get_logger(name)


def configure_from_config(config) -> None:
    """
    从配置对象或字典配置日志
    
    Args:
        config: 配置对象或字典，包含 level, file, json_logs 等字段
    """
    # 支持字典和对象两种形式
    if isinstance(config, dict):
        level = config.get("level", "INFO")
        log_file = config.get("file")
        json_logs = config.get("json_logs", False)
        enable_console = config.get("enable_console", True)
    else:
        level = config.level
        log_file = config.file
        json_logs = config.json_logs
        enable_console = config.enable_console
    
    configure_logging(
        level=level,
        log_file=log_file,
        json_logs=json_logs,
        enable_console=enable_console
    )


__all__ = [
    "configure_logging",
    "get_logger",
    "configure_from_config",
]