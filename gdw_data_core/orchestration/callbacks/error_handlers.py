"""
Error Handlers for Airflow DAGs.

Provides reusable callbacks and utilities for:
- Dead Letter Queue (DLQ) publishing on validation failure
- Error notification
- Quarantine file handling
- Standardized error logging

This is a reusable module. Configuration can be customized per project.

Usage:
    # With default configuration
    from gdw_data_core.orchestration.callbacks import on_failure_callback

    task = PythonOperator(
        task_id='process_data',
        python_callable=process_fn,
        on_failure_callback=on_failure_callback,
    )

    # With custom configuration
    from gdw_data_core.orchestration.callbacks import create_error_handler

    config = ErrorHandlerConfig(
        dlq_topic="my-project-dlq",
        quarantine_bucket="my-quarantine",
        project_id_var="my_project_id",
    )
    handler = create_error_handler(config)
    handler.on_validation_failure(context, errors, file_path)
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)


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


# Default configuration - can be overridden
_default_config = ErrorHandlerConfig()


def set_default_config(config: ErrorHandlerConfig) -> None:
    """Set the default error handler configuration."""
    global _default_config
    _default_config = config


def get_default_config() -> ErrorHandlerConfig:
    """Get the current default error handler configuration."""
    return _default_config


class ErrorType:
    """Error type constants for DLQ messages."""

    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    ROUTING_FAILURE = "ROUTING_FAILURE"
    TASK_FAILURE = "TASK_FAILURE"
    PROCESSING_FAILURE = "PROCESSING_FAILURE"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    DATA_QUALITY_FAILURE = "DATA_QUALITY_FAILURE"


def _get_project_id(
    context: Optional[Dict[str, Any]] = None,
    config: Optional[ErrorHandlerConfig] = None,
) -> str:
    """
    Get GCP project ID from Airflow variable or environment.

    Args:
        context: Airflow context (optional)
        config: Error handler configuration

    Returns:
        Project ID string
    """
    cfg = config or _default_config
    try:
        from airflow.models import Variable
        return Variable.get(cfg.project_id_var)
    except Exception:
        import os
        return os.environ.get("GCP_PROJECT_ID", "")


def _build_error_payload(
    error_type: str,
    error_message: str,
    context: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    config: Optional[ErrorHandlerConfig] = None,
) -> Dict[str, Any]:
    """
    Build standardized error payload for DLQ.

    Args:
        error_type: Type of error (from ErrorType constants)
        error_message: Human-readable error description
        context: Airflow context
        metadata: Additional metadata to include
        config: Error handler configuration

    Returns:
        Error payload dictionary
    """
    cfg = config or _default_config

    payload = {
        "error_type": error_type,
        "error_message": error_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata or {},
    }

    # Add context information if available
    if context:
        try:
            ti = context.get("ti") or context.get("task_instance")
            if ti:
                payload["dag_id"] = getattr(ti, "dag_id", None) or context.get("dag", {}).dag_id
                payload["task_id"] = ti.task_id
                payload["run_id"] = context.get("run_id")
                payload["execution_date"] = context.get("execution_date").isoformat() if context.get("execution_date") else None
                payload["try_number"] = getattr(ti, "try_number", None)

                # Try to get routing metadata from XCom
                try:
                    routing_metadata = ti.xcom_pull(key=cfg.routing_metadata_key)
                    if routing_metadata:
                        payload["file_path"] = routing_metadata.get("gcs_path")
                        payload["entity_type"] = routing_metadata.get("entity_type")
                        payload["system_id"] = routing_metadata.get("system_id")
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Error extracting context info: {e}")

    return payload


def publish_to_dlq(
    context: Dict[str, Any],
    error_message: str,
    error_type: str = ErrorType.TASK_FAILURE,
    metadata: Optional[Dict[str, Any]] = None,
    topic: Optional[str] = None,
    config: Optional[ErrorHandlerConfig] = None,
) -> Optional[str]:
    """
    Publish error event to Dead Letter Queue.

    Args:
        context: Airflow task context
        error_message: Error description
        error_type: Type of error (use ErrorType constants)
        metadata: Additional metadata
        topic: DLQ topic name (overrides config)
        config: Error handler configuration

    Returns:
        Message ID from Pub/Sub, or None if publishing failed
    """
    cfg = config or _default_config

    if not cfg.enable_dlq:
        logger.info("DLQ publishing disabled")
        return None

    try:
        from gdw_data_core.core.clients.pubsub_client import PubSubClient

        project_id = _get_project_id(context, cfg)
        if not project_id:
            logger.error("Could not determine GCP project ID")
            return None

        # Build error payload
        error_payload = _build_error_payload(
            error_type=error_type,
            error_message=error_message,
            context=context,
            metadata=metadata,
            config=cfg,
        )

        # Use provided topic or default from config
        dlq_topic = topic or cfg.dlq_topic

        # Publish to DLQ
        client = PubSubClient(project=project_id)
        message_id = client.publish_event(
            topic=dlq_topic,
            message=error_payload,
            error_type=error_type,
            dag_id=error_payload.get("dag_id", "unknown"),
        )

        logger.info(
            f"Published error to DLQ: message_id={message_id}, "
            f"error_type={error_type}, topic={dlq_topic}"
        )
        return message_id

    except ImportError:
        logger.error("Could not import PubSubClient - DLQ publishing not available")
        return None
    except Exception as e:
        logger.error(f"Failed to publish to DLQ: {e}")
        return None


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
    cfg = config or _default_config

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
        file_path: Path to the file that could not be routed
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


def quarantine_file(
    context: Dict[str, Any],
    file_path: str,
    reason: str = "unknown",
    quarantine_bucket: Optional[str] = None,
    config: Optional[ErrorHandlerConfig] = None,
) -> Optional[str]:
    """
    Move a file to the quarantine bucket.

    Args:
        context: Airflow task context
        file_path: GCS path to the file (gs://bucket/path/file.ext)
        reason: Reason for quarantine
        quarantine_bucket: Target bucket (overrides config)
        config: Error handler configuration

    Returns:
        New file path in quarantine bucket, or None if failed
    """
    cfg = config or _default_config

    if not cfg.enable_quarantine:
        logger.info("Quarantine disabled")
        return None

    try:
        from google.cloud import storage

        project_id = _get_project_id(context, cfg)
        if not project_id:
            logger.error("Could not determine GCP project ID")
            return None

        # Parse source path
        if not file_path.startswith("gs://"):
            logger.error(f"Invalid GCS path: {file_path}")
            return None

        path_parts = file_path.replace("gs://", "").split("/", 1)
        if len(path_parts) != 2:
            logger.error(f"Could not parse GCS path: {file_path}")
            return None

        source_bucket_name = path_parts[0]
        source_blob_name = path_parts[1]

        # Generate quarantine path with timestamp and reason
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        quarantine_blob_name = f"{reason}/{timestamp}/{source_blob_name}"

        # Use provided bucket or default from config
        dest_bucket_name = quarantine_bucket or cfg.quarantine_bucket

        # Use storage client directly for copy and delete
        client = storage.Client(project=project_id)
        source_bucket = client.bucket(source_bucket_name)
        source_blob = source_bucket.blob(source_blob_name)

        dest_bucket = client.bucket(dest_bucket_name)

        # Copy to quarantine bucket
        source_bucket.copy_blob(source_blob, dest_bucket, quarantine_blob_name)

        # Delete original
        source_blob.delete()

        new_path = f"gs://{dest_bucket_name}/{quarantine_blob_name}"
        logger.info(f"Quarantined file: {file_path} -> {new_path}")

        return new_path

    except ImportError:
        logger.error("Could not import google.cloud.storage - quarantine not available")
        return None
    except Exception as e:
        logger.error(f"Failed to quarantine file {file_path}: {e}")
        return None


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


class ErrorHandler:
    """
    Error handler instance with custom configuration.

    Use this class when you need project-specific error handling configuration.
    """

    def __init__(self, config: ErrorHandlerConfig):
        """Initialize with custom configuration."""
        self.config = config

    def publish_to_dlq(self, context, error_message, error_type=ErrorType.TASK_FAILURE, metadata=None, topic=None):
        return publish_to_dlq(context, error_message, error_type, metadata, topic, self.config)

    def on_failure_callback(self, context):
        return on_failure_callback(context, self.config)

    def on_validation_failure(self, context, validation_errors, file_path, quarantine=None):
        return on_validation_failure(context, validation_errors, file_path, quarantine, self.config)

    def on_routing_failure(self, context, file_path, reason):
        return on_routing_failure(context, file_path, reason, self.config)

    def quarantine_file(self, context, file_path, reason="unknown", quarantine_bucket=None):
        return quarantine_file(context, file_path, reason, quarantine_bucket, self.config)

    def on_schema_mismatch(self, context, file_path, expected_columns, actual_columns):
        return on_schema_mismatch(context, file_path, expected_columns, actual_columns, self.config)

    def on_data_quality_failure(self, context, table_name, quality_checks):
        return on_data_quality_failure(context, table_name, quality_checks, self.config)


def create_error_handler(config: ErrorHandlerConfig) -> ErrorHandler:
    """
    Create an error handler with custom configuration.

    Args:
        config: Error handler configuration

    Returns:
        Configured ErrorHandler instance
    """
    return ErrorHandler(config)

