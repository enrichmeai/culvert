"""
Unit tests for FileMetadata and FileMetadataExtractor.

Tests cover:
- File size extraction
- Timestamp extraction
- Row counting
- Column parsing
- Checksum retrieval
- All metadata extraction
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from gdw_data_core.core.file_management.metadata import FileMetadata, FileMetadataExtractor


class TestFileMetadata:
    """Test FileMetadata dataclass."""

    def test_create_file_metadata(self):
        """Test creating a FileMetadata instance."""
        metadata = FileMetadata(
            file_path="landing/data.csv",
            file_size=1024,
            created_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
            modified_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
            row_count=100,
            columns=["id", "name", "email"],
            checksum="abc123",
            extracted_at="2025-01-02T10:00:00Z"
        )

        assert metadata.file_path == "landing/data.csv"
        assert metadata.file_size == 1024
        assert metadata.row_count == 100
        assert len(metadata.columns) == 3

    def test_file_metadata_optional_fields(self):
        """Test FileMetadata with None optional fields."""
        metadata = FileMetadata(
            file_path="data.csv",
            file_size=0,
            created_time=None,
            modified_time=None,
            row_count=0,
            columns=[],
            checksum=None,
            extracted_at="2025-01-01T00:00:00Z"
        )

        assert metadata.created_time is None
        assert metadata.checksum is None


class TestFileMetadataExtractorInit:
    """Test FileMetadataExtractor initialization."""

    @patch('gdw_data_core.core.file_management.metadata.storage.Client')
    def test_init(self, mock_storage):
        """Test basic initialization."""
        extractor = FileMetadataExtractor(gcs_bucket="test-bucket")

        assert extractor.gcs_bucket == "test-bucket"
        mock_storage.assert_called_once()


class TestGetFileSize:
    """Test get_file_size method."""

    @pytest.fixture
    def extractor_with_mocks(self):
        """Create extractor with mocked GCS."""
        with patch('gdw_data_core.core.file_management.metadata.storage.Client') as mock_storage:
            mock_client = Mock()
            mock_storage.return_value = mock_client

            mock_bucket = Mock()
            mock_blob = Mock()
            mock_blob.size = 2048
            mock_bucket.blob.return_value = mock_blob

            mock_client.bucket.return_value = mock_bucket

            extractor = FileMetadataExtractor(gcs_bucket="test-bucket")

            yield extractor, mock_blob

    def test_get_file_size_success(self, extractor_with_mocks):
        """Test successful file size retrieval."""
        extractor, mock_blob = extractor_with_mocks
        mock_blob.size = 4096

        size = extractor.get_file_size("path/to/file.csv")

        assert size == 4096
        mock_blob.reload.assert_called_once()

    def test_get_file_size_none(self, extractor_with_mocks):
        """Test file size when blob size is None."""
        extractor, mock_blob = extractor_with_mocks
        mock_blob.size = None

        size = extractor.get_file_size("path/to/file.csv")

        assert size == 0

    def test_get_file_size_error(self, extractor_with_mocks):
        """Test file size on error."""
        extractor, mock_blob = extractor_with_mocks
        mock_blob.reload.side_effect = Exception("GCS Error")

        size = extractor.get_file_size("path/to/file.csv")

        assert size == 0


class TestGetFileTimestamps:
    """Test timestamp extraction methods."""

    @pytest.fixture
    def extractor_with_mocks(self):
        """Create extractor with mocked GCS."""
        with patch('gdw_data_core.core.file_management.metadata.storage.Client') as mock_storage:
            mock_client = Mock()
            mock_storage.return_value = mock_client

            mock_bucket = Mock()
            mock_blob = Mock()
            mock_blob.time_created = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
            mock_blob.updated = datetime(2025, 1, 2, 15, 30, 0, tzinfo=timezone.utc)
            mock_bucket.blob.return_value = mock_blob

            mock_client.bucket.return_value = mock_bucket

            extractor = FileMetadataExtractor(gcs_bucket="test-bucket")

            yield extractor, mock_blob

    def test_get_file_created_time(self, extractor_with_mocks):
        """Test getting file creation time."""
        extractor, mock_blob = extractor_with_mocks

        created_time = extractor.get_file_created_time("file.csv")

        assert created_time == datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    def test_get_file_modified_time(self, extractor_with_mocks):
        """Test getting file modification time."""
        extractor, mock_blob = extractor_with_mocks

        modified_time = extractor.get_file_modified_time("file.csv")

        assert modified_time == datetime(2025, 1, 2, 15, 30, 0, tzinfo=timezone.utc)

    def test_get_created_time_error(self, extractor_with_mocks):
        """Test created time on error."""
        extractor, mock_blob = extractor_with_mocks
        mock_blob.reload.side_effect = Exception("Error")

        created_time = extractor.get_file_created_time("file.csv")

        assert created_time is None

    def test_get_modified_time_error(self, extractor_with_mocks):
        """Test modified time on error."""
        extractor, mock_blob = extractor_with_mocks
        mock_blob.reload.side_effect = Exception("Error")

        modified_time = extractor.get_file_modified_time("file.csv")

        assert modified_time is None


class TestGetCsvRowCount:
    """Test CSV row counting."""

    @pytest.fixture
    def extractor_with_mocks(self):
        """Create extractor with mocked GCS."""
        with patch('gdw_data_core.core.file_management.metadata.storage.Client') as mock_storage:
            mock_client = Mock()
            mock_storage.return_value = mock_client

            mock_bucket = Mock()
            mock_blob = Mock()
            mock_bucket.blob.return_value = mock_blob

            mock_client.bucket.return_value = mock_bucket

            extractor = FileMetadataExtractor(gcs_bucket="test-bucket")

            yield extractor, mock_blob

    def test_get_csv_row_count(self, extractor_with_mocks, sample_csv_content):
        """Test counting CSV rows."""
        extractor, mock_blob = extractor_with_mocks
        mock_blob.download_as_string.return_value = sample_csv_content.encode('utf-8')

        count = extractor.get_csv_row_count("data.csv")

        # Sample CSV has header + 3 data rows
        assert count == 3

    def test_get_csv_row_count_empty_file(self, extractor_with_mocks):
        """Test row count for empty file."""
        extractor, mock_blob = extractor_with_mocks
        mock_blob.download_as_string.return_value = b""

        count = extractor.get_csv_row_count("empty.csv")

        assert count == 0

    def test_get_csv_row_count_header_only(self, extractor_with_mocks):
        """Test row count for file with header only."""
        extractor, mock_blob = extractor_with_mocks
        mock_blob.download_as_string.return_value = b"id,name,email\n"

        count = extractor.get_csv_row_count("header_only.csv")

        assert count == 0

    def test_get_csv_row_count_error(self, extractor_with_mocks):
        """Test row count on error."""
        extractor, mock_blob = extractor_with_mocks
        mock_blob.download_as_string.side_effect = Exception("Download error")

        count = extractor.get_csv_row_count("error.csv")

        assert count == 0


class TestGetCsvColumns:
    """Test CSV column extraction."""

    @pytest.fixture
    def extractor_with_mocks(self):
        """Create extractor with mocked GCS."""
        with patch('gdw_data_core.core.file_management.metadata.storage.Client') as mock_storage:
            mock_client = Mock()
            mock_storage.return_value = mock_client

            mock_bucket = Mock()
            mock_blob = Mock()
            mock_bucket.blob.return_value = mock_blob

            mock_client.bucket.return_value = mock_bucket

            extractor = FileMetadataExtractor(gcs_bucket="test-bucket")

            yield extractor, mock_blob

    def test_get_csv_columns(self, extractor_with_mocks, sample_csv_content):
        """Test extracting CSV columns."""
        extractor, mock_blob = extractor_with_mocks
        mock_blob.download_as_string.return_value = sample_csv_content.encode('utf-8')

        columns = extractor.get_csv_columns("data.csv")

        assert columns == ["id", "name", "email", "created_at"]

    def test_get_csv_columns_empty(self, extractor_with_mocks):
        """Test columns for empty file."""
        extractor, mock_blob = extractor_with_mocks
        mock_blob.download_as_string.return_value = b""

        columns = extractor.get_csv_columns("empty.csv")

        assert columns == []

    def test_get_csv_columns_error(self, extractor_with_mocks):
        """Test columns on error."""
        extractor, mock_blob = extractor_with_mocks
        mock_blob.download_as_string.side_effect = Exception("Error")

        columns = extractor.get_csv_columns("error.csv")

        assert columns == []


class TestGetFileChecksum:
    """Test file checksum retrieval."""

    @pytest.fixture
    def extractor_with_mocks(self):
        """Create extractor with mocked GCS."""
        with patch('gdw_data_core.core.file_management.metadata.storage.Client') as mock_storage:
            mock_client = Mock()
            mock_storage.return_value = mock_client

            mock_bucket = Mock()
            mock_blob = Mock()
            mock_blob.md5_hash = "abc123def456"
            mock_bucket.blob.return_value = mock_blob

            mock_client.bucket.return_value = mock_bucket

            extractor = FileMetadataExtractor(gcs_bucket="test-bucket")

            yield extractor, mock_blob

    def test_get_file_checksum(self, extractor_with_mocks):
        """Test getting file checksum."""
        extractor, mock_blob = extractor_with_mocks

        checksum = extractor.get_file_checksum("file.csv")

        assert checksum == "abc123def456"

    def test_get_file_checksum_none(self, extractor_with_mocks):
        """Test checksum when md5_hash is None."""
        extractor, mock_blob = extractor_with_mocks
        mock_blob.md5_hash = None

        checksum = extractor.get_file_checksum("file.csv")

        assert checksum is None

    def test_get_file_checksum_error(self, extractor_with_mocks):
        """Test checksum on error."""
        extractor, mock_blob = extractor_with_mocks
        mock_blob.reload.side_effect = Exception("Error")

        checksum = extractor.get_file_checksum("file.csv")

        assert checksum is None


class TestExtractAllMetadata:
    """Test extract_all_metadata method."""

    @pytest.fixture
    def extractor_with_mocks(self):
        """Create extractor with mocked GCS."""
        with patch('gdw_data_core.core.file_management.metadata.storage.Client') as mock_storage:
            mock_client = Mock()
            mock_storage.return_value = mock_client

            mock_bucket = Mock()
            mock_blob = Mock()
            mock_blob.size = 2048
            mock_blob.md5_hash = "checksum123"
            mock_blob.time_created = datetime(2025, 1, 1, tzinfo=timezone.utc)
            mock_blob.updated = datetime(2025, 1, 2, tzinfo=timezone.utc)
            mock_blob.download_as_string.return_value = b"id,name\n1,John\n2,Jane\n"
            mock_bucket.blob.return_value = mock_blob

            mock_client.bucket.return_value = mock_bucket

            extractor = FileMetadataExtractor(gcs_bucket="test-bucket")

            yield extractor, mock_blob

    def test_extract_all_metadata(self, extractor_with_mocks):
        """Test extracting all metadata."""
        extractor, mock_blob = extractor_with_mocks

        metadata = extractor.extract_all_metadata("data.csv")

        assert metadata.file_path == "data.csv"
        assert metadata.file_size == 2048
        assert metadata.extracted_at is not None

    def test_extract_all_metadata_partial_error(self, extractor_with_mocks):
        """Test that partial errors don't fail entire extraction."""
        extractor, mock_blob = extractor_with_mocks
        # Size works but download fails
        mock_blob.download_as_string.side_effect = Exception("Download error")

        metadata = extractor.extract_all_metadata("data.csv")

        # Should still have file_path and size
        assert metadata.file_path == "data.csv"
        assert metadata.file_size == 2048


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

