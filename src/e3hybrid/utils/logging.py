"""Logging setup for command-line and experiment execution."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from e3hybrid.config.schemas import LogLevel


class _ColorFormatter(logging.Formatter):
    """Formatter that adds ANSI color to console log levels."""

    _COLORS = {
        logging.DEBUG: "\033[36m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[35m",
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record with color when supported by the terminal."""

        rendered = super().format(record)
        color = self._COLORS.get(record.levelno)
        if color is None:
            return rendered
        return f"{color}{rendered}{self._RESET}"


def configure_logging(
    level: LogLevel,
    log_dir: Path,
    max_bytes: int,
    backup_count: int,
) -> Path:
    """Configure framework logging and return the log file path."""

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "e3hybrid.log"
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level.value)

    file_formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )
    console_formatter = _ColorFormatter("%(levelname)s [%(name)s] %(message)s")

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(level.value)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(level.value)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    return log_file
