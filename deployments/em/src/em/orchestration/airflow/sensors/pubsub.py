"""
LOA Pub/Sub Sensor - Enhanced with .ok file filtering.

LOA-specific sensor extending the base sensor from gcp_pipeline_builder.
Pre-configured with LOA defaults.
"""

from gcp_pipeline_builder.orchestration.sensors import BasePubSubPullSensor
import logging

logger = logging.getLogger(__name__)


class LOAPubSubPullSensor(BasePubSubPullSensor):
    """
    LOA-specific PubSubPullSensor.

    Pre-configured with:
    - .ok file filtering enabled
    - XCom key 'loa_metadata'

    Example:
        >>> sensor = LOAPubSubPullSensor(
        ...     task_id='wait_for_file',
        ...     project_id='my-project',
        ...     subscription='loa-processing-notifications-sub',
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
        Initialize LOA sensor.

        Args:
            ack_messages: Whether to automatically acknowledge messages
            filter_ok_files: If True, only process .ok file events
            *args: Passed to BasePubSubPullSensor
            **kwargs: Passed to BasePubSubPullSensor
        """
        # Set LOA-specific defaults
        filter_extension = '.ok' if filter_ok_files else None

        super().__init__(
            *args,
            ack_messages=ack_messages,
            filter_extension=filter_extension,
            metadata_xcom_key='loa_metadata',
            extract_metadata=True,
            **kwargs
        )

        # Keep for backwards compatibility
        self.filter_ok_files = filter_ok_files


__all__ = ['LOAPubSubPullSensor']

