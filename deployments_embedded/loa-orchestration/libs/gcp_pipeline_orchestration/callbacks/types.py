"""
Error Handler Types and Configuration.

Contains dataclasses and constants for error handling.
"""

from dataclasses import dataclass


@dataclass
class ErrorHandlerConfig:
    """
    Configuration for error handlers.

    Customize these values for project-specific DLQ topics, quarantine buckets, etc.

    Attributes:
        dlq_topic: Pub/Sub topic for Dead Letter Queue
        quarantine_bucket: GCS bucket for quarantined files
        project_id_var: Airflow variable name for GCP project ID
        routing_metadata_key: XCom key for routing metadata
        enable_quarantine: Whether to quarantine files on validation failure
        enable_dlq: Whether to publish to DLQ on errors
    """

    dlq_topic: str = "notifications-dead-letter"
    quarantine_bucket: str = "quarantine"
    project_id_var: str = "gcp_project_id"
    routing_metadata_key: str = "routing_metadata"
    enable_quarantine: bool = True
    enable_dlq: bool = True


class ErrorType:
    """Error type constants for DLQ messages."""

    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    ROUTING_FAILURE = "ROUTING_FAILURE"
    TASK_FAILURE = "TASK_FAILURE"
    PROCESSING_FAILURE = "PROCESSING_FAILURE"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    DATA_QUALITY_FAILURE = "DATA_QUALITY_FAILURE"


# Default configuration - can be overridden
_default_config = ErrorHandlerConfig()


def set_default_config(config: ErrorHandlerConfig) -> None:
    """Set the default error handler configuration."""
    global _default_config
    _default_config = config


def get_default_config() -> ErrorHandlerConfig:
    """Get the current default error handler configuration."""
    return _default_config


__all__ = [
    'ErrorHandlerConfig',
    'ErrorType',
    'set_default_config',
    'get_default_config',
]

