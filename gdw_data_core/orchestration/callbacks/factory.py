"""
Error Handler Factory.

Factory function and class for creating configured error handlers.
"""

import logging
from typing import Dict, Any, Optional, List

from .types import ErrorHandlerConfig, ErrorType
from .dlq import publish_to_dlq
from .quarantine import quarantine_file
from .handlers import (
    on_failure_callback,
    on_validation_failure,
    on_routing_failure,
    on_schema_mismatch,
    on_data_quality_failure,
)

logger = logging.getLogger(__name__)


class ErrorHandler:
    """
    Error handler instance with custom configuration.

    Use this class when you need project-specific error handling configuration.

    Example:
        >>> config = ErrorHandlerConfig(
        ...     dlq_topic="my-project-dlq",
        ...     quarantine_bucket="my-quarantine",
        ... )
        >>> handler = ErrorHandler(config)
        >>> handler.on_validation_failure(context, errors, file_path)
    """

    def __init__(self, config: ErrorHandlerConfig):
        """Initialize with custom configuration."""
        self.config = config

    def publish_to_dlq(
        self,
        context: Dict[str, Any],
        error_message: str,
        error_type: str = ErrorType.TASK_FAILURE,
        metadata: Optional[Dict[str, Any]] = None,
        topic: Optional[str] = None
    ) -> Optional[str]:
        """Publish to DLQ with this handler's config."""
        return publish_to_dlq(context, error_message, error_type, metadata, topic, self.config)

    def on_failure_callback(self, context: Dict[str, Any]) -> None:
        """Handle task failure."""
        return on_failure_callback(context, self.config)

    def on_validation_failure(
        self,
        context: Dict[str, Any],
        validation_errors: List[str],
        file_path: str,
        quarantine: Optional[bool] = None
    ) -> Optional[str]:
        """Handle validation failure."""
        return on_validation_failure(context, validation_errors, file_path, quarantine, self.config)

    def on_routing_failure(
        self,
        context: Dict[str, Any],
        file_path: str,
        reason: str
    ) -> Optional[str]:
        """Handle routing failure."""
        return on_routing_failure(context, file_path, reason, self.config)

    def quarantine_file(
        self,
        context: Dict[str, Any],
        file_path: str,
        reason: str = "unknown",
        quarantine_bucket: Optional[str] = None
    ) -> Optional[str]:
        """Quarantine a file."""
        return quarantine_file(context, file_path, reason, quarantine_bucket, self.config)

    def on_schema_mismatch(
        self,
        context: Dict[str, Any],
        file_path: str,
        expected_columns: List[str],
        actual_columns: List[str]
    ) -> Optional[str]:
        """Handle schema mismatch."""
        return on_schema_mismatch(context, file_path, expected_columns, actual_columns, self.config)

    def on_data_quality_failure(
        self,
        context: Dict[str, Any],
        table_name: str,
        quality_checks: Dict[str, Any]
    ) -> Optional[str]:
        """Handle data quality failure."""
        return on_data_quality_failure(context, table_name, quality_checks, self.config)


def create_error_handler(config: ErrorHandlerConfig) -> ErrorHandler:
    """
    Create an error handler with custom configuration.

    Args:
        config: Error handler configuration

    Returns:
        Configured ErrorHandler instance

    Example:
        >>> config = ErrorHandlerConfig(dlq_topic="my-dlq")
        >>> handler = create_error_handler(config)
    """
    return ErrorHandler(config)


__all__ = [
    'ErrorHandler',
    'create_error_handler',
]

