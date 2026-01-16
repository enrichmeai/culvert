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
    Publishes messages to Google Pub/Sub topics using asynchronous batching.

    Serializes records to JSON and publishes them to a Pub/Sub topic.
    Implements a callback mechanism to handle successes/failures without
    blocking the main pipeline thread.

    Attributes:
        project: GCP Project ID
        topic: Pub/Sub topic name

    Outputs:
        Main: Dict - Published records (for chaining)

    Metrics:
        pubsub/published: Counter of published messages
        pubsub/errors: Counter of publish failures
    """

    def __init__(self, project: str, topic: str):
        super().__init__()
        self.project = project
        self.topic = topic
        self.publisher = None
        self.published = beam.metrics.Metrics.counter("pubsub", "published")
        self.errors = beam.metrics.Metrics.counter("pubsub", "errors")

    def setup(self):
        """Initialize Pub/Sub publisher client."""
        from google.cloud import pubsub_v1
        # Use default batching settings or configure as needed
        self.publisher = pubsub_v1.PublisherClient()
        self.topic_path = self.publisher.topic_path(self.project, self.topic)

    def _callback(self, future):
        """Callback to handle publish results."""
        try:
            message_id = future.result()
            self.published.inc()
            logger.debug(f"Published message {message_id} to {self.topic}")
        except Exception as e:
            logger.error(f"Error publishing to Pub/Sub: {e}")
            self.errors.inc()

    def process(self, element: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """
        Publish element to Pub/Sub asynchronously.
        """
        try:
            # Serialize to JSON if needed
            if isinstance(element, dict):
                message_data = json.dumps(element).encode('utf-8')
            else:
                message_data = str(element).encode('utf-8')

            # Publish message asynchronously
            future = self.publisher.publish(self.topic_path, message_data)
            future.add_done_callback(self._callback)

            yield element

        except Exception as e:
            logger.error(f"Error initiating publish to Pub/Sub: {e}")
            self.errors.inc()
            raise

