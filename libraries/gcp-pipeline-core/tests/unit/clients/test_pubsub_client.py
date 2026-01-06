"""
Unit tests for PubSubClient.

Tests mirror source: gcp_pipeline_builder/core/clients/pubsub_client.py

Run tests in isolation to avoid module caching issues:
    pytest gcp_pipeline_builder/tests/unit/core/clients/test_pubsub_client.py -v
"""

import pytest
import sys
from unittest.mock import patch, MagicMock



def _reload_pubsub_client():
    """Force reload of pubsub_client module to pick up mocks."""
    for mod in list(sys.modules.keys()):
        if 'pubsub_client' in mod:
            del sys.modules[mod]
    from gcp_pipeline_core.clients.pubsub_client import PubSubClient
    return PubSubClient


class TestPubSubClientInit:
    """Tests for PubSubClient initialization."""

    def test_init_success(self):
        """Test successful Pub/Sub client initialization."""
        with patch('gcp_pipeline_core.clients.pubsub_client.pubsub_v1.PublisherClient') as mock_publisher_class:
            mock_instance = MagicMock()
            mock_publisher_class.return_value = mock_instance

            PubSubClient = _reload_pubsub_client()
            client = PubSubClient(project="test-project")

            assert client.project == "test-project"
            assert client.publisher == mock_instance
            mock_publisher_class.assert_called_once()

    def test_init_failure(self):
        """Test error handling on failed publisher initialization (lazy loaded)."""
        with patch('gcp_pipeline_core.clients.pubsub_client.pubsub_v1.PublisherClient') as mock_publisher_class:
            mock_publisher_class.side_effect = Exception("Pub/Sub init error")

            PubSubClient = _reload_pubsub_client()
            client = PubSubClient(project="test-project")

            with pytest.raises(Exception, match="Pub/Sub init error"):
                _ = client.publisher


class TestPubSubClientPublishEvent:
    """Tests for PubSubClient.publish_event method."""

    def test_publish_event_success(self):
        """Test successful event publishing."""
        with patch('gcp_pipeline_core.clients.pubsub_client.pubsub_v1.PublisherClient') as mock_publisher_class:
            mock_future = MagicMock()
            mock_future.result.return_value = "message-123"
            mock_pub_client = MagicMock()
            mock_pub_client.publish.return_value = mock_future
            mock_pub_client.topic_path.return_value = "projects/test-project/topics/test-topic"
            mock_publisher_class.return_value = mock_pub_client

            PubSubClient = _reload_pubsub_client()
            client = PubSubClient(project="test-project")
            message_id = client.publish_event("test-topic", {"key": "value"})

            assert message_id == "message-123"
            mock_pub_client.topic_path.assert_called_once_with("test-project", "test-topic")
            mock_pub_client.publish.assert_called_once()
            mock_future.result.assert_called_once()

    def test_publish_event_with_complex_message(self):
        """Test publishing event with complex nested message."""
        with patch('gcp_pipeline_core.clients.pubsub_client.pubsub_v1.PublisherClient') as mock_publisher_class:
            mock_future = MagicMock()
            mock_future.result.return_value = "message-456"
            mock_pub_client = MagicMock()
            mock_pub_client.publish.return_value = mock_future
            mock_pub_client.topic_path.return_value = "projects/test-project/topics/test-topic"
            mock_publisher_class.return_value = mock_pub_client

            PubSubClient = _reload_pubsub_client()
            client = PubSubClient(project="test-project")
            complex_message = {
                "event": "test",
                "data": {
                    "nested": "value",
                    "list": [1, 2, 3]
                }
            }
            message_id = client.publish_event("test-topic", complex_message)

            assert message_id == "message-456"
            mock_pub_client.publish.assert_called_once()

    def test_publish_event_error_api(self):
        """Test error handling on Pub/Sub API error."""
        with patch('gcp_pipeline_core.clients.pubsub_client.pubsub_v1.PublisherClient') as mock_publisher_class:
            from google.api_core.exceptions import GoogleAPIError

            mock_pub_client = MagicMock()
            mock_pub_client.topic_path.side_effect = GoogleAPIError("Pub/Sub API error")
            mock_publisher_class.return_value = mock_pub_client

            PubSubClient = _reload_pubsub_client()
            client = PubSubClient(project="test-project")
            with pytest.raises(IOError) as exc_info:
                client.publish_event("test-topic", {"key": "value"})
            assert "Failed to publish" in str(exc_info.value)

    def test_publish_event_error_general(self):
        """Test error handling on general error during publish."""
        with patch('gcp_pipeline_core.clients.pubsub_client.pubsub_v1.PublisherClient') as mock_publisher_class:
            mock_pub_client = MagicMock()
            mock_pub_client.topic_path.return_value = "projects/test-project/topics/test-topic"
            mock_pub_client.publish.side_effect = Exception("General error")
            mock_publisher_class.return_value = mock_pub_client

            PubSubClient = _reload_pubsub_client()
            client = PubSubClient(project="test-project")
            with pytest.raises(IOError) as exc_info:
                client.publish_event("test-topic", {"key": "value"})
            assert "Failed to publish" in str(exc_info.value)
