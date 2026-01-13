"""
Unit tests for GCSClient.

Tests mirror source: gcp_pipeline_core/core/clients/gcs_client.py

Run tests in isolation to avoid module caching issues:
    pytest gcp_pipeline_core/tests/unit/core/clients/test_gcs_client.py -v
"""

import pytest
import sys
from unittest.mock import patch, MagicMock



def _reload_gcs_client():
    """Force reload of gcs_client module to pick up mocks."""
    for mod in list(sys.modules.keys()):
        if 'gcs_client' in mod:
            del sys.modules[mod]
    from gcp_pipeline_core.clients.gcs_client import GCSClient
    return GCSClient


class TestGCSClientInit:
    """Tests for GCSClient initialization."""

    def test_init_success(self):
        """Test successful GCS client initialization."""
        with patch('gcp_pipeline_core.clients.gcs_client.storage.Client') as mock_client_class:
            mock_instance = MagicMock()
            mock_client_class.return_value = mock_instance

            GCSClient = _reload_gcs_client()
            client = GCSClient(project="test-project")

            assert client.project == "test-project"
            assert client.client == mock_instance
            mock_client_class.assert_called_once_with(project="test-project")

    def test_init_failure(self):
        """Test error handling on failed initialization."""
        with patch('gcp_pipeline_core.clients.gcs_client.storage.Client') as mock_client_class:
            mock_client_class.side_effect = Exception("GCS init error")

            GCSClient = _reload_gcs_client()
            with pytest.raises(Exception):
                GCSClient(project="test-project")


class TestGCSClientReadFile:
    """Tests for GCSClient.read_file method."""

    def test_read_file_success(self):
        """Test successful file read from GCS."""
        with patch('gcp_pipeline_core.clients.gcs_client.storage.Client') as mock_client_class:
            mock_blob = MagicMock()
            mock_blob.download_as_string.return_value = b"test content"
            mock_bucket = MagicMock()
            mock_bucket.blob.return_value = mock_blob
            mock_gcs_client = MagicMock()
            mock_gcs_client.bucket.return_value = mock_bucket
            mock_client_class.return_value = mock_gcs_client

            GCSClient = _reload_gcs_client()
            client = GCSClient(project="test-project")
            result = client.read_file("test-bucket", "test.txt")

            assert result == "test content"
            mock_gcs_client.bucket.assert_called_once_with("test-bucket")
            mock_bucket.blob.assert_called_once_with("test.txt")
            mock_blob.download_as_string.assert_called_once()

    def test_read_file_error_gcs_api(self):
        """Test error handling on GCS API error during read."""
        with patch('gcp_pipeline_core.clients.gcs_client.storage.Client') as mock_client_class:
            from google.api_core.exceptions import GoogleAPIError

            mock_blob = MagicMock()
            mock_blob.download_as_string.side_effect = GoogleAPIError("GCS API error")
            mock_bucket = MagicMock()
            mock_bucket.blob.return_value = mock_blob
            mock_gcs_client = MagicMock()
            mock_gcs_client.bucket.return_value = mock_bucket
            mock_client_class.return_value = mock_gcs_client

            GCSClient = _reload_gcs_client()
            client = GCSClient(project="test-project")
            with pytest.raises(IOError) as exc_info:
                client.read_file("test-bucket", "test.txt")
            assert "Failed to read" in str(exc_info.value)

    def test_read_file_error_general(self):
        """Test error handling on general error during read."""
        with patch('gcp_pipeline_core.clients.gcs_client.storage.Client') as mock_client_class:
            mock_gcs_client = MagicMock()
            mock_gcs_client.bucket.side_effect = Exception("General error")
            mock_client_class.return_value = mock_gcs_client

            GCSClient = _reload_gcs_client()
            client = GCSClient(project="test-project")
            with pytest.raises(IOError) as exc_info:
                client.read_file("test-bucket", "test.txt")
            assert "Failed to read" in str(exc_info.value)


class TestGCSClientWriteFile:
    """Tests for GCSClient.write_file method."""

    def test_write_file_success(self):
        """Test successful file write to GCS."""
        with patch('gcp_pipeline_core.clients.gcs_client.storage.Client') as mock_client_class:
            mock_blob = MagicMock()
            mock_bucket = MagicMock()
            mock_bucket.blob.return_value = mock_blob
            mock_gcs_client = MagicMock()
            mock_gcs_client.bucket.return_value = mock_bucket
            mock_client_class.return_value = mock_gcs_client

            GCSClient = _reload_gcs_client()
            client = GCSClient(project="test-project")
            result = client.write_file("test-bucket", "test.txt", "test content")

            assert result is True
            mock_gcs_client.bucket.assert_called_once_with("test-bucket")
            mock_bucket.blob.assert_called_once_with("test.txt")
            mock_blob.upload_from_string.assert_called_once_with("test content")

    def test_write_file_error(self):
        """Test error handling on failed file write."""
        with patch('gcp_pipeline_core.clients.gcs_client.storage.Client') as mock_client_class:
            from google.api_core.exceptions import GoogleAPIError

            mock_blob = MagicMock()
            mock_blob.upload_from_string.side_effect = GoogleAPIError("Write error")
            mock_bucket = MagicMock()
            mock_bucket.blob.return_value = mock_blob
            mock_gcs_client = MagicMock()
            mock_gcs_client.bucket.return_value = mock_bucket
            mock_client_class.return_value = mock_gcs_client

            GCSClient = _reload_gcs_client()
            client = GCSClient(project="test-project")
            with pytest.raises(IOError) as exc_info:
                client.write_file("test-bucket", "test.txt", "content")
            assert "Failed to write" in str(exc_info.value)


class TestGCSClientListFiles:
    """Tests for GCSClient.list_files method."""

    def test_list_files_success(self):
        """Test successful file listing from GCS."""
        with patch('gcp_pipeline_core.clients.gcs_client.storage.Client') as mock_client_class:
            mock_blob1 = MagicMock()
            mock_blob1.name = "file1.txt"
            mock_blob2 = MagicMock()
            mock_blob2.name = "file2.txt"
            mock_blob3 = MagicMock()
            mock_blob3.name = "file3.txt"

            mock_gcs_client = MagicMock()
            mock_gcs_client.list_blobs.return_value = [mock_blob1, mock_blob2, mock_blob3]
            mock_client_class.return_value = mock_gcs_client

            GCSClient = _reload_gcs_client()
            client = GCSClient(project="test-project")
            result = client.list_files("test-bucket", "prefix/")

            assert result == ["file1.txt", "file2.txt", "file3.txt"]
            mock_gcs_client.list_blobs.assert_called_once_with("test-bucket", prefix="prefix/")

    def test_list_files_empty(self):
        """Test file listing when bucket is empty."""
        with patch('gcp_pipeline_core.clients.gcs_client.storage.Client') as mock_client_class:
            mock_gcs_client = MagicMock()
            mock_gcs_client.list_blobs.return_value = []
            mock_client_class.return_value = mock_gcs_client

            GCSClient = _reload_gcs_client()
            client = GCSClient(project="test-project")
            result = client.list_files("test-bucket")

            assert result == []

    def test_list_files_error(self):
        """Test error handling on failed file listing."""
        with patch('gcp_pipeline_core.clients.gcs_client.storage.Client') as mock_client_class:
            from google.api_core.exceptions import GoogleAPIError

            mock_gcs_client = MagicMock()
            mock_gcs_client.list_blobs.side_effect = GoogleAPIError("List error")
            mock_client_class.return_value = mock_gcs_client

            GCSClient = _reload_gcs_client()
            client = GCSClient(project="test-project")
            with pytest.raises(IOError) as exc_info:
                client.list_files("test-bucket")
            assert "Failed to list" in str(exc_info.value)


class TestGCSClientArchiveFile:
    """Tests for GCSClient.archive_file method."""

    def test_archive_file_success(self):
        """Test successful file archiving."""
        with patch('gcp_pipeline_core.clients.gcs_client.storage.Client') as mock_client_class:
            mock_source_blob = MagicMock()
            mock_bucket = MagicMock()
            mock_bucket.blob.return_value = mock_source_blob
            mock_bucket.copy_blob.return_value = MagicMock()
            mock_gcs_client = MagicMock()
            mock_gcs_client.bucket.return_value = mock_bucket
            mock_client_class.return_value = mock_gcs_client

            GCSClient = _reload_gcs_client()
            client = GCSClient(project="test-project")
            result = client.archive_file("test-bucket", "source.txt", "archive/source.txt")

            assert result is True
            mock_gcs_client.bucket.assert_called_with("test-bucket")
            mock_bucket.blob.assert_called_once_with("source.txt")
            mock_bucket.copy_blob.assert_called_once()
            mock_source_blob.delete.assert_called_once()

    def test_archive_file_error(self):
        """Test error handling on failed file archiving."""
        with patch('gcp_pipeline_core.clients.gcs_client.storage.Client') as mock_client_class:
            from google.api_core.exceptions import GoogleAPIError

            mock_gcs_client = MagicMock()
            mock_gcs_client.bucket.side_effect = GoogleAPIError("Archive error")
            mock_client_class.return_value = mock_gcs_client

            GCSClient = _reload_gcs_client()
            client = GCSClient(project="test-project")
            with pytest.raises(IOError) as exc_info:
                client.archive_file("test-bucket", "source.txt", "archive/source.txt")
            assert "Failed to archive" in str(exc_info.value)
