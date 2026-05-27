"""PubSubSource / PubSubSink — Source/Sink Protocols over google-cloud-pubsub.

Java siblings:
- ``com.enrichmeai.culvert.gcp.pubsub.PubSubSource``
- ``com.enrichmeai.culvert.gcp.pubsub.PubSubSink``
"""

from __future__ import annotations

import logging
from typing import Any, Iterator, Mapping

logger = logging.getLogger(__name__)


class PubSubSource:
    """Source[Mapping[str, Any]] backed by a Pub/Sub subscriber.

    ``read(context)`` pulls a batch from the subscription and yields each
    message as a dict ``{"data": bytes, "attributes": dict, "message_id": str,
    "publish_time": ..., "ack_id": str}``. Eager-ack on yield (at-most-once).
    For at-least-once with caller-controlled ack, use the underlying
    ``SubscriberClient`` directly.
    """

    def __init__(self, subscriber: Any, subscription_path: str, max_messages: int = 100) -> None:
        if subscriber is None:
            raise TypeError("subscriber must not be None")
        if subscription_path is None:
            raise TypeError("subscription_path must not be None")
        if max_messages <= 0:
            raise ValueError("max_messages must be positive")
        self.subscriber = subscriber
        self.subscription_path = subscription_path
        self.max_messages = max_messages

    def read(self, context: Any = None) -> Iterator[Mapping[str, Any]]:
        response = self.subscriber.pull(
            request={
                "subscription": self.subscription_path,
                "max_messages": self.max_messages,
            }
        )
        ack_ids = []
        for received in response.received_messages:
            msg = received.message
            ack_ids.append(received.ack_id)
            yield {
                "data": msg.data,
                "attributes": dict(msg.attributes),
                "message_id": msg.message_id,
                "publish_time": msg.publish_time,
                "ack_id": received.ack_id,
            }
        # Eager-ack the whole batch — at-most-once semantics.
        if ack_ids:
            self.subscriber.acknowledge(
                request={
                    "subscription": self.subscription_path,
                    "ack_ids": ack_ids,
                }
            )


class PubSubSink:
    """Sink[Mapping[str, Any]] backed by a Pub/Sub publisher.

    Each record dict can carry ``"data"`` (bytes, required) and
    ``"attributes"`` (dict[str, str], optional). The sink publishes each
    record and waits for the publisher's futures to resolve so failures
    surface synchronously.
    """

    def __init__(self, publisher: Any, topic_path: str) -> None:
        if publisher is None:
            raise TypeError("publisher must not be None")
        if topic_path is None:
            raise TypeError("topic_path must not be None")
        self.publisher = publisher
        self.topic_path = topic_path

    def write(self, records: Iterator[Mapping[str, Any]], context: Any = None) -> None:
        futures = []
        for record in records:
            data = record.get("data")
            if data is None:
                raise ValueError("Each record must carry 'data' bytes")
            attributes = record.get("attributes", {})
            future = self.publisher.publish(self.topic_path, data, **attributes)
            futures.append(future)
        # Block on each future so any publish error surfaces here.
        for future in futures:
            future.result()
