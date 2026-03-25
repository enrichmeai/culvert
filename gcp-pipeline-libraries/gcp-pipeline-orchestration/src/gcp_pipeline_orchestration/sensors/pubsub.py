"""
Base Pub/Sub Sensor with enhanced filtering and metadata extraction.

Provides a reusable sensor that extends Airflow's PubSubPullSensor with:
- Configurable file extension filtering (e.g., .ok files)
- Standardized metadata extraction to XCom
- Error handling for malformed messages

Usage:
    from gcp_pipeline_orchestration.sensors import BasePubSubPullSensor

    sensor = BasePubSubPullSensor(
        task_id='wait_for_file',
        project_id='my-project',
        subscription='notifications-sub',
        filter_extension='.ok',
        metadata_xcom_key='file_metadata',
    )
"""

from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

# Try to import Airflow - if not available, create a stub class
try:
    from airflow.providers.google.cloud.sensors.pubsub import PubSubPullSensor
    from airflow.providers.google.cloud.hooks.pubsub import PubSubHook
    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False
    PubSubPullSensor = object  # Stub for type hints
    PubSubHook = None


class BasePubSubPullSensor(PubSubPullSensor if AIRFLOW_AVAILABLE else object):
    """
    Enhanced PubSubPullSensor with file filtering and metadata extraction.

    Features:
    - Configurable file extension filtering
    - Standardized metadata extraction to XCom
    - Error handling for malformed messages
    - Retry configuration support

    Args:
        filter_extension: File extension to filter for (e.g., '.ok', '.done')
        metadata_xcom_key: XCom key for pushing extracted metadata
        extract_metadata: Whether to extract and push metadata to XCom
        *args: Passed to PubSubPullSensor
        **kwargs: Passed to PubSubPullSensor

    Example:
        >>> sensor = BasePubSubPullSensor(
        ...     task_id='wait_for_file',
        ...     project_id='my-project',
        ...     subscription='notifications-sub',
        ...     filter_extension='.ok',
        ...     metadata_xcom_key='file_metadata',
        ... )
    """

    def __init__(
        self,
        *args,
        ack_messages: bool = True,
        filter_extension: Optional[str] = None,
        metadata_xcom_key: str = "file_metadata",
        extract_metadata: bool = True,
        **kwargs
    ):
        if not AIRFLOW_AVAILABLE:
            raise ImportError(
                "apache-airflow-providers-google is required for PubSub sensors. "
                "Install with: pip install apache-airflow-providers-google"
            )
        super().__init__(*args, ack_messages=ack_messages, **kwargs)
        self.filter_extension = filter_extension
        self.metadata_xcom_key = metadata_xcom_key
        self.extract_metadata = extract_metadata

    def poke(self, context) -> bool:
        """
        Pull messages, filter by extension BEFORE acking.

        Without this override, the parent's poke() acks all pulled messages
        immediately. If a non-matching message (e.g. .csv notification) is
        pulled, it gets acked and discarded, and poke returns True — ending
        the sensor prematurely. This override filters first: non-matching
        messages are acked (to clear them) but poke returns False so the
        sensor keeps looking for a matching message.
        """
        if not self.filter_extension:
            return super().poke(context)

        hook = PubSubHook(
            gcp_conn_id=self.gcp_conn_id,
            impersonation_chain=self.impersonation_chain,
        )

        pulled_messages = hook.pull(
            project_id=self.project_id,
            subscription=self.subscription,
            max_messages=self.max_messages,
            return_immediately=self.return_immediately,
        )

        if not pulled_messages:
            return False

        # Convert raw messages to serializable dicts for filtering
        handle_messages = self.messages_callback or self._default_message_callback
        all_converted = handle_messages(pulled_messages, context)
        filtered = self._filter_by_extension(all_converted) if all_converted else []

        # Always ack pulled messages to clear them from the subscription
        if self.ack_messages:
            hook.acknowledge(
                project_id=self.project_id,
                subscription=self.subscription,
                messages=pulled_messages,
            )

        if filtered:
            self._return_value = filtered
            return True

        # No matching messages — keep poking
        return False

    def execute(self, context: Dict[str, Any]) -> Optional[List[Dict]]:
        """
        Execute sensor and optionally push metadata to XCom.

        When filter_extension is set, poke() handles filtering before acking.
        This method receives already-filtered messages via _return_value.

        Args:
            context: Airflow task context

        Returns:
            List of filtered messages or None if no matching messages
        """
        messages = super().execute(context)

        if not messages:
            logger.info("No messages received")
            return None

        # When filter_extension is set, poke() already filtered — skip re-filtering.
        # When filter_extension is not set, messages come from parent poke() unfiltered.
        if self.filter_extension:
            # poke() already filtered; messages is self._return_value
            pass
        else:
            pass  # No filtering needed

        # Extract and push metadata if enabled
        if self.extract_metadata and messages:
            try:
                message = messages[0]
                metadata = self._extract_metadata(message)
                context['ti'].xcom_push(key=self.metadata_xcom_key, value=metadata)
                logger.info("Extracted metadata for: %s", metadata.get('gcs_path'))
            except (KeyError, IndexError, TypeError) as exc:
                logger.error("Error extracting metadata: %s", exc)

        return messages

    def _filter_by_extension(self, messages: List[Dict]) -> List[Dict]:
        """
        Filter messages to only include files with specified extension.

        Args:
            messages: List of Pub/Sub messages

        Returns:
            Filtered list containing only matching file messages
        """
        import json
        import base64
        
        filtered = []

        for msg in messages:
            try:
                # Handle different message formats from PubSubPullSensor
                # Format 1: Direct message dict with 'message' key
                # Format 2: ReceivedMessage object
                if hasattr(msg, 'message'):
                    payload = msg.message
                    attributes = dict(payload.attributes) if payload.attributes else {}
                    data = payload.data
                else:
                    payload = msg.get('message', msg)
                    attributes = payload.get('attributes', {})
                    data = payload.get('data', '')

                # Try to get object name from attributes first
                object_name = attributes.get('objectId', '')
                
                # If not in attributes, try to parse from data (JSON payload)
                if not object_name and data:
                    try:
                        # Data might be base64 encoded
                        if isinstance(data, bytes):
                            data_str = data.decode('utf-8')
                        elif isinstance(data, str):
                            try:
                                data_str = base64.b64decode(data).decode('utf-8')
                            except Exception:
                                data_str = data
                        else:
                            data_str = str(data)
                        
                        data_json = json.loads(data_str)
                        object_name = data_json.get('name', '')
                    except (json.JSONDecodeError, Exception) as e:
                        logger.debug(f"Could not parse message data as JSON: {e}")

                if object_name and object_name.endswith(self.filter_extension):
                    filtered.append(msg)
                    logger.info(f"Found matching file: {object_name}")
                else:
                    logger.debug(f"Skipping file (no match for {self.filter_extension}): {object_name}")

            except Exception as exc:
                logger.warning("Error filtering message: %s", exc)
                continue

        return filtered

    def _extract_metadata(self, message: Dict) -> Dict[str, Any]:
        """
        Extract standardized metadata from message.

        Override this method in subclasses for custom metadata extraction.

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


class PubSubCompletionSensor(BasePubSubPullSensor):
    """
    Sensor that waits for a "Job Finished" message in Pub/Sub.

    Allows downstream tasks to trigger instantly upon batch completion.
    """

    def __init__(
        self,
        *args,
        expected_status: str = "SUCCESS",
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.expected_status = expected_status

    def execute(self, context: Dict[str, Any]) -> Optional[List[Dict]]:
        messages = super().execute(context)
        if not messages:
            return None

        filtered_messages = []
        for msg in messages:
            payload = msg.get('message', {})
            attributes = payload.get('attributes', {})
            
            # Check for completion status
            status = attributes.get('status')
            if status == self.expected_status:
                filtered_messages.append(msg)
                logger.info(f"Received expected completion status: {status}")
            else:
                logger.debug(f"Ignoring message with status: {status}")

        return filtered_messages if filtered_messages else None


__all__ = ['BasePubSubPullSensor', 'PubSubCompletionSensor', 'AIRFLOW_AVAILABLE']

