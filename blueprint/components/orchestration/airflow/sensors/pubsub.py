"""
LOA Pub/Sub Sensor - Enhanced with .ok file filtering.

This module provides a specialized PubSubPullSensor for the LOA Blueprint
that automatically handles message acknowledgement, .ok file filtering,
and standardized metadata extraction.
"""

from typing import Optional, Dict, Any, List
from airflow.providers.google.cloud.sensors.pubsub import PubSubPullSensor
import logging

logger = logging.getLogger(__name__)


class LOAPubSubPullSensor(PubSubPullSensor):
    """
    Specialized PubSubPullSensor for LOA Blueprint.

    Features:
    - Automatic .ok file filtering (configurable)
    - Standardized metadata extraction to XCom
    - Error handling for malformed messages
    - Retry configuration support

    Example:
        >>> sensor = LOAPubSubPullSensor(
        ...     task_id='wait_for_file',
        ...     project_id='my-project',
        ...     subscription='loa-processing-notifications-sub',
        ...     filter_ok_files=True,
        ... )
    """

    def __init__(
        self,
        *args,
        ack_messages: bool = True,
        filter_ok_files: bool = True,
        **kwargs
    ):
        """
        Initialize sensor.

        Args:
            ack_messages: Whether to automatically acknowledge messages
            filter_ok_files: If True, only process .ok file events
            *args: Passed to PubSubPullSensor
            **kwargs: Passed to PubSubPullSensor
        """
        super().__init__(*args, ack_messages=ack_messages, **kwargs)
        self.filter_ok_files = filter_ok_files

    def execute(self, context: Dict[str, Any]) -> Optional[List[Dict]]:
        """
        Execute sensor and push metadata to XCom.

        Returns messages after filtering for .ok files if configured.
        Extracts metadata from the first message and pushes to XCom.

        Args:
            context: Airflow task context

        Returns:
            List of filtered messages or None if no matching messages
        """
        messages = super().execute(context)

        if not messages:
            logger.info("No messages received")
            return None

        # Filter for .ok files if enabled
        if self.filter_ok_files:
            messages = self._filter_ok_files(messages)
            if not messages:
                logger.info("No .ok files in received messages")
                return None

        # Process the first message for metadata
        try:
            message = messages[0]
            metadata = self._extract_metadata(message)

            # Push metadata to XCom for downstream operators
            context['ti'].xcom_push(key='loa_metadata', value=metadata)
            logger.info("Extracted metadata for: %s", metadata.get('gcs_path'))

        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Error extracting metadata: %s", exc)
            # Still return messages for processing

        return messages

    def _filter_ok_files(self, messages: List[Dict]) -> List[Dict]:
        """
        Filter messages to only include .ok file events.

        Args:
            messages: List of Pub/Sub messages

        Returns:
            Filtered list containing only .ok file messages
        """
        filtered = []

        for msg in messages:
            try:
                payload = msg.get('message', {})
                attributes = payload.get('attributes', {})

                # Get object name from GCS notification
                # Support multiple attribute formats
                object_name = (
                    attributes.get('objectId') or
                    attributes.get('gcs_path', '').split('/')[-1] or
                    attributes.get('name', '')
                )

                if object_name and object_name.endswith('.ok'):
                    filtered.append(msg)
                    logger.debug("Found .ok file: %s", object_name)

            except Exception as exc:
                logger.warning("Error filtering message: %s", exc)
                continue

        return filtered

    def _extract_metadata(self, message: Dict) -> Dict[str, Any]:
        """
        Extract standardized metadata from message.

        Args:
            message: Pub/Sub message dict

        Returns:
            Extracted metadata dict
        """
        payload = message.get('message', {})
        attributes = payload.get('attributes', {})

        # Construct full GCS path if individual components available
        gcs_path = attributes.get('gcs_path') or attributes.get('objectId')
        if not gcs_path and attributes.get('bucketId') and attributes.get('objectId'):
            gcs_path = f"gs://{attributes['bucketId']}/{attributes['objectId']}"

        return {
            'gcs_path': gcs_path,
            'bucket': attributes.get('bucketId'),
            'object_id': attributes.get('objectId'),
            'system_id': attributes.get('system_id'),
            'entity_type': attributes.get('entity_type'),
            'event_type': attributes.get('eventType'),
            'publish_time': payload.get('publishTime'),
            'message_id': payload.get('messageId'),
            'object_generation': attributes.get('objectGeneration'),
            'event_time': attributes.get('eventTime'),
        }

