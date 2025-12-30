"""
Orchestration utilities for LOA Blueprint.
"""

from typing import Optional, Dict, Any
from airflow.providers.google.cloud.sensors.pubsub import PubSubPullSensor

class LOAPubSubPullSensor(PubSubPullSensor):
    """
    Specialized PubSubPullSensor for LOA Blueprint.
    Automatically handles message acknowledgement and standardized metadata extraction.
    """

    def __init__(
        self,
        *args,
        ack_messages: bool = True,
        **kwargs
    ):
        super().__init__(*args, ack_messages=ack_messages, **kwargs)

    def execute(self, context: Dict[str, Any]):
        """
        Executes the sensor and pushes metadata to XCom.
        """
        messages = super().execute(context)
        if not messages:
            return None

        # Process the first message for metadata (standard LOA pattern)
        message = messages[0]
        payload = message.get('message', {})
        attributes = payload.get('attributes', {})

        # Standard LOA Metadata Extraction
        metadata = {
            'gcs_path': attributes.get('gcs_path') or attributes.get('objectId'),
            'bucket': attributes.get('bucketId'),
            'system_id': attributes.get('system_id'),
            'entity_type': attributes.get('entity_type'),
            'event_type': attributes.get('eventType'),
            'publish_time': payload.get('publishTime'),
            'message_id': payload.get('messageId')
        }

        # Push metadata to XCom for downstream operators (e.g., PipelineSelector)
        context['ti'].xcom_push(key='loa_metadata', value=metadata)

        return messages
