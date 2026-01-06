"""
File Metadata Module

Extracts and manages file metadata.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError, NotFound

logger = logging.getLogger(__name__)


@dataclass
class FileMetadata:
    """Data class for file metadata."""
    file_path: str
    file_size: int
    created_time: Optional[datetime]
    modified_time: Optional[datetime]
    row_count: int
    columns: List[str]
    checksum: Optional[str]
    extracted_at: str


class FileMetadataExtractor:
    """
    Extracts metadata from files.
    """

    def __init__(self, gcs_bucket: str):
        """
        Initialize metadata extractor.
        """
        self.gcs_bucket = gcs_bucket
        self.storage_client = storage.Client()

    def _get_blob(self, gcs_path: str) -> storage.Blob:
        """
        Get GCS blob object.

        Args:
            gcs_path: Path to file in GCS

        Returns:
            storage.Blob: Blob object

        Raises:
            NotFound: If blob doesn't exist
        """
        bucket = self.storage_client.bucket(self.gcs_bucket)
        return bucket.blob(gcs_path)

    def get_file_size(self, gcs_path: str) -> int:
        """
        Get file size in bytes.
        """
        try:
            blob = self._get_blob(gcs_path)
            blob.reload()  # Ensure metadata is loaded
            return blob.size if blob.size is not None else 0
        except (GoogleCloudError, NotFound, Exception) as e:
            logger.error("Error getting file size for %s: %s", gcs_path, e)
            return 0

    def get_file_created_time(self, gcs_path: str) -> Optional[datetime]:
        """
        Get file creation timestamp.
        """
        try:
            blob = self._get_blob(gcs_path)
            blob.reload()
            return blob.time_created
        except (GoogleCloudError, NotFound, Exception) as e:
            logger.error("Error getting creation time for %s: %s", gcs_path, e)
            return None

    def get_file_modified_time(self, gcs_path: str) -> Optional[datetime]:
        """
        Get file modification timestamp.
        """
        try:
            blob = self._get_blob(gcs_path)
            blob.reload()
            return blob.updated
        except (GoogleCloudError, NotFound, Exception) as e:
            logger.error("Error getting modification time for %s: %s", gcs_path, e)
            return None

    def get_csv_row_count(self, gcs_path: str) -> int:
        """
        Count rows in CSV file (excluding header).
        """
        try:
            blob = self._get_blob(gcs_path)
            content = blob.download_as_string().decode('utf-8')
            lines = content.strip().split('\n')
            # Subtract 1 for header row, return 0 if only header or empty
            return max(0, len(lines) - 1)
        except (GoogleCloudError, NotFound, Exception) as e:
            logger.error("Error counting rows for %s: %s", gcs_path, e)
            return 0

    def get_csv_columns(self, gcs_path: str) -> List[str]:
        """
        Extract column names from CSV header.
        """
        try:
            blob = self._get_blob(gcs_path)
            # Read only first line for efficiency
            content = blob.download_as_string(start=0, end=1024).decode('utf-8')
            if not content.strip():
                return []
            header = content.split('\n')[0]
            columns = [col.strip() for col in header.split(',')]
            # Filter out empty column names
            return [col for col in columns if col]
        except (GoogleCloudError, NotFound, Exception) as e:
            logger.error("Error getting CSV columns for %s: %s", gcs_path, e)
            return []

    def get_file_checksum(self, gcs_path: str) -> Optional[str]:
        """
        Get file MD5 checksum.
        """
        try:
            blob = self._get_blob(gcs_path)
            blob.reload()
            return blob.md5_hash
        except (GoogleCloudError, NotFound, Exception) as e:
            logger.error("Error getting checksum for %s: %s", gcs_path, e)
            return None

    def extract_all_metadata(self, gcs_path: str) -> FileMetadata:
        """
        Extract all available metadata for a file.
        """
        return FileMetadata(
            file_path=gcs_path,
            file_size=self.get_file_size(gcs_path),
            created_time=self.get_file_created_time(gcs_path),
            modified_time=self.get_file_modified_time(gcs_path),
            row_count=self.get_csv_row_count(gcs_path),
            columns=self.get_csv_columns(gcs_path),
            checksum=self.get_file_checksum(gcs_path),
            extracted_at=datetime.utcnow().isoformat()
        )
