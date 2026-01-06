"""
PubSub Publishers Module

Google Pub/Sub publishing DoFns for Apache Beam pipelines.
"""

import logging
import json
from typing import Dict, Any, Iterator

import apache_beam as beam

logger = logging.getLogger(__name__)


class PublishToPubSubDoFn(beam.DoFn):
    """
    Publishes messages to Google Pub/Sub topics.

    Serializes records to JSON and publishes them to a Pub/Sub topic.
    Useful for event streaming and downstream system integration.

    Attributes:
        project: GCP Project ID
        topic: Pub/Sub topic name

    Outputs:
        Main: Dict - Published records (for chaining)

    Metrics:
        pubsub/published: Counter of published messages
        pubsub/errors: Counter of publish failures

    Example:
        >>> records | 'PublishPubSub' >> beam.ParDo(PublishToPubSubDoFn(
        ...     project='my-project',
        ...     topic='my-topic'
        ... ))
    """

    def __init__(self, project: str, topic: str):
        """
        Initialize Pub/Sub publisher.

        Args:
            project: GCP Project ID
            topic: Pub/Sub topic name (without 'projects/...' prefix)

        Example:
            >>> publisher = PublishToPubSubDoFn(
            ...     project='my-project',
            ...     topic='migration_events'
            ... )
        """
        super().__init__()
        self.project = project
        self.topic = topic
        self.publisher = None
        self.published = beam.metrics.Metrics.counter("pubsub", "published")
        self.errors = beam.metrics.Metrics.counter("pubsub", "errors")

    def setup(self):
        """Initialize Pub/Sub publisher client."""
        from google.cloud import pubsub_v1
        self.publisher = pubsub_v1.PublisherClient()

    def process(self, element: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """
        Publish element to Pub/Sub.

        Args:
            element: Message to publish (dict or JSON-serializable)

        Yields:
            Dict: Element (for chaining)

        Example:
            >>> publisher = PublishToPubSubDoFn('my-project', 'my-topic')
            >>> publisher.setup()
            >>> result = list(publisher.process({'id': '1', 'action': 'created'}))
        """
        try:
            topic_path = self.publisher.topic_path(self.project, self.topic)

            # Serialize to JSON if needed
            if isinstance(element, dict):
                message_data = json.dumps(element).encode('utf-8')
            else:
                message_data = str(element).encode('utf-8')

            # Publish message (synchronous for simplicity)
            future = self.publisher.publish(topic_path, message_data)
            message_id = future.result()  # Wait for publication

            self.published.inc()
            logger.debug(f"Published message {message_id} to {self.topic}")
            yield element

        except Exception as e:
            logger.error(f"Error publishing to Pub/Sub: {e}")
            self.errors.inc()
            raise

