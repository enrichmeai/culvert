"""
Pub/Sub Client - Google Cloud Pub/Sub Operations
Handles event publishing AND subscribing with error handling.
"""

import json
import logging
from typing import List, Dict, Any, Callable, Optional
from google.cloud import pubsub_v1
from google.api_core.exceptions import GoogleAPIError

logger = logging.getLogger(__name__)


class PubSubClient:
    """Google Cloud Pub/Sub client with publisher and subscriber support."""

    def __init__(self, project: str = None):
        """Initialize Pub/Sub client.

        Args:
            project: GCP project ID (required for topic/subscription path construction)
        """
        self.project = project
        self._publisher = None
        self._subscriber = None
        logger.info("PubSubClient initialized for project: %s", project)

    @property
    def publisher(self) -> pubsub_v1.PublisherClient:
        """Lazy-load publisher client."""
        if self._publisher is None:
            self._publisher = pubsub_v1.PublisherClient()
        return self._publisher

    @property
    def subscriber(self) -> pubsub_v1.SubscriberClient:
        """Lazy-load subscriber client."""
        if self._subscriber is None:
            self._subscriber = pubsub_v1.SubscriberClient()
        return self._subscriber

    def publish_event(self, topic: str, message: dict, **attributes) -> str:
        """Publish event to Pub/Sub topic.

        Args:
            topic: Topic name (without project prefix)
            message: Message dict to publish (will be JSON encoded)
            **attributes: Optional message attributes

        Returns:
            Message ID from Pub/Sub

        Raises:
            IOError: If publish fails
        """
        try:
            topic_path = self.publisher.topic_path(self.project, topic)
            message_json = json.dumps(message)
            message_bytes = message_json.encode('utf-8')

            future = self.publisher.publish(
                topic_path,
                message_bytes,
                **{k: str(v) for k, v in attributes.items()}
            )
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

    def publish_batch(self, topic: str, messages: List[dict]) -> List[str]:
        """Publish multiple messages to Pub/Sub topic.

        Args:
            topic: Topic name
            messages: List of message dicts

        Returns:
            List of message IDs
        """
        message_ids = []
        for message in messages:
            msg_id = self.publish_event(topic, message)
            message_ids.append(msg_id)
        return message_ids

    def pull_messages(
        self,
        subscription: str,
        max_messages: int = 10,
        timeout: float = 30.0
    ) -> List[Dict[str, Any]]:
        """Pull messages from subscription (synchronous).

        Args:
            subscription: Subscription name
            max_messages: Maximum messages to pull
            timeout: Request timeout in seconds

        Returns:
            List of message dicts with 'data', 'attributes', 'message_id', 'ack_id'

        Raises:
            IOError: If pull fails
        """
        try:
            subscription_path = self.subscriber.subscription_path(
                self.project, subscription
            )

            response = self.subscriber.pull(
                request={
                    "subscription": subscription_path,
                    "max_messages": max_messages,
                },
                timeout=timeout
            )

            messages = []
            for received_message in response.received_messages:
                msg = received_message.message
                try:
                    data = json.loads(msg.data.decode('utf-8')) if msg.data else {}
                except json.JSONDecodeError:
                    data = {'raw': msg.data.decode('utf-8') if msg.data else ''}

                messages.append({
                    'data': data,
                    'attributes': dict(msg.attributes),
                    'message_id': msg.message_id,
                    'ack_id': received_message.ack_id,
                    'publish_time': msg.publish_time.isoformat() if msg.publish_time else None
                })

            logger.info("Pulled %d messages from %s", len(messages), subscription)
            return messages

        except GoogleAPIError as exc:
            logger.error("Pub/Sub API error pulling from %s: %s", subscription, exc)
            raise IOError(f"Failed to pull from {subscription}: {exc}") from exc

    def acknowledge_messages(self, subscription: str, ack_ids: List[str]) -> None:
        """Acknowledge messages by ack_ids.

        Args:
            subscription: Subscription name
            ack_ids: List of ack IDs to acknowledge

        Raises:
            IOError: If acknowledgement fails
        """
        if not ack_ids:
            logger.warning("No ack_ids provided to acknowledge")
            return

        try:
            subscription_path = self.subscriber.subscription_path(
                self.project, subscription
            )

            self.subscriber.acknowledge(
                request={
                    "subscription": subscription_path,
                    "ack_ids": ack_ids,
                }
            )

            logger.info("Acknowledged %d messages from %s", len(ack_ids), subscription)

        except GoogleAPIError as exc:
            logger.error("Failed to acknowledge messages: %s", exc)
            raise IOError(f"Failed to acknowledge: {exc}") from exc

    def nack_messages(self, subscription: str, ack_ids: List[str]) -> None:
        """Nack messages (modify ack deadline to 0) for immediate redelivery.

        Args:
            subscription: Subscription name
            ack_ids: List of ack IDs to nack

        Raises:
            IOError: If nack fails
        """
        if not ack_ids:
            return

        try:
            subscription_path = self.subscriber.subscription_path(
                self.project, subscription
            )

            self.subscriber.modify_ack_deadline(
                request={
                    "subscription": subscription_path,
                    "ack_ids": ack_ids,
                    "ack_deadline_seconds": 0,
                }
            )

            logger.info("Nacked %d messages from %s", len(ack_ids), subscription)

        except GoogleAPIError as exc:
            logger.error("Failed to nack messages: %s", exc)
            raise IOError(f"Failed to nack: {exc}") from exc

    def subscribe_async(
        self,
        subscription: str,
        callback: Callable[[Dict[str, Any]], bool],
        flow_control_max_messages: int = 100
    ) -> pubsub_v1.subscriber.futures.StreamingPullFuture:
        """Subscribe to messages asynchronously.

        Args:
            subscription: Subscription name
            callback: Callback function(message_dict) -> should_ack
            flow_control_max_messages: Max outstanding messages

        Returns:
            StreamingPullFuture for managing subscription
        """
        subscription_path = self.subscriber.subscription_path(
            self.project, subscription
        )

        def wrapped_callback(message: pubsub_v1.subscriber.message.Message):
            try:
                try:
                    data = json.loads(message.data.decode('utf-8')) if message.data else {}
                except json.JSONDecodeError:
                    data = {'raw': message.data.decode('utf-8') if message.data else ''}

                msg_dict = {
                    'data': data,
                    'attributes': dict(message.attributes),
                    'message_id': message.message_id,
                }

                should_ack = callback(msg_dict)

                if should_ack:
                    message.ack()
                else:
                    message.nack()

            except Exception as exc:
                logger.error("Error in message callback: %s", exc)
                message.nack()

        flow_control = pubsub_v1.types.FlowControl(
            max_messages=flow_control_max_messages
        )

        future = self.subscriber.subscribe(
            subscription_path,
            wrapped_callback,
            flow_control=flow_control
        )

        logger.info("Started async subscription to %s", subscription)
        return future

    def close(self) -> None:
        """Close the client connections."""
        if self._publisher:
            self._publisher.stop()
            self._publisher = None
        if self._subscriber:
            self._subscriber.close()
            self._subscriber = None
        logger.info("PubSubClient closed")

