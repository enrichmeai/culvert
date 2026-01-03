"""
GDW Data Core - Audit Publisher Module

Handles publishing of audit records to external systems (Pub/Sub).
"""

import json
import dataclasses
from datetime import datetime
from typing import Any, Dict
from gcp_pipeline_builder.clients.pubsub_client import PubSubClient
from gcp_pipeline_builder.audit.records import AuditRecord

class AuditPublisher:
    """Publishes audit records to Pub/Sub."""

    def __init__(self, project_id: str, topic_name: str):
        """
        Initialize the audit publisher.

        Args:
            project_id: GCP Project ID
            topic_name: Pub/Sub topic name for audit events
        """
        self.project_id = project_id
        self.topic_name = topic_name
        self.pubsub_client = PubSubClient(project=project_id)

    def publish(self, record: AuditRecord) -> str:
        """
        Publish an audit record to Pub/Sub.

        Args:
            record: The AuditRecord to publish

        Returns:
            Message ID from Pub/Sub
        """
        message = self._prepare_message(record)
        return self.pubsub_client.publish_event(self.topic_name, message)

    def _prepare_message(self, record: AuditRecord) -> Dict[str, Any]:
        """Convert AuditRecord to a JSON-serializable dictionary."""
        message = dataclasses.asdict(record)

        # Handle datetime serialization
        for key, value in message.items():
            if isinstance(value, datetime):
                message[key] = value.isoformat()

        return message
