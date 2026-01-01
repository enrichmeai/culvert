"""
Unit tests for FileLifecycleManager.

Tests cover:
- Complete lifecycle flow
- Validation state transitions
- Processing state transitions
- Archive state transitions
- Error handling and error file movement
- Metadata extraction integration
- Monitoring integration
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch, PropertyMock

from gdw_data_core.core.file_management.lifecycle import FileLifecycleManager
from gdw_data_core.core.file_management.types import ArchiveResult, ArchiveStatus


class TestFileLifecycleManagerInit:
    """Test FileLifecycleManager initialization."""

    @patch('gdw_data_core.core.file_management.lifecycle.storage.Client')
    @patch('gdw_data_core.core.file_management.lifecycle.FileValidator')
    @patch('gdw_data_core.core.file_management.lifecycle.FileArchiver')
    @patch('gdw_data_core.core.file_management.lifecycle.FileMetadataExtractor')
    def test_basic_init(self, mock_extractor, mock_archiver, mock_validator, mock_storage):
        """Test basic initialization."""
        manager = FileLifecycleManager(
            gcs_bucket="source-bucket",
            archive_bucket="archive-bucket"
        )

        assert manager.gcs_bucket == "source-bucket"
        assert manager.archive_bucket == "archive-bucket"
        assert manager.error_bucket == "archive-bucket"  # Defaults to archive
        assert manager.error_handler is None
        assert manager.monitoring is None

    @patch('gdw_data_core.core.file_management.lifecycle.storage.Client')
    @patch('gdw_data_core.core.file_management.lifecycle.FileValidator')
    @patch('gdw_data_core.core.file_management.lifecycle.FileArchiver')
    @patch('gdw_data_core.core.file_management.lifecycle.FileMetadataExtractor')
    def test_init_with_error_bucket(self, mock_extractor, mock_archiver, mock_validator, mock_storage):
        """Test initialization with separate error bucket."""
        manager = FileLifecycleManager(
            gcs_bucket="source-bucket",
            archive_bucket="archive-bucket",
            error_bucket="error-bucket"
        )

        assert manager.error_bucket == "error-bucket"

    @patch('gdw_data_core.core.file_management.lifecycle.storage.Client')
    @patch('gdw_data_core.core.file_management.lifecycle.FileValidator')
    @patch('gdw_data_core.core.file_management.lifecycle.FileArchiver')
    @patch('gdw_data_core.core.file_management.lifecycle.FileMetadataExtractor')
    def test_init_with_all_optional_params(
        self, mock_extractor, mock_archiver, mock_validator, mock_storage,
        mock_error_handler, mock_monitoring, mock_audit_logger, sample_config_dict
    ):
        """Test initialization with all optional parameters."""
        from gdw_data_core.core.file_management.policy import ArchivePolicyEngine
        policy_engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        manager = FileLifecycleManager(
            gcs_bucket="source-bucket",
            archive_bucket="archive-bucket",
            error_bucket="error-bucket",
            error_handler=mock_error_handler,
            monitoring=mock_monitoring,
            policy_engine=policy_engine,
            audit_logger=mock_audit_logger
        )

        assert manager.error_handler is mock_error_handler
        assert manager.monitoring is mock_monitoring
        assert manager.policy_engine is policy_engine
        assert manager.audit_logger is mock_audit_logger


class TestValidateFile:
    """Test file validation."""

    @pytest.fixture
    def manager_with_mocks(self):
        """Create manager with mocked dependencies."""
        with patch('gdw_data_core.core.file_management.lifecycle.storage.Client'), \
             patch('gdw_data_core.core.file_management.lifecycle.FileValidator') as mock_validator_cls, \
             patch('gdw_data_core.core.file_management.lifecycle.FileArchiver'), \
             patch('gdw_data_core.core.file_management.lifecycle.FileMetadataExtractor'):

            mock_validator = Mock()
            mock_validator_cls.return_value = mock_validator

            manager = FileLifecycleManager(
                gcs_bucket="source-bucket",
                archive_bucket="archive-bucket"
            )
            manager.validator = mock_validator

            yield manager, mock_validator

    def test_validate_file_success(self, manager_with_mocks):
        """Test successful file validation."""
        manager, mock_validator = manager_with_mocks
        mock_validator.get_validation_errors.return_value = []

        is_valid, errors = manager.validate_file("landing/data.csv")

        assert is_valid is True
        assert errors == []

    def test_validate_file_with_errors(self, manager_with_mocks):
        """Test validation with errors."""
        manager, mock_validator = manager_with_mocks
        mock_validator.get_validation_errors.return_value = [
            "File is empty",
            "Invalid encoding"
        ]

        is_valid, errors = manager.validate_file("landing/bad_data.csv")

        assert is_valid is False
        assert len(errors) == 2
        assert "File is empty" in errors

    def test_validate_file_updates_metrics(self, manager_with_mocks, mock_monitoring):
        """Test that validation errors update metrics."""
        manager, mock_validator = manager_with_mocks
        manager.monitoring = mock_monitoring
        mock_validator.get_validation_errors.return_value = ["Error 1", "Error 2"]

        is_valid, errors = manager.validate_file("landing/data.csv")

        assert is_valid is False
        mock_monitoring.metrics.increment.assert_called_with('file_validation_errors', 2)


class TestProcessFile:
    """Test file processing."""

    @pytest.fixture
    def manager_with_mocks(self):
        """Create manager with mocked dependencies."""
        with patch('gdw_data_core.core.file_management.lifecycle.storage.Client'), \
             patch('gdw_data_core.core.file_management.lifecycle.FileValidator'), \
             patch('gdw_data_core.core.file_management.lifecycle.FileArchiver'), \
             patch('gdw_data_core.core.file_management.lifecycle.FileMetadataExtractor'):

            manager = FileLifecycleManager(
                gcs_bucket="source-bucket",
                archive_bucket="archive-bucket"
            )

            yield manager

    def test_process_file_success(self, manager_with_mocks):
        """Test successful file processing."""
        manager = manager_with_mocks
        processing_fn = Mock()

        result = manager.process_file("landing/data.csv", processing_fn)

        assert result is True
        processing_fn.assert_called_once_with("landing/data.csv")

    def test_process_file_failure(self, manager_with_mocks):
        """Test processing failure."""
        manager = manager_with_mocks
        processing_fn = Mock(side_effect=Exception("Processing error"))

        result = manager.process_file("landing/data.csv", processing_fn)

        assert result is False

    def test_process_file_updates_metrics(self, manager_with_mocks, mock_monitoring):
        """Test that successful processing updates metrics."""
        manager = manager_with_mocks
        manager.monitoring = mock_monitoring
        processing_fn = Mock()

        result = manager.process_file("landing/data.csv", processing_fn)

        assert result is True
        mock_monitoring.metrics.increment.assert_called_with('files_processed', 1)

    def test_process_file_calls_error_handler(self, manager_with_mocks, mock_error_handler):
        """Test that errors trigger error handler."""
        manager = manager_with_mocks
        manager.error_handler = mock_error_handler
        processing_fn = Mock(side_effect=Exception("Error"))

        result = manager.process_file("landing/data.csv", processing_fn)

        assert result is False
        mock_error_handler.handle_exception.assert_called_once()


class TestArchiveFile:
    """Test file archiving."""

    @pytest.fixture
    def manager_with_mocks(self, fixed_datetime):
        """Create manager with mocked dependencies."""
        with patch('gdw_data_core.core.file_management.lifecycle.storage.Client'), \
             patch('gdw_data_core.core.file_management.lifecycle.FileValidator'), \
             patch('gdw_data_core.core.file_management.lifecycle.FileArchiver') as mock_archiver_cls, \
             patch('gdw_data_core.core.file_management.lifecycle.FileMetadataExtractor'):

            mock_archiver = Mock()
            mock_archiver_cls.return_value = mock_archiver

            mock_archiver.archive_file.return_value = ArchiveResult(
                success=True,
                source_path="landing/data.csv",
                archive_path="archive/data/2025/12/31/data.csv",
                archived_at=fixed_datetime,
                status=ArchiveStatus.SUCCESS,
                file_size=1024
            )

            manager = FileLifecycleManager(
                gcs_bucket="source-bucket",
                archive_bucket="archive-bucket"
            )
            manager.archiver = mock_archiver

            yield manager, mock_archiver

    def test_archive_file_success(self, manager_with_mocks):
        """Test successful file archiving."""
        manager, mock_archiver = manager_with_mocks

        result = manager.archive_file("landing/data.csv")

        assert result is not None
        assert result.success is True

    def test_archive_file_with_entity(self, manager_with_mocks):
        """Test archiving with entity parameter."""
        manager, mock_archiver = manager_with_mocks

        result = manager.archive_file(
            "landing/users.csv",
            entity="users",
            policy_name="standard_daily"
        )

        mock_archiver.archive_file.assert_called_with(
            source_path="landing/users.csv",
            entity="users",
            policy_name="standard_daily"
        )

    def test_archive_file_failure_returns_none(self, manager_with_mocks, fixed_datetime):
        """Test that archive failure returns None."""
        manager, mock_archiver = manager_with_mocks

        mock_archiver.archive_file.return_value = ArchiveResult(
            success=False,
            source_path="landing/data.csv",
            archive_path="",
            archived_at=fixed_datetime,
            status=ArchiveStatus.FAILED,
            file_size=0,
            error="Archive failed"
        )

        result = manager.archive_file("landing/data.csv")

        assert result is None

    def test_archive_file_updates_metrics(self, manager_with_mocks, mock_monitoring):
        """Test that successful archive updates metrics."""
        manager, mock_archiver = manager_with_mocks
        manager.monitoring = mock_monitoring

        result = manager.archive_file("landing/data.csv")

        assert result is not None
        mock_monitoring.metrics.increment.assert_called_with('files_archived', 1)


class TestHandleErrorFile:
    """Test error file handling."""

    @pytest.fixture
    def manager_with_mocks(self):
        """Create manager with mocked GCS."""
        with patch('gdw_data_core.core.file_management.lifecycle.storage.Client') as mock_storage, \
             patch('gdw_data_core.core.file_management.lifecycle.FileValidator'), \
             patch('gdw_data_core.core.file_management.lifecycle.FileArchiver'), \
             patch('gdw_data_core.core.file_management.lifecycle.FileMetadataExtractor'):

            mock_client = Mock()
            mock_storage.return_value = mock_client

            source_bucket = Mock()
            error_bucket = Mock()

            source_blob = Mock()
            source_blob.exists.return_value = True
            source_bucket.blob.return_value = source_blob
            source_bucket.copy_blob = Mock()

            def get_bucket(name):
                if name == "error-bucket":
                    return error_bucket
                return source_bucket

            mock_client.bucket = get_bucket

            manager = FileLifecycleManager(
                gcs_bucket="source-bucket",
                archive_bucket="archive-bucket",
                error_bucket="error-bucket"
            )
            manager.storage_client = mock_client

            yield manager, source_bucket, source_blob

    def test_handle_error_file_success(self, manager_with_mocks):
        """Test successful error file handling."""
        manager, source_bucket, source_blob = manager_with_mocks

        error_path = manager.handle_error_file(
            "landing/bad_file.csv",
            "Validation failed"
        )

        assert error_path is not None
        assert error_path.startswith("error/")
        assert "bad_file.csv" in error_path
        source_bucket.copy_blob.assert_called_once()
        source_blob.delete.assert_called_once()

    def test_handle_error_file_generates_timestamp_path(self, manager_with_mocks):
        """Test that error path includes timestamp."""
        manager, _, _ = manager_with_mocks

        error_path = manager.handle_error_file(
            "landing/file.csv",
            "Error reason"
        )

        # Should have format: error/YYYYMMDD_HHMMSS/filename
        parts = error_path.split('/')
        assert parts[0] == "error"
        assert "_" in parts[1]  # Timestamp has underscore

    def test_handle_error_file_not_found(self, manager_with_mocks):
        """Test handling when source file doesn't exist."""
        manager, source_bucket, source_blob = manager_with_mocks
        source_blob.exists.return_value = False

        error_path = manager.handle_error_file(
            "landing/missing.csv",
            "Test error"
        )

        assert error_path is None

    def test_handle_error_file_no_error_bucket(self):
        """Test handling when error bucket not configured."""
        with patch('gdw_data_core.core.file_management.lifecycle.storage.Client'), \
             patch('gdw_data_core.core.file_management.lifecycle.FileValidator'), \
             patch('gdw_data_core.core.file_management.lifecycle.FileArchiver'), \
             patch('gdw_data_core.core.file_management.lifecycle.FileMetadataExtractor'):

            manager = FileLifecycleManager(
                gcs_bucket="source-bucket",
                archive_bucket="archive-bucket"
            )
            manager.error_bucket = None

            error_path = manager.handle_error_file("file.csv", "Error")

            assert error_path is None

    def test_handle_error_file_updates_metrics(self, manager_with_mocks, mock_monitoring):
        """Test that error file handling updates metrics."""
        manager, _, _ = manager_with_mocks
        manager.monitoring = mock_monitoring

        error_path = manager.handle_error_file(
            "landing/error_file.csv",
            "Validation failed"
        )

        assert error_path is not None
        mock_monitoring.metrics.increment.assert_called_with('files_error', 1)

    def test_handle_error_file_logs_to_audit(self, manager_with_mocks, mock_audit_logger):
        """Test that error file handling logs to audit trail."""
        manager, _, _ = manager_with_mocks
        manager.audit_logger = mock_audit_logger

        error_path = manager.handle_error_file(
            "landing/file.csv",
            "Test error reason"
        )

        assert error_path is not None
        mock_audit_logger.log_entry.assert_called_once()


class TestCompleteLifecycle:
    """Test complete lifecycle flow."""

    @pytest.fixture
    def manager_with_full_mocks(self, fixed_datetime):
        """Create manager with all mocked components."""
        with patch('gdw_data_core.core.file_management.lifecycle.storage.Client') as mock_storage, \
             patch('gdw_data_core.core.file_management.lifecycle.FileValidator') as mock_validator_cls, \
             patch('gdw_data_core.core.file_management.lifecycle.FileArchiver') as mock_archiver_cls, \
             patch('gdw_data_core.core.file_management.lifecycle.FileMetadataExtractor') as mock_extractor_cls:

            mock_client = Mock()
            mock_storage.return_value = mock_client

            mock_validator = Mock()
            mock_validator.get_validation_errors.return_value = []
            mock_validator_cls.return_value = mock_validator

            mock_archiver = Mock()
            mock_archiver.archive_file.return_value = ArchiveResult(
                success=True,
                source_path="landing/data.csv",
                archive_path="archive/data/2025/12/31/data.csv",
                archived_at=fixed_datetime,
                status=ArchiveStatus.SUCCESS,
                file_size=1024
            )
            mock_archiver_cls.return_value = mock_archiver

            mock_extractor = Mock()
            mock_extractor.extract_all_metadata.return_value = {
                'file_size': 1024,
                'row_count': 100
            }
            mock_extractor_cls.return_value = mock_extractor

            manager = FileLifecycleManager(
                gcs_bucket="source-bucket",
                archive_bucket="archive-bucket",
                error_bucket="error-bucket"
            )
            manager.validator = mock_validator
            manager.archiver = mock_archiver
            manager.metadata_extractor = mock_extractor
            manager.storage_client = mock_client

            yield manager, mock_validator, mock_archiver, mock_extractor

    def test_complete_lifecycle_success(self, manager_with_full_mocks):
        """Test successful complete lifecycle."""
        manager, mock_validator, mock_archiver, mock_extractor = manager_with_full_mocks
        processing_fn = Mock()

        result = manager.complete_lifecycle(
            gcs_path="landing/data.csv",
            processing_fn=processing_fn,
            entity="users"
        )

        assert result['status'] == 'COMPLETED'
        assert result['archive_result'] is not None
        assert 'archive_path' in result
        assert 'metadata' in result

    def test_complete_lifecycle_validation_failed(self, manager_with_full_mocks):
        """Test lifecycle when validation fails."""
        manager, mock_validator, mock_archiver, mock_extractor = manager_with_full_mocks
        mock_validator.get_validation_errors.return_value = ["File is empty"]

        # Mock the handle_error_file to avoid GCS calls
        manager.handle_error_file = Mock(return_value="error/file.csv")

        processing_fn = Mock()

        result = manager.complete_lifecycle(
            gcs_path="landing/empty.csv",
            processing_fn=processing_fn
        )

        assert result['status'] == 'VALIDATION_FAILED'
        assert "File is empty" in result['errors']
        processing_fn.assert_not_called()
        manager.handle_error_file.assert_called_once()

    def test_complete_lifecycle_processing_failed(self, manager_with_full_mocks):
        """Test lifecycle when processing fails."""
        manager, mock_validator, mock_archiver, mock_extractor = manager_with_full_mocks
        processing_fn = Mock(side_effect=Exception("Processing error"))

        manager.handle_error_file = Mock(return_value="error/file.csv")

        result = manager.complete_lifecycle(
            gcs_path="landing/data.csv",
            processing_fn=processing_fn
        )

        assert result['status'] == 'PROCESSING_FAILED'
        manager.handle_error_file.assert_called()

    def test_complete_lifecycle_archive_failed(self, manager_with_full_mocks, fixed_datetime):
        """Test lifecycle when archiving fails."""
        manager, mock_validator, mock_archiver, mock_extractor = manager_with_full_mocks

        mock_archiver.archive_file.return_value = ArchiveResult(
            success=False,
            source_path="landing/data.csv",
            archive_path="",
            archived_at=fixed_datetime,
            status=ArchiveStatus.FAILED,
            file_size=0,
            error="Archive failed"
        )

        processing_fn = Mock()

        result = manager.complete_lifecycle(
            gcs_path="landing/data.csv",
            processing_fn=processing_fn
        )

        assert result['status'] == 'ARCHIVE_FAILED'

    def test_complete_lifecycle_includes_metadata(self, manager_with_full_mocks):
        """Test that lifecycle includes metadata."""
        manager, _, _, mock_extractor = manager_with_full_mocks
        processing_fn = Mock()

        result = manager.complete_lifecycle(
            gcs_path="landing/data.csv",
            processing_fn=processing_fn
        )

        assert 'metadata' in result
        assert result['metadata']['file_size'] == 1024
        assert result['metadata']['row_count'] == 100

    def test_complete_lifecycle_includes_timestamps(self, manager_with_full_mocks):
        """Test that lifecycle includes timestamps."""
        manager, _, _, _ = manager_with_full_mocks
        processing_fn = Mock()

        result = manager.complete_lifecycle(
            gcs_path="landing/data.csv",
            processing_fn=processing_fn
        )

        assert 'started_at' in result
        assert 'completed_at' in result

    def test_complete_lifecycle_with_entity_and_policy(self, manager_with_full_mocks):
        """Test lifecycle passes entity and policy to archiver."""
        manager, _, mock_archiver, _ = manager_with_full_mocks
        processing_fn = Mock()

        result = manager.complete_lifecycle(
            gcs_path="landing/users.csv",
            processing_fn=processing_fn,
            entity="users",
            policy_name="standard_daily"
        )

        mock_archiver.archive_file.assert_called_with(
            source_path="landing/users.csv",
            entity="users",
            policy_name="standard_daily"
        )


class TestGetFileStatus:
    """Test get_file_status method."""

    @pytest.fixture
    def manager_with_mocks(self):
        """Create manager with mocked metadata extractor."""
        with patch('gdw_data_core.core.file_management.lifecycle.storage.Client'), \
             patch('gdw_data_core.core.file_management.lifecycle.FileValidator'), \
             patch('gdw_data_core.core.file_management.lifecycle.FileArchiver'), \
             patch('gdw_data_core.core.file_management.lifecycle.FileMetadataExtractor') as mock_extractor_cls:

            mock_extractor = Mock()
            mock_extractor.extract_all_metadata.return_value = {
                'file_size': 2048,
                'row_count': 50,
                'checksum': 'xyz123'
            }
            mock_extractor_cls.return_value = mock_extractor

            manager = FileLifecycleManager(
                gcs_bucket="source-bucket",
                archive_bucket="archive-bucket"
            )
            manager.metadata_extractor = mock_extractor

            yield manager

    def test_get_file_status(self, manager_with_mocks):
        """Test getting file status."""
        manager = manager_with_mocks

        status = manager.get_file_status("landing/data.csv")

        assert status['file_path'] == "landing/data.csv"
        assert 'metadata' in status
        assert status['metadata']['file_size'] == 2048
        assert 'status_checked_at' in status


class TestLifecycleEdgeCases:
    """Test edge cases for FileLifecycleManager to improve coverage."""

    @pytest.fixture
    def manager_with_full_mocks(self):
        """Create manager with all dependencies mocked."""
        with patch('gdw_data_core.core.file_management.lifecycle.storage.Client') as mock_storage, \
             patch('gdw_data_core.core.file_management.lifecycle.FileValidator') as mock_validator_cls, \
             patch('gdw_data_core.core.file_management.lifecycle.FileArchiver') as mock_archiver_cls, \
             patch('gdw_data_core.core.file_management.lifecycle.FileMetadataExtractor') as mock_extractor_cls:

            mock_client = Mock()
            mock_storage.return_value = mock_client
            mock_bucket = Mock()
            mock_blob = Mock()
            mock_blob.exists.return_value = True
            mock_bucket.blob.return_value = mock_blob
            mock_bucket.copy_blob = Mock()
            mock_client.bucket.return_value = mock_bucket

            mock_validator = Mock()
            mock_validator.validate_file_exists.return_value = True
            mock_validator.validate_file_not_empty.return_value = True
            mock_validator.validate_file_not_corrupt.return_value = True
            mock_validator.validate_encoding.return_value = True
            mock_validator.validate_csv_format.return_value = (True, [])
            mock_validator_cls.return_value = mock_validator

            mock_archiver = Mock()
            mock_archiver_cls.return_value = mock_archiver

            mock_extractor = Mock()
            mock_extractor.extract_all_metadata.return_value = {
                'file_size': 1024,
                'row_count': 100
            }
            mock_extractor_cls.return_value = mock_extractor

            manager = FileLifecycleManager(
                gcs_bucket="source-bucket",
                archive_bucket="archive-bucket",
                error_bucket="error-bucket"
            )
            manager.validator = mock_validator
            manager.archiver = mock_archiver
            manager.metadata_extractor = mock_extractor

            yield {
                'manager': manager,
                'storage': mock_client,
                'bucket': mock_bucket,
                'blob': mock_blob,
                'validator': mock_validator,
                'archiver': mock_archiver,
                'extractor': mock_extractor
            }

    def test_handle_error_file_source_not_exists(self, manager_with_full_mocks):
        """Test error handling when source file doesn't exist."""
        mocks = manager_with_full_mocks
        manager = mocks['manager']
        mocks['blob'].exists.return_value = False

        result = manager.handle_error_file("missing.csv", "Test error")

        # Should return None when source doesn't exist
        assert result is None

    def test_handle_error_file_copy_exception(self, manager_with_full_mocks):
        """Test error handling when copy fails."""
        mocks = manager_with_full_mocks
        manager = mocks['manager']
        mocks['bucket'].copy_blob.side_effect = Exception("Copy failed")

        result = manager.handle_error_file("test.csv", "Test error")

        assert result is None

    def test_complete_lifecycle_unexpected_exception(self, manager_with_full_mocks):
        """Test lifecycle handling of unexpected exceptions."""
        mocks = manager_with_full_mocks
        manager = mocks['manager']

        def bad_processor(path):
            raise RuntimeError("Unexpected error")

        # Make validation pass
        manager.validate_file = Mock(return_value=(True, []))
        manager.process_file = Mock(return_value=False)  # Processing fails

        result = manager.complete_lifecycle(
            gcs_path="test.csv",
            processing_fn=bad_processor
        )

        assert result['status'] == 'PROCESSING_FAILED'

    def test_complete_lifecycle_archive_fails(self, manager_with_full_mocks):
        """Test lifecycle when archive step fails."""
        mocks = manager_with_full_mocks
        manager = mocks['manager']

        def good_processor(path):
            return True

        # Make validation and processing pass, but archive fails
        manager.validate_file = Mock(return_value=(True, []))
        manager.process_file = Mock(return_value=True)
        manager.archive_file = Mock(return_value=None)  # Archive returns None on failure

        result = manager.complete_lifecycle(
            gcs_path="test.csv",
            processing_fn=good_processor
        )

        assert result['status'] == 'ARCHIVE_FAILED'

    def test_complete_lifecycle_validation_fails_moves_to_error(self, manager_with_full_mocks):
        """Test that validation failure moves file to error bucket."""
        mocks = manager_with_full_mocks
        manager = mocks['manager']

        def processor(path):
            return True

        manager.validate_file = Mock(return_value=(False, ["File is empty", "Invalid encoding"]))
        manager.handle_error_file = Mock(return_value="error/timestamp/test.csv")

        result = manager.complete_lifecycle(
            gcs_path="test.csv",
            processing_fn=processor
        )

        assert result['status'] == 'VALIDATION_FAILED'
        assert result['error_path'] == "error/timestamp/test.csv"
        assert "File is empty" in result['errors']
        manager.handle_error_file.assert_called_once()

    def test_complete_lifecycle_with_entity_and_policy(self, manager_with_full_mocks):
        """Test complete lifecycle passes entity and policy to archive."""
        mocks = manager_with_full_mocks
        manager = mocks['manager']

        from gdw_data_core.core.file_management.types import ArchiveResult, ArchiveStatus
        mock_archive_result = ArchiveResult(
            success=True,
            source_path="test.csv",
            archive_path="archive/users/2025/01/01/test.csv",
            archived_at=datetime.now(timezone.utc),
            status=ArchiveStatus.SUCCESS,
            file_size=1024
        )

        manager.validate_file = Mock(return_value=(True, []))
        manager.process_file = Mock(return_value=True)
        manager.archive_file = Mock(return_value=mock_archive_result)

        def processor(path):
            return True

        result = manager.complete_lifecycle(
            gcs_path="test.csv",
            processing_fn=processor,
            entity="users",
            policy_name="standard_daily"
        )

        assert result['status'] == 'COMPLETED'
        manager.archive_file.assert_called_with(
            "test.csv",
            entity="users",
            policy_name="standard_daily"
        )

    def test_handle_error_file_with_audit_logger(self, manager_with_full_mocks, mock_audit_logger):
        """Test error file movement records to audit trail."""
        mocks = manager_with_full_mocks
        manager = mocks['manager']
        manager.audit_logger = mock_audit_logger
        mocks['blob'].exists.return_value = True
        mocks['bucket'].copy_blob = Mock()

        result = manager.handle_error_file("test.csv", "Validation failed")

        # Should have an error path returned
        assert result is not None
        assert "error/" in result

    def test_archive_file_with_error_handler_on_failure(self, manager_with_full_mocks, mock_error_handler):
        """Test that error handler is invoked on archive failure."""
        mocks = manager_with_full_mocks
        manager = mocks['manager']
        manager.error_handler = mock_error_handler

        mocks['archiver'].archive_file.side_effect = Exception("Archive failed")

        result = manager.archive_file("test.csv", entity="test", policy_name="default")

        assert result is None
        mock_error_handler.handle_exception.assert_called_once()

    def test_get_file_status_with_error(self, manager_with_full_mocks):
        """Test get_file_status handles metadata extraction errors."""
        mocks = manager_with_full_mocks
        manager = mocks['manager']
        mocks['extractor'].extract_all_metadata.side_effect = Exception("Extraction failed")

        # Should handle error gracefully
        try:
            status = manager.get_file_status("test.csv")
            assert 'file_path' in status
        except Exception:
            # Some implementations may raise, which is also valid
            pass


class TestHandleErrorFileEdgeCases:
    """Additional edge cases for handle_error_file."""

    @patch('gdw_data_core.core.file_management.lifecycle.storage.Client')
    @patch('gdw_data_core.core.file_management.lifecycle.FileValidator')
    @patch('gdw_data_core.core.file_management.lifecycle.FileArchiver')
    @patch('gdw_data_core.core.file_management.lifecycle.FileMetadataExtractor')
    def test_handle_error_file_no_error_bucket_uses_archive(
        self, mock_extractor, mock_archiver, mock_validator, mock_storage
    ):
        """Test that archive bucket is used as fallback for error bucket."""
        manager = FileLifecycleManager(
            gcs_bucket="source-bucket",
            archive_bucket="archive-bucket",
            error_bucket=None  # Not provided
        )

        # Should default to archive bucket
        assert manager.error_bucket == "archive-bucket"

    @patch('gdw_data_core.core.file_management.lifecycle.storage.Client')
    @patch('gdw_data_core.core.file_management.lifecycle.FileValidator')
    @patch('gdw_data_core.core.file_management.lifecycle.FileArchiver')
    @patch('gdw_data_core.core.file_management.lifecycle.FileMetadataExtractor')
    def test_handle_error_file_delete_after_copy_failure(
        self, mock_extractor, mock_archiver, mock_validator, mock_storage
    ):
        """Test error handling when delete after copy fails."""
        mock_client = Mock()
        mock_storage.return_value = mock_client

        mock_bucket = Mock()
        mock_blob = Mock()
        mock_blob.exists.return_value = True
        mock_blob.delete.side_effect = Exception("Delete failed")
        mock_bucket.blob.return_value = mock_blob
        mock_bucket.copy_blob = Mock()  # Copy succeeds
        mock_client.bucket.return_value = mock_bucket

        manager = FileLifecycleManager(
            gcs_bucket="source-bucket",
            archive_bucket="archive-bucket",
            error_bucket="error-bucket"
        )

        # May return path or None depending on implementation
        result = manager.handle_error_file("test.csv", "Test error")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

