"""
LOA Error Handlers - Project-Specific Extensions.

Extends the base error handlers from gdw_data_core with LOA-specific defaults:
- LOA DLQ topic ('loa-notifications-dead-letter')
- LOA quarantine bucket ('loa-quarantine')
- LOA routing metadata key ('loa_metadata')

For the base reusable implementation, see:
    gdw_data_core.orchestration.callbacks.error_handlers

Usage:
    # Use LOA-specific handlers directly
    from blueprint.components.orchestration.airflow.callbacks import (
        on_failure_callback,
        on_validation_failure,
    )

    task = PythonOperator(
        task_id='process_data',
        python_callable=process_fn,
        on_failure_callback=on_failure_callback,
    )

    # Or use the LOA error handler instance
    from blueprint.components.orchestration.airflow.callbacks import loa_error_handler

    loa_error_handler.on_validation_failure(context, errors, file_path)
"""

import logging
from typing import Dict, Any, Optional, List, Union

# Import base classes from library
from gdw_data_core.orchestration.callbacks import (
    ErrorType,
    ErrorHandlerConfig,
    ErrorHandler,
    create_error_handler,
    publish_to_dlq as base_publish_to_dlq,
    on_failure_callback as base_on_failure_callback,
    on_validation_failure as base_on_validation_failure,
    on_routing_failure as base_on_routing_failure,
    quarantine_file as base_quarantine_file,
    on_schema_mismatch as base_on_schema_mismatch,
    on_data_quality_failure as base_on_data_quality_failure,
)

logger = logging.getLogger(__name__)

# LOA-specific configuration
LOA_ERROR_CONFIG = ErrorHandlerConfig(
    dlq_topic="loa-notifications-dead-letter",
    quarantine_bucket="loa-quarantine",
    project_id_var="gcp_project_id",
    routing_metadata_key="loa_metadata",
    enable_quarantine=True,
    enable_dlq=True,
)

# Create LOA-specific error handler instance
loa_error_handler = create_error_handler(LOA_ERROR_CONFIG)

# Re-export base types for convenience
__all__ = [
    # LOA-specific
    "LOA_ERROR_CONFIG",
    "loa_error_handler",
    # Wrapped functions with LOA defaults
    "publish_to_dlq",
    "on_failure_callback",
    "on_validation_failure",
    "on_routing_failure",
    "quarantine_file",
    "on_schema_mismatch",
    "on_data_quality_failure",
    # Base types
    "ErrorType",
    "ErrorHandlerConfig",
]


def publish_to_dlq(
    context: Dict[str, Any],
    error_message: str,
    error_type: str = ErrorType.TASK_FAILURE,
    metadata: Optional[Dict[str, Any]] = None,
    topic: Optional[str] = None,
) -> Optional[str]:
    """
    Publish error event to LOA Dead Letter Queue.

    Uses LOA-specific defaults (loa-notifications-dead-letter topic).

    Args:
        context: Airflow task context
        error_message: Error description
        error_type: Type of error (use ErrorType constants)
        metadata: Additional metadata
        topic: DLQ topic name (overrides LOA default)

    Returns:
        Message ID from Pub/Sub, or None if publishing failed
    """
    return base_publish_to_dlq(
        context=context,
        error_message=error_message,
        error_type=error_type,
        metadata=metadata,
        topic=topic,
        config=LOA_ERROR_CONFIG,
    )


def on_failure_callback(context: Dict[str, Any]) -> None:
    """
    LOA callback for task failure - publishes to LOA DLQ.

    Use this as the on_failure_callback for LOA tasks.

    Args:
        context: Airflow task context
    """
    base_on_failure_callback(context, config=LOA_ERROR_CONFIG)


def on_validation_failure(
    context: Dict[str, Any],
    validation_errors: Union[List[str], str],
    file_path: str,
    quarantine: bool = True,
) -> Optional[str]:
    """
    LOA handler for validation failures.

    Uses LOA-specific DLQ and quarantine bucket.

    Args:
        context: Airflow task context
        validation_errors: List of validation error messages or single error string
        file_path: Path to the file that failed validation
        quarantine: Whether to quarantine file

    Returns:
        Message ID from DLQ publish, or None if failed
    """
    return base_on_validation_failure(
        context=context,
        validation_errors=validation_errors,
        file_path=file_path,
        quarantine=quarantine,
        config=LOA_ERROR_CONFIG,
    )


def on_routing_failure(
    context: Dict[str, Any],
    file_path: str,
    reason: str,
) -> Optional[str]:
    """
    LOA handler for routing failures.

    Args:
        context: Airflow task context
        file_path: Path to the file that could not be routed
        reason: Reason for routing failure

    Returns:
        Message ID from DLQ publish, or None if failed
    """
    return base_on_routing_failure(
        context=context,
        file_path=file_path,
        reason=reason,
        config=LOA_ERROR_CONFIG,
    )


def quarantine_file(
    context: Dict[str, Any],
    file_path: str,
    reason: str = "unknown",
    quarantine_bucket: Optional[str] = None,
) -> Optional[str]:
    """
    Move a file to the LOA quarantine bucket.

    Args:
        context: Airflow task context
        file_path: GCS path to the file
        reason: Reason for quarantine
        quarantine_bucket: Target bucket (defaults to loa-quarantine)

    Returns:
        New file path in quarantine bucket, or None if failed
    """
    return base_quarantine_file(
        context=context,
        file_path=file_path,
        reason=reason,
        quarantine_bucket=quarantine_bucket,
        config=LOA_ERROR_CONFIG,
    )


def on_schema_mismatch(
    context: Dict[str, Any],
    file_path: str,
    expected_columns: List[str],
    actual_columns: List[str],
) -> Optional[str]:
    """
    LOA handler for schema mismatch errors.

    Args:
        context: Airflow task context
        file_path: Path to the file with schema issues
        expected_columns: Expected column names
        actual_columns: Actual column names found

    Returns:
        Message ID from DLQ publish, or None if failed
    """
    return base_on_schema_mismatch(
        context=context,
        file_path=file_path,
        expected_columns=expected_columns,
        actual_columns=actual_columns,
        config=LOA_ERROR_CONFIG,
    )


def on_data_quality_failure(
    context: Dict[str, Any],
    table_name: str,
    quality_checks: Dict[str, Any],
) -> Optional[str]:
    """
    LOA handler for data quality check failures.

    Args:
        context: Airflow task context
        table_name: Name of the table that failed quality checks
        quality_checks: Dictionary of check names to results

    Returns:
        Message ID from DLQ publish, or None if failed
    """
    return base_on_data_quality_failure(
        context=context,
        table_name=table_name,
        quality_checks=quality_checks,
        config=LOA_ERROR_CONFIG,
    )

