"""Deployment-local audit publisher.

Implements Culvert's `AuditEventPublisher` Protocol
(`data_pipeline_core.contracts.audit`) over Pub/Sub: each `AuditRecord`
is serialised to JSON and published to the pipeline-events topic.
`flush()` blocks on the outstanding publish futures, satisfying the
Protocol's at-least-once guarantee at stage boundaries.
"""

from __future__ import annotations

import dataclasses
import json
from typing import List

from google.cloud import pubsub_v1

from data_pipeline_core.audit.records import AuditRecord


class PubSubAuditPublisher:
    """Publishes AuditRecords as JSON messages on a Pub/Sub topic."""

    def __init__(self, project_id: str, topic_name: str,
                 publisher: pubsub_v1.PublisherClient | None = None) -> None:
        self._publisher = publisher or pubsub_v1.PublisherClient()
        self._topic = self._publisher.topic_path(project_id, topic_name)
        self._pending: List = []

    def publish(self, record: AuditRecord) -> None:
        payload = dataclasses.asdict(record)
        payload["processed_timestamp"] = record.processed_timestamp.isoformat()
        future = self._publisher.publish(
            self._topic,
            json.dumps(payload).encode("utf-8"),
            run_id=record.run_id,
            pipeline_name=record.pipeline_name,
        )
        self._pending.append(future)

    def flush(self) -> None:
        pending, self._pending = self._pending, []
        for future in pending:
            future.result(timeout=30)
