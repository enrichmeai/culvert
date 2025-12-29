"""
File Lifecycle Management Module

Orchestrates complete file lifecycle including validation, processing, and archiving.
"""

from datetime import datetime, timezone
from typing import Callable, Dict, Any, Optional, Tuple, List
import logging

from .validator import FileValidator
from .archiver import FileArchiver
from .metadata import FileMetadataExtractor
from gdw_data_core.core.error_handling import ErrorHandler
from gdw_data_core.core.monitoring import ObservabilityManager

logger = logging.getLogger(__name__)


class FileLifecycleManager:
    """
    Orchestrates complete file lifecycle including validation, processing, and archiving.
    """

    def __init__(self,
                 gcs_bucket: str,
                 archive_bucket: str,
                 error_handler: Optional[ErrorHandler] = None,
                 monitoring: Optional[ObservabilityManager] = None):
        """
        Initialize lifecycle manager.

        Args:
            gcs_bucket: Source GCS bucket name
            archive_bucket: Archive GCS bucket name
            error_handler: Optional error handler instance
            monitoring: Optional observability manager instance
        """
        self.gcs_bucket = gcs_bucket
        self.archive_bucket = archive_bucket
        self.error_handler = error_handler
        self.monitoring = monitoring

        self.validator = FileValidator(gcs_bucket)
        self.archiver = FileArchiver(gcs_bucket, archive_bucket)
        self.metadata_extractor = FileMetadataExtractor(gcs_bucket)

    def validate_file(self, gcs_path: str) -> Tuple[bool, List[str]]:
        """
        Validate file and return errors.

        Args:
            gcs_path: Path to file in GCS

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = self.validator.get_validation_errors(gcs_path)

        if self.monitoring and errors:
            self.monitoring.metrics.increment('file_validation_errors', len(errors))

        return len(errors) == 0, errors

    def process_file(self, gcs_path: str, processing_fn: Callable) -> bool:
        """
        Process file with provided function.

        Args:
            gcs_path: Path to file in GCS
            processing_fn: Function to process the file

        Returns:
            True if processing succeeded, False otherwise
        """
        try:
            processing_fn(gcs_path)
            logger.info("Successfully processed %s", gcs_path)

            if self.monitoring:
                self.monitoring.metrics.increment('files_processed', 1)

            return True
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Error processing file: %s", exc, exc_info=True)

            if self.error_handler:
                self.error_handler.handle_exception(exc, source_file=gcs_path)

            return False

    def archive_file(self, gcs_path: str) -> Optional[str]:
        """
        Archive file to archive bucket.

        Args:
            gcs_path: Path to file in GCS

        Returns:
            Archive path if successful, None otherwise
        """
        try:
            archive_path = self.archiver.archive_file(gcs_path)

            if self.monitoring:
                self.monitoring.metrics.increment('files_archived', 1)

            return archive_path
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Error archiving file: %s", exc, exc_info=True)

            if self.error_handler:
                self.error_handler.handle_exception(exc, source_file=gcs_path)

            return None

    def handle_error_file(self, gcs_path: str, error_reason: str) -> Optional[str]:
        """
        Move file to error bucket.

        Args:
            gcs_path: Path to file in GCS
            error_reason: Reason for the error

        Returns:
            Error path if successful, None otherwise
        """
        try:
            # Use archiver to move to error prefix
            filename = gcs_path.split('/')[-1]
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            error_path = f"error/{timestamp}/{filename}"

            if self.monitoring:
                self.monitoring.metrics.increment('files_error', 1)

            logger.warning("Moving %s to error: %s", gcs_path, error_reason)
            return error_path
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Error handling error file: %s", exc, exc_info=True)
            return None

    def complete_lifecycle(self, gcs_path: str, processing_fn: Callable) -> Dict[str, Any]:
        """
        Execute complete file lifecycle: validate → process → archive.

        Args:
            gcs_path: Path to file in GCS
            processing_fn: Function to process the file

        Returns:
            Dictionary containing lifecycle execution details
        """
        lifecycle = {
            'file_path': gcs_path,
            'started_at': datetime.now(timezone.utc).isoformat(),
            'status': 'PENDING',
            'metadata': {},
            'errors': []
        }

        try:
            # Step 1: Validate
            is_valid, errors = self.validate_file(gcs_path)
            if not is_valid:
                lifecycle['errors'] = errors
                lifecycle['status'] = 'VALIDATION_FAILED'
                self.handle_error_file(gcs_path, f"Validation failed: {errors}")
                return lifecycle

            # Step 2: Extract metadata
            lifecycle['metadata'] = self.metadata_extractor.extract_all_metadata(gcs_path)

            # Step 3: Process
            if not self.process_file(gcs_path, processing_fn):
                lifecycle['status'] = 'PROCESSING_FAILED'
                self.handle_error_file(gcs_path, "Processing failed")
                return lifecycle

            # Step 4: Archive
            archive_path = self.archive_file(gcs_path)
            if not archive_path:
                lifecycle['status'] = 'ARCHIVE_FAILED'
                return lifecycle

            lifecycle['status'] = 'COMPLETED'
            lifecycle['archive_path'] = archive_path

        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Unexpected error in lifecycle: %s", exc, exc_info=True)
            lifecycle['status'] = 'FAILED'
            lifecycle['error'] = str(exc)

            if self.error_handler:
                self.error_handler.handle_exception(exc, source_file=gcs_path)

        finally:
            lifecycle['completed_at'] = datetime.now(timezone.utc).isoformat()

        return lifecycle

    def get_file_status(self, gcs_path: str) -> Dict[str, Any]:
        """
        Get current file status and metadata.

        Args:
            gcs_path: Path to file in GCS

        Returns:
            Dictionary containing file status and metadata
        """
        return {
            'file_path': gcs_path,
            'metadata': self.metadata_extractor.extract_all_metadata(gcs_path),
            'status_checked_at': datetime.now(timezone.utc).isoformat()
        }
