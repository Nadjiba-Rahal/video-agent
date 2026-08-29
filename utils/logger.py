"""
Simple shared logger.

Writes to both the console and a daily log file under logs/,
e.g. logs/2026-08-03.log

Usage in any file:
    from utils.logger import get_logger
    log = get_logger(__name__)
    log.info("something happened")
"""

import logging
import os
from datetime import datetime

from config.settings import settings

os.makedirs(settings.log_dir, exist_ok=True)

_log_file = os.path.join(settings.log_dir, f"{datetime.now():%Y-%m-%d}.log")

_formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

_file_handler = logging.FileHandler(_log_file, encoding="utf-8")
_file_handler.setFormatter(_formatter)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)
_console_handler.setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:  # avoid adding duplicate handlers on reload
        logger.setLevel(logging.INFO)
        logger.addHandler(_file_handler)
        logger.addHandler(_console_handler)
    return logger
