"""
日志配置
小陈说：日志是debug的救命稻草，好好写
"""
import logging
import sys
from typing import Optional


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    配置日志系统
    Args:
        level: 日志级别，默认INFO
    Returns:
        配置好的logger
    """
    # 创建logger
    logger = logging.getLogger("deepresearch")
    logger.setLevel(getattr(logging, level.upper()))

    # 避免重复添加handler
    if logger.handlers:
        return logger

    # 控制台handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))

    # 格式化器 - 小陈喜欢看清楚时间和位置
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    return logger


# 导出默认logger
logger = setup_logging()
