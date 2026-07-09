"""Tests for logging setup."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from e3hybrid.config.schemas import LogLevel
from e3hybrid.utils.logging import configure_logging


def test_configure_logging_adds_console_and_rotating_file_handlers(
    tmp_path: Path,
) -> None:
    """Logging setup should include console and rotating file handlers."""

    log_path = configure_logging(
        level=LogLevel.DEBUG,
        log_dir=tmp_path,
        max_bytes=1024,
        backup_count=1,
    )

    handlers = logging.getLogger().handlers

    assert log_path == tmp_path / "e3hybrid.log"
    assert any(isinstance(handler, RotatingFileHandler) for handler in handlers)
    assert len(handlers) == 2
