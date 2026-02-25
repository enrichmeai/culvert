"""
PubSub Mock Module

Mock objects for Google Pub/Sub testing.
"""

import json
from typing import Dict, List, Any, Callable, Optional
from unittest.mock import Mock


class PubSubClientMock:
    """
    Mock Pub/Sub client for testing.

    Provides a mock interface for Pub/Sub operations without
    requiring actual Pub/Sub connectivity.

    Example:
        >>> mock_client = PubSubClientMock()
        >>> future = mock_client.publish(topic_path, message_data)
        >>> message_id = future.result()
    """

    def __init__(self, project: str = None):
        """Initialize mock Pub/Sub client."""
        self.project = project
        self.published_messages: List[Dict[str, Any]] = []
        self.topics: Dict[str, List[bytes]] = {}
        self.subscriptions: Dict[str, List[Dict[str, Any]]] = {}
        self.acknowledged: List[str] = []
        self.nacked: List[str] = []

    def topic_path(self, project: str, topic: str) -> str:
        """
        Mock topic path generation.

        Args:
            project: GCP project ID
            topic: Topic name

        Returns:
            Full topic path
        """
        return f"projects/{project}/topics/{topic}"

    def subscription_path(self, project: str, subscription: str) -> str:
        """
        Mock subscription path generation.

        Args:
            project: GCP project ID
            subscription: Subscription name

        Returns:
            Full subscription path
        """
        return f"projects/{project}/subscriptions/{subscription}"

    def publish(self, topic_path: str, data: bytes, **attributes) -> Any:
        """
        Mock publish message.

        Args:
            topic_path: Full topic path
            data: Message data as bytes
            **attributes: Message attributes

        Returns:
            Mock future object
        """
        message_id = f"msg_{len(self.published_messages)}"
        self.published_messages.append({
            'topic_path': topic_path,
            'data': data,
            'message_id': message_id,
            'attributes': attributes
        })

        if topic_path not in self.topics:
            self.topics[topic_path] = []
        self.topics[topic_path].append(data)

        # Return mock future
        mock_future = Mock()
        mock_future.result.return_value = message_id
        return mock_future

    def get_published_messages(self, topic_path: str = None) -> List:
        """Get published messages."""
        if topic_path:
            return self.topics.get(topic_path, [])
        return self.published_messages.copy()

    def add_message_to_subscription(
        self,
        subscription_path: str,
        data: dict,
        attributes: dict = None,
        message_id: str = None
    ) -> str:
        """
        Add a message to mock subscription for testing.

        Args:
            subscription_path: Full subscription path
            data: Message data dict
            attributes: Message attributes
            message_id: Optional message ID

        Returns:
            Message ID
        """
        if subscription_path not in self.subscriptions:
            self.subscriptions[subscription_path] = []

        msg_id = message_id or f"msg_{len(self.subscriptions[subscription_path])}"
        ack_id = f"ack_{msg_id}"

        self.subscriptions[subscription_path].append({
            'data': data,
            'attributes': attributes or {},
            'message_id': msg_id,
            'ack_id': ack_id,
            'publish_time': None
        })

        return msg_id

    def pull(self, request: dict, timeout: float = None) -> Any:
        """
        Mock pull operation.

        Args:
            request: Pull request dict with 'subscription' and 'max_messages'
            timeout: Request timeout (ignored in mock)

        Returns:
            Mock response with received_messages
        """
        subscription = request.get('subscription', '')
        max_messages = request.get('max_messages', 10)

        messages = self.subscriptions.get(subscription, [])[:max_messages]

        # Create mock response
        mock_response = Mock()
        mock_response.received_messages = []

        for msg in messages:
            mock_msg = Mock()
            mock_msg.message = Mock()
            mock_msg.message.data = json.dumps(msg['data']).encode()
            mock_msg.message.attributes = msg['attributes']
            mock_msg.message.message_id = msg['message_id']
            mock_msg.message.publish_time = msg.get('publish_time')
            mock_msg.ack_id = msg['ack_id']
            mock_response.received_messages.append(mock_msg)

        return mock_response

    def acknowledge(self, request: dict) -> None:
        """
        Mock acknowledge operation.

        Args:
            request: Acknowledge request with 'subscription' and 'ack_ids'
        """
        ack_ids = request.get('ack_ids', [])
        self.acknowledged.extend(ack_ids)

        # Remove acknowledged messages from subscription
        subscription = request.get('subscription', '')
        if subscription in self.subscriptions:
            self.subscriptions[subscription] = [
                msg for msg in self.subscriptions[subscription]
                if msg['ack_id'] not in ack_ids
            ]

    def modify_ack_deadline(self, request: dict) -> None:
        """
        Mock modify ack deadline (used for nack).

        Args:
            request: Request with 'subscription', 'ack_ids', 'ack_deadline_seconds'
        """
        if request.get('ack_deadline_seconds') == 0:
            # This is a nack
            ack_ids = request.get('ack_ids', [])
            self.nacked.extend(ack_ids)

    def subscribe(
        self,
        subscription_path: str,
        callback: Callable,
        flow_control: Any = None
    ) -> Mock:
        """
        Mock async subscribe.

        Args:
            subscription_path: Full subscription path
            callback: Message callback function
            flow_control: Flow control settings (ignored in mock)

        Returns:
            Mock StreamingPullFuture
        """
        mock_future = Mock()
        mock_future.result.return_value = None
        mock_future.cancel.return_value = True
        mock_future.cancelled.return_value = False
        mock_future.running.return_value = True
        return mock_future

    def stop(self) -> None:
        """Mock stop for publisher."""
        pass

    def close(self) -> None:
        """Mock close for subscriber."""
        pass

    def reset(self) -> None:
        """Reset mock state."""
        self.published_messages = []
        self.topics = {}
        self.subscriptions = {}
        self.acknowledged = []
        self.nacked = []


class PubSubSubscriberMock:
    """
    Mock Pub/Sub subscriber for testing.

    Provides a dedicated mock interface for subscription operations.

    Example:
        >>> mock_subscriber = PubSubSubscriberMock()
        >>> mock_subscriber.add_message("projects/test-project/subscriptions/s", {"key": "value"})
        >>> response = mock_subscriber.pull({"subscription": "...", "max_messages": 10})
    """

    def __init__(self):
        """Initialize mock subscriber."""
        self.subscriptions: Dict[str, List[Dict[str, Any]]] = {}
        self.acknowledged: List[str] = []
        self.nacked: List[str] = []
        self._message_counter = 0

    def subscription_path(self, project: str, subscription: str) -> str:
        """Generate subscription path."""
        return f"projects/{project}/subscriptions/{subscription}"

    def add_message(
        self,
        subscription_path: str,
        data: dict,
        attributes: dict = None,
        message_id: str = None,
        publish_time: str = None
    ) -> str:
        """
        Add a message to mock subscription for testing.

        Args:
            subscription_path: Full subscription path
            data: Message data dict
            attributes: Message attributes
            message_id: Optional message ID
            publish_time: Optional publish time ISO string

        Returns:
            Message ID
        """
        if subscription_path not in self.subscriptions:
            self.subscriptions[subscription_path] = []

        self._message_counter += 1
        msg_id = message_id or f"msg_{self._message_counter}"
        ack_id = f"ack_{msg_id}"

        self.subscriptions[subscription_path].append({
            'data': data,
            'attributes': attributes or {},
            'message_id': msg_id,
            'ack_id': ack_id,
            'publish_time': publish_time
        })

        return msg_id

    def pull(self, request: dict, timeout: float = None) -> Any:
        """Mock pull operation."""
        subscription = request.get('subscription', '')
        max_messages = request.get('max_messages', 10)

        messages = self.subscriptions.get(subscription, [])[:max_messages]

        # Create mock response
        mock_response = Mock()
        mock_response.received_messages = []

        for msg in messages:
            mock_msg = Mock()
            mock_msg.message = Mock()
            mock_msg.message.data = json.dumps(msg['data']).encode()
            mock_msg.message.attributes = msg['attributes']
            mock_msg.message.message_id = msg['message_id']

            if msg.get('publish_time'):
                mock_time = Mock()
                mock_time.isoformat.return_value = msg['publish_time']
                mock_msg.message.publish_time = mock_time
            else:
                mock_msg.message.publish_time = None

            mock_msg.ack_id = msg['ack_id']
            mock_response.received_messages.append(mock_msg)

        return mock_response

    def acknowledge(self, request: dict) -> None:
        """Mock acknowledge operation."""
        ack_ids = request.get('ack_ids', [])
        self.acknowledged.extend(ack_ids)

        # Remove acknowledged messages
        subscription = request.get('subscription', '')
        if subscription in self.subscriptions:
            self.subscriptions[subscription] = [
                msg for msg in self.subscriptions[subscription]
                if msg['ack_id'] not in ack_ids
            ]

    def modify_ack_deadline(self, request: dict) -> None:
        """Mock modify ack deadline (for nack)."""
        if request.get('ack_deadline_seconds') == 0:
            ack_ids = request.get('ack_ids', [])
            self.nacked.extend(ack_ids)

    def subscribe(
        self,
        subscription_path: str,
        callback: Callable,
        flow_control: Any = None
    ) -> Mock:
        """Mock async subscribe."""
        mock_future = Mock()
        mock_future.result.return_value = None
        mock_future.cancel.return_value = True
        mock_future.cancelled.return_value = False
        mock_future.running.return_value = True

        # Store callback for testing
        mock_future._callback = callback
        mock_future._subscription_path = subscription_path

        return mock_future

    def close(self) -> None:
        """Mock close."""
        pass

    def reset(self) -> None:
        """Reset mock state."""
        self.subscriptions = {}
        self.acknowledged = []
        self.nacked = []
        self._message_counter = 0

    def get_pending_messages(self, subscription_path: str) -> List[Dict[str, Any]]:
        """Get pending messages in subscription."""
        return self.subscriptions.get(subscription_path, []).copy()

    def get_acknowledged_ids(self) -> List[str]:
        """Get list of acknowledged ack IDs."""
        return self.acknowledged.copy()

    def get_nacked_ids(self) -> List[str]:
        """Get list of nacked ack IDs."""
        return self.nacked.copy()

