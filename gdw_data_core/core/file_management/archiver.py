"""
File Archiver Module

Archives processed files to archive bucket with restoration capability.
"""

from google.cloud import storage
from datetime import datetime, timezone
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class FileArchiver:
    """
    Archives processed files to archive bucket with restoration capability.
    """

    def __init__(self, source_bucket: str, archive_bucket: str, archive_prefix: str = 'archive'):
        """
        Initialize file archiver.
        """
        self.source_bucket = source_bucket
        self.archive_bucket = archive_bucket
        self.archive_prefix = archive_prefix
        self.storage_client = storage.Client()

    def archive_file(self, source_path: str, archive_path: str = None) -> str:
        """
        Move file from source to archive bucket.
        """
        try:
            if archive_path is None:
                archive_path = self.get_archive_path(source_path)

            # Copy from source to archive
            source_bucket = self.storage_client.bucket(self.source_bucket)
            source_blob = source_bucket.blob(source_path)

            archive_bucket = self.storage_client.bucket(self.archive_bucket)
            source_bucket.copy_blob(source_blob, archive_bucket, archive_path)

            # Delete from source
            source_blob.delete()

            logger.info(f"Archived {source_path} to {archive_path}")
            return archive_path
        except Exception as e:
            logger.error(f"Error archiving file: {e}")
            raise

    def archive_batch(self, source_paths: List[str], archive_prefix: str = None) -> Dict[str, str]:
        """
        Archive multiple files.
        """
        results = {}
        prefix = archive_prefix or self.archive_prefix

        for source_path in source_paths:
            try:
                archive_path = f"{prefix}/{source_path.split('/')[-1]}"
                archive_path = self.archive_file(source_path, archive_path)
                results[source_path] = archive_path
            except Exception as e:
                logger.error(f"Failed to archive {source_path}: {e}")
                results[source_path] = None

        return results

    def get_archive_path(self, source_path: str) -> str:
        """
        Generate archive path from source path.
        """
        filename = source_path.split('/')[-1]
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        return f"{self.archive_prefix}/{timestamp}_{filename}"

    def restore_from_archive(self, archive_path: str, restore_path: str) -> bool:
        """
        Restore file from archive to source.
        """
        try:
            archive_bucket = self.storage_client.bucket(self.archive_bucket)
            archive_blob = archive_bucket.blob(archive_path)

            source_bucket = self.storage_client.bucket(self.source_bucket)
            archive_bucket.copy_blob(archive_blob, source_bucket, restore_path)

            logger.info(f"Restored {archive_path} to {restore_path}")
            return True
        except Exception as e:
            logger.error(f"Error restoring file: {e}")
            return False

    def list_archived_files(self, prefix: str = None) -> List[str]:
        """
        List all archived files.
        """
        try:
            bucket = self.storage_client.bucket(self.archive_bucket)
            search_prefix = prefix or self.archive_prefix

            blobs = bucket.list_blobs(prefix=search_prefix)
            return [blob.name for blob in blobs]
        except Exception as e:
            logger.error(f"Error listing archived files: {e}")
            return []

