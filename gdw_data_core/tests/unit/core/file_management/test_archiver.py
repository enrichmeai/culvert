"""
Unit tests for FileArchiver.

Tests cover:
- Archive file operations with policy engine
- Archive result structure and serialization
- Audit trail recording
- GCS operations (mocked)
- Error handling scenarios
- Batch operations
- XCom compatibility
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch

from gdw_data_core.core.file_management.archiver import FileArchiver
from gdw_data_core.core.file_management.types import ArchiveResult, ArchiveStatus
from gdw_data_core.core.file_management.policy import ArchivePolicyEngine


class TestFileArchiverInit:
    """Test FileArchiver initialization."""

    @patch('gdw_data_core.core.file_management.archiver.storage.Client')
    def test_basic_init(self, mock_storage):
        """Test basic initialization without optional parameters."""
        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket"
        )

        assert archiver.source_bucket == "source-bucket"
        assert archiver.archive_bucket == "archive-bucket"
        assert archiver.archive_prefix == "archive"
        assert archiver.policy_engine is None
        assert archiver.audit_logger is None

    @patch('gdw_data_core.core.file_management.archiver.storage.Client')
    def test_init_with_policy_engine(self, mock_storage, sample_config_dict):
        """Test initialization with policy engine."""
        policy_engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket",
            policy_engine=policy_engine
        )

        assert archiver.policy_engine is policy_engine

    @patch('gdw_data_core.core.file_management.archiver.storage.Client')
    def test_init_with_audit_logger(self, mock_storage, mock_audit_logger):
        """Test initialization with audit logger."""
        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket",
            audit_logger=mock_audit_logger
        )

        assert archiver.audit_logger is mock_audit_logger

    @patch('gdw_data_core.core.file_management.archiver.storage.Client')
    def test_init_with_custom_prefix(self, mock_storage):
        """Test initialization with custom archive prefix."""
        archiver = FileArchiver(
            source_bucket="source",
            archive_bucket="archive",
            archive_prefix="custom_archive"
        )

        assert archiver.archive_prefix == "custom_archive"


class TestArchiveFile:
    """Test archive_file method."""

    @pytest.fixture
    def mock_gcs_setup(self):
        """Setup mock GCS client, buckets, and blobs."""
        with patch('gdw_data_core.core.file_management.archiver.storage.Client') as mock_client:
            client = Mock()
            mock_client.return_value = client

            source_bucket = Mock()
            archive_bucket = Mock()

            source_blob = Mock()
            source_blob.exists.return_value = True
            source_blob.size = 1024
            source_blob.md5_hash = "abc123"

            source_bucket.blob.return_value = source_blob
            source_bucket.copy_blob = Mock()

            def get_bucket(name):
                if name == "source-bucket":
                    return source_bucket
                return archive_bucket

            client.bucket = get_bucket

            yield {
                'client': client,
                'source_bucket': source_bucket,
                'archive_bucket': archive_bucket,
                'source_blob': source_blob
            }

    def test_archive_file_success(self, mock_gcs_setup):
        """Test successful file archiving."""
        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket"
        )

        result = archiver.archive_file(
            source_path="landing/users.csv"
        )

        assert isinstance(result, ArchiveResult)
        assert result.success is True
        assert result.status == ArchiveStatus.SUCCESS
        assert result.source_path == "landing/users.csv"
        assert result.file_size == 1024

    def test_archive_file_with_policy_engine(self, mock_gcs_setup, sample_config_dict):
        """Test archiving with policy engine."""
        policy_engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket",
            policy_engine=policy_engine
        )

        result = archiver.archive_file(
            source_path="landing/users.csv",
            entity="users",
            policy_name="standard_daily"
        )

        assert result.success is True
        assert "archive/users/" in result.archive_path
        assert "users.csv" in result.archive_path

    def test_archive_file_explicit_path(self, mock_gcs_setup):
        """Test archiving with explicit archive path."""
        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket"
        )

        result = archiver.archive_file(
            source_path="landing/data.csv",
            archive_path="custom/path/data.csv"
        )

        assert result.success is True
        assert result.archive_path == "custom/path/data.csv"

    def test_archive_file_not_found(self, mock_gcs_setup):
        """Test archiving when source file doesn't exist."""
        mock_gcs_setup['source_blob'].exists.return_value = False

        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket"
        )

        result = archiver.archive_file(
            source_path="landing/missing.csv"
        )

        assert result.success is False
        assert result.status == ArchiveStatus.FAILED
        assert "not found" in result.error.lower()

    def test_archive_file_gcs_error(self, mock_gcs_setup):
        """Test handling GCS errors during archiving."""
        mock_gcs_setup['source_bucket'].copy_blob.side_effect = Exception("GCS Error")

        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket"
        )

        result = archiver.archive_file(
            source_path="landing/data.csv"
        )

        assert result.success is False
        assert result.status == ArchiveStatus.FAILED
        assert "GCS Error" in result.error

    def test_archive_file_with_audit_logging(self, mock_gcs_setup, mock_audit_logger):
        """Test that archive operations are logged to audit trail."""
        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket",
            audit_logger=mock_audit_logger
        )

        result = archiver.archive_file(
            source_path="landing/users.csv"
        )

        assert result.success is True
        mock_audit_logger.log_entry.assert_called()

    def test_archive_file_records_failure_to_audit(self, mock_gcs_setup, mock_audit_logger):
        """Test that failures are recorded to audit trail."""
        mock_gcs_setup['source_bucket'].copy_blob.side_effect = Exception("Copy failed")

        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket",
            audit_logger=mock_audit_logger
        )

        result = archiver.archive_file(
            source_path="landing/data.csv"
        )

        assert result.success is False
        mock_audit_logger.log_entry.assert_called()


class TestArchiveResult:
    """Test ArchiveResult structure and serialization."""

    def test_archive_result_creation(self, fixed_datetime):
        """Test creating an ArchiveResult."""
        result = ArchiveResult(
            success=True,
            source_path="landing/data.csv",
            archive_path="archive/data/2025/12/31/data.csv",
            archived_at=fixed_datetime,
            status=ArchiveStatus.SUCCESS,
            file_size=1024,
            file_checksum="abc123",
            original_filename="data.csv"
        )

        assert result.success is True
        assert result.source_path == "landing/data.csv"
        assert result.file_size == 1024

    def test_to_xcom_dict(self, fixed_datetime):
        """Test XCom serialization."""
        result = ArchiveResult(
            success=True,
            source_path="landing/data.csv",
            archive_path="archive/data.csv",
            archived_at=fixed_datetime,
            status=ArchiveStatus.SUCCESS,
            file_size=1024
        )

        xcom_dict = result.to_xcom_dict()

        assert isinstance(xcom_dict, dict)
        assert xcom_dict['success'] is True
        assert xcom_dict['status'] == 'SUCCESS'
        assert isinstance(xcom_dict['archived_at'], str)  # Should be ISO string

    def test_from_xcom_dict(self, archive_result_data):
        """Test reconstruction from XCom data."""
        result = ArchiveResult.from_xcom_dict(archive_result_data)

        assert result.success is True
        assert result.source_path == 'landing/users.csv'
        assert result.status == ArchiveStatus.SUCCESS
        assert isinstance(result.archived_at, datetime)

    def test_to_dict(self, fixed_datetime):
        """Test dictionary conversion."""
        result = ArchiveResult(
            success=True,
            source_path="landing/data.csv",
            archive_path="archive/data.csv",
            archived_at=fixed_datetime,
            status=ArchiveStatus.SUCCESS,
            file_size=1024
        )

        result_dict = result.to_dict()

        assert 'success' in result_dict
        assert 'archived_at' in result_dict
        assert result_dict['status'] == 'SUCCESS'

    def test_is_success_true(self, fixed_datetime):
        """Test is_success returns True for successful result."""
        result = ArchiveResult(
            success=True,
            source_path="data.csv",
            archive_path="archive/data.csv",
            archived_at=fixed_datetime,
            status=ArchiveStatus.SUCCESS,
            file_size=1024
        )

        assert result.is_success() is True

    def test_is_success_false(self, fixed_datetime):
        """Test is_success returns False for failed result."""
        result = ArchiveResult(
            success=False,
            source_path="data.csv",
            archive_path="",
            archived_at=fixed_datetime,
            status=ArchiveStatus.FAILED,
            file_size=0,
            error="Test error"
        )

        assert result.is_success() is False

    def test_collision_resolved_status(self, fixed_datetime):
        """Test COLLISION_RESOLVED is considered success."""
        result = ArchiveResult(
            success=True,
            source_path="data.csv",
            archive_path="archive/data_123.csv",
            archived_at=fixed_datetime,
            status=ArchiveStatus.COLLISION_RESOLVED,
            file_size=1024,
            collision_resolved=True
        )

        assert result.is_success() is True
        assert result.collision_resolved is True


class TestArchiveBatch:
    """Test batch archiving operations."""

    @pytest.fixture
    def mock_gcs_batch_setup(self):
        """Setup mock GCS for batch operations."""
        with patch('gdw_data_core.core.file_management.archiver.storage.Client') as mock_client:
            client = Mock()
            mock_client.return_value = client

            source_bucket = Mock()
            archive_bucket = Mock()

            # Create blobs for multiple files
            blobs = {}
            for i in range(3):
                blob = Mock()
                blob.exists.return_value = True
                blob.size = 1024 * (i + 1)
                blob.md5_hash = f"hash{i}"
                blobs[f"file{i}.csv"] = blob

            def get_blob(name):
                filename = name.split('/')[-1]
                if filename in blobs:
                    return blobs[filename]
                blob = Mock()
                blob.exists.return_value = False
                return blob

            source_bucket.blob = get_blob
            source_bucket.copy_blob = Mock()

            client.bucket.return_value = source_bucket

            yield client

    def test_archive_batch_all_success(self, mock_gcs_batch_setup):
        """Test batch archiving with all successful."""
        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket"
        )

        results = archiver.archive_batch(
            source_paths=[
                "landing/file0.csv",
                "landing/file1.csv",
                "landing/file2.csv"
            ]
        )

        assert len(results) == 3
        assert all(r.success for r in results.values())

    def test_archive_batch_partial_failure(self, mock_gcs_batch_setup):
        """Test batch archiving with some failures."""
        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket"
        )

        # Include a file that doesn't exist
        results = archiver.archive_batch(
            source_paths=[
                "landing/file0.csv",
                "landing/missing.csv",  # This will fail
                "landing/file1.csv"
            ]
        )

        assert len(results) == 3
        assert results["landing/file0.csv"].success is True
        assert results["landing/missing.csv"].success is False
        assert results["landing/file1.csv"].success is True

    def test_archive_batch_with_summary(self, mock_gcs_batch_setup, sample_config_dict):
        """Test batch archiving with summary."""
        policy_engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket",
            policy_engine=policy_engine
        )

        result = archiver.archive_batch_with_summary(
            source_paths=[
                "landing/file0.csv",
                "landing/file1.csv"
            ],
            entity="users"
        )

        assert result.total_files == 2
        assert result.successful_count == 2
        assert result.failed_count == 0
        assert result.overall_status == ArchiveStatus.SUCCESS


class TestDefaultArchivePath:
    """Test default archive path generation."""

    @patch('gdw_data_core.core.file_management.archiver.storage.Client')
    def test_default_archive_path_format(self, mock_storage):
        """Test default path includes timestamp."""
        archiver = FileArchiver(
            source_bucket="source",
            archive_bucket="archive"
        )

        path = archiver._default_archive_path("landing/data.csv")

        assert path.startswith("archive/")
        assert "data.csv" in path
        assert "_" in path  # Timestamp separator

    @patch('gdw_data_core.core.file_management.archiver.storage.Client')
    def test_default_archive_path_extracts_filename(self, mock_storage):
        """Test that filename is correctly extracted."""
        archiver = FileArchiver(
            source_bucket="source",
            archive_bucket="archive"
        )

        path = archiver._default_archive_path("a/b/c/deep/file.csv")

        assert "file.csv" in path
        assert "deep" not in path


class TestRestoreFromArchive:
    """Test file restoration."""

    @patch('gdw_data_core.core.file_management.archiver.storage.Client')
    def test_restore_success(self, mock_storage):
        """Test successful file restoration."""
        client = Mock()
        mock_storage.return_value = client

        archive_bucket = Mock()
        archive_blob = Mock()
        archive_blob.size = 1024
        archive_bucket.blob.return_value = archive_blob
        archive_bucket.copy_blob = Mock()

        source_bucket = Mock()

        def get_bucket(name):
            if name == "archive-bucket":
                return archive_bucket
            return source_bucket

        client.bucket = get_bucket

        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket"
        )

        result = archiver.restore_from_archive(
            archive_path="archive/2025/data.csv",
            restore_path="landing/restored_data.csv"
        )

        assert result is True
        archive_bucket.copy_blob.assert_called_once()

    @patch('gdw_data_core.core.file_management.archiver.storage.Client')
    def test_restore_failure(self, mock_storage):
        """Test restoration failure handling."""
        client = Mock()
        mock_storage.return_value = client

        archive_bucket = Mock()
        archive_bucket.blob.side_effect = Exception("Restore failed")

        client.bucket.return_value = archive_bucket

        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket"
        )

        result = archiver.restore_from_archive(
            archive_path="archive/data.csv",
            restore_path="landing/data.csv"
        )

        assert result is False


class TestListArchivedFiles:
    """Test listing archived files."""

    @patch('gdw_data_core.core.file_management.archiver.storage.Client')
    def test_list_archived_files(self, mock_storage):
        """Test listing archived files."""
        client = Mock()
        mock_storage.return_value = client

        bucket = Mock()
        blob1 = Mock()
        blob1.name = "archive/2025/file1.csv"
        blob2 = Mock()
        blob2.name = "archive/2025/file2.csv"
        blobs = [blob1, blob2]
        bucket.list_blobs.return_value = blobs

        client.bucket.return_value = bucket

        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket"
        )

        files = archiver.list_archived_files()

        assert len(files) == 2
        assert "archive/2025/file1.csv" in files

    @patch('gdw_data_core.core.file_management.archiver.storage.Client')
    def test_list_archived_files_with_prefix(self, mock_storage):
        """Test listing with custom prefix."""
        client = Mock()
        mock_storage.return_value = client

        bucket = Mock()
        bucket.list_blobs.return_value = []

        client.bucket.return_value = bucket

        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket"
        )

        archiver.list_archived_files(prefix="archive/2025/12/")

        bucket.list_blobs.assert_called_once_with(prefix="archive/2025/12/")

    @patch('gdw_data_core.core.file_management.archiver.storage.Client')
    def test_list_archived_files_error(self, mock_storage):
        """Test error handling when listing fails."""
        client = Mock()
        mock_storage.return_value = client

        bucket = Mock()
        bucket.list_blobs.side_effect = Exception("List failed")

        client.bucket.return_value = bucket

        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket"
        )

        files = archiver.list_archived_files()

        assert files == []


class TestArchiverEdgeCases:
    """Test edge cases for FileArchiver to improve coverage."""

    @patch('gdw_data_core.core.file_management.archiver.storage.Client')
    def test_create_failed_result_structure(self, mock_storage):
        """Test _create_failed_result returns correct structure."""
        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket"
        )
        result = archiver._create_failed_result(
            source_path="test.csv",
            archive_path="archive/test.csv",
            error="Test error"
        )
        assert result.success is False
        assert result.error == "Test error"
        assert result.status == ArchiveStatus.FAILED
        assert result.source_path == "test.csv"
        assert result.archive_path == "archive/test.csv"

    @patch('gdw_data_core.core.file_management.archiver.storage.Client')
    def test_record_audit_with_error_message(self, mock_storage, mock_audit_logger):
        """Test audit recording includes error message."""
        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket",
            audit_logger=mock_audit_logger
        )
        archiver._record_audit(
            source_path="test.csv",
            archive_path="archive/test.csv",
            timestamp=datetime.now(timezone.utc),
            file_size=0,
            status="FAILED",
            error_message="Permission denied"
        )
        mock_audit_logger.log_entry.assert_called_once()
        call_args = mock_audit_logger.log_entry.call_args
        assert "Permission denied" in str(call_args)

    @patch('gdw_data_core.core.file_management.archiver.storage.Client')
    def test_record_audit_exception_handling(self, mock_storage, mock_audit_logger):
        """Test that audit recording handles exceptions gracefully."""
        mock_audit_logger.log_entry.side_effect = Exception("Audit service unavailable")

        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket",
            audit_logger=mock_audit_logger
        )

        # Should not raise exception
        archiver._record_audit(
            source_path="test.csv",
            archive_path="archive/test.csv",
            timestamp=datetime.now(timezone.utc),
            file_size=1024,
            status="SUCCESS"
        )

    @patch('gdw_data_core.core.file_management.archiver.storage.Client')
    def test_record_audit_without_logger(self, mock_storage):
        """Test that audit recording is skipped when no logger configured."""
        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket",
            audit_logger=None
        )

        # Should not raise exception
        archiver._record_audit(
            source_path="test.csv",
            archive_path="archive/test.csv",
            timestamp=datetime.now(timezone.utc),
            file_size=1024,
            status="SUCCESS"
        )

    @patch('gdw_data_core.core.file_management.archiver.storage.Client')
    def test_archive_file_with_gcs_copy_error_and_audit(self, mock_storage, mock_audit_logger):
        """Test that GCS copy errors are recorded to audit trail."""
        client = Mock()
        mock_storage.return_value = client

        source_bucket = Mock()
        source_blob = Mock()
        source_blob.exists.return_value = True
        source_blob.size = 1024
        source_blob.md5_hash = "abc123"
        source_bucket.blob.return_value = source_blob
        source_bucket.copy_blob.side_effect = Exception("Copy failed")

        archive_bucket = Mock()

        def get_bucket(name):
            if name == "source-bucket":
                return source_bucket
            return archive_bucket

        client.bucket = get_bucket

        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket",
            audit_logger=mock_audit_logger
        )

        result = archiver.archive_file(source_path="test.csv")

        assert result.success is False
        assert result.status == ArchiveStatus.FAILED
        mock_audit_logger.log_entry.assert_called()

    @patch('gdw_data_core.core.file_management.archiver.storage.Client')
    def test_restore_with_audit_logging(self, mock_storage, mock_audit_logger):
        """Test restoration records to audit trail."""
        client = Mock()
        mock_storage.return_value = client

        archive_bucket = Mock()
        archive_blob = Mock()
        archive_blob.size = 1024
        archive_bucket.blob.return_value = archive_blob
        archive_bucket.copy_blob = Mock()

        source_bucket = Mock()

        def get_bucket(name):
            if name == "archive-bucket":
                return archive_bucket
            return source_bucket

        client.bucket = get_bucket

        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket",
            audit_logger=mock_audit_logger
        )

        result = archiver.restore_from_archive(
            archive_path="archive/data.csv",
            restore_path="landing/data.csv"
        )

        assert result is True
        mock_audit_logger.log_entry.assert_called()
        call_args = mock_audit_logger.log_entry.call_args
        assert "RESTORED" in str(call_args)


class TestBatchArchiveEdgeCases:
    """Test edge cases for batch archiving."""

    @patch('gdw_data_core.core.file_management.archiver.storage.Client')
    def test_batch_archive_all_failed(self, mock_storage):
        """Test batch archive when all files fail."""
        client = Mock()
        mock_storage.return_value = client

        source_bucket = Mock()
        source_blob = Mock()
        source_blob.exists.return_value = False  # All files missing
        source_bucket.blob.return_value = source_blob

        client.bucket.return_value = source_bucket

        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket"
        )

        result = archiver.archive_batch_with_summary(
            source_paths=["file1.csv", "file2.csv", "file3.csv"],
            entity="test"
        )

        assert result.overall_status == ArchiveStatus.FAILED
        assert result.failed_count == 3
        assert result.successful_count == 0

    @patch('gdw_data_core.core.file_management.archiver.storage.Client')
    def test_batch_archive_partial_success(self, mock_storage):
        """Test batch archive with some successes and failures."""
        client = Mock()
        mock_storage.return_value = client

        source_bucket = Mock()
        call_count = [0]

        def mock_blob(path):
            blob = Mock()
            # First file succeeds, second fails
            blob.exists.return_value = call_count[0] % 2 == 0
            blob.size = 1024
            blob.md5_hash = "abc123"
            call_count[0] += 1
            return blob

        source_bucket.blob = mock_blob
        source_bucket.copy_blob = Mock()

        archive_bucket = Mock()

        def get_bucket(name):
            if name == "source-bucket":
                return source_bucket
            return archive_bucket

        client.bucket = get_bucket

        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket"
        )

        result = archiver.archive_batch_with_summary(
            source_paths=["file1.csv", "file2.csv"],
            entity="test"
        )

        assert result.overall_status == ArchiveStatus.PARTIAL
        assert result.successful_count >= 1
        assert result.failed_count >= 1

    @patch('gdw_data_core.core.file_management.archiver.storage.Client')
    def test_batch_archive_returns_dict(self, mock_storage):
        """Test that archive_batch returns a dictionary."""
        client = Mock()
        mock_storage.return_value = client

        source_bucket = Mock()
        source_blob = Mock()
        source_blob.exists.return_value = True
        source_blob.size = 1024
        source_blob.md5_hash = "abc123"
        source_bucket.blob.return_value = source_blob
        source_bucket.copy_blob = Mock()

        archive_bucket = Mock()

        def get_bucket(name):
            if name == "source-bucket":
                return source_bucket
            return archive_bucket

        client.bucket = get_bucket

        archiver = FileArchiver(
            source_bucket="source-bucket",
            archive_bucket="archive-bucket"
        )

        result = archiver.archive_batch(
            source_paths=["file1.csv", "file2.csv"],
            entity="test"
        )

        assert isinstance(result, dict)
        assert "file1.csv" in result
        assert "file2.csv" in result
        assert all(isinstance(r, ArchiveResult) for r in result.values())


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

