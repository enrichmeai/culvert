"""
GCS File Discovery Module
Utilities for discovering and managing split files in Google Cloud Storage.
"""

import re
import logging
from typing import List, Optional, Any

logger = logging.getLogger(__name__)

def build_gcs_path(bucket: str, *parts: str) -> str:
    """
    Build a properly formatted GCS path.

    Args:
        bucket: GCS bucket name
        *parts: Path components to join

    Returns:
        Full gs:// path
    """
    # Remove leading/trailing slashes from parts and filter empty parts
    clean_parts = [p.strip("/") for p in parts if p and p.strip("/")]
    path = "/".join(clean_parts)

    # If the original last part ended with a slash, preserve it (optional)
    if parts and parts[-1].endswith("/") and path:
        path += "/"

    return f"gs://{bucket}/{path}" if path else f"gs://{bucket}"

def discover_split_files(gcs_client: Any, bucket: str, prefix: str, pattern: Optional[str] = None) -> List[str]:
    """
    Find split files in GCS that match a given prefix and optional pattern.

    Args:
        gcs_client: GCS client instance (must have list_prefix method)
        bucket: GCS bucket name
        prefix: Path prefix to search
        pattern: Optional regex pattern to filter files

    Returns:
        Sorted list of matching GCS paths
    """
    try:
        files = gcs_client.list_prefix(bucket, prefix)
        if not files:
            return []

        if pattern:
            regex = re.compile(pattern)
            files = [f for f in files if regex.search(f)]

        return sorted(files)
    except Exception as e:
        logger.error(f"Error discovering split files: {e}")
        return []

def discover_files_by_date(gcs_client: Any, bucket: str, prefix: str, date_pattern: str = "%Y-%m-%d") -> List[str]:
    """
    Find files organized by date in GCS.

    Args:
        gcs_client: GCS client instance
        bucket: GCS bucket name
        prefix: Path prefix to search
        date_pattern: Date pattern to expect in the path

    Returns:
        Sorted list of matching GCS paths
    """
    # For now, simple discovery of files under the prefix
    try:
        files = gcs_client.list_prefix(bucket, prefix)
        return sorted(files)
    except Exception as e:
        logger.error(f"Error discovering files by date: {e}")
        return []
