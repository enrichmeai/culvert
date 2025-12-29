"""
Pub/Sub Client - Google Cloud Pub/Sub Operations
Handles event publishing with error handling.
"""

import json
import logging
from google.cloud import pubsub_v1
from google.api_core.exceptions import GoogleAPIError

logger = logging.getLogger(__name__)


class PubSubClient:
    """Google Cloud Pub/Sub client with real implementation."""

    def __init__(self, project: str = None):
        """Initialize Pub/Sub client.

        Args:
            project: GCP project ID (required for topic path construction)
        """
        self.project = project
        try:
            self.publisher = pubsub_v1.PublisherClient()
            logger.info("PubSubClient initialized for project: %s", project)
        except Exception as exc:
            logger.error("Failed to initialize PubSub client: %s", exc)
            raise

    def publish_event(self, topic: str, message: dict) -> str:
        """Publish event to Pub/Sub topic.

        Args:
            topic: Topic name (without project prefix)
            message: Message dict to publish (will be JSON encoded)

        Returns:
            Message ID from Pub/Sub

        Raises:
            IOError: If publish fails
        """
        try:
            topic_path = self.publisher.topic_path(self.project, topic)
            message_json = json.dumps(message)
            message_bytes = message_json.encode('utf-8')

            future = self.publisher.publish(topic_path, message_bytes)
            message_id = future.result()

            logger.info("Published message %s to %s", message_id, topic)
            return message_id
        except GoogleAPIError as exc:
            logger.error("Pub/Sub API error publishing to %s: %s", topic, exc)
            raise IOError(
                f"Failed to publish to {topic}: {exc}") from exc
        except Exception as exc:
            logger.error("Error publishing to %s: %s", topic, exc)
            raise IOError(
                f"Failed to publish to {topic}: {exc}") from exc
