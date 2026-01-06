"""
File I/O Utilities Unit Tests

Tests for file management utilities including validation, archival,
metadata extraction, and lifecycle management for GCS operations.

Tests: FileValidator, FileArchiver, FileMetadataExtractor, FileLifecycleManager
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timedelta
from io import BytesIO
from typing import Dict, List, Any

from gcp_pipeline_beam.file_management import (
    FileValidator,
    FileArchiver,
    FileMetadataExtractor,
    FileLifecycleManager
)


class TestFileValidator:
    """Test suite for FileValidator."""

    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    def test_validate_file_exists_success(self, mock_client):
        """Test that file existence check returns True for existing file."""
        validator = FileValidator("test-bucket")
        validator.storage_client = mock_client.return_value
        validator.storage_client.bucket.return_value.blob.return_value.exists.return_value = True

        result = validator.validate_file_exists("test.csv")

        assert result is True
        validator.storage_client.bucket.assert_called_with("test-bucket")

    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    def test_validate_file_exists_not_found(self, mock_client):
        """Test that file existence check returns False for missing file."""
        validator = FileValidator("test-bucket")
        validator.storage_client = mock_client.return_value
        validator.storage_client.bucket.return_value.blob.return_value.exists.return_value = False

        result = validator.validate_file_exists("missing.csv")

        assert result is False

    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    def test_validate_file_not_empty_success(self, mock_client):
        """Test that file size check passes for non-empty file."""
        validator = FileValidator("test-bucket")
        validator.storage_client = mock_client.return_value
        validator.storage_client.bucket.return_value.blob.return_value.size = 1024 * 100

        result = validator.validate_file_not_empty("test.csv")

        assert result is True

    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    def test_validate_file_not_empty_fails(self, mock_client):
        """Test that file size check fails for empty file."""
        validator = FileValidator("test-bucket")
        validator.storage_client = mock_client.return_value
        validator.storage_client.bucket.return_value.blob.return_value.size = 0

        result = validator.validate_file_not_empty("empty.csv")

        assert result is False

    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    def test_validate_csv_format_success(self, mock_client):
        """Test CSV format validation with correct headers."""
        validator = FileValidator("test-bucket")
        validator.storage_client = mock_client.return_value
        csv_content = b"application_id,ssn,loan_amount\nAPP001,123-45-6789,250000"
        validator.storage_client.bucket.return_value.blob.return_value.download_as_string.return_value = csv_content

        is_valid, errors = validator.validate_csv_format(
            "test.csv",
            expected_columns=["application_id", "ssn", "loan_amount"]
        )

        assert is_valid is True
        assert len(errors) == 0

    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    def test_validate_csv_format_missing_columns(self, mock_client):
        """Test CSV validation fails with missing columns."""
        validator = FileValidator("test-bucket")
        validator.storage_client = mock_client.return_value
        csv_content = b"application_id,ssn\nAPP001,123-45-6789"
        validator.storage_client.bucket.return_value.blob.return_value.download_as_string.return_value = csv_content

        is_valid, errors = validator.validate_csv_format(
            "test.csv",
            expected_columns=["application_id", "ssn", "loan_amount"]
        )

        assert is_valid is False
        assert len(errors) > 0
        assert "loan_amount" in str(errors)

    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    def test_validate_encoding_utf8(self, mock_client):
        """Test UTF-8 encoding validation."""
        validator = FileValidator("test-bucket")
        validator.storage_client = mock_client.return_value
        validator.storage_client.bucket.return_value.blob.return_value.download_as_string.return_value = (
            "valid utf-8 content".encode('utf-8')
        )

        result = validator.validate_encoding("test.csv")

        assert result is True

    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    def test_validate_encoding_invalid(self, mock_client):
        """Test encoding validation fails for invalid encoding."""
        validator = FileValidator("test-bucket")
        validator.storage_client = mock_client.return_value
        # Create bytes that are invalid UTF-8
        invalid_bytes = b'\x80\x81\x82\x83'
        validator.storage_client.bucket.return_value.blob.return_value.download_as_string.return_value = invalid_bytes

        result = validator.validate_encoding("test.csv")

        assert result is False

    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    def test_validate_multiple_checks_all_pass(self, mock_client):
        """Test multiple validation checks all passing."""
        validator = FileValidator("test-bucket")
        validator.storage_client = mock_client.return_value
        validator.storage_client.bucket.return_value.blob.return_value.exists.return_value = True
        validator.storage_client.bucket.return_value.blob.return_value.size = 5000

        exists = validator.validate_file_exists("test.csv")
        not_empty = validator.validate_file_not_empty("test.csv")

        assert exists is True
        assert not_empty is True

    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    def test_validate_file_with_special_characters(self, mock_client):
        """Test validation of files with special characters in name."""
        validator = FileValidator("test-bucket")
        validator.storage_client = mock_client.return_value
        validator.storage_client.bucket.return_value.blob.return_value.exists.return_value = True

        result = validator.validate_file_exists("app-extract_2025-01-15.csv")

        assert result is True


class TestFileArchiver:
    """Test suite for FileArchiver."""

    @patch('gcp_pipeline_builder.file_management.archiver.storage.Client')
    def test_archive_file_success(self, mock_client):
        """Test successful file archival."""
        archiver = FileArchiver("source-bucket", "archive-bucket")
        archiver.storage_client = mock_client.return_value
        source_blob = Mock()
        source_blob.name = "uploads/test.csv"
        archiver.storage_client.bucket.return_value.blob.return_value = source_blob
        archiver.storage_client.bucket.return_value.copy_blob.return_value = Mock()

        result = archiver.archive_file("test.csv")

        assert result is not None
        archive_path = result.archive_path if hasattr(result, 'archive_path') else result
        assert "archive" in archive_path
        assert "test.csv" in archive_path

    @patch('gcp_pipeline_builder.file_management.archiver.storage.Client')
    def test_archive_file_with_custom_path(self, mock_client):
        """Test archival with custom archive path."""
        archiver = FileArchiver("source-bucket", "archive-bucket")
        archiver.storage_client = mock_client.return_value
        source_blob = Mock()
        custom_path = "custom/archive/test.csv"
        archiver.storage_client.bucket.return_value.blob.return_value = source_blob
        archiver.storage_client.bucket.return_value.copy_blob.return_value = Mock()

        result = archiver.archive_file("test.csv", archive_path=custom_path)

        archive_path = result.archive_path if hasattr(result, 'archive_path') else result
        assert custom_path == archive_path

    @patch('gcp_pipeline_builder.file_management.archiver.storage.Client')
    def test_archive_batch_success(self, mock_client):
        """Test archiving multiple files."""
        archiver = FileArchiver("source-bucket", "archive-bucket")
        archiver.storage_client = mock_client.return_value
        source_blob = Mock()
        archiver.storage_client.bucket.return_value.blob.return_value = source_blob
        archiver.storage_client.bucket.return_value.copy_blob.return_value = Mock()

        files = ["file1.csv", "file2.csv", "file3.csv"]
        result = archiver.archive_batch(files)

        assert isinstance(result, dict)
        assert len(result) == 3

    @patch('gcp_pipeline_builder.file_management.archiver.storage.Client')
    def test_archive_path_formatting(self, mock_client):
        """Test that archive path is properly formatted."""
        archiver = FileArchiver("source-bucket", "archive-bucket")
        archiver.storage_client = mock_client.return_value
        source_blob = Mock()
        archiver.storage_client.bucket.return_value.blob.return_value = source_blob
        archiver.storage_client.bucket.return_value.copy_blob.return_value = Mock()

        result = archiver.archive_file("test.csv")

        archive_path = result.archive_path if hasattr(result, 'archive_path') else result
        assert "/" in archive_path
        assert "test.csv" in archive_path
        assert "archive/" in archive_path

    @patch('gcp_pipeline_builder.file_management.archiver.storage.Client')
    def test_restore_from_archive_success(self, mock_client):
        """Test restoring file from archive."""
        archiver = FileArchiver("source-bucket", "archive-bucket")
        archiver.storage_client = mock_client.return_value
        source_blob = Mock()
        archiver.storage_client.bucket.return_value.blob.return_value = source_blob
        archiver.storage_client.bucket.return_value.copy_blob.return_value = Mock()

        result = archiver.restore_from_archive(
            "archive/2025-01-15/test.csv",
            "restore/test.csv"
        )

        assert result is True

    @patch('gcp_pipeline_builder.file_management.archiver.storage.Client')
    def test_list_archived_files(self, mock_client):
        """Test listing archived files."""
        archiver = FileArchiver("source-bucket", "archive-bucket")
        archiver.storage_client = mock_client.return_value
        mock_blob1 = Mock()
        mock_blob1.name = "archive/2025-01-15/file1.csv"
        mock_blob2 = Mock()
        mock_blob2.name = "archive/2025-01-15/file2.csv"
        archiver.storage_client.bucket.return_value.list_blobs.return_value = [
            mock_blob1, mock_blob2
        ]

        files = archiver.list_archived_files()

        assert len(files) == 2
        assert "archive/2025-01-15/file1.csv" in files


class TestFileMetadataExtractor:
    """Test suite for FileMetadataExtractor."""

    @patch('gcp_pipeline_builder.file_management.metadata.storage.Client')
    def test_get_file_size(self, mock_client):
        """Test file size extraction."""
        extractor = FileMetadataExtractor("test-bucket")
        extractor.storage_client = mock_client.return_value
        blob = Mock()
        blob.size = 1024 * 1024  # 1 MB
        extractor.storage_client.bucket.return_value.blob.return_value = blob

        size = extractor.get_file_size("test.csv")

        assert size == 1024 * 1024

    @patch('gcp_pipeline_builder.file_management.metadata.storage.Client')
    def test_get_file_created_time(self, mock_client):
        """Test file creation time extraction."""
        extractor = FileMetadataExtractor("test-bucket")
        extractor.storage_client = mock_client.return_value
        blob = Mock()
        test_time = datetime(2025, 1, 15, 10, 30, 0)
        blob.time_created = test_time
        extractor.storage_client.bucket.return_value.blob.return_value = blob

        created_time = extractor.get_file_created_time("test.csv")

        assert created_time == test_time

    @patch('gcp_pipeline_builder.file_management.metadata.storage.Client')
    def test_get_file_modified_time(self, mock_client):
        """Test file modified time extraction."""
        extractor = FileMetadataExtractor("test-bucket")
        extractor.storage_client = mock_client.return_value
        blob = Mock()
        test_time = datetime(2025, 1, 15, 11, 45, 0)
        blob.updated = test_time
        extractor.storage_client.bucket.return_value.blob.return_value = blob

        modified_time = extractor.get_file_modified_time("test.csv")

        assert modified_time == test_time

    @patch('gcp_pipeline_builder.file_management.metadata.storage.Client')
    def test_get_csv_row_count(self, mock_client):
        """Test CSV row count extraction."""
        extractor = FileMetadataExtractor("test-bucket")
        extractor.storage_client = mock_client.return_value
        csv_content = b"col1,col2,col3\nval1,val2,val3\nval4,val5,val6"
        blob = Mock()
        blob.download_as_string.return_value = csv_content
        extractor.storage_client.bucket.return_value.blob.return_value = blob

        row_count = extractor.get_csv_row_count("test.csv")

        assert row_count == 2  # 2 data rows (excluding header)

    @patch('gcp_pipeline_builder.file_management.metadata.storage.Client')
    def test_get_csv_columns(self, mock_client):
        """Test CSV column extraction."""
        extractor = FileMetadataExtractor("test-bucket")
        extractor.storage_client = mock_client.return_value
        csv_content = b"application_id,ssn,loan_amount\nAPP001,123-45-6789,250000"
        blob = Mock()
        blob.download_as_string.return_value = csv_content
        extractor.storage_client.bucket.return_value.blob.return_value = blob

        columns = extractor.get_csv_columns("test.csv")

        assert "application_id" in columns
        assert "ssn" in columns
        assert "loan_amount" in columns
        assert len(columns) == 3

    @patch('gcp_pipeline_builder.file_management.metadata.storage.Client')
    def test_get_file_checksum(self, mock_client):
        """Test file checksum calculation."""
        extractor = FileMetadataExtractor("test-bucket")
        extractor.storage_client = mock_client.return_value
        blob = Mock()
        blob.md5_hash = "abc123hash"
        extractor.storage_client.bucket.return_value.blob.return_value = blob

        checksum = extractor.get_file_checksum("test.csv")

        assert checksum == "abc123hash"

    @patch('gcp_pipeline_builder.file_management.metadata.storage.Client')
    def test_extract_all_metadata(self, mock_client):
        """Test extracting all metadata at once."""
        extractor = FileMetadataExtractor("test-bucket")
        extractor.storage_client = mock_client.return_value
        blob = Mock()
        blob.size = 5000
        blob.time_created = datetime(2025, 1, 15, 10, 0, 0)
        blob.updated = datetime(2025, 1, 15, 11, 0, 0)
        blob.md5_hash = "hash"
        blob.download_as_string.return_value = b"col1,col2\nval1,val2"
        extractor.storage_client.bucket.return_value.blob.return_value = blob

        metadata = extractor.extract_all_metadata("test.csv")

        assert metadata.file_size == 5000
        assert metadata.checksum == "hash"
        assert metadata.row_count == 1
        assert "col1" in metadata.columns


class TestFileLifecycleManager:
    """Test suite for FileLifecycleManager."""

    @patch('gcp_pipeline_builder.file_management.lifecycle.storage.Client')
    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    @patch('gcp_pipeline_builder.file_management.archiver.storage.Client')
    @patch('gcp_pipeline_builder.file_management.metadata.storage.Client')
    def test_validate_file_success(self, mock_metadata, mock_archiver, mock_validator, mock_lifecycle):
        """Test successful file validation."""
        manager = FileLifecycleManager("source-bucket", "archive-bucket")
        manager.validator.get_validation_errors = Mock(return_value=[])

        is_valid, errors = manager.validate_file("test.csv")

        assert is_valid is True
        assert len(errors) == 0

    @patch('gcp_pipeline_builder.file_management.lifecycle.storage.Client')
    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    @patch('gcp_pipeline_builder.file_management.archiver.storage.Client')
    @patch('gcp_pipeline_builder.file_management.metadata.storage.Client')
    def test_validate_file_failure(self, mock_metadata, mock_archiver, mock_validator, mock_lifecycle):
        """Test file validation failure."""
        manager = FileLifecycleManager("source-bucket", "archive-bucket")
        manager.validator.get_validation_errors = Mock(return_value=["File does not exist"])

        is_valid, errors = manager.validate_file("missing.csv")

        assert is_valid is False

    @patch('gcp_pipeline_builder.file_management.lifecycle.storage.Client')
    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    @patch('gcp_pipeline_builder.file_management.archiver.storage.Client')
    @patch('gcp_pipeline_builder.file_management.metadata.storage.Client')
    def test_complete_lifecycle_success(self, mock_metadata, mock_archiver, mock_validator, mock_lifecycle):
        """Test successful complete lifecycle."""
        manager = FileLifecycleManager("source-bucket", "archive-bucket")
        manager.validator.get_validation_errors = Mock(return_value=[])
        manager.archiver.archive_file = Mock(return_value="archive/test.csv")

        def mock_process(file_path):
            return True

        result = manager.complete_lifecycle("test.csv", mock_process)

        assert result is not None

    @patch('gcp_pipeline_builder.file_management.lifecycle.storage.Client')
    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    @patch('gcp_pipeline_builder.file_management.archiver.storage.Client')
    @patch('gcp_pipeline_builder.file_management.metadata.storage.Client')
    def test_complete_lifecycle_validation_failure(self, mock_metadata, mock_archiver, mock_validator, mock_lifecycle):
        """Test lifecycle stops at validation failure."""
        manager = FileLifecycleManager("source-bucket", "archive-bucket")
        manager.validator.get_validation_errors = Mock(return_value=["File does not exist"])
        manager.archiver.archive_file = Mock()

        def mock_process(file_path):
            return True

        result = manager.complete_lifecycle("missing.csv", mock_process)

        # Should not proceed past validation
        manager.archiver.archive_file.assert_not_called()

    @patch('gcp_pipeline_builder.file_management.lifecycle.storage.Client')
    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    @patch('gcp_pipeline_builder.file_management.archiver.storage.Client')
    @patch('gcp_pipeline_builder.file_management.metadata.storage.Client')
    def test_handle_error_file(self, mock_metadata, mock_archiver, mock_validator, mock_lifecycle):
        """Test error file handling."""
        manager = FileLifecycleManager("source-bucket", "archive-bucket")
        manager.archiver.archive_file = Mock(return_value="error/bad.csv")

        result = manager.handle_error_file("bad.csv", "File format invalid")

        assert result is not None

    @patch('gcp_pipeline_builder.file_management.lifecycle.storage.Client')
    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    @patch('gcp_pipeline_builder.file_management.archiver.storage.Client')
    @patch('gcp_pipeline_builder.file_management.metadata.storage.Client')
    def test_get_file_status(self, mock_metadata, mock_archiver, mock_validator, mock_lifecycle):
        """Test getting file status."""
        manager = FileLifecycleManager("source-bucket", "archive-bucket")
        manager.metadata_extractor.extract_all_metadata = Mock(return_value={
            "size": 5000,
            "created_time": datetime.now(),
            "row_count": 100
        })

        status = manager.get_file_status("test.csv")

        assert status is not None
        assert isinstance(status, dict)

    @patch('gcp_pipeline_builder.file_management.lifecycle.storage.Client')
    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    @patch('gcp_pipeline_builder.file_management.archiver.storage.Client')
    @patch('gcp_pipeline_builder.file_management.metadata.storage.Client')
    def test_multiple_files_lifecycle(self, mock_metadata, mock_archiver, mock_validator, mock_lifecycle):
        """Test lifecycle for multiple files."""
        manager = FileLifecycleManager("source-bucket", "archive-bucket")
        manager.validator.get_validation_errors = Mock(return_value=[])
        manager.archiver.archive_file = Mock(return_value="archive/test.csv")

        files = ["file1.csv", "file2.csv", "file3.csv"]

        def mock_process(file_path):
            return True

        results = [manager.complete_lifecycle(f, mock_process) for f in files]

        assert len(results) == 3


class TestFileIntegration:
    """Integration tests for file operations."""

    @patch('gcp_pipeline_builder.file_management.lifecycle.storage.Client')
    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    @patch('gcp_pipeline_builder.file_management.archiver.storage.Client')
    @patch('gcp_pipeline_builder.file_management.metadata.storage.Client')
    def test_full_workflow_csv_file(self, mock_metadata, mock_archiver, mock_validator, mock_lifecycle):
        """Test full workflow with CSV file."""
        manager = FileLifecycleManager("source-bucket", "archive-bucket")
        manager.validator.get_validation_errors = Mock(return_value=[])
        manager.archiver.archive_file = Mock(return_value="archive/2025-01-15/test.csv")
        manager.metadata_extractor.get_file_size = Mock(return_value=10000)
        manager.metadata_extractor.get_csv_row_count = Mock(return_value=500)

        def process_fn(path):
            return True

        # Validate
        is_valid, errors = manager.validate_file("test.csv")
        assert is_valid is True

        # Archive
        archive_path = manager.archiver.archive_file("test.csv")
        assert archive_path is not None

        # Extract metadata
        size = manager.metadata_extractor.get_file_size("test.csv")
        row_count = manager.metadata_extractor.get_csv_row_count("test.csv")

        assert size == 10000
        assert row_count == 500

    @patch('gcp_pipeline_builder.file_management.lifecycle.storage.Client')
    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    @patch('gcp_pipeline_builder.file_management.archiver.storage.Client')
    @patch('gcp_pipeline_builder.file_management.metadata.storage.Client')
    def test_error_handling_workflow(self, mock_metadata, mock_archiver, mock_validator, mock_lifecycle):
        """Test error handling in workflow."""
        manager = FileLifecycleManager("source-bucket", "archive-bucket")
        manager.validator.get_validation_errors = Mock(return_value=["File does not exist"])
        manager.archiver.archive_file = Mock()

        # Validation should fail
        is_valid, errors = manager.validate_file("missing.csv")
        assert is_valid is False

        # Should not proceed to archival
        manager.archiver.archive_file.assert_not_called()

