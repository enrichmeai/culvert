"""
File Quarantine Utilities.

Functions for moving files to quarantine bucket on validation failures.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from .types import ErrorHandlerConfig, get_default_config
from .dlq import _get_project_id

logger = logging.getLogger(__name__)


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
    cfg = config or get_default_config()

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


__all__ = [
    'quarantine_file',
]

