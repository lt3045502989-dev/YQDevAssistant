"""
YQ Dev Assistant — Log Manager.

Centralized logging configuration using Python's built-in `logging`
module with Rich for beautiful console output and RotatingFileHandler
for persistent log files.

Design principles:
    1. DUAL OUTPUT: Console (Rich, colored) + File (plain text, rotated).
    2. HIERARCHICAL: Loggers are named with dots: "yqa.core.event_bus".
       Setting "yqa" to WARNING silences everything except warnings+.
       Setting "yqa.modules.health" to DEBUG gives verbose output for
       just the Health module.
    3. ROTATION: Log files rotate at 10MB, keeping 5 backups.
       This prevents logs from eating your disk over months of use.
    4. LEVELS AS VOLUME KNOB:
       - DEBUG: Everything (diagnostic, verbose)
       - INFO: Normal operations (default)
       - WARNING: Suspicious but not broken
       - ERROR: Something failed
       - CRITICAL: Application may not continue

Usage:
    >>> lm = LogManager(log_dir="logs", log_level="INFO")
    >>> logger = lm.get_logger(__name__)
    >>> logger.info("Application started")
    >>> lm.set_level("DEBUG")  # Increase verbosity at runtime
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

from src.utils.constants import MAX_LOG_BYTES, LOG_BACKUP_COUNT, DEFAULT_LOG_LEVEL

if TYPE_CHECKING:
    pass


class LogManager:
    """
    Initializes and manages the application-wide logging system.

    Features:
    - Console output via Rich (if installed) or plain StreamHandler
    - File output with rotation
    - Hierarchical logger naming
    - Runtime level changes

    Usage:
        >>> lm = LogManager(log_dir="logs")
        >>> logger = lm.get_logger("yqa.modules.health")
        >>> logger.info("Health check started")
    """

    # The format used for file logs (plain text, machine-parseable)
    FILE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    FILE_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(
        self,
        log_dir: str | Path = "logs",
        log_level: str = DEFAULT_LOG_LEVEL,
        max_bytes: int = MAX_LOG_BYTES,
        backup_count: int = LOG_BACKUP_COUNT,
        console: bool = True,
        file: bool = True,
    ) -> None:
        """
        Initialize the logging system.

        Sets up the root "yqa" logger with the configured handlers.
        All application loggers should be children of "yqa".

        Args:
            log_dir: Directory for log files. Created if it doesn't exist.
            log_level: Default log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            max_bytes: Max size per log file before rotation (default: 10MB).
            backup_count: Number of rotated log files to keep.
            console: Enable console output (Rich or plain).
            file: Enable file output with rotation.
        """
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_level = log_level.upper()
        self._max_bytes = max_bytes
        self._backup_count = backup_count

        # The root logger for this application
        self._root_logger = logging.getLogger("yqa")
        self._root_logger.setLevel(self._log_level)

        # Prevent the root logger from propagating to Python's root logger,
        # which would cause duplicate output if someone configured it.
        self._root_logger.propagate = False

        # Add handlers
        if console:
            self._add_console_handler()
        if file:
            self._add_file_handler()

        # Log startup
        self._root_logger.info(
            "LogManager initialized | level=%s | dir=%s | console=%s | file=%s",
            self._log_level,
            self._log_dir,
            console,
            file,
        )

    # ── Public API ─────────────────────────────────────

    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a named logger.

        Modules should use their module path:
            >>> logger = log_manager.get_logger(__name__)
            # Produces: yqa.modules.health.module

        This creates a hierarchy:
            yqa
            ├── yqa.core
            │   ├── yqa.core.event_bus
            │   ├── yqa.core.config_manager
            │   └── yqa.core.module_manager
            └── yqa.modules
                ├── yqa.modules.health
                └── yqa.modules.backup

        Setting "yqa.modules" to DEBUG gives verbosity for all modules
        while keeping core at INFO.

        Args:
            name: Logger name. If it starts with "src.", the prefix is stripped.

        Returns:
            A configured logger instance.
        """
        # Normalize: strip "src." prefix if present
        normalized = name.removeprefix("src.")
        return logging.getLogger(f"yqa.{normalized}")

    def set_level(self, level: str) -> None:
        """
        Change the log level at runtime.

        Useful for CLI's --verbose flag or settings changes.
        Affects the root "yqa" logger and all its children.

        Args:
            level: One of DEBUG, INFO, WARNING, ERROR, CRITICAL.
        """
        new_level = level.upper()
        self._root_logger.setLevel(new_level)
        self._log_level = new_level
        self._root_logger.info("Log level changed to %s", new_level)

    def get_log_dir(self) -> Path:
        """Return the log directory path."""
        return self._log_dir

    @property
    def root_logger(self) -> logging.Logger:
        """The root 'yqa' logger (parent of all application loggers)."""
        return self._root_logger

    # ── Internal ───────────────────────────────────────

    def _add_console_handler(self) -> None:
        """Add a console handler (Rich if available, plain otherwise)."""
        try:
            from rich.logging import RichHandler

            handler = RichHandler(
                rich_tracebacks=True,
                show_time=True,
                show_level=True,
                show_path=False,
                markup=False,
            )
            # Rich handles its own formatting
            handler.setFormatter(logging.Formatter("%(message)s"))
        except ImportError:
            # Fallback: plain StreamHandler
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%H:%M:%S",
            )
            handler.setFormatter(formatter)

        self._root_logger.addHandler(handler)

    def _add_file_handler(self) -> None:
        """Add a rotating file handler."""
        log_file = self._log_dir / "yqa.log"

        handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=self._max_bytes,
            backupCount=self._backup_count,
            encoding="utf-8",
        )

        formatter = logging.Formatter(
            self.FILE_FORMAT,
            datefmt=self.FILE_DATE_FORMAT,
        )
        handler.setFormatter(formatter)

        self._root_logger.addHandler(handler)
