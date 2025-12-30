import unittest
from unittest.mock import MagicMock, patch
import sys
from typing import Dict, Any

# Create a dummy base class
class DummyPubSubPullSensor:
    def __init__(self, *args, **kwargs):
        pass
    def execute(self, context):
        return []

# Mock airflow.providers.google.cloud.sensors.pubsub.PubSubPullSensor
mock_airflow = MagicMock()
sys.modules['airflow'] = mock_airflow
sys.modules['airflow.providers'] = mock_airflow.providers
sys.modules['airflow.providers.google'] = mock_airflow.providers.google
sys.modules['airflow.providers.google.cloud'] = mock_airflow.providers.google.cloud
sys.modules['airflow.providers.google.cloud.sensors'] = mock_airflow.providers.google.cloud.sensors
sys.modules['airflow.providers.google.cloud.sensors.pubsub'] = mock_airflow.providers.google.cloud.sensors.pubsub
mock_airflow.providers.google.cloud.sensors.pubsub.PubSubPullSensor = DummyPubSubPullSensor

from blueprint.components.orchestration.airflow.sensors.pubsub import LOAPubSubPullSensor

class TestLOAPubSubPullSensor(unittest.TestCase):
    def test_execute_metadata_extraction(self):
        # Mock context and task instance
        mock_ti = MagicMock()
        context = {'ti': mock_ti}

        # Mock messages from PubSub
        mock_messages = [
            {
                'message': {
                    'attributes': {
                        'gcs_path': 'gs://bucket/file.csv',
                        'system_id': 'SYS001',
                        'entity_type': 'applications'
                    },
                    'publishTime': '2023-01-01T00:00:00Z',
                    'messageId': 'msg123'
                }
            }
        ]

        # Patch the DummyPubSubPullSensor.execute call
        with patch.object(DummyPubSubPullSensor, 'execute', return_value=mock_messages):
            sensor = LOAPubSubPullSensor(
                task_id='test_sensor',
                project_id='test-project',
                subscription='test-sub'
            )

            result = sensor.execute(context)

            # Verify results
            self.assertEqual(result, mock_messages)

            # Verify XCom push
            mock_ti.xcom_push.assert_called_once()
            args, kwargs = mock_ti.xcom_push.call_args
            self.assertEqual(kwargs['key'], 'loa_metadata')
            metadata = kwargs['value']
            self.assertEqual(metadata['gcs_path'], 'gs://bucket/file.csv')
            self.assertEqual(metadata['system_id'], 'SYS001')
            self.assertEqual(metadata['entity_type'], 'applications')

if __name__ == '__main__':
    unittest.main()
