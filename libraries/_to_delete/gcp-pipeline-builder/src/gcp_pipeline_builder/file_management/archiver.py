"""
File Archiver Module with Audit Trail Integration

Archives processed files to archive bucket with:
- Policy-driven path resolution
- Audit trail recording
- Restoration capability
- Structured success signals for Airflow XCom

Example:
    >>> from gcp_pipeline_builder.file_management import FileArchiver, ArchivePolicyEngine
    >>>
    >>> policy_engine = ArchivePolicyEngine("archive_config.yaml")
    >>> archiver = FileArchiver(
    ...     source_bucket="my-source",
    ...     archive_bucket="my-archive",
    ...     policy_engine=policy_engine
    ... )
    >>>
    >>> result = archiver.archive_file(
    ...     source_path="landing/users.csv",
    ...     entity="users"
    ... )
    >>> if result.success:
    ...     print(f"Archived to: {result.archive_path}")
"""

from google.cloud import storage
from datetime import datetime, timezone
from typing import List, Dict, Optional, TYPE_CHECKING
import logging

from .types import ArchiveResult, ArchiveStatus, BatchArchiveResult

if TYPE_CHECKING:
    from .policy import ArchivePolicyEngine
    from gcp_pipeline_builder.audit import AuditTrail

logger = logging.getLogger(__name__)


class FileArchiver:
    """
    Archives processed files with audit trail and policy-driven path resolution.

    Provides atomic file archiving (copy + delete) with complete audit trail
    and structured results suitable for Airflow XCom.

    Attributes:
        source_bucket: Source GCS bucket name
        archive_bucket: Archive GCS bucket name
        archive_prefix: Default archive prefix
        policy_engine: Optional policy engine for path resolution
        audit_logger: Optional audit logger for recording operations

    Example:
        >>> archiver = FileArchiver(
        ...     source_bucket="landing-bucket",
        ...     archive_bucket="archive-bucket"
        ... )
        >>> result = archiver.archive_file("landing/data.csv", entity="users")
        >>> print(result.to_xcom_dict())
    """

    def __init__(
        self,
        source_bucket: str,
        archive_bucket: str,
        archive_prefix: str = 'archive',
        policy_engine: Optional['ArchivePolicyEngine'] = None,
        audit_logger: Optional['AuditTrail'] = None
    ):
        """
        Initialize file archiver.

        Args:
            source_bucket: Source GCS bucket name
            archive_bucket: Archive GCS bucket name
            archive_prefix: Default archive prefix for paths
            policy_engine: Archive policy engine for path resolution
            audit_logger: Audit logger for recording operations
        """
        self.source_bucket = source_bucket
        self.archive_bucket = archive_bucket
        self.archive_prefix = archive_prefix
        self.policy_engine = policy_engine
        self.audit_logger = audit_logger
        self.storage_client = storage.Client()

    def archive_file(
        self,
        source_path: str,
        archive_path: Optional[str] = None,
        entity: Optional[str] = None,
        policy_name: Optional[str] = None,
        run_id: Optional[str] = None,
        existing_paths: Optional[List[str]] = None
    ) -> ArchiveResult:
        """
        Move file from source to archive bucket with audit trail.

        Performs atomic move (copy + delete) and records operation
        to audit trail if configured.

        Args:
            source_path: Source file path in GCS
            archive_path: Target archive path (uses policy if None)
            entity: Entity for policy-based path resolution
            policy_name: Archive policy to use
            run_id: Processing run identifier
            existing_paths: Existing paths for collision detection

        Returns:
            ArchiveResult with success signal for orchestration

        Example:
            >>> result = archiver.archive_file(
            ...     source_path="landing/users.csv",
            ...     entity="users",
            ...     policy_name="standard_daily"
            ... )
            >>> if result.success:
            ...     print(f"Archived to {result.archive_path}")
            ...     task.xcom_push(key='archive_result', value=result.to_xcom_dict())
        """
        collision_resolved = False

        try:
            # Resolve archive path if not provided
            if archive_path is None:
                if self.policy_engine and entity:
                    archive_path = self.policy_engine.resolve_path(
                        source_path=source_path,
                        entity=entity,
                        policy_name=policy_name,
                        run_id=run_id,
                        existing_paths=existing_paths
                    )
                    # Check if collision was resolved
                    if existing_paths and any(archive_path != source_path for _ in existing_paths):
                        collision_resolved = True
                else:
                    archive_path = self._default_archive_path(source_path)

            # Get file metadata before move
            source_bucket = self.storage_client.bucket(self.source_bucket)
            source_blob = source_bucket.blob(source_path)

            if not source_blob.exists():
                error_msg = f"Source file not found: {source_path}"
                logger.error(error_msg)
                return self._create_failed_result(
                    source_path=source_path,
                    archive_path=archive_path or '',
                    error=error_msg
                )

            source_blob.reload()  # Ensure metadata is loaded
            file_size = source_blob.size or 0
            file_checksum = source_blob.md5_hash

            # Perform atomic move (copy + delete)
            archive_bucket_obj = self.storage_client.bucket(self.archive_bucket)
            source_bucket.copy_blob(source_blob, archive_bucket_obj, archive_path)
            source_blob.delete()

            # Record to audit trail
            archive_time = datetime.now(timezone.utc)
            if self.audit_logger:
                self._record_audit(
                    source_path=source_path,
                    archive_path=archive_path,
                    timestamp=archive_time,
                    file_size=file_size,
                    file_checksum=file_checksum,
                    status="SUCCESS"
                )

            logger.info(f"Archived {source_path} to {archive_path}")

            # Determine status
            status = (
                ArchiveStatus.COLLISION_RESOLVED
                if collision_resolved
                else ArchiveStatus.SUCCESS
            )

            # Return structured success signal
            return ArchiveResult(
                success=True,
                source_path=source_path,
                archive_path=archive_path,
                archived_at=archive_time,
                status=status,
                file_size=file_size,
                file_checksum=file_checksum,
                original_filename=source_path.split('/')[-1],
                collision_resolved=collision_resolved
            )

        except FileNotFoundError as e:
            logger.error(f"Source file error: {e}")
            return self._create_failed_result(
                source_path=source_path,
                archive_path=archive_path or '',
                error=str(e)
            )
        except Exception as e:
            logger.error(f"Error archiving file: {e}", exc_info=True)

            # Record failure to audit trail
            if self.audit_logger:
                self._record_audit(
                    source_path=source_path,
                    archive_path=archive_path or '',
                    timestamp=datetime.now(timezone.utc),
                    file_size=0,
                    status="FAILED",
                    error_message=str(e)
                )

            return self._create_failed_result(
                source_path=source_path,
                archive_path=archive_path or '',
                error=str(e)
            )

    def archive_batch(
        self,
        source_paths: List[str],
        entity: Optional[str] = None,
        policy_name: Optional[str] = None,
        run_id: Optional[str] = None
    ) -> Dict[str, ArchiveResult]:
        """
        Archive multiple files with structured results.

        Args:
            source_paths: List of source file paths
            entity: Entity for policy-based resolution
            policy_name: Archive policy to use
            run_id: Processing run identifier

        Returns:
            Dictionary mapping source paths to ArchiveResults

        Example:
            >>> results = archiver.archive_batch(
            ...     source_paths=["file1.csv", "file2.csv"],
            ...     entity="users"
            ... )
            >>> for path, result in results.items():
            ...     print(f"{path}: {result.status.value}")
        """
        results: Dict[str, ArchiveResult] = {}

        # Get existing paths for collision detection
        existing_paths: List[str] = []

        for source_path in source_paths:
            result = self.archive_file(
                source_path=source_path,
                entity=entity,
                policy_name=policy_name,
                run_id=run_id,
                existing_paths=existing_paths
            )
            results[source_path] = result

            # Track successful archives for collision detection
            if result.success:
                existing_paths.append(result.archive_path)

        return results

    def archive_batch_with_summary(
        self,
        source_paths: List[str],
        entity: Optional[str] = None,
        policy_name: Optional[str] = None,
        run_id: Optional[str] = None
    ) -> BatchArchiveResult:
        """
        Archive multiple files and return summary result.

        Args:
            source_paths: List of source file paths
            entity: Entity for policy-based resolution
            policy_name: Archive policy to use
            run_id: Processing run identifier

        Returns:
            BatchArchiveResult with summary and individual results
        """
        results = self.archive_batch(
            source_paths=source_paths,
            entity=entity,
            policy_name=policy_name,
            run_id=run_id
        )

        successful_count = sum(1 for r in results.values() if r.success)
        failed_count = len(results) - successful_count

        if failed_count == 0:
            overall_status = ArchiveStatus.SUCCESS
        elif successful_count == 0:
            overall_status = ArchiveStatus.FAILED
        else:
            overall_status = ArchiveStatus.PARTIAL

        return BatchArchiveResult(
            total_files=len(source_paths),
            successful_count=successful_count,
            failed_count=failed_count,
            results=results,
            overall_status=overall_status
        )

    def _default_archive_path(self, source_path: str) -> str:
        """
        Generate default archive path (fallback when no policy engine).

        Args:
            source_path: Original source path

        Returns:
            Default archive path with timestamp
        """
        filename = source_path.split('/')[-1]
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        return f"{self.archive_prefix}/{timestamp}_{filename}"

    def _create_failed_result(
        self,
        source_path: str,
        archive_path: str,
        error: str
    ) -> ArchiveResult:
        """Create a failed ArchiveResult."""
        return ArchiveResult(
            success=False,
            source_path=source_path,
            archive_path=archive_path,
            archived_at=datetime.now(timezone.utc),
            status=ArchiveStatus.FAILED,
            file_size=0,
            error=error
        )

    def _record_audit(
        self,
        source_path: str,
        archive_path: str,
        timestamp: datetime,
        file_size: int,
        status: str,
        file_checksum: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Record archive operation to audit trail."""
        if not self.audit_logger:
            return

        try:
            context = {
                'source_path': source_path,
                'archive_path': archive_path,
                'file_size': file_size,
                'file_checksum': file_checksum,
                'status': status
            }
            if error_message:
                context['error'] = error_message

            self.audit_logger.log_entry(
                status=status,
                message=f"Archive operation: {source_path} -> {archive_path}",
                context=context
            )
        except Exception as e:
            logger.warning(f"Failed to record audit: {e}")

    def get_archive_path(self, source_path: str) -> str:
        """
        Generate archive path from source path (legacy method).

        Deprecated: Use archive_file() with policy_engine instead.
        """
        return self._default_archive_path(source_path)

    def restore_from_archive(self, archive_path: str, restore_path: str) -> bool:
        """
        Restore file from archive to source bucket.

        Args:
            archive_path: Path in archive bucket
            restore_path: Destination path in source bucket

        Returns:
            True if restoration successful, False otherwise
        """
        try:
            archive_bucket = self.storage_client.bucket(self.archive_bucket)
            archive_blob = archive_bucket.blob(archive_path)

            source_bucket = self.storage_client.bucket(self.source_bucket)
            archive_bucket.copy_blob(archive_blob, source_bucket, restore_path)

            logger.info(f"Restored {archive_path} to {restore_path}")

            # Record restoration to audit trail
            if self.audit_logger:
                self._record_audit(
                    source_path=archive_path,
                    archive_path=restore_path,
                    timestamp=datetime.now(timezone.utc),
                    file_size=archive_blob.size or 0,
                    status="RESTORED"
                )

            return True
        except Exception as e:
            logger.error(f"Error restoring file: {e}")
            return False

    def list_archived_files(self, prefix: Optional[str] = None) -> List[str]:
        """
        List all archived files.

        Args:
            prefix: Optional prefix to filter results

        Returns:
            List of archive file paths
        """
        try:
            bucket = self.storage_client.bucket(self.archive_bucket)
            search_prefix = prefix or self.archive_prefix

            blobs = bucket.list_blobs(prefix=search_prefix)
            return [blob.name for blob in blobs]
        except Exception as e:
            logger.error(f"Error listing archived files: {e}")
            return []

