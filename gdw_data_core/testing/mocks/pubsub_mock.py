"""
PubSub Mock Module

Mock objects for Google Pub/Sub testing.
"""

from typing import Dict, List, Any
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

    def __init__(self):
        """Initialize mock Pub/Sub client."""
        self.published_messages: List[Dict[str, Any]] = []
        self.topics: Dict[str, List[bytes]] = {}

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

    def publish(self, topic_path: str, data: bytes) -> Any:
        """
        Mock publish message.

        Args:
            topic_path: Full topic path
            data: Message data as bytes

        Returns:
            Mock future object
        """
        message_id = f"msg_{len(self.published_messages)}"
        self.published_messages.append({
            'topic_path': topic_path,
            'data': data,
            'message_id': message_id
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

    def reset(self) -> None:
        """Reset mock state."""
        self.published_messages = []
        self.topics = {}

