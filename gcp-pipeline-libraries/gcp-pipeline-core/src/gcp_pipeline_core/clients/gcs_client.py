"""
GCS Client - Google Cloud Storage Operations
Handles all GCS read/write/list operations with error handling.
"""

from typing import List
import logging
from google.cloud import storage
from google.api_core.exceptions import GoogleAPIError

logger = logging.getLogger(__name__)


class GCSClient:
    """Google Cloud Storage client with real implementation."""

    def __init__(self, project: str = None):
        """Initialize GCS client.

        Args:
            project: GCP project ID (optional, uses default credentials if
                     not provided)
        """
        self.project = project
        try:
            self.client = storage.Client(project=project)
            logger.info("GCSClient initialized for project: %s", project)
        except Exception as exc:
            logger.error("Failed to initialize GCS client: %s", exc)
            raise

    def file_exists(self, bucket: str, path: str) -> bool:
        """Check if a file exists in GCS.

        Args:
            bucket: GCS bucket name
            path: Path to file in bucket

        Returns:
            True if file exists, False otherwise
        """
        try:
            bucket_obj = self.client.bucket(bucket)
            blob = bucket_obj.blob(path)
            exists = blob.exists()
            logger.debug("File existence check %s/%s: %s", bucket, path, exists)
            return exists
        except GoogleAPIError as exc:
            logger.error("GCS API error checking existence of %s/%s: %s",
                        bucket, path, exc)
            return False
        except Exception as exc:
            logger.error("Error checking existence of %s/%s: %s",
                        bucket, path, exc)
            return False

    def blob_exists(self, gcs_uri: str) -> bool:
        """Check if a blob exists given a full GCS URI.

        Args:
            gcs_uri: Full GCS URI (gs://bucket/path/to/file)

        Returns:
            True if blob exists, False otherwise

        Raises:
            ValueError: If URI format is invalid
        """
        if not gcs_uri.startswith("gs://"):
            raise ValueError(f"Invalid GCS URI format: {gcs_uri}")

        # Parse gs://bucket/path format
        parts = gcs_uri[5:].split("/", 1)
        bucket = parts[0]
        path = parts[1] if len(parts) > 1 else ""

        return self.file_exists(bucket, path)

    def validate_files_exist(self, bucket: str, paths: List[str]) -> dict:
        """Validate multiple files exist in GCS.

        Args:
            bucket: GCS bucket name
            paths: List of file paths to check

        Returns:
            Dict with 'existing', 'missing', and 'all_exist' keys
        """
        existing = []
        missing = []

        for path in paths:
            if self.file_exists(bucket, path):
                existing.append(path)
            else:
                missing.append(path)

        result = {
            'existing': existing,
            'missing': missing,
            'all_exist': len(missing) == 0,
            'total': len(paths),
            'found': len(existing)
        }

        logger.info("File validation: %d/%d files exist in %s",
                   len(existing), len(paths), bucket)

        return result

    def read_file(self, bucket: str, path: str) -> str:
        """Read file from GCS.

        Args:
            bucket: GCS bucket name
            path: Path to file in bucket

        Returns:
            File content as string

        Raises:
            IOError: If file read fails
        """
        try:
            bucket_obj = self.client.bucket(bucket)
            blob = bucket_obj.blob(path)
            content = blob.download_as_string().decode('utf-8')
            logger.info("Successfully read %s/%s", bucket, path)
            return content
        except GoogleAPIError as exc:
            logger.error("GCS API error reading %s/%s: %s", bucket, path, exc)
            raise IOError(
                f"Failed to read {bucket}/{path}: {exc}") from exc
        except Exception as exc:
            logger.error("Error reading %s/%s: %s", bucket, path, exc)
            raise IOError(
                f"Failed to read {bucket}/{path}: {exc}") from exc

    def write_file(self, bucket: str, path: str, content: str) -> bool:
        """Write file to GCS.

        Args:
            bucket: GCS bucket name
            path: Path to file in bucket
            content: Content to write

        Returns:
            True if write successful

        Raises:
            IOError: If file write fails
        """
        try:
            bucket_obj = self.client.bucket(bucket)
            blob = bucket_obj.blob(path)
            blob.upload_from_string(content)
            logger.info("Successfully wrote to %s/%s", bucket, path)
            return True
        except GoogleAPIError as exc:
            logger.error("GCS API error writing to %s/%s: %s",
                        bucket, path, exc)
            raise IOError(
                f"Failed to write {bucket}/{path}: {exc}") from exc
        except Exception as exc:
            logger.error("Error writing to %s/%s: %s", bucket, path, exc)
            raise IOError(
                f"Failed to write {bucket}/{path}: {exc}") from exc

    def list_files(self, bucket: str, prefix: str = "") -> List[str]:
        """List files in GCS bucket.

        Args:
            bucket: GCS bucket name
            prefix: Optional prefix to filter files

        Returns:
            List of file paths in bucket

        Raises:
            IOError: If listing fails
        """
        try:
            blobs = self.client.list_blobs(bucket, prefix=prefix)
            files = [blob.name for blob in blobs]
            logger.info("Listed %d files in %s/%s", len(files), bucket, prefix)
            return files
        except GoogleAPIError as exc:
            logger.error("GCS API error listing %s/%s: %s",
                        bucket, prefix, exc)
            raise IOError(
                f"Failed to list {bucket}/{prefix}: {exc}") from exc
        except Exception as exc:
            logger.error("Error listing %s/%s: %s", bucket, prefix, exc)
            raise IOError(
                f"Failed to list {bucket}/{prefix}: {exc}") from exc

    def archive_file(self, bucket: str, source_path: str,
                     archive_path: str) -> bool:
        """Archive file by copying to archive location and deleting original.

        Args:
            bucket: GCS bucket name
            source_path: Original file path in bucket
            archive_path: Destination archive path in bucket

        Returns:
            True if archive successful

        Raises:
            IOError: If archive fails
        """
        try:
            bucket_obj = self.client.bucket(bucket)
            source_blob = bucket_obj.blob(source_path)
            bucket_obj.copy_blob(source_blob, bucket_obj, archive_path)
            source_blob.delete()
            logger.info("Archived %s/%s to %s/%s", bucket, source_path,
                       bucket, archive_path)
            return True
        except GoogleAPIError as exc:
            logger.error("GCS API error archiving %s: %s", source_path, exc)
            raise IOError(
                f"Failed to archive {source_path}: {exc}") from exc
        except Exception as exc:
            logger.error("Error archiving %s: %s", source_path, exc)
            raise IOError(
                f"Failed to archive {source_path}: {exc}") from exc
