"""
DLQ (Dead Letter Queue) Publishing Utilities.

Functions for publishing error messages to Pub/Sub DLQ.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from .types import ErrorHandlerConfig, ErrorType, get_default_config

logger = logging.getLogger(__name__)


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
    cfg = config or get_default_config()
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
    cfg = config or get_default_config()

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
    cfg = config or get_default_config()

    if not cfg.enable_dlq:
        logger.info("DLQ publishing disabled")
        return None

    try:
        from gcp_pipeline_builder.clients.pubsub_client import PubSubClient

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


__all__ = [
    '_get_project_id',
    '_build_error_payload',
    'publish_to_dlq',
]

