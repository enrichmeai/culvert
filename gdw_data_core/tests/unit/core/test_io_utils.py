import pytest
from unittest.mock import patch, MagicMock
from gdw_data_core.core.clients import GCSClient, PubSubClient
from gdw_data_core.core.utilities import generate_run_id


def test_generate_run_id():
    """Test unique run ID generation."""
    run_id = generate_run_id("TEST_JOB")
    assert "TEST_JOB" in run_id
    assert len(run_id) > len("TEST_JOB") + 15


class TestGCSClient:
    """Unit tests for GCSClient."""

    @patch('gdw_data_core.core.clients.gcs_client.storage.Client')
    def test_init_success(self, mock_client_class):
        """Test successful GCS client initialization."""
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance

        client = GCSClient(project="test-project")

        assert client.project == "test-project"
        assert client.client == mock_instance
        mock_client_class.assert_called_once_with(project="test-project")

    @patch('gdw_data_core.core.clients.gcs_client.storage.Client')
    def test_init_failure(self, mock_client_class):
        """Test error handling on failed initialization."""
        mock_client_class.side_effect = Exception("GCS init error")

        with pytest.raises(Exception):
            GCSClient(project="test-project")

    @patch('gdw_data_core.core.clients.gcs_client.storage.Client')
    def test_read_file_success(self, mock_client_class):
        """Test successful file read from GCS."""
        # Setup mock
        mock_blob = MagicMock()
        mock_blob.download_as_string.return_value = b"test content"
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_gcs_client = MagicMock()
        mock_gcs_client.bucket.return_value = mock_bucket
        mock_client_class.return_value = mock_gcs_client

        # Execute
        client = GCSClient(project="test-project")
        result = client.read_file("test-bucket", "test.txt")

        # Assert
        assert result == "test content"
        mock_gcs_client.bucket.assert_called_once_with("test-bucket")
        mock_bucket.blob.assert_called_once_with("test.txt")
        mock_blob.download_as_string.assert_called_once()

    @patch('gdw_data_core.core.clients.gcs_client.storage.Client')
    def test_read_file_error_gcs_api(self, mock_client_class):
        """Test error handling on GCS API error during read."""
        from google.api_core.exceptions import GoogleAPIError

        # Setup mock to raise GCS API error
        mock_gcs_client = MagicMock()
        mock_gcs_client.bucket.side_effect = GoogleAPIError("GCS API error")
        mock_client_class.return_value = mock_gcs_client

        # Execute & Assert
        client = GCSClient(project="test-project")
        with pytest.raises(IOError) as exc_info:
            client.read_file("test-bucket", "test.txt")
        assert "Failed to read" in str(exc_info.value)

    @patch('gdw_data_core.core.clients.gcs_client.storage.Client')
    def test_read_file_error_general(self, mock_client_class):
        """Test error handling on general error during read."""
        # Setup mock to raise general error
        mock_gcs_client = MagicMock()
        mock_gcs_client.bucket.side_effect = Exception("General error")
        mock_client_class.return_value = mock_gcs_client

        # Execute & Assert
        client = GCSClient(project="test-project")
        with pytest.raises(IOError) as exc_info:
            client.read_file("test-bucket", "test.txt")
        assert "Failed to read" in str(exc_info.value)

    @patch('gdw_data_core.core.clients.gcs_client.storage.Client')
    def test_write_file_success(self, mock_client_class):
        """Test successful file write to GCS."""
        # Setup mock
        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_gcs_client = MagicMock()
        mock_gcs_client.bucket.return_value = mock_bucket
        mock_client_class.return_value = mock_gcs_client

        # Execute
        client = GCSClient(project="test-project")
        result = client.write_file("test-bucket", "test.txt", "test content")

        # Assert
        assert result is True
        mock_gcs_client.bucket.assert_called_once_with("test-bucket")
        mock_bucket.blob.assert_called_once_with("test.txt")
        mock_blob.upload_from_string.assert_called_once_with("test content")

    @patch('gdw_data_core.core.clients.gcs_client.storage.Client')
    def test_write_file_error(self, mock_client_class):
        """Test error handling on failed file write."""
        from google.api_core.exceptions import GoogleAPIError

        # Setup mock to raise error
        mock_gcs_client = MagicMock()
        mock_gcs_client.bucket.side_effect = GoogleAPIError("Write error")
        mock_client_class.return_value = mock_gcs_client

        # Execute & Assert
        client = GCSClient(project="test-project")
        with pytest.raises(IOError) as exc_info:
            client.write_file("test-bucket", "test.txt", "content")
        assert "Failed to write" in str(exc_info.value)

    @patch('gdw_data_core.core.clients.gcs_client.storage.Client')
    def test_list_files_success(self, mock_client_class):
        """Test successful file listing from GCS."""
        # Setup mock
        mock_blob1 = MagicMock()
        mock_blob1.name = "file1.txt"
        mock_blob2 = MagicMock()
        mock_blob2.name = "file2.txt"
        mock_blob3 = MagicMock()
        mock_blob3.name = "file3.txt"

        mock_gcs_client = MagicMock()
        mock_gcs_client.list_blobs.return_value = [mock_blob1, mock_blob2, mock_blob3]
        mock_client_class.return_value = mock_gcs_client

        # Execute
        client = GCSClient(project="test-project")
        result = client.list_files("test-bucket", "prefix/")

        # Assert
        assert result == ["file1.txt", "file2.txt", "file3.txt"]
        mock_gcs_client.list_blobs.assert_called_once_with("test-bucket", prefix="prefix/")

    @patch('gdw_data_core.core.clients.gcs_client.storage.Client')
    def test_list_files_empty(self, mock_client_class):
        """Test file listing when bucket is empty."""
        # Setup mock
        mock_gcs_client = MagicMock()
        mock_gcs_client.list_blobs.return_value = []
        mock_client_class.return_value = mock_gcs_client

        # Execute
        client = GCSClient(project="test-project")
        result = client.list_files("test-bucket")

        # Assert
        assert result == []

    @patch('gdw_data_core.core.clients.gcs_client.storage.Client')
    def test_list_files_error(self, mock_client_class):
        """Test error handling on failed file listing."""
        from google.api_core.exceptions import GoogleAPIError

        # Setup mock to raise error
        mock_gcs_client = MagicMock()
        mock_gcs_client.list_blobs.side_effect = GoogleAPIError("List error")
        mock_client_class.return_value = mock_gcs_client

        # Execute & Assert
        client = GCSClient(project="test-project")
        with pytest.raises(IOError) as exc_info:
            client.list_files("test-bucket")
        assert "Failed to list" in str(exc_info.value)

    @patch('gdw_data_core.core.clients.gcs_client.storage.Client')
    def test_archive_file_success(self, mock_client_class):
        """Test successful file archiving."""
        # Setup mock
        mock_source_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_source_blob
        mock_bucket.copy_blob.return_value = MagicMock()
        mock_gcs_client = MagicMock()
        mock_gcs_client.bucket.return_value = mock_bucket
        mock_client_class.return_value = mock_gcs_client

        # Execute
        client = GCSClient(project="test-project")
        result = client.archive_file("test-bucket", "source.txt", "archive/source.txt")

        # Assert
        assert result is True
        mock_gcs_client.bucket.assert_called_with("test-bucket")
        mock_bucket.blob.assert_called_once_with("source.txt")
        mock_bucket.copy_blob.assert_called_once()
        mock_source_blob.delete.assert_called_once()

    @patch('gdw_data_core.core.clients.gcs_client.storage.Client')
    def test_archive_file_error(self, mock_client_class):
        """Test error handling on failed file archiving."""
        from google.api_core.exceptions import GoogleAPIError

        # Setup mock to raise error
        mock_gcs_client = MagicMock()
        mock_gcs_client.bucket.side_effect = GoogleAPIError("Archive error")
        mock_client_class.return_value = mock_gcs_client

        # Execute & Assert
        client = GCSClient(project="test-project")
        with pytest.raises(IOError) as exc_info:
            client.archive_file("test-bucket", "source.txt", "archive/source.txt")
        assert "Failed to archive" in str(exc_info.value)


class TestPubSubClient:
    """Unit tests for PubSubClient."""

    @patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1.PublisherClient')
    def test_init_success(self, mock_publisher_class):
        """Test successful Pub/Sub client initialization."""
        mock_instance = MagicMock()
        mock_publisher_class.return_value = mock_instance

        client = PubSubClient(project="test-project")

        assert client.project == "test-project"
        assert client.publisher == mock_instance
        mock_publisher_class.assert_called_once()

    @patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1.PublisherClient')
    def test_init_failure(self, mock_publisher_class):
        """Test error handling on failed initialization."""
        mock_publisher_class.side_effect = Exception("Pub/Sub init error")

        with pytest.raises(Exception):
            PubSubClient(project="test-project")

    @patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1.PublisherClient')
    def test_publish_event_success(self, mock_publisher_class):
        """Test successful event publishing."""
        # Setup mock
        mock_future = MagicMock()
        mock_future.result.return_value = "message-123"
        mock_pub_client = MagicMock()
        mock_pub_client.publish.return_value = mock_future
        mock_pub_client.topic_path.return_value = "projects/test-project/topics/test-topic"
        mock_publisher_class.return_value = mock_pub_client

        # Execute
        client = PubSubClient(project="test-project")
        message_id = client.publish_event("test-topic", {"key": "value"})

        # Assert
        assert message_id == "message-123"
        mock_pub_client.topic_path.assert_called_once_with("test-project", "test-topic")
        mock_pub_client.publish.assert_called_once()
        mock_future.result.assert_called_once()

    @patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1.PublisherClient')
    def test_publish_event_with_complex_message(self, mock_publisher_class):
        """Test publishing event with complex nested message."""
        # Setup mock
        mock_future = MagicMock()
        mock_future.result.return_value = "message-456"
        mock_pub_client = MagicMock()
        mock_pub_client.publish.return_value = mock_future
        mock_pub_client.topic_path.return_value = "projects/test-project/topics/test-topic"
        mock_publisher_class.return_value = mock_pub_client

        # Execute
        client = PubSubClient(project="test-project")
        complex_message = {
            "event": "test",
            "data": {
                "nested": "value",
                "list": [1, 2, 3]
            }
        }
        message_id = client.publish_event("test-topic", complex_message)

        # Assert
        assert message_id == "message-456"
        mock_pub_client.publish.assert_called_once()

    @patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1.PublisherClient')
    def test_publish_event_error_gcs_api(self, mock_publisher_class):
        """Test error handling on Pub/Sub API error."""
        from google.api_core.exceptions import GoogleAPIError

        # Setup mock to raise error
        mock_pub_client = MagicMock()
        mock_pub_client.topic_path.side_effect = GoogleAPIError("Pub/Sub API error")
        mock_publisher_class.return_value = mock_pub_client

        # Execute & Assert
        client = PubSubClient(project="test-project")
        with pytest.raises(IOError) as exc_info:
            client.publish_event("test-topic", {"key": "value"})
        assert "Failed to publish" in str(exc_info.value)

    @patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1.PublisherClient')
    def test_publish_event_error_general(self, mock_publisher_class):
        """Test error handling on general error during publish."""
        # Setup mock to raise error
        mock_pub_client = MagicMock()
        mock_pub_client.topic_path.return_value = "projects/test-project/topics/test-topic"
        mock_pub_client.publish.side_effect = Exception("General error")
        mock_publisher_class.return_value = mock_pub_client

        # Execute & Assert
        client = PubSubClient(project="test-project")
        with pytest.raises(IOError) as exc_info:
            client.publish_event("test-topic", {"key": "value"})
        assert "Failed to publish" in str(exc_info.value)
