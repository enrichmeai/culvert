"""
File Management Type Definitions

Provides structured types for archive operations, results, and status tracking.
Designed for seamless integration with Airflow XCom for orchestration.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum


class ArchiveStatus(Enum):
    """
    Archive operation status.

    Attributes:
        SUCCESS: Archive completed successfully
        FAILED: Archive operation failed
        PARTIAL: Only some files were archived successfully
        COLLISION_RESOLVED: Archive succeeded after collision resolution
    """
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    COLLISION_RESOLVED = "COLLISION_RESOLVED"


@dataclass
class ArchiveResult:
    """
    Structured result of archive operation for orchestration layer.

    Suitable for Airflow XCom passing to downstream tasks.
    Provides complete metadata about the archive operation.

    Attributes:
        success: Whether the archive operation succeeded
        source_path: Original source file path
        archive_path: Destination archive path
        archived_at: Timestamp of archive operation
        status: Archive status enum
        file_size: Size of archived file in bytes
        file_checksum: MD5 hash of the file (optional)
        original_filename: Original filename without path
        error: Error message if operation failed
        collision_resolved: Whether a collision was detected and resolved

    Example:
        >>> result = ArchiveResult(
        ...     success=True,
        ...     source_path="landing/data.csv",
        ...     archive_path="archive/entity/2025/01/01/data.csv",
        ...     archived_at=datetime.utcnow(),
        ...     status=ArchiveStatus.SUCCESS,
        ...     file_size=1024,
        ...     file_checksum="abc123",
        ...     original_filename="data.csv"
        ... )
        >>> xcom_data = result.to_xcom_dict()
        >>> restored = ArchiveResult.from_xcom_dict(xcom_data)
    """
    success: bool
    source_path: str
    archive_path: str
    archived_at: datetime
    status: ArchiveStatus
    file_size: int
    file_checksum: Optional[str] = None
    original_filename: Optional[str] = None
    error: Optional[str] = None
    collision_resolved: bool = False

    def to_xcom_dict(self) -> Dict[str, Any]:
        """
        Convert to XCom-compatible dictionary for Airflow.

        All datetime objects are converted to ISO format strings for
        JSON serialization compatibility.

        Returns:
            Dictionary suitable for XCom push

        Example:
            result = archiver.archive_file(path)
            task.xcom_push(key='archive_result', value=result.to_xcom_dict())
        """
        return {
            'success': self.success,
            'source_path': self.source_path,
            'archive_path': self.archive_path,
            'archived_at': self.archived_at.isoformat(),
            'status': self.status.value,
            'file_size': self.file_size,
            'file_checksum': self.file_checksum,
            'original_filename': self.original_filename,
            'collision_resolved': self.collision_resolved,
            'error': self.error
        }

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary with serializable values.

        Returns:
            Dictionary representation of the result
        """
        data = asdict(self)
        data['archived_at'] = self.archived_at.isoformat()
        data['status'] = self.status.value
        return data

    @staticmethod
    def from_xcom_dict(data: Dict[str, Any]) -> 'ArchiveResult':
        """
        Reconstruct ArchiveResult from XCom dictionary.

        Args:
            data: Dictionary from XCom pull

        Returns:
            ArchiveResult instance

        Example:
            xcom_data = task.xcom_pull(key='archive_result')
            result = ArchiveResult.from_xcom_dict(xcom_data)
        """
        return ArchiveResult(
            success=data['success'],
            source_path=data['source_path'],
            archive_path=data['archive_path'],
            archived_at=datetime.fromisoformat(data['archived_at']),
            status=ArchiveStatus(data['status']),
            file_size=data['file_size'],
            file_checksum=data.get('file_checksum'),
            original_filename=data.get('original_filename'),
            collision_resolved=data.get('collision_resolved', False),
            error=data.get('error')
        )

    def is_success(self) -> bool:
        """Check if archive operation was successful."""
        return self.success and self.status in (
            ArchiveStatus.SUCCESS,
            ArchiveStatus.COLLISION_RESOLVED
        )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"ArchiveResult(success={self.success}, "
            f"source_path='{self.source_path}', "
            f"archive_path='{self.archive_path}', "
            f"status={self.status.value})"
        )


@dataclass
class BatchArchiveResult:
    """
    Result of batch archive operation.

    Aggregates results from multiple file archive operations.

    Attributes:
        total_files: Total number of files in batch
        successful_count: Number of successfully archived files
        failed_count: Number of failed archives
        results: Dictionary mapping source paths to ArchiveResults
        overall_status: Overall batch status
    """
    total_files: int
    successful_count: int
    failed_count: int
    results: Dict[str, ArchiveResult]
    overall_status: ArchiveStatus

    def to_xcom_dict(self) -> Dict[str, Any]:
        """Convert to XCom-compatible dictionary."""
        return {
            'total_files': self.total_files,
            'successful_count': self.successful_count,
            'failed_count': self.failed_count,
            'overall_status': self.overall_status.value,
            'results': {
                path: result.to_xcom_dict()
                for path, result in self.results.items()
            }
        }

    @staticmethod
    def from_xcom_dict(data: Dict[str, Any]) -> 'BatchArchiveResult':
        """Reconstruct from XCom dictionary."""
        return BatchArchiveResult(
            total_files=data['total_files'],
            successful_count=data['successful_count'],
            failed_count=data['failed_count'],
            overall_status=ArchiveStatus(data['overall_status']),
            results={
                path: ArchiveResult.from_xcom_dict(result_data)
                for path, result_data in data['results'].items()
            }
        )

    def is_complete_success(self) -> bool:
        """Check if all files were archived successfully."""
        return self.failed_count == 0

    def get_failed_paths(self) -> list:
        """Get list of paths that failed to archive."""
        return [
            path for path, result in self.results.items()
            if not result.success
        ]

