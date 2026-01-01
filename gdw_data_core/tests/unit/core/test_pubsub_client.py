"""
Unit tests for PubSubClient.

Tests cover:
- Publisher operations (publish_event, publish_batch)
- Subscriber operations (pull_messages, acknowledge_messages, subscribe_async)
- Error handling
- Message serialization
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
import json

from google.api_core.exceptions import GoogleAPIError


class TestPubSubClientInit:
    """Test PubSubClient initialization."""

    def test_init_with_project(self):
        """Test initialization with project ID."""
        with patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1'):
            from gdw_data_core.core.clients.pubsub_client import PubSubClient
            client = PubSubClient(project="test-project")
            assert client.project == "test-project"
            assert client._publisher is None
            assert client._subscriber is None

    def test_init_without_project(self):
        """Test initialization without project ID."""
        with patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1'):
            from gdw_data_core.core.clients.pubsub_client import PubSubClient
            client = PubSubClient()
            assert client.project is None

    def test_lazy_publisher_initialization(self):
        """Test that publisher is lazily initialized."""
        with patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1.PublisherClient') as mock_pub:
            from gdw_data_core.core.clients.pubsub_client import PubSubClient
            client = PubSubClient(project="test-project")
            # Publisher not created yet
            assert client._publisher is None
            # Access publisher property
            _ = client.publisher
            # Now it's created
            mock_pub.assert_called_once()

    def test_lazy_subscriber_initialization(self):
        """Test that subscriber is lazily initialized."""
        with patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1.SubscriberClient') as mock_sub:
            from gdw_data_core.core.clients.pubsub_client import PubSubClient
            client = PubSubClient(project="test-project")
            assert client._subscriber is None
            _ = client.subscriber
            mock_sub.assert_called_once()

    def test_publisher_reuses_instance(self):
        """Test that publisher property returns same instance."""
        with patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1.PublisherClient') as mock_pub:
            from gdw_data_core.core.clients.pubsub_client import PubSubClient
            client = PubSubClient(project="test-project")
            pub1 = client.publisher
            pub2 = client.publisher
            assert pub1 is pub2
            mock_pub.assert_called_once()

    def test_subscriber_reuses_instance(self):
        """Test that subscriber property returns same instance."""
        with patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1.SubscriberClient') as mock_sub:
            from gdw_data_core.core.clients.pubsub_client import PubSubClient
            client = PubSubClient(project="test-project")
            sub1 = client.subscriber
            sub2 = client.subscriber
            assert sub1 is sub2
            mock_sub.assert_called_once()


class TestPublishEvent:
    """Test publish_event method."""

    @pytest.fixture
    def mock_client(self):
        with patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1.PublisherClient') as mock_pub:
            mock_publisher = Mock()
            mock_pub.return_value = mock_publisher

            mock_future = Mock()
            mock_future.result.return_value = "msg-123"
            mock_publisher.publish.return_value = mock_future
            mock_publisher.topic_path.return_value = "projects/test/topics/test-topic"

            from gdw_data_core.core.clients.pubsub_client import PubSubClient
            client = PubSubClient(project="test-project")
            yield client, mock_publisher

    def test_publish_event_success(self, mock_client):
        """Test successful event publishing."""
        client, mock_publisher = mock_client

        message = {"event": "test", "data": {"key": "value"}}
        msg_id = client.publish_event("test-topic", message)

        assert msg_id == "msg-123"
        mock_publisher.publish.assert_called_once()

    def test_publish_event_with_attributes(self, mock_client):
        """Test publishing with message attributes."""
        client, mock_publisher = mock_client

        message = {"event": "test"}
        client.publish_event("test-topic", message, source="test", priority="high")

        call_args = mock_publisher.publish.call_args
        # Attributes should be passed as kwargs
        assert call_args.kwargs.get('source') == 'test'
        assert call_args.kwargs.get('priority') == 'high'

    def test_publish_event_api_error(self, mock_client):
        """Test handling of Google API errors."""
        client, mock_publisher = mock_client

        mock_publisher.publish.side_effect = GoogleAPIError("API Error")

        with pytest.raises(IOError) as exc_info:
            client.publish_event("test-topic", {"test": "data"})

        assert "Failed to publish" in str(exc_info.value)

    def test_publish_event_generic_error(self, mock_client):
        """Test handling of generic errors."""
        client, mock_publisher = mock_client

        mock_publisher.publish.side_effect = ValueError("Unexpected error")

        with pytest.raises(IOError) as exc_info:
            client.publish_event("test-topic", {"test": "data"})

        assert "Failed to publish" in str(exc_info.value)

    def test_publish_event_json_serialization(self, mock_client):
        """Test that messages are JSON serialized."""
        client, mock_publisher = mock_client

        message = {"nested": {"key": [1, 2, 3]}}
        client.publish_event("test-topic", message)

        call_args = mock_publisher.publish.call_args
        published_data = call_args.args[1]  # Second arg is the data
        assert json.loads(published_data.decode()) == message

    def test_publish_event_attributes_converted_to_string(self, mock_client):
        """Test that numeric attributes are converted to strings."""
        client, mock_publisher = mock_client

        message = {"event": "test"}
        client.publish_event("test-topic", message, count=42, enabled=True)

        call_args = mock_publisher.publish.call_args
        assert call_args.kwargs.get('count') == '42'
        assert call_args.kwargs.get('enabled') == 'True'

    def test_publish_event_topic_path_construction(self, mock_client):
        """Test that topic path is correctly constructed."""
        client, mock_publisher = mock_client

        client.publish_event("my-topic", {"data": "test"})

        mock_publisher.topic_path.assert_called_with("test-project", "my-topic")


class TestPublishBatch:
    """Test publish_batch method."""

    @pytest.fixture
    def mock_client(self):
        with patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1.PublisherClient') as mock_pub:
            mock_publisher = Mock()
            mock_pub.return_value = mock_publisher

            call_count = [0]

            def mock_publish(*args, **kwargs):
                call_count[0] += 1
                future = Mock()
                future.result.return_value = f"msg-{call_count[0]}"
                return future

            mock_publisher.publish = mock_publish
            mock_publisher.topic_path.return_value = "projects/test/topics/test-topic"

            from gdw_data_core.core.clients.pubsub_client import PubSubClient
            client = PubSubClient(project="test-project")
            yield client

    def test_publish_batch_success(self, mock_client):
        """Test batch publishing."""
        messages = [{"id": 1}, {"id": 2}, {"id": 3}]

        msg_ids = mock_client.publish_batch("test-topic", messages)

        assert len(msg_ids) == 3
        assert msg_ids == ["msg-1", "msg-2", "msg-3"]

    def test_publish_batch_empty_list(self, mock_client):
        """Test batch publishing with empty list."""
        msg_ids = mock_client.publish_batch("test-topic", [])
        assert msg_ids == []

    def test_publish_batch_single_message(self, mock_client):
        """Test batch publishing with single message."""
        messages = [{"single": "message"}]
        msg_ids = mock_client.publish_batch("test-topic", messages)
        assert len(msg_ids) == 1


class TestPullMessages:
    """Test pull_messages method."""

    @pytest.fixture
    def mock_client(self):
        with patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1.SubscriberClient') as mock_sub:
            mock_subscriber = Mock()
            mock_sub.return_value = mock_subscriber
            mock_subscriber.subscription_path.return_value = "projects/test/subscriptions/test-sub"

            from gdw_data_core.core.clients.pubsub_client import PubSubClient
            client = PubSubClient(project="test-project")
            yield client, mock_subscriber

    def test_pull_messages_success(self, mock_client):
        """Test successful message pull."""
        client, mock_subscriber = mock_client

        mock_message = Mock()
        mock_message.message.data = json.dumps({"test": "data"}).encode()
        mock_message.message.attributes = {"attr1": "value1"}
        mock_message.message.message_id = "msg-123"
        mock_message.message.publish_time = None
        mock_message.ack_id = "ack-123"

        mock_response = Mock()
        mock_response.received_messages = [mock_message]
        mock_subscriber.pull.return_value = mock_response

        messages = client.pull_messages("test-sub", max_messages=10)

        assert len(messages) == 1
        assert messages[0]['data'] == {"test": "data"}
        assert messages[0]['message_id'] == "msg-123"
        assert messages[0]['ack_id'] == "ack-123"
        assert messages[0]['attributes'] == {"attr1": "value1"}

    def test_pull_messages_multiple(self, mock_client):
        """Test pulling multiple messages."""
        client, mock_subscriber = mock_client

        mock_messages = []
        for i in range(3):
            mock_msg = Mock()
            mock_msg.message.data = json.dumps({"id": i}).encode()
            mock_msg.message.attributes = {}
            mock_msg.message.message_id = f"msg-{i}"
            mock_msg.message.publish_time = None
            mock_msg.ack_id = f"ack-{i}"
            mock_messages.append(mock_msg)

        mock_response = Mock()
        mock_response.received_messages = mock_messages
        mock_subscriber.pull.return_value = mock_response

        messages = client.pull_messages("test-sub", max_messages=10)

        assert len(messages) == 3
        for i, msg in enumerate(messages):
            assert msg['data'] == {"id": i}
            assert msg['message_id'] == f"msg-{i}"

    def test_pull_messages_empty(self, mock_client):
        """Test pull with no messages."""
        client, mock_subscriber = mock_client

        mock_response = Mock()
        mock_response.received_messages = []
        mock_subscriber.pull.return_value = mock_response

        messages = client.pull_messages("test-sub")

        assert messages == []

    def test_pull_messages_api_error(self, mock_client):
        """Test API error handling."""
        client, mock_subscriber = mock_client

        mock_subscriber.pull.side_effect = GoogleAPIError("Pull failed")

        with pytest.raises(IOError) as exc_info:
            client.pull_messages("test-sub")

        assert "Failed to pull" in str(exc_info.value)

    def test_pull_messages_with_timeout(self, mock_client):
        """Test pull with custom timeout."""
        client, mock_subscriber = mock_client

        mock_response = Mock()
        mock_response.received_messages = []
        mock_subscriber.pull.return_value = mock_response

        client.pull_messages("test-sub", timeout=60.0)

        call_args = mock_subscriber.pull.call_args
        assert call_args.kwargs.get('timeout') == 60.0

    def test_pull_messages_with_publish_time(self, mock_client):
        """Test pull includes publish time when available."""
        client, mock_subscriber = mock_client

        from datetime import datetime
        mock_time = Mock()
        mock_time.isoformat.return_value = "2026-01-01T10:00:00"

        mock_message = Mock()
        mock_message.message.data = json.dumps({"test": "data"}).encode()
        mock_message.message.attributes = {}
        mock_message.message.message_id = "msg-123"
        mock_message.message.publish_time = mock_time
        mock_message.ack_id = "ack-123"

        mock_response = Mock()
        mock_response.received_messages = [mock_message]
        mock_subscriber.pull.return_value = mock_response

        messages = client.pull_messages("test-sub")

        assert messages[0]['publish_time'] == "2026-01-01T10:00:00"

    def test_pull_messages_empty_data(self, mock_client):
        """Test pull with empty message data."""
        client, mock_subscriber = mock_client

        mock_message = Mock()
        mock_message.message.data = None
        mock_message.message.attributes = {}
        mock_message.message.message_id = "msg-123"
        mock_message.message.publish_time = None
        mock_message.ack_id = "ack-123"

        mock_response = Mock()
        mock_response.received_messages = [mock_message]
        mock_subscriber.pull.return_value = mock_response

        messages = client.pull_messages("test-sub")

        assert messages[0]['data'] == {}

    def test_pull_messages_invalid_json(self, mock_client):
        """Test pull with non-JSON message data."""
        client, mock_subscriber = mock_client

        mock_message = Mock()
        mock_message.message.data = b"not valid json"
        mock_message.message.attributes = {}
        mock_message.message.message_id = "msg-123"
        mock_message.message.publish_time = None
        mock_message.ack_id = "ack-123"

        mock_response = Mock()
        mock_response.received_messages = [mock_message]
        mock_subscriber.pull.return_value = mock_response

        messages = client.pull_messages("test-sub")

        # Should return raw data when JSON decode fails
        assert messages[0]['data'] == {'raw': 'not valid json'}


class TestAcknowledgeMessages:
    """Test acknowledge_messages method."""

    @pytest.fixture
    def mock_client(self):
        with patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1.SubscriberClient') as mock_sub:
            mock_subscriber = Mock()
            mock_sub.return_value = mock_subscriber
            mock_subscriber.subscription_path.return_value = "projects/test/subscriptions/test-sub"

            from gdw_data_core.core.clients.pubsub_client import PubSubClient
            client = PubSubClient(project="test-project")
            yield client, mock_subscriber

    def test_acknowledge_success(self, mock_client):
        """Test successful acknowledgement."""
        client, mock_subscriber = mock_client

        client.acknowledge_messages("test-sub", ["ack-1", "ack-2"])

        mock_subscriber.acknowledge.assert_called_once()
        call_args = mock_subscriber.acknowledge.call_args
        assert call_args.kwargs['request']['ack_ids'] == ["ack-1", "ack-2"]

    def test_acknowledge_single_message(self, mock_client):
        """Test acknowledging single message."""
        client, mock_subscriber = mock_client

        client.acknowledge_messages("test-sub", ["ack-1"])

        mock_subscriber.acknowledge.assert_called_once()

    def test_acknowledge_api_error(self, mock_client):
        """Test acknowledgement error handling."""
        client, mock_subscriber = mock_client

        mock_subscriber.acknowledge.side_effect = GoogleAPIError("Ack failed")

        with pytest.raises(IOError) as exc_info:
            client.acknowledge_messages("test-sub", ["ack-1"])

        assert "Failed to acknowledge" in str(exc_info.value)

    def test_acknowledge_empty_list(self, mock_client):
        """Test acknowledging empty list does nothing."""
        client, mock_subscriber = mock_client

        client.acknowledge_messages("test-sub", [])

        mock_subscriber.acknowledge.assert_not_called()


class TestNackMessages:
    """Test nack_messages method."""

    @pytest.fixture
    def mock_client(self):
        with patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1.SubscriberClient') as mock_sub:
            mock_subscriber = Mock()
            mock_sub.return_value = mock_subscriber
            mock_subscriber.subscription_path.return_value = "projects/test/subscriptions/test-sub"

            from gdw_data_core.core.clients.pubsub_client import PubSubClient
            client = PubSubClient(project="test-project")
            yield client, mock_subscriber

    def test_nack_success(self, mock_client):
        """Test successful nack."""
        client, mock_subscriber = mock_client

        client.nack_messages("test-sub", ["ack-1", "ack-2"])

        mock_subscriber.modify_ack_deadline.assert_called_once()
        call_args = mock_subscriber.modify_ack_deadline.call_args
        assert call_args.kwargs['request']['ack_deadline_seconds'] == 0

    def test_nack_empty_list(self, mock_client):
        """Test nacking empty list does nothing."""
        client, mock_subscriber = mock_client

        client.nack_messages("test-sub", [])

        mock_subscriber.modify_ack_deadline.assert_not_called()

    def test_nack_api_error(self, mock_client):
        """Test nack error handling."""
        client, mock_subscriber = mock_client

        mock_subscriber.modify_ack_deadline.side_effect = GoogleAPIError("Nack failed")

        with pytest.raises(IOError) as exc_info:
            client.nack_messages("test-sub", ["ack-1"])

        assert "Failed to nack" in str(exc_info.value)


class TestSubscribeAsync:
    """Test subscribe_async method."""

    @pytest.fixture
    def mock_client(self):
        with patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1') as mock_pubsub:
            mock_subscriber = Mock()
            mock_pubsub.SubscriberClient.return_value = mock_subscriber
            mock_subscriber.subscription_path.return_value = "projects/test/subscriptions/test-sub"

            mock_future = Mock()
            mock_subscriber.subscribe.return_value = mock_future

            mock_pubsub.types.FlowControl.return_value = Mock()

            from gdw_data_core.core.clients.pubsub_client import PubSubClient
            client = PubSubClient(project="test-project")
            yield client, mock_subscriber, mock_future, mock_pubsub

    def test_subscribe_async_returns_future(self, mock_client):
        """Test async subscription returns future."""
        client, mock_subscriber, mock_future, _ = mock_client

        def callback(msg):
            return True

        result = client.subscribe_async("test-sub", callback)

        assert result == mock_future
        mock_subscriber.subscribe.assert_called_once()

    def test_subscribe_async_with_flow_control(self, mock_client):
        """Test async subscription with custom flow control."""
        client, mock_subscriber, _, mock_pubsub = mock_client

        def callback(msg):
            return True

        client.subscribe_async("test-sub", callback, flow_control_max_messages=50)

        mock_pubsub.types.FlowControl.assert_called_with(max_messages=50)

    def test_subscribe_async_callback_acks_on_true(self, mock_client):
        """Test that callback returning True acks message."""
        client, mock_subscriber, _, _ = mock_client

        captured_callback = None

        def capture_subscribe(path, callback, flow_control):
            nonlocal captured_callback
            captured_callback = callback
            return Mock()

        mock_subscriber.subscribe = capture_subscribe

        def user_callback(msg):
            return True

        client.subscribe_async("test-sub", user_callback)

        # Simulate message
        mock_message = Mock()
        mock_message.data = json.dumps({"test": "data"}).encode()
        mock_message.attributes = {}
        mock_message.message_id = "msg-123"

        captured_callback(mock_message)

        mock_message.ack.assert_called_once()

    def test_subscribe_async_callback_nacks_on_false(self, mock_client):
        """Test that callback returning False nacks message."""
        client, mock_subscriber, _, _ = mock_client

        captured_callback = None

        def capture_subscribe(path, callback, flow_control):
            nonlocal captured_callback
            captured_callback = callback
            return Mock()

        mock_subscriber.subscribe = capture_subscribe

        def user_callback(msg):
            return False

        client.subscribe_async("test-sub", user_callback)

        mock_message = Mock()
        mock_message.data = json.dumps({"test": "data"}).encode()
        mock_message.attributes = {}
        mock_message.message_id = "msg-123"

        captured_callback(mock_message)

        mock_message.nack.assert_called_once()

    def test_subscribe_async_callback_nacks_on_exception(self, mock_client):
        """Test that exceptions in callback cause nack."""
        client, mock_subscriber, _, _ = mock_client

        captured_callback = None

        def capture_subscribe(path, callback, flow_control):
            nonlocal captured_callback
            captured_callback = callback
            return Mock()

        mock_subscriber.subscribe = capture_subscribe

        def user_callback(msg):
            raise ValueError("Callback error")

        client.subscribe_async("test-sub", user_callback)

        mock_message = Mock()
        mock_message.data = json.dumps({"test": "data"}).encode()
        mock_message.attributes = {}
        mock_message.message_id = "msg-123"

        captured_callback(mock_message)

        mock_message.nack.assert_called_once()


class TestClose:
    """Test close method."""

    def test_close_stops_publisher(self):
        """Test that close stops publisher."""
        with patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1.PublisherClient') as mock_pub:
            mock_publisher = Mock()
            mock_pub.return_value = mock_publisher

            from gdw_data_core.core.clients.pubsub_client import PubSubClient
            client = PubSubClient(project="test-project")

            # Access publisher to initialize it
            _ = client.publisher
            client.close()

            mock_publisher.stop.assert_called_once()
            assert client._publisher is None

    def test_close_closes_subscriber(self):
        """Test that close closes subscriber."""
        with patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1.SubscriberClient') as mock_sub:
            mock_subscriber = Mock()
            mock_sub.return_value = mock_subscriber

            from gdw_data_core.core.clients.pubsub_client import PubSubClient
            client = PubSubClient(project="test-project")

            # Access subscriber to initialize it
            _ = client.subscriber
            client.close()

            mock_subscriber.close.assert_called_once()
            assert client._subscriber is None

    def test_close_without_initialization(self):
        """Test that close works when clients not initialized."""
        with patch('gdw_data_core.core.clients.pubsub_client.pubsub_v1'):
            from gdw_data_core.core.clients.pubsub_client import PubSubClient
            client = PubSubClient(project="test-project")

            # Should not raise
            client.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

