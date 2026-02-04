"""
File Lifecycle Management Module

Orchestrates complete file lifecycle including validation, processing, and archiving.
Provides error handling with actual file movement to error bucket.

Features:
- File validation with aggregated errors
- Processing with monitoring integration
- Archive with policy-based paths
- Error file movement to dedicated bucket
- Complete lifecycle orchestration

Example:
    >>> manager = FileLifecycleManager(
    ...     gcs_bucket="source-bucket",
    ...     archive_bucket="archive-bucket",
    ...     error_bucket="error-bucket"
    ... )
    >>> result = manager.complete_lifecycle(
    ...     gcs_path="landing/data.csv",
    ...     processing_fn=process_data
    ... )
"""

from datetime import datetime, timezone
from typing import Callable, Dict, Any, Optional, Tuple, List, TYPE_CHECKING

from google.cloud import storage

from gcp_pipeline_core.utilities.logging import get_logger
from .validator import FileValidator
from .archiver import FileArchiver
from .metadata import FileMetadataExtractor
from .types import ArchiveResult, ArchiveStatus
from gcp_pipeline_core.error_handling import ErrorHandler
from gcp_pipeline_core.monitoring import ObservabilityManager

if TYPE_CHECKING:
    from .policy import ArchivePolicyEngine
    from gcp_pipeline_core.audit import AuditTrail

logger = get_logger(__name__)


class FileLifecycleManager:
    """
    Orchestrates complete file lifecycle including validation, processing, and archiving.

    Provides comprehensive file management with:
    - Validation with aggregated errors
    - Processing with custom functions
    - Policy-based archiving
    - Error file movement to dedicated bucket
    - Monitoring and audit integration

    Attributes:
        gcs_bucket: Source GCS bucket name
        archive_bucket: Archive GCS bucket name
        error_bucket: Error files GCS bucket name
        error_handler: Optional error handler instance
        monitoring: Optional observability manager
        policy_engine: Optional archive policy engine
        audit_logger: Optional audit trail logger

    Example:
        >>> manager = FileLifecycleManager(
        ...     gcs_bucket="source-bucket",
        ...     archive_bucket="archive-bucket",
        ...     error_bucket="error-bucket"
        ... )
        >>> result = manager.complete_lifecycle(
        ...     gcs_path="landing/data.csv",
        ...     processing_fn=lambda p: process(p)
        ... )
    """

    def __init__(
        self,
        gcs_bucket: str,
        archive_bucket: str,
        error_bucket: Optional[str] = None,
        error_handler: Optional[ErrorHandler] = None,
        monitoring: Optional[ObservabilityManager] = None,
        policy_engine: Optional['ArchivePolicyEngine'] = None,
        audit_logger: Optional['AuditTrail'] = None
    ):
        """
        Initialize lifecycle manager.

        Args:
            gcs_bucket: Source GCS bucket name
            archive_bucket: Archive GCS bucket name
            error_bucket: Error files GCS bucket name (defaults to archive_bucket)
            error_handler: Optional error handler instance
            monitoring: Optional observability manager instance
            policy_engine: Optional archive policy engine for path resolution
            audit_logger: Optional audit trail logger
        """
        self.gcs_bucket = gcs_bucket
        self.archive_bucket = archive_bucket
        self.error_bucket = error_bucket or archive_bucket
        self.error_handler = error_handler
        self.monitoring = monitoring
        self.policy_engine = policy_engine
        self.audit_logger = audit_logger

        # Initialize storage client
        self.storage_client = storage.Client()

        self.validator = FileValidator(gcs_bucket)
        self.archiver = FileArchiver(
            gcs_bucket,
            archive_bucket,
            policy_engine=policy_engine,
            audit_logger=audit_logger
        )
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
            logger.info(f"Successfully processed {gcs_path}")

            if self.monitoring:
                self.monitoring.metrics.increment('files_processed', 1)

            return True
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error(f"Error processing file: {exc}", exc_info=True)

            if self.error_handler:
                self.error_handler.handle_exception(exc, source_file=gcs_path)

            return False

    def archive_file(
        self,
        gcs_path: str,
        entity: Optional[str] = None,
        policy_name: Optional[str] = None
    ) -> Optional[ArchiveResult]:
        """
        Archive file to archive bucket.

        Args:
            gcs_path: Path to file in GCS
            entity: Entity for policy-based path resolution
            policy_name: Archive policy to use

        Returns:
            ArchiveResult if successful, None otherwise
        """
        try:
            result = self.archiver.archive_file(
                source_path=gcs_path,
                entity=entity,
                policy_name=policy_name
            )

            if self.monitoring and result.success:
                self.monitoring.metrics.increment('files_archived', 1)

            return result if result.success else None
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error(f"Error archiving file: {exc}", exc_info=True)

            if self.error_handler:
                self.error_handler.handle_exception(exc, source_file=gcs_path)

            return None

    def handle_error_file(self, gcs_path: str, error_reason: str) -> Optional[str]:
        """
        Move file to error bucket for manual review.

        Performs atomic move (copy + delete) to error bucket with
        timestamp-based path for organization.

        Args:
            gcs_path: Path to file in GCS
            error_reason: Reason for the error

        Returns:
            Error path if successful, None otherwise

        Example:
            >>> error_path = manager.handle_error_file(
            ...     "landing/bad_file.csv",
            ...     "Validation failed: missing columns"
            ... )
            >>> print(error_path)
            "error/20251231_143022/bad_file.csv"
        """
        if not self.error_bucket:
            logger.error("Error bucket not configured")
            return None

        try:
            source_bucket = self.storage_client.bucket(self.gcs_bucket)
            source_blob = source_bucket.blob(gcs_path)

            if not source_blob.exists():
                logger.warning(f"File already moved or doesn't exist: {gcs_path}")
                return None

            # Generate error path with timestamp
            filename = gcs_path.split('/')[-1]
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            error_path = f"error/{timestamp}/{filename}"

            # Perform atomic move (copy + delete)
            error_bucket = self.storage_client.bucket(self.error_bucket)
            source_bucket.copy_blob(source_blob, error_bucket, error_path)
            source_blob.delete()  # Delete after successful copy

            # Log error file movement
            logger.warning(
                f"Moved {gcs_path} to error bucket: {error_reason}\n"
                f"Error path: {error_path}"
            )

            if self.monitoring:
                self.monitoring.metrics.increment('files_error', 1)

            # Record to audit trail
            if self.audit_logger:
                self.audit_logger.log_entry(
                    status="ERROR_MOVED",
                    message=f"File moved to error bucket: {error_reason}",
                    context={
                        'source_path': gcs_path,
                        'error_path': error_path,
                        'error_reason': error_reason
                    }
                )

            return error_path

        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error(f"Error moving file to error bucket: {exc}", exc_info=True)
            return None

    def complete_lifecycle(
        self,
        gcs_path: str,
        processing_fn: Callable,
        entity: Optional[str] = None,
        policy_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute complete file lifecycle: validate → process → archive.

        Args:
            gcs_path: Path to file in GCS
            processing_fn: Function to process the file
            entity: Entity for policy-based archive path resolution
            policy_name: Archive policy to use

        Returns:
            Dictionary containing lifecycle execution details

        Example:
            >>> result = manager.complete_lifecycle(
            ...     gcs_path="landing/users.csv",
            ...     processing_fn=process_users,
            ...     entity="users",
            ...     policy_name="standard_daily"
            ... )
            >>> if result['status'] == 'COMPLETED':
            ...     print(f"Archived to: {result['archive_result'].archive_path}")
        """
        lifecycle: Dict[str, Any] = {
            'file_path': gcs_path,
            'started_at': datetime.now(timezone.utc).isoformat(),
            'status': 'PENDING',
            'metadata': {},
            'errors': [],
            'archive_result': None
        }

        try:
            # Step 1: Validate
            is_valid, errors = self.validate_file(gcs_path)
            if not is_valid:
                lifecycle['errors'] = errors
                lifecycle['status'] = 'VALIDATION_FAILED'
                error_path = self.handle_error_file(
                    gcs_path,
                    f"Validation failed: {errors}"
                )
                lifecycle['error_path'] = error_path
                return lifecycle

            # Step 2: Extract metadata
            lifecycle['metadata'] = self.metadata_extractor.extract_all_metadata(gcs_path)

            # Step 3: Process
            if not self.process_file(gcs_path, processing_fn):
                lifecycle['status'] = 'PROCESSING_FAILED'
                error_path = self.handle_error_file(gcs_path, "Processing failed")
                lifecycle['error_path'] = error_path
                return lifecycle

            # Step 4: Archive with policy
            archive_result = self.archive_file(
                gcs_path,
                entity=entity,
                policy_name=policy_name
            )
            if not archive_result:
                lifecycle['status'] = 'ARCHIVE_FAILED'
                return lifecycle

            lifecycle['status'] = 'COMPLETED'
            lifecycle['archive_result'] = archive_result
            lifecycle['archive_path'] = archive_result.archive_path

        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error(f"Unexpected error in lifecycle: {exc}", exc_info=True)
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
