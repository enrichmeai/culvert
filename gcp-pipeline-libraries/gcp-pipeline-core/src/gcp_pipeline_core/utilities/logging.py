"""
Structured JSON Logging for GCP Cloud Logging.

Provides consistent, machine-readable JSON logging for all pipeline components.
Automatically includes context fields (run_id, system_id, entity_type) in all log entries.

Features:
- JSON-formatted output for Cloud Logging parsing
- Automatic context injection (run_id, system_id, entity_type)
- Thread-safe context management
- Standard severity levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Extra fields support for business metrics

Example:
    >>> from gcp_pipeline_core.utilities.logging import configure_structured_logging
    >>>
    >>> logger = configure_structured_logging(
    ...     run_id="application1_20260105_143022_abc123",
    ...     system_id="Application1",
    ...     entity_type="customers"
    ... )
    >>> logger.info("Processing started", records=1000)
    # Output: {"timestamp": "2026-01-05T14:30:22.123Z", "level": "INFO",
    #          "message": "Processing started", "run_id": "application1_20260105_143022_abc123",
    #          "system_id": "Application1", "entity_type": "customers", "records": 1000}
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from threading import local
from contextvars import ContextVar

# Thread-local context for run_id, system_id, entity_type
_log_context: ContextVar[Dict[str, Any]] = ContextVar('log_context', default={})


class StructuredJsonFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Outputs log records as JSON objects with standard fields:
    - timestamp: ISO 8601 format with timezone
    - level: Log level (INFO, ERROR, etc.)
    - message: Log message
    - logger: Logger name
    - module: Source module
    - run_id: Pipeline run ID (from context)
    - system_id: System identifier (e.g., Application1, Application2)
    - entity_type: Entity being processed
    - Additional fields passed as extras
    """

    RESERVED_ATTRS = {
        'name', 'msg', 'args', 'created', 'filename', 'funcName',
        'levelname', 'levelno', 'lineno', 'module', 'msecs',
        'pathname', 'process', 'processName', 'relativeCreated',
        'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
        'taskName', 'message',
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Get context
        context = _log_context.get()

        # Build base log entry
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add context fields
        if context:
            log_entry.update(context)

        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in self.RESERVED_ATTRS and not key.startswith('_'):
                log_entry[key] = value

        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


class StructuredLogger:
    """
    Structured logger with automatic context injection.

    Wraps a standard Python logger and automatically includes
    run_id, system_id, and entity_type in all log entries.

    Example:
        >>> logger = StructuredLogger("my_pipeline", run_id="run_123", system_id="Application1")
        >>> logger.info("Processing", records=100, stage="validation")
        # Output includes all context plus extra fields
    """

    def __init__(
        self,
        name: str,
        run_id: Optional[str] = None,
        system_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        level: int = logging.INFO
    ):
        """
        Initialize structured logger.

        Args:
            name: Logger name
            run_id: Pipeline run identifier
            system_id: System identifier (e.g., Application1, Application2)
            entity_type: Entity being processed (e.g., customers, accounts)
            level: Logging level (default: INFO)
        """
        self.name = name
        self.run_id = run_id
        self.system_id = system_id
        self.entity_type = entity_type

        # Get or create logger
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)

        # Set context
        self._update_context()

    def _update_context(self):
        """Update the context var with current values."""
        context = {}
        if self.run_id:
            context['run_id'] = self.run_id
        if self.system_id:
            context['system_id'] = self.system_id
        if self.entity_type:
            context['entity_type'] = self.entity_type
        _log_context.set(context)

    def set_context(
        self,
        run_id: Optional[str] = None,
        system_id: Optional[str] = None,
        entity_type: Optional[str] = None
    ):
        """
        Update logging context.

        Args:
            run_id: Pipeline run identifier
            system_id: System identifier
            entity_type: Entity being processed
        """
        if run_id is not None:
            self.run_id = run_id
        if system_id is not None:
            self.system_id = system_id
        if entity_type is not None:
            self.entity_type = entity_type
        self._update_context()

    def _log(self, level: int, message: str, **kwargs):
        """Log with extra fields."""
        extra = kwargs.copy()
        exc_info = extra.pop('exc_info', None)
        self._logger.log(level, message, extra=extra, exc_info=exc_info)

    def debug(self, message: str, **kwargs):
        """Log debug message with optional extra fields."""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message with optional extra fields."""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message with optional extra fields."""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message with optional extra fields."""
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical message with optional extra fields."""
        self._log(logging.CRITICAL, message, **kwargs)

    def exception(self, message: str, **kwargs):
        """Log exception with traceback."""
        extra = kwargs.copy()
        exc_info = extra.pop('exc_info', True)  # Default to True for exception
        self._logger.exception(message, extra=extra, exc_info=exc_info)


def configure_structured_logging(
    run_id: Optional[str] = None,
    system_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    level: int = logging.INFO,
    logger_name: str = "gcp_pipeline",
    stream: Any = None
) -> StructuredLogger:
    """
    Configure structured JSON logging for the application.

    Sets up a JSON formatter on the root logger and returns a
    StructuredLogger instance with context pre-configured.

    Args:
        run_id: Pipeline run identifier
        system_id: System identifier (Application1, Application2)
        entity_type: Entity being processed
        level: Logging level (default: INFO)
        logger_name: Name for the logger
        stream: Output stream (default: sys.stdout)

    Returns:
        StructuredLogger instance configured with context

    Example:
        >>> logger = configure_structured_logging(
        ...     run_id="application1_20260105_143022",
        ...     system_id="Application1",
        ...     entity_type="customers"
        ... )
        >>> logger.info("Pipeline started")
        >>> logger.info("Processing records", count=1000, stage="validation")
    """
    if stream is None:
        stream = sys.stdout

    # Get or create the logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create JSON handler
    handler = logging.StreamHandler(stream)
    handler.setLevel(level)
    handler.setFormatter(StructuredJsonFormatter())
    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return StructuredLogger(
        name=logger_name,
        run_id=run_id,
        system_id=system_id,
        entity_type=entity_type,
        level=level
    )


def get_logger(name: str = "gcp_pipeline") -> StructuredLogger:
    """
    Get an existing structured logger by name.

    Args:
        name: Logger name

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name=name)


__all__ = [
    'StructuredLogger',
    'StructuredJsonFormatter',
    'configure_structured_logging',
    'get_logger',
]

