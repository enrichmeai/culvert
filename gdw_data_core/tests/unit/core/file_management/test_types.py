"""
Unit tests for file management types.

Tests cover:
- ArchiveStatus enum
- ArchiveResult dataclass and serialization
- BatchArchiveResult dataclass and serialization
- XCom compatibility
"""

import pytest
from datetime import datetime, timezone

from gdw_data_core.core.file_management.types import (
    ArchiveStatus,
    ArchiveResult,
    BatchArchiveResult
)


class TestArchiveStatus:
    """Test ArchiveStatus enum."""

    def test_success_status_value(self):
        """Test SUCCESS status has correct value."""
        assert ArchiveStatus.SUCCESS.value == "SUCCESS"

    def test_failed_status_value(self):
        """Test FAILED status has correct value."""
        assert ArchiveStatus.FAILED.value == "FAILED"

    def test_partial_status_value(self):
        """Test PARTIAL status has correct value."""
        assert ArchiveStatus.PARTIAL.value == "PARTIAL"

    def test_collision_resolved_status_value(self):
        """Test COLLISION_RESOLVED status has correct value."""
        assert ArchiveStatus.COLLISION_RESOLVED.value == "COLLISION_RESOLVED"

    def test_status_from_string(self):
        """Test creating status from string value."""
        assert ArchiveStatus("SUCCESS") == ArchiveStatus.SUCCESS
        assert ArchiveStatus("FAILED") == ArchiveStatus.FAILED
        assert ArchiveStatus("PARTIAL") == ArchiveStatus.PARTIAL

    def test_invalid_status_raises_error(self):
        """Test invalid status string raises ValueError."""
        with pytest.raises(ValueError):
            ArchiveStatus("INVALID")


class TestArchiveResultCreation:
    """Test ArchiveResult creation and basic properties."""

    def test_create_successful_result(self, fixed_datetime):
        """Test creating a successful archive result."""
        result = ArchiveResult(
            success=True,
            source_path="landing/users.csv",
            archive_path="archive/users/2025/12/31/users.csv",
            archived_at=fixed_datetime,
            status=ArchiveStatus.SUCCESS,
            file_size=1024,
            file_checksum="abc123",
            original_filename="users.csv"
        )

        assert result.success is True
        assert result.source_path == "landing/users.csv"
        assert result.archive_path == "archive/users/2025/12/31/users.csv"
        assert result.archived_at == fixed_datetime
        assert result.status == ArchiveStatus.SUCCESS
        assert result.file_size == 1024
        assert result.file_checksum == "abc123"
        assert result.original_filename == "users.csv"
        assert result.error is None
        assert result.collision_resolved is False

    def test_create_failed_result(self, fixed_datetime):
        """Test creating a failed archive result."""
        result = ArchiveResult(
            success=False,
            source_path="landing/missing.csv",
            archive_path="",
            archived_at=fixed_datetime,
            status=ArchiveStatus.FAILED,
            file_size=0,
            error="Source file not found"
        )

        assert result.success is False
        assert result.status == ArchiveStatus.FAILED
        assert result.error == "Source file not found"

    def test_create_collision_resolved_result(self, fixed_datetime):
        """Test creating a result with collision resolved."""
        result = ArchiveResult(
            success=True,
            source_path="landing/data.csv",
            archive_path="archive/data_20251231_143022.csv",
            archived_at=fixed_datetime,
            status=ArchiveStatus.COLLISION_RESOLVED,
            file_size=2048,
            collision_resolved=True
        )

        assert result.success is True
        assert result.status == ArchiveStatus.COLLISION_RESOLVED
        assert result.collision_resolved is True


class TestArchiveResultSerialization:
    """Test ArchiveResult serialization methods."""

    def test_to_xcom_dict(self, fixed_datetime):
        """Test XCom dictionary serialization."""
        result = ArchiveResult(
            success=True,
            source_path="landing/users.csv",
            archive_path="archive/users/2025/12/31/users.csv",
            archived_at=fixed_datetime,
            status=ArchiveStatus.SUCCESS,
            file_size=1024,
            file_checksum="abc123",
            original_filename="users.csv"
        )

        xcom_dict = result.to_xcom_dict()

        assert isinstance(xcom_dict, dict)
        assert xcom_dict['success'] is True
        assert xcom_dict['source_path'] == "landing/users.csv"
        assert xcom_dict['archive_path'] == "archive/users/2025/12/31/users.csv"
        assert xcom_dict['archived_at'] == "2025-12-31T14:30:22+00:00"
        assert xcom_dict['status'] == "SUCCESS"
        assert xcom_dict['file_size'] == 1024
        assert xcom_dict['file_checksum'] == "abc123"
        assert xcom_dict['original_filename'] == "users.csv"
        assert xcom_dict['collision_resolved'] is False
        assert xcom_dict['error'] is None

    def test_to_dict(self, fixed_datetime):
        """Test dictionary serialization."""
        result = ArchiveResult(
            success=True,
            source_path="data.csv",
            archive_path="archive/data.csv",
            archived_at=fixed_datetime,
            status=ArchiveStatus.SUCCESS,
            file_size=512
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict['success'] is True
        assert result_dict['archived_at'] == "2025-12-31T14:30:22+00:00"
        assert result_dict['status'] == "SUCCESS"

    def test_from_xcom_dict_success(self, archive_result_data):
        """Test reconstruction from XCom dictionary."""
        result = ArchiveResult.from_xcom_dict(archive_result_data)

        assert isinstance(result, ArchiveResult)
        assert result.success is True
        assert result.source_path == "landing/users.csv"
        assert result.archive_path == "archive/users/2025/12/31/users.csv"
        assert isinstance(result.archived_at, datetime)
        assert result.status == ArchiveStatus.SUCCESS
        assert result.file_size == 1024

    def test_from_xcom_dict_failed(self, failed_archive_result_data):
        """Test reconstruction of failed result."""
        result = ArchiveResult.from_xcom_dict(failed_archive_result_data)

        assert result.success is False
        assert result.status == ArchiveStatus.FAILED
        assert result.error == "Source file not found"

    def test_roundtrip_serialization(self, fixed_datetime):
        """Test that serialization and deserialization are lossless."""
        original = ArchiveResult(
            success=True,
            source_path="landing/test.csv",
            archive_path="archive/test.csv",
            archived_at=fixed_datetime,
            status=ArchiveStatus.COLLISION_RESOLVED,
            file_size=4096,
            file_checksum="xyz789",
            original_filename="test.csv",
            collision_resolved=True
        )

        # Roundtrip through XCom dict
        xcom_dict = original.to_xcom_dict()
        restored = ArchiveResult.from_xcom_dict(xcom_dict)

        assert restored.success == original.success
        assert restored.source_path == original.source_path
        assert restored.archive_path == original.archive_path
        assert restored.status == original.status
        assert restored.file_size == original.file_size
        assert restored.collision_resolved == original.collision_resolved


class TestArchiveResultMethods:
    """Test ArchiveResult helper methods."""

    def test_is_success_for_success_status(self, fixed_datetime):
        """Test is_success returns True for SUCCESS status."""
        result = ArchiveResult(
            success=True,
            source_path="data.csv",
            archive_path="archive/data.csv",
            archived_at=fixed_datetime,
            status=ArchiveStatus.SUCCESS,
            file_size=1024
        )

        assert result.is_success() is True

    def test_is_success_for_collision_resolved(self, fixed_datetime):
        """Test is_success returns True for COLLISION_RESOLVED status."""
        result = ArchiveResult(
            success=True,
            source_path="data.csv",
            archive_path="archive/data_v2.csv",
            archived_at=fixed_datetime,
            status=ArchiveStatus.COLLISION_RESOLVED,
            file_size=1024,
            collision_resolved=True
        )

        assert result.is_success() is True

    def test_is_success_for_failed_status(self, fixed_datetime):
        """Test is_success returns False for FAILED status."""
        result = ArchiveResult(
            success=False,
            source_path="data.csv",
            archive_path="",
            archived_at=fixed_datetime,
            status=ArchiveStatus.FAILED,
            file_size=0,
            error="Error"
        )

        assert result.is_success() is False

    def test_repr(self, fixed_datetime):
        """Test string representation."""
        result = ArchiveResult(
            success=True,
            source_path="data.csv",
            archive_path="archive/data.csv",
            archived_at=fixed_datetime,
            status=ArchiveStatus.SUCCESS,
            file_size=1024
        )

        repr_str = repr(result)

        assert "ArchiveResult" in repr_str
        assert "success=True" in repr_str
        assert "data.csv" in repr_str


class TestBatchArchiveResult:
    """Test BatchArchiveResult dataclass."""

    def test_create_batch_result(self, fixed_datetime):
        """Test creating a batch archive result."""
        results = {
            "file1.csv": ArchiveResult(
                success=True,
                source_path="file1.csv",
                archive_path="archive/file1.csv",
                archived_at=fixed_datetime,
                status=ArchiveStatus.SUCCESS,
                file_size=1024
            ),
            "file2.csv": ArchiveResult(
                success=True,
                source_path="file2.csv",
                archive_path="archive/file2.csv",
                archived_at=fixed_datetime,
                status=ArchiveStatus.SUCCESS,
                file_size=2048
            )
        }

        batch_result = BatchArchiveResult(
            total_files=2,
            successful_count=2,
            failed_count=0,
            results=results,
            overall_status=ArchiveStatus.SUCCESS
        )

        assert batch_result.total_files == 2
        assert batch_result.successful_count == 2
        assert batch_result.failed_count == 0
        assert batch_result.overall_status == ArchiveStatus.SUCCESS

    def test_batch_result_with_failures(self, fixed_datetime):
        """Test batch result with some failures."""
        results = {
            "file1.csv": ArchiveResult(
                success=True,
                source_path="file1.csv",
                archive_path="archive/file1.csv",
                archived_at=fixed_datetime,
                status=ArchiveStatus.SUCCESS,
                file_size=1024
            ),
            "file2.csv": ArchiveResult(
                success=False,
                source_path="file2.csv",
                archive_path="",
                archived_at=fixed_datetime,
                status=ArchiveStatus.FAILED,
                file_size=0,
                error="Not found"
            )
        }

        batch_result = BatchArchiveResult(
            total_files=2,
            successful_count=1,
            failed_count=1,
            results=results,
            overall_status=ArchiveStatus.PARTIAL
        )

        assert batch_result.overall_status == ArchiveStatus.PARTIAL
        assert batch_result.is_complete_success() is False

    def test_is_complete_success(self, fixed_datetime):
        """Test is_complete_success method."""
        results = {
            "file1.csv": ArchiveResult(
                success=True,
                source_path="file1.csv",
                archive_path="archive/file1.csv",
                archived_at=fixed_datetime,
                status=ArchiveStatus.SUCCESS,
                file_size=1024
            )
        }

        batch_result = BatchArchiveResult(
            total_files=1,
            successful_count=1,
            failed_count=0,
            results=results,
            overall_status=ArchiveStatus.SUCCESS
        )

        assert batch_result.is_complete_success() is True

    def test_get_failed_paths(self, fixed_datetime):
        """Test getting list of failed paths."""
        results = {
            "file1.csv": ArchiveResult(
                success=True,
                source_path="file1.csv",
                archive_path="archive/file1.csv",
                archived_at=fixed_datetime,
                status=ArchiveStatus.SUCCESS,
                file_size=1024
            ),
            "file2.csv": ArchiveResult(
                success=False,
                source_path="file2.csv",
                archive_path="",
                archived_at=fixed_datetime,
                status=ArchiveStatus.FAILED,
                file_size=0
            ),
            "file3.csv": ArchiveResult(
                success=False,
                source_path="file3.csv",
                archive_path="",
                archived_at=fixed_datetime,
                status=ArchiveStatus.FAILED,
                file_size=0
            )
        }

        batch_result = BatchArchiveResult(
            total_files=3,
            successful_count=1,
            failed_count=2,
            results=results,
            overall_status=ArchiveStatus.PARTIAL
        )

        failed_paths = batch_result.get_failed_paths()

        assert len(failed_paths) == 2
        assert "file2.csv" in failed_paths
        assert "file3.csv" in failed_paths


class TestBatchArchiveResultSerialization:
    """Test BatchArchiveResult serialization."""

    def test_to_xcom_dict(self, fixed_datetime):
        """Test XCom dictionary serialization for batch result."""
        results = {
            "file1.csv": ArchiveResult(
                success=True,
                source_path="file1.csv",
                archive_path="archive/file1.csv",
                archived_at=fixed_datetime,
                status=ArchiveStatus.SUCCESS,
                file_size=1024
            )
        }

        batch_result = BatchArchiveResult(
            total_files=1,
            successful_count=1,
            failed_count=0,
            results=results,
            overall_status=ArchiveStatus.SUCCESS
        )

        xcom_dict = batch_result.to_xcom_dict()

        assert isinstance(xcom_dict, dict)
        assert xcom_dict['total_files'] == 1
        assert xcom_dict['successful_count'] == 1
        assert xcom_dict['overall_status'] == "SUCCESS"
        assert 'results' in xcom_dict
        assert 'file1.csv' in xcom_dict['results']

    def test_from_xcom_dict(self, fixed_datetime):
        """Test reconstruction from XCom dictionary."""
        xcom_data = {
            'total_files': 2,
            'successful_count': 1,
            'failed_count': 1,
            'overall_status': 'PARTIAL',
            'results': {
                'file1.csv': {
                    'success': True,
                    'source_path': 'file1.csv',
                    'archive_path': 'archive/file1.csv',
                    'archived_at': '2025-12-31T14:30:22+00:00',
                    'status': 'SUCCESS',
                    'file_size': 1024,
                    'collision_resolved': False
                },
                'file2.csv': {
                    'success': False,
                    'source_path': 'file2.csv',
                    'archive_path': '',
                    'archived_at': '2025-12-31T14:30:22+00:00',
                    'status': 'FAILED',
                    'file_size': 0,
                    'error': 'Not found'
                }
            }
        }

        batch_result = BatchArchiveResult.from_xcom_dict(xcom_data)

        assert batch_result.total_files == 2
        assert batch_result.successful_count == 1
        assert batch_result.failed_count == 1
        assert batch_result.overall_status == ArchiveStatus.PARTIAL
        assert 'file1.csv' in batch_result.results
        assert batch_result.results['file1.csv'].success is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

