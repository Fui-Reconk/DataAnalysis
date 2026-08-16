"""应用日志：错误与运行信息写入项目根目录 logs/ 下，便于排查问题。

- 捕获的异常（弹窗提示的同时）通过 logger.error/exception 落盘并带堆栈
- 未捕获异常由 sys.excepthook 兜底记录（不改变默认终止行为）
- 日志文件自动轮转（1MB × 3 份），开关与级别见 config.cfg [log]
"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from app import config

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")

_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    """获取应用日志器（惰性初始化，按 config.cfg [log] 配置）。"""
    global _logger
    if _logger is not None:
        return _logger
    _logger = logging.getLogger("dmatcher")
    if config.LOG_ENABLED:
        if not _logger.handlers:
            os.makedirs(LOG_DIR, exist_ok=True)
            handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000,
                                          backupCount=3, encoding="utf-8")
            handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s"))
            _logger.addHandler(handler)
            _logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
    else:
        # 关闭日志：吞掉所有记录
        _logger.addHandler(logging.NullHandler())
        _logger.setLevel(logging.CRITICAL + 1)
    return _logger


def _excepthook(exc_type, exc_value, exc_tb) -> None:
    """未捕获异常：写入日志后保留默认行为。"""
    get_logger().error("未捕获异常", exc_info=(exc_type, exc_value, exc_tb))
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _excepthook

logger = get_logger()
