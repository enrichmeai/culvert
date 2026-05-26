"""
Callback Handlers for Airflow DAGs.

Functions that handle various error scenarios in Airflow pipelines.
"""

import logging
from typing import Dict, Any, Optional, List, Union

from .types import ErrorHandlerConfig, ErrorType, get_default_config
from .dlq import publish_to_dlq
from .quarantine import quarantine_file

logger = logging.getLogger(__name__)


def on_failure_callback(
    context: Dict[str, Any],
    config: Optional[ErrorHandlerConfig] = None,
) -> None:
    """
    Callback for task failure - publishes to DLQ.

    Use this as the on_failure_callback for any task that should
    report failures to the Dead Letter Queue.

    Args:
        context: Airflow task context
        config: Error handler configuration
    """
    try:
        exception = context.get("exception")
        error_message = str(exception) if exception else "Unknown error"
        task_id = context.get("ti").task_id if context.get("ti") else "unknown"

        logger.error(f"Task {task_id} failed: {error_message}")

        publish_to_dlq(
            context=context,
            error_message=error_message,
            error_type=ErrorType.TASK_FAILURE,
            metadata={
                "exception_type": type(exception).__name__ if exception else None,
            },
            config=config,
        )
    except Exception as e:
        logger.error(f"Error in failure callback: {e}")


def on_validation_failure(
    context: Dict[str, Any],
    validation_errors: Union[List[str], str],
    file_path: str,
    quarantine: Optional[bool] = None,
    config: Optional[ErrorHandlerConfig] = None,
) -> Optional[str]:
    """
    Handler for validation failures - publishes to DLQ with details.

    Args:
        context: Airflow task context
        validation_errors: List of validation error messages or single error string
        file_path: Path to the file that failed validation
        quarantine: Whether to quarantine file (None uses config default)
        config: Error handler configuration

    Returns:
        Message ID from DLQ publish, or None if failed
    """
    cfg = config or get_default_config()

    if isinstance(validation_errors, str):
        validation_errors = [validation_errors]

    error_message = f"Validation failed for {file_path}: {'; '.join(validation_errors)}"
    logger.error(error_message)

    # Optionally quarantine the file
    should_quarantine = quarantine if quarantine is not None else cfg.enable_quarantine
    if should_quarantine:
        try:
            quarantine_file(context, file_path, reason="validation_failure", config=cfg)
        except Exception as e:
            logger.warning(f"Could not quarantine file {file_path}: {e}")

    return publish_to_dlq(
        context=context,
        error_message=error_message,
        error_type=ErrorType.VALIDATION_FAILURE,
        metadata={
            "file_path": file_path,
            "validation_errors": validation_errors,
            "error_count": len(validation_errors),
        },
        config=cfg,
    )


def on_routing_failure(
    context: Dict[str, Any],
    file_path: str,
    reason: str,
    config: Optional[ErrorHandlerConfig] = None,
) -> Optional[str]:
    """
    Handler for routing failures - publishes to DLQ.

    Args:
        context: Airflow task context
        file_path: Path to the file that couldn't be routed
        reason: Reason for routing failure
        config: Error handler configuration

    Returns:
        Message ID from DLQ publish, or None if failed
    """
    error_message = f"Routing failed for {file_path}: {reason}"
    logger.error(error_message)

    return publish_to_dlq(
        context=context,
        error_message=error_message,
        error_type=ErrorType.ROUTING_FAILURE,
        metadata={
            "file_path": file_path,
            "routing_reason": reason,
        },
        config=config,
    )


def on_schema_mismatch(
    context: Dict[str, Any],
    file_path: str,
    expected_columns: List[str],
    actual_columns: List[str],
    config: Optional[ErrorHandlerConfig] = None,
) -> Optional[str]:
    """
    Handler for schema mismatch errors.

    Args:
        context: Airflow task context
        file_path: Path to the file with schema issues
        expected_columns: Expected column names
        actual_columns: Actual column names found
        config: Error handler configuration

    Returns:
        Message ID from DLQ publish, or None if failed
    """
    missing_cols = set(expected_columns) - set(actual_columns)
    extra_cols = set(actual_columns) - set(expected_columns)

    error_message = f"Schema mismatch for {file_path}"
    if missing_cols:
        error_message += f" - Missing columns: {missing_cols}"
    if extra_cols:
        error_message += f" - Unexpected columns: {extra_cols}"

    logger.error(error_message)

    return publish_to_dlq(
        context=context,
        error_message=error_message,
        error_type=ErrorType.SCHEMA_MISMATCH,
        metadata={
            "file_path": file_path,
            "expected_columns": expected_columns,
            "actual_columns": actual_columns,
            "missing_columns": list(missing_cols),
            "extra_columns": list(extra_cols),
        },
        config=config,
    )


def on_data_quality_failure(
    context: Dict[str, Any],
    table_name: str,
    quality_checks: Dict[str, Any],
    config: Optional[ErrorHandlerConfig] = None,
) -> Optional[str]:
    """
    Handler for data quality check failures.

    Args:
        context: Airflow task context
        table_name: Name of the table that failed quality checks
        quality_checks: Dictionary of check names to results
        config: Error handler configuration

    Returns:
        Message ID from DLQ publish, or None if failed
    """
    failed_checks = {k: v for k, v in quality_checks.items() if not v.get("passed", True)}

    error_message = f"Data quality checks failed for {table_name}: {list(failed_checks.keys())}"
    logger.error(error_message)

    return publish_to_dlq(
        context=context,
        error_message=error_message,
        error_type=ErrorType.DATA_QUALITY_FAILURE,
        metadata={
            "table_name": table_name,
            "failed_checks": failed_checks,
            "total_checks": len(quality_checks),
            "failed_count": len(failed_checks),
        },
        config=config,
    )


__all__ = [
    'on_failure_callback',
    'on_validation_failure',
    'on_routing_failure',
    'on_schema_mismatch',
    'on_data_quality_failure',
]

